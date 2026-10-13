"""Atomic creation of one revision-bound Harness DebugSession."""

import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from bkflow.harness.constants import DebugSessionStatus, HarnessRunStatus
from bkflow.harness.models import (
    CapabilityBinding,
    DebugSession,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.debug.adapter import DebugAdapter, DebugContextBusy
from bkflow.harness.services.debug.contracts import DebugSessionView
from bkflow.harness.services.debug.policy import (
    DebugStartRejected,
    context_matches_run,
    trusted_context_snapshot,
)
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.idempotency import (
    IdempotencyOutcome,
    IdempotencyScope,
    execute_idempotent,
)
from bkflow.harness.services.state import transition_run
from bkflow.harness.services.validator import WorkflowValidator, recompute_p0_plan_hash
from bkflow.template.models import Template, TemplateSnapshot

TOOL_NAME = "start_debug_session"
DEBUG_SESSION_TTL_SECONDS = 10 * 60


def _managed_draft_artifact(run):
    artifacts = [
        item for item in run.artifact_references if isinstance(item, dict) and item.get("type") == "harness_draft"
    ]
    if len(artifacts) != 1:
        raise DebugStartRejected("VALIDATION_STALE", "artifact_refs")
    return artifacts[0]


def _validate_session_artifact_identity(session, *, template_id=None, lock_revisions=False):
    """Bind a session to the exact managed template and latest run revision."""
    artifact = _managed_draft_artifact(session.run)
    raw_template_id = artifact.get("template_id")
    try:
        artifact_template_id = int(raw_template_id) if not isinstance(raw_template_id, bool) else None
    except (TypeError, ValueError):
        raise DebugStartRejected("VALIDATION_STALE", "artifact_refs") from None
    expected_template_id = session.template_id if template_id is None else template_id
    if (
        artifact_template_id != session.template_id
        or session.template_id != expected_template_id
        or artifact.get("revision_id") != str(session.revision_id)
    ):
        raise DebugStartRejected("VALIDATION_STALE", "artifact_refs")
    revisions = WorkflowPlanRevision.objects.filter(run=session.run)
    if lock_revisions:
        revisions = revisions.select_for_update()
    latest_revision = revisions.order_by("-sequence").first()
    if latest_revision is None or latest_revision.id != session.revision_id:
        raise DebugStartRejected("VALIDATION_STALE", "revision_id")
    return artifact


def _validate_template(context, template):
    if (
        template.is_deleted
        or template.space_id != context.space_id
        or template.scope_type != context.scope_type
        or template.scope_value != context.scope_value
        or template.bk_app_code != context.platform_app
    ):
        raise DebugStartRejected("CAPABILITY_FORBIDDEN", "artifact_refs", category="PERMISSION", repairable=False)


def _current_validation_report(run, revision, pipeline_tree_hash):
    report = ValidationReport.objects.select_for_update().filter(run=run, checkpoint="VALIDATE").order_by("-id").first()
    if (
        report is None
        or report.revision_id != revision.id
        or report.result.get("valid") is not True
        or report.errors
        or report.validator_version != WorkflowValidator.VERSION
        or report.result.get("pipeline_tree_hash") != pipeline_tree_hash
        or not report.result.get("converter_fingerprint")
    ):
        raise DebugStartRejected("VALIDATION_STALE", "revision_id")
    return report


def _reresolve_bindings(revision, resolver):
    expected_conversions = {}
    for binding in CapabilityBinding.objects.select_for_update().filter(revision=revision).order_by("node_id"):
        capability = resolver.resolve(binding.capability_ref, expected_schema_hash=binding.schema_hash)
        if (
            capability.capability_ref != binding.capability_ref
            or capability.resolved_version != binding.resolved_version
            or capability.schema_hash != binding.schema_hash
            or capability.conversion_fingerprint != binding.conversion_fingerprint
        ):
            raise DebugStartRejected("VALIDATION_STALE", "bindings")
        expected_conversions[binding.node_id] = binding.conversion_fingerprint
    return expected_conversions


def _success_envelope(context, run, revision, view):
    validator = WorkflowValidator(context, resolver=object())
    response = validator._envelope(
        ok=True,
        run=run,
        revision=revision,
        plan_hash_value=revision.plan_hash,
        status=HarnessRunStatus.DEBUGGING,
        artifact_refs=[view.as_artifact_ref()],
    )
    response["summary"] = "Debug session is ready."
    response["next_actions"] = ["run_debug", "get_debug_session"]
    return response


def start_debug_session(context, request, *, resolver, adapter_class=DebugAdapter):
    """Start one session after fresh revision, schema, draft, and lock checks."""
    with transaction.atomic():
        # Read only enough trusted state to enter the durable idempotency
        # namespace. A completed replay returns its original response without
        # reacquiring mutable template or session resources.
        seed_run = HarnessRun.objects.get(run_id=request.run_id)
        if not context_matches_run(context, seed_run):
            raise DebugStartRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False)
        scope = IdempotencyScope.for_run(
            context.platform_app,
            context.actor,
            context.space_id,
            TOOL_NAME,
            seed_run,
            request.idempotency_key,
        )
        trusted_idempotency_context = trusted_context_snapshot(context)
        trusted_idempotency_context.pop("correlation_id")
        request_hash = sha256_json({"request": request.as_dict(), "trusted_context": trusted_idempotency_context})

        def create_session():
            # Derive the server-owned template identity without a lock, then
            # acquire lifecycle rows in the order shared with TokenBroker:
            # Template -> HarnessRun/revision -> DebugSession.
            seed_artifact = _managed_draft_artifact(seed_run)
            try:
                template_id = int(seed_artifact["template_id"])
            except (KeyError, TypeError, ValueError):
                raise DebugStartRejected("VALIDATION_STALE", "artifact_refs") from None
            template = Template.objects.select_for_update().get(pk=template_id)
            run = HarnessRun.objects.select_for_update().get(pk=seed_run.pk)
            if not context_matches_run(context, run):
                raise DebugStartRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False)
            artifact = _managed_draft_artifact(run)
            try:
                current_template_id = int(artifact["template_id"])
            except (KeyError, TypeError, ValueError):
                raise DebugStartRejected("VALIDATION_STALE", "artifact_refs") from None
            if current_template_id != template.id:
                raise DebugStartRejected("VALIDATION_STALE", "artifact_refs")
            if run.status != HarnessRunStatus.DRAFT_READY:
                raise DebugStartRejected("DEBUG_CONFLICT", "run_id", category="DEBUG_CONFLICT", repairable=False)
            revision = WorkflowPlanRevision.objects.select_for_update().get(pk=request.revision_id, run=run)
            latest_revision = run.revisions.select_for_update().order_by("-sequence").first()
            if latest_revision is None or latest_revision.id != revision.id:
                raise DebugStartRejected("VALIDATION_STALE", "revision_id")
            if (
                revision.plan_hash != request.expected_plan_hash
                or recompute_p0_plan_hash(revision) != revision.plan_hash
            ):
                raise DebugStartRejected("VALIDATION_STALE", "expected_plan_hash")

            if artifact.get("revision_id") != str(revision.id):
                raise DebugStartRejected("VALIDATION_STALE", "artifact_refs")
            _validate_template(context, template)
            snapshot = TemplateSnapshot.objects.select_for_update().get(
                pk=template.snapshot_id,
                template_id=template.id,
                draft=True,
                is_deleted=False,
            )
            pipeline_tree = snapshot.data
            pipeline_tree_hash = sha256_json(pipeline_tree)
            if artifact.get("pipeline_tree_hash") != pipeline_tree_hash:
                raise DebugStartRejected("VALIDATION_STALE", "artifact_refs")
            report = _current_validation_report(run, revision, pipeline_tree_hash)
            expected_conversions = _reresolve_bindings(revision, resolver)
            report_conversions = report.result.get("capability_conversion_fingerprints")
            if report_conversions != expected_conversions:
                raise DebugStartRejected("VALIDATION_STALE", "bindings")

            if (
                DebugSession._base_manager.select_for_update()
                .filter(template_id=template.id, status__in=DebugSession.ACTIVE_STATUSES)
                .exists()
            ):
                raise DebugStartRejected("DEBUG_CONFLICT", "run_id", category="DEBUG_CONFLICT", repairable=False)

            try:
                adapter_snapshot = adapter_class(
                    template_id=template.id,
                    space_id=context.space_id,
                    pipeline_tree=pipeline_tree,
                ).prepare()
            except DebugContextBusy:
                raise DebugStartRejected(
                    "DEBUG_CONFLICT", "debug_context", category="DEBUG_CONFLICT", repairable=False
                ) from None
            now = timezone.now()
            try:
                with transaction.atomic():
                    session = DebugSession.objects.create(
                        run=run,
                        revision=revision,
                        template_id=template.id,
                        debug_context_id=adapter_snapshot.debug_context_id,
                        mode=request.mode,
                        status=DebugSessionStatus.ACTIVE,
                        plan_hash=revision.plan_hash,
                        tree_fingerprint=adapter_snapshot.tree_fingerprint,
                        actor=context.actor,
                        policy_version=context.policy_version,
                        trusted_context_snapshot=trusted_context_snapshot(context),
                        expires_at=now + datetime.timedelta(seconds=DEBUG_SESSION_TTL_SECONDS),
                        last_heartbeat_at=now,
                    )
            except IntegrityError:
                raise DebugStartRejected(
                    "DEBUG_CONFLICT", "debug_context", category="DEBUG_CONFLICT", repairable=False
                ) from None
            transition_run(run, HarnessRunStatus.DEBUGGING)
            run.refresh_from_db(fields=["status"])
            record_evidence(
                run=run,
                revision=revision,
                debug_session=session,
                event_type="DEBUG_SESSION_STARTED",
                action=TOOL_NAME,
                payload={
                    "session_id": str(session.id),
                    "debug_context_id": session.debug_context_id,
                    "template_id": session.template_id,
                    "mode": session.mode,
                    "plan_hash": session.plan_hash,
                    "tree_fingerprint_hash": sha256_json(session.tree_fingerprint),
                    "tree_fingerprint_node_count": len(session.tree_fingerprint["nodes"]),
                },
                actor=context.actor,
                correlation_id=context.correlation_id,
            )
            view = DebugSessionView(
                session_id=str(session.id),
                debug_context_id=session.debug_context_id,
                template_id=session.template_id,
                mode=session.mode,
                status=session.status,
                plan_hash=session.plan_hash,
                tree_fingerprint=adapter_snapshot.tree_fingerprint,
                input_schema=adapter_snapshot.input_schema,
                node_readiness=adapter_snapshot.node_readiness,
            )
            response = _success_envelope(context, run, revision, view)
            return IdempotencyOutcome(response_snapshot=response, run=run, resource_reference=str(session.id))

        return execute_idempotent(scope, request_hash, create_session).response_snapshot
