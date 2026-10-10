"""Agent recovery hints must preserve barriers, authority and evidence boundaries."""

import datetime

import pytest

from bkflow.apigw.views.harness.common import _safe_domain_result
from bkflow.harness.constants import DebugSessionStatus, HarnessRunStatus
from bkflow.harness.models import EvidenceEvent, HarnessIdempotencyRecord
from bkflow.harness.services.debug.adapter import DebugAdapter
from bkflow.harness.services.debug.facade import (
    control_debug_session_with_context,
    get_debug_session_with_context,
    run_debug_with_context,
    start_debug_session_with_context,
)
from bkflow.template.models import DebugContext, DebugNodeState
from tests.interface.harness.debug.test_context_pages import _view
from tests.interface.harness.debug.test_control_session import _control_request
from tests.interface.harness.debug.test_get_session import _get_request, _started
from tests.interface.harness.debug.test_run_debug import _step_request

pytest_plugins = ("tests.interface.harness.debug.test_start_session",)


@pytest.mark.django_db
@pytest.mark.parametrize("tool", ["run_debug", "control_debug_session"])
def test_pending_write_tells_agent_to_read_without_releasing_barrier(start_case, tool):
    """不确定写入阻挡后续写入，并提示回读而不是重新校验或更换幂等键。"""
    context, session, resolver = _started(start_case)
    barrier = HarnessIdempotencyRecord.objects.create(
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
    if tool == "run_debug":
        result = run_debug_with_context(context, _step_request(session), resolver=resolver)
    else:
        result = control_debug_session_with_context(
            context, _control_request(session, "set_context_var", key="${safe}", value="value"), resolver=resolver
        )
    result = _safe_domain_result(context, result, tool)
    assert result["errors"][0]["code"] == "DEBUG_OPERATION_IN_FLIGHT"
    assert result["errors"][0]["retryable"] is False
    assert result["next_actions"] == ["get_debug_session"]
    assert "validation" not in result["summary"].lower()
    barrier.refresh_from_db()
    assert barrier.status == "IN_FLIGHT"
    assert HarnessIdempotencyRecord.objects.filter(status="IN_FLIGHT").count() == 1
    assert DebugContext.objects.get(pk=session.debug_context_id).global_vars == {}


@pytest.mark.django_db
def test_expired_write_guides_read_then_allows_new_session(start_case, monkeypatch):
    """过期写入先回读收尾；不得提示在 Run 仍被占用时直接新建。"""
    context, session, resolver = _started(start_case)
    now = session.expires_at + datetime.timedelta(seconds=1)
    monkeypatch.setattr("bkflow.harness.services.debug.control.timezone.now", lambda: now)
    response = control_debug_session_with_context(
        context, _control_request(session, "set_context_var", key="${safe}", value="value"), resolver=resolver
    )
    public = _safe_domain_result(context, response, "control_debug_session")
    assert public["errors"][0]["code"] == "DEBUG_SESSION"
    assert public["next_actions"] == ["get_debug_session"]
    assert get_debug_session_with_context(context, _get_request(session), resolver=resolver)["ok"]
    session.refresh_from_db()
    session.run.refresh_from_db()
    assert session.status == DebugSessionStatus.EXPIRED
    assert session.run.status == HarnessRunStatus.DRAFT_READY
    request = {**start_case[4], "idempotency_key": "start-after-expiry"}
    assert start_debug_session_with_context(context, request, resolver=resolver)["ok"]


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["step", "set_node_mock", "reset"])
def test_unknown_node_is_rejected_before_dispatch_and_can_be_corrected(start_case, action):
    """错误节点定位不能派发调试、留下运行证据，或污染可重试的请求记录。"""
    context, session, resolver = _started(start_case)
    if action == "step":
        call = run_debug_with_context
        request = _step_request(session, node_id="not_in_this_workflow")
        tool = "run_debug"
    else:
        call = control_debug_session_with_context
        tool = "control_debug_session"
        fields = (
            {"node_ids": ["A", "not_in_this_workflow"]}
            if action == "reset"
            else {
                "node_id": "not_in_this_workflow",
                "enabled": True,
                "mock_result": "success",
                "mock_outputs": {},
                "mock_error": "",
            }
        )
        request = _control_request(session, action, **fields)
    before = EvidenceEvent.objects.count()
    result = _safe_domain_result(context, call(context, request, resolver=resolver), tool)
    assert result["errors"][0]["code"] == "DEBUG_NODE_NOT_FOUND"
    assert result["errors"][0]["path"] == ("node_ids" if action == "reset" else "node_id")
    assert result["next_actions"] == ["get_debug_session"]
    assert EvidenceEvent.objects.count() == before
    assert not HarnessIdempotencyRecord.objects.filter(status="IN_FLIGHT").exists()
    assert set(
        DebugNodeState.objects.filter(debug_context_id=session.debug_context_id).values_list("status", flat=True)
    ) == {"not_run"}
    request.update({"node_ids": ["A"]} if action == "reset" else {"node_id": "A"})
    request["idempotency_key"] += "-corrected"
    assert call(context, request, resolver=resolver)["ok"]


