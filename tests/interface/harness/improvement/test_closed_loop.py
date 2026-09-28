"""P4 feedback-to-candidate closed-loop acceptance without external-evidence claims."""

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
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.services.eval.fixtures import derive_regression_case
from bkflow.harness.services.eval.gate import CandidateEvalGate
from bkflow.harness.services.eval.runner import MANDATORY_LOCAL_SUITES, run_local_eval
from bkflow.harness.services.feedback.attribution import (
    attribute_feedback,
    persist_attribution_results,
)
from bkflow.harness.services.feedback.contracts import FeedbackRetentionPolicy
from bkflow.harness.services.feedback.facade import (
    submit_generation_feedback_with_context,
)
from bkflow.harness.services.improvement.governance import (
    review_candidate,
    submit_candidate,
)
from bkflow.harness.services.improvement.package import build_candidate_review_package
from bkflow.harness.services.improvement.promotion import (
    CandidatePromotionError,
    DenyPromotionReadbackProvider,
    DenyPromotionVerifier,
    acknowledge_promotion,
)
from bkflow.harness.services.improvement.routing import (
    ImprovementOwnerMap,
    OwnerAssignment,
    route_improvement_candidate,
)
from bkflow.space.models import SpaceConfig
from tests.interface.harness.eval.p4_eval_support import (
    case_spec,
    passing_observations,
    resolved_thresholds,
)
from tests.interface.harness.p4_model_support import create_run_revision


class _AllowPromotionPolicy:
    def allows(self, candidate):
        return True


def _context(run):
    return TrustedHarnessContext(
        platform_key=run.platform,
        platform_app=run.platform_app,
        actor=run.actor,
        space_id=run.space_id,
        scope_type="project",
        scope_value=str(run.space_id),
        target_environment=run.environment,
        policy_version=run.policy_version,
        mcp_contract_version="1.4.0",
        correlation_id="p4-closed-loop",
    )


def _record_feedback():
    run, revision = create_run_revision()
    SpaceConfig.objects.update_or_create(
        space_id=run.space_id,
        name="harness_feedback_enabled",
        defaults={"text_value": "true"},
    )
    response = submit_generation_feedback_with_context(
        _context(run),
        {
            "run_id": str(run.run_id),
            "revision_id": str(revision.id),
            "expected_plan_hash": revision.plan_hash,
            "feedback_type": "CORRECTION",
            "consent_scope": "harness_improvement",
            "idempotency_key": "p4-closed-loop-feedback",
            "rating": 2,
            "summary": "The generated flow did not satisfy the typed outcome.",
            "observed_outcome": {"result": "mismatch"},
        },
        retention_policy=FeedbackRetentionPolicy.approved(
            policy_version="p4-closed-loop-test",
            allowed_consent_scopes=("harness_improvement",),
            retention_days=30,
        ),
    )
    assert response["ok"] is True
    return harness_models.GenerationFeedback.objects.get(), run, revision


def _typed_attribution(feedback, candidate_type):
    signals = {
        ImprovementCandidateType.KNOWLEDGE: (
            FeedbackAttributionCategory.KNOWLEDGE,
            [{"id": 1, "errors": [{"code": "KNOWLEDGE_SNAPSHOT_STALE"}]}],
            [],
        ),
        ImprovementCandidateType.REGISTRY: (
            FeedbackAttributionCategory.RESOLVER,
            [{"id": 1, "errors": [{"code": "CAPABILITY_NOT_FOUND"}]}],
            [],
        ),
        ImprovementCandidateType.VALIDATOR_POLICY: (
            FeedbackAttributionCategory.VALIDATOR,
            [{"id": 1, "errors": [{"code": "PIPELINE_VALIDATION_ERROR"}]}],
            [],
        ),
        ImprovementCandidateType.PROMPT_SKILL: (
            FeedbackAttributionCategory.PROMPT,
            [{"id": 1, "errors": [{"code": "PROMPT_CONSTRAINT_MISSED"}]}],
            [],
        ),
        ImprovementCandidateType.EVAL: (
            FeedbackAttributionCategory.ENVIRONMENT,
            [],
            [
                {
                    "id": "p4-closed-loop-event",
                    "event_type": "RUNTIME_ENVIRONMENT_UNAVAILABLE",
                    "redacted_payload": {"error_code": "RUNTIME_ENVIRONMENT_UNAVAILABLE"},
                }
            ],
        ),
    }
    expected_category, reports, events = signals[candidate_type]
    results = attribute_feedback(feedback, validation_reports=reports, evidence_events=events)
    result = next(item for item in results if item.category == expected_category)
    assert candidate_type in result.recommended_candidate_types
    persist_attribution_results(feedback, results, correlation_id="p4-closed-loop-attribution")
    return result


def _knowledge_binding(feedback):
    return harness_models.KnowledgeSourceBinding.objects.create(
        provider="p4-closed-loop",
        source_ref="knowledge://p4-closed-loop/space-{}".format(feedback.space_id),
        tier=KnowledgeTier.SPACE,
        platform_key=feedback.platform,
        space_id=feedback.space_id,
        trust_level=KnowledgeTrustLevel.VERIFIED,
        environment=feedback.target_environment,
        allowed_apps=[feedback.platform_app],
        allowed_actors=[feedback.actor],
        data_classification="internal",
        snapshot_version="snapshot-1",
        last_verified_at=timezone.now(),
        owner="knowledge-owner",
        reviewer="knowledge-reviewer",
        status=KnowledgeBindingStatus.ACTIVE,
        retrieval_mode=KnowledgeRetrievalMode.HYBRID,
        max_top_k=5,
    )


