"""Persistence boundaries for governed P4 improvement candidates."""

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError

from bkflow.harness import models as harness_models
from bkflow.harness.constants import ImprovementCandidateType, KnowledgeTier
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    create_space_binding,
    feedback_values,
)


@pytest.fixture
def draft_candidate(db):
    """Persist one draft candidate rooted in immutable feedback."""
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    candidate = harness_models.ImprovementCandidate.objects.create(**candidate_values(feedback))
    return feedback, candidate


def test_candidate_stores_governance_and_version_coordinates(draft_candidate):
    """A DRAFT contains review inputs but no invented Owner or promotion receipt."""
    feedback, candidate = draft_candidate

    assert candidate.source_feedback_id == feedback.id
    assert candidate.status == "DRAFT"
    assert candidate.owner_ref is None
    assert candidate.reviewer_ref is None
    assert candidate.target_tier == KnowledgeTier.SPACE
    assert candidate.source_version == "snapshot-1"
    assert candidate.current_version == "snapshot-1"
    assert candidate.target_version == "snapshot-2"
    assert candidate.promotion_receipt_digest is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"proposal_artifact_ref": "https://credential.example.test/proposal"},
        {"owner_ref": "token=raw-secret"},
        {"confidence": -0.01},
        {"confidence": 1.01},
        {"regression_case_refs": ["evalcase://case/1", "evalcase://case/1"]},
        {"target_tier": KnowledgeTier.SCOPE, "target_scope_type": None, "target_scope_value": None},
        {"promotion_receipt_digest": "not-a-digest"},
    ],
)
def test_candidate_rejects_secrets_invalid_refs_and_broadened_dimensions(overrides):
    """Candidate metadata cannot smuggle credentials or omit target-scope authority."""
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))

    with pytest.raises(ValidationError):
        harness_models.ImprovementCandidate.objects.create(**candidate_values(feedback, **overrides))


def test_knowledge_candidate_binds_exact_source_and_contains_no_credentials(draft_candidate):
    """Knowledge content stays external while the candidate stores lineage and citations only."""
    _feedback, candidate = draft_candidate
    binding = create_space_binding(space_id=candidate.target_space_id)
    knowledge = harness_models.KnowledgeCandidate.objects.create(
        candidate=candidate,
        target_binding=binding,
        target_source_ref=binding.source_ref,
        proposed_snapshot_lineage={"parent": "snapshot-1", "proposed": "snapshot-2"},
        citation_refs=["knowledge-hit://bkfara/hit-1"],
        conflict_set=["knowledge-hit://bkfara/hit-2"],
    )

    assert knowledge.target_binding_id == binding.id
    assert knowledge.proposed_snapshot_lineage["parent"] == binding.snapshot_version
    for forbidden_field in ("credential", "credential_ref", "raw_document", "content"):
        with pytest.raises(FieldDoesNotExist):
            harness_models.KnowledgeCandidate._meta.get_field(forbidden_field)

    knowledge.citation_refs = ["knowledge-hit://bkfara/rewritten"]
    with pytest.raises(ValidationError):
        knowledge.save()


@pytest.mark.django_db
def test_knowledge_candidate_rejects_wrong_type_binding_scope_and_raw_content():
    """A knowledge target cannot be attached to a non-knowledge or cross-space draft."""
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    binding = create_space_binding(space_id=run.space_id)
    registry = harness_models.ImprovementCandidate.objects.create(
        **candidate_values(
            feedback,
            candidate_type=ImprovementCandidateType.REGISTRY,
            target_tier=None,
            target_platform_key=None,
            target_space_id=None,
            target_system="capability-registry",
        )
    )
    with pytest.raises(ValidationError):
        harness_models.KnowledgeCandidate.objects.create(
            candidate=registry,
            target_binding=binding,
            target_source_ref=binding.source_ref,
            proposed_snapshot_lineage={"parent": "snapshot-1", "raw_content": "unbounded document"},
            citation_refs=[],
            conflict_set=[],
        )

    _other_run, other_revision = create_run_revision(space_id=907)
    other_feedback = harness_models.GenerationFeedback.objects.create(
        **feedback_values(_other_run, other_revision, idempotency_digest="c" * 64)
    )
    cross_space = harness_models.ImprovementCandidate.objects.create(**candidate_values(other_feedback))
    with pytest.raises(ValidationError):
        harness_models.KnowledgeCandidate.objects.create(
            candidate=cross_space,
            target_binding=binding,
            target_source_ref=binding.source_ref,
            proposed_snapshot_lineage={"parent": "snapshot-1", "proposed": "snapshot-2"},
            citation_refs=[],
            conflict_set=[],
        )
