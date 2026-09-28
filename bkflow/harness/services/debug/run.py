"""Bounded Harness dispatch for revision-bound step and global debug."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from bkflow.harness.constants import (
    DebugExecutionMode,
    DebugMode,
    DebugSessionStatus,
    HarnessRunStatus,
)
from bkflow.harness.models import (
    DebugSession,
    HarnessRun,
    TokenLease,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.contract_versions import is_harness_real_step_enabled
from bkflow.harness.services.debug.adapter import DebugAdapter
from bkflow.harness.services.debug.approval import (
    DebugApprovalVerifier,
    normalize_approval_decision,
)
from bkflow.harness.services.debug.policy import DebugStartRejected, context_matches_run
from bkflow.harness.services.debug.session import (
    _reresolve_bindings,
    _validate_session_artifact_identity,
    _validate_template,
)
from bkflow.harness.services.evidence import (
    evidence_projection_omission_reason,
    project_evidence_payload,
    record_evidence,
)
from bkflow.harness.services.idempotency import (
    IdempotencyOutcome,
    IdempotencyScope,
    acquire_debug_session_barrier,
    complete_idempotency,
    fail_idempotency,
)
from bkflow.harness.services.state import transition_run
from bkflow.harness.services.token_broker import TokenBroker
from bkflow.harness.services.validator import WorkflowValidator, recompute_p0_plan_hash
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.debug.service import DebugConflictError, DebugStateError
from bkflow.template.models import Template, TemplateSnapshot

TOOL_NAME = "run_debug"


def _session_matches_context(context, session):
    snapshot = session.trusted_context_snapshot
    fields = (
        "platform_key",
        "platform_app",
        "actor",
        "space_id",
        "scope_type",
        "scope_value",
        "target_environment",
        "policy_version",
        "mcp_contract_version",
    )
    return (
        context_matches_run(context, session.run)
        and isinstance(snapshot, dict)
        and all(snapshot.get(field) == getattr(context, field) for field in fields)
        and session.actor == context.actor
        and session.policy_version == context.policy_version
    )


def _error_envelope(context, session, code, path="debug", *, category=None, repairable=True):
    rejection = DebugStartRejected(code, path, category=category, repairable=repairable)
    validator = WorkflowValidator(context, resolver=object())
    response = validator._envelope(
        ok=False,
        run=session.run,
        revision=session.revision,
        plan_hash_value=session.plan_hash,
        status=HarnessRunStatus.DEBUGGING,
        errors=[
            validator._input_failure(
                {},
                rejection.code,
                path=rejection.path,
                category=rejection.category,
                repairable=rejection.repairable,
            )["errors"][0]
        ],
    )
    response["summary"] = "Debug execution requires attention."
    return response


def _safe_result_projection(result):
    """Normalize and redact every value returned by the legacy debug service."""
    if not isinstance(result, dict) or result.get("status") not in {"running", "finished", "failed"}:
        raise DebugStateError("debug result is invalid")
    status = result["status"]
    task_id = result.get("task_id")
    if task_id is not None and (isinstance(task_id, bool) or not isinstance(task_id, int) or task_id <= 0):
        raise DebugStateError("debug result is invalid")
    if status == "running" and task_id is None:
        raise DebugStateError("debug result is invalid")
    value = {
        "status": status,
        "task_id": task_id,
        "outputs": project_evidence_payload(result.get("outputs")),
        "updated_global_vars": project_evidence_payload(result.get("updated_global_vars")),
        "has_error": status == "failed" or bool(result.get("error_detail")),
    }
    if "selected_flow_ids" in result:
        value["selected_flow_ids"] = project_evidence_payload(result.get("selected_flow_ids"))
        value["condition_results"] = project_evidence_payload(result.get("condition_results", []))
    return value


def _result_artifact(session, request, result):
    value = {
        "type": "debug_run",
        "session_id": str(session.id),
        "mode": request.mode,
        "node_id": request.node_id if request.mode == DebugMode.STEP else None,
        "execution_mode": request.execution_mode,
        "status": result["status"],
        "outputs": result.get("outputs"),
        "updated_global_vars": result.get("updated_global_vars"),
        "engine_ref": {"task_id": result["task_id"]} if result.get("task_id") else None,
    }
    if result["has_error"]:
        value["error"] = {
            "code": "DEBUG_EXECUTION_FAILED",
            "message": "Debug execution failed.",
        }
    if "selected_flow_ids" in result:
        value["selected_flow_ids"] = result["selected_flow_ids"]
        value["condition_results"] = result.get("condition_results", [])
    return value


def _success_envelope(context, session, request, result):
    validator = WorkflowValidator(context, resolver=object())
    response = validator._envelope(
        ok=True,
        run=session.run,
        revision=session.revision,
        plan_hash_value=session.plan_hash,
        status=session.run.status,
        artifact_refs=[_result_artifact(session, request, result)],
    )
    response["summary"] = "Debug execution accepted."
    response["next_actions"] = (
        ["run_debug", "get_debug_session"]
        if session.status == DebugSessionStatus.ACTIVE and result["status"] != "running"
        else ["get_debug_session"]
    )
    return response


def _approval_claims(context, session, request, now):
    return {
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope_type": context.scope_type,
        "scope_value": context.scope_value,
        "environment": context.target_environment,
        "plan_hash": session.plan_hash,
        "action": "run_debug_real_step",
        "node_id": request.node_id,
        "expires_after": now,
    }


def _authorize_real_step(
    context,
    session,
    request,
    *,
    approval_verifier,
    token_broker,
    allow_real,
):
    if not allow_real or not is_harness_real_step_enabled(context.space_id):
        raise DebugStartRejected("APPROVAL_REQUIRED", "execution_mode", repairable=False)
    if not request.approval_receipt_ref:
        raise DebugStartRejected("APPROVAL_REQUIRED", "approval_receipt_ref", repairable=False)
    now = timezone.now()
    try:
        decision = normalize_approval_decision(
            approval_verifier.verify(
                request.approval_receipt_ref,
                _approval_claims(context, session, request, now),
            ),
            request.approval_receipt_ref,
        )
    except Exception as error:
        if isinstance(error, DebugStartRejected):
            raise
        raise DebugStartRejected("APPROVAL_INVALID", "approval_receipt_ref", repairable=False) from None
    if not decision.allowed:
        code = "APPROVAL_REQUIRED" if decision.reason == "verifier_unavailable" else "APPROVAL_INVALID"
        raise DebugStartRejected(code, "approval_receipt_ref", repairable=False)
    live_lease = (
        TokenLease._base_manager.filter(
            session=session,
            resource_type=TokenLease.Resource.TEMPLATE,
            resource_id=str(session.template_id),
            permission=TokenLease.Permission.MOCK,
            status=TokenLease.Status.ACTIVE,
            expires_at__gt=now,
            revoked_at__isnull=True,
        )
        .order_by("-issued_at")
        .first()
    )
    if live_lease is None:
        raise DebugStartRejected("TOKEN_LEASE", "session_id", repairable=False)
    try:
        handle = token_broker.acquire_debug_lease(context, session)
    except ValidationError:
        raise DebugStartRejected("TOKEN_LEASE", "session_id", repairable=False) from None
    return decision, handle


def _evidence(session, event_type, request, *, result=None, approval_decision=None):
    payload = {
        "session_id": str(session.id),
        "mode": request.mode,
        "execution_mode": request.execution_mode,
        "node_id": request.node_id,
        "input_fingerprint": sha256_json(request.input_overrides if request.mode == DebugMode.STEP else request.inputs),
    }
    if result is not None:
        payload.update({"status": result.get("status"), "task_id": result.get("task_id")})
        outputs = result.get("outputs")
        omission_reason = evidence_projection_omission_reason(outputs)
        if omission_reason is None:
            payload["output_fingerprint"] = sha256_json(outputs)
        else:
            payload["output_omitted"] = True
            payload["output_omission_reason"] = omission_reason
    if approval_decision is not None:
        payload["approval"] = {
            "allowed": approval_decision.allowed,
            "provider": approval_decision.provider,
            "receipt_digest": approval_decision.receipt_digest,
            "claims_digest": approval_decision.claims_digest,
            "reason": approval_decision.reason,
        }
    record_evidence(
        run=session.run,
        revision=session.revision,
        debug_session=session,
        event_type=event_type,
        action=TOOL_NAME,
        payload=payload,
        actor=session.actor,
        correlation_id=session.trusted_context_snapshot["correlation_id"],
    )


def _fail_session(context, session, *, token_broker):
    """Revoke authority before closing a synchronous failed assertion attempt."""
    token_broker.revoke_active_leases(context, session)
    session.status = DebugSessionStatus.FAILED
    session.current_task_id = None
    session.terminal_reason = "debug_failed"
    session.save(update_fields=["status", "current_task_id", "terminal_reason"])
    if session.run.status == HarnessRunStatus.DEBUGGING:
        transition_run(session.run, HarnessRunStatus.DRAFT_READY)
        session.run.refresh_from_db(fields=["status"])


def run_debug(
    context,
    request,
    *,
    resolver,
    adapter_class=DebugAdapter,
    approval_verifier=None,
    token_broker=None,
    allow_real=False,
):
    """Revalidate and dispatch one idempotent debug operation."""
    approval_verifier = approval_verifier or DebugApprovalVerifier()
    token_broker = token_broker or TokenBroker()
    seed = DebugSession._base_manager.select_related("run", "revision").get(pk=request.session_id)
    if not _session_matches_context(context, seed):
        raise DebugStartRejected("CAPABILITY_FORBIDDEN", "session_id", category="PERMISSION", repairable=False)
    # Stale managed identity must win over even a previously completed replay.
    # This read-only preflight also avoids creating a barrier for known-stale work.
    _validate_session_artifact_identity(seed)
    scope = IdempotencyScope.for_run(
        context.platform_app,
        context.actor,
        context.space_id,
        TOOL_NAME,
        seed.run,
        request.idempotency_key,
    )
    request_hash = sha256_json({"request": request.as_dict(), "session_id": str(seed.id)})
    acquisition = acquire_debug_session_barrier(
        scope,
        request_hash,
        seed,
        blocking_tool_names=("run_debug", "control_debug_session"),
    )
    if acquisition.replayed:
        return acquisition.response_snapshot
    adapter_entered = False

    try:
        with transaction.atomic():
            template = Template.objects.select_for_update().get(pk=seed.template_id)
            run = HarnessRun.objects.select_for_update().get(pk=seed.run_id)
            revision = WorkflowPlanRevision.objects.select_for_update().get(pk=seed.revision_id, run=run)
            session = DebugSession._base_manager.select_for_update().get(pk=seed.pk, run=run, revision=revision)
            session.run = run
            session.revision = revision
            if not _session_matches_context(context, session):
                raise DebugStartRejected("CAPABILITY_FORBIDDEN", "session_id", category="PERMISSION", repairable=False)
            artifact = _validate_session_artifact_identity(
                session,
                template_id=template.id,
                lock_revisions=True,
            )

            def dispatch():
                nonlocal adapter_entered
                if session.run.status != HarnessRunStatus.DEBUGGING:
                    raise DebugStartRejected("DEBUG_SESSION", "run_id", repairable=False)
                if session.status not in DebugSession.ACTIVE_STATUSES or session.expires_at <= timezone.now():
                    raise DebugStartRejected("DEBUG_SESSION", "session_id", repairable=False)
                if session.status == DebugSessionStatus.RUNNING:
                    raise DebugStartRejected(
                        "DEBUG_CONFLICT", "session_id", category="DEBUG_CONFLICT", repairable=False
                    )
                if session.mode != request.mode:
                    raise DebugStartRejected("DEBUG_SESSION", "mode", repairable=False)
                if (
                    request.expected_plan_hash != session.plan_hash
                    or recompute_p0_plan_hash(session.revision) != session.plan_hash
                ):
                    raise DebugStartRejected("VALIDATION_STALE", "expected_plan_hash")
                _validate_template(context, template)
                snapshot = TemplateSnapshot.objects.select_for_update().get(
                    pk=template.snapshot_id,
                    template_id=template.id,
                    draft=True,
                    is_deleted=False,
                )
                pipeline_tree = snapshot.data
                if (
                    artifact.get("pipeline_tree_hash") != sha256_json(pipeline_tree)
                    or compute_tree_fingerprint(pipeline_tree) != session.tree_fingerprint
                ):
                    raise DebugStartRejected("VALIDATION_STALE", "tree_fingerprint")
                _reresolve_bindings(session.revision, resolver)

                token_handle = None
                approval_decision = None
                if request.execution_mode == DebugExecutionMode.REAL:
                    approval_decision, token_handle = _authorize_real_step(
                        context,
                        session,
                        request,
                        approval_verifier=approval_verifier,
                        token_broker=token_broker,
                        allow_real=allow_real,
                    )
                adapter = adapter_class(
                    template_id=template.id,
                    space_id=context.space_id,
                    pipeline_tree=pipeline_tree,
                )
                adapter_entered = True
                try:
                    if request.mode == DebugMode.GLOBAL:
                        raw_result = adapter.run_global(request, operator=context.actor)
                    else:
                        raw_result = adapter.run_step(request, operator=context.actor, token_handle=token_handle)
                    result = _safe_result_projection(raw_result)
                except DebugConflictError:
                    response = _error_envelope(
                        context, session, "DEBUG_CONFLICT", category="DEBUG_CONFLICT", repairable=False
                    )
                    return IdempotencyOutcome(
                        response_snapshot=response, run=session.run, resource_reference=str(session.id)
                    )
                except DebugStateError as error:
                    detail = error.args[0] if error.args else None
                    if not (isinstance(detail, dict) and detail.get("missing_vars")):
                        raise
                    response = _error_envelope(context, session, "DEBUG_DEPENDENCY", repairable=True)
                    return IdempotencyOutcome(
                        response_snapshot=response, run=session.run, resource_reference=str(session.id)
                    )

                _evidence(session, "DEBUG_RUN_STARTED", request, approval_decision=approval_decision)
                if result.get("status") == "running":
                    session.status = DebugSessionStatus.RUNNING
                    session.current_task_id = result.get("task_id")
                    session.last_heartbeat_at = timezone.now()
                    session.save(update_fields=["status", "current_task_id", "last_heartbeat_at"])
                else:
                    event_type = "DEBUG_RUN_FAILED" if result.get("status") == "failed" else "DEBUG_RUN_COMPLETED"
                    if result.get("status") == "failed":
                        _fail_session(context, session, token_broker=token_broker)
                    _evidence(session, event_type, request, result=result)
                response = _success_envelope(context, session, request, result)
                return IdempotencyOutcome(
                    response_snapshot=response,
                    run=session.run,
                    resource_reference=str(session.id),
                )

            outcome = dispatch()
            record = complete_idempotency(
                acquisition.record,
                outcome.response_snapshot,
                run=outcome.run,
                resource_reference=outcome.resource_reference,
            )
            return record.response_snapshot
    except Exception:
        if not adapter_entered:
            fail_idempotency(acquisition.record)
        raise
