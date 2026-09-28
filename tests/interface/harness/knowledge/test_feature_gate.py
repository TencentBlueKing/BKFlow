"""Knowledge-search is separately gated without changing P0 availability."""

import pytest

from bkflow.harness.contracts import HarnessContextError, TrustedHarnessContext
from bkflow.harness.services.contract_versions import require_tool_enabled
from bkflow.space.configs import (
    HarnessKnowledgeRouterEnabledConfig,
    SpaceConfigValueType,
)
from bkflow.space.models import SpaceConfig


def trusted_context(contract_version):
    """Create a complete, trusted context for feature-gate behavior tests."""
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
        correlation_id="knowledge-feature-gate-test",
    )


@pytest.mark.django_db
def test_default_knowledge_flag_does_not_disable_p0_tools():
    """Absent P1 configuration keeps its default off while negotiated P0 stays callable."""
    context = trusted_context("1.0.0")

    assert SpaceConfig.get_config(context.space_id, HarnessKnowledgeRouterEnabledConfig.name) == "false"
    assert require_tool_enabled(context, "search_workflow_capabilities") is None


@pytest.mark.django_db
def test_enabled_knowledge_flag_does_not_grant_the_tool_to_contract_1_0():
    """An enabled space flag cannot bypass the negotiated contract membership check."""
    context = trusted_context("1.0.0")
    SpaceConfig.objects.create(
        space_id=context.space_id,
        name=HarnessKnowledgeRouterEnabledConfig.name,
        value_type=SpaceConfigValueType.TEXT.value,
        text_value="true",
    )

    assert SpaceConfig.get_config(context.space_id, HarnessKnowledgeRouterEnabledConfig.name) == "true"
    with pytest.raises(HarnessContextError) as error:
        require_tool_enabled(context, "search_workflow_knowledge")
    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"


@pytest.mark.django_db
def test_knowledge_search_requires_contract_1_1_and_an_enabled_space_flag():
    """A P1 tool becomes callable only after both its contract and space feature gate pass."""
    context = trusted_context("1.1.0")

    with pytest.raises(HarnessContextError) as error:
        require_tool_enabled(context, "search_workflow_knowledge")
    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"

    SpaceConfig.objects.create(
        space_id=context.space_id,
        name=HarnessKnowledgeRouterEnabledConfig.name,
        value_type=SpaceConfigValueType.TEXT.value,
        text_value="true",
    )

    assert require_tool_enabled(context, "search_workflow_knowledge") is None
