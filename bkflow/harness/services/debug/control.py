"""Revision-bound, idempotent Harness debug controls."""

from django.db import transaction
from django.utils import timezone

from bkflow.harness.constants import (
    DebugControlAction,
    DebugSessionStatus,
    HarnessRunStatus,
)
from bkflow.harness.models import DebugSession, HarnessRun, WorkflowPlanRevision
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.debug.adapter import (
    DebugAdapter,
    DebugContextOwnershipConflict,
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

TOOL_NAME = "control_debug_session"


def _session_matches_context(context, session):
    snapshot = session.trusted_context_snapshot
    return (
        context_matches_run(context, session.run)
        and isinstance(snapshot, dict)
        and all(
            snapshot.get(field) == getattr(context, field)
            for field in (
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
        )
    )


def _error_envelope(context, session, code, *, category=None, repairable=True):
    validator = WorkflowValidator(context, resolver=object())
    rejection = DebugStartRejected(code, "debug", category=category, repairable=repairable)
    response = validator._envelope(
        ok=False,
        run=session.run,
        revision=session.revision,
        plan_hash_value=session.plan_hash,
        status=session.run.status,
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
    response["summary"] = "Debug control requires attention."
    return response


def _success_envelope(context, session, request, result, reset_impact):
    validator = WorkflowValidator(context, resolver=object())
    response = validator._envelope(
        ok=True,
        run=session.run,
        revision=session.revision,
        plan_hash_value=session.plan_hash,
        status=session.run.status,
        artifact_refs=[
            {
                "type": "debug_control",
                "session_id": str(session.id),
                "action": request.action,
                "session_status": session.status,
                "run_status": session.run.status,
                "result": project_evidence_payload(result),
                "reset_impact": project_evidence_payload(reset_impact),
            }
        ],
    )
    response["summary"] = "Debug control accepted."
    response["next_actions"] = (
        ["run_debug", "control_debug_session", "get_debug_session"]
        if session.status == DebugSessionStatus.ACTIVE
        else ["get_debug_session"]
    )
    return response


def _evidence(session, event_type, request, *, result=None):
    payload = {
        "session_id": str(session.id),
        "action": request.action,
        "node_id": request.node_id,
        "node_ids_fingerprint": sha256_json(request.node_ids or []),
    }
    if result is not None:
        projection = project_evidence_payload(result)
        omission_reason = evidence_projection_omission_reason(projection)
        if omission_reason is None:
            payload["result_fingerprint"] = sha256_json(projection)
        else:
            payload["result_omitted"] = True
            payload["result_omission_reason"] = omission_reason
        payload["session_status"] = session.status
        payload["run_status"] = session.run.status
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


def _failed_evidence(session, request, code):
    """Close a requested audit pair without copying downstream error details."""
    record_evidence(
        run=session.run,
        revision=session.revision,
        debug_session=session,
        event_type="DEBUG_CONTROL_FAILED",
        action=TOOL_NAME,
        payload={
            "session_id": str(session.id),
            "action": request.action,
            "code": code,
            "session_status": session.status,
            "run_status": session.run.status,
            "leases_revoked": not session.token_leases.filter(status="ACTIVE").exists(),
        },
        actor=session.actor,
        correlation_id=session.trusted_context_snapshot["correlation_id"],
    )


def _close_session(context, session, *, token_broker, reason, leases_revoked=False):
    """Revoke every lease before releasing the terminal session/run keys."""
    if not leases_revoked:
        token_broker.revoke_active_leases(context, session)
    session.status = DebugSessionStatus.TERMINATED
    session.current_task_id = None
    session.terminal_reason = reason
    session.save(update_fields=["status", "current_task_id", "terminal_reason"])
    if session.run.status == HarnessRunStatus.DEBUGGING:
        transition_run(session.run, HarnessRunStatus.DRAFT_READY)
        session.run.refresh_from_db(fields=["status"])


def _dispatch_control(context, session, request, adapter, *, token_broker):
    reset_impact = {"reset_node_ids": [], "reasons": {}}
    if request.action == DebugControlAction.RESET:
        reset_node_ids, reset_impact = adapter.reset(session.debug_context_id, node_ids=request.node_ids)
        return {"reset_node_ids": reset_node_ids}, reset_impact
    if request.action == DebugControlAction.SET_NODE_MOCK:
        result = adapter.set_node_mock(
            session.debug_context_id,
            node_id=request.node_id,
            enabled=request.enabled,
            mock_result=request.mock_result,
            mock_outputs=request.mock_outputs,
            mock_error=request.mock_error,
        )
        return result, reset_impact
    if request.action == DebugControlAction.SET_CONTEXT_VAR:
        return (
            adapter.set_context_var(
                session.debug_context_id,
                key=request.key,
                value=request.value,
            ),
            reset_impact,
        )
    if session.status == DebugSessionStatus.ACTIVE:
        if request.node_id is not None:
            raise DebugStateError("there is no active node to terminate")
        _close_session(context, session, token_broker=token_broker, reason="debug_terminated")
        return {"status": "terminated"}, reset_impact
    # Remove debug authority as soon as a termination control is accepted.
    # This remains committed even when the Engine rejects the operation, while
    # Session/Run ownership stays RUNNING for safe recovery and inspection.
    token_broker.revoke_active_leases(context, session)
    result = adapter.terminate(
        session.debug_context_id,
        current_task_id=session.current_task_id,
        node_id=request.node_id,
        operator=context.actor,
    )
    if request.node_id is not None and result.get("status") == "idle":
        session.status = DebugSessionStatus.ACTIVE
        session.current_task_id = None
        session.save(update_fields=["status", "current_task_id"])
    elif request.node_id is None and result.get("status") == "idle":
        _close_session(
            context,
            session,
            token_broker=token_broker,
            reason="debug_terminated",
            leases_revoked=True,
        )
    return result, reset_impact


def control_debug_session(context, request, *, resolver, adapter_class=DebugAdapter, token_broker=None):
    """Revalidate and apply one control behind a persistent session barrier."""
    token_broker = token_broker or TokenBroker()
    seed = DebugSession._base_manager.select_related("run", "revision").get(pk=request.session_id)
    if not _session_matches_context(context, seed):
        raise DebugStartRejected("CAPABILITY_FORBIDDEN", "session_id", category="PERMISSION", repairable=False)
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
            session = (
                DebugSession._base_manager.select_for_update()
                .select_related("run", "revision")
                .get(pk=seed.pk, run=run, revision=revision)
            )
            if not _session_matches_context(context, session):
                raise DebugStartRejected("CAPABILITY_FORBIDDEN", "session_id", category="PERMISSION", repairable=False)
            artifact = _validate_session_artifact_identity(
                session,
                template_id=template.id,
                lock_revisions=True,
            )
            if session.status not in DebugSession.ACTIVE_STATUSES or session.expires_at <= timezone.now():
                raise DebugStartRejected("DEBUG_SESSION", "session_id", repairable=False)
            if session.run.status != HarnessRunStatus.DEBUGGING:
                raise DebugStartRejected("DEBUG_SESSION", "run_id", repairable=False)
            if request.expected_plan_hash != session.plan_hash or recompute_p0_plan_hash(revision) != session.plan_hash:
                raise DebugStartRejected("VALIDATION_STALE", "expected_plan_hash")
            if session.status == DebugSessionStatus.RUNNING and request.action != DebugControlAction.TERMINATE:
                raise DebugStartRejected("DEBUG_CONFLICT", "session_id", category="DEBUG_CONFLICT", repairable=False)
            _validate_template(context, template)
            snapshot = TemplateSnapshot.objects.select_for_update().get(
                pk=template.snapshot_id,
                template_id=template.id,
                draft=True,
                is_deleted=False,
            )
            if (
                artifact.get("revision_id") != str(revision.id)
                or artifact.get("pipeline_tree_hash") != sha256_json(snapshot.data)
                or compute_tree_fingerprint(snapshot.data) != session.tree_fingerprint
            ):
                raise DebugStartRejected("VALIDATION_STALE", "tree_fingerprint")
            _reresolve_bindings(revision, resolver)
            adapter = adapter_class(
                template_id=template.id,
                space_id=context.space_id,
                pipeline_tree=snapshot.data,
            )
            try:
                adapter.require_context_ownership(
                    session.debug_context_id,
                    current_task_id=session.current_task_id,
                )
            except DebugContextOwnershipConflict:
                raise DebugStartRejected(
                    "DEBUG_EXECUTION_FAILED",
                    "session_id",
                    repairable=False,
                ) from None
            _evidence(session, "DEBUG_CONTROL_REQUESTED", request)
            adapter_entered = True
            try:
                result, reset_impact = _dispatch_control(
                    context,
                    session,
                    request,
                    adapter,
                    token_broker=token_broker,
                )
            except DebugConflictError:
                _failed_evidence(session, request, "DEBUG_CONFLICT")
                outcome = IdempotencyOutcome(
                    response_snapshot=_error_envelope(
                        context,
                        session,
                        "DEBUG_CONFLICT",
                        category="DEBUG_CONFLICT",
                        repairable=False,
                    ),
                    run=session.run,
                    resource_reference=str(session.id),
                )
            except DebugStateError:
                _failed_evidence(session, request, "DEBUG_EXECUTION_FAILED")
                outcome = IdempotencyOutcome(
                    response_snapshot=_error_envelope(
                        context,
                        session,
                        "DEBUG_EXECUTION_FAILED",
                        repairable=False,
                    ),
                    run=session.run,
                    resource_reference=str(session.id),
                )
            else:
                _evidence(session, "DEBUG_CONTROL_COMPLETED", request, result=result)
                outcome = IdempotencyOutcome(
                    response_snapshot=_success_envelope(
                        context,
                        session,
                        request,
                        result,
                        reset_impact,
                    ),
                    run=session.run,
                    resource_reference=str(session.id),
                )
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
