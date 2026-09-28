"""P2 debug contract, state, and fail-closed feature-gate tests."""

from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory

import bkflow.harness.constants as harness_constants
from bkflow.harness.contracts import HarnessContextError, TrustedHarnessContext
from bkflow.harness.services import contract_versions
from bkflow.space.configs import (
    HarnessDebugEnabledConfig,
    HarnessDeploymentConfig,
    SpaceConfigValueType,
)
from bkflow.space.models import Space, SpaceConfig

MUTATING_DEBUG_TOOLS = ("start_debug_session", "run_debug", "control_debug_session")


def trusted_context(contract_version="1.2.0"):
    return TrustedHarnessContext(
        platform_key="bkaidev",
        platform_app="trusted-app",
        actor="trusted-user",
        space_id=903,
        scope_type="project",
        scope_value="903",
        target_environment="stag",
        policy_version="risk-2026.09",
        mcp_contract_version=contract_version,
        correlation_id="debug-feature-gate-test",
    )


def set_flag(name, enabled):
    SpaceConfig.objects.update_or_create(
        space_id=903,
        name=name,
        defaults={"text_value": "true" if enabled else "false"},
    )


def context_from_persisted_deployment(contract_version):
    """Build authority through the real space binding and authenticated request path."""
    space = Space.objects.create(
        name="P2 trusted contract {}".format(contract_version),
        app_code="trusted-p2-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name=HarnessDeploymentConfig.name,
        value_type=SpaceConfigValueType.JSON.value,
        json_value={
            "platform_key": "bkaidev",
            "allowed_scope_types": ["biz", "project"],
            "scope_type": "project",
            "scope_value": "p2-project",
            "target_environment": "stag",
            "risk_policy_version": "risk-2026.09",
            "mcp_contract_version": contract_version,
        },
    )
    request = APIRequestFactory().post("/api/harness/debug/", {}, format="json")
    request.app = SimpleNamespace(bk_app_code=space.app_code, verified=True)
    request.user = SimpleNamespace(username="real-p2-actor", is_authenticated=True)
    request.trace_id = "p2-trusted-contract-test"
    return space, TrustedHarnessContext.from_request(request, space_id=space.id)


@pytest.mark.django_db
def test_persisted_contract_1_2_reaches_debug_feature_gate_through_trusted_context():
    """The deployable P2 binding reaches mutating Tools while disabled sessions stay readable."""
    space, context = context_from_persisted_deployment("1.2.0")
    SpaceConfig.objects.create(
        space_id=space.id,
        name=HarnessDebugEnabledConfig.name,
        value_type=SpaceConfigValueType.TEXT.value,
        text_value="true",
    )

    assert context.platform_key == "bkaidev"
    assert context.platform_app == "trusted-p2-app"
    assert context.actor == "real-p2-actor"
    assert context.space_id == space.id
    assert context.scope_type == "project"
    assert context.scope_value == "p2-project"
    assert context.target_environment == "stag"
    assert context.policy_version == "risk-2026.09"
    assert context.mcp_contract_version == "1.2.0"
    for tool_name in MUTATING_DEBUG_TOOLS:
        assert contract_versions.require_tool_enabled(context, tool_name) is None

    SpaceConfig.objects.filter(space_id=space.id, name=HarnessDebugEnabledConfig.name).update(text_value="false")
    assert contract_versions.require_tool_enabled(context, "get_debug_session") is None


@pytest.mark.django_db
@pytest.mark.parametrize("contract_version", ["1.0.0", "1.1.0"])
def test_persisted_predecessor_contracts_remain_compatible(contract_version):
    """The same trusted binding path keeps negotiated P0/P1 calls reachable."""
    _, context = context_from_persisted_deployment(contract_version)

    assert context.mcp_contract_version == contract_version
    assert contract_versions.require_tool_enabled(context, "search_workflow_capabilities") is None


@pytest.mark.django_db
@pytest.mark.parametrize("contract_version", ["9.9.9"])
def test_persisted_unknown_contracts_still_fail_closed(contract_version):
    """Persisting an undeclared contract cannot bypass deployment revalidation."""
    with pytest.raises(HarnessContextError) as error:
        context_from_persisted_deployment(contract_version)

    assert error.value.code == "HARNESS_DEPLOYMENT_INVALID"


