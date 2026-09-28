"""Locked Owner/Reviewer lifecycle governance for improvement candidates."""

import pytest
from django.core.exceptions import ValidationError

from bkflow.harness import models as harness_models
from bkflow.harness.constants import (
    FeedbackAttributionCategory,
    ImprovementCandidateStatus,
    ImprovementCandidateType,
)
from bkflow.harness.services.improvement.governance import (
    CandidateGovernanceError,
    review_candidate,
    revise_candidate,
    submit_candidate,
)
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    feedback_values,
)


def _candidate():
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    return harness_models.ImprovementCandidate.objects.create(
        **candidate_values(
            feedback,
            candidate_type=ImprovementCandidateType.REGISTRY,
            attribution=FeedbackAttributionCategory.RESOLVER,
            owner_ref="candidate-owner",
            reviewer_ref="candidate-reviewer",
            target_system="capability-registry",
            target_tier=None,
            target_platform_key=None,
            target_space_id=None,
        )
    )


@pytest.mark.django_db
def test_owner_and_reviewer_drive_the_legal_review_lifecycle():
    candidate = _candidate()

    submitted = submit_candidate(candidate.id, operator="candidate-owner")
    approved = review_candidate(submitted.id, operator="candidate-reviewer", decision="APPROVE")

    assert submitted.status == ImprovementCandidateStatus.IN_REVIEW
    assert approved.status == ImprovementCandidateStatus.APPROVED
    events = list(
        approved.source_feedback.run.evidence_events.filter(
            event_type__in=["IMPROVEMENT_CANDIDATE_SUBMITTED", "IMPROVEMENT_CANDIDATE_REVIEWED"]
        ).values_list("event_type", "redacted_payload__operator")
    )
    assert events == [
        ("IMPROVEMENT_CANDIDATE_SUBMITTED", "candidate-owner"),
        ("IMPROVEMENT_CANDIDATE_REVIEWED", "candidate-reviewer"),
    ]


@pytest.mark.django_db
def test_reviewer_may_reject_but_submitter_cannot_self_approve():
    candidate = _candidate()
    submit_candidate(candidate.id, operator="candidate-owner")

    with pytest.raises(CandidateGovernanceError, match="REVIEWER_REQUIRED"):
        review_candidate(candidate.id, operator="candidate-owner", decision="APPROVE")

    rejected = review_candidate(candidate.id, operator="candidate-reviewer", decision="REJECT")
    assert rejected.status == ImprovementCandidateStatus.REJECTED


@pytest.mark.django_db
def test_direct_status_or_approved_proposal_mutation_is_rejected():
    candidate = _candidate()
    candidate.status = ImprovementCandidateStatus.IN_REVIEW
    with pytest.raises(ValidationError, match="governance service"):
        candidate.save()

    submit_candidate(candidate.id, operator="candidate-owner")
    approved = review_candidate(candidate.id, operator="candidate-reviewer", decision="APPROVE")
    approved.proposal_artifact_ref = "artifact://candidate/rewritten-in-place"
    with pytest.raises(ValidationError, match="new candidate revision"):
        approved.save()


@pytest.mark.django_db
def test_approved_change_creates_a_draft_revision_and_does_not_inherit_approval():
    candidate = _candidate()
    submit_candidate(candidate.id, operator="candidate-owner")
    approved = review_candidate(candidate.id, operator="candidate-reviewer", decision="APPROVE")

    revised = revise_candidate(
        approved.id,
        operator="candidate-owner",
        changes={
            "proposal_artifact_ref": "artifact://candidate/proposal-2",
            "regression_case_refs": ["evalcase://harness/case-2"],
            "target_version": "snapshot-3",
        },
    )

    approved.refresh_from_db()
    assert approved.status == ImprovementCandidateStatus.APPROVED
    assert revised.status == ImprovementCandidateStatus.DRAFT
    assert revised.parent_candidate_id == approved.id
    assert revised.revision_number == 2
    assert revised.promotion_receipt_digest is None
    assert revised.proposal_artifact_ref.endswith("proposal-2")


@pytest.mark.django_db
def test_revision_rejects_untrusted_fields_and_wrong_operator():
    candidate = _candidate()
    submit_candidate(candidate.id, operator="candidate-owner")
    review_candidate(candidate.id, operator="candidate-reviewer", decision="APPROVE")

    with pytest.raises(CandidateGovernanceError, match="OWNER_REQUIRED"):
        revise_candidate(
            candidate.id,
            operator="candidate-reviewer",
            changes={"target_version": "snapshot-3"},
        )
    with pytest.raises(CandidateGovernanceError, match="REVISION_FIELDS_INVALID"):
        revise_candidate(
            candidate.id,
            operator="candidate-owner",
            changes={"status": ImprovementCandidateStatus.PUBLISHED},
        )
