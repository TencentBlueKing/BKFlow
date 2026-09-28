"""Approval-bound, idempotent publication of one prepared release Manifest."""

import re
import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from bkflow.constants import TemplateOperationSource
from bkflow.exceptions import ValidationError as DomainValidationError
from bkflow.harness.constants import HarnessAction, HarnessRunStatus
from bkflow.harness.contracts import HarnessContextError
from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.models import (
    ApprovalRequest,
    HarnessRun,
    ReleaseManifest,
    ReleasePublication,
    WorkflowPlanRevision,
)
from bkflow.harness.safety import is_safe_harness_text, is_safe_idempotency_key
from bkflow.harness.services.approval import (
    ApprovalInvalid,
    ApprovalVerifier,
    normalize_approval_decision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.contract_versions import require_tool_enabled
from bkflow.harness.services.debug.policy import context_matches_run
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.idempotency import (
    IdempotencyScope,
    acquire_idempotency,
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
from bkflow.template.models import Template, TemplateOperationRecord, TemplateSnapshot
from bkflow.template.services.release import TemplateReleaseService

TOOL_NAME = HarnessAction.PUBLISH_WORKFLOW
_BASE_FIELDS = frozenset(("run_id", "manifest_id", "manifest_hash", "version", "description", "idempotency_key"))
_APPROVED_FIELDS = _BASE_FIELDS | frozenset(("approval_request_id", "approval_receipt_ref"))


class WorkflowPublicationRejected(ValueError):
    """A safe publication failure projected through the common Harness Envelope."""

    def __init__(
        self,
        code,
        path,
        *,
        category=None,
        repairable=True,
        retryable=False,
        invalidate=False,
        approval_request_id=None,
    ):
        self.code = code
        self.path = path
        self.category = category
        self.repairable = repairable
        self.retryable = retryable
        self.invalidate = invalidate
        self.approval_request_id = approval_request_id
        super().__init__(code)


@dataclass(frozen=True)
class PublishWorkflowRequest:
    """Closed model-controlled input for one exact publication action."""

    run_id: str
    manifest_id: str
    manifest_hash: str
    version: str
    description: str
    idempotency_key: str
    approval_request_id: str = None
    approval_receipt_ref: str = None

    @property
    def has_approval(self):
        return self.approval_request_id is not None

    def action_payload(self):
        """Return only the stable publication inputs; never include receipt material."""
        return {
            "run_id": self.run_id,
            "manifest_id": self.manifest_id,
            "manifest_hash": self.manifest_hash,
            "version": self.version,
            "description": self.description,
            "idempotency_key": self.idempotency_key,
            "approval_request_id": self.approval_request_id,
        }


def _canonical_uuid(value, field_name):
    try:
        normalized = str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", field_name) from None
    if not isinstance(value, str) or value != normalized:
        raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", field_name)
    return value


def validate_publish_request(payload):
    """Parse either phase of the exact two-call publication request."""
    if not isinstance(payload, dict) or frozenset(payload) not in {_BASE_FIELDS, _APPROVED_FIELDS}:
        raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", "request")
    values = dict(payload)
    _canonical_uuid(values.get("run_id"), "run_id")
    _canonical_uuid(values.get("manifest_id"), "manifest_id")
    if frozenset(payload) == _APPROVED_FIELDS:
        _canonical_uuid(values.get("approval_request_id"), "approval_request_id")
        if not is_safe_harness_text(
            values.get("approval_receipt_ref"), max_chars=255, max_bytes=1024, allow_empty=False
        ):
            raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", "approval_receipt_ref")
    if (
        not isinstance(values.get("manifest_hash"), str)
        or re.fullmatch(r"[0-9a-f]{64}", values["manifest_hash"]) is None
    ):
        raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", "manifest_hash")
    if not is_safe_harness_text(values.get("version"), max_chars=32, max_bytes=128, allow_empty=False):
        raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", "version")
    if not is_safe_harness_text(values.get("description"), max_chars=255, max_bytes=1024, allow_empty=True):
        raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", "description")
    if not is_safe_idempotency_key(values.get("idempotency_key")):
        raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", "idempotency_key")
    return PublishWorkflowRequest(**values)


def _failure(context, rejection, *, run=None, revision=None):
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
    )
    response["summary"] = "Workflow publication is blocked."
    if rejection.approval_request_id is not None:
        response["approval_request_id"] = str(rejection.approval_request_id)
    if rejection.code == "APPROVAL_REQUIRED":
        response["next_actions"] = ["obtain_approval"]
    return response


def _publication_artifact(publication):
    return {
        "type": "release_publication",
        "publication_id": str(publication.id),
        "publication_hash": publication.publication_hash,
        "manifest_id": str(publication.manifest_id),
        "published_template_id": publication.published_template_id,
        "published_snapshot_id": publication.published_snapshot_id,
        "published_version": publication.published_version,
    }


def _success(context, run, revision, publication):
    response = WorkflowValidator(context, resolver=object())._envelope(
        ok=True,
        run=run,
        revision=revision,
        plan_hash_value=revision.plan_hash,
        status=run.status,
        artifact_refs=[_publication_artifact(publication)],
    )
    response["summary"] = "Workflow was published."
    response["next_actions"] = [HarnessAction.START_WORKFLOW_EXECUTION]
    return response


def _load_seed(context, request):
    try:
        run = HarnessRun.objects.get(run_id=request.run_id)
        manifest = ReleaseManifest.objects.select_related("revision").get(pk=request.manifest_id, run=run)
    except (HarnessRun.DoesNotExist, ReleaseManifest.DoesNotExist):
        raise WorkflowPublicationRejected(
            "CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False
        ) from None
    if not context_matches_run(context, run):
        raise WorkflowPublicationRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False)
    if manifest.manifest_hash != request.manifest_hash:
        # A caller-provided hash is not server evidence and cannot revoke a
        # valid approval merely by being wrong.
        raise WorkflowPublicationRejected("VALIDATION_STALE", "manifest_hash")
    return run, manifest


