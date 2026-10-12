"""Deterministic read-only revalidation and immutable release preparation."""

import copy
import re
import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from pipeline.exceptions import PipelineException

from bkflow.harness.constants import (
    DebugMode,
    DebugSessionStatus,
    HarnessAction,
    HarnessRunStatus,
)
from bkflow.harness.models import (
    CapabilityBinding,
    DebugSession,
    EvidenceEvent,
    HarnessRun,
    ReleaseManifest,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.safety import is_safe_idempotency_key
from bkflow.harness.services.canonical import canonical_json_bytes, sha256_json
from bkflow.harness.services.debug.policy import context_matches_run
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.idempotency import (
    IdempotencyScope,
    acquire_idempotency,
    complete_idempotency,
    fail_idempotency,
)
from bkflow.harness.services.release.policy import ActionPolicy
from bkflow.harness.services.resolver import (
    CapabilityResolutionError,
    ProviderInfrastructureError,
    SchemaDriftError,
)
from bkflow.harness.services.validator import WorkflowValidator, recompute_p0_plan_hash
from bkflow.pipeline_converter.exceptions import (
    A2FlowConvertError,
    A2FlowValidationError,
)
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.models import Template, TemplateSnapshot

TOOL_NAME = HarnessAction.PREPARE_RELEASE
_REQUEST_FIELDS = frozenset(("run_id", "revision_id", "expected_plan_hash", "idempotency_key"))
# Test-only coordination point used to reproduce a state change between the
# unlocked seed read and the authoritative row-lock check.
test_after_run_lock_hook = None


class ReleasePreparationRejected(ValueError):
    """A safe prepare failure with no caller or provider details."""

    def __init__(
        self, code, path, *, category=None, repairable=True, retryable=False, next_action=None, invalidate=False
    ):
        self.code = code
        self.path = path
        self.category = category
        self.repairable = repairable
        self.retryable = retryable
        self.next_action = next_action
        self.invalidate = invalidate
        super().__init__(code)


@dataclass(frozen=True)
class PrepareReleaseRequest:
    """Closed model-controlled input for one release preparation."""

    run_id: str
    revision_id: str
    expected_plan_hash: str
    idempotency_key: str

    def as_dict(self):
        """Return the exact canonical idempotency payload."""
        return {
            "run_id": self.run_id,
            "revision_id": self.revision_id,
            "expected_plan_hash": self.expected_plan_hash,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class ReleaseValidationFacts:
    """Fresh server facts that participate in the immutable Manifest."""

    draft_tree_fingerprint: dict
    capability_snapshot: list
    validation_evidence_refs: list
    debug_evidence_refs: list
    risk_manifest: dict
    debug_session_id: uuid.UUID


def validate_prepare_request(payload):
    """Parse the exact four-field prepare request without accepting authority."""
    if not isinstance(payload, dict) or set(payload) != _REQUEST_FIELDS:
        raise ReleasePreparationRejected("SCHEMA_VALIDATION_ERROR", "request")
    values = dict(payload)
    for field_name in ("run_id", "revision_id"):
        value = values[field_name]
        try:
            normalized = str(uuid.UUID(value))
        except (ValueError, TypeError, AttributeError):
            raise ReleasePreparationRejected("SCHEMA_VALIDATION_ERROR", field_name) from None
        if not isinstance(value, str) or normalized != value:
            raise ReleasePreparationRejected("SCHEMA_VALIDATION_ERROR", field_name)
    if (
        not isinstance(values["expected_plan_hash"], str)
        or re.fullmatch(r"[0-9a-f]{64}", values["expected_plan_hash"]) is None
    ):
        raise ReleasePreparationRejected("SCHEMA_VALIDATION_ERROR", "expected_plan_hash")
    if not is_safe_idempotency_key(values["idempotency_key"]):
        raise ReleasePreparationRejected("SCHEMA_VALIDATION_ERROR", "idempotency_key")
    return PrepareReleaseRequest(**values)


def _canonicalize_lists(value):
    """Recursively normalize every list participating in a Manifest hash."""
    if isinstance(value, dict):
        return {key: _canonicalize_lists(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        normalized = [_canonicalize_lists(item) for item in value]
        return sorted(normalized, key=canonical_json_bytes)
    return value


def _managed_draft_artifact(run):
    """Return the sole well-shaped Harness draft reference."""
    artifacts = [
        item for item in run.artifact_references if isinstance(item, dict) and item.get("type") == "harness_draft"
    ]
    if len(artifacts) != 1:
        raise ReleasePreparationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True)
    artifact = artifacts[0]
    try:
        template_id = int(artifact.get("template_id"))
    except (TypeError, ValueError):
        raise ReleasePreparationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True) from None
    if isinstance(artifact.get("template_id"), bool) or template_id <= 0:
        raise ReleasePreparationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True)
    return artifact, template_id


def _validate_template_identity(context, template):
    """Ensure the managed template remains in the exact trusted tenant scope."""
    if (
        template.is_deleted
        or template.space_id != context.space_id
        or template.scope_type != context.scope_type
        or template.scope_value != context.scope_value
        or template.bk_app_code != context.platform_app
    ):
        raise ReleasePreparationRejected(
            "CAPABILITY_FORBIDDEN", "artifact_refs", category="PERMISSION", repairable=False
        )


def _current_validation_report(run, revision, pipeline_tree_hash, *, lock_rows):
    """Resolve the latest accepted VALIDATE checkpoint without writing a new one."""
    reports = ValidationReport.objects.filter(run=run, checkpoint="VALIDATE")
    if lock_rows:
        reports = reports.select_for_update()
    report = reports.order_by("-id").first()
    if (
        report is None
        or report.revision_id != revision.id
        or report.validator_version != WorkflowValidator.VERSION
        or report.result.get("valid") is not True
        or bool(report.errors)
        or report.result.get("pipeline_tree_hash") != pipeline_tree_hash
        or not report.result.get("converter_fingerprint")
    ):
        raise ReleasePreparationRejected("VALIDATION_STALE", "validation", invalidate=True)
    return report


def _fresh_capabilities(revision, report, resolver, *, lock_rows):
    """Re-resolve every exact binding for both conversion and Manifest projection."""
    bindings = CapabilityBinding.objects.filter(revision=revision)
    if lock_rows:
        bindings = bindings.select_for_update()
    bindings = list(bindings.order_by("node_id", "capability_ref"))
    snapshot = []
    resolved_bindings = []
    conversions = {}
    for binding in bindings:
        try:
            capability = resolver.resolve(binding.capability_ref, expected_schema_hash=binding.schema_hash)
        except ProviderInfrastructureError:
            raise
        except (CapabilityResolutionError, SchemaDriftError):
            raise ReleasePreparationRejected("VALIDATION_STALE", "bindings", invalidate=True) from None
        if (
            capability.capability_ref != binding.capability_ref
            or capability.resolved_version != binding.resolved_version
            or capability.schema_hash != binding.schema_hash
            or capability.conversion_fingerprint != binding.conversion_fingerprint
            or capability.risk_level != binding.risk
        ):
            raise ReleasePreparationRejected("VALIDATION_STALE", "bindings", invalidate=True)
        conversions[binding.node_id] = binding.conversion_fingerprint
        resolved_bindings.append(
            {
                "node_id": binding.node_id,
                "capability_ref": binding.capability_ref,
                "resolved_version": binding.resolved_version,
                "schema_hash": binding.schema_hash,
                "conversion_fingerprint": binding.conversion_fingerprint,
                "credential_ref": binding.credential_ref,
                "risk": binding.risk,
                "capability": capability,
            }
        )
        snapshot.append(
            {
                "capability_ref": binding.capability_ref,
                "conversion_fingerprint": binding.conversion_fingerprint,
                "node_id": binding.node_id,
                "resolved_version": binding.resolved_version,
                "risk_level": binding.risk,
                "schema_hash": binding.schema_hash,
            }
        )
    if report.result.get("capability_conversion_fingerprints") != conversions:
        raise ReleasePreparationRejected("VALIDATION_STALE", "bindings", invalidate=True)
    return _canonicalize_lists(snapshot), resolved_bindings


def _debug_evidence(context, run, revision, template, tree_fingerprint, *, lock_rows):
    """Require the latest exact GLOBAL completion and its append-only terminal Evidence."""
    sessions = DebugSession._base_manager.filter(run=run, revision=revision, template_id=template.id)
    if lock_rows:
        sessions = sessions.select_for_update()
    session = sessions.order_by("-create_at", "-id").first()
    static_snapshot = (
        {key: value for key, value in session.trusted_context_snapshot.items() if key != "correlation_id"}
        if session is not None and isinstance(session.trusted_context_snapshot, dict)
        else None
    )
    expected_snapshot = {
        "platform_key": context.platform_key,
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope_type": context.scope_type,
        "scope_value": context.scope_value,
        "target_environment": context.target_environment,
        "policy_version": context.policy_version,
        "mcp_contract_version": context.mcp_contract_version,
    }
    if (
        session is None
        or session.mode != DebugMode.GLOBAL
        or session.status != DebugSessionStatus.COMPLETED
        or session.plan_hash != revision.plan_hash
        or session.tree_fingerprint != tree_fingerprint
        or session.actor != context.actor
        or session.policy_version != context.policy_version
        or session.terminal_reason != "debug_completed"
        or static_snapshot != expected_snapshot
    ):
        raise ReleasePreparationRejected(
            "DEBUG_SESSION", "debug_session", next_action="start_debug_session", invalidate=True
        )
    events = EvidenceEvent._base_manager.filter(
        run=run,
        revision=revision,
        debug_session=session,
        event_type="DEBUG_SESSION_COMPLETED",
        action="get_debug_session",
    )
    if lock_rows:
        events = events.select_for_update()
    events = list(events.order_by("occurred_at", "id")[:2])
    expected_payload = {
        "session_id": str(session.id),
        "status": DebugSessionStatus.COMPLETED,
        "reason": "debug_completed",
    }
    if len(events) != 1 or events[0].redacted_payload != expected_payload:
        raise ReleasePreparationRejected(
            "DEBUG_SESSION", "debug_evidence", next_action="start_debug_session", invalidate=True
        )
    return session, events[0]


def revalidate_revision_for_release(
    context,
    run,
    revision,
    template,
    snapshot,
    *,
    resolver,
    lock_rows=False,
    converter_class=None,
    pipeline_validator=None,
    allow_published_snapshot=False,
    allow_template_pointer_advance=False,
):
    """Read current plan, schema, draft, validation and debug facts without persisting reports."""
    if not context_matches_run(context, run):
        raise ReleasePreparationRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False)
    _validate_template_identity(context, template)
    artifact, template_id = _managed_draft_artifact(run)
    if template_id != template.id:
        raise ReleasePreparationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True)
    revisions = WorkflowPlanRevision.objects.filter(run=run)
    if lock_rows:
        revisions = revisions.select_for_update()
    latest_revision = revisions.order_by("-sequence").first()
    if latest_revision is None or latest_revision.id != revision.id:
        raise ReleasePreparationRejected("VALIDATION_STALE", "revision_id", invalidate=True)
    if revision.plan_hash != recompute_p0_plan_hash(revision):
        raise ReleasePreparationRejected("VALIDATION_STALE", "expected_plan_hash", invalidate=True)
    if (
        artifact.get("revision_id") != str(revision.id)
        or (template.snapshot_id != snapshot.id and not allow_template_pointer_advance)
        or snapshot.template_id != template.id
        or (not snapshot.draft and not allow_published_snapshot)
        or snapshot.is_deleted
    ):
        raise ReleasePreparationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True)
    pipeline_tree_hash = sha256_json(snapshot.data)
    if artifact.get("pipeline_tree_hash") != pipeline_tree_hash:
        raise ReleasePreparationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True)
    report = _current_validation_report(run, revision, pipeline_tree_hash, lock_rows=lock_rows)
    capability_snapshot, resolved_bindings = _fresh_capabilities(revision, report, resolver, lock_rows=lock_rows)
    validator = WorkflowValidator(
        context,
        resolver=object(),
        converter_class=converter_class,
        pipeline_validator=pipeline_validator,
    )
    try:
        conversion = validator._convert(revision.canonical_a2flow, resolved_bindings)
        converted_tree_hash = sha256_json(conversion.pipeline_tree)
        # Existing template validators normalize the tree in place.  Validate a
        # defensive copy so the exact converter product remains the release
        # comparison authority.
        validator.pipeline_validator(copy.deepcopy(conversion.pipeline_tree))
    except (A2FlowValidationError, A2FlowConvertError, PipelineException, ValidationError):
        raise ReleasePreparationRejected("VALIDATION_STALE", "pipeline_tree", invalidate=True) from None
    if converted_tree_hash != pipeline_tree_hash or conversion.converter_fingerprint != report.result.get(
        "converter_fingerprint"
    ):
        raise ReleasePreparationRejected("VALIDATION_STALE", "pipeline_tree", invalidate=True)
    tree_fingerprint = _canonicalize_lists(compute_tree_fingerprint(snapshot.data))
    debug_session, debug_event = _debug_evidence(
        context, run, revision, template, tree_fingerprint, lock_rows=lock_rows
    )
    risk_manifest = {
        "capability_risks": [
            {"node_id": item["node_id"], "risk_level": item["risk_level"]} for item in capability_snapshot
        ]
    }
    return ReleaseValidationFacts(
        draft_tree_fingerprint=tree_fingerprint,
        capability_snapshot=capability_snapshot,
        validation_evidence_refs=["evidence://validation/{}".format(report.id)],
        debug_evidence_refs=["evidence://debug/{}".format(debug_event.id)],
        risk_manifest=_canonicalize_lists(risk_manifest),
        debug_session_id=debug_session.id,
    )


