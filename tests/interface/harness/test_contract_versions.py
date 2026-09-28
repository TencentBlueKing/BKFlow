"""Versioned Harness tool contracts fail closed outside declared capabilities."""

import pytest

from bkflow.harness.contracts import HarnessContextError, TrustedHarnessContext
from bkflow.harness.services import contract_versions
from bkflow.harness.services.contract_versions import (
    CONTRACT_TOOLSETS,
    P1_KNOWLEDGE_TOOL_OPERATION_MAP,
    P2_DEBUG_TOOL_OPERATION_MAP,
    require_tool_enabled,
    tools_for_contract,
)

P0_TOOLSET = (
    ("search_workflow_capabilities", "harness_search_workflow_capabilities"),
    ("get_plugin_schema", "harness_get_plugin_schema"),
    ("validate_workflow", "harness_validate_workflow"),
    ("create_workflow_draft", "harness_create_workflow_draft"),
)
P1_TOOLSET = P0_TOOLSET + (("search_workflow_knowledge", "harness_search_workflow_knowledge"),)
P2_DEBUG_TOOLSET = (
    ("start_debug_session", "harness_start_debug_session"),
    ("run_debug", "harness_run_debug"),
    ("get_debug_session", "harness_get_debug_session"),
    ("control_debug_session", "harness_control_debug_session"),
)
P3_RELEASE_EXECUTION_TOOLSET = (
    ("prepare_release", "harness_prepare_release"),
    ("publish_workflow", "harness_publish_workflow"),
    ("start_workflow_execution", "harness_start_workflow_execution"),
    ("get_workflow_execution", "harness_get_workflow_execution"),
    ("control_workflow_execution", "harness_control_workflow_execution"),
)
P4_FEEDBACK_TOOLSET = (("submit_generation_feedback", "harness_submit_generation_feedback"),)


def trusted_context(contract_version):
    """Create a complete trusted context without accepting model-controlled authority."""
    return TrustedHarnessContext(
        platform_key="bkaidev",
        platform_app="trusted-app",
        actor="trusted-user",
        space_id=902,
        scope_type="project",
        scope_value="902",
        target_environment="stag",
        policy_version="risk-2026.09",
        mcp_contract_version=contract_version,
        correlation_id="contract-version-test",
    )


def test_contract_1_0_keeps_exact_p0_toolset():
    """P0 clients retain the ordered set of four operations they already negotiated."""
    assert tuple(tools_for_contract("1.0.0").items()) == P0_TOOLSET


def test_contract_1_1_adds_only_knowledge_search():
    """P1 extends, rather than reorders or replaces, the P0 tool contract."""
    assert tuple(tools_for_contract("1.1.0").items()) == P1_TOOLSET


def test_contract_1_2_appends_exact_debug_toolset_in_order():
    """P2 appends exactly four debug operations after the byte-stable P1 prefix."""
    assert "1.2.0" in CONTRACT_TOOLSETS
    assert tuple(tools_for_contract("1.2.0").items()) == P1_TOOLSET + P2_DEBUG_TOOLSET


def test_contract_1_3_appends_exact_release_execution_toolset_after_byte_stable_p2_prefix():
    """P3 adds five operations without changing any previously negotiated item or order."""
    assert tuple(tools_for_contract("1.3.0").items()) == P1_TOOLSET + P2_DEBUG_TOOLSET + P3_RELEASE_EXECUTION_TOOLSET
    assert tuple(tools_for_contract("1.3.0").items())[: len(P1_TOOLSET + P2_DEBUG_TOOLSET)] == tuple(
        tools_for_contract("1.2.0").items()
    )


def test_contract_1_4_appends_only_feedback_after_byte_stable_p3_prefix():
    """P4 exposes one intake Tool without exposing Owner governance controls."""
    p3 = tuple(tools_for_contract("1.3.0").items())
    p4 = tuple(tools_for_contract("1.4.0").items())

    assert p4 == p3 + P4_FEEDBACK_TOOLSET
    assert len(p4) == 15
    assert set(dict(p4)) - set(dict(p3)) == {"submit_generation_feedback"}
    assert not {
        "review_improvement_candidate",
        "promote_improvement_candidate",
        "rollback_improvement_candidate",
    }.intersection(dict(p4))