def _policy_decision(context, manifest, request, action_policy, release_policy):
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
            raise WorkflowPublicationRejected("VALIDATION_STALE", "policy", invalidate=True)
        return action_policy.evaluate(
            action=HarnessAction.PUBLISH_WORKFLOW,
            manifest_hash=manifest.manifest_hash,
            plan_hash=manifest.plan_hash,
            target_resource={
                "template_id": manifest.draft_template_id,
                "draft_snapshot_id": manifest.draft_snapshot_id,
                "target_environment": manifest.target_environment,
            },
            normalized_params={"description": request.description, "version": request.version},
            policy_version=manifest.policy_version,
        )
    except ReleasePolicyUnavailable:
        raise
    except WorkflowPublicationRejected:
        raise
    except DjangoValidationError:
        raise WorkflowPublicationRejected("VALIDATION_STALE", "policy", invalidate=True) from None


def _approval_claims(context, run, manifest, decision):
    return {
        "actor": context.actor,
        "platform_app": context.platform_app,
        "space_id": context.space_id,
        "scope": run.scope,
        "environment": context.target_environment,
        "plan_hash": manifest.plan_hash,
        "action": HarnessAction.PUBLISH_WORKFLOW,
        "action_digest": decision.action_digest,
    }


def _approval_matches(approval, context, run, manifest, decision):
    return {
        "manifest_id": approval.manifest_id,
        "run_id": approval.run_id,
        "revision_id": approval.revision_id,
        "plan_hash": approval.plan_hash,
        "action": approval.action,
        "action_digest": approval.action_digest,
        "platform": approval.platform,
        "platform_app": approval.platform_app,
        "actor": approval.actor,
        "space_id": approval.space_id,
        "scope": approval.scope,
        "target_environment": approval.target_environment,
        "policy_version": approval.policy_version,
        "risk_level": approval.risk_level,
    } == {
        "manifest_id": manifest.id,
        "run_id": run.id,
        "revision_id": manifest.revision_id,
        "plan_hash": manifest.plan_hash,
        "action": HarnessAction.PUBLISH_WORKFLOW,
        "action_digest": decision.action_digest,
        "platform": run.platform,
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope": run.scope,
        "target_environment": context.target_environment,
        "policy_version": context.policy_version,
        "risk_level": decision.risk_level,
    }