def _manifest_values(context, run, revision, template, snapshot, facts, *, action_policy, release_policy):
    """Build the complete deterministic Manifest value set from server facts."""
    postconditions = _canonicalize_lists(release_policy.postconditions_for(context.policy_version))
    required_approvals = _canonicalize_lists(
        action_policy.requirements_for(
            [HarnessAction.PUBLISH_WORKFLOW, HarnessAction.START_WORKFLOW_EXECUTION],
            context.policy_version,
        )
    )
    risk_manifest = dict(facts.risk_manifest)
    risk_manifest["action_risks"] = [
        {"action": item["action"], "risk_level": item["risk_level"]} for item in required_approvals
    ]
    return {
        "run": run,
        "revision": revision,
        "plan_hash": revision.plan_hash,
        "draft_template_id": template.id,
        "draft_snapshot_id": snapshot.id,
        "draft_tree_fingerprint": facts.draft_tree_fingerprint,
        "capability_snapshot": facts.capability_snapshot,
        "validation_evidence_refs": sorted(facts.validation_evidence_refs),
        "debug_evidence_refs": sorted(facts.debug_evidence_refs),
        "postcondition_spec": postconditions,
        "risk_manifest": _canonicalize_lists(risk_manifest),
        "required_approvals": required_approvals,
        "policy_version": context.policy_version,
        "target_environment": context.target_environment,
    }


