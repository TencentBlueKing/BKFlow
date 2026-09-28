"""Harness control_debug_session validation and lifecycle contracts."""

import copy
from dataclasses import replace

import pytest
from django.db import DatabaseError

from bkflow.harness.constants import DebugSessionStatus, HarnessRunStatus
from bkflow.harness.models import (
    DebugSession,
    EvidenceEvent,
    HarnessIdempotencyRecord,
    TokenLease,
    WorkflowPlanRevision,
)
from bkflow.harness.services.debug.facade import (
    control_debug_session_with_context,
    get_debug_session_with_context,
    start_debug_session_with_context,
)
from bkflow.harness.services.token_broker import TokenBroker
from bkflow.space.configs import HarnessDebugEnabledConfig, SpaceConfigValueType
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.debug.service import DebugConflictError
from bkflow.template.models import (
    DebugContext,
    DebugNodeState,
    Template,
    TemplateSnapshot,
)

pytest_plugins = ("tests.interface.harness.debug.test_start_session",)


def _started(start_case):
    context, _run, _revision, _template, request, resolver = start_case
    SpaceConfig.objects.create(
        space_id=context.space_id,
        name=HarnessDebugEnabledConfig.name,
        value_type=SpaceConfigValueType.TEXT.value,
        text_value="true",
    )
    assert start_debug_session_with_context(context, request, resolver=resolver)["ok"] is True
    return context, DebugSession.objects.get(), resolver


def _control_request(session, action, **values):
    return {
        "session_id": str(session.id),
        "expected_plan_hash": session.plan_hash,
        "action": action,
        "idempotency_key": "control-{}-1".format(action),
        **values,
    }


