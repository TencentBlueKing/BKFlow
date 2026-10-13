"""Small trusted persistence fixtures shared by P4 model tests."""

from bkflow.harness import models as harness_models
from bkflow.harness.constants import (
    FeedbackAttributionCategory,
    GenerationFeedbackType,
    HarnessRunStatus,
    ImprovementCandidateStatus,
    ImprovementCandidateType,
    KnowledgeBindingStatus,
    KnowledgeRetrievalMode,
    KnowledgeTier,
    KnowledgeTrustLevel,
    RiskLevel,
)
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.evidence import EVIDENCE_REDACTION_VERSION


def create_run_revision(*, space_id=906, actor="feedback-user"):
    """Persist one complete trusted P4 run and immutable revision."""
    run = harness_models.HarnessRun.objects.create(
        platform="bkaidev",
        platform_app="trusted-p4-app",
        actor=actor,
        space_id=space_id,
        scope=canonical_scope("project", str(space_id)),
        environment="stag",
        status=HarnessRunStatus.EVIDENCE_FINALIZED,
        policy_version="risk-2026.09",
        mcp_contract_version="1.4.0",
        artifact_references=["artifact://feedback/correction-1"],
    )
    revision = harness_models.WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={"goal": "restart service"},
        canonical_a2flow={"version": "2.0", "nodes": []},
        plan_hash="a" * 64,
    )
    return run, revision


def feedback_values(run, revision, **overrides):
    """Build one consent-bound, already-redacted feedback payload."""
    values = {
        "run": run,
        "revision": revision,
        "plan_hash": revision.plan_hash,
        "platform": run.platform,
        "platform_app": run.platform_app,
        "actor": run.actor,
        "space_id": run.space_id,
        "scope": run.scope,
        "target_environment": run.environment,
        "policy_version": run.policy_version,
        "feedback_type": GenerationFeedbackType.CORRECTION,
        "rating": 2,
        "redacted_summary": "The selected capability did not match the requested service.",
        "correction_artifact_ref": "artifact://feedback/correction-1",
        "observed_outcome": {"expected": "service restarted", "actual": "wrong service"},
        "consent_scope": "harness_improvement",
        "idempotency_digest": "b" * 64,
        "redaction_version": EVIDENCE_REDACTION_VERSION,
    }
    values.update(overrides)
    return values


def candidate_values(feedback, **overrides):
    """Build one local draft candidate without claiming an external Owner."""
    values = {
        "source_feedback": feedback,
        "candidate_type": ImprovementCandidateType.KNOWLEDGE,
        "attribution": FeedbackAttributionCategory.KNOWLEDGE,
        "proposal_artifact_ref": "artifact://candidate/proposal-1",
        "owner_ref": None,
        "reviewer_ref": None,
        "target_system": "bkfara-knowledge",
        "target_tier": KnowledgeTier.SPACE,
        "target_platform_key": feedback.platform,
        "target_space_id": feedback.space_id,
        "target_scope_type": None,
        "target_scope_value": None,
        "status": ImprovementCandidateStatus.DRAFT,
        "risk": RiskLevel.L1,
        "confidence": 0.75,
        "regression_case_refs": ["evalcase://harness/wrong-service-1"],
        "impact_artifact_ref": "artifact://candidate/impact-1",
        "rollback_artifact_ref": "artifact://candidate/rollback-1",
        "source_version": "snapshot-1",
        "current_version": "snapshot-1",
        "target_version": "snapshot-2",
        "revision_number": 1,
    }
    values.update(overrides)
    return values


def create_space_binding(*, space_id=906):
    """Persist one governed space-tier knowledge target."""
    return harness_models.KnowledgeSourceBinding.objects.create(
        provider="bkfara",
        source_ref="knowledge://bkfara/space-{}".format(space_id),
        tier=KnowledgeTier.SPACE,
        platform_key="bkaidev",
        space_id=space_id,
        trust_level=KnowledgeTrustLevel.UNVERIFIED,
        priority=10,
        environment="stag",
        allowed_apps=["trusted-p4-app"],
        allowed_actors=["feedback-user"],
        data_classification="internal",
        snapshot_version="snapshot-1",
        owner="knowledge-owner",
        reviewer="knowledge-reviewer",
        status=KnowledgeBindingStatus.ACTIVE,
        retrieval_mode=KnowledgeRetrievalMode.HYBRID,
        max_top_k=5,
    )
