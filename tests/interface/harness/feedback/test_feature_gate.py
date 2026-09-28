"""P4 contract taxonomy and fail-closed feature gates."""

import pytest

import bkflow.harness.constants as harness_constants
from bkflow.harness.contracts import HarnessContextError, TrustedHarnessContext
from bkflow.harness.services import contract_versions
from bkflow.space.models import SpaceConfig


def trusted_context(contract_version="1.4.0"):
    """Build a server-owned P4 context for feedback policy tests."""
    return TrustedHarnessContext(
        platform_key="bkaidev",
        platform_app="trusted-app",
        actor="trusted-user",
        space_id=905,
        scope_type="project",
        scope_value="905",
        target_environment="stag",
        policy_version="risk-2026.09",
        mcp_contract_version=contract_version,
        correlation_id="p4-feature-gate-test",
    )


def set_flag(name, enabled):
    """Persist one canonical server-side P4 feature flag."""
    SpaceConfig.objects.update_or_create(
        space_id=905,
        name=name,
        defaults={"text_value": "true" if enabled else "false"},
    )


def enum_values(name):
    """Require a shared taxonomy class and return its stable values."""
    enum = getattr(harness_constants, name, None)
    assert enum is not None
    return list(enum.values)


@pytest.mark.django_db
def test_feedback_tool_defaults_to_deny_and_requires_its_own_flag():
    """A negotiated P4 contract alone cannot start retaining user feedback."""
    helper = getattr(contract_versions, "is_harness_feedback_enabled", None)
    assert helper is not None
    assert helper(905) is False

    with pytest.raises(HarnessContextError) as error:
        contract_versions.require_tool_enabled(trusted_context(), "submit_generation_feedback")
    assert error.value.code == "HARNESS_TOOL_UNAVAILABLE"

    set_flag("harness_feedback_enabled", True)
    assert helper(905) is True
    assert contract_versions.require_tool_enabled(trusted_context(), "submit_generation_feedback") is None


@pytest.mark.django_db
def test_candidate_promotion_flag_is_independent_and_defaults_to_deny():
    """Feedback intake never implies authority for an Owner-controlled promotion."""
    helper = getattr(contract_versions, "is_harness_candidate_promotion_enabled", None)
    assert helper is not None
    set_flag("harness_feedback_enabled", True)

    assert helper(905) is False
    set_flag("harness_candidate_promotion_enabled", True)
    assert helper(905) is True


def test_p4_feedback_and_improvement_taxonomy_is_exact():
    """Persistence and policy code share one ordered, closed P4 vocabulary."""
    assert enum_values("GenerationFeedbackType") == [
        "ACCEPTED",
        "REJECTED",
        "CORRECTION",
        "RUNTIME_ISSUE",
        "BUSINESS_OUTCOME",
    ]
    assert enum_values("FeedbackAttributionCategory") == [
        "REQUIREMENT",
        "KNOWLEDGE",
        "PROMPT",
        "SCHEMA",
        "RESOLVER",
        "VALIDATOR",
        "PERMISSION",
        "PLUGIN",
        "ENVIRONMENT",
        "POSTCONDITION",
    ]
    assert enum_values("ImprovementCandidateType") == [
        "KNOWLEDGE",
        "REGISTRY",
        "VALIDATOR_POLICY",
        "PROMPT_SKILL",
        "EVAL",
    ]
    assert enum_values("ImprovementCandidateStatus") == [
        "DRAFT",
        "IN_REVIEW",
        "APPROVED",
        "REJECTED",
        "PUBLISHED",
        "RETIRED",
    ]


def test_p4_checkpoints_append_without_rewriting_historical_values():
    """Feedback and promotion reports extend the P3 checkpoint sequence only at the tail."""
    p3_values = [
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
    ]
    assert list(harness_constants.ValidationCheckpoint.values) == p3_values + [
        "FEEDBACK_INTAKE",
        "PROMOTION_EVAL",
    ]


def test_feedback_taxonomy_does_not_extend_terminal_harness_run_outcomes():
    """Submitting feedback is not a state transition on the historical Harness run."""
    assert list(harness_constants.HarnessRunStatus.values)[-5:] == [
        "EXECUTING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "EVIDENCE_FINALIZED",
    ]