def _manifest_artifact(manifest):
    """Project only immutable, non-secret release authority into the Envelope."""
    return {
        "type": "release_manifest",
        "manifest_id": str(manifest.id),
        "manifest_hash": manifest.manifest_hash,
        "draft_template_id": manifest.draft_template_id,
        "draft_snapshot_id": manifest.draft_snapshot_id,
        "target_environment": manifest.target_environment,
        "required_approvals": manifest.required_approvals,
        "validation_evidence_refs": manifest.validation_evidence_refs,
        "debug_evidence_refs": manifest.debug_evidence_refs,
        "postcondition_spec": manifest.postcondition_spec,
        "risk_manifest": manifest.risk_manifest,
    }


def _success_envelope(context, run, revision, manifest):
    """Return the common Envelope for a prepared immutable Manifest."""
    response = WorkflowValidator(context, resolver=object())._envelope(
        ok=True,
        run=run,
        revision=revision,
        plan_hash_value=revision.plan_hash,
        status=run.status,
        artifact_refs=[_manifest_artifact(manifest)],
    )
    response["summary"] = "Release manifest is ready."
    response["next_actions"] = [HarnessAction.PUBLISH_WORKFLOW]
    return response


def _set_draft_ready(run):
    """Invalidate release authority without creating a synthetic validation report."""
    locked = HarnessRun.objects.select_for_update().get(pk=run.pk)
    if locked.status in {HarnessRunStatus.RELEASE_READY, HarnessRunStatus.APPROVAL_PENDING}:
        locked.status = HarnessRunStatus.DRAFT_READY
        locked.save(update_fields=["status", "update_at"])


