"""Fail-closed P3 publish, execution, and global-real feature gates."""

import pytest

from bkflow.harness.contracts import HarnessContextError, TrustedHarnessContext
from bkflow.harness.services import contract_versions
from bkflow.space.models import SpaceConfig

PUBLISH_WRITE_TOOLS = ("prepare_release", "publish_workflow")
EXECUTION_WRITE_TOOLS = ("start_workflow_execution", "control_workflow_execution")


def trusted_context():
    """Build a complete P3 context with no caller-controlled feature grants."""
    return TrustedHarnessContext(
        platform_key="bkaidev",
        platform_app="trusted-app",
        actor="trusted-user",
        space_id=904,
        scope_type="project",
        scope_value="904",
        target_environment="stag",
        policy_version="risk-2026.09",
        mcp_contract_version="1.3.0",
        correlation_id="p3-feature-gate-test",
    )


def set_flag(name, enabled):
    """Persist a canonical server-side text flag for one test space."""
    SpaceConfig.objects.update_or_create(
        space_id=904,
        name=name,
        defaults={"text_value": "true" if enabled else "false"},
    )


def helper(name):
    """Fail with the missing public policy surface rather than an import error."""
    value = getattr(contract_versions, name, None)
    assert value is not None
    return value


@pytest.mark.django_db
def test_all_p3_phase_switches_default_to_deny():
    """Absent publish, execution, and global-real flags cannot self-enable."""
    assert helper("is_harness_publish_enabled")(904) is False
    assert helper("is_harness_execution_enabled")(904) is False
    assert helper("is_harness_global_real_debug_enabled")(904) is False


@pytest.mark.django_db
@pytest.mark.parametrize("tool_name", PUBLISH_WRITE_TOOLS)
def test_publish_switch_denies_manifest_and_publish_writes_until_enabled(tool_name):
    """A negotiated P3 contract alone cannot mutate release state."""
    with pytest.raises(HarnessContextError) as error:
        contract_versions.require_tool_enabled(trusted_context(), tool_name)
    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"

    set_flag("harness_publish_enabled", True)
    assert contract_versions.require_tool_enabled(trusted_context(), tool_name) is None


@pytest.mark.django_db
@pytest.mark.parametrize("tool_name", EXECUTION_WRITE_TOOLS)
def test_execution_switch_denies_task_mutations_until_enabled(tool_name):
    """Start and control cannot inherit authority from publish enablement."""
    set_flag("harness_publish_enabled", True)
    with pytest.raises(HarnessContextError) as error:
        contract_versions.require_tool_enabled(trusted_context(), tool_name)
    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"

    set_flag("harness_execution_enabled", True)
    assert contract_versions.require_tool_enabled(trusted_context(), tool_name) is None


@pytest.mark.django_db
def test_execution_read_remains_available_after_runtime_switch_is_disabled():
    """Operators can read existing execution Evidence during freeze or rollback."""
    set_flag("harness_execution_enabled", False)

    assert contract_versions.require_tool_enabled(trusted_context(), "get_workflow_execution") is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "debug_enabled,real_enabled,global_enabled,expected",
    [
        (False, False, False, False),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
        (True, True, True, True),
    ],
)
def test_global_real_switch_requires_both_p2_parent_gates(
    debug_enabled,
    real_enabled,
    global_enabled,
    expected,
):
    """The P3 leaf flag cannot bypass the P2 debug and real-step parents."""
    set_flag("harness_debug_enabled", debug_enabled)
    set_flag("harness_real_step_enabled", real_enabled)
    set_flag("harness_global_real_enabled", global_enabled)

    assert helper("is_harness_global_real_debug_enabled")(904) is expected
