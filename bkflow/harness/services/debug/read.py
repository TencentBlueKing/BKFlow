"""Owned, bounded projection and convergence for Harness debug sessions."""

import base64
import datetime
import json
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from bkflow.harness.constants import DebugSessionStatus, HarnessRunStatus
from bkflow.harness.models import (
    DebugSession,
    EvidenceEvent,
    HarnessRun,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.debug.adapter import (
    DebugAdapter,
    DebugContextOwnershipConflict,
)
from bkflow.harness.services.debug.policy import DebugStartRejected, context_matches_run
from bkflow.harness.services.debug.projection import (
    META_EVENT,
    NODES_EVENT,
    build_context_snapshot,
    context_page,
    enrich_context_view,
    load_context_snapshot,
    persist_context_snapshot,
    project_debug_payload,
)
from bkflow.harness.services.debug.session import (
    _reresolve_bindings,
    _validate_session_artifact_identity,
    _validate_template,
)
from bkflow.harness.services.evidence import (
    is_safe_evidence_ref,
    prepare_evidence_artifact_payload,
    record_evidence,
)
from bkflow.harness.services.state import transition_run
from bkflow.harness.services.token_broker import TokenBroker
from bkflow.harness.services.validator import (
    WorkflowValidationFailure,
    WorkflowValidator,
    recompute_p0_plan_hash,
)
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.debug.service import DebugConflictError, DebugStateError
from bkflow.template.models import Template, TemplateSnapshot

TOOL_NAME = "get_debug_session"
MAX_HISTORY_UTF8_BYTES = 32 * 1024


def _cursor(event):
    value = json.dumps(
        [event.occurred_at.isoformat(), str(event.id)],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_cursor(value):
    if value is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        occurred_at_value, event_id_value = json.loads(raw.decode("utf-8"))
        occurred_at = datetime.datetime.fromisoformat(occurred_at_value)
        event_id = uuid.UUID(event_id_value)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "cursor") from None
    if timezone.is_naive(occurred_at):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "cursor")
    return occurred_at, event_id