def _approval_values(context, run, manifest, request, decision):
    return {
        "manifest": manifest,
        "run": run,
        "revision_id": manifest.revision_id,
        "plan_hash": manifest.plan_hash,
        "action": HarnessAction.PUBLISH_WORKFLOW,
        "action_digest": decision.action_digest,
        "platform": run.platform,
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope": run.scope,
        "target_environment": context.target_environment,
        "policy_version": context.policy_version,
        "risk_level": decision.risk_level,
        "risk_summary": {
            "action": HarnessAction.PUBLISH_WORKFLOW,
            "description_digest": sha256_json(request.description),
            "target_environment": context.target_environment,
            "template_id": manifest.draft_template_id,
            "version": request.version,
        },
    }


def _locked_release_graph(
    context,
    run,
    manifest,
    request,
    *,
    resolver,
    action_policy,
    release_policy,
    converter_class,
    pipeline_validator,
):
    """Lock in the shared order and return freshly verified publication facts."""
    template = Template.objects.select_for_update().get(pk=manifest.draft_template_id)
    locked_run = HarnessRun.objects.select_for_update().get(pk=run.pk)
    if not context_matches_run(context, locked_run):
        raise WorkflowPublicationRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False)
    if locked_run.status not in {
        HarnessRunStatus.RELEASE_READY,
        HarnessRunStatus.APPROVAL_PENDING,
        HarnessRunStatus.PUBLISHING,
        HarnessRunStatus.PUBLISHED,
    }:
        raise WorkflowPublicationRejected("VALIDATION_STALE", "run_id", repairable=False)
    revision = WorkflowPlanRevision.objects.select_for_update().get(pk=manifest.revision_id, run=locked_run)
    snapshot = TemplateSnapshot.objects.select_for_update().get(pk=manifest.draft_snapshot_id)
    drafts = list(
        TemplateSnapshot.objects.select_for_update().filter(template_id=template.id, draft=True).order_by("id")[:2]
    )
    if snapshot.draft and (len(drafts) != 1 or drafts[0].id != snapshot.id):
        raise WorkflowPublicationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True)
    if not snapshot.draft and locked_run.status == HarnessRunStatus.PUBLISHING and drafts:
        raise WorkflowPublicationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True)
    try:
        revalidate_revision_for_release(
            context,
            locked_run,
            revision,
            template,
            snapshot,
            resolver=resolver,
            lock_rows=True,
            converter_class=converter_class,
            pipeline_validator=pipeline_validator,
            allow_published_snapshot=locked_run.status in {HarnessRunStatus.PUBLISHING, HarnessRunStatus.PUBLISHED},
        )
    except ReleasePreparationRejected as error:
        raise WorkflowPublicationRejected(
            error.code,
            error.path,
            category=error.category,
            repairable=error.repairable,
            retryable=error.retryable,
            invalidate=error.invalidate,
        ) from None
    locked_manifest = ReleaseManifest.objects.select_for_update().get(pk=manifest.pk, run=locked_run)
    if locked_manifest.manifest_hash != request.manifest_hash:
        raise WorkflowPublicationRejected("VALIDATION_STALE", "manifest_hash", invalidate=True)
    decision = _policy_decision(context, locked_manifest, request, action_policy, release_policy)
    return template, locked_run, revision, snapshot, locked_manifest, decision


