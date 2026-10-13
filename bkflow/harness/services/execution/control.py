"""Approval-bound workflow execution control orchestration."""

from copy import deepcopy

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from bkflow.harness.constants import RiskLevel
from bkflow.harness.contracts import HarnessContextError
from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.models import (
    ApprovalRequest,
    EvidenceEvent,
    ExecutionRun,
    HarnessIdempotencyRecord,
    HarnessRun,
    ReleaseManifest,
    ReleasePublication,
    WorkflowPlanRevision,
)
from bkflow.harness.services.approval import (
    ApprovalInvalid,
    ApprovalVerifier,
    normalize_approval_decision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.contract_versions import require_tool_enabled
from bkflow.harness.services.debug.policy import context_matches_run
from bkflow.harness.services.evidence import MAX_EVIDENCE_ITEMS, record_evidence
from bkflow.harness.services.execution.adapter import (
    ApplicationTaskAdapter,
    ControlActionUnavailable,
    ControlDispatchReceipt,
    ControlDispatchUncertain,
    ControlObservation,
    ReadbackUnavailable,
    TaskNotFound,
    runtime_mapping_fingerprint,
)
from bkflow.harness.services.execution.contracts import (
    StartExecutionRejected,
    validate_control_execution_request,
)
from bkflow.harness.services.idempotency import (
    IdempotencyScope,
    acquire_execution_barrier,
    complete_idempotency,
)
from bkflow.harness.services.release.policy import ACTION_RISK, ActionPolicy
from bkflow.harness.services.validator import (
    WorkflowValidationFailure,
    WorkflowValidator,
)
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.models import Template, TemplateSnapshot

TOOL_NAME = "control_workflow_execution"
_BLOCKING_EXECUTION_TOOLS = frozenset(("start_workflow_execution", TOOL_NAME))


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
        artifact_refs=(
            [{"type": "workflow_execution", "execution_id": str(execution.id), "execution_status": execution.status}]
            if execution
            else []
        ),
    )
    response["summary"] = "Workflow execution control is blocked."
    if rejection.approval_request_id is not None:
        response["approval_request_id"] = str(rejection.approval_request_id)
    if rejection.manual_reconcile:
        response["next_actions"] = ["manual_reconcile_execution"]
    return response


def _manual_response(context, run, revision, execution):
    return _failure(
        context,
        StartExecutionRejected(
            "RETRYABLE_INFRA",
            "control",
            repairable=False,
            retryable=True,
            manual_reconcile=True,
        ),
        run=run,
        revision=revision,
        execution=execution,
    )


def _receipt_is_acknowledged(receipt):
    """Accept only the exact safe DTO and a strict boolean acknowledgement."""
    return isinstance(receipt, ControlDispatchReceipt) and receipt.acknowledged is True


def _publication_hash(publication):
    return sha256_json(
        {
            "manifest_id": str(publication.manifest_id),
            "published_template_id": publication.published_template_id,
            "published_snapshot_id": publication.published_snapshot_id,
            "published_version": publication.published_version,
            "operator": publication.operator,
            "publish_idempotency_ref": publication.publish_idempotency_ref,
        }
    )


def _graph_is_valid(context, run, revision, manifest, publication, execution, template, snapshot):
    return not (
        execution.run_id != run.id
        or execution.manifest_id != manifest.id
        or execution.revision_id != revision.id
        or execution.platform != context.platform_key
        or execution.platform_app != context.platform_app
        or execution.actor != context.actor
        or execution.space_id != context.space_id
        or execution.scope != run.scope
        or execution.target_environment != context.target_environment
        or execution.policy_version != context.policy_version
        or manifest.run_id != run.id
        or manifest.revision_id != revision.id
        or manifest.plan_hash != revision.plan_hash
        or manifest.manifest_hash != sha256_json(manifest._hash_payload())
        or publication.manifest_id != manifest.id
        or publication.publication_hash != _publication_hash(publication)
        or publication.published_template_id != execution.published_template_id
        or publication.published_snapshot_id != execution.published_snapshot_id
        or publication.published_version != execution.published_version
        or snapshot.id != publication.published_snapshot_id
        or snapshot.template_id != template.id
        or snapshot.version != publication.published_version
        or snapshot.draft
        or snapshot.is_deleted
        or template.is_deleted
        or template.space_id != context.space_id
        or template.scope_type != context.scope_type
        or template.scope_value != context.scope_value
        or template.bk_app_code != context.platform_app
        or manifest.draft_tree_fingerprint != compute_tree_fingerprint(snapshot.data)
        or not execution.task_ref
    )