@pytest.mark.parametrize("contract_version", ["1.0.0", "1.1.0", "1.2.0", "1.3.0", "1.4.0"])
def test_contract_toolset_cannot_be_mutated_by_a_caller(contract_version):
    """A caller-side assignment must not change later negotiation results for any session."""
    toolset = tools_for_contract(contract_version)

    with pytest.raises(TypeError):
        toolset["publish_workflow"] = "harness_publish_workflow"

    assert tools_for_contract(contract_version) is toolset


def test_contract_version_registry_cannot_be_mutated_by_a_caller():
    """Callers cannot inject a new contract version into the process-wide registry."""
    with pytest.raises(TypeError):
        CONTRACT_TOOLSETS["9.9.9"] = {}


@pytest.mark.parametrize(
    "operation_map",
    [P1_KNOWLEDGE_TOOL_OPERATION_MAP, P2_DEBUG_TOOL_OPERATION_MAP],
)
def test_extension_operation_maps_cannot_be_mutated_by_a_caller(operation_map):
    """Views and adapters cannot rewrite a shared P1/P2 operation binding."""
    with pytest.raises(TypeError):
        operation_map["publish_workflow"] = "harness_publish_workflow"


def test_p3_extension_operation_map_cannot_be_mutated_by_a_caller():
    """The shared release/runtime binding is immutable after process startup."""
    operation_map = getattr(contract_versions, "P3_RELEASE_EXECUTION_TOOL_OPERATION_MAP", None)
    assert operation_map is not None
    with pytest.raises(TypeError):
        operation_map["publish_workflow"] = "other_operation"


def test_p4_extension_operation_map_cannot_be_mutated_by_a_caller():
    """The single feedback binding is immutable after process startup."""
    operation_map = getattr(contract_versions, "P4_FEEDBACK_TOOL_OPERATION_MAP", None)
    assert operation_map is not None
    with pytest.raises(TypeError):
        operation_map["submit_generation_feedback"] = "other_operation"


def test_contract_1_0_rejects_the_p1_knowledge_tool():
    """A P0 context cannot invoke an operation absent from its negotiated contract."""
    with pytest.raises(HarnessContextError) as error:
        require_tool_enabled(trusted_context("1.0.0"), "search_workflow_knowledge")

    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"


@pytest.mark.parametrize("tool_name", dict(P2_DEBUG_TOOLSET))
def test_contract_1_1_rejects_p2_debug_tools(tool_name):
    """P1 contexts cannot gain debug access from a later server deployment."""
    with pytest.raises(HarnessContextError) as error:
        require_tool_enabled(trusted_context("1.1.0"), tool_name)

    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"


@pytest.mark.parametrize("contract_version", ["1.0.0", "1.1.0", "1.2.0"])
@pytest.mark.parametrize("tool_name", dict(P3_RELEASE_EXECUTION_TOOLSET))
def test_predecessor_contracts_reject_p3_release_execution_tools(contract_version, tool_name):
    """Deploying P3 cannot grant release or runtime operations to older clients."""
    with pytest.raises(HarnessContextError) as error:
        require_tool_enabled(trusted_context(contract_version), tool_name)

    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"


@pytest.mark.parametrize("contract_version", ["1.0.0", "1.1.0", "1.2.0", "1.3.0"])
def test_predecessor_contracts_reject_p4_feedback_tool(contract_version):
    """Deploying P4 never grants feedback intake to a predecessor contract."""
    with pytest.raises(HarnessContextError) as error:
        require_tool_enabled(trusted_context(contract_version), "submit_generation_feedback")

    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"


def test_unknown_contract_has_no_toolset():
    """A caller cannot obtain tools through an undeclared contract version."""
    with pytest.raises(HarnessContextError) as error:
        tools_for_contract("9.9.9")

    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"


@pytest.mark.parametrize(
    "contract_version,tool_name",
    [
        ("9.9.9", "search_workflow_capabilities"),
        ("1.1.0", "unknown_tool"),
    ],
)
def test_unknown_contract_or_tool_fails_closed(contract_version, tool_name):
    """Unrecognized capabilities cannot be granted by a permissive fallback."""
    with pytest.raises(HarnessContextError) as error:
        require_tool_enabled(trusted_context(contract_version), tool_name)

    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"
