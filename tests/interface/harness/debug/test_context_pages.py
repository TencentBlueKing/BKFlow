"""Large debug views remain inspectable without increasing evidence budgets."""

import json
from dataclasses import replace

import pytest
from django.db import DatabaseError

from bkflow.apigw.views.harness.common import _safe_domain_result
from bkflow.harness.constants import DebugContextEvidenceType, DebugSessionStatus
from bkflow.harness.models import EvidenceEvent
from bkflow.harness.services.debug.adapter import DebugAdapter
from bkflow.harness.services.debug.facade import get_debug_session_with_context
from tests.interface.harness.debug.test_get_session import _get_request, _started

pytest_plugins = ("tests.interface.harness.debug.test_start_session",)


def _view():
    return {
        "status": "idle",
        "active_task_id": None,
        "last_task_id": 7001,
        "last_run_type": "global",
        "last_run_status": "finished",
        "global_vars": {"password": "do-not-return-this"},
        "nodes": [
            {
                "node_id": "node_{:02d}".format(i),
                "status": "finished",
                "node_type": "ServiceActivity",
                "error_detail": "公开诊断" * 60,
            }
            for i in range(26)
        ],
    }


@pytest.mark.django_db
def test_large_context_is_paginated_and_redacted(start_case, monkeypatch):
    context, session, resolver = _started(start_case)
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: _view())
    seen = []
    cursor = None
    while True:
        payload = _get_request(session, node_limit=5, **({"node_cursor": cursor} if cursor else {}))
        response = get_debug_session_with_context(context, payload, resolver=resolver)
        assert response["ok"] is True, response["errors"]
        assert _safe_domain_result(context, response, "get_debug_session")["ok"] is True
        page = response["artifact_refs"][0]["context_page"]
        assert page["summary"]["total_nodes"] == 26
        assert page["summary"]["status_counts"]["finished"] == 26
        assert len(json.dumps(page, ensure_ascii=False).encode()) <= 8192
        assert "do-not-return-this" not in str(response)
        seen.extend(item["node_id"] for item in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == ["node_{:02d}".format(i) for i in range(26)]


@pytest.mark.django_db
def test_terminal_pages_use_session_snapshot_not_new_template_context(start_case, monkeypatch):
    context, session, resolver = _started(start_case, mode="global")
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: _view())
    first = get_debug_session_with_context(context, _get_request(session, node_limit=3), resolver=resolver)
    assert first["ok"] is True, first["errors"]
    cursor = first["artifact_refs"][0]["context_page"]["next_cursor"]
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: pytest.fail("must not read live context"))
    second = get_debug_session_with_context(
        context, _get_request(session, node_limit=3, node_cursor=cursor), resolver=resolver
    )
    assert second["ok"] is True, second["errors"]
    assert second["artifact_refs"][0]["context_page"]["items"][0]["node_id"] == "node_03"
    single = get_debug_session_with_context(context, _get_request(session, node_id="node_25"), resolver=resolver)
    assert [item["node_id"] for item in single["artifact_refs"][0]["context_page"]["items"]] == ["node_25"]
    denied = get_debug_session_with_context(replace(context, actor="other"), _get_request(session), resolver=resolver)
    assert denied["ok"] is False
    assert "node_25" not in str(denied)
    assert (
        EvidenceEvent.objects.filter(debug_session=session, event_type=DebugContextEvidenceType.SNAPSHOT).count() == 1
    )


@pytest.mark.django_db
def test_snapshot_storage_failure_rolls_back_partial_evidence_and_transition(start_case, monkeypatch):
    from bkflow.harness.services.debug import projection
    from bkflow.harness.services.token_broker import TokenBroker

    context, session, resolver = _started(start_case, mode="global")
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: _view())
    monkeypatch.setattr(TokenBroker, "revoke_active_leases", lambda *args: pytest.fail("snapshot must commit first"))
    write = projection.record_evidence

    def fail_node_chunk(**kwargs):
        if kwargs["event_type"] == DebugContextEvidenceType.NODES:
            raise DatabaseError("test-only write failure")
        return write(**kwargs)

    monkeypatch.setattr(projection, "record_evidence", fail_node_chunk)
    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    session.refresh_from_db()
    assert session.status == DebugSessionStatus.RUNNING
    assert session.current_task_id == 7001
    assert not EvidenceEvent.objects.filter(
        debug_session=session, event_type__in=DebugContextEvidenceType.values
    ).exists()


@pytest.mark.django_db
def test_changed_context_rejects_old_cursor(start_case, monkeypatch):
    context, session, resolver = _started(start_case)
    view = _view()
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: view)
    first = get_debug_session_with_context(context, _get_request(session, node_limit=3), resolver=resolver)
    assert first["ok"] is True
    cursor = first["artifact_refs"][0]["context_page"]["next_cursor"]
    view["nodes"][0]["status"] = "failed"
    response = get_debug_session_with_context(context, _get_request(session, node_cursor=cursor), resolver=resolver)
    assert response["errors"][0]["code"] == "DEBUG_CONTEXT_CHANGED"