def _owned_graph(context, execution_id):
    try:
        execution = ExecutionRun.objects.select_related("run", "manifest__revision").get(pk=execution_id)
        run = execution.run
        manifest = execution.manifest
        revision = manifest.revision
        publication = ReleasePublication.objects.get(manifest=manifest)
        template = Template.objects.get(pk=publication.published_template_id)
        snapshot = TemplateSnapshot.objects.get(pk=publication.published_snapshot_id)
    except (
        ExecutionRun.DoesNotExist,
        ReleasePublication.DoesNotExist,
        Template.DoesNotExist,
        TemplateSnapshot.DoesNotExist,
    ):
        raise StartExecutionRejected(
            "CAPABILITY_FORBIDDEN", "execution_id", category="PERMISSION", repairable=False
        ) from None
    if not context_matches_run(context, run):
        raise StartExecutionRejected("CAPABILITY_FORBIDDEN", "execution_id", category="PERMISSION", repairable=False)
    if not _graph_is_valid(context, run, revision, manifest, publication, execution, template, snapshot):
        raise StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False)
    return run, revision, manifest, publication, execution, snapshot


def _lock_graph(context, seed_execution, approval_id=None):
    """Lock the immutable authority graph in the shared release/runtime order."""
    template = Template.objects.select_for_update().get(pk=seed_execution.published_template_id)
    run = HarnessRun.objects.select_for_update().get(pk=seed_execution.run_id)
    if not context_matches_run(context, run):
        raise StartExecutionRejected("CAPABILITY_FORBIDDEN", "execution_id", category="PERMISSION", repairable=False)
    revision = WorkflowPlanRevision.objects.select_for_update().get(pk=seed_execution.revision_id, run=run)
    snapshot = TemplateSnapshot.objects.select_for_update().get(pk=seed_execution.published_snapshot_id)
    manifest = ReleaseManifest.objects.select_for_update().get(pk=seed_execution.manifest_id, run=run)
    approval = None
    if approval_id is not None:
        approval = ApprovalRequest.objects.select_for_update().get(pk=approval_id, manifest=manifest)
    publication = ReleasePublication.objects.select_for_update().get(manifest=manifest)
    execution = ExecutionRun.objects.select_for_update().get(pk=seed_execution.pk, manifest=manifest)
    if not _graph_is_valid(context, run, revision, manifest, publication, execution, template, snapshot):
        raise StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False)
    return run, revision, manifest, publication, approval, execution, snapshot


def _target_resource(execution, publication, request):
    target = {
        "execution_id": str(execution.id),
        "task_ref": execution.task_ref,
        "publication_id": str(publication.id),
        "template_id": publication.published_template_id,
        "snapshot_id": publication.published_snapshot_id,
        "published_version": publication.published_version,
    }
    for name in (
        "template_node_id",
        "template_gateway_id",
        "template_flow_id",
        "template_flow_ids",
        "template_converge_gateway_id",
    ):
        value = getattr(request, name)
        if value not in (None, ()):
            target[name] = list(value) if isinstance(value, tuple) else value
    return target


def _policy_decision(manifest, publication, execution, request, action_policy):
    if request.expected_manifest_hash != manifest.manifest_hash:
        raise StartExecutionRejected("VALIDATION_STALE", "expected_manifest_hash", repairable=False)
    try:
        decision = action_policy.evaluate(
            action=request.action,
            manifest_hash=manifest.manifest_hash,
            plan_hash=manifest.plan_hash,
            target_resource=_target_resource(execution, publication, request),
            normalized_params={
                "control_intent": request.action_payload(),
                "idempotency_key": request.idempotency_key,
            },
            policy_version=manifest.policy_version,
        )
    except DjangoValidationError:
        raise StartExecutionRejected("VALIDATION_STALE", "policy", repairable=False) from None
    if (
        request.action not in ACTION_RISK
        or decision.action != request.action
        or decision.risk_level not in {RiskLevel.L2, RiskLevel.L3}
        or decision.risk_level != ACTION_RISK[request.action]
        or decision.requires_approval is not True
    ):
        raise StartExecutionRejected("VALIDATION_STALE", "policy", repairable=False)
    return decision