def _get_or_create_approval(context, run, manifest, request, decision):
    existing = (
        ApprovalRequest.objects.select_for_update()
        .filter(
            manifest=manifest,
            action=HarnessAction.PUBLISH_WORKFLOW,
            action_digest=decision.action_digest,
            status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED],
        )
        .first()
    )
    if existing is not None:
        if not _approval_matches(existing, context, run, manifest, decision):
            raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
        return existing
    try:
        with transaction.atomic():
            return ApprovalRequest.objects.create(**_approval_values(context, run, manifest, request, decision))
    except IntegrityError:
        existing = ApprovalRequest.objects.select_for_update().get(
            manifest=manifest,
            action=HarnessAction.PUBLISH_WORKFLOW,
            action_digest=decision.action_digest,
            status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED],
        )
        if not _approval_matches(existing, context, run, manifest, decision):
            raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
        return existing


def _invalidate(run, approval=None):
    with transaction.atomic():
        locked_run = HarnessRun.objects.select_for_update().get(pk=run.pk)
        if locked_run.status in {
            HarnessRunStatus.RELEASE_READY,
            HarnessRunStatus.APPROVAL_PENDING,
            HarnessRunStatus.PUBLISHING,
        }:
            locked_run.status = HarnessRunStatus.DRAFT_READY
            locked_run.save(update_fields=["status", "update_at"])
        approvals = ApprovalRequest.objects.select_for_update().filter(
            run=locked_run,
            action=HarnessAction.PUBLISH_WORKFLOW,
            status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED],
        )
        if approval is not None:
            approvals = approvals.filter(pk=approval.pk)
        for locked_approval in approvals:
            if locked_approval.status in {ApprovalRequest.Status.PENDING, ApprovalRequest.Status.VERIFIED}:
                locked_approval.status = ApprovalRequest.Status.REVOKED
                locked_approval.save(update_fields=["status", "active_approval_key", "update_at"])


def _request_approval(
    context,
    run,
    manifest,
    request,
    *,
    resolver,
    action_policy,
    release_policy,
    converter_class,
    pipeline_validator,
):
    try:
        with transaction.atomic():
            _, locked_run, revision, _, locked_manifest, decision = _locked_release_graph(
                context,
                run,
                manifest,
                request,
                resolver=resolver,
                action_policy=action_policy,
                release_policy=release_policy,
                converter_class=converter_class,
                pipeline_validator=pipeline_validator,
            )
            if not decision.requires_approval:
                return None
            approval = _get_or_create_approval(context, locked_run, locked_manifest, request, decision)
            return _failure(
                context,
                WorkflowPublicationRejected(
                    "APPROVAL_REQUIRED",
                    "approval_receipt_ref",
                    repairable=False,
                    approval_request_id=approval.id,
                ),
                run=locked_run,
                revision=revision,
            )
    except WorkflowPublicationRejected as error:
        if error.invalidate:
            _invalidate(run)
        raise


def _exact_publication(publication, manifest, snapshot, request, run):
    return (
        publication.manifest_id == manifest.id
        and publication.published_template_id == manifest.draft_template_id
        and publication.published_snapshot_id == manifest.draft_snapshot_id
        and publication.published_version == request.version
        and publication.operator == run.actor
        and snapshot.template_id == manifest.draft_template_id
        and snapshot.id == manifest.draft_snapshot_id
        and snapshot.draft is False
        and snapshot.version == request.version
        and snapshot.desc == request.description
        and snapshot.operator == run.actor
    )


def _can_reconcile_published_snapshot(template, run, manifest, snapshot, request):
    """Recognize only the exact former draft after a lost domain-service response."""
    if not (
        run.status == HarnessRunStatus.PUBLISHING
        and template.snapshot_id == manifest.draft_snapshot_id
        and snapshot.id == manifest.draft_snapshot_id
        and snapshot.template_id == manifest.draft_template_id
        and snapshot.draft is False
        and snapshot.version == request.version
        and snapshot.desc == request.description
        and snapshot.operator == run.actor
    ):
        return False
    records = TemplateOperationRecord.objects.filter(
        operate_source=TemplateOperationSource.api.name,
        operate_type="release",
        instance_id=template.id,
        operator=run.actor,
    )
    exact = [record for record in records if record.extra_info == {"version": request.version}]
    return len(exact) == 1


