"""Owned, bounded readback and convergence for Harness executions."""

import base64
import datetime
import json
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from bkflow.harness.constants import HarnessAction, HarnessRunStatus
from bkflow.harness.contracts import HarnessContextError
from bkflow.harness.models import (
    EvidenceBundle,
    EvidenceEvent,
    ExecutionRun,
    HarnessIdempotencyRecord,
    HarnessRun,
    ReleaseManifest,
    ReleasePublication,
    WorkflowPlanRevision,
)
from bkflow.harness.safety import safe_opaque_identifier
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.contract_versions import (
    is_harness_execution_enabled,
    require_tool_enabled,
)
from bkflow.harness.services.debug.policy import context_matches_run
from bkflow.harness.services.evidence import (
    MAX_EVIDENCE_ITEMS,
    finalize_evidence_bundle,
    record_evidence,
)
from bkflow.harness.services.execution.adapter import (
    ControlReadbackObservation,
    ExecutionReadAdapter,
    ReadbackUnavailable,
    TaskNotFound,
)
from bkflow.harness.services.execution.contracts import (
    StartExecutionRejected,
    validate_get_execution_request,
)
from bkflow.harness.services.execution.postconditions import (
    PostconditionEvaluator,
    PostconditionSpecError,
)
from bkflow.harness.services.idempotency import complete_idempotency
from bkflow.harness.services.token_broker import TokenBroker
from bkflow.harness.services.validator import (
    WorkflowValidationFailure,
    WorkflowValidator,
)
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.models import Template, TemplateSnapshot

TOOL_NAME = HarnessAction.GET_WORKFLOW_EXECUTION
POSTCONDITION_EVIDENCE_WAIT = datetime.timedelta(minutes=5)
MAX_HISTORY_UTF8_BYTES = 32 * 1024
CONTROL_TOOL_NAME = "control_workflow_execution"
_CONTROL_STATES = frozenset(
    {
        ExecutionRun.Status.CONTROL_DISPATCHING,
        ExecutionRun.Status.CONTROL_UNCERTAIN,
    }
)
_CONTROL_ACTIONS = frozenset({"pause", "resume", "revoke", "retry", "skip", "forced_fail"})
_NODE_CONTROL_ACTIONS = frozenset({"retry", "skip", "forced_fail"})
_WIRE_CONTROL_STATES = frozenset(
    {"CREATED", "READY", "RUNNING", "SUSPENDED", "NODE_SUSPENDED", "FINISHED", "FAILED", "REVOKED", "EXPIRED"}
)
_NODE_RETRY_STATES = frozenset({"READY", "RUNNING", "SUSPENDED", "FINISHED", "FAILED", "REVOKED"})
_IDEMPOTENCY_REF = re.compile(r"^idempotency://execution/([1-9][0-9]{0,18})$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CONTROL_JOURNAL_KEYS = frozenset(
    {
        "version",
        "action",
        "attempt",
        "idempotency_ref",
        "action_digest",
        "pre_execution_status",
        "pre_state",
        "template_target",
        "expected_readback",
        "input_fields",
        "input_digest",
    }
)
_CONTROL_PRE_STATE_KEYS = frozenset(
    {
        "root_state",
        "template_node_id",
        "node_state",
        "node_version",
        "runtime_mapping_fingerprint",
    }
)
_EXPECTED_CONTROL_READBACK = {
    "pause": "SUSPENDED",
    "resume": "RUNNING",
    "revoke": "REVOKED",
    "retry": "NODE_VERSION_ADVANCED",
    "skip": "NODE_VERSION_ADVANCED",
    "forced_fail": "NODE_FAILED",
}


@dataclass(frozen=True)
class _ControlAttempt:
    """Strict safe projection of one append-only control dispatch journal."""

    record_id: int
    event_id: uuid.UUID
    idempotency_ref: str
    action: str
    attempt: int
    action_digest: str
    pre_execution_status: str
    pre_root_state: str
    template_node_id: str = None
    pre_node_state: str = None
    pre_node_version: str = None
    runtime_mapping_fingerprint: str = None
    expected_readback: str = None
    input_fields: tuple = ()
    input_digest: str = None
    journal_fingerprint: str = None


class _ControlBarrierChanged(RuntimeError):
    """Abort an ordinary GET write after a concurrent control barrier wins."""


def _is_sha256(value):
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


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
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "cursor") from None
    if timezone.is_naive(occurred_at):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "cursor")
    return occurred_at, event_id