@pytest.mark.django_db
def test_persisted_contract_1_3_builds_the_same_server_owned_authority_dimensions():
    """A P3 deployment is admitted without moving identity into the request body."""
    space, context = context_from_persisted_deployment("1.3.0")

    assert context.platform_app == space.app_code
    assert context.actor == "real-p2-actor"
    assert context.space_id == space.id
    assert context.scope_type == "project"
    assert context.scope_value == "p2-project"
    assert context.target_environment == "stag"
    assert context.mcp_contract_version == "1.3.0"


@pytest.mark.django_db
@pytest.mark.parametrize("tool_name", MUTATING_DEBUG_TOOLS)
def test_debug_switch_defaults_to_deny_mutating_debug_tools(tool_name):
    """An absent space flag fails closed for every operation that mutates debug state."""
    with pytest.raises(HarnessContextError) as error:
        contract_versions.require_tool_enabled(trusted_context(), tool_name)

    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"


@pytest.mark.django_db
def test_debug_switch_does_not_hide_existing_read_only_evidence():
    """P2 clients can read an existing session after administrators disable new debug work."""
    set_flag("harness_debug_enabled", False)

    assert contract_versions.require_tool_enabled(trusted_context(), "get_debug_session") is None


@pytest.mark.django_db
@pytest.mark.parametrize("tool_name", MUTATING_DEBUG_TOOLS + ("get_debug_session",))
def test_debug_switch_enables_all_p2_tools_without_granting_real_step(tool_name):
    """The total switch exposes P2 control calls; the real-step policy stays separate."""
    set_flag("harness_debug_enabled", True)
    set_flag("harness_real_step_enabled", False)

    assert contract_versions.require_tool_enabled(trusted_context(), tool_name) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "debug_enabled,real_step_enabled,expected",
    [
        (False, False, False),
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
def test_real_step_effective_enable_requires_both_space_flags(debug_enabled, real_step_enabled, expected):
    """A real step is effective only inside an explicitly enabled debug space."""
    helper = getattr(contract_versions, "is_harness_real_step_enabled", None)
    assert helper is not None
    set_flag("harness_debug_enabled", debug_enabled)
    set_flag("harness_real_step_enabled", real_step_enabled)

    assert helper(903) is expected


@pytest.mark.django_db
def test_read_only_debug_tool_still_requires_the_p2_contract():
    """Read-only behavior does not let older contracts invoke an undeclared Tool."""
    set_flag("harness_debug_enabled", True)

    with pytest.raises(HarnessContextError) as error:
        contract_versions.require_tool_enabled(trusted_context("1.1.0"), "get_debug_session")

    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"


def test_p3_lifecycle_choices_append_exact_values_without_rewriting_p0_or_p2_states():
    """Persisted P0/P2 values remain an exact prefix while P3 appends its lifecycle states."""
    assert list(harness_constants.HarnessRunStatus.values) == [
        "INTENT_CAPTURED",
        "PLANNING",
        "VALIDATING",
        "NEEDS_REPAIR",
        "DRAFT_READY",
        "DEBUGGING",
        "RELEASE_READY",
        "APPROVAL_PENDING",
        "PUBLISHING",
        "PUBLISHED",
        "EXECUTING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "EVIDENCE_FINALIZED",
    ]
    assert list(harness_constants.ValidationCheckpoint.values) == [
        "VALIDATE",
        "DRAFT",
        "DEBUG",
        "RELEASE",
        "EXECUTE",
        "START_DEBUG_SESSION",
        "RUN_DEBUG",
        "PREPARE_RELEASE",
        "PUBLISH",
        "PRE_EXECUTE",
        "POSTCONDITION",
        "FEEDBACK_INTAKE",
        "PROMOTION_EVAL",
    ]


def test_p2_debug_choices_are_stable_and_unambiguous():
    """Later models and serializers share one exact vocabulary for mode, status, and controls."""
    debug_mode = getattr(harness_constants, "DebugMode", None)
    execution_mode = getattr(harness_constants, "DebugExecutionMode", None)
    session_status = getattr(harness_constants, "DebugSessionStatus", None)
    control_action = getattr(harness_constants, "DebugControlAction", None)

    assert debug_mode is not None
    assert execution_mode is not None
    assert session_status is not None
    assert control_action is not None
    assert list(debug_mode.values) == ["step", "global"]
    assert list(execution_mode.values) == ["mock", "real"]
    assert list(session_status.values) == ["ACTIVE", "RUNNING", "COMPLETED", "FAILED", "TERMINATED", "EXPIRED"]
    assert list(control_action.values) == ["reset", "terminate", "set_node_mock", "set_context_var"]