def _verify_approval_outside_transaction(context, run, manifest, request, decision, approval, verifier):
    if not _approval_matches(approval, context, run, manifest, decision):
        raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
    if approval.status == ApprovalRequest.Status.VERIFIED:
        if (
            approval.receipt_ref != request.approval_receipt_ref
            or approval.expires_at is None
            or approval.expires_at <= timezone.now()
        ):
            raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
        return None
    if approval.status != ApprovalRequest.Status.PENDING:
        raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
    decision_result = normalize_approval_decision(
        (verifier or ApprovalVerifier()).verify(
            request.approval_receipt_ref,
            _approval_claims(context, run, manifest, decision),
        ),
        request.approval_receipt_ref,
    )
    if not decision_result.allowed:
        raise WorkflowPublicationRejected(
            decision_result.failure_code,
            "approval_receipt_ref",
            repairable=False,
            approval_request_id=approval.id,
        )
    return decision_result


def _persist_verified_approval(approval, request, decision_result):
    if approval.status == ApprovalRequest.Status.VERIFIED:
        if approval.receipt_ref != request.approval_receipt_ref or approval.expires_at <= timezone.now():
            raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
        return
    if approval.status != ApprovalRequest.Status.PENDING or decision_result is None:
        raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
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
    run,
    manifest,
    request,
    *,
    resolver,
    action_policy,
    release_policy,
    approval,
    approval_decision,
    converter_class,
    pipeline_validator,
):
    """Commit a verified receipt after a fresh graph check, before publication starts."""
    try:
        with transaction.atomic():
            _, locked_run, _, _, locked_manifest, decision = _locked_release_graph(
                context,
                run,
                manifest,
                request,
                resolver=resolver,
                action_policy=action_policy,
                release_policy=release_policy,
                converter_class=converter_class,
                pipeline_validator=pipeline_validator,
            )
            locked_approval = ApprovalRequest.objects.select_for_update().get(pk=approval.pk)
            if not _approval_matches(locked_approval, context, locked_run, locked_manifest, decision):
                raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
            expected_claims_digest = sha256_json(_approval_claims(context, locked_run, locked_manifest, decision))
            if approval_decision.claims_digest != expected_claims_digest:
                raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False)
            _persist_verified_approval(locked_approval, request, approval_decision)
            return locked_approval
    except WorkflowPublicationRejected as error:
        if error.invalidate:
            _invalidate(run, approval)
        raise