@pytest.mark.django_db
def test_stale_page_does_not_rollback_terminal_convergence(start_case, monkeypatch):
    context, session, resolver = _started(start_case, mode="global")
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    view = _view()
    view.update(active_task_id=7001, last_run_status="running")
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: view)
    first = get_debug_session_with_context(context, _get_request(session, node_limit=3), resolver=resolver)
    cursor = first["artifact_refs"][0]["context_page"]["next_cursor"]
    view.update(active_task_id=None, last_run_status="finished")
    response = get_debug_session_with_context(context, _get_request(session, node_cursor=cursor), resolver=resolver)
    assert response["errors"][0]["code"] == "DEBUG_CONTEXT_CHANGED"
    session.refresh_from_db()
    assert session.status == DebugSessionStatus.COMPLETED
    assert (
        EvidenceEvent.objects.filter(debug_session=session, event_type=DebugContextEvidenceType.SNAPSHOT).count() == 1
    )


def test_oversized_node_does_not_hide_other_node_results():
    from bkflow.harness.services.debug.policy import validate_get_request
    from bkflow.harness.services.debug.projection import (
        build_context_snapshot,
        context_page,
    )

    view = _view()
    view["nodes"][0]["mock_outputs"] = {"large": "x" * 20000, "password": "do-not-return-this"}
    snapshot = build_context_snapshot(view)
    assert snapshot["nodes"][0]["details_omitted"] is True
    assert snapshot["nodes"][0]["status"] == "finished"
    session_id = "00000000-0000-0000-0000-000000000001"
    page = context_page(session_id, snapshot, validate_get_request({"session_id": session_id, "node_id": "node_01"}))
    assert page["items"][0]["error_detail"] == "公开诊断" * 60
    assert "do-not-return-this" not in str(snapshot)


def test_summary_uses_all_engine_debug_node_states():
    from bkflow.harness.services.debug.projection import build_context_snapshot
    from bkflow.template.models import DebugNodeState

    statuses = [choice[0] for choice in DebugNodeState.STATUS_CHOICES]
    snapshot = build_context_snapshot({"nodes": [{"node_id": state, "status": state} for state in statuses]})
    assert snapshot["summary"]["status_counts"] == dict.fromkeys(statuses, 1)


@pytest.mark.django_db
def test_deep_legacy_context_cannot_block_safe_node_page(start_case, monkeypatch):
    context, session, resolver = _started(start_case)
    view = {
        "nodes": [
            {
                "node_id": "n1",
                "status": "finished",
                "mock_outputs": {"nested": {"nested": {"nested": {"nested": "result"}}}},
            }
        ]
    }
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: view)
    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)
    public = _safe_domain_result(context, response, "get_debug_session")
    assert public["ok"] is True, public["errors"]
    artifact = public["artifact_refs"][0]
    assert artifact["context"]["omitted"] is True
    assert artifact["context_page"]["items"][0]["details_omitted"] is True
    assert artifact["context_page"]["items"][0]["status"] == "finished"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "reserved",
    [
        {"type": "approval_request"},
        {"approval_request_id": "public-data"},
        {"traceback": "public-error"},
        {"providerDetail": "public-error"},
    ],
)
def test_reserved_detail_only_omits_local_node_or_metadata(start_case, monkeypatch, reserved):
    context, session, resolver = _started(start_case)
    view = _view()
    view["nodes"][0]["mock_outputs"] = reserved
    view["global_vars"] = reserved
    monkeypatch.setattr(DebugAdapter, "context_view", lambda *args, **kwargs: view)
    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)
    public = _safe_domain_result(context, response, "get_debug_session")
    assert public["ok"] is True, public["errors"]
    page = public["artifact_refs"][0]["context_page"]
    assert page["items"][0]["details_omitted"] is True
    assert page["items"][0]["status"] == "finished"
    assert page["items"][1]["status"] == "finished"
    assert page["metadata"]["omitted"] is True


@pytest.mark.parametrize(
    "extra",
    [
        {"node_limit": True},
        {"node_limit": "5"},
        {"node_limit": 21},
        {"node_limit": 0},
        {"node_cursor": "bad!"},
        {"node_id": ""},
        {"node_id": "node_01", "node_cursor": "abc"},
    ],
)
def test_invalid_node_page_arguments_are_rejected(extra):
    from bkflow.apigw.serializers.harness.debug import GetDebugSessionSerializer

    serializer = GetDebugSessionSerializer(data={"session_id": "00000000-0000-0000-0000-000000000001", **extra})
    assert not serializer.is_valid()


def test_cursor_cannot_be_reused_for_another_session():
    from bkflow.harness.services.debug.policy import (
        DebugStartRejected,
        validate_get_request,
    )
    from bkflow.harness.services.debug.projection import (
        build_context_snapshot,
        context_page,
    )

    first_id = "00000000-0000-0000-0000-000000000001"
    second_id = "00000000-0000-0000-0000-000000000002"
    snapshot = build_context_snapshot(_view())
    page = context_page(first_id, snapshot, validate_get_request({"session_id": first_id, "node_limit": 1}))
    with pytest.raises(DebugStartRejected) as rejected:
        context_page(
            second_id, snapshot, validate_get_request({"session_id": second_id, "node_cursor": page["next_cursor"]})
        )
    assert rejected.value.code == "DEBUG_CONTEXT_CHANGED"