def _approval_values(context, run, manifest, request, decision):
    return {
        "manifest": manifest,
        "run": run,
        "revision": manifest.revision,
        "plan_hash": manifest.plan_hash,
        "action": request.action,
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
            "action": request.action,
            "execution_id": str(request.execution_id),
            "intent_digest": sha256_json(request.action_payload()),
        },
    }


def _invalidate_control_approval(context, request):
    """Revoke exact control authority after server-observed execution drift."""
    if request is None or not request.has_approval:
        return
    try:
        seed_execution = ExecutionRun.objects.select_related("run").get(pk=request.execution_id)
    except ExecutionRun.DoesNotExist:
        return
    seed_run = seed_execution.run
    if not context_matches_run(context, seed_run) or any(
        (
            seed_execution.platform != context.platform_key,
            seed_execution.platform_app != context.platform_app,
            seed_execution.actor != context.actor,
            seed_execution.space_id != context.space_id,
            seed_execution.scope != seed_run.scope,
            seed_execution.target_environment != context.target_environment,
            seed_execution.policy_version != context.policy_version,
        )
    ):
        return
    with transaction.atomic():
        # Keep the same partial lock order used by publish/start/control.
        Template.objects.select_for_update().filter(pk=seed_execution.published_template_id).first()
        locked_run = HarnessRun.objects.select_for_update().get(pk=seed_run.pk)
        approval = (
            ApprovalRequest.objects.select_for_update()
            .filter(
                pk=request.approval_request_id,
                manifest_id=seed_execution.manifest_id,
                run=locked_run,
                action=request.action,
                platform=context.platform_key,
                platform_app=context.platform_app,
                actor=context.actor,
                space_id=context.space_id,
                scope=locked_run.scope,
                target_environment=context.target_environment,
                policy_version=context.policy_version,
            )
            .first()
        )
        if approval is not None and approval.status in {
            ApprovalRequest.Status.PENDING,
            ApprovalRequest.Status.VERIFIED,
        }:
            approval.status = ApprovalRequest.Status.REVOKED
            approval.save(update_fields=["status", "active_approval_key", "update_at"])


def _safe_invalidate_control_approval(context, request):
    """Contain invalidation storage failures within the stable Envelope boundary."""
    try:
        _invalidate_control_approval(context, request)
    except Exception:
        return False
    return True


def _approval_matches(approval, context, run, manifest, request, decision):
    return (
        approval.manifest_id == manifest.id
        and approval.run_id == run.id
        and approval.revision_id == manifest.revision_id
        and approval.plan_hash == manifest.plan_hash
        and approval.action == request.action
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


def _approval_claims(context, run, manifest, request, decision):
    return {
        "actor": context.actor,
        "platform_app": context.platform_app,
        "space_id": context.space_id,
        "scope": run.scope,
        "environment": context.target_environment,
        "plan_hash": manifest.plan_hash,
        "action": request.action,
        "action_digest": decision.action_digest,
    }


def _request_approval(context, seed_execution, request, *, action_policy):
    with transaction.atomic():
        run, _, manifest, publication, _, execution, _ = _lock_graph(context, seed_execution)
        decision = _policy_decision(manifest, publication, execution, request, action_policy)
        if not _execution_source_is_allowed(execution, request):
            raise StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False)
        existing = (
            ApprovalRequest.objects.select_for_update()
            .filter(
                manifest=manifest,
                action=request.action,
                action_digest=decision.action_digest,
                status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED],
            )
            .first()
        )
        if existing is None:
            try:
                with transaction.atomic():
                    existing = ApprovalRequest.objects.create(
                        **_approval_values(context, run, manifest, request, decision)
                    )
            except IntegrityError:
                existing = ApprovalRequest.objects.select_for_update().get(
                    manifest=manifest,
                    action=request.action,
                    action_digest=decision.action_digest,
                    status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED],
                )
        if not _approval_matches(existing, context, run, manifest, request, decision):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
        return existing


def _verify_approval(context, run, manifest, request, decision, approval, verifier):
    if not _approval_matches(approval, context, run, manifest, request, decision):
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
                _approval_claims(context, run, manifest, request, decision),
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


def _scope(context, run, request):
    return IdempotencyScope.for_run(
        context.platform_app,
        context.actor,
        context.space_id,
        TOOL_NAME,
        run,
        request.idempotency_key,
    )