def _route(feedback, attribution, candidate_type):
    assignment = OwnerAssignment("candidate-owner", "candidate-reviewer")
    owner_maps = {
        ImprovementCandidateType.KNOWLEDGE: ImprovementOwnerMap(),
        ImprovementCandidateType.REGISTRY: ImprovementOwnerMap(
            registry_owners={"plugin://p4/closed-loop@1": (assignment,)}
        ),
        ImprovementCandidateType.VALIDATOR_POLICY: ImprovementOwnerMap(bkflow_owners=(assignment,)),
        ImprovementCandidateType.PROMPT_SKILL: ImprovementOwnerMap(bkaidev_release_owners=(assignment,)),
        ImprovementCandidateType.EVAL: ImprovementOwnerMap(harness_eval_owners=(assignment,)),
    }
    values = {
        "feedback": feedback,
        "attribution": attribution,
        "candidate_type": candidate_type,
        "proposal_artifact_ref": "artifact://candidate/p4-closed-loop-proposal",
        "source_version": "snapshot-1",
        "current_version": "snapshot-1",
        "target_version": "snapshot-2",
        "risk": RiskLevel.L1,
        "regression_case_refs": ("evalcase://harness/p4-closed-loop",),
        "impact_artifact_ref": "artifact://candidate/p4-closed-loop-impact",
        "rollback_artifact_ref": "artifact://candidate/p4-closed-loop-rollback",
        "owner_map": owner_maps[candidate_type],
    }
    if candidate_type == ImprovementCandidateType.KNOWLEDGE:
        _knowledge_binding(feedback)
        values.update(source_knowledge_tier=KnowledgeTier.SPACE, knowledge_classification="internal")
    elif candidate_type == ImprovementCandidateType.REGISTRY:
        values["capability_ref"] = "plugin://p4/closed-loop@1"
    return route_improvement_candidate(**values).candidate


def _mandatory_cases(candidate):
    tag_map = {"acl": ["permission", "cross_space"], "security": ["secret"]}
    return tuple(
        derive_regression_case(
            candidate.id,
            operator=candidate.owner_ref,
            **case_spec(suite, safety_tags=tag_map.get(suite)),
        )
        for suite in MANDATORY_LOCAL_SUITES
    )


@pytest.mark.django_db
@pytest.mark.parametrize("candidate_type", ImprovementCandidateType.values)
def test_each_candidate_type_reaches_reviewed_eval_evidence_then_an_explicit_external_block(candidate_type):
    """No feedback Tool call can skip Owner review, Eval, or destination verification."""
    feedback, run, _revision = _record_feedback()
    attribution = _typed_attribution(feedback, candidate_type)
    candidate = _route(feedback, attribution, candidate_type)

    assert candidate.status == ImprovementCandidateStatus.DRAFT
    assert harness_models.ImprovementCandidate.objects.count() == 1
    submitted = submit_candidate(candidate.id, operator=candidate.owner_ref)
    approved = review_candidate(submitted.id, operator=submitted.reviewer_ref, decision="APPROVE")
    review_package = build_candidate_review_package(approved)
    assert review_package["candidate"]["status"] == ImprovementCandidateStatus.APPROVED
    assert review_package["proposal"]["content_inline"] is False
    assert "NO_AUTOMATIC_PUBLICATION" in review_package["exclusions"]

    cases = _mandatory_cases(approved)
    eval_run = run_local_eval(
        approved.id,
        bkaidev_agent_release="agent-release-p4-closed-loop",
        observations=passing_observations(cases),
        thresholds=resolved_thresholds(),
    )
    assert eval_run.status == "PASSED"
    eval_gate = CandidateEvalGate(resolved_thresholds())
    decision = eval_gate.evaluate(approved)

    if candidate_type in {ImprovementCandidateType.KNOWLEDGE, ImprovementCandidateType.PROMPT_SKILL}:
        assert decision.reasons == ("SIGNED_BKAIDEV_EVAL_REQUIRED",)
    else:
        assert decision.passed is True
        with pytest.raises(CandidatePromotionError, match="RECEIPT_UNREADABLE"):
            acknowledge_promotion(
                approved.id,
                operator=approved.owner_ref,
                receipt_ref="promotion-receipt://p4-closed-loop/not-integrated",
                expected_target_version=approved.target_version,
                policy=_AllowPromotionPolicy(),
                gate=eval_gate,
                verifier=DenyPromotionVerifier(),
                readback_provider=DenyPromotionReadbackProvider(),
            )

    approved.refresh_from_db()
    run.refresh_from_db()
    assert approved.status == ImprovementCandidateStatus.APPROVED
    assert approved.rollback_artifact_ref == "artifact://candidate/p4-closed-loop-rollback"
    assert harness_models.ImprovementCandidate.objects.filter(status=ImprovementCandidateStatus.PUBLISHED).count() == 0
    if candidate_type == ImprovementCandidateType.KNOWLEDGE:
        approved.knowledge_candidate.target_binding.refresh_from_db()
        assert approved.knowledge_candidate.target_binding.snapshot_version == "snapshot-1"
