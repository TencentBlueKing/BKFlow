"""P4 feedback intake provenance, consent, and idempotency tests."""

import pytest

from bkflow.harness import models as harness_models
from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.services.feedback.contracts import FeedbackRetentionPolicy
from bkflow.harness.services.feedback.facade import (
    submit_generation_feedback_with_context,
)
from bkflow.space.models import SpaceConfig
from tests.interface.harness.p4_model_support import create_run_revision


def context_for(run, **overrides):
    """Rebuild the exact trusted authority that owns a test run."""
    values = {
        "platform_key": run.platform,
        "platform_app": run.platform_app,
        "actor": run.actor,
        "space_id": run.space_id,
        "scope_type": "project",
        "scope_value": str(run.space_id),
        "target_environment": run.environment,
        "policy_version": run.policy_version,
        "mcp_contract_version": run.mcp_contract_version,
        "correlation_id": "feedback-intake-test",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


def request_for(run, revision, **overrides):
    """Build one closed public feedback request."""
    values = {
        "run_id": str(run.run_id),
        "revision_id": str(revision.id),
        "expected_plan_hash": revision.plan_hash,
        "feedback_type": "CORRECTION",
        "consent_scope": "harness_improvement",
        "idempotency_key": "feedback-intake-1",
        "rating": 2,
        "summary": "The selected capability did not match the requested service.",
        "correction_artifact_ref": "artifact://feedback/correction-1",
        "observed_outcome": {"expected": "service-a", "actual": "service-b"},
    }
    values.update(overrides)
    return values


def approved_policy():
    """Create the explicit test-only retention decision required by intake."""
    return FeedbackRetentionPolicy.approved(
        policy_version="retention-2026.09-test",
        allowed_consent_scopes=("harness_improvement",),
        retention_days=30,
    )


def enable_feedback(space_id):
    SpaceConfig.objects.update_or_create(
        space_id=space_id,
        name="harness_feedback_enabled",
        defaults={"text_value": "true"},
    )


@pytest.mark.django_db
def test_intake_persists_exact_provenance_evidence_and_stable_envelope():
    """One accepted request stores no caller authority and leaves the run outcome untouched."""
    run, revision = create_run_revision()
    enable_feedback(run.space_id)

    response = submit_generation_feedback_with_context(
        context_for(run),
        request_for(run, revision),
        retention_policy=approved_policy(),
    )

    assert response["ok"] is True
    assert response["run_id"] == str(run.run_id)
    assert response["revision_id"] == str(revision.id)
    assert response["plan_hash"] == revision.plan_hash
    assert response["status"] == "FEEDBACK_RECORDED"
    assert response["next_actions"] == []
    feedback_ref = response["artifact_refs"][0]["feedback_ref"]
    feedback = harness_models.GenerationFeedback.objects.get(id=feedback_ref.rsplit("/", 1)[-1])
    assert feedback.platform == run.platform
    assert feedback.platform_app == run.platform_app
    assert feedback.actor == run.actor
    assert feedback.space_id == run.space_id
    assert feedback.scope == run.scope
    assert feedback.revision_id == revision.id
    assert (
        harness_models.EvidenceEvent.objects.filter(
            run=run,
            revision=revision,
            event_type="GENERATION_FEEDBACK_RECORDED",
            action="submit_generation_feedback",
        ).count()
        == 1
    )
    event = harness_models.EvidenceEvent.objects.get(event_type="GENERATION_FEEDBACK_RECORDED")
    assert event.redacted_payload["retention_policy_version"] == "retention-2026.09-test"
    assert event.redacted_payload["retention_days"] == 30
    run.refresh_from_db()
    assert run.status == HarnessRunStatus.EVIDENCE_FINALIZED
    assert harness_models.ImprovementCandidate.objects.count() == 0


@pytest.mark.django_db
def test_intake_replays_same_request_and_rejects_conflicting_idempotency_payload():
    """A retry returns the original feedback while key reuse with changed content fails closed."""
    run, revision = create_run_revision()
    enable_feedback(run.space_id)
    context = context_for(run)
    request = request_for(run, revision)

    first = submit_generation_feedback_with_context(context, request, retention_policy=approved_policy())
    second = submit_generation_feedback_with_context(context, request, retention_policy=approved_policy())
    conflict = submit_generation_feedback_with_context(
        context,
        request_for(run, revision, rating=5),
        retention_policy=approved_policy(),
    )

    assert second == first
    assert harness_models.GenerationFeedback.objects.count() == 1
    assert harness_models.EvidenceEvent.objects.count() == 1
    assert conflict["ok"] is False
    assert conflict["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "failure,expected_code",
    [
        ("feature_off", "HARNESS_TOOL_UNAVAILABLE"),
        ("retention_disabled", "HARNESS_TOOL_UNAVAILABLE"),
        ("cross_actor", "CAPABILITY_FORBIDDEN"),
        ("cross_space", "CAPABILITY_FORBIDDEN"),
        ("plan_mismatch", "PLAN_HASH_MISMATCH"),
        ("cross_revision", "CAPABILITY_FORBIDDEN"),
        ("unowned_correction_artifact", "CAPABILITY_FORBIDDEN"),
    ],
)
def test_intake_rejects_unapproved_retention_and_unowned_references_before_writes(failure, expected_code):
    """Feature, consent, ownership, and plan checks precede feedback or Evidence persistence."""
    run, revision = create_run_revision()
    other_run, other_revision = create_run_revision(space_id=907)
    if failure != "feature_off":
        enable_feedback(run.space_id)
    context = context_for(run)
    request = request_for(run, revision)
    policy = approved_policy()
    if failure == "retention_disabled":
        policy = FeedbackRetentionPolicy.disabled()
    elif failure == "cross_actor":
        context = context_for(run, actor="other-user")
    elif failure == "cross_space":
        context = context_for(run, space_id=other_run.space_id, scope_value=str(other_run.space_id))
        enable_feedback(other_run.space_id)
    elif failure == "plan_mismatch":
        request["expected_plan_hash"] = "f" * 64
    elif failure == "cross_revision":
        request["revision_id"] = str(other_revision.id)
    elif failure == "unowned_correction_artifact":
        request["correction_artifact_ref"] = "artifact://feedback/not-owned"

    response = submit_generation_feedback_with_context(context, request, retention_policy=policy)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == expected_code
    assert harness_models.GenerationFeedback.objects.count() == 0
    assert harness_models.EvidenceEvent.objects.count() == 0


@pytest.mark.django_db
def test_p4_context_can_record_feedback_for_an_owned_predecessor_run():
    """The new intake Tool may close the loop on P0-P3 runs without rewriting their contract."""
    run, revision = create_run_revision()
    run.mcp_contract_version = "1.3.0"
    run.save(update_fields=["mcp_contract_version"])
    enable_feedback(run.space_id)

    response = submit_generation_feedback_with_context(
        context_for(run, mcp_contract_version="1.4.0"),
        request_for(run, revision),
        retention_policy=approved_policy(),
    )

    assert response["ok"] is True
    run.refresh_from_db()
    assert run.mcp_contract_version == "1.3.0"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "run_status",
    [HarnessRunStatus.NEEDS_REPAIR, HarnessRunStatus.DEBUGGING, HarnessRunStatus.FAILED],
)
def test_feedback_can_capture_validation_debug_and_runtime_failures(run_status):
    """Feedback is allowed for failed phases without rewriting their lifecycle status."""
    run, revision = create_run_revision()
    run.status = run_status
    run.save(update_fields=["status"])
    enable_feedback(run.space_id)

    response = submit_generation_feedback_with_context(
        context_for(run),
        request_for(run, revision, feedback_type="RUNTIME_ISSUE"),
        retention_policy=approved_policy(),
    )

    assert response["ok"] is True
    run.refresh_from_db()
    assert run.status == run_status


@pytest.mark.django_db
def test_execution_reference_must_belong_to_the_owned_run_and_revision():
    """An execution identifier cannot be used as a cross-space Evidence oracle."""
    run, revision = create_run_revision()
    enable_feedback(run.space_id)

    response = submit_generation_feedback_with_context(
        context_for(run),
        request_for(run, revision, execution_id="00000000-0000-4000-8000-000000000001"),
        retention_policy=approved_policy(),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert harness_models.GenerationFeedback.objects.count() == 0
