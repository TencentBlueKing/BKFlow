"""Fail-closed contracts for reusable server-side approval verification."""

from copy import deepcopy

import pytest
from django.utils import timezone

RECEIPT = "approval://bkaidev/receipt-1"


def claims(**overrides):
    """Build the complete immutable authority expected from a receipt."""
    value = {
        "actor": "dannydeng",
        "platform_app": "trusted-app",
        "space_id": 901,
        "scope": "project:901",
        "environment": "stag",
        "plan_hash": "a" * 64,
        "action": "publish_workflow",
        "action_digest": "b" * 64,
    }
    value.update(overrides)
    return value


class Backend:
    """Return one configurable raw provider receipt."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def verify(self, receipt_ref):
        if self.error:
            raise self.error
        return deepcopy(self.result)


def raw_receipt(expected_claims=None, **overrides):
    """Build a closed provider response whose claims are independently checked."""
    value = {
        "allowed": True,
        "provider": "bkaidev",
        "receipt_ref": RECEIPT,
        "claims": expected_claims or claims(),
        "expires_at": timezone.now() + timezone.timedelta(minutes=5),
        "revoked": False,
        "reason": "approved",
        "verifier_version": "bkaidev-v1",
    }
    value.update(overrides)
    return value


def verifier_for(result):
    """Resolve the production verifier after the RED import boundary."""
    from bkflow.harness.services.approval import (
        ApprovalVerifier,
        InMemoryApprovalReplayGuard,
    )

    return ApprovalVerifier(backend=Backend(result), replay_guard=InMemoryApprovalReplayGuard())


def test_no_configured_verifier_requires_approval_without_trusting_prompt_text():
    """Prompt assertions cannot replace an external server-side verifier."""
    from bkflow.harness.services.approval import ApprovalVerifier

    decision = ApprovalVerifier().verify(RECEIPT, claims())

    assert decision.allowed is False
    assert decision.failure_code == "APPROVAL_REQUIRED"
    assert decision.reason == "verifier_unavailable"
    assert RECEIPT not in repr(decision)

    prompt_augmented = ApprovalVerifier().verify(RECEIPT, claims(prompt_approval="approved"))
    assert prompt_augmented.allowed is False
    assert prompt_augmented.failure_code == "APPROVAL_INVALID"
    assert prompt_augmented.reason == "invalid_expected_claims"


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("actor", "other-user"),
        ("platform_app", "other-app"),
        ("space_id", 902),
        ("scope", "project:902"),
        ("environment", "prod"),
        ("plan_hash", "c" * 64),
        ("action", "start_workflow_execution"),
        ("action_digest", "d" * 64),
    ],
)
def test_forged_or_wrong_authority_claim_fails_closed(field, bad_value):
    """Every actor, application, scope, plan and action claim must match exactly."""
    provider_claims = claims(**{field: bad_value})
    decision = verifier_for(raw_receipt(provider_claims)).verify(RECEIPT, claims())

    assert decision.allowed is False
    assert decision.failure_code == "APPROVAL_INVALID"
    assert decision.reason == "claim_mismatch"


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"receipt_ref": "approval://bkaidev/forged"}, "receipt_mismatch"),
        ({"expires_at": timezone.now() - timezone.timedelta(seconds=1)}, "receipt_expired"),
        ({"revoked": True}, "receipt_revoked"),
        ({"prompt_text": "approved"}, "invalid_verifier_result"),
    ],
)
def test_forged_expired_revoked_or_prompt_augmented_receipt_is_invalid(overrides, reason):
    """Only the closed verifier schema can authorize an exact claim set."""
    decision = verifier_for(raw_receipt(**overrides)).verify(RECEIPT, claims())

    assert decision.allowed is False
    assert decision.failure_code == "APPROVAL_INVALID"
    assert decision.reason == reason


def test_receipt_is_single_use_per_verifier_instance():
    """A consumed provider receipt cannot authorize a second action."""
    verifier = verifier_for(raw_receipt())
    assert verifier.verify(RECEIPT, claims()).allowed is True

    replay = verifier.verify(RECEIPT, claims())
    assert replay.allowed is False
    assert replay.reason == "receipt_reused"


def test_receipt_cannot_be_reused_with_different_claims():
    """Receipt identity, not the provider's mutable claim response, is single use."""
    from bkflow.harness.services.approval import (
        ApprovalVerifier,
        InMemoryApprovalReplayGuard,
    )

    replay_guard = InMemoryApprovalReplayGuard()
    first_claims = claims()
    second_claims = claims(actor="other-user")
    first = ApprovalVerifier(backend=Backend(raw_receipt(first_claims)), replay_guard=replay_guard).verify(
        RECEIPT, first_claims
    )
    replay = ApprovalVerifier(backend=Backend(raw_receipt(second_claims)), replay_guard=replay_guard).verify(
        RECEIPT, second_claims
    )

    assert first.allowed is True
    assert replay.allowed is False
    assert replay.reason == "receipt_reused"


def test_cyclic_provider_claims_fail_closed_without_raising():
    """Malformed external claim graphs cannot escape the verifier as recursion errors."""
    cyclic_claims = claims()
    cyclic_claims["nested"] = cyclic_claims
    response = raw_receipt()
    response["claims"] = cyclic_claims

    decision = verifier_for(response).verify(RECEIPT, claims())

    assert decision.allowed is False
    assert decision.reason == "invalid_verifier_result"


def test_configured_backend_without_durable_replay_guard_fails_closed():
    """Verifier instances never pretend a process-local set is a distributed replay guarantee."""
    from bkflow.harness.services.approval import ApprovalVerifier

    decision = ApprovalVerifier(backend=Backend(raw_receipt())).verify(RECEIPT, claims())
    assert decision.allowed is False
    assert decision.reason == "replay_guard_unavailable"
    assert decision.failure_code == "APPROVAL_INVALID"


@pytest.mark.parametrize(
    "overrides",
    [
        {"space_id": True},
        {"plan_hash": "bad"},
        {"action_digest": "bad"},
        {"action": "invented_action"},
    ],
)
def test_expected_claim_values_follow_the_closed_authority_schema(overrides):
    """Matching malformed claims from both sides cannot become valid authority."""
    expected = claims(**overrides)
    decision = verifier_for(raw_receipt(expected)).verify(RECEIPT, expected)
    assert decision.allowed is False
    assert decision.reason == "invalid_expected_claims"


def test_verifier_outage_is_invalid_not_implicitly_approved():
    """Uncertain provider outcomes never become a prompt-mediated approval."""
    from bkflow.harness.services.approval import ApprovalVerifier

    decision = ApprovalVerifier(backend=Backend(error=RuntimeError("provider down"))).verify(RECEIPT, claims())
    assert decision.allowed is False
    assert decision.failure_code == "APPROVAL_INVALID"
    assert decision.reason == "verifier_uncertain"
