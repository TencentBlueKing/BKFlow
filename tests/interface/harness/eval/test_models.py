"""Persistence boundaries for reproducible P4 evaluation cases and runs."""

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.utils import timezone

from bkflow.harness import models as harness_models
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    feedback_values,
)


@pytest.fixture
def eval_candidate(db):
    """Persist one candidate used by immutable Eval fixtures."""
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    return harness_models.ImprovementCandidate.objects.create(**candidate_values(feedback))


def eval_case_values(candidate, **overrides):
    """Build one safe, reproducible Eval case."""
    values = {
        "case_id": "wrong-service-selection",
        "case_version": "1.0.0",
        "source_candidate": candidate,
        "tier": candidate.target_tier,
        "scope": "space:{}".format(candidate.target_space_id),
        "sanitized_input_artifact_ref": "artifact://eval/input-1",
        "expected_invariants": {"selected_service": "service-a", "safety_passed": True},
        "scoring_schema": {"required": ["selected_service"], "version": "1"},
        "safety_tags": ["permission", "cross_space", "secret"],
    }
    values.update(overrides)
    return values


def test_eval_case_derives_hash_and_is_immutable(eval_candidate):
    """A case version is a hash-addressed fixture, not mutable training content."""
    case = harness_models.HarnessEvalCase.objects.create(**eval_case_values(eval_candidate))

    assert len(case.fixture_hash) == 64
    assert case.source_candidate_id == eval_candidate.id
    with pytest.raises(FieldDoesNotExist):
        harness_models.HarnessEvalCase._meta.get_field("raw_feedback")

    case.expected_invariants = {"selected_service": "forged"}
    with pytest.raises(ValidationError):
        case.save()
    with pytest.raises(ValidationError):
        harness_models.HarnessEvalCase.objects.filter(pk=case.pk).update(case_version="2.0.0")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"sanitized_input_artifact_ref": "https://credential.example.test/input"},
        {"expected_invariants": {"token": "raw-secret"}},
        {"scoring_schema": {"password": "raw-secret"}},
        {"safety_tags": ["safe", "safe"]},
        {"fixture_hash": "0" * 64},
    ],
)
def test_eval_case_rejects_secrets_duplicates_and_forged_hash(eval_candidate, overrides):
    """Fixture identity is derived only from bounded sanitized fields."""
    with pytest.raises(ValidationError):
        harness_models.HarnessEvalCase.objects.create(**eval_case_values(eval_candidate, **overrides))


def test_eval_run_records_versions_hashes_thresholds_and_signed_result(eval_candidate):
    """An external Eval result remains bound to its package, releases, and signature digest."""
    run = harness_models.HarnessEvalRun.objects.create(
        candidate=eval_candidate,
        base_release_version="agent-release-10",
        candidate_release_version="agent-release-11",
        runner_mode=harness_models.HarnessEvalRun.RunnerMode.SIGNED_BKAIDEV,
        package_hash="c" * 64,
        result_hash="d" * 64,
        signed_result_ref="eval-result://bkaidev/run-1",
        signed_result_digest="e" * 64,
        aggregate_metrics={"intent_completion_rate": 0.93, "case_count": 42},
        safety_result=harness_models.HarnessEvalRun.SafetyResult.PASSED,
        threshold_snapshot={"safety_regressions_max": 0, "mandatory_suite_pass_rate": 1.0},
        status=harness_models.HarnessEvalRun.Status.PASSED,
        started_at=timezone.now(),
        finalized_at=timezone.now(),
    )

    assert run.signed_result_digest == "e" * 64
    assert run.status == "PASSED"
    assert run.threshold_snapshot["safety_regressions_max"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"package_hash": "not-a-hash"},
        {"aggregate_metrics": {"secret": "raw-secret"}},
        {"threshold_snapshot": {"token": "raw-secret"}},
        {"signed_result_ref": None},
        {"signed_result_digest": None},
    ],
)
def test_passed_external_eval_rejects_unbound_or_secret_results(eval_candidate, overrides):
    """A signed external pass cannot omit authenticity or carry unsafe metadata."""
    values = {
        "candidate": eval_candidate,
        "base_release_version": "agent-release-10",
        "candidate_release_version": "agent-release-11",
        "runner_mode": "SIGNED_BKAIDEV",
        "package_hash": "c" * 64,
        "result_hash": "d" * 64,
        "signed_result_ref": "eval-result://bkaidev/run-1",
        "signed_result_digest": "e" * 64,
        "aggregate_metrics": {"case_count": 42},
        "safety_result": "PASSED",
        "threshold_snapshot": {"safety_regressions_max": 0},
        "status": "PASSED",
        "started_at": timezone.now(),
        "finalized_at": timezone.now(),
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        harness_models.HarnessEvalRun.objects.create(**values)