@pytest.mark.django_db
def test_reset_is_idempotent_returns_impact_and_preserves_evidence(start_case):
    """Reset mutates once while retaining immutable session Evidence history."""
    context, session, resolver = _started(start_case)
    node = DebugNodeState.objects.get(debug_context_id=session.debug_context_id, node_id="A")
    node.status = "finished"
    node.outputs = {"result": "old"}
    node.save(update_fields=["status", "outputs"])
    evidence_before = EvidenceEvent.objects.count()
    request = _control_request(session, "reset", node_ids=["A"])

    first = control_debug_session_with_context(context, request, resolver=resolver)
    replay = control_debug_session_with_context(context, request, resolver=resolver)

    node.refresh_from_db()
    session.refresh_from_db()
    session.run.refresh_from_db()
    assert first == replay
    assert first["ok"] is True
    assert first["artifact_refs"][0]["result"] == {"reset_node_ids": ["A"]}
    assert "reset_impact" in first["artifact_refs"][0]
    assert first["artifact_refs"][0]["session_status"] == DebugSessionStatus.ACTIVE
    assert first["artifact_refs"][0]["run_status"] == HarnessRunStatus.DEBUGGING
    assert node.status == "not_run"
    assert session.status == DebugSessionStatus.ACTIVE
    assert session.run.status == HarnessRunStatus.DEBUGGING
    assert EvidenceEvent.objects.count() == evidence_before + 2
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_debug_session", status="COMPLETED").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mutation",
    [
        {"action": "reset", "node_ids": ["A"], "unexpected": True},
        {"action": "reset", "node_ids": [{}]},
        {"action": "reset", "node_ids": ["credential://id/raw-secret"]},
        {
            "action": "set_node_mock",
            "node_id": "A",
            "enabled": True,
            "mock_result": "success",
            "mock_outputs": {"password": "raw-secret"},
            "mock_error": "",
        },
        {"action": "set_context_var", "key": "${token}", "value": "Bearer raw-secret"},
    ],
)
def test_control_schema_and_secret_validation_fail_before_side_effects(start_case, mutation):
    """Malformed tagged controls cannot create idempotency or Evidence rows."""
    context, session, resolver = _started(start_case)
    mutation = dict(mutation)
    payload = _control_request(session, mutation.pop("action"), **mutation)
    evidence_before = EvidenceEvent.objects.count()
    idempotency_before = HarnessIdempotencyRecord.objects.count()

    response = control_debug_session_with_context(context, payload, resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert EvidenceEvent.objects.count() == evidence_before
    assert HarnessIdempotencyRecord.objects.count() == idempotency_before


@pytest.mark.django_db
def test_control_revalidates_tree_and_rejects_running_reset(start_case):
    """A control cannot mutate a drifted draft or bypass a live operation lock."""
    context, session, resolver = _started(start_case)
    snapshot = TemplateSnapshot.objects.get(pk=Template.objects.get(pk=session.template_id).snapshot_id)
    original = copy.deepcopy(snapshot.data)
    changed = copy.deepcopy(snapshot.data)
    changed["activities"]["A"]["component"]["data"] = {"changed": {"value": True}}
    snapshot.data = changed
    snapshot.save(update_fields=["data"])

    drift = control_debug_session_with_context(
        context,
        _control_request(session, "reset", node_ids=["A"]),
        resolver=resolver,
    )
    assert drift["ok"] is False
    assert drift["errors"][0]["code"] == "VALIDATION_STALE"

    snapshot.data = original
    snapshot.save(update_fields=["data"])
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    debug_context.status = "running"
    debug_context.active_task_id = 7001
    debug_context.save(update_fields=["status", "active_task_id"])
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    conflict = control_debug_session_with_context(
        context,
        _control_request(session, "reset", node_ids=["A"], idempotency_key="control-reset-running"),
        resolver=resolver,
    )
    assert conflict["ok"] is False
    assert conflict["errors"][0]["code"] == "DEBUG_CONFLICT"


@pytest.mark.django_db
def test_set_node_mock_and_context_var_apply_once(start_case):
    """The two configuration actions use the existing SDK semantics exactly once."""
    context, session, resolver = _started(start_case)
    mock_response = control_debug_session_with_context(
        context,
        _control_request(
            session,
            "set_node_mock",
            node_id="A",
            enabled=True,
            mock_result="success",
            mock_outputs={"result": "preset"},
            mock_error="",
        ),
        resolver=resolver,
    )
    variable_response = control_debug_session_with_context(
        context,
        _control_request(
            session,
            "set_context_var",
            key="${safe}",
            value={"nested": "value"},
            idempotency_key="control-context-1",
        ),
        resolver=resolver,
    )

    node = DebugNodeState.objects.get(debug_context_id=session.debug_context_id, node_id="A")
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    assert mock_response["ok"] is True
    assert mock_response["artifact_refs"][0]["result"]["execution_mode"] == "mock"
    assert variable_response["ok"] is True
    assert node.mock_outputs == {"result": "preset"}
    assert debug_context.global_vars["${result}"] == "preset"
    assert debug_context.global_vars["${safe}"] == {"nested": "value"}


@pytest.mark.django_db
def test_terminate_revokes_every_lease_before_terminal_session_and_run(start_case, mocker):
    """A terminal transition is impossible until the broker revokes all live leases."""
    context, session, resolver = _started(start_case)
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="control-space",
    )
    mocker.patch("bkflow.permission.token_issuer.TokenResourceValidator.validate", return_value=None)
    TokenBroker().acquire_debug_lease(context, session)
    assert TokenLease.objects.filter(session=session, status=TokenLease.Status.ACTIVE).count() == 1

    response = control_debug_session_with_context(
        context,
        _control_request(session, "terminate"),
        resolver=resolver,
    )

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is True
    assert response["artifact_refs"][0]["result"] == {"status": "terminated"}
    assert session.status == DebugSessionStatus.TERMINATED
    assert session.run.status == HarnessRunStatus.DRAFT_READY
    assert not TokenLease.objects.filter(session=session, status=TokenLease.Status.ACTIVE).exists()
    assert TokenLease.objects.filter(session=session, status=TokenLease.Status.REVOKED).count() == 1


@pytest.mark.django_db
def test_running_node_terminate_id_map_failure_keeps_session_locked(start_case, mocker):
    """An Engine mapping failure must not release an owned running session."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=7001,
        active_node_id="A",
    )
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="failed-control-space",
    )
    mocker.patch("bkflow.permission.token_issuer.TokenResourceValidator.validate", return_value=None)
    TokenBroker().acquire_debug_lease(context, session)
    client = mocker.MagicMock()
    client.get_node_id_map.return_value = {"result": False}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=client)

    response = control_debug_session_with_context(
        context,
        _control_request(session, "terminate", node_id="A"),
        resolver=resolver,
    )

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_EXECUTION_FAILED"
    assert session.status == DebugSessionStatus.RUNNING
    assert session.current_task_id == 7001
    assert session.run.status == HarnessRunStatus.DEBUGGING
    assert not TokenLease.objects.filter(session=session, status=TokenLease.Status.ACTIVE).exists()
    assert TokenLease.objects.filter(session=session, status=TokenLease.Status.REVOKED).count() == 1
    events = list(EvidenceEvent.objects.filter(action="control_debug_session").order_by("occurred_at", "id"))
    assert [event.event_type for event in events] == ["DEBUG_CONTROL_REQUESTED", "DEBUG_CONTROL_FAILED"]
    assert events[-1].redacted_payload == {
        "action": "terminate",
        "code": "DEBUG_EXECUTION_FAILED",
        "leases_revoked": True,
        "run_status": HarnessRunStatus.DEBUGGING,
        "session_id": str(session.id),
        "session_status": DebugSessionStatus.RUNNING,
    }


@pytest.mark.django_db
def test_running_terminate_ack_revokes_leases_without_premature_terminal(start_case, mocker):
    """An async Engine acknowledgement removes authority but keeps polling ownership."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=7001,
    )
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="terminating-control-space",
    )
    mocker.patch("bkflow.permission.token_issuer.TokenResourceValidator.validate", return_value=None)
    TokenBroker().acquire_debug_lease(context, session)
    client = mocker.MagicMock()
    client.operate_task.return_value = {"result": True}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=client)

    response = control_debug_session_with_context(
        context,
        _control_request(session, "terminate"),
        resolver=resolver,
    )

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is True
    assert response["artifact_refs"][0]["result"] == {"status": "terminating"}
    assert session.status == DebugSessionStatus.RUNNING
    assert session.current_task_id == 7001
    assert session.run.status == HarnessRunStatus.DEBUGGING
    assert not TokenLease.objects.filter(session=session, status=TokenLease.Status.ACTIVE).exists()
    assert TokenLease.objects.filter(session=session, status=TokenLease.Status.REVOKED).count() == 1


