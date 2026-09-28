"""Owner and tier routing for governed improvement drafts."""

import pytest
from django.utils import timezone

from bkflow.harness import models as harness_models
from bkflow.harness.constants import (
    FeedbackAttributionCategory,
    ImprovementCandidateStatus,
    ImprovementCandidateType,
    KnowledgeBindingStatus,
    KnowledgeRetrievalMode,
    KnowledgeTier,
    KnowledgeTrustLevel,
    RiskLevel,
)
from bkflow.harness.services.feedback.attribution import AttributionResult
from bkflow.harness.services.improvement.routing import (
    ImprovementOwnerMap,
    OwnerAssignment,
    route_improvement_candidate,
)
from tests.interface.harness.p4_model_support import (
    create_run_revision,
    feedback_values,
)


def _feedback():
    run, revision = create_run_revision()
    return harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))


def _attribution(candidate_type, category=FeedbackAttributionCategory.KNOWLEDGE):
    return AttributionResult(
        category=category,
        evidence_refs=("evidence://event/typed-1",),
        confidence=0.91,
        ambiguous=False,
        ambiguity_reasons=(),
        recommended_candidate_types=(candidate_type,),
        requires_human_triage=False,
        rule_version="p4-attribution-v1",
        rule_id="typed-rule",
        result_hash="a" * 64,
    )


def _binding(feedback, suffix, tier, priority=0, **overrides):
    dimensions = {
        KnowledgeTier.PUBLIC: {},
        KnowledgeTier.PLATFORM: {"platform_key": feedback.platform},
        KnowledgeTier.SPACE: {"platform_key": feedback.platform, "space_id": feedback.space_id},
        KnowledgeTier.SCOPE: {
            "platform_key": feedback.platform,
            "space_id": feedback.space_id,
            "scope_type": "project",
            "scope_value": str(feedback.space_id),
        },
    }[tier]
    values = {
        "provider": "fixture-docs",
        "source_ref": "knowledge://fixture/{}".format(suffix),
        "tier": tier,
        "trust_level": KnowledgeTrustLevel.VERIFIED,
        "priority": priority,
        "environment": feedback.target_environment,
        "allowed_apps": [feedback.platform_app],
        "allowed_actors": [feedback.actor],
        "data_classification": "internal",
        "snapshot_version": "snapshot-1",
        "last_verified_at": timezone.now(),
        "owner": "{}-owner".format(suffix),
        "reviewer": "{}-reviewer".format(suffix),
        "status": KnowledgeBindingStatus.ACTIVE,
        "retrieval_mode": KnowledgeRetrievalMode.HYBRID,
        "max_top_k": 5,
    }
    values.update(dimensions)
    values.update(overrides)
    return harness_models.KnowledgeSourceBinding.objects.create(**values)


def _route(feedback, attribution, candidate_type, owner_map, **overrides):
    values = {
        "feedback": feedback,
        "attribution": attribution,
        "candidate_type": candidate_type,
        "proposal_artifact_ref": "artifact://candidate/proposal-1",
        "source_version": "snapshot-1",
        "current_version": "snapshot-1",
        "target_version": "snapshot-2",
        "risk": RiskLevel.L1,
        "regression_case_refs": ("evalcase://harness/case-1",),
        "impact_artifact_ref": "artifact://candidate/impact-1",
        "rollback_artifact_ref": "artifact://candidate/rollback-1",
        "owner_map": owner_map,
    }
    values.update(overrides)
    return route_improvement_candidate(**values)


@pytest.mark.django_db
def test_knowledge_uses_most_specific_eligible_binding_without_broadening_source_tier():
    feedback = _feedback()
    _binding(feedback, "public", KnowledgeTier.PUBLIC)
    _binding(feedback, "space", KnowledgeTier.SPACE)
    scope = _binding(feedback, "scope", KnowledgeTier.SCOPE)

    result = _route(
        feedback,
        _attribution(ImprovementCandidateType.KNOWLEDGE),
        ImprovementCandidateType.KNOWLEDGE,
        ImprovementOwnerMap(),
        source_knowledge_tier=KnowledgeTier.SPACE,
        knowledge_classification="internal",
    )

    assert result.routing_reason == "ROUTED_TO_KNOWLEDGE_BINDING"
    assert result.candidate.status == ImprovementCandidateStatus.DRAFT
    assert result.candidate.owner_ref == scope.owner
    assert result.candidate.target_tier == KnowledgeTier.SCOPE
    assert result.knowledge_candidate.target_binding_id == scope.id


