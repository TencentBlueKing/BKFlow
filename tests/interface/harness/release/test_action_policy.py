"""Deterministic P3 action risk and digest policy contracts."""

import pytest
from django.core.exceptions import ValidationError

from bkflow.harness.constants import HarnessAction, RiskLevel


def evaluate(action=HarnessAction.PUBLISH_WORKFLOW, **overrides):
    """Evaluate one complete immutable action identity."""
    from bkflow.harness.services.release.policy import ActionPolicy

    values = {
        "action": action,
        "manifest_hash": "a" * 64,
        "plan_hash": "b" * 64,
        "target_resource": {"type": "template", "id": "42"},
        "normalized_params": {"version": "2026.09.05.1", "labels": ["safe"]},
        "policy_version": "risk-2026.09",
    }
    values.update(overrides)
    return ActionPolicy().evaluate(**values)


@pytest.mark.parametrize(
    "action,risk",
    [
        (HarnessAction.PREPARE_RELEASE, RiskLevel.L0),
        (HarnessAction.GET_WORKFLOW_EXECUTION, RiskLevel.L0),
        (HarnessAction.PUBLISH_WORKFLOW, RiskLevel.L2),
        (HarnessAction.START_WORKFLOW_EXECUTION, RiskLevel.L2),
        (HarnessAction.PAUSE, RiskLevel.L2),
        (HarnessAction.RESUME, RiskLevel.L2),
        (HarnessAction.REVOKE, RiskLevel.L2),
        (HarnessAction.RETRY, RiskLevel.L2),
        (HarnessAction.SKIP, RiskLevel.L3),
        (HarnessAction.CALLBACK, RiskLevel.L3),
        (HarnessAction.FORCED_FAIL, RiskLevel.L3),
        (HarnessAction.SKIP_EXG, RiskLevel.L3),
        (HarnessAction.SKIP_CPG, RiskLevel.L3),
    ],
)
def test_policy_maps_every_declared_release_execution_action(action, risk):
    """Risk and approval requirements come from a closed server-side table."""
    decision = evaluate(action)
    assert decision.risk_level == risk
    assert decision.requires_approval is (risk in {RiskLevel.L2, RiskLevel.L3})
    assert len(decision.action_digest) == 64


def test_digest_is_canonical_but_binds_every_authority_component():
    """Object key ordering is irrelevant while each immutable input changes the digest."""
    first = evaluate(HarnessAction.PUBLISH_WORKFLOW)
    reordered = evaluate(
        HarnessAction.PUBLISH_WORKFLOW,
        normalized_params={"labels": ["safe"], "version": "2026.09.05.1"},
    )
    assert first.action_digest == reordered.action_digest

    for name, value in [
        ("manifest_hash", "c" * 64),
        ("plan_hash", "d" * 64),
        ("target_resource", {"type": "template", "id": "43"}),
        ("normalized_params", {"version": "2026.09.05.2"}),
        ("policy_version", "risk-2026.10"),
    ]:
        assert evaluate(HarnessAction.PUBLISH_WORKFLOW, **{name: value}).action_digest != first.action_digest


def test_requirements_are_deterministic_manifest_input_without_approval_ids():
    """Prepare can hash requirements before a Manifest or ApprovalRequest exists."""
    from bkflow.harness.services.release.policy import ActionPolicy

    policy = ActionPolicy()
    first = policy.requirements_for(
        [HarnessAction.START_WORKFLOW_EXECUTION, HarnessAction.PUBLISH_WORKFLOW, HarnessAction.PUBLISH_WORKFLOW],
        "risk-2026.09",
    )
    reordered = policy.requirements_for(
        [HarnessAction.PUBLISH_WORKFLOW, HarnessAction.START_WORKFLOW_EXECUTION],
        "risk-2026.09",
    )

    assert first == reordered
    assert first == [
        {
            "action": HarnessAction.PUBLISH_WORKFLOW,
            "risk_level": RiskLevel.L2,
            "policy_ref": "policy://risk-2026.09/publish_workflow/l2",
        },
        {
            "action": HarnessAction.START_WORKFLOW_EXECUTION,
            "risk_level": RiskLevel.L2,
            "policy_ref": "policy://risk-2026.09/start_workflow_execution/l2",
        },
    ]
    assert all(set(requirement) == {"action", "risk_level", "policy_ref"} for requirement in first)
    assert policy.requirements_for([HarnessAction.PREPARE_RELEASE], "risk-2026.09") == []
    assert policy.requirements_for([HarnessAction.PUBLISH_WORKFLOW], "risk-2026.10") != first[:1]


def test_requirements_reject_unhashable_or_nested_action_input():
    """Malformed caller collections fail as policy validation, not runtime type errors."""
    from bkflow.harness.services.release.policy import ActionPolicy

    with pytest.raises(ValidationError):
        ActionPolicy().requirements_for([{"action": HarnessAction.PUBLISH_WORKFLOW}], "risk-2026.09")


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "invented_action"},
        {"action": {"name": HarnessAction.PUBLISH_WORKFLOW}},
        {"manifest_hash": "bad"},
        {"normalized_params": {"token": "raw-secret"}},
        {"target_resource": {"url": "https://user:password@example.test"}},
        {"policy_version": "Bearer raw-secret"},
    ],
)
def test_unknown_or_secret_bearing_policy_input_fails_closed(overrides):
    """Caller input cannot create actions or contaminate the approval digest."""
    with pytest.raises(ValidationError):
        evaluate(**overrides)