@pytest.mark.django_db
def test_control_rejects_foreign_owner_before_idempotency_or_evidence(start_case):
    """Request fields cannot override the trusted platform identity."""
    context, session, resolver = _started(start_case)
    evidence_before = EvidenceEvent.objects.count()
    idempotency_before = HarnessIdempotencyRecord.objects.count()

    response = control_debug_session_with_context(
        replace(context, actor="foreign-user"),
        _control_request(session, "set_context_var", key="${safe}", value="value"),
        resolver=resolver,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert EvidenceEvent.objects.count() == evidence_before
    assert HarnessIdempotencyRecord.objects.count() == idempotency_before


@pytest.mark.django_db
def test_control_never_adopts_a_foreign_engine_task(start_case):
    """The shared canvas context must still belong to this exact session task."""
    context, session, resolver = _started(start_case)
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=9009,
    )

    response = control_debug_session_with_context(
        context,
        _control_request(session, "terminate"),
        resolver=resolver,
    )

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_EXECUTION_FAILED"
    assert session.status == DebugSessionStatus.ACTIVE
    assert session.run.status == HarnessRunStatus.DEBUGGING
    assert not EvidenceEvent.objects.filter(action="control_debug_session").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("mutation", ["artifact_template", "superseded_revision"])
def test_control_rejects_managed_artifact_or_latest_revision_drift_without_side_effects(
    start_case,
    mutation,
):
    """Control must bind the exact latest revision and managed template identity."""
    context, session, resolver = _started(start_case)
    if mutation == "artifact_template":
        artifacts = copy.deepcopy(session.run.artifact_references)
        artifacts[0]["template_id"] = session.template_id + 1
        session.run.artifact_references = artifacts
        session.run.save(update_fields=["artifact_references"])
    else:
        WorkflowPlanRevision.objects.create(
            run=session.run,
            sequence=session.revision.sequence + 1,
            parent_revision=session.revision,
            intent_spec={"goal": "superseding revision"},
            canonical_a2flow={"version": "2.0", "nodes": []},
            plan_hash="f" * 64,
        )
    evidence_before = EvidenceEvent.objects.count()
    idempotency_before = HarnessIdempotencyRecord.objects.count()

    response = control_debug_session_with_context(
        context,
        _control_request(session, "reset", node_ids=["A"]),
        resolver=resolver,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert EvidenceEvent.objects.count() == evidence_before
    assert HarnessIdempotencyRecord.objects.count() == idempotency_before


@pytest.mark.django_db
def test_debug_conflict_pairs_requested_with_fixed_failed_evidence(start_case):
    """A deterministic downstream conflict never leaves REQUESTED orphaned."""
    context, session, resolver = _started(start_case)

    class ConflictAdapter:
        def __init__(self, **_kwargs):
            pass

        def require_context_ownership(self, *_args, **_kwargs):
            return None

        def set_context_var(self, *_args, **_kwargs):
            raise DebugConflictError("downstream secret-shaped conflict")

    response = control_debug_session_with_context(
        context,
        _control_request(session, "set_context_var", key="${safe}", value="value"),
        resolver=resolver,
        adapter_class=ConflictAdapter,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_CONFLICT"
    events = list(EvidenceEvent.objects.filter(action="control_debug_session").order_by("occurred_at", "id"))
    assert [event.event_type for event in events] == ["DEBUG_CONTROL_REQUESTED", "DEBUG_CONTROL_FAILED"]
    assert events[-1].redacted_payload["code"] == "DEBUG_CONFLICT"
    assert "downstream secret-shaped conflict" not in str(response) + str(events[-1].redacted_payload)


@pytest.mark.django_db
def test_control_omitted_result_records_reason_without_false_fingerprint(start_case):
    """An omitted projection is not a complete value that can be truthfully hashed."""
    context, session, resolver = _started(start_case)

    class LargeResultAdapter:
        def __init__(self, **_kwargs):
            pass

        def require_context_ownership(self, *_args, **_kwargs):
            return None

        def set_context_var(self, *_args, **_kwargs):
            return {"global_vars": {"large": "x" * 20000}}

    response = control_debug_session_with_context(
        context,
        _control_request(session, "set_context_var", key="${safe}", value="value"),
        resolver=resolver,
        adapter_class=LargeResultAdapter,
    )

    assert response["ok"] is True
    assert response["artifact_refs"][0]["result"]["omitted"] is True
    event = EvidenceEvent.objects.get(event_type="DEBUG_CONTROL_COMPLETED")
    assert event.redacted_payload["result_omitted"] is True
    assert event.redacted_payload["result_omission_reason"] == "projection_budget_exceeded"
    assert "result_fingerprint" not in event.redacted_payload


@pytest.mark.django_db
def test_run_debug_inflight_barrier_blocks_control_across_keys(start_case):
    """An uncertain run dispatch blocks every later control for the same session."""
    context, session, resolver = _started(start_case)
    HarnessIdempotencyRecord.objects.create(
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        tool_name="run_debug",
        run_scope="run:{}".format(session.run.run_id),
        run=session.run,
        idempotency_key="uncertain-run",
        request_hash="f" * 64,
        status="IN_FLIGHT",
        resource_reference=str(session.id),
    )

    response = control_debug_session_with_context(
        context,
        _control_request(session, "set_context_var", key="${safe}", value="value"),
        resolver=resolver,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert "${safe}" not in DebugContext.objects.get(pk=session.debug_context_id).global_vars
    assert not HarnessIdempotencyRecord.objects.filter(tool_name="control_debug_session").exists()


@pytest.mark.django_db
def test_uncertain_terminate_new_key_never_redispatches(start_case, mocker):
    """A post-Engine DB failure retains the barrier across new idempotency keys."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=7001,
    )
    calls = {"terminate": 0, "revoke": 0}

    class UncertainAdapter:
        def __init__(self, **_kwargs):
            pass

        def require_context_ownership(self, *_args, **_kwargs):
            return None

        def terminate(self, *_args, **_kwargs):
            calls["terminate"] += 1
            return {"status": "idle"}

    class RecordingBroker:
        def revoke_active_leases(self, _context, _session):
            calls["revoke"] += 1
            return 0

    original_save = HarnessIdempotencyRecord.save

    def fail_completion(record, *args, **kwargs):
        if record.status == "COMPLETED":
            raise DatabaseError("post-dispatch failure")
        return original_save(record, *args, **kwargs)

    mocker.patch.object(HarnessIdempotencyRecord, "save", autospec=True, side_effect=fail_completion)
    first = control_debug_session_with_context(
        context,
        _control_request(session, "terminate", idempotency_key="terminate-uncertain-1"),
        resolver=resolver,
        adapter_class=UncertainAdapter,
        token_broker=RecordingBroker(),
    )
    second = control_debug_session_with_context(
        context,
        _control_request(session, "terminate", idempotency_key="terminate-uncertain-2"),
        resolver=resolver,
        adapter_class=UncertainAdapter,
        token_broker=RecordingBroker(),
    )

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert first["ok"] is second["ok"] is False
    assert first["errors"][0]["code"] == second["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert calls == {"terminate": 1, "revoke": 1}
    assert session.status == DebugSessionStatus.RUNNING
    assert session.run.status == HarnessRunStatus.DEBUGGING
    barrier = HarnessIdempotencyRecord.objects.get(tool_name="control_debug_session")
    assert barrier.status == "IN_FLIGHT"
    assert barrier.resource_reference == str(session.id)


@pytest.mark.django_db
def test_disabled_flag_keeps_get_available_but_rejects_control_before_mutation(start_case):
    """Disabling debug blocks control without hiding an already-created session."""
    context, session, resolver = _started(start_case)
    SpaceConfig.objects.filter(space_id=context.space_id, name=HarnessDebugEnabledConfig.name).update(
        text_value="false"
    )
    evidence_before = EvidenceEvent.objects.count()

    read_response = get_debug_session_with_context(
        context,
        {"session_id": str(session.id)},
        resolver=resolver,
    )

    response = control_debug_session_with_context(
        context,
        _control_request(session, "set_context_var", key="${safe}", value="value"),
        resolver=resolver,
    )

    assert read_response["ok"] is True
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    assert EvidenceEvent.objects.count() == evidence_before
