"""Sanitized, hash-addressed candidate review packages."""

import json

import pytest

from bkflow.harness import models as harness_models
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.improvement.package import build_candidate_review_package
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    feedback_values,
)


@pytest.mark.django_db
def test_package_contains_review_contract_and_no_raw_feedback_or_secret():
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(
        **feedback_values(
            run,
            revision,
            redacted_summary="raw-user-phrase-that-must-not-be-exported",
            observed_outcome={"code": "WRONG_CAPABILITY"},
        )
    )
    record_evidence(
        run=run,
        revision=revision,
        event_type="FEEDBACK_ATTRIBUTION_RECORDED",
        action="attribute_generation_feedback",
        payload={
            "feedback_ref": "feedback://generation/{}".format(feedback.id),
            "results": [
                {
                    "category": "KNOWLEDGE",
                    "evidence_refs": ["validation-report://harness/42"],
                    "confidence": 0.91,
                    "ambiguous": False,
                    "ambiguity_reasons": [],
                    "recommended_candidate_types": ["KNOWLEDGE"],
                    "requires_human_triage": False,
                    "rule_version": "p4-attribution-v1",
                    "rule_id": "knowledge-miss",
                    "result_hash": "a" * 64,
                }
            ],
        },
        actor=run.actor,
        correlation_id="package-test",
    )
    candidate = harness_models.ImprovementCandidate.objects.create(
        **candidate_values(
            feedback,
            owner_ref="knowledge-owner",
            reviewer_ref="knowledge-reviewer",
        )
    )

    package = build_candidate_review_package(candidate)

    assert package["schema_version"] == "p4-improvement-package-v1"
    assert package["candidate"]["candidate_ref"] == "candidate://improvement/{}".format(candidate.id)
    assert package["provenance"]["feedback_ref"] == "feedback://generation/{}".format(feedback.id)
    assert package["proposal"] == {"artifact_ref": candidate.proposal_artifact_ref, "content_inline": False}
    assert package["evidence_citations"] == ["validation-report://harness/42"]
    assert package["versions"] == {
        "source": "snapshot-1",
        "current": "snapshot-1",
        "proposed": "snapshot-2",
    }
    assert package["applicability"]["space_id"] == feedback.space_id
    assert package["exclusions"]
    assert package["risk"]["level"] == "L1"
    assert package["risk"]["blast_radius_artifact_ref"] == candidate.impact_artifact_ref
    assert package["regression_case_refs"] == ["evalcase://harness/wrong-service-1"]
    assert package["evaluation_requirements"]["zero_regression_required"] is True
    assert package["rollback_steps"]["artifact_ref"] == candidate.rollback_artifact_ref
    assert package["package_hash"] == sha256_json(
        {key: value for key, value in package.items() if key != "package_hash"}
    )

    serialized = json.dumps(package, sort_keys=True)
    assert "raw-user-phrase-that-must-not-be-exported" not in serialized
    assert "WRONG_CAPABILITY" not in serialized
    assert "token=" not in serialized.casefold()


@pytest.mark.django_db
def test_package_uses_bounded_governance_defaults_when_optional_artifacts_are_absent():
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    candidate = harness_models.ImprovementCandidate.objects.create(
        **candidate_values(
            feedback,
            impact_artifact_ref=None,
            rollback_artifact_ref=None,
            regression_case_refs=[],
            target_version="owner-must-propose",
        )
    )

    package = build_candidate_review_package(candidate)

    assert package["evidence_citations"] == []
    assert package["risk"]["blast_radius_artifact_ref"] is None
    assert package["evaluation_requirements"]["case_refs"] == []
    assert package["rollback_steps"] == {"artifact_ref": None, "owner_definition_required": True}
    assert len(json.dumps(package).encode("utf-8")) < 64 * 1024
