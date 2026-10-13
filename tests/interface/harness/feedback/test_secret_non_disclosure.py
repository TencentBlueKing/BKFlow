"""P4 full-chain sensitive-data non-disclosure checks."""

import json

import pytest

from bkflow.harness import models as harness_models
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.services.eval.runner import build_eval_package, run_local_eval
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
from bkflow.space.models import SpaceConfig
from tests.interface.harness.eval.p4_eval_support import (
    create_mandatory_cases,
    passing_observations,
    resolved_thresholds,
)
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    create_space_binding,
)


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
        correlation_id="p4-secret-non-disclosure",
    )


def _policy():
    return FeedbackRetentionPolicy.approved(
        policy_version="p4-secret-test",
        allowed_consent_scopes=("harness_improvement",),
        retention_days=30,
    )


@pytest.mark.django_db
def test_feedback_candidate_and_eval_artifacts_never_disclose_raw_sensitive_input():
    sentinel = "p4-raw-secret-sentinel"
    raw_credential = "Bearer {}".format(sentinel)
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
            "idempotency_key": "p4-secret-feedback",
            "summary": "The generated flow returned {} during validation.".format(raw_credential),
            "observed_outcome": {
                "access_token": raw_credential,
                "nested": {"authorization": raw_credential},
            },
        },
        retention_policy=_policy(),
    )
    assert response["ok"] is True
    feedback = harness_models.GenerationFeedback.objects.get()
    results = attribute_feedback(
        feedback,
        validation_reports=[{"id": 1, "errors": [{"code": "KNOWLEDGE_SNAPSHOT_STALE"}]}],
        evidence_events=[],
    )
    persist_attribution_results(feedback, results, correlation_id="p4-secret-attribution")
    candidate = harness_models.ImprovementCandidate.objects.create(
        **candidate_values(feedback, owner_ref="candidate-owner", reviewer_ref="candidate-reviewer")
    )
    binding = create_space_binding(space_id=feedback.space_id)
    harness_models.KnowledgeCandidate.objects.create(
        candidate=candidate,
        target_binding=binding,
        target_source_ref=binding.source_ref,
        proposed_snapshot_lineage={"parent": "snapshot-1", "proposed": "snapshot-2"},
        citation_refs=list(results[0].evidence_refs),
        conflict_set=[],
    )
    submit_candidate(candidate.id, operator="candidate-owner")
    candidate = review_candidate(candidate.id, operator="candidate-reviewer", decision="APPROVE")
    review_package = build_candidate_review_package(candidate)
    cases = create_mandatory_cases(candidate)
    eval_package = build_eval_package(candidate, bkaidev_agent_release="agent-release-p4-secret-test")
    eval_run = run_local_eval(
        candidate.id,
        bkaidev_agent_release="agent-release-p4-secret-test",
        observations=passing_observations(cases),
        thresholds=resolved_thresholds(),
    )

    persisted_projection = {
        "response": response,
        "feedback": {
            "summary": feedback.redacted_summary,
            "observed_outcome": feedback.observed_outcome,
            "correction_artifact_ref": feedback.correction_artifact_ref,
        },
        "events": list(run.evidence_events.values_list("redacted_payload", flat=True)),
        "review_package": review_package,
        "eval_package": eval_package,
        "eval_metrics": eval_run.aggregate_metrics,
    }
    serialized = json.dumps(persisted_projection, ensure_ascii=False, sort_keys=True, default=str)
    assert sentinel not in serialized
    assert raw_credential not in serialized
    assert feedback.observed_outcome == {
        "access_token": "[REDACTED]",
        "nested": {"authorization": "[REDACTED]"},
    }
    assert review_package["proposal"]["content_inline"] is False
    assert all("summary" not in case for case in eval_package["cases"])


@pytest.mark.django_db
def test_credential_shaped_correction_reference_is_rejected_before_any_feedback_write():
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
            "idempotency_key": "p4-secret-ref",
            "correction_artifact_ref": "credential://p4/raw-sensitive-material",
        },
        retention_policy=_policy(),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert harness_models.GenerationFeedback.objects.count() == 0
    assert harness_models.EvidenceEvent.objects.count() == 0