def _publish(
    context,
    run,
    manifest,
    request,
    *,
    resolver,
    action_policy,
    release_policy,
    approval,
    approval_decision,
    converter_class,
    pipeline_validator,
):
    scope = IdempotencyScope.for_run(
        context.platform_app,
        context.actor,
        context.space_id,
        TOOL_NAME,
        run,
        request.idempotency_key,
    )
    request_hash = sha256_json({"request": request.action_payload(), "trusted_run_id": str(run.run_id)})
    try:
        with transaction.atomic():
            acquisition = acquire_idempotency(scope, request_hash)
            template, locked_run, revision, snapshot, locked_manifest, decision = _locked_release_graph(
                context,
                run,
                manifest,
                request,
                resolver=resolver,
                action_policy=action_policy,
                release_policy=release_policy,
                converter_class=converter_class,
                pipeline_validator=pipeline_validator,
            )
            locked_approval = None
            if decision.requires_approval:
                if approval is None:
                    raise WorkflowPublicationRejected("APPROVAL_REQUIRED", "approval_receipt_ref")
                locked_approval = ApprovalRequest.objects.select_for_update().get(pk=approval.pk)
                if not _approval_matches(locked_approval, context, locked_run, locked_manifest, decision):
                    raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_request_id", repairable=False)
                _persist_verified_approval(locked_approval, request, approval_decision)
            publication = ReleasePublication.objects.select_for_update().filter(manifest=locked_manifest).first()
            if publication is not None:
                if not _exact_publication(publication, locked_manifest, snapshot, request, locked_run):
                    raise WorkflowPublicationRejected("VALIDATION_STALE", "publication", invalidate=True)
                if locked_run.status == HarnessRunStatus.PUBLISHING:
                    locked_run.status = HarnessRunStatus.PUBLISHED
                    locked_run.save(update_fields=["status", "update_at"])
                if locked_run.status != HarnessRunStatus.PUBLISHED:
                    raise WorkflowPublicationRejected("VALIDATION_STALE", "run_id", repairable=False)
                response = _success(context, locked_run, revision, publication)
                if acquisition.replayed:
                    if (
                        acquisition.record.resource_reference != str(publication.id)
                        or acquisition.response_snapshot != response
                    ):
                        raise WorkflowPublicationRejected("VALIDATION_STALE", "publication", invalidate=True)
                    return acquisition.response_snapshot
                complete_idempotency(
                    acquisition.record,
                    response,
                    run=locked_run,
                    resource_reference=str(publication.id),
                )
                return response
            if acquisition.replayed:
                raise WorkflowPublicationRejected("VALIDATION_STALE", "publication", invalidate=True)
            if snapshot.draft:
                if locked_run.status not in {
                    HarnessRunStatus.RELEASE_READY,
                    HarnessRunStatus.APPROVAL_PENDING,
                    HarnessRunStatus.PUBLISHING,
                }:
                    raise WorkflowPublicationRejected("VALIDATION_STALE", "run_id", repairable=False)
                if locked_run.status != HarnessRunStatus.PUBLISHING:
                    locked_run.status = HarnessRunStatus.PUBLISHING
                    locked_run.save(update_fields=["status", "update_at"])
                published_snapshot = TemplateReleaseService.release(
                    template,
                    {"version": request.version, "desc": request.description, "force": False},
                    context.actor,
                    TemplateOperationSource.api.name,
                    emit_webhook=True,
                    expected_draft_snapshot_id=locked_manifest.draft_snapshot_id,
                )
            else:
                if not _can_reconcile_published_snapshot(template, locked_run, locked_manifest, snapshot, request):
                    raise WorkflowPublicationRejected("VALIDATION_STALE", "publication", invalidate=True)
                published_snapshot = snapshot
            publication = ReleasePublication.objects.create(
                manifest=locked_manifest,
                published_template_id=template.id,
                published_snapshot_id=published_snapshot.id,
                published_version=request.version,
                operator=context.actor,
                publish_idempotency_ref="idempotency://publish/{}".format(acquisition.record.id),
            )
            record_evidence(
                run=locked_run,
                revision=revision,
                event_type="WORKFLOW_PUBLISHED",
                action=HarnessAction.PUBLISH_WORKFLOW,
                payload={
                    "manifest_id": str(locked_manifest.id),
                    "manifest_hash": locked_manifest.manifest_hash,
                    "publication_id": str(publication.id),
                    "publication_hash": publication.publication_hash,
                    "published_snapshot_id": published_snapshot.id,
                    "published_version": request.version,
                },
                actor=context.actor,
                correlation_id=context.correlation_id,
            )
            locked_run.status = HarnessRunStatus.PUBLISHED
            locked_run.save(update_fields=["status", "update_at"])
            response = _success(context, locked_run, revision, publication)
            complete_idempotency(
                acquisition.record,
                response,
                run=locked_run,
                resource_reference=str(publication.id),
            )
            return response
    except Exception as error:
        if isinstance(error, WorkflowPublicationRejected) and error.invalidate:
            _invalidate(run, approval)
        raise