def _request_hash(run, request):
    return sha256_json({"request": request.action_payload(), "trusted_run_id": str(run.run_id)})


def _existing_attempt(context, scope, request_hash, execution):
    record = HarnessIdempotencyRecord.objects.filter(**scope.lookup()).first()
    scope.check_record(record)
    if record is not None and record.request_hash != request_hash:
        raise IdempotencyConflict("idempotency key was already used for a different request")
    if record is not None and record.status == "COMPLETED":
        return deepcopy(record.response_snapshot)
    if record is not None:
        return _manual_response(context, execution.run, execution.revision, execution)
    if execution.status in {
        ExecutionRun.Status.CONTROL_DISPATCHING,
        ExecutionRun.Status.CONTROL_UNCERTAIN,
    }:
        return _manual_response(context, execution.run, execution.revision, execution)
    return None


def _execution_source_is_allowed(execution, request):
    if request.action == "resume":
        return execution.status == ExecutionRun.Status.PAUSED
    if request.action == "revoke":
        return execution.status in {ExecutionRun.Status.EXECUTING, ExecutionRun.Status.PAUSED}
    if request.action in {"pause", "retry", "skip", "forced_fail"}:
        return execution.status == ExecutionRun.Status.EXECUTING
    return False


def _observation_is_bound(observation, execution, request):
    return (
        isinstance(observation, ControlObservation)
        and observation.task_ref == execution.task_ref
        and observation.action == request.action
        and observation.template_node_id == request.template_node_id
    )


def _expected_readback(request):
    return {
        "pause": "SUSPENDED",
        "resume": "RUNNING",
        "revoke": "REVOKED",
        "retry": "NODE_VERSION_ADVANCED",
        "skip": "NODE_VERSION_ADVANCED",
        "forced_fail": "NODE_FAILED",
    }[request.action]


def _journal_payload(request, decision, observation, idempotency_ref, attempt, execution_status):
    input_fields = sorted(request.inputs) if request.inputs is not None else []
    input_digest = sha256_json(request.inputs or {})
    template_target = {}
    if request.template_node_id is not None:
        template_target["template_node_id"] = request.template_node_id
    return {
        "version": "control-attempt-v1",
        "action": request.action,
        "attempt": attempt,
        "idempotency_ref": idempotency_ref,
        "action_digest": decision.action_digest,
        "pre_execution_status": execution_status,
        "pre_state": {
            "root_state": observation.root_state,
            "template_node_id": observation.template_node_id,
            "node_state": observation.node_state,
            "node_version": observation.node_version,
            "runtime_mapping_fingerprint": (
                runtime_mapping_fingerprint(observation.template_node_id, observation.runtime_node_id)
                if observation.template_node_id is not None
                else None
            ),
        },
        "template_target": template_target,
        "expected_readback": _expected_readback(request),
        "input_fields": input_fields,
        "input_digest": input_digest,
    }


def _approval_is_active(approval, request, decision):
    return (
        approval.status == ApprovalRequest.Status.VERIFIED
        and approval.action == request.action
        and approval.action_digest == decision.action_digest
        and approval.receipt_ref == request.approval_receipt_ref
        and bool(approval.receipt_digest)
        and bool(approval.verifier_version)
        and approval.expires_at is not None
        and approval.expires_at > timezone.now()
    )


def _commit_approval(
    context,
    seed_execution,
    request,
    decision_result,
    *,
    action_policy,
):
    with transaction.atomic():
        run, _, manifest, publication, approval, execution, _ = _lock_graph(
            context, seed_execution, request.approval_request_id
        )
        decision = _policy_decision(manifest, publication, execution, request, action_policy)
        if not _approval_matches(approval, context, run, manifest, request, decision):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
        if decision_result is not None and decision_result.claims_digest != sha256_json(
            _approval_claims(context, run, manifest, request, decision)
        ):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
        _persist_verified(approval, request, decision_result)
        return approval


