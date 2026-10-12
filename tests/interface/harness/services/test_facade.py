"""Public P0 facade contract."""

from unittest.mock import Mock

from bkflow.harness.services.facade import (
    HARNESS_CONTRACT_VERSION,
    P0_ACTION_RISK,
    P0_TOOL_OPERATION_MAP,
    P1_ACTION_RISK,
    P2_ACTION_RISK,
    P3_ACTION_RISK,
    P4_ACTION_RISK,
    HarnessFacade,
)
from bkflow.harness.services.resolver import CapabilityResolutionError


def test_p0_contract_stays_exact_while_p1_through_p4_add_versioned_facade_methods():
    """Later contracts add only their frozen methods without changing the P0 maps."""
    assert HARNESS_CONTRACT_VERSION == "1.0.0"
    assert P0_TOOL_OPERATION_MAP == {
        "search_workflow_capabilities": "harness_search_workflow_capabilities",
        "get_plugin_schema": "harness_get_plugin_schema",
        "validate_workflow": "harness_validate_workflow",
        "create_workflow_draft": "harness_create_workflow_draft",
    }
    assert P0_ACTION_RISK == {
        "search_workflow_capabilities": "L0",
        "get_plugin_schema": "L0",
        "validate_workflow": "L0",
        "create_workflow_draft": "L1",
    }
    assert P1_ACTION_RISK == {"search_workflow_knowledge": "L0"}
    assert P2_ACTION_RISK == {
        "start_debug_session": "L1",
        "run_debug": "L2",
        "get_debug_session": "L0",
        "control_debug_session": "L1",
    }
    assert P3_ACTION_RISK == {
        "prepare_release": "L0",
        "publish_workflow": "L2",
        "start_workflow_execution": "L2",
        "get_workflow_execution": "L0",
        "control_workflow_execution": "L3",
    }
    assert P4_ACTION_RISK == {"submit_generation_feedback": "L0"}
    assert {name for name in HarnessFacade.__dict__ if not name.startswith("_")} == set(P0_TOOL_OPERATION_MAP) | set(
        P1_ACTION_RISK
    ) | set(P2_ACTION_RISK) | set(P3_ACTION_RISK) | set(P4_ACTION_RISK)


def test_direct_schema_facade_failure_is_a_complete_frozen_error_entry(monkeypatch):
    """Direct Facade callers receive the same complete read-failure contract as APIGW callers."""
    context = Mock(space_id=1, actor="trusted-user", correlation_id="trace")
    service = Mock()
    monkeypatch.setattr(HarnessFacade, "_service", Mock(return_value=service))
    monkeypatch.setattr(
        "bkflow.harness.services.facade.CapabilityResolver.resolve",
        Mock(side_effect=CapabilityResolutionError("CAPABILITY_NOT_FOUND")),
    )

    result = HarnessFacade().get_plugin_schema(
        context, {"capability_ref": "cap_v1_missing", "expected_schema_hash": "a" * 64}
    )

    assert result["ok"] is False
    assert set(result["errors"][0]) == {
        "category",
        "code",
        "path",
        "repairable",
        "retryable",
        "message",
        "suggested_action",
    }
    assert result["errors"][0]["code"] == "CAPABILITY_NOT_FOUND"
    assert "provider detail" not in str(result)