def _history(execution, request):
    query = EvidenceEvent.objects.filter(execution=execution).order_by("occurred_at", "id")
    decoded = _decode_cursor(request.cursor)
    if decoded is not None:
        occurred_at, event_id = decoded
        query = query.filter(Q(occurred_at__gt=occurred_at) | Q(occurred_at=occurred_at, id__gt=event_id))
    events = list(query[: request.limit + 1])
    projected = []
    selected = []
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
        size = len(json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if projected and total_bytes + size > MAX_HISTORY_UTF8_BYTES:
            break
        projected.append(item)
        selected.append(event)
        total_bytes += size
    has_more = len(selected) < len(events)
    return {
        "items": projected,
        "next_cursor": _cursor(selected[-1]) if has_more and selected else None,
    }


def _bundle_projection(execution):
    bundle = EvidenceBundle.objects.filter(execution=execution).first()
    if bundle is None:
        return None
    return {
        "bundle_id": str(bundle.id),
        "bundle_hash": bundle.bundle_hash,
        "outcome": bundle.outcome,
        "artifact_refs": list(bundle.artifact_refs),
        "finalized_at": bundle.finalized_at.isoformat(),
    }


def _execution_projection(execution):
    return {
        "execution_id": str(execution.id),
        "manifest_id": str(execution.manifest_id),
        "task_ref": execution.task_ref,
        "status": execution.status,
        "last_engine_state": execution.last_engine_state,
        "postcondition_status": execution.postcondition_status,
        "postcondition_report": deepcopy(execution.postcondition_report),
        "heartbeat_at": execution.heartbeat_at.isoformat() if execution.heartbeat_at else None,
        "terminal_at": execution.terminal_at.isoformat() if execution.terminal_at else None,
    }


def _terminal_error(execution):
    if execution.status != ExecutionRun.Status.FAILED:
        return None
    if execution.last_engine_state == "FINISHED" and execution.postcondition_status in {
        ExecutionRun.PostconditionStatus.FAILED,
        ExecutionRun.PostconditionStatus.UNAVAILABLE,
    }:
        return WorkflowValidationFailure(
            "POSTCONDITION_FAILED",
            path="postconditions",
            category="POSTCONDITION",
            repairable=False,
        ).as_error()
    return WorkflowValidationFailure(
        "EXECUTION_FAILED",
        path="execution",
        category="EXECUTION",
        repairable=False,
    ).as_error()


def _response(context, execution, request, *, refresh):
    error = _terminal_error(execution)
    response = WorkflowValidator(context, resolver=object())._envelope(
        ok=error is None,
        run=execution.run,
        revision=execution.revision,
        plan_hash_value=execution.revision.plan_hash,
        status=execution.run.status,
        errors=[error] if error else [],
        artifact_refs=[
            {
                "type": "workflow_execution_status",
                "execution": _execution_projection(execution),
                "refresh": refresh,
                "history": _history(execution, request),
                "evidence_bundle": _bundle_projection(execution),
            }
        ],
    )
    response["summary"] = "Workflow execution status is available."
    response["next_actions"] = [TOOL_NAME]
    return response


def _failure(context, rejection):
    validator = WorkflowValidator(context, resolver=object())
    return validator._input_failure(
        {},
        rejection.code,
        path=rejection.path,
        category=rejection.category,
        repairable=rejection.repairable,
        retryable=rejection.retryable,
    )


def _matches_authority(context, execution):
    run = execution.run
    manifest = execution.manifest
    try:
        publication = manifest.publication
    except ReleasePublication.DoesNotExist:
        return False
    return (
        context_matches_run(context, run)
        and execution.run_id == manifest.run_id
        and execution.revision_id == manifest.revision_id
        and execution.platform == run.platform
        and execution.platform_app == run.platform_app
        and execution.actor == run.actor
        and execution.space_id == run.space_id
        and execution.scope == run.scope
        and execution.target_environment == run.environment
        and execution.policy_version == run.policy_version
        and execution.published_template_id == publication.published_template_id
        and execution.published_snapshot_id == publication.published_snapshot_id
        and execution.published_version == publication.published_version
    )


def _load_owned_execution(context, execution_id):
    try:
        execution = ExecutionRun.objects.select_related("run", "revision", "manifest__publication").get(pk=execution_id)
    except ExecutionRun.DoesNotExist:
        raise StartExecutionRejected(
            "CAPABILITY_FORBIDDEN", "execution_id", category="PERMISSION", repairable=False
        ) from None
    if not _matches_authority(context, execution):
        raise StartExecutionRejected("CAPABILITY_FORBIDDEN", "execution_id", category="PERMISSION", repairable=False)
    return execution


def _control_record_matches(context, execution, record):
    return (
        record.tool_name == CONTROL_TOOL_NAME
        and record.run_id == execution.run_id
        and record.platform_app == context.platform_app
        and record.actor == context.actor
        and record.space_id == context.space_id
        and record.run_scope == "run:{}".format(execution.run.run_id)
        and record.resource_reference == str(execution.id)
        and record.status in {"IN_FLIGHT", "COMPLETED"}
        and _is_sha256(record.request_hash)
        and (record.status != "IN_FLIGHT" or not record.response_snapshot)
    )


def _parse_control_journal(execution, event, idempotency_ref, record_id, expected_attempt):
    payload = event.redacted_payload
    if (
        event.execution_id != execution.id
        or event.run_id != execution.run_id
        or event.revision_id != execution.revision_id
        or event.event_type != "EXECUTION_CONTROL_DISPATCHING"
        or event.actor != execution.actor
        or not isinstance(payload, dict)
        or set(payload) != _CONTROL_JOURNAL_KEYS
        or payload.get("version") != "control-attempt-v1"
        or payload.get("idempotency_ref") != idempotency_ref
    ):
        return None
    action = payload.get("action")
    attempt = payload.get("attempt")
    pre_status = payload.get("pre_execution_status")
    pre_state = payload.get("pre_state")
    target = payload.get("template_target")
    input_fields = payload.get("input_fields")
    if (
        not isinstance(action, str)
        or action not in _CONTROL_ACTIONS
        or event.action != action
        or isinstance(attempt, bool)
        or not isinstance(attempt, int)
        or attempt <= 0
        or attempt != expected_attempt
        or not _is_sha256(payload.get("action_digest"))
        or not _is_sha256(payload.get("input_digest"))
        or payload.get("expected_readback") != _EXPECTED_CONTROL_READBACK[action]
        or not isinstance(pre_state, dict)
        or set(pre_state) != _CONTROL_PRE_STATE_KEYS
        or not isinstance(pre_state.get("root_state"), str)
        or pre_state.get("root_state") not in _WIRE_CONTROL_STATES
        or not isinstance(target, dict)
        or not isinstance(input_fields, list)
        or any(not isinstance(value, str) for value in input_fields)
        or input_fields != sorted(input_fields)
        or len(input_fields) != len(set(input_fields))
        or any(safe_opaque_identifier(value) is None for value in input_fields)
        or len(input_fields) > 100
    ):
        return None
    allowed_pre_statuses = {
        "pause": {ExecutionRun.Status.EXECUTING},
        "resume": {ExecutionRun.Status.PAUSED},
        "revoke": {ExecutionRun.Status.EXECUTING, ExecutionRun.Status.PAUSED},
        "retry": {ExecutionRun.Status.EXECUTING},
        "skip": {ExecutionRun.Status.EXECUTING},
        "forced_fail": {ExecutionRun.Status.EXECUTING},
    }
    if not isinstance(pre_status, str) or pre_status not in allowed_pre_statuses[action]:
        return None
    template_node_id = pre_state.get("template_node_id")
    node_state = pre_state.get("node_state")
    node_version = pre_state.get("node_version")
    mapping_fingerprint = pre_state.get("runtime_mapping_fingerprint")
    allowed_task_pre_states = {
        "pause": {"RUNNING"},
        "resume": {"SUSPENDED"},
        "revoke": {"RUNNING", "SUSPENDED", "FAILED", "NODE_SUSPENDED"},
    }
    if action in _NODE_CONTROL_ACTIONS:
        if (
            set(target) != {"template_node_id"}
            or target.get("template_node_id") != template_node_id
            or safe_opaque_identifier(template_node_id) is None
            or not isinstance(node_state, str)
            or node_state not in _WIRE_CONTROL_STATES
            or safe_opaque_identifier(node_version) is None
            or not _is_sha256(mapping_fingerprint)
            or (action in {"retry", "skip"} and pre_state["root_state"] != "FAILED")
            or (action == "forced_fail" and pre_state["root_state"] != "RUNNING")
            or (action in {"retry", "skip"} and node_state != "FAILED")
            or (action == "forced_fail" and node_state != "RUNNING")
        ):
            return None
    elif (
        target
        or template_node_id is not None
        or node_state is not None
        or node_version is not None
        or mapping_fingerprint is not None
        or pre_state["root_state"] not in allowed_task_pre_states[action]
    ):
        return None
    if input_fields or payload["input_digest"] != sha256_json({}):
        # P3 deliberately denies caller-supplied retry inputs.  A later
        # contract must version this journal before accepting non-empty input.
        return None
    return _ControlAttempt(
        record_id=record_id,
        event_id=event.id,
        idempotency_ref=idempotency_ref,
        action=action,
        attempt=attempt,
        action_digest=payload["action_digest"],
        pre_execution_status=pre_status,
        pre_root_state=pre_state["root_state"],
        template_node_id=template_node_id,
        pre_node_state=node_state,
        pre_node_version=node_version,
        runtime_mapping_fingerprint=mapping_fingerprint,
        expected_readback=payload["expected_readback"],
        input_fields=tuple(input_fields),
        input_digest=payload["input_digest"],
        journal_fingerprint=sha256_json(
            {
                "event_id": str(event.id),
                "event_action": event.action,
                "payload": payload,
            }
        ),
    )


def _load_control_attempt(context, execution, *, locked_record=None, lock_event=False):
    refs = execution.control_idempotency_refs
    if not isinstance(refs, list) or not refs or len(refs) > MAX_EVIDENCE_ITEMS:
        return None, None
    matches = [_IDEMPOTENCY_REF.fullmatch(item) if isinstance(item, str) else None for item in refs]
    if any(match is None for match in matches):
        return None, None
    record_ids = [int(match.group(1)) for match in matches]
    if len(record_ids) != len(set(record_ids)):
        return None, None
    record_id = record_ids[-1]
    if locked_record is None:
        record = HarnessIdempotencyRecord.objects.filter(pk=record_id).first()
    else:
        record = locked_record
    if record is None or record.pk != record_id or not _control_record_matches(context, execution, record):
        return None, None
    records = HarnessIdempotencyRecord.objects.in_bulk(record_ids)
    records[record_id] = record
    if len(records) != len(record_ids) or any(
        not _control_record_matches(context, execution, records[item]) for item in record_ids
    ):
        return None, None
    if any(records[item].status != "COMPLETED" for item in record_ids[:-1]):
        return None, None
    events = EvidenceEvent.objects.filter(
        execution=execution,
        event_type="EXECUTION_CONTROL_DISPATCHING",
    ).order_by("occurred_at", "id")
    if lock_event:
        events = events.select_for_update()
    events = list(events[: MAX_EVIDENCE_ITEMS + 1])
    if len(events) != len(refs):
        return record, None
    attempts = [
        _parse_control_journal(execution, event, idempotency_ref, current_record_id, index)
        for index, (event, idempotency_ref, current_record_id) in enumerate(
            zip(events, refs, record_ids),
            start=1,
        )
    ]
    if any(attempt is None for attempt in attempts):
        return record, None
    return record, attempts[-1]


def _runtime_snapshot(context, execution):
    try:
        template = Template.objects.get(pk=execution.published_template_id, is_deleted=False)
        snapshot = TemplateSnapshot.objects.get(
            pk=execution.published_snapshot_id,
            template_id=template.id,
            draft=False,
            is_deleted=False,
            version=execution.published_version,
        )
    except (Template.DoesNotExist, TemplateSnapshot.DoesNotExist):
        raise StartExecutionRejected("VALIDATION_STALE", "published_snapshot", repairable=False) from None
    if (
        template.space_id != execution.space_id
        or template.scope_type != context.scope_type
        or template.scope_value != context.scope_value
        or template.bk_app_code != execution.platform_app
        or compute_tree_fingerprint(snapshot.data) != execution.manifest.draft_tree_fingerprint
    ):
        raise StartExecutionRejected("VALIDATION_STALE", "published_snapshot", repairable=False)
    return deepcopy(snapshot.data), sha256_json(snapshot.data)


def _lock_graph(context, execution_id, expected_snapshot_hash=None, *, lock_siblings=False):
    seed = ExecutionRun.objects.only("published_template_id").get(pk=execution_id)
    template = Template.objects.select_for_update().get(pk=seed.published_template_id, is_deleted=False)
    execution_seed = ExecutionRun.objects.only("run_id", "revision_id", "manifest_id", "published_snapshot_id").get(
        pk=execution_id
    )
    run = HarnessRun.objects.select_for_update().get(pk=execution_seed.run_id)
    revision = WorkflowPlanRevision.objects.select_for_update().get(pk=execution_seed.revision_id, run=run)
    snapshot = TemplateSnapshot.objects.select_for_update().get(
        pk=execution_seed.published_snapshot_id,
        template_id=template.id,
        draft=False,
        is_deleted=False,
    )
    manifest = ReleaseManifest.objects.select_for_update().get(
        pk=execution_seed.manifest_id, run=run, revision=revision
    )
    ReleasePublication.objects.select_for_update().get(manifest=manifest, published_snapshot_id=snapshot.id)
    execution_query = ExecutionRun.objects.select_for_update().select_related(
        "run", "revision", "manifest__publication"
    )
    if lock_siblings:
        siblings = list(execution_query.filter(run=run).order_by("id"))
        execution = next(
            (
                item
                for item in siblings
                if item.pk == execution_id and item.revision_id == revision.id and item.manifest_id == manifest.id
            ),
            None,
        )
        if execution is None:
            raise ExecutionRun.DoesNotExist
    else:
        execution = execution_query.get(pk=execution_id, run=run, revision=revision, manifest=manifest)
    if not _matches_authority(context, execution):
        raise StartExecutionRejected("CAPABILITY_FORBIDDEN", "execution_id", category="PERMISSION", repairable=False)
    if (
        expected_snapshot_hash is not None and sha256_json(snapshot.data) != expected_snapshot_hash
    ) or compute_tree_fingerprint(snapshot.data) != manifest.draft_tree_fingerprint:
        raise StartExecutionRejected("VALIDATION_STALE", "published_snapshot", repairable=False)
    return run, execution


def _persist_live_projection(context, execution_id, state, now, expected_snapshot_hash):
    target = ExecutionRun.Status.PAUSED if state == "SUSPENDED" else ExecutionRun.Status.EXECUTING
    with transaction.atomic():
        run, execution = _lock_graph(context, execution_id, expected_snapshot_hash)
        if execution.status in _CONTROL_STATES:
            raise _ControlBarrierChanged()
        if execution.status in ExecutionRun.TERMINAL:
            return execution
        if target == ExecutionRun.Status.PAUSED and execution.status in {
            ExecutionRun.Status.START_DISPATCHING,
            ExecutionRun.Status.START_UNCERTAIN,
        }:
            # SUSPENDED proves start completion, but the model deliberately
            # requires the durable START_* -> EXECUTING -> PAUSED sequence.
            execution.status = ExecutionRun.Status.EXECUTING
            execution.save(update_fields=["status", "update_at"])
        update_fields = ["last_engine_state", "heartbeat_at", "update_at"]
        execution.last_engine_state = state
        execution.heartbeat_at = now
        if execution.status != target:
            execution.status = target
            update_fields.append("status")
        execution.save(update_fields=update_fields)
        if run.status == HarnessRunStatus.PUBLISHED:
            run.status = HarnessRunStatus.EXECUTING
            run.save(update_fields=["status", "update_at"])
        return execution


def _parse_deadline(report):
    try:
        observed = datetime.datetime.fromisoformat(report["terminal_observed_at"])
        deadline = datetime.datetime.fromisoformat(report["deadline_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if timezone.is_naive(observed) or timezone.is_naive(deadline) or deadline <= observed:
        return None
    return observed, deadline


def _persist_waiting(context, execution_id, evaluation, now, expected_snapshot_hash):
    with transaction.atomic():
        _run, execution = _lock_graph(context, execution_id, expected_snapshot_hash)
        if execution.status in _CONTROL_STATES:
            raise _ControlBarrierChanged()
        if execution.status in ExecutionRun.TERMINAL:
            return execution, False
        timing = _parse_deadline(execution.postcondition_report)
        if timing is None:
            if execution.postcondition_status == ExecutionRun.PostconditionStatus.RUNNING:
                raise StartExecutionRejected("VALIDATION_STALE", "postconditions", repairable=False)
            observed, deadline = now, now + POSTCONDITION_EVIDENCE_WAIT
        else:
            observed, deadline = timing
        report = evaluation.as_report()
        report.update(
            {
                "reason": "evidence_pending" if now < deadline else "evidence_deadline_expired",
                "terminal_observed_at": observed.isoformat(),
                "deadline_at": deadline.isoformat(),
            }
        )
        execution.status = ExecutionRun.Status.EXECUTING
        execution.last_engine_state = "FINISHED"
        execution.heartbeat_at = now
        execution.postcondition_status = ExecutionRun.PostconditionStatus.RUNNING
        execution.postcondition_report = report
        execution.save(
            update_fields=[
                "status",
                "last_engine_state",
                "heartbeat_at",
                "postcondition_status",
                "postcondition_report",
                "update_at",
            ]
        )
        return execution, now >= deadline


def _terminal_report(execution, evaluation, reason):
    report = evaluation.as_report() if evaluation is not None else {"status": "UNAVAILABLE", "predicates": []}
    timing = _parse_deadline(execution.postcondition_report)
    if timing is not None:
        report["terminal_observed_at"] = timing[0].isoformat()
        report["deadline_at"] = timing[1].isoformat()
    report["reason"] = reason
    return report


def _terminalize(
    context,
    execution,
    *,
    target_status,
    postcondition_status,
    evaluation,
    reason,
    engine_state,
    now,
    expected_snapshot_hash,
    token_broker,
    control_recovery=False,
):
    with transaction.atomic():
        run, locked = _lock_graph(context, execution.id, expected_snapshot_hash, lock_siblings=True)
        if locked.status in _CONTROL_STATES and not control_recovery:
            raise _ControlBarrierChanged()
        if locked.status not in ExecutionRun.TERMINAL:
            if EvidenceEvent.objects.select_for_update().filter(execution=locked).count() >= MAX_EVIDENCE_ITEMS:
                raise StartExecutionRejected("RETRYABLE_INFRA", "evidence", retryable=True, repairable=False)
            # Revocation is part of the same terminal transaction after the
            # complete locked authority graph has been revalidated.  A stale
            # readback must not consume live execution authority.
            token_broker.revoke_execution_leases(context, locked)
            locked.status = target_status
            locked.last_engine_state = engine_state
            locked.heartbeat_at = now
            locked.postcondition_status = postcondition_status
            locked.postcondition_report = _terminal_report(locked, evaluation, reason)
            locked.terminal_at = now
            locked.save(
                update_fields=[
                    "status",
                    "last_engine_state",
                    "heartbeat_at",
                    "postcondition_status",
                    "postcondition_report",
                    "terminal_at",
                    "update_at",
                ]
            )
            if run.status == HarnessRunStatus.PUBLISHED:
                run.status = HarnessRunStatus.EXECUTING
                run.save(update_fields=["status", "update_at"])
            sibling_statuses = list(ExecutionRun.objects.filter(run=run).values_list("status", flat=True))
            if all(status in ExecutionRun.TERMINAL for status in sibling_statuses):
                if ExecutionRun.Status.FAILED in sibling_statuses:
                    run_target = HarnessRunStatus.FAILED
                elif ExecutionRun.Status.SUCCEEDED in sibling_statuses:
                    run_target = HarnessRunStatus.SUCCEEDED
                else:
                    run_target = HarnessRunStatus.CANCELLED
                if run.status != run_target:
                    if run.status != HarnessRunStatus.EXECUTING:
                        raise StartExecutionRejected("VALIDATION_STALE", "run_id", repairable=False)
                    run.status = run_target
                    run.save(update_fields=["status", "update_at"])
            record_evidence(
                run=run,
                revision=locked.revision,
                execution=locked,
                event_type="EXECUTION_{}".format(target_status),
                action=TOOL_NAME,
                payload={
                    "execution_id": str(locked.id),
                    "status": target_status,
                    "postcondition_status": postcondition_status,
                    "reason": reason,
                },
                actor=context.actor,
                correlation_id=context.correlation_id,
            )
    locked.refresh_from_db()
    finalize_evidence_bundle(locked)
    return locked


def _converge(
    context,
    execution,
    observation,
    evaluator,
    *,
    now,
    expected_snapshot_hash,
    token_broker,
):
    state = observation.state
    if state == "READY" and execution.status in {
        ExecutionRun.Status.CREATED,
        ExecutionRun.Status.START_DISPATCHING,
        ExecutionRun.Status.START_UNCERTAIN,
    }:
        # READY proves task creation only.  It cannot prove that the start
        # dispatch completed, so leave the Task 7 start Saga barrier intact.
        return execution
    if state == "FINISHED" and execution.status in {
        ExecutionRun.Status.START_DISPATCHING,
        ExecutionRun.Status.START_UNCERTAIN,
    }:
        # FINISHED is conclusive start readback.  Persist the required model
        # edge before applying terminal postconditions in the next lock phase.
        execution = _persist_live_projection(
            context,
            execution.id,
            "RUNNING",
            now,
            expected_snapshot_hash,
        )
    if state in {"READY", "RUNNING", "SUSPENDED", "FAILED"}:
        return _persist_live_projection(context, execution.id, state, now, expected_snapshot_hash)
    if state in {"REVOKED", "CANCELLED"}:
        return _terminalize(
            context,
            execution,
            target_status=ExecutionRun.Status.CANCELLED,
            postcondition_status=ExecutionRun.PostconditionStatus.UNAVAILABLE,
            evaluation=None,
            reason="engine_cancelled",
            engine_state=state,
            now=now,
            expected_snapshot_hash=expected_snapshot_hash,
            token_broker=token_broker,
        )
    if state == "EXPIRED":
        # TaskInstance expiry removes the trustworthy outcome evidence.  It is
        # not proof of user cancellation, so fail closed as execution failure.
        return _terminalize(
            context,
            execution,
            target_status=ExecutionRun.Status.FAILED,
            postcondition_status=ExecutionRun.PostconditionStatus.UNAVAILABLE,
            evaluation=None,
            reason="engine_execution_expired",
            engine_state=state,
            now=now,
            expected_snapshot_hash=expected_snapshot_hash,
            token_broker=token_broker,
        )
    evaluation = evaluator.evaluate(state, observation.node_outputs)
    if evaluation.status == "PASSED":
        return _terminalize(
            context,
            execution,
            target_status=ExecutionRun.Status.SUCCEEDED,
            postcondition_status=ExecutionRun.PostconditionStatus.PASSED,
            evaluation=evaluation,
            reason="postconditions_passed",
            engine_state=state,
            now=now,
            expected_snapshot_hash=expected_snapshot_hash,
            token_broker=token_broker,
        )
    if evaluation.status == "FAILED":
        return _terminalize(
            context,
            execution,
            target_status=ExecutionRun.Status.FAILED,
            postcondition_status=ExecutionRun.PostconditionStatus.FAILED,
            evaluation=evaluation,
            reason="postconditions_failed",
            engine_state=state,
            now=now,
            expected_snapshot_hash=expected_snapshot_hash,
            token_broker=token_broker,
        )
    waiting, expired = _persist_waiting(context, execution.id, evaluation, now, expected_snapshot_hash)
    if not expired or waiting.status in ExecutionRun.TERMINAL:
        return waiting
    return _terminalize(
        context,
        waiting,
        target_status=ExecutionRun.Status.FAILED,
        postcondition_status=ExecutionRun.PostconditionStatus.UNAVAILABLE,
        evaluation=evaluation,
        reason="postcondition_evidence_unavailable",
        engine_state=state,
        now=now,
        expected_snapshot_hash=expected_snapshot_hash,
        token_broker=token_broker,
    )


def _control_response_snapshot(context, run, revision, execution, action):
    response = WorkflowValidator(context, resolver=object())._envelope(
        ok=True,
        run=run,
        revision=revision,
        plan_hash_value=revision.plan_hash,
        status=run.status,
        errors=[],
        artifact_refs=[
            {
                "type": "workflow_execution_control",
                "execution_id": str(execution.id),
                "execution_status": execution.status,
                "action": action,
                "reconciled": True,
            }
        ],
    )
    response["summary"] = "Workflow execution control was reconciled from bounded Engine readback."
    response["next_actions"] = [TOOL_NAME, CONTROL_TOOL_NAME]
    return response


def _manual_control_response(context, execution, request):
    response = _response(
        context,
        execution,
        request,
        refresh={"available": False, "reason": "control_reconciliation_required"},
    )
    response["next_actions"] = ["manual_reconcile_execution"]
    return response


def _control_readback_proves(attempt, observation):
    if not isinstance(observation, ControlReadbackObservation):
        return False
    if not isinstance(observation.root_state, str) or observation.root_state not in _WIRE_CONTROL_STATES:
        return False
    empty_node_facts = (
        observation.template_node_id,
        observation.node_state,
        observation.node_version,
        observation.runtime_mapping_fingerprint,
    )
    if attempt.action == "pause":
        return not any(value is not None for value in empty_node_facts) and observation.root_state == "SUSPENDED"
    if attempt.action == "resume":
        return not any(value is not None for value in empty_node_facts) and observation.root_state == "RUNNING"
    if attempt.action == "revoke":
        return not any(value is not None for value in empty_node_facts) and observation.root_state == "REVOKED"
    if observation.root_state in {"FINISHED", "REVOKED", "EXPIRED"}:
        return False
    if (
        observation.template_node_id != attempt.template_node_id
        or observation.runtime_mapping_fingerprint != attempt.runtime_mapping_fingerprint
        or safe_opaque_identifier(observation.node_version) is None
        or observation.node_version == attempt.pre_node_version
    ):
        return False
    if attempt.action == "retry":
        return isinstance(observation.node_state, str) and observation.node_state in _NODE_RETRY_STATES
    if attempt.action == "skip":
        return observation.node_state == "FINISHED"
    return attempt.action == "forced_fail" and observation.node_state == "FAILED"


def _persist_control_state(execution, attempt, observation, now):
    target = ExecutionRun.Status.PAUSED if attempt.action == "pause" else ExecutionRun.Status.EXECUTING
    execution.status = target
    execution.last_engine_state = observation.root_state
    execution.heartbeat_at = now
    execution.save(update_fields=["status", "last_engine_state", "heartbeat_at", "update_at"])
    return execution


def _completed_control_state_matches(execution, attempt):
    expected = {
        "pause": ExecutionRun.Status.PAUSED,
        "resume": ExecutionRun.Status.EXECUTING,
        "revoke": ExecutionRun.Status.CANCELLED,
        "retry": ExecutionRun.Status.EXECUTING,
        "skip": ExecutionRun.Status.EXECUTING,
        "forced_fail": ExecutionRun.Status.EXECUTING,
    }
    return execution.status == expected[attempt.action]


def _reconcile_control(
    context,
    execution,
    attempt,
    observation,
    *,
    now,
    expected_snapshot_hash,
    token_broker,
):
    """Converge one journaled mutation without redispatching or appending audit noise."""
    with transaction.atomic():
        record = HarnessIdempotencyRecord.objects.select_for_update().get(pk=attempt.record_id)
        run, locked = _lock_graph(
            context, execution.id, expected_snapshot_hash, lock_siblings=attempt.action == "revoke"
        )
        current_record, current_attempt = _load_control_attempt(
            context,
            locked,
            locked_record=record,
            lock_event=True,
        )
        if (
            current_record is None
            or current_attempt is None
            or current_attempt.journal_fingerprint != attempt.journal_fingerprint
            or not _control_readback_proves(current_attempt, observation)
        ):
            return locked, False
        if locked.status not in _CONTROL_STATES:
            return locked, record.status == "COMPLETED" and _completed_control_state_matches(locked, current_attempt)
        if current_attempt.action == "revoke":
            locked = _terminalize(
                context,
                locked,
                target_status=ExecutionRun.Status.CANCELLED,
                postcondition_status=ExecutionRun.PostconditionStatus.UNAVAILABLE,
                evaluation=None,
                reason="engine_cancelled",
                engine_state="REVOKED",
                now=now,
                expected_snapshot_hash=expected_snapshot_hash,
                token_broker=token_broker,
                control_recovery=True,
            )
            run.refresh_from_db()
        else:
            locked = _persist_control_state(locked, current_attempt, observation, now)
        if record.status == "IN_FLIGHT":
            complete_idempotency(
                record,
                _control_response_snapshot(context, run, locked.revision, locked, current_attempt.action),
                run=run,
                resource_reference=str(locked.id),
            )
        return locked, True


def _refresh_control_execution(
    context,
    execution,
    request,
    adapter,
    pipeline_tree,
    snapshot_hash,
    *,
    now,
    token_broker,
):
    _record, attempt = _load_control_attempt(context, execution)
    if attempt is None:
        return _manual_control_response(context, execution, request)
    observation = adapter.observe_control(
        execution.task_ref,
        pipeline_tree,
        template_node_id=attempt.template_node_id,
    )
    execution, reconciled = _reconcile_control(
        context,
        execution,
        attempt,
        observation,
        now=now,
        expected_snapshot_hash=snapshot_hash,
        token_broker=token_broker,
    )
    if not reconciled:
        return _manual_control_response(context, execution, request)
    return _response(
        context,
        execution,
        request,
        refresh={"available": True, "reason": "control_reconciled"},
    )


def get_workflow_execution_with_context(
    context,
    payload,
    *,
    adapter=None,
    token_broker=None,
    clock=None,
):
    """Project one owned execution and refresh it only behind the execution flag."""
    try:
        require_tool_enabled(context, TOOL_NAME)
        request = validate_get_execution_request(payload)
        _decode_cursor(request.cursor)
        execution = _load_owned_execution(context, request.execution_id)
        runtime_enabled = is_harness_execution_enabled(context.space_id)
        if not runtime_enabled:
            return _response(
                context,
                execution,
                request,
                refresh={"available": False, "reason": "execution_disabled"},
            )
        if execution.status in ExecutionRun.TERMINAL:
            if not EvidenceBundle.objects.filter(execution=execution).exists():
                finalize_evidence_bundle(execution)
                execution.refresh_from_db()
            return _response(
                context,
                execution,
                request,
                refresh={"available": False, "reason": "execution_terminal"},
            )
        if not execution.task_ref:
            return _response(
                context,
                execution,
                request,
                refresh={"available": False, "reason": "task_reference_unavailable"},
            )
        pipeline_tree, snapshot_hash = _runtime_snapshot(context, execution)
        active_adapter = adapter or ExecutionReadAdapter(space_id=context.space_id)
        now = (clock or timezone.now)()
        if timezone.is_naive(now):
            raise StartExecutionRejected("RETRYABLE_INFRA", "clock", repairable=False)
        active_token_broker = token_broker or TokenBroker()
        if execution.status in _CONTROL_STATES:
            return _refresh_control_execution(
                context,
                execution,
                request,
                active_adapter,
                pipeline_tree,
                snapshot_hash,
                now=now,
                token_broker=active_token_broker,
            )
        evaluator = PostconditionEvaluator(execution.manifest.postcondition_spec)
        observation = active_adapter.observe(execution.task_ref, pipeline_tree, evaluator.required_outputs)
        try:
            execution = _converge(
                context,
                execution,
                observation,
                evaluator,
                now=now,
                expected_snapshot_hash=snapshot_hash,
                token_broker=active_token_broker,
            )
        except _ControlBarrierChanged:
            # The ordinary graph-lock transaction has rolled back before this
            # reload; control recovery may now acquire idempotency first.
            execution = _load_owned_execution(context, request.execution_id)
            return _refresh_control_execution(
                context,
                execution,
                request,
                active_adapter,
                pipeline_tree,
                snapshot_hash,
                now=now,
                token_broker=active_token_broker,
            )
        return _response(
            context,
            execution,
            request,
            refresh={"available": True, "reason": "engine_refreshed"},
        )
    except StartExecutionRejected as rejection:
        return _failure(context, rejection)
    except HarnessContextError as error:
        return _failure(context, StartExecutionRejected(error.code, "execution", repairable=False))
    except TaskNotFound:
        return _failure(context, StartExecutionRejected("VALIDATION_STALE", "task_ref", repairable=False))
    except ReadbackUnavailable:
        return _failure(context, StartExecutionRejected("RETRYABLE_INFRA", "execution", retryable=True))
    except PostconditionSpecError:
        return _failure(context, StartExecutionRejected("VALIDATION_STALE", "postconditions", repairable=False))
    except (
        ExecutionRun.DoesNotExist,
        HarnessRun.DoesNotExist,
        WorkflowPlanRevision.DoesNotExist,
        ReleaseManifest.DoesNotExist,
        ReleasePublication.DoesNotExist,
        Template.DoesNotExist,
        TemplateSnapshot.DoesNotExist,
    ):
        return _failure(
            context,
            StartExecutionRejected("CAPABILITY_FORBIDDEN", "execution_id", category="PERMISSION", repairable=False),
        )
    except (DatabaseError, ValidationError):
        return _failure(context, StartExecutionRejected("RETRYABLE_INFRA", "execution", retryable=True))
    except Exception:
        return _failure(context, StartExecutionRejected("RETRYABLE_INFRA", "execution", retryable=True))


__all__ = ["POSTCONDITION_EVIDENCE_WAIT", "get_workflow_execution_with_context"]
