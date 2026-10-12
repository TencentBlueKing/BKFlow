"""Fault-injection proof for P2 secret non-disclosure and retry barriers."""

import logging

import pytest
from django.db import DatabaseError

from bkflow.harness.constants import DebugMode, DebugSessionStatus
from bkflow.harness.models import (
    DebugSession,
    EvidenceEvent,
    HarnessIdempotencyRecord,
    HarnessRun,
    TokenLease,
    WorkflowPlanRevision,
)
from bkflow.harness.services.debug.adapter import DebugAdapter
from bkflow.harness.services.debug.facade import (
    control_debug_session_with_context,
    get_debug_session_with_context,
    run_debug_with_context,
    start_debug_session_with_context,
)
from bkflow.harness.services.token_broker import TokenBroker
from bkflow.permission.models import Token
from bkflow.space.configs import HarnessDebugEnabledConfig, SpaceConfigValueType
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import DebugContext, DebugNodeState, TemplateSnapshot

pytest_plugins = ("tests.interface.harness.debug.test_start_session",)

ENGINE_SECRET = "FORBIDDEN_ENGINE_ACK_SECRET"
DOMAIN_SECRET = "FORBIDDEN_DOMAIN_RESULT_SENTINEL"


def _started(start_case, *, mode=DebugMode.STEP):
    context, _run, _revision, _template, request, resolver = start_case
    response = start_debug_session_with_context(context, {**request, "mode": mode}, resolver=resolver)
    assert response["ok"] is True
    return context, DebugSession.objects.get(), resolver


def _step_request(session, *, key):
    return {
        "session_id": str(session.id),
        "expected_plan_hash": session.plan_hash,
        "mode": "step",
        "execution_mode": "mock",
        "node_id": "A",
        "input_overrides": {},
        "mock_result": "success",
        "mock_outputs": {"result": "bounded"},
        "mock_error": "",
        "idempotency_key": key,
    }


def _global_request(session, *, key):
    return {
        "session_id": str(session.id),
        "expected_plan_hash": session.plan_hash,
        "mode": "global",
        "execution_mode": "mock",
        "inputs": {},
        "idempotency_key": key,
    }


def _enable_debug(context):
    SpaceConfig.objects.get_or_create(
        space_id=context.space_id,
        name=HarnessDebugEnabledConfig.name,
        defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": "true"},
    )


def _harness_database_projection():
    """Serialize only P2 Harness state; legacy Token plaintext is an explicit compatibility boundary."""
    return {
        "runs": list(HarnessRun.objects.values()),
        "revisions": list(WorkflowPlanRevision.objects.values()),
        "sessions": list(DebugSession._base_manager.values()),
        "leases": list(TokenLease._base_manager.values()),
        "idempotency": list(HarnessIdempotencyRecord.objects.values()),
        "evidence": list(EvidenceEvent._base_manager.values()),
        "debug_contexts": list(DebugContext.objects.values()),
        "debug_nodes": list(DebugNodeState.objects.values()),
        "template_snapshots": list(TemplateSnapshot.objects.values()),
    }


def _assert_absent(markers, *channels):
    rendered = "\n".join(str(channel) for channel in channels)
    for marker in markers:
        assert marker not in rendered


@pytest.mark.django_db(transaction=True)
def test_token_issue_then_lease_write_crash_rolls_back_and_never_discloses_secret(start_case, mocker, caplog):
    """Direct Broker rollback is complemented by real get/control Tool Envelopes."""
    caplog.set_level(logging.INFO)
    context, session, resolver = _started(start_case)
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="secret-gate-space",
    )
    mocker.patch("bkflow.permission.token_issuer.TokenResourceValidator.validate", return_value=None)

    from bkflow.harness.services import token_broker as broker_module

    issued_secrets = []
    real_issue = broker_module.issue_resource_token

    def recording_issue(*args, **kwargs):
        issued = real_issue(*args, **kwargs)
        issued_secrets.append(issued.secret)
        return issued

    mocker.patch.object(broker_module, "issue_resource_token", side_effect=recording_issue)
    real_save = TokenLease.save
    crashed = {"value": False}

    def fail_first_lease_save(lease, *args, **kwargs):
        if lease._state.adding and not crashed["value"]:
            crashed["value"] = True
            raise DatabaseError("lease persistence failed")
        return real_save(lease, *args, **kwargs)

    mocker.patch.object(TokenLease, "save", autospec=True, side_effect=fail_first_lease_save)

    with pytest.raises(DatabaseError) as captured:
        TokenBroker().acquire_debug_lease(context, session)

    assert Token.objects.count() == 0
    assert TokenLease._base_manager.count() == 0
    handle = TokenBroker().acquire_debug_lease(context, session)
    assert len(issued_secrets) == 2
    assert Token.objects.count() == 1
    assert TokenLease._base_manager.count() == 1
    assert handle.secret == issued_secrets[-1]
    _enable_debug(context)
    read_response = get_debug_session_with_context(
        context,
        {"session_id": str(session.id), "limit": 20},
        resolver=resolver,
    )
    control_response = control_debug_session_with_context(
        context,
        {
            "session_id": str(session.id),
            "expected_plan_hash": session.plan_hash,
            "action": "terminate",
            "idempotency_key": "secret-token-control-envelope",
        },
        resolver=resolver,
    )
    assert read_response["ok"] is True
    assert control_response["ok"] is True
    _assert_absent(
        issued_secrets,
        repr(handle),
        read_response,
        control_response,
        _harness_database_projection(),
        caplog.text,
        captured.value,
    )