def _history(session, request):
    query = (
        EvidenceEvent.objects.filter(debug_session=session)
        .exclude(event_type__in=(META_EVENT, NODES_EVENT))
        .order_by("occurred_at", "id")
    )
    decoded = _decode_cursor(request.cursor)
    if decoded is not None:
        occurred_at, event_id = decoded
        query = query.filter(Q(occurred_at__gt=occurred_at) | Q(occurred_at=occurred_at, id__gt=event_id))
    events = list(query[: request.limit + 1])
    page = []
    items = []
    total_bytes = 0
    for event in events[: request.limit]:
        item = {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "action": event.action,
            "occurred_at": event.occurred_at.isoformat(),
            "payload": event.redacted_payload,
            "artifact_refs": event.artifact_refs,
        }
        item_bytes = len(json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if items and total_bytes + item_bytes > MAX_HISTORY_UTF8_BYTES:
            break
        page.append(event)
        items.append(item)
        total_bytes += item_bytes
    has_more = len(page) < len(events)
    return {
        "items": items,
        "next_cursor": _cursor(page[-1]) if has_more and page else None,
    }


def _project(value, artifact_writer):
    # Reserve artifact_refs -> artifact -> field nesting. A legacy context that
    # cannot survive the final APIGW guard must not mask the safe node page.
    projection = project_debug_payload([{"context": value}])
    if isinstance(projection, list):
        projection = projection[0]["context"]
    if not (isinstance(projection, dict) and projection.get("omitted") is True):
        return projection
    if projection.get("reason") == "reserved_metadata":
        return projection
    if artifact_writer is None:
        return projection
    artifact_payload = prepare_evidence_artifact_payload(value)
    if artifact_payload is None:
        return projection
    try:
        artifact_ref = artifact_writer(artifact_payload)
    except Exception:
        raise ValidationError("Debug status artifact storage failed") from None
    if not is_safe_evidence_ref(artifact_ref):
        raise ValidationError("Debug status artifact reference is invalid")
    return {"externalized": True, "artifact_ref": artifact_ref}


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


def _terminalize(context, session, status, reason, *, token_broker, leases_revoked=False):
    """Revoke authority before releasing the session and run lifecycle locks."""
    if not leases_revoked:
        token_broker.revoke_active_leases(context, session)
    session.status = status
    session.current_task_id = None
    session.terminal_reason = reason
    session.save(update_fields=["status", "current_task_id", "terminal_reason"])
    target = HarnessRunStatus.RELEASE_READY if status == DebugSessionStatus.COMPLETED else HarnessRunStatus.DRAFT_READY
    if session.run.status == HarnessRunStatus.DEBUGGING:
        transition_run(session.run, target)
        session.run.refresh_from_db(fields=["status"])
    record_evidence(
        run=session.run,
        revision=session.revision,
        debug_session=session,
        event_type="DEBUG_SESSION_{}".format(status),
        action=TOOL_NAME,
        payload={"session_id": str(session.id), "status": status, "reason": reason},
        actor=session.actor,
        correlation_id=session.trusted_context_snapshot["correlation_id"],
    )


def _complete_step(session, view):
    """Release only the current task while keeping the step session active."""
    completed_task_id = session.current_task_id
    session.status = DebugSessionStatus.ACTIVE
    session.current_task_id = None
    session.last_heartbeat_at = timezone.now()
    session.save(update_fields=["status", "current_task_id", "last_heartbeat_at"])
    record_evidence(
        run=session.run,
        revision=session.revision,
        debug_session=session,
        event_type="DEBUG_RUN_COMPLETED",
        action=TOOL_NAME,
        payload={
            "session_id": str(session.id),
            "mode": session.mode,
            "task_id": completed_task_id,
            "status": view.get("last_run_status"),
        },
        actor=session.actor,
        correlation_id=session.trusted_context_snapshot["correlation_id"],
    )


def _handle_expiry(context, seed, *, adapter_class, token_broker, now):
    """Commit deauthorization before mutable draft, provider, or Engine checks."""
    with transaction.atomic():
        session = DebugSession._base_manager.select_for_update().select_related("run", "revision").get(pk=seed.pk)
        if not _session_matches_context(context, session):
            raise DebugStartRejected(
                "CAPABILITY_FORBIDDEN",
                "session_id",
                category="PERMISSION",
                repairable=False,
            )
        if session.status not in DebugSession.ACTIVE_STATUSES or session.expires_at > now:
            return False, None
        token_broker.revoke_active_leases(context, session)
        if session.status == DebugSessionStatus.ACTIVE:
            _terminalize(
                context,
                session,
                DebugSessionStatus.EXPIRED,
                "session_expired",
                token_broker=token_broker,
                leases_revoked=True,
            )
            return True, None
        current_task_id = session.current_task_id
        debug_context_id = session.debug_context_id
        template_id = session.template_id

    if current_task_id is None:
        raise DebugStartRejected("DEBUG_EXECUTION_FAILED", "session_id", repairable=False)
    try:
        with transaction.atomic():
            session = DebugSession._base_manager.select_for_update().select_related("run", "revision").get(pk=seed.pk)
            if not _session_matches_context(context, session):
                raise DebugStartRejected(
                    "CAPABILITY_FORBIDDEN",
                    "session_id",
                    category="PERMISSION",
                    repairable=False,
                )
            if session.status != DebugSessionStatus.RUNNING or session.current_task_id != current_task_id:
                raise DebugStartRejected("DEBUG_EXECUTION_FAILED", "session_id", repairable=False)
            adapter = adapter_class(template_id=template_id, space_id=context.space_id, pipeline_tree={})
            termination = adapter.terminate(
                debug_context_id,
                current_task_id=current_task_id,
                node_id=None,
                operator=context.actor,
            )
            if termination.get("status") not in {"idle", "terminating"}:
                raise DebugStartRejected("DEBUG_EXECUTION_FAILED", "session_id", repairable=False)
            if termination.get("status") == "idle":
                _terminalize(
                    context,
                    session,
                    DebugSessionStatus.EXPIRED,
                    "session_expired",
                    token_broker=token_broker,
                    leases_revoked=True,
                )
    except (DebugConflictError, DebugStateError, DebugContextOwnershipConflict):
        raise DebugStartRejected("DEBUG_EXECUTION_FAILED", "session_id", repairable=False) from None
    if termination.get("status") == "idle":
        return True, None
    return True, {
        "available": False,
        "reason": "expiry_termination_pending",
        "termination_status": "terminating",
    }


def _converge(context, session, adapter, *, token_broker):
    if session.status != DebugSessionStatus.RUNNING:
        return None
    if session.current_task_id is None:
        raise DebugStartRejected("DEBUG_EXECUTION_FAILED", "session_id", repairable=False)
    try:
        view = adapter.context_view(session.debug_context_id, current_task_id=session.current_task_id)
    except DebugContextOwnershipConflict:
        raise DebugStartRejected("DEBUG_EXECUTION_FAILED", "session_id", repairable=False) from None
    if view.get("active_task_id") is not None or view.get("last_task_id") != session.current_task_id:
        return view
    run_status = view.get("last_run_status")
    if run_status not in {"finished", "failed", "revoked"}:
        return view
    if view.get("last_run_type") != session.mode:
        raise DebugStartRejected("DEBUG_EXECUTION_FAILED", "session_id", repairable=False)
    if run_status == "finished" and session.mode == "step":
        _complete_step(session, view)
        return view
    if run_status == "finished":
        terminal_status, reason = DebugSessionStatus.COMPLETED, "debug_completed"
    elif run_status == "failed":
        terminal_status, reason = DebugSessionStatus.FAILED, "debug_failed"
    else:
        terminal_status, reason = DebugSessionStatus.TERMINATED, "debug_terminated"
    view = enrich_context_view(session, view)
    persist_context_snapshot(session, view)
    _terminalize(context, session, terminal_status, reason, token_broker=token_broker)
    return view


def _artifact(session, context_view, history, reset_impact, *, artifact_writer, node_page, read_guidance):
    artifact = {
        "type": "debug_session_status",
        "session": {
            "session_id": str(session.id),
            "template_id": session.template_id,
            "mode": session.mode,
            "status": session.status,
            "current_task_id": session.current_task_id,
            "expires_at": session.expires_at.isoformat(),
            "terminal_reason": session.terminal_reason,
        },
        "context": _project(context_view, artifact_writer),
        "history": history,
        "reset_impact": _project(reset_impact, artifact_writer),
        "read_guidance": read_guidance,
    }
    if node_page is not None:
        artifact["context_page"] = node_page
    return artifact


def _next_actions(session, *, runtime_enabled, read_guidance):
    further_pages = read_guidance["node_page_has_more"] or read_guidance["history_has_more"]
    if not runtime_enabled:
        return ["get_debug_session"] if further_pages else []
    if session.status == DebugSessionStatus.ACTIVE:
        return ["run_debug", "control_debug_session", "get_debug_session"]
    if session.status == DebugSessionStatus.RUNNING:
        return ["control_debug_session", "get_debug_session"]
    return ["get_debug_session"] if further_pages else []


def _response(
    context,
    session,
    request,
    *,
    context_view,
    reset_impact,
    artifact_writer,
    runtime_enabled,
):
    history = _history(session, request)
    context_view = enrich_context_view(session, context_view)
    snapshot = build_context_snapshot(context_view)
    if snapshot is None and session.status in DebugSession.TERMINAL_STATUSES:
        snapshot = load_context_snapshot(session)
    validator = WorkflowValidator(context, resolver=object())
    try:
        node_page = context_page(session.id, snapshot, request)
    except DebugStartRejected as error:
        # A stale browsing cursor is not a reason to roll back an observed
        # terminal task, its immutable snapshot, or credential revocation.
        return validator._envelope(
            ok=False,
            run=session.run,
            revision=session.revision,
            plan_hash_value=session.plan_hash,
            status=session.run.status,
            errors=[WorkflowValidationFailure(error.code, path=error.path).as_error()],
        )
    # 这里只描述本次返回及当前位置，不声称调用者读过前页或业务验收通过。
    read_guidance = {
        "context_source": "context_page" if node_page is not None else "unavailable",
        "poll_required": runtime_enabled and session.status == DebugSessionStatus.RUNNING,
        "node_query": "single_node" if request.node_id else "all_nodes",
        "node_page_has_more": node_page is not None and node_page["next_cursor"] is not None,
        "history_has_more": history["next_cursor"] is not None,
    }
    response = validator._envelope(
        ok=True,
        run=session.run,
        revision=session.revision,
        plan_hash_value=session.plan_hash,
        status=session.run.status,
        artifact_refs=[
            _artifact(
                session,
                context_view,
                history,
                reset_impact,
                artifact_writer=artifact_writer,
                node_page=node_page,
                read_guidance=read_guidance,
            )
        ],
    )
    response["summary"] = "Debug session status is available."
    response["next_actions"] = _next_actions(session, runtime_enabled=runtime_enabled, read_guidance=read_guidance)
    return response


def get_debug_session(
    context,
    request,
    *,
    resolver,
    adapter_class=DebugAdapter,
    token_broker=None,
    artifact_writer=None,
    runtime_enabled=True,
):
    """Read owned session Evidence and converge only its exact Engine task."""
    _decode_cursor(request.cursor)
    seed = DebugSession._base_manager.select_related("run", "revision").get(pk=request.session_id)
    if not _session_matches_context(context, seed):
        raise DebugStartRejected("CAPABILITY_FORBIDDEN", "session_id", category="PERMISSION", repairable=False)
    empty_impact = {"reset_node_ids": [], "reasons": {}}
    if not runtime_enabled:
        return _response(
            context,
            seed,
            request,
            context_view={"available": False, "reason": "debug_disabled"},
            reset_impact=empty_impact,
            artifact_writer=None,
            runtime_enabled=False,
        )
    if seed.status not in DebugSession.ACTIVE_STATUSES:
        return _response(
            context,
            seed,
            request,
            context_view={"available": False, "reason": "session_terminal"},
            reset_impact=empty_impact,
            artifact_writer=None,
            runtime_enabled=True,
        )

    token_broker = token_broker or TokenBroker()
    expiry_handled, expiry_context = _handle_expiry(
        context,
        seed,
        adapter_class=adapter_class,
        token_broker=token_broker,
        now=timezone.now(),
    )
    if expiry_handled:
        session = DebugSession._base_manager.select_related("run", "revision").get(pk=seed.pk)
        if expiry_context is None:
            expiry_context = (
                {"available": False, "reason": "session_terminal"}
                if session.status in DebugSession.TERMINAL_STATUSES
                else {
                    "available": False,
                    "reason": "expiry_termination_pending",
                    "termination_status": "unknown",
                }
            )
        return _response(
            context,
            session,
            request,
            context_view=expiry_context,
            reset_impact=empty_impact,
            artifact_writer=None,
            runtime_enabled=True,
        )

    _validate_session_artifact_identity(seed)
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
        context_view = {"available": False, "reason": "session_terminal"}
        reset_impact = empty_impact
        if session.status in DebugSession.ACTIVE_STATUSES:
            _validate_template(context, template)
            if recompute_p0_plan_hash(revision) != session.plan_hash:
                raise DebugStartRejected("VALIDATION_STALE", "plan_hash")
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
            context_view = _converge(context, session, adapter, token_broker=token_broker)
            if context_view is None and session.status in DebugSession.ACTIVE_STATUSES:
                context_view = adapter.context_view(
                    session.debug_context_id,
                    current_task_id=session.current_task_id,
                )
            reset_impact = adapter.reset_impact()
        return _response(
            context,
            session,
            request,
            context_view=context_view,
            reset_impact=reset_impact,
            artifact_writer=artifact_writer,
            runtime_enabled=True,
        )