def _lifecycle_rejection(status):
    """Return the exact next P2 action for an authoritative locked run state."""
    if status == HarnessRunStatus.DRAFT_READY:
        return ReleasePreparationRejected("DEBUG_SESSION", "run_id", next_action="start_debug_session")
    if status == HarnessRunStatus.DEBUGGING:
        return ReleasePreparationRejected("DEBUG_SESSION", "run_id", next_action="get_debug_session")
    return ReleasePreparationRejected("VALIDATION_STALE", "run_id", repairable=False)


def prepare_release(
    context,
    request,
    *,
    resolver,
    release_policy,
    action_policy=None,
    converter_class=None,
    pipeline_validator=None,
):
    """Lock, revalidate and persist or safely replay one immutable ReleaseManifest."""
    action_policy = action_policy or ActionPolicy()
    seed_run = HarnessRun.objects.get(run_id=request.run_id)
    if not context_matches_run(context, seed_run):
        raise ReleasePreparationRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False)
    if seed_run.status in {HarnessRunStatus.DRAFT_READY, HarnessRunStatus.DEBUGGING}:
        raise _lifecycle_rejection(seed_run.status)
    if seed_run.status not in {HarnessRunStatus.RELEASE_READY, HarnessRunStatus.APPROVAL_PENDING}:
        raise ReleasePreparationRejected("VALIDATION_STALE", "run_id", repairable=False)

    scope = IdempotencyScope.for_run(
        context.platform_app,
        context.actor,
        context.space_id,
        TOOL_NAME,
        seed_run,
        request.idempotency_key,
    )
    request_hash = sha256_json({"request": request.as_dict(), "trusted_run_id": str(seed_run.run_id)})
    failure = None
    with transaction.atomic():
        acquisition = acquire_idempotency(scope, request_hash)
        try:
            with transaction.atomic():
                artifact, seed_template_id = _managed_draft_artifact(seed_run)
                template = Template.objects.select_for_update().get(pk=seed_template_id)
                run = HarnessRun.objects.select_for_update().get(pk=seed_run.pk)
                if test_after_run_lock_hook is not None:
                    test_after_run_lock_hook(run)
                if run.status != seed_run.status or run.status not in {
                    HarnessRunStatus.RELEASE_READY,
                    HarnessRunStatus.APPROVAL_PENDING,
                }:
                    raise _lifecycle_rejection(run.status)
                current_artifact, current_template_id = _managed_draft_artifact(run)
                if current_template_id != template.id or current_artifact != artifact:
                    raise ReleasePreparationRejected("VALIDATION_STALE", "artifact_refs", invalidate=True)
                revision = WorkflowPlanRevision.objects.select_for_update().get(pk=request.revision_id, run=run)
                if revision.plan_hash != request.expected_plan_hash:
                    raise ReleasePreparationRejected("VALIDATION_STALE", "expected_plan_hash", invalidate=True)
                snapshot = TemplateSnapshot.objects.select_for_update().get(pk=template.snapshot_id)
                facts = revalidate_revision_for_release(
                    context,
                    run,
                    revision,
                    template,
                    snapshot,
                    resolver=resolver,
                    lock_rows=True,
                    converter_class=converter_class,
                    pipeline_validator=pipeline_validator,
                )
                values = _manifest_values(
                    context,
                    run,
                    revision,
                    template,
                    snapshot,
                    facts,
                    action_policy=action_policy,
                    release_policy=release_policy,
                )
                candidate = ReleaseManifest(**values)
                candidate.full_clean(validate_unique=False)
                manifest = (
                    ReleaseManifest.objects.select_for_update().filter(manifest_hash=candidate.manifest_hash).first()
                )
                if acquisition.replayed:
                    if (
                        manifest is None
                        or acquisition.record.resource_reference != str(manifest.id)
                        or acquisition.response_snapshot.get("artifact_refs", [{}])[0].get("manifest_hash")
                        != manifest.manifest_hash
                    ):
                        raise ReleasePreparationRejected("VALIDATION_STALE", "manifest", invalidate=True)
                    return acquisition.response_snapshot
                if manifest is None:
                    manifest = ReleaseManifest.objects.create(**values)
                    record_evidence(
                        run=run,
                        revision=revision,
                        event_type="RELEASE_PREPARED",
                        action=TOOL_NAME,
                        payload={
                            "manifest_id": str(manifest.id),
                            "manifest_hash": manifest.manifest_hash,
                            "debug_session_id": str(facts.debug_session_id),
                            "required_approval_count": len(manifest.required_approvals),
                        },
                        actor=context.actor,
                        correlation_id=context.correlation_id,
                    )
                if manifest.required_approvals and run.status == HarnessRunStatus.RELEASE_READY:
                    run.status = HarnessRunStatus.APPROVAL_PENDING
                    run.save(update_fields=["status", "update_at"])
                response = _success_envelope(context, run, revision, manifest)
                complete_idempotency(
                    acquisition.record,
                    response,
                    run=run,
                    resource_reference=str(manifest.id),
                )
                return response
        except Exception as error:
            if not acquisition.replayed:
                fail_idempotency(acquisition.record)
            if isinstance(error, ReleasePreparationRejected) and error.invalidate:
                _set_draft_ready(seed_run)
            failure = error
    if failure is not None:
        raise failure
