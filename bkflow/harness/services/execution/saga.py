"""Approval-bound durable create/start Saga for Harness executions."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from bkflow.harness.constants import HarnessAction, HarnessRunStatus, RiskLevel
from bkflow.harness.contracts import HarnessContextError
from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.models import (
    ApprovalRequest,
    CapabilityBinding,
    ExecutionRun,
    HarnessIdempotencyRecord,
    HarnessRun,
    ReleaseManifest,
    ReleasePublication,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.safety import safe_opaque_identifier
from bkflow.harness.services.approval import (
    ApprovalInvalid,
    ApprovalVerifier,
    normalize_approval_decision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.contract_versions import require_tool_enabled
from bkflow.harness.services.debug.policy import context_matches_run
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.execution.adapter import (
    ApplicationTaskAdapter,
    BoundCredentialResolver,
    CreateDispatchRejected,
    CreateDispatchUncertain,
    StartDispatchRejected,
    StartDispatchUncertain,
)
from bkflow.harness.services.execution.contracts import (
    StartExecutionRejected,
    validate_start_execution_request,
)
from bkflow.harness.services.idempotency import (
    IdempotencyScope,
    acquire_idempotency,
    bind_inflight_idempotency,
    complete_idempotency,
)
from bkflow.harness.services.release.policy import (
    ActionPolicy,
    ReleasePolicyUnavailable,
)
from bkflow.harness.services.release.prepare import (
    ReleasePreparationRejected,
    _canonicalize_lists,
    revalidate_revision_for_release,
)
from bkflow.harness.services.resolver import (
    CapabilityResolver,
    ProviderInfrastructureError,
)
from bkflow.harness.services.validator import (
    WorkflowValidationFailure,
    WorkflowValidator,
)
from bkflow.task.services.task_creator import TaskCreationReceipt
from bkflow.template.models import Template, TemplateSnapshot

TOOL_NAME = HarnessAction.START_WORKFLOW_EXECUTION
_START_PROVEN_ENGINE_STATES = frozenset({"RUNNING", "SUSPENDED", "FINISHED", "FAILED", "REVOKED", "CANCELLED"})
CREATE_DISPATCH_BARRIER_TTL = timezone.timedelta(seconds=30)
_SAFE_CREATE_WARNING_CODES = frozenset({"TASK_CREATE_NOTIFICATION_FAILED"})


@dataclass(frozen=True)
class _PreflightFacts:
    capability_snapshot: list
    binding_signature: tuple
    validation_report_id: int
    validation_report_fingerprint: str
    run_artifact_fingerprint: str
    snapshot_fingerprint: str


def _execution_artifact(execution):
    return {
        "type": "workflow_execution",
        "execution_id": str(execution.id),
        "task_ref": execution.task_ref,
        "execution_status": execution.status,
        "last_engine_state": execution.last_engine_state,
    }


def _success(context, run, revision, execution):
    response = WorkflowValidator(context, resolver=object())._envelope(
        ok=True,
        run=run,
        revision=revision,
        plan_hash_value=revision.plan_hash,
        status=run.status,
        artifact_refs=[_execution_artifact(execution)],
    )
    response["summary"] = "Workflow execution was started."
    response["next_actions"] = [HarnessAction.GET_WORKFLOW_EXECUTION]
    return response


def _failure(context, rejection, *, run=None, revision=None, execution=None):
    error = WorkflowValidationFailure(
        rejection.code,
        path=rejection.path,
        category=rejection.category,
        repairable=rejection.repairable,
        retryable=rejection.retryable,
    ).as_error()
    response = WorkflowValidator(context, resolver=object())._envelope(
        ok=False,
        run=run,
        revision=revision,
        plan_hash_value=revision.plan_hash if revision else None,
        status=run.status if run else None,
        errors=[error],
        artifact_refs=[_execution_artifact(execution)] if execution else [],
    )
    response["summary"] = "Workflow execution is blocked."
    if rejection.approval_request_id is not None:
        response["approval_request_id"] = str(rejection.approval_request_id)
    if rejection.manual_reconcile:
        response["next_actions"] = ["manual_reconcile_execution"]
    return response


def _load_seed(context, request):
    try:
        run = HarnessRun.objects.get(run_id=request.run_id)
        manifest = ReleaseManifest.objects.select_related("revision").get(pk=request.manifest_id, run=run)
        publication = ReleasePublication.objects.select_related("manifest__run").get(
            pk=request.publication_id, manifest=manifest
        )
    except (HarnessRun.DoesNotExist, ReleaseManifest.DoesNotExist, ReleasePublication.DoesNotExist):
        raise StartExecutionRejected(
            "CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False
        ) from None
    if not context_matches_run(context, run):
        raise StartExecutionRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False)
    if manifest.plan_hash != request.expected_plan_hash:
        raise StartExecutionRejected("VALIDATION_STALE", "expected_plan_hash")
    if run.status not in {HarnessRunStatus.PUBLISHED, HarnessRunStatus.EXECUTING}:
        raise StartExecutionRejected("VALIDATION_STALE", "run_id", repairable=False)
    return run, manifest, publication


def _policy_decision(context, manifest, publication, request, action_policy, release_policy):
    try:
        expected_postconditions = _canonicalize_lists(release_policy.postconditions_for(context.policy_version))
        expected_requirements = _canonicalize_lists(
            action_policy.requirements_for(
                [HarnessAction.PUBLISH_WORKFLOW, HarnessAction.START_WORKFLOW_EXECUTION],
                context.policy_version,
            )
        )
        if (
            manifest.policy_version != context.policy_version
            or manifest.target_environment != context.target_environment
            or manifest.postcondition_spec != expected_postconditions
            or manifest.required_approvals != expected_requirements
        ):
            raise StartExecutionRejected("VALIDATION_STALE", "policy", repairable=False)
        decision = action_policy.evaluate(
            action=HarnessAction.START_WORKFLOW_EXECUTION,
            manifest_hash=manifest.manifest_hash,
            plan_hash=manifest.plan_hash,
            target_resource={
                "publication_id": str(publication.id),
                "template_id": publication.published_template_id,
                "snapshot_id": publication.published_snapshot_id,
                "version": publication.published_version,
                "target_environment": manifest.target_environment,
            },
            normalized_params={"constants": request.constants, "name": request.name},
            policy_version=manifest.policy_version,
        )
        start_requirements = [
            item for item in expected_requirements if item.get("action") == HarnessAction.START_WORKFLOW_EXECUTION
        ]
        if (
            len(start_requirements) != 1
            or start_requirements[0].get("risk_level") != RiskLevel.L2
            or decision.action != HarnessAction.START_WORKFLOW_EXECUTION
            or decision.risk_level != RiskLevel.L2
            or decision.requires_approval is not True
        ):
            raise StartExecutionRejected("VALIDATION_STALE", "policy", repairable=False)
        return decision
    except (ReleasePolicyUnavailable, DjangoValidationError):
        raise StartExecutionRejected("VALIDATION_STALE", "policy", repairable=False) from None


def _approval_claims(context, run, manifest, decision):
    return {
        "actor": context.actor,
        "platform_app": context.platform_app,
        "space_id": context.space_id,
        "scope": run.scope,
        "environment": context.target_environment,
        "plan_hash": manifest.plan_hash,
        "action": HarnessAction.START_WORKFLOW_EXECUTION,
        "action_digest": decision.action_digest,
    }


def _approval_matches(approval, context, run, manifest, decision):
    return (
        approval.manifest_id == manifest.id
        and approval.run_id == run.id
        and approval.revision_id == manifest.revision_id
        and approval.plan_hash == manifest.plan_hash
        and approval.action == HarnessAction.START_WORKFLOW_EXECUTION
        and approval.action_digest == decision.action_digest
        and approval.platform == context.platform_key
        and approval.platform_app == context.platform_app
        and approval.actor == context.actor
        and approval.space_id == context.space_id
        and approval.scope == run.scope
        and approval.target_environment == context.target_environment
        and approval.policy_version == context.policy_version
        and approval.risk_level == decision.risk_level
    )


def _binding_signature(bindings):
    return tuple(
        (
            binding.id,
            binding.node_id,
            binding.capability_ref,
            binding.resolved_version,
            binding.schema_hash,
            binding.conversion_fingerprint,
            binding.credential_ref,
            binding.risk,
        )
        for binding in bindings
    )


def _lock_authority(
    context,
    request,
    seed_manifest,
    seed_publication,
    *,
    action_policy,
    release_policy,
    preflight=None,
    approval_id=None,
    execution_id=None,
    require_active_approval=False,
):
    """Lock the shared graph in one deterministic order without external calls."""
    template = Template.objects.select_for_update().get(pk=seed_publication.published_template_id)
    run = HarnessRun.objects.select_for_update().get(pk=seed_manifest.run_id)
    if not context_matches_run(context, run):
        raise StartExecutionRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False)
    if run.status not in {
        HarnessRunStatus.PUBLISHED,
        HarnessRunStatus.EXECUTING,
    }:
        raise StartExecutionRejected("VALIDATION_STALE", "run_id", repairable=False)
    revision = WorkflowPlanRevision.objects.select_for_update().get(pk=seed_manifest.revision_id, run=run)
    latest_revision = WorkflowPlanRevision.objects.select_for_update().filter(run=run).order_by("-sequence").first()
    snapshot = TemplateSnapshot.objects.select_for_update().get(pk=seed_publication.published_snapshot_id)
    reports = list(
        ValidationReport.objects.select_for_update().filter(run=run, checkpoint="VALIDATE").order_by("-id")[:2]
    )
    bindings = list(
        CapabilityBinding.objects.select_for_update().filter(revision=revision).order_by("node_id", "capability_ref")
    )
    manifest = ReleaseManifest.objects.select_for_update().get(pk=seed_manifest.pk, run=run)
    approval = None
    if approval_id is not None:
        approval = ApprovalRequest.objects.select_for_update().get(pk=approval_id, manifest=manifest)
    else:
        list(
            ApprovalRequest.objects.select_for_update()
            .filter(manifest=manifest, action=HarnessAction.START_WORKFLOW_EXECUTION)
            .order_by("id")
        )
    publication = ReleasePublication.objects.select_for_update().get(pk=seed_publication.pk, manifest=manifest)
    execution = None
    if execution_id is not None:
        execution = ExecutionRun.objects.select_for_update().get(pk=execution_id, manifest=manifest)
    else:
        execution = (
            ExecutionRun.objects.select_for_update()
            .filter(manifest=manifest, start_idempotency_key=request.idempotency_key)
            .first()
        )
    if (
        manifest.plan_hash != request.expected_plan_hash
        or latest_revision is None
        or latest_revision.id != revision.id
        or manifest.revision_id != revision.id
        or manifest.draft_template_id != template.id
        or manifest.draft_snapshot_id != snapshot.id
        or publication.published_template_id != template.id
        or publication.published_snapshot_id != snapshot.id
        or publication.published_version != snapshot.version
        or snapshot.template_id != template.id
        or snapshot.draft
        or snapshot.is_deleted
        or template.is_deleted
        or template.space_id != context.space_id
        or template.scope_type != context.scope_type
        or template.scope_value != context.scope_value
        or template.bk_app_code != context.platform_app
    ):
        raise StartExecutionRejected("VALIDATION_STALE", "publication", repairable=False)
    decision = _policy_decision(context, manifest, publication, request, action_policy, release_policy)
    if approval is not None:
        if not _approval_matches(approval, context, run, manifest, decision):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
        if require_active_approval and (
            approval.status != ApprovalRequest.Status.VERIFIED
            or approval.receipt_ref != request.approval_receipt_ref
            or not approval.receipt_digest
            or not approval.verifier_version
            or approval.expires_at is None
            or approval.expires_at <= timezone.now()
        ):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
    if preflight is not None:
        if (
            not reports
            or reports[0].id != preflight.validation_report_id
            or sha256_json(
                {
                    "checkpoint": reports[0].checkpoint,
                    "errors": reports[0].errors,
                    "result": reports[0].result,
                    "validator_version": reports[0].validator_version,
                    "revision_id": str(reports[0].revision_id),
                }
            )
            != preflight.validation_report_fingerprint
            or sha256_json(run.artifact_references) != preflight.run_artifact_fingerprint
            or sha256_json(snapshot.data) != preflight.snapshot_fingerprint
            or _binding_signature(bindings) != preflight.binding_signature
            or manifest.capability_snapshot != preflight.capability_snapshot
        ):
            raise StartExecutionRejected("VALIDATION_STALE", "bindings", repairable=False)
    return template, run, revision, snapshot, bindings, manifest, approval, publication, execution, decision


def _approval_values(context, run, manifest, request, decision):
    return {
        "manifest": manifest,
        "run": run,
        "revision": manifest.revision,
        "plan_hash": manifest.plan_hash,
        "action": HarnessAction.START_WORKFLOW_EXECUTION,
        "action_digest": decision.action_digest,
        "platform": context.platform_key,
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope": run.scope,
        "target_environment": context.target_environment,
        "policy_version": context.policy_version,
        "risk_level": decision.risk_level,
        "risk_summary": {
            "action": HarnessAction.START_WORKFLOW_EXECUTION,
            "publication_id": str(manifest.publication.id),
            "task_name_digest": sha256_json(request.name),
        },
    }


def _request_approval(context, request, run, manifest, publication, *, action_policy, release_policy):
    with transaction.atomic():
        _, locked_run, revision, _, _, locked_manifest, _, locked_publication, _, decision = _lock_authority(
            context,
            request,
            manifest,
            publication,
            action_policy=action_policy,
            release_policy=release_policy,
        )
        existing = (
            ApprovalRequest.objects.select_for_update()
            .filter(
                manifest=locked_manifest,
                action=HarnessAction.START_WORKFLOW_EXECUTION,
                action_digest=decision.action_digest,
                status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED],
            )
            .first()
        )
        if existing is None:
            try:
                with transaction.atomic():
                    existing = ApprovalRequest.objects.create(
                        **_approval_values(context, locked_run, locked_manifest, request, decision)
                    )
            except IntegrityError:
                existing = ApprovalRequest.objects.select_for_update().get(
                    manifest=locked_manifest,
                    action=HarnessAction.START_WORKFLOW_EXECUTION,
                    action_digest=decision.action_digest,
                    status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED],
                )
        if not _approval_matches(existing, context, locked_run, locked_manifest, decision):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
        if locked_publication.id != publication.id:
            raise StartExecutionRejected("VALIDATION_STALE", "publication", repairable=False)
        return existing


def _verify_approval_outside_transaction(context, request, run, manifest, decision, approval, verifier):
    if not _approval_matches(approval, context, run, manifest, decision):
        raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
    if approval.status == ApprovalRequest.Status.VERIFIED:
        if (
            approval.receipt_ref != request.approval_receipt_ref
            or approval.expires_at is None
            or approval.expires_at <= timezone.now()
        ):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
        return None
    if approval.status != ApprovalRequest.Status.PENDING:
        raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
    try:
        result = normalize_approval_decision(
            (verifier or ApprovalVerifier()).verify(
                request.approval_receipt_ref,
                _approval_claims(context, run, manifest, decision),
            ),
            request.approval_receipt_ref,
        )
    except ApprovalInvalid:
        raise StartExecutionRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False) from None
    if not result.allowed:
        raise StartExecutionRejected(
            result.failure_code,
            "approval_receipt_ref",
            repairable=False,
            approval_request_id=approval.id,
        )
    return result


def _persist_verified(approval, request, decision_result):
    if approval.status == ApprovalRequest.Status.VERIFIED:
        if approval.receipt_ref != request.approval_receipt_ref or approval.expires_at <= timezone.now():
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
        return
    if approval.status != ApprovalRequest.Status.PENDING or decision_result is None:
        raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
    approval.status = ApprovalRequest.Status.VERIFIED
    approval.approver = decision_result.provider
    approval.receipt_provider = decision_result.provider
    approval.receipt_ref = request.approval_receipt_ref
    approval.receipt_digest = decision_result.receipt_digest
    approval.verified_at = timezone.now()
    approval.expires_at = decision_result.expires_at
    approval.verifier_version = decision_result.verifier_version
    approval.save(
        update_fields=[
            "status",
            "approver",
            "receipt_provider",
            "receipt_ref",
            "receipt_digest",
            "verified_at",
            "expires_at",
            "verifier_version",
            "active_approval_key",
            "update_at",
        ]
    )


def _commit_verified_approval(
    context,
    request,
    run,
    manifest,
    publication,
    approval,
    decision_result,
    *,
    action_policy,
    release_policy,
):
    with transaction.atomic():
        _, locked_run, _, _, _, locked_manifest, locked_approval, _, _, decision = _lock_authority(
            context,
            request,
            manifest,
            publication,
            action_policy=action_policy,
            release_policy=release_policy,
            approval_id=approval.id,
        )
        if not _approval_matches(locked_approval, context, locked_run, locked_manifest, decision):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
        if decision_result is not None and decision_result.claims_digest != sha256_json(
            _approval_claims(context, locked_run, locked_manifest, decision)
        ):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
        _persist_verified(locked_approval, request, decision_result)
        return locked_approval


def _invalidate_start_approval(run, approval):
    """Revoke only start authority; a completed Publication remains immutable."""
    with transaction.atomic():
        HarnessRun.objects.select_for_update().get(pk=run.pk)
        locked = ApprovalRequest.objects.select_for_update().get(pk=approval.pk, run=run)
        if locked.status in {ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED}:
            locked.status = ApprovalRequest.Status.REVOKED
            locked.save(update_fields=["status", "active_approval_key", "update_at"])


class _CachingResolver:
    """Retain the exact capabilities produced by one fresh provider pass."""

    def __init__(self, delegate):
        self._delegate = delegate
        self._resolved = {}

    def resolve(self, capability_ref, expected_schema_hash=None):
        key = (capability_ref, expected_schema_hash)
        if key not in self._resolved:
            self._resolved[key] = self._delegate.resolve(capability_ref, expected_schema_hash=expected_schema_hash)
        return self._resolved[key]


def _preflight_schema(
    context,
    run,
    manifest,
    publication,
    *,
    resolver,
    converter_class,
    pipeline_validator,
):
    template = Template.objects.get(pk=publication.published_template_id)
    snapshot = TemplateSnapshot.objects.get(pk=publication.published_snapshot_id)
    revision = WorkflowPlanRevision.objects.get(pk=manifest.revision_id, run=run)
    caching_resolver = _CachingResolver(resolver)
    facts = revalidate_revision_for_release(
        context,
        run,
        revision,
        template,
        snapshot,
        resolver=caching_resolver,
        lock_rows=False,
        converter_class=converter_class,
        pipeline_validator=pipeline_validator,
        allow_published_snapshot=True,
        allow_template_pointer_advance=True,
    )
    bindings = list(CapabilityBinding.objects.filter(revision=revision).order_by("node_id", "capability_ref"))
    report = ValidationReport.objects.filter(run=run, checkpoint="VALIDATE").order_by("-id").first()
    if report is None or facts.capability_snapshot != manifest.capability_snapshot:
        raise StartExecutionRejected("VALIDATION_STALE", "bindings", repairable=False)
    resolved_bindings = [
        {
            "binding": binding,
            "capability": caching_resolver.resolve(binding.capability_ref, expected_schema_hash=binding.schema_hash),
        }
        for binding in bindings
    ]
    report_fingerprint = sha256_json(
        {
            "checkpoint": report.checkpoint,
            "errors": report.errors,
            "result": report.result,
            "validator_version": report.validator_version,
            "revision_id": str(report.revision_id),
        }
    )
    return (
        _PreflightFacts(
            facts.capability_snapshot,
            _binding_signature(bindings),
            report.id,
            report_fingerprint,
            sha256_json(run.artifact_references),
            sha256_json(snapshot.data),
        ),
        resolved_bindings,
    )


def _resolve_credentials(context, resolved_bindings, credential_resolver):
    return credential_resolver.resolve(
        resolved_bindings,
        space_id=context.space_id,
        scope_type=context.scope_type,
        scope_value=context.scope_value,
    )


class ExecutionSaga:
    """Persist each create/start boundary before crossing the Engine API."""

    def __init__(
        self,
        context,
        request,
        run,
        manifest,
        publication,
        approval,
        *,
        preflight,
        credentials,
        action_policy,
        release_policy,
        adapter,
        test_after_task_persist_hook=None,
        test_after_create_barrier_hook=None,
        test_before_create_barrier_hook=None,
        test_before_start_barrier_hook=None,
    ):
        self.context = context
        self.request = request
        self.run = run
        self.manifest = manifest
        self.publication = publication
        self.approval = approval
        self.preflight = preflight
        self.credentials = credentials
        self.action_policy = action_policy
        self.release_policy = release_policy
        self.adapter = adapter
        self.test_after_task_persist_hook = test_after_task_persist_hook
        self.test_after_create_barrier_hook = test_after_create_barrier_hook
        self.test_before_create_barrier_hook = test_before_create_barrier_hook
        self.test_before_start_barrier_hook = test_before_start_barrier_hook
        self.scope = IdempotencyScope.for_run(
            context.platform_app,
            context.actor,
            context.space_id,
            TOOL_NAME,
            run,
            request.idempotency_key,
        )
        self.request_hash = sha256_json({"request": request.action_payload(), "trusted_run_id": str(run.run_id)})

    def _record(self, execution, event_type, extra_payload=None):
        payload = {
            "execution_id": str(execution.id),
            "status": execution.status,
            "task_ref": execution.task_ref,
            "last_engine_state": execution.last_engine_state,
        }
        if extra_payload:
            payload.update(extra_payload)
        return record_evidence(
            run=execution.run,
            revision=execution.revision,
            execution=execution,
            event_type=event_type,
            action=TOOL_NAME,
            payload=payload,
            actor=self.context.actor,
            correlation_id=self.context.correlation_id,
        )

    def _locked_record(self):
        record = HarnessIdempotencyRecord.objects.select_for_update().get(**self.scope.lookup())
        self.scope.check_record(record)
        if record.request_hash != self.request_hash:
            raise IdempotencyConflict()
        return record

    def _lock_graph(self, execution_id=None, *, require_active_approval=False):
        return _lock_authority(
            self.context,
            self.request,
            self.manifest,
            self.publication,
            action_policy=self.action_policy,
            release_policy=self.release_policy,
            preflight=self.preflight,
            approval_id=self.approval.id,
            execution_id=execution_id,
            require_active_approval=require_active_approval,
        )

    def _manual(self, execution):
        run = HarnessRun.objects.get(pk=execution.run_id)
        revision = WorkflowPlanRevision.objects.get(pk=execution.revision_id)
        return _failure(
            self.context,
            StartExecutionRejected(
                "RETRYABLE_INFRA",
                "execution",
                retryable=True,
                repairable=False,
                manual_reconcile=True,
            ),
            run=run,
            revision=revision,
            execution=execution,
        )

    def _mark_uncertain(self, execution_id, status):
        with transaction.atomic():
            self._locked_record()
            *_, execution, _ = self._lock_graph(execution_id)
            if execution.status != status:
                execution.status = status
                execution.save(update_fields=["status", "update_at"])
                self._record(execution, status)
            return execution

    def _mark_rejected(self, execution_id, reason):
        with transaction.atomic():
            record = self._locked_record()
            _, run, revision, _, _, _, _, _, execution, _ = self._lock_graph(execution_id)
            if execution.status not in ExecutionRun.TERMINAL:
                execution.status = ExecutionRun.Status.FAILED
                execution.postcondition_status = ExecutionRun.PostconditionStatus.UNAVAILABLE
                execution.postcondition_report = {"reason": reason}
                execution.terminal_at = timezone.now()
                execution.save(
                    update_fields=[
                        "status",
                        "postcondition_status",
                        "postcondition_report",
                        "terminal_at",
                        "update_at",
                    ]
                )
                self._record(execution, "EXECUTION_REJECTED")
            response = _failure(
                self.context,
                StartExecutionRejected("EXECUTION_REJECTED", "execution", repairable=False),
                run=run,
                revision=revision,
                execution=execution,
            )
            complete_idempotency(record, response, run=run, resource_reference=str(execution.id))
            return response

    def _complete_from_readback(self, execution_id):
        execution = ExecutionRun.objects.get(pk=execution_id)
        try:
            state = self.adapter.read_state(execution.task_ref)
        except Exception:
            return self._mark_uncertain(execution_id, ExecutionRun.Status.START_UNCERTAIN)
        if state not in _START_PROVEN_ENGINE_STATES:
            return self._mark_uncertain(execution_id, ExecutionRun.Status.START_UNCERTAIN)
        with transaction.atomic():
            record = self._locked_record()
            _, run, revision, _, _, _, _, _, locked_execution, _ = self._lock_graph(execution_id)
            if locked_execution.status in {
                ExecutionRun.Status.START_DISPATCHING,
                ExecutionRun.Status.START_UNCERTAIN,
            }:
                locked_execution.status = ExecutionRun.Status.EXECUTING
                locked_execution.last_engine_state = state
                locked_execution.heartbeat_at = timezone.now()
                locked_execution.save(update_fields=["status", "last_engine_state", "heartbeat_at", "update_at"])
                self._record(locked_execution, "EXECUTION_STARTED")
            if run.status == HarnessRunStatus.PUBLISHED:
                run.status = HarnessRunStatus.EXECUTING
                run.save(update_fields=["status", "update_at"])
            response = _success(self.context, run, revision, locked_execution)
            if record.status == "COMPLETED":
                if record.response_snapshot != response or record.resource_reference != str(locked_execution.id):
                    raise IdempotencyRecordImmutable()
                return record.response_snapshot
            complete_idempotency(
                record,
                response,
                run=run,
                resource_reference=str(locked_execution.id),
            )
            return response

    def _dispatch_start(self, execution_id):
        if self.test_before_start_barrier_hook is not None:
            self.test_before_start_barrier_hook(ExecutionRun.objects.get(pk=execution_id))
        with transaction.atomic():
            self._locked_record()
            *_, execution, _ = self._lock_graph(execution_id, require_active_approval=True)
            if execution.status == ExecutionRun.Status.CREATED:
                execution.status = ExecutionRun.Status.START_DISPATCHING
                execution.save(update_fields=["status", "update_at"])
                self._record(execution, "START_DISPATCHING")
            elif execution.status not in {
                ExecutionRun.Status.START_DISPATCHING,
                ExecutionRun.Status.START_UNCERTAIN,
            }:
                raise StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False)
            task_ref = execution.task_ref
        try:
            self.adapter.start(task_ref)
        except StartDispatchRejected:
            return self._mark_rejected(execution_id, "start_rejected")
        except StartDispatchUncertain:
            pass
        return self._complete_from_readback(execution_id)

    def _resume(self, execution, record):
        if record.status == "COMPLETED":
            if record.resource_reference != str(execution.id):
                raise IdempotencyRecordImmutable()
            return record.response_snapshot
        if execution.status == ExecutionRun.Status.CREATE_DISPATCHING:
            if timezone.now() - execution.update_at >= CREATE_DISPATCH_BARRIER_TTL:
                uncertain = self._mark_uncertain(execution.id, ExecutionRun.Status.CREATE_UNCERTAIN)
                return self._manual(uncertain)
            return _failure(
                self.context,
                StartExecutionRejected("RETRYABLE_INFRA", "execution", retryable=True, repairable=False),
                run=execution.run,
                revision=execution.revision,
                execution=execution,
            )
        if execution.status == ExecutionRun.Status.CREATE_UNCERTAIN:
            return self._manual(execution)
        if execution.status == ExecutionRun.Status.CREATED:
            return self._dispatch_start(execution.id)
        if execution.status == ExecutionRun.Status.START_DISPATCHING:
            recovered = self._complete_from_readback(execution.id)
            return recovered if isinstance(recovered, dict) else self._manual(recovered)
        if execution.status == ExecutionRun.Status.START_UNCERTAIN:
            recovered = self._complete_from_readback(execution.id)
            if isinstance(recovered, ExecutionRun) and recovered.status == ExecutionRun.Status.START_UNCERTAIN:
                return self._manual(recovered)
            return recovered
        if execution.status == ExecutionRun.Status.EXECUTING:
            with transaction.atomic():
                locked_record = self._locked_record()
                _, run, revision, _, _, _, _, _, locked_execution, _ = self._lock_graph(execution.id)
                response = _success(self.context, run, revision, locked_execution)
                complete_idempotency(
                    locked_record,
                    response,
                    run=run,
                    resource_reference=str(locked_execution.id),
                )
                return response
        raise StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False)

    def start(self):
        existing_record = HarnessIdempotencyRecord.objects.filter(**self.scope.lookup()).first()
        self.scope.check_record(existing_record)
        if existing_record is not None:
            if existing_record.request_hash != self.request_hash:
                raise IdempotencyConflict()
            execution = ExecutionRun.objects.filter(
                manifest=self.manifest,
                start_idempotency_key=self.request.idempotency_key,
            ).first()
            if execution is None:
                raise IdempotencyInFlight()
            return self._resume(execution, existing_record)

        if self.test_before_create_barrier_hook is not None:
            self.test_before_create_barrier_hook(None)
        with transaction.atomic():
            acquisition = acquire_idempotency(self.scope, self.request_hash)
            _, run, revision, _, _, manifest, _, publication, existing, _ = self._lock_graph(
                require_active_approval=True
            )
            if acquisition.replayed:
                return acquisition.response_snapshot
            if existing is not None:
                raise IdempotencyInFlight()
            execution = ExecutionRun.objects.create(
                manifest=manifest,
                run=run,
                revision=revision,
                published_template_id=publication.published_template_id,
                published_snapshot_id=publication.published_snapshot_id,
                published_version=publication.published_version,
                start_idempotency_key=self.request.idempotency_key,
                create_idempotency_ref="idempotency://execution/{}".format(acquisition.record.id),
                start_idempotency_ref="idempotency://execution/{}".format(acquisition.record.id),
                platform=self.context.platform_key,
                platform_app=self.context.platform_app,
                actor=self.context.actor,
                space_id=self.context.space_id,
                scope=run.scope,
                target_environment=self.context.target_environment,
                policy_version=self.context.policy_version,
            )
            execution.status = ExecutionRun.Status.CREATE_DISPATCHING
            execution.save(update_fields=["status", "update_at"])
            bind_inflight_idempotency(acquisition.record, run=run, resource_reference=str(execution.id))
            self._record(execution, "CREATE_DISPATCHING")
            execution_id = execution.id

        if self.test_after_create_barrier_hook is not None:
            self.test_after_create_barrier_hook(execution)

        try:
            create_result = self.adapter.create(
                publication=self.publication,
                request=self.request,
                credentials=self.credentials,
            )
        except CreateDispatchRejected:
            return self._mark_rejected(execution_id, "create_rejected")
        except CreateDispatchUncertain:
            uncertain = self._mark_uncertain(execution_id, ExecutionRun.Status.CREATE_UNCERTAIN)
            return self._manual(uncertain)
        except Exception:
            uncertain = self._mark_uncertain(execution_id, ExecutionRun.Status.CREATE_UNCERTAIN)
            return self._manual(uncertain)

        warning_codes = ()
        if isinstance(create_result, TaskCreationReceipt):
            task_ref = create_result.task_ref
            warning_codes = create_result.warnings
            if any(code not in _SAFE_CREATE_WARNING_CODES for code in warning_codes):
                uncertain = self._mark_uncertain(execution_id, ExecutionRun.Status.CREATE_UNCERTAIN)
                return self._manual(uncertain)
        else:
            task_ref = create_result
        if safe_opaque_identifier(str(task_ref)) is None:
            uncertain = self._mark_uncertain(execution_id, ExecutionRun.Status.CREATE_UNCERTAIN)
            return self._manual(uncertain)

        try:
            with transaction.atomic():
                self._locked_record()
                *_, execution, _ = self._lock_graph(execution_id)
                if (
                    execution.status
                    not in {
                        ExecutionRun.Status.CREATE_DISPATCHING,
                        ExecutionRun.Status.CREATE_UNCERTAIN,
                    }
                    or execution.task_ref
                ):
                    raise StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False)
                execution.task_ref = str(task_ref)
                execution.status = ExecutionRun.Status.CREATED
                execution.save(update_fields=["task_ref", "status", "update_at"])
                extra_payload = {"warning_codes": list(warning_codes)} if warning_codes else None
                self._record(execution, "TASK_CREATED", extra_payload)
        except (DjangoValidationError, DatabaseError):
            uncertain = self._mark_uncertain(execution_id, ExecutionRun.Status.CREATE_UNCERTAIN)
            return self._manual(uncertain)
        if self.test_after_task_persist_hook is not None:
            self.test_after_task_persist_hook(execution)
        return self._dispatch_start(execution_id)


def start_workflow_execution_with_context(
    context,
    payload,
    plugin_schema_service=None,
    *,
    resolver=None,
    release_policy=None,
    action_policy=None,
    approval_verifier=None,
    credential_resolver=None,
    adapter=None,
    converter_class=None,
    pipeline_validator=None,
    test_after_task_persist_hook=None,
    test_after_create_barrier_hook=None,
    test_before_create_barrier_hook=None,
    test_before_start_barrier_hook=None,
):
    """Validate, approve and drive one publication-bound execution Saga."""
    run = revision = execution = None
    try:
        request = validate_start_execution_request(payload)
        require_tool_enabled(context, TOOL_NAME)
        if release_policy is None:
            raise StartExecutionRejected("VALIDATION_STALE", "policy", repairable=False)
        active_action_policy = action_policy or ActionPolicy()
        active_resolver = resolver or CapabilityResolver(plugin_schema_service)
        active_credential_resolver = credential_resolver or BoundCredentialResolver()
        active_adapter = adapter or ApplicationTaskAdapter(space_id=context.space_id, actor=context.actor)
        run, manifest, publication = _load_seed(context, request)
        revision = manifest.revision
        decision = _policy_decision(context, manifest, publication, request, active_action_policy, release_policy)
        if not request.has_approval:
            pending = _request_approval(
                context,
                request,
                run,
                manifest,
                publication,
                action_policy=active_action_policy,
                release_policy=release_policy,
            )
            raise StartExecutionRejected(
                "APPROVAL_REQUIRED",
                "approval_receipt_ref",
                repairable=False,
                approval_request_id=pending.id,
            )
        try:
            approval = ApprovalRequest.objects.get(pk=request.approval_request_id, manifest=manifest)
        except ApprovalRequest.DoesNotExist:
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False) from None
        try:
            preflight, resolved_bindings = _preflight_schema(
                context,
                run,
                manifest,
                publication,
                resolver=active_resolver,
                converter_class=converter_class,
                pipeline_validator=pipeline_validator,
            )
        except ProviderInfrastructureError:
            raise
        except ReleasePreparationRejected as error:
            if error.invalidate:
                _invalidate_start_approval(run, approval)
            raise
        decision_result = _verify_approval_outside_transaction(
            context, request, run, manifest, decision, approval, approval_verifier
        )
        approval = _commit_verified_approval(
            context,
            request,
            run,
            manifest,
            publication,
            approval,
            decision_result,
            action_policy=active_action_policy,
            release_policy=release_policy,
        )
        try:
            credentials = _resolve_credentials(context, resolved_bindings, active_credential_resolver)
        except (DjangoValidationError, ValueError):
            _invalidate_start_approval(run, approval)
            raise StartExecutionRejected("VALIDATION_STALE", "credentials", repairable=False) from None
        saga = ExecutionSaga(
            context,
            request,
            run,
            manifest,
            publication,
            approval,
            preflight=preflight,
            credentials=credentials,
            action_policy=active_action_policy,
            release_policy=release_policy,
            adapter=active_adapter,
            test_after_task_persist_hook=test_after_task_persist_hook,
            test_after_create_barrier_hook=test_after_create_barrier_hook,
            test_before_create_barrier_hook=test_before_create_barrier_hook,
            test_before_start_barrier_hook=test_before_start_barrier_hook,
        )
        result = saga.start()
        if isinstance(result, ExecutionRun):
            execution = result
            return saga._manual(result)
        return result
    except StartExecutionRejected as error:
        return _failure(context, error, run=run, revision=revision, execution=execution)
    except HarnessContextError as error:
        return _failure(context, StartExecutionRejected(error.code, "execution", repairable=False))
    except IdempotencyConflict:
        return _failure(
            context,
            StartExecutionRejected("IDEMPOTENCY_CONFLICT", "idempotency_key", repairable=False),
            run=run,
            revision=revision,
        )
    except (IdempotencyInFlight, IdempotencyRecordImmutable, ProviderInfrastructureError, DatabaseError):
        return _failure(
            context,
            StartExecutionRejected("RETRYABLE_INFRA", "execution", retryable=True, repairable=False),
            run=run,
            revision=revision,
        )
    except ReleasePreparationRejected as error:
        return _failure(
            context,
            StartExecutionRejected(
                error.code,
                error.path,
                category=error.category,
                repairable=error.repairable,
                retryable=error.retryable,
            ),
            run=run,
            revision=revision,
        )
    except (DjangoValidationError, ValueError):
        return _failure(
            context,
            StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False),
            run=run,
            revision=revision,
        )
    except Exception:
        return _failure(
            context,
            StartExecutionRejected("RETRYABLE_INFRA", "execution", retryable=True, repairable=False),
            run=run,
            revision=revision,
        )


__all__ = ["ExecutionSaga", "start_workflow_execution_with_context"]