@pytest.mark.django_db
def test_terminal_pages_end_polling_but_keep_history_pagination_independent(start_case, monkeypatch):
    """终态不再轮询 Engine；两套分页均结束后停止查询，不把读完等同业务通过。"""
    context, session, resolver = _started(start_case, mode="global")
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    view = _view()
    for node in view["nodes"]:
        node["error_detail"] = ""
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: view)
    payload = _get_request(session, node_limit=20, limit=1)
    first = _safe_domain_result(
        context, get_debug_session_with_context(context, payload, resolver=resolver), "get_debug_session"
    )
    artifact = first["artifact_refs"][0]
    assert artifact["read_guidance"]["context_source"] == "context_page"
    assert artifact["read_guidance"]["poll_required"] is False
    assert artifact["read_guidance"]["node_query"] == "all_nodes"
    assert artifact["read_guidance"]["node_page_has_more"] is True
    assert artifact["read_guidance"]["history_has_more"] is True
    assert first["next_actions"] == ["get_debug_session"]
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: pytest.fail("no live terminal read"))
    payload["node_cursor"] = artifact["context_page"]["next_cursor"]
    second = get_debug_session_with_context(context, payload, resolver=resolver)
    assert second["artifact_refs"][0]["read_guidance"]["node_page_has_more"] is False
    assert second["next_actions"] == ["get_debug_session"]  # History remains unread.
    payload.update(cursor=artifact["history"]["next_cursor"], limit=100)
    last = get_debug_session_with_context(context, payload, resolver=resolver)
    assert last["next_actions"] == []
    assert last["artifact_refs"][0]["read_guidance"]["history_has_more"] is False
    assert last["artifact_refs"][0]["context"] == {"available": False, "reason": "session_terminal"}
    single = get_debug_session_with_context(
        context, _get_request(session, node_id="node_25", limit=100), resolver=resolver
    )
    assert single["artifact_refs"][0]["read_guidance"]["node_query"] == "single_node"
    assert single["artifact_refs"][0]["read_guidance"]["context_source"] == "context_page"


@pytest.mark.django_db
def test_terminal_without_snapshot_reports_unavailable_not_passed(start_case):
    """无终态快照的旧会话明确缺证据，不反复轮询也不借用新画布状态。"""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.TERMINATED
    session.save(update_fields=["status"])
    result = get_debug_session_with_context(context, _get_request(session, limit=100), resolver=resolver)
    artifact = result["artifact_refs"][0]
    assert "context_page" not in artifact
    assert artifact["read_guidance"]["context_source"] == "unavailable"
    assert artifact["read_guidance"]["poll_required"] is False
    assert result["next_actions"] == []


@pytest.mark.django_db
def test_debug_infrastructure_log_identifies_failure_without_raw_exception(start_case, monkeypatch, caplog):
    """Facade 吞掉的基础设施错误仍能定位类型，但日志和返回均不得回显秘密。"""
    from django.db import DatabaseError

    context, session, resolver = _started(start_case)

    def fail_context(*args, **kwargs):
        raise DatabaseError("password=fixture-private-marker")

    monkeypatch.setattr(DebugAdapter, "context_view", fail_context)
    result = get_debug_session_with_context(context, _get_request(session), resolver=resolver)
    assert result["errors"][0]["code"] == "RETRYABLE_INFRA"
    failures = [r.harness_failure for r in caplog.records if hasattr(r, "harness_failure")]
    assert failures == [
        {"tool": "get_debug_session", "correlation": context.correlation_id, "exception_type": "DatabaseError"}
    ]
    assert "fixture-private-marker" not in str(result) + caplog.text + str(failures)