@pytest.mark.django_db
def test_knowledge_does_not_fall_back_to_a_broader_binding():
    feedback = _feedback()
    _binding(feedback, "public", KnowledgeTier.PUBLIC)

    result = _route(
        feedback,
        _attribution(ImprovementCandidateType.KNOWLEDGE),
        ImprovementCandidateType.KNOWLEDGE,
        ImprovementOwnerMap(),
        source_knowledge_tier=KnowledgeTier.SPACE,
        knowledge_classification="internal",
    )

    assert result.routing_reason == "KNOWLEDGE_TIER_BROADENING_BLOCKED"
    assert result.candidate.status == ImprovementCandidateStatus.DRAFT
    assert result.candidate.owner_ref is None
    assert result.knowledge_candidate is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "candidate_type,category,capability_ref,assignment_attr,expected_system",
    [
        (
            ImprovementCandidateType.REGISTRY,
            FeedbackAttributionCategory.RESOLVER,
            "plugin://cmdb/query@1.0.0",
            "registry_owners",
            "capability-registry",
        ),
        (
            ImprovementCandidateType.VALIDATOR_POLICY,
            FeedbackAttributionCategory.VALIDATOR,
            None,
            "bkflow_owners",
            "bkflow",
        ),
        (
            ImprovementCandidateType.PROMPT_SKILL,
            FeedbackAttributionCategory.PROMPT,
            None,
            "bkaidev_release_owners",
            "bkaidev-agent-release",
        ),
        (
            ImprovementCandidateType.EVAL,
            FeedbackAttributionCategory.POSTCONDITION,
            None,
            "harness_eval_owners",
            "harness-eval",
        ),
    ],
)
def test_non_knowledge_candidate_routes_to_the_explicit_owner_map(
    candidate_type, category, capability_ref, assignment_attr, expected_system
):
    feedback = _feedback()
    assignment = OwnerAssignment("owner-ref", "reviewer-ref")
    values = {assignment_attr: (assignment,)}
    if assignment_attr == "registry_owners":
        values[assignment_attr] = {capability_ref: (assignment,)}
    owner_map = ImprovementOwnerMap(**values)

    result = _route(
        feedback,
        _attribution(candidate_type, category),
        candidate_type,
        owner_map,
        capability_ref=capability_ref,
    )

    assert result.routing_reason.startswith("ROUTED_TO_")
    assert result.candidate.owner_ref == "owner-ref"
    assert result.candidate.reviewer_ref == "reviewer-ref"
    assert result.candidate.target_system == expected_system
    assert result.candidate.target_tier is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "assignments,reason",
    [
        ((), "OWNER_MISSING"),
        (
            (OwnerAssignment("owner-a", "reviewer-a"), OwnerAssignment("owner-b", "reviewer-b")),
            "OWNER_AMBIGUOUS",
        ),
    ],
)
def test_missing_or_ambiguous_owner_stays_draft_with_explicit_reason(assignments, reason):
    feedback = _feedback()
    result = _route(
        feedback,
        _attribution(ImprovementCandidateType.VALIDATOR_POLICY, FeedbackAttributionCategory.VALIDATOR),
        ImprovementCandidateType.VALIDATOR_POLICY,
        ImprovementOwnerMap(bkflow_owners=assignments),
    )

    assert result.routing_reason == reason
    assert result.candidate.status == ImprovementCandidateStatus.DRAFT
    assert result.candidate.owner_ref is None
    assert result.candidate.reviewer_ref is None


@pytest.mark.django_db
def test_routing_rejects_a_candidate_type_not_recommended_by_attribution():
    feedback = _feedback()

    with pytest.raises(ValueError, match="candidate type"):
        _route(
            feedback,
            _attribution(ImprovementCandidateType.EVAL, FeedbackAttributionCategory.POSTCONDITION),
            ImprovementCandidateType.REGISTRY,
            ImprovementOwnerMap(),
        )