def publish_workflow_with_context(
    context,
    payload,
    plugin_schema_service=None,
    *,
    resolver=None,
    release_policy=None,
    action_policy=None,
    approval_verifier=None,
    converter_class=None,
    pipeline_validator=None,
):
    """Validate, authorize, and atomically publish one exact Manifest draft."""
    run = None
    revision = None
    try:
        request = validate_publish_request(payload)
        require_tool_enabled(context, TOOL_NAME)
        if release_policy is None:
            raise WorkflowPublicationRejected("RELEASE_POLICY_UNAVAILABLE", "policy", repairable=False)
        active_resolver = resolver or CapabilityResolver(plugin_schema_service)
        action_policy = action_policy or ActionPolicy()
        run, manifest = _load_seed(context, request)
        revision = manifest.revision
        try:
            decision = _policy_decision(context, manifest, request, action_policy, release_policy)
        except WorkflowPublicationRejected as error:
            if error.invalidate:
                _invalidate(run)
            raise
        if decision.requires_approval and not request.has_approval:
            return _request_approval(
                context,
                run,
                manifest,
                request,
                resolver=active_resolver,
                action_policy=action_policy,
                release_policy=release_policy,
                converter_class=converter_class,
                pipeline_validator=pipeline_validator,
            )
        approval = None
        approval_decision = None
        if decision.requires_approval:
            try:
                approval = ApprovalRequest.objects.get(pk=request.approval_request_id)
            except ApprovalRequest.DoesNotExist:
                raise WorkflowPublicationRejected("APPROVAL_INVALID", "approval_request_id", repairable=False) from None
            approval_decision = _verify_approval_outside_transaction(
                context,
                run,
                manifest,
                request,
                decision,
                approval,
                approval_verifier,
            )
            if approval_decision is not None:
                approval = _commit_verified_approval(
                    context,
                    run,
                    manifest,
                    request,
                    resolver=active_resolver,
                    action_policy=action_policy,
                    release_policy=release_policy,
                    approval=approval,
                    approval_decision=approval_decision,
                    converter_class=converter_class,
                    pipeline_validator=pipeline_validator,
                )
                approval_decision = None
        elif request.has_approval:
            raise WorkflowPublicationRejected("SCHEMA_VALIDATION_ERROR", "approval_request_id")
        return _publish(
            context,
            run,
            manifest,
            request,
            resolver=active_resolver,
            action_policy=action_policy,
            release_policy=release_policy,
            approval=approval,
            approval_decision=approval_decision,
            converter_class=converter_class,
            pipeline_validator=pipeline_validator,
        )
    except WorkflowPublicationRejected as rejection:
        return _failure(context, rejection, run=run, revision=revision)
    except HarnessContextError as error:
        return _failure(
            context,
            WorkflowPublicationRejected(error.code, "publication", repairable=False),
            run=run,
            revision=revision,
        )
    except IdempotencyConflict:
        return _failure(
            context,
            WorkflowPublicationRejected("IDEMPOTENCY_CONFLICT", "idempotency_key", repairable=False),
            run=run,
            revision=revision,
        )
    except (IdempotencyInFlight, IdempotencyRecordImmutable, ProviderInfrastructureError, DatabaseError):
        return _failure(
            context,
            WorkflowPublicationRejected("RETRYABLE_INFRA", "publication", retryable=True),
            run=run,
            revision=revision,
        )
    except ReleasePolicyUnavailable:
        return _failure(
            context,
            WorkflowPublicationRejected("RELEASE_POLICY_UNAVAILABLE", "policy", repairable=False),
            run=run,
            revision=revision,
        )
    except DomainValidationError as error:
        code = "VERSION_CONFLICT" if "版本已存在" in str(error) else "VALIDATION_STALE"
        return _failure(
            context,
            WorkflowPublicationRejected(code, "version", repairable=True),
            run=run,
            revision=revision,
        )
    except (DjangoValidationError, ApprovalInvalid):
        return _failure(
            context,
            WorkflowPublicationRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False),
            run=run,
            revision=revision,
        )
    except (Template.DoesNotExist, TemplateSnapshot.DoesNotExist, WorkflowPlanRevision.DoesNotExist):
        return _failure(
            context,
            WorkflowPublicationRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False),
            run=run,
            revision=revision,
        )
    except Exception:
        return _failure(
            context,
            WorkflowPublicationRejected("RETRYABLE_INFRA", "publication", retryable=True),
            run=run,
            revision=revision,
        )


__all__ = ["publish_workflow_with_context", "validate_publish_request"]