def _create_barrier(
    context,
    seed_execution,
    request,
    approval,
    observation,
    *,
    action_policy,
):
    scope = _scope(context, seed_execution.run, request)
    request_hash = _request_hash(seed_execution.run, request)
    with transaction.atomic():
        acquisition = acquire_execution_barrier(
            scope,
            request_hash,
            run=seed_execution.run,
            execution_id=seed_execution.id,
            blocking_tool_names=_BLOCKING_EXECUTION_TOOLS,
        )
        if acquisition.replayed:
            return acquisition, None, None
        run, revision, manifest, publication, locked_approval, execution, snapshot = _lock_graph(
            context, seed_execution, approval.id
        )
        decision = _policy_decision(manifest, publication, execution, request, action_policy)
        if not _approval_matches(locked_approval, context, run, manifest, request, decision) or not _approval_is_active(
            locked_approval, request, decision
        ):
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
        if not _execution_source_is_allowed(execution, request):
            raise StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False)
        if not _observation_is_bound(observation, execution, request):
            raise StartExecutionRejected("VALIDATION_STALE", "control", repairable=False)
        idempotency_ref = "idempotency://execution/{}".format(acquisition.record.id)
        if idempotency_ref in execution.control_idempotency_refs:
            raise IdempotencyInFlight("this execution already has an uncertain mutation")
        # Reserve one final slot for Task8 terminal evidence and bundle closure.
        if EvidenceEvent.objects.select_for_update().filter(execution=execution).count() >= MAX_EVIDENCE_ITEMS - 1:
            raise StartExecutionRejected("RETRYABLE_INFRA", "evidence", retryable=True, repairable=False)
        previous_status = execution.status
        refs = list(execution.control_idempotency_refs)
        refs.append(idempotency_ref)
        execution.control_idempotency_refs = refs
        execution.status = ExecutionRun.Status.CONTROL_DISPATCHING
        execution.save(update_fields=["status", "control_idempotency_refs", "update_at"])
        record_evidence(
            run=run,
            revision=revision,
            execution=execution,
            event_type="EXECUTION_CONTROL_DISPATCHING",
            action=request.action,
            payload=_journal_payload(
                request,
                decision,
                observation,
                idempotency_ref,
                len(refs),
                previous_status,
            ),
            actor=context.actor,
            correlation_id=context.correlation_id,
        )
        return acquisition, execution, deepcopy(snapshot.data)


def _complete_uncertain(context, seed_execution, request, acquisition):
    with transaction.atomic():
        record = HarnessIdempotencyRecord.objects.select_for_update().get(pk=acquisition.record.pk)
        if record.status == "COMPLETED" and record.request_hash == _request_hash(seed_execution.run, request):
            # A concurrent GET may have proven the post-dispatch state and
            # completed this exact barrier while the Engine call was in flight.
            return deepcopy(record.response_snapshot)
        if record.status != "IN_FLIGHT" or record.request_hash != _request_hash(seed_execution.run, request):
            raise IdempotencyRecordImmutable("control dispatch barrier is unavailable")
        run, revision, _, _, _, execution, _ = _lock_graph(context, seed_execution)
        if execution.status != ExecutionRun.Status.CONTROL_DISPATCHING:
            raise IdempotencyRecordImmutable("control execution barrier is unavailable")
        execution.status = ExecutionRun.Status.CONTROL_UNCERTAIN
        execution.save(update_fields=["status", "update_at"])
        response = _manual_response(context, run, revision, execution)
        complete_idempotency(record, response, run=run, resource_reference=str(execution.id))
        return response


