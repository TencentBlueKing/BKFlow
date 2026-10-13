"""Versioned Harness tool availability gates."""

from types import MappingProxyType
from typing import Mapping

from bkflow.harness.contracts import HarnessContextError
from bkflow.harness.services.facade import P0_TOOL_OPERATION_MAP
from bkflow.space.configs import (
    HarnessCandidatePromotionEnabledConfig,
    HarnessDebugEnabledConfig,
    HarnessExecutionEnabledConfig,
    HarnessFeedbackEnabledConfig,
    HarnessGlobalRealDebugEnabledConfig,
    HarnessKnowledgeRouterEnabledConfig,
    HarnessPublishEnabledConfig,
    HarnessRealStepEnabledConfig,
)
from bkflow.space.models import SpaceConfig

P1_KNOWLEDGE_TOOL_OPERATION_MAP = MappingProxyType(
    {
        "search_workflow_knowledge": "harness_search_workflow_knowledge",
    }
)
P2_DEBUG_TOOL_OPERATION_MAP = MappingProxyType(
    {
        "start_debug_session": "harness_start_debug_session",
        "run_debug": "harness_run_debug",
        "get_debug_session": "harness_get_debug_session",
        "control_debug_session": "harness_control_debug_session",
    }
)
P3_RELEASE_EXECUTION_TOOL_OPERATION_MAP = MappingProxyType(
    {
        "prepare_release": "harness_prepare_release",
        "publish_workflow": "harness_publish_workflow",
        "start_workflow_execution": "harness_start_workflow_execution",
        "get_workflow_execution": "harness_get_workflow_execution",
        "control_workflow_execution": "harness_control_workflow_execution",
    }
)
P4_FEEDBACK_TOOL_OPERATION_MAP = MappingProxyType(
    {
        "submit_generation_feedback": "harness_submit_generation_feedback",
    }
)
_MUTATING_DEBUG_TOOLS = frozenset(("start_debug_session", "run_debug", "control_debug_session"))
_MUTATING_PUBLISH_TOOLS = frozenset(("prepare_release", "publish_workflow"))
_MUTATING_EXECUTION_TOOLS = frozenset(("start_workflow_execution", "control_workflow_execution"))
_MUTATING_FEEDBACK_TOOLS = frozenset(("submit_generation_feedback",))

CONTRACT_TOOLSETS = MappingProxyType(
    {
        "1.0.0": MappingProxyType(dict(P0_TOOL_OPERATION_MAP)),
        "1.1.0": MappingProxyType(
            {
                **P0_TOOL_OPERATION_MAP,
                **P1_KNOWLEDGE_TOOL_OPERATION_MAP,
            }
        ),
        "1.2.0": MappingProxyType(
            {
                **P0_TOOL_OPERATION_MAP,
                **P1_KNOWLEDGE_TOOL_OPERATION_MAP,
                **P2_DEBUG_TOOL_OPERATION_MAP,
            }
        ),
        "1.3.0": MappingProxyType(
            {
                **P0_TOOL_OPERATION_MAP,
                **P1_KNOWLEDGE_TOOL_OPERATION_MAP,
                **P2_DEBUG_TOOL_OPERATION_MAP,
                **P3_RELEASE_EXECUTION_TOOL_OPERATION_MAP,
            }
        ),
        "1.4.0": MappingProxyType(
            {
                **P0_TOOL_OPERATION_MAP,
                **P1_KNOWLEDGE_TOOL_OPERATION_MAP,
                **P2_DEBUG_TOOL_OPERATION_MAP,
                **P3_RELEASE_EXECUTION_TOOL_OPERATION_MAP,
                **P4_FEEDBACK_TOOL_OPERATION_MAP,
            }
        ),
    }
)


def tools_for_contract(version: str) -> Mapping[str, str]:
    """Return the negotiated toolset, rejecting unknown contract versions."""
    if not isinstance(version, str) or version not in CONTRACT_TOOLSETS:
        raise HarnessContextError("HARNESS_TOOL_UNAVAILABLE")
    return CONTRACT_TOOLSETS[version]


def is_harness_real_step_enabled(space_id: int) -> bool:
    """Return the effective real-step switch, which requires the total debug gate."""
    return is_harness_debug_enabled(space_id) and (
        SpaceConfig.get_config(space_id, HarnessRealStepEnabledConfig.name) == "true"
    )


def is_harness_debug_enabled(space_id: int) -> bool:
    """Return the effective P2 debug runtime switch for read projections."""
    return SpaceConfig.get_config(space_id, HarnessDebugEnabledConfig.name) == "true"


def is_harness_publish_enabled(space_id: int) -> bool:
    """Return whether P3 release preparation and publication are enabled."""
    return SpaceConfig.get_config(space_id, HarnessPublishEnabledConfig.name) == "true"


def is_harness_execution_enabled(space_id: int) -> bool:
    """Return whether P3 workflow execution mutations are enabled."""
    return SpaceConfig.get_config(space_id, HarnessExecutionEnabledConfig.name) == "true"


def is_harness_global_real_debug_enabled(space_id: int) -> bool:
    """Return the effective global-real switch, including both P2 parent gates."""
    return is_harness_real_step_enabled(space_id) and (
        SpaceConfig.get_config(space_id, HarnessGlobalRealDebugEnabledConfig.name) == "true"
    )


def is_harness_feedback_enabled(space_id: int) -> bool:
    """Return whether a space may retain new P4 generation feedback."""
    return SpaceConfig.get_config(space_id, HarnessFeedbackEnabledConfig.name) == "true"


def is_harness_candidate_promotion_enabled(space_id: int) -> bool:
    """Return the independent Owner-only candidate promotion switch."""
    return SpaceConfig.get_config(space_id, HarnessCandidatePromotionEnabledConfig.name) == "true"


def require_tool_enabled(context, tool_name) -> None:
    """Fail closed unless the trusted context's contract and feature gates permit a tool."""
    if not isinstance(tool_name, str) or tool_name not in tools_for_contract(context.mcp_contract_version):
        raise HarnessContextError("HARNESS_TOOL_UNAVAILABLE")
    if (
        tool_name == "search_workflow_knowledge"
        and SpaceConfig.get_config(context.space_id, HarnessKnowledgeRouterEnabledConfig.name) != "true"
    ):
        raise HarnessContextError("HARNESS_TOOL_UNAVAILABLE")
    if tool_name in _MUTATING_DEBUG_TOOLS and not is_harness_debug_enabled(context.space_id):
        raise HarnessContextError("HARNESS_TOOL_UNAVAILABLE")
    if tool_name in _MUTATING_PUBLISH_TOOLS and not is_harness_publish_enabled(context.space_id):
        raise HarnessContextError("HARNESS_TOOL_UNAVAILABLE")
    if tool_name in _MUTATING_EXECUTION_TOOLS and not is_harness_execution_enabled(context.space_id):
        raise HarnessContextError("HARNESS_TOOL_UNAVAILABLE")
    if tool_name in _MUTATING_FEEDBACK_TOOLS and not is_harness_feedback_enabled(context.space_id):
        raise HarnessContextError("HARNESS_TOOL_UNAVAILABLE")