@pytest.mark.django_db(transaction=True)
def test_engine_ack_then_session_write_crash_is_barriered_for_same_and_new_keys(start_case, mocker, caplog):
    """An acknowledged Engine task is never dispatched twice after local state becomes uncertain."""
    caplog.set_level(logging.INFO)
    context, session, resolver = _started(start_case, mode=DebugMode.GLOBAL)
    task_client = mocker.MagicMock()
    task_client.create_task.return_value = {
        "result": True,
        "data": {"id": 7601},
        "message": ENGINE_SECRET,
    }
    task_client.operate_task.return_value = {"result": True, "message": ENGINE_SECRET}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=task_client)
    real_save = DebugSession.save
    crashed = {"value": False}

    def fail_running_session_save(current, *args, **kwargs):
        if current.status == DebugSessionStatus.RUNNING and not crashed["value"]:
            crashed["value"] = True
            raise DatabaseError("session persistence failed")
        return real_save(current, *args, **kwargs)

    mocker.patch.object(DebugSession, "save", autospec=True, side_effect=fail_running_session_save)
    request = _global_request(session, key="engine-ack-crash")

    first = run_debug_with_context(context, request, resolver=resolver)
    same_key = run_debug_with_context(context, request, resolver=resolver)
    new_key = run_debug_with_context(
        context,
        {**request, "idempotency_key": "engine-ack-crash-new-key"},
        resolver=resolver,
    )

    assert first["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert same_key["errors"][0]["code"] == new_key["errors"][0]["code"] == "DEBUG_OPERATION_IN_FLIGHT"
    assert task_client.create_task.call_count == 1
    assert task_client.operate_task.call_count == 1
    barrier = HarnessIdempotencyRecord.objects.get(tool_name="run_debug")
    assert barrier.status == "IN_FLIGHT"
    assert barrier.resource_reference == str(session.id)
    session.refresh_from_db()
    assert session.status == DebugSessionStatus.ACTIVE
    assert not EvidenceEvent.objects.filter(action="run_debug").exists()
    _assert_absent(
        [ENGINE_SECRET],
        first,
        same_key,
        new_key,
        _harness_database_projection(),
        caplog.text,
    )


@pytest.mark.django_db(transaction=True)
def test_domain_completion_then_idempotency_crash_rolls_back_and_never_redispatches(start_case, mocker, caplog):
    """A post-domain completion failure keeps one session-scoped in-flight dispatch barrier."""
    caplog.set_level(logging.INFO)
    context, session, resolver = _started(start_case)

    class SecretResultAdapter(DebugAdapter):
        calls = 0
        saw_secret = False

        def run_step(self, *args, **kwargs):
            type(self).calls += 1
            type(self).saw_secret = True
            return {
                "status": "finished",
                "task_id": None,
                "outputs": {"password": DOMAIN_SECRET},
                "updated_global_vars": {"auth": DOMAIN_SECRET},
                "error_detail": {},
            }

    completion_error = DatabaseError("idempotency completion failed")
    mocker.patch("bkflow.harness.services.debug.run.complete_idempotency", side_effect=completion_error)
    request = _step_request(session, key="domain-complete-crash")

    first = run_debug_with_context(context, request, resolver=resolver, adapter_class=SecretResultAdapter)
    same_key = run_debug_with_context(context, request, resolver=resolver, adapter_class=SecretResultAdapter)
    new_key = run_debug_with_context(
        context,
        {**request, "idempotency_key": "domain-complete-crash-new-key"},
        resolver=resolver,
        adapter_class=SecretResultAdapter,
    )

    assert first["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert same_key["errors"][0]["code"] == new_key["errors"][0]["code"] == "DEBUG_OPERATION_IN_FLIGHT"
    assert SecretResultAdapter.calls == 1
    assert SecretResultAdapter.saw_secret is True
    barrier = HarnessIdempotencyRecord.objects.get(tool_name="run_debug")
    assert barrier.status == "IN_FLIGHT"
    assert barrier.response_snapshot == {}
    session.refresh_from_db()
    assert session.status == DebugSessionStatus.ACTIVE
    assert DebugContext.objects.get(pk=session.debug_context_id).global_vars == {}
    assert not EvidenceEvent.objects.filter(action="run_debug").exists()
    _assert_absent(
        [DOMAIN_SECRET],
        first,
        same_key,
        new_key,
        _harness_database_projection(),
        caplog.text,
        completion_error,
    )