def control_workflow_execution_with_context(
    context,
    payload,
    *,
    adapter=None,
    approval_verifier=None,
    action_policy=None,
    test_after_barrier_hook=None,
    test_after_dispatch_hook=None,
):
    """Authorize and durably dispatch one execution control intent at most once."""
    request = run = revision = execution = None
    try:
        request = validate_control_execution_request(payload)
        require_tool_enabled(context, TOOL_NAME)
        run, revision, manifest, publication, execution, snapshot = _owned_graph(context, request.execution_id)
        active_policy = action_policy or ActionPolicy()
        decision = _policy_decision(manifest, publication, execution, request, active_policy)
        scope = _scope(context, run, request)
        request_hash = _request_hash(run, request)
        existing = _existing_attempt(context, scope, request_hash, execution)
        if existing is not None:
            return existing
        if not _execution_source_is_allowed(execution, request):
            raise StartExecutionRejected("VALIDATION_STALE", "execution", repairable=False)
        active_adapter = adapter or ApplicationTaskAdapter(space_id=context.space_id, actor=context.actor)
        observation = active_adapter.control_preflight(execution.task_ref, request, deepcopy(snapshot.data))
        if not request.has_approval:
            approval = _request_approval(context, execution, request, action_policy=active_policy)
            raise StartExecutionRejected(
                "APPROVAL_REQUIRED",
                "approval_receipt_ref",
                repairable=False,
                approval_request_id=approval.id,
            )
        try:
            approval = ApprovalRequest.objects.get(pk=request.approval_request_id, manifest=manifest)
        except ApprovalRequest.DoesNotExist:
            raise StartExecutionRejected("APPROVAL_INVALID", "approval_request_id", repairable=False) from None
        decision_result = _verify_approval(context, run, manifest, request, decision, approval, approval_verifier)
        # The verifier and both Engine preflight reads remain outside DB locks.
        fresh_observation = active_adapter.control_preflight(execution.task_ref, request, deepcopy(snapshot.data))
        if fresh_observation != observation:
            raise StartExecutionRejected("VALIDATION_STALE", "control", repairable=False)
        approval = _commit_approval(
            context,
            execution,
            request,
            decision_result,
            action_policy=active_policy,
        )
        barrier_observation = active_adapter.control_preflight(execution.task_ref, request, deepcopy(snapshot.data))
        if barrier_observation != fresh_observation:
            raise StartExecutionRejected("VALIDATION_STALE", "control", repairable=False)
        acquisition, locked_execution, pipeline_tree = _create_barrier(
            context,
            execution,
            request,
            approval,
            barrier_observation,
            action_policy=active_policy,
        )
        if acquisition.replayed:
            return deepcopy(acquisition.response_snapshot)
        execution = locked_execution
        if test_after_barrier_hook is not None:
            test_after_barrier_hook()
        try:
            receipt = active_adapter.control_dispatch(
                execution.task_ref,
                request,
                barrier_observation,
                pipeline_tree=pipeline_tree,
            )
            if not _receipt_is_acknowledged(receipt):
                raise ControlDispatchUncertain()
        except ControlDispatchUncertain:
            pass
        if test_after_dispatch_hook is not None:
            test_after_dispatch_hook()
        return _complete_uncertain(context, execution, request, acquisition)
    except StartExecutionRejected as rejection:
        if rejection.code == "VALIDATION_STALE" and rejection.path != "expected_manifest_hash":
            if not _safe_invalidate_control_approval(context, request):
                return _failure(
                    context,
                    StartExecutionRejected("RETRYABLE_INFRA", "control", retryable=True, repairable=False),
                    run=run,
                    revision=revision,
                    execution=execution,
                )
        return _failure(context, rejection, run=run, revision=revision, execution=execution)
    except HarnessContextError as error:
        return _failure(context, StartExecutionRejected(error.code, "control", repairable=False))
    except ReadbackUnavailable:
        if execution is not None and execution.status == ExecutionRun.Status.CONTROL_DISPATCHING:
            return _manual_response(context, run, revision, execution)
        return _failure(
            context,
            StartExecutionRejected("RETRYABLE_INFRA", "control", retryable=True, repairable=False),
            run=run,
            revision=revision,
            execution=execution,
        )
    except (ControlActionUnavailable, TaskNotFound):
        if not _safe_invalidate_control_approval(context, request):
            return _failure(
                context,
                StartExecutionRejected("RETRYABLE_INFRA", "control", retryable=True, repairable=False),
                run=run,
                revision=revision,
                execution=execution,
            )
        return _failure(
            context,
            StartExecutionRejected("VALIDATION_STALE", "control", repairable=False),
            run=run,
            revision=revision,
            execution=execution,
        )
    except (DatabaseError, DjangoValidationError):
        return _failure(
            context,
            StartExecutionRejected("RETRYABLE_INFRA", "control", retryable=True, repairable=False),
            run=run,
            revision=revision,
            execution=execution,
        )
    except IdempotencyConflict:
        return _failure(
            context,
            StartExecutionRejected("IDEMPOTENCY_CONFLICT", "idempotency_key", repairable=False),
            run=run,
            revision=revision,
            execution=execution,
        )
    except (IdempotencyInFlight, IdempotencyRecordImmutable):
        if run is not None and revision is not None and execution is not None:
            return _manual_response(context, run, revision, execution)
        return _failure(
            context,
            StartExecutionRejected("RETRYABLE_INFRA", "control", retryable=True, repairable=False),
        )
    except Exception:
        return _failure(
            context,
            StartExecutionRejected("RETRYABLE_INFRA", "control", retryable=True, repairable=False),
            run=run,
            revision=revision,
            execution=execution,
        )


__all__ = ["control_workflow_execution_with_context"]
