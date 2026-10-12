"""Characterization contracts for the Harness debug adapter."""

from unittest.mock import patch

import pytest

from bkflow.harness.services.debug.adapter import DebugAdapter
from bkflow.template.models import DebugContext, DebugNodeState, TemplateMockScheme

PIPELINE_TREE = {
    "activities": {
        "A": {
            "id": "A",
            "type": "ServiceActivity",
            "component": {"code": "test", "data": {}},
        },
        "B": {
            "id": "B",
            "type": "ServiceActivity",
            "component": {"code": "test", "data": {"value": {"hook": True, "value": "${result}"}}},
        },
    },
    "flows": {"f1": {"id": "f1", "source": "A", "target": "B"}},
    "gateways": {},
    "constants": {
        "${input}": {
            "key": "${input}",
            "name": "Input",
            "show_type": "show",
            "value": "safe-default",
            "source_type": "custom",
            "custom_type": "input",
            "source_info": {},
        },
        "${result}": {
            "key": "${result}",
            "name": "Result",
            "show_type": "hide",
            "value": "",
            "source_type": "component_outputs",
            "custom_type": "",
            "source_info": {"A": ["result"]},
        },
    },
}


@pytest.mark.django_db
def test_adapter_translates_existing_debug_service_without_running_a_task():
    """Changing DebugService context/schema/fingerprint translation must break this contract."""
    snapshot = DebugAdapter(template_id=42, space_id=902, pipeline_tree=PIPELINE_TREE).prepare()

    assert snapshot.debug_context_id == DebugContext.objects.get(template_id=42).id
    assert snapshot.input_schema == [
        {"key": "${input}", "name": "Input", "type": "input", "default": "safe-default", "required": True}
    ]
    assert snapshot.node_readiness == [
        {
            "node_id": "A",
            "node_type": "ServiceActivity",
            "execution_mode": "real",
            "status": "not_run",
            "supports_step": True,
            "supports_mock": True,
            "can_step": True,
            "missing_vars": [],
        },
        {
            "node_id": "B",
            "node_type": "ServiceActivity",
            "execution_mode": "real",
            "status": "not_run",
            "supports_step": True,
            "supports_mock": True,
            "can_step": False,
            "missing_vars": [{"key": "${result}", "source_node_id": "A"}],
        },
    ]
    assert snapshot.tree_fingerprint == {
        "nodes": {"A": "44b87023b7859e9ff60e8beeea44e77c", "B": "7c4ddb5916d7eb7715ce12eda8524fda"},
        "flows": "e9653ef88335c0af23bb5ddf27ba8902",
        "gateways": "99914b932bd37a50b983c5e7c90ae93b",
        "constants": "ce58b19b9e497f80cc9066a62bdd0d4c",
    }
    context = DebugContext.objects.get(template_id=42)
    assert context.active_task_id is None
    assert context.status == "idle"
    assert set(DebugNodeState.objects.filter(debug_context=context).values_list("node_id", flat=True)) == {"A", "B"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "context_values",
    [
        {"status": "running"},
        {"status": "idle", "active_task_id": 991},
    ],
)
def test_adapter_rejects_busy_canvas_context_before_building_remote_backed_view(context_values):
    """A running canvas debug must not be adopted or queried by a new Harness session."""
    DebugContext.objects.create(template_id=42, space_id=902, **context_values)

    with patch(
        "bkflow.harness.services.debug.adapter.DebugService.build_context_view",
        side_effect=AssertionError("context view must not run for a busy context"),
    ):
        with pytest.raises(RuntimeError, match="Debug context is busy"):
            DebugAdapter(template_id=42, space_id=902, pipeline_tree=PIPELINE_TREE).prepare()


@pytest.mark.django_db
def test_prepare_replaces_shared_canvas_residue_with_a_clean_session_baseline():
    """A new Harness session cannot inherit a previous user's runtime or Mock state."""
    context = DebugContext.objects.create(
        template_id=42,
        space_id=902,
        global_vars={"${old}": "old-output"},
        tree_fingerprint={"old": True},
        status="idle",
        last_task_id=7001,
        last_run_type="global",
        last_run_status="failed",
        last_error_detail={"message": "old failure"},
        last_inputs={"${old}": "old-input"},
        locked_by="previous-user",
        locked_at=None,
    )
    DebugNodeState.objects.create(
        debug_context=context,
        node_id="A",
        execution_mode="mock",
        mock_result="success",
        mock_outputs={"result": "old-mock"},
        status="finished",
        inputs={"old": True},
        outputs={"result": "old-output"},
        error_detail={"message": "old failure"},
    )
    TemplateMockScheme.objects.create(
        space_id=902,
        template_id=42,
        data={"nodes": ["B"]},
    )

    snapshot = DebugAdapter(template_id=42, space_id=902, pipeline_tree=PIPELINE_TREE).prepare()

    context.refresh_from_db()
    states = {state.node_id: state for state in DebugNodeState.objects.filter(debug_context=context)}
    assert context.global_vars == {}
    assert context.tree_fingerprint == {}
    assert context.last_inputs == {}
    assert context.last_task_id is None
    assert context.last_run_type == ""
    assert context.last_run_status == "not_run"
    assert context.last_error_detail == {}
    assert context.locked_by == ""
    assert context.locked_at is None
    assert states["A"].execution_mode == "real"
    assert states["A"].status == "not_run"
    assert states["A"].outputs == {}
    assert states["A"].mock_outputs == {}
    assert states["B"].execution_mode == "mock"
    assert [node["status"] for node in snapshot.node_readiness] == ["not_run", "not_run"]
