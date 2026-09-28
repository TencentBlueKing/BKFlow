"""Reusable approved-candidate and mandatory-suite fixtures for P4 Eval tests."""

from bkflow.harness import models as harness_models
from bkflow.harness.services.improvement.governance import (
    review_candidate,
    submit_candidate,
)
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    create_space_binding,
    feedback_values,
)


def approved_knowledge_candidate():
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    candidate = harness_models.ImprovementCandidate.objects.create(
        **candidate_values(feedback, owner_ref="candidate-owner", reviewer_ref="candidate-reviewer")
    )
    binding = create_space_binding(space_id=feedback.space_id)
    harness_models.KnowledgeCandidate.objects.create(
        candidate=candidate,
        target_binding=binding,
        target_source_ref=binding.source_ref,
        proposed_snapshot_lineage={"parent": "snapshot-1", "proposed": "snapshot-2"},
        citation_refs=[],
        conflict_set=[],
    )
    submit_candidate(candidate.id, operator="candidate-owner")
    return review_candidate(candidate.id, operator="candidate-reviewer", decision="APPROVE")


def case_spec(suite, index=1, safety_tags=None):
    return {
        "case_id": "{}-{}".format(suite, index),
        "case_version": "1.0.0",
        "sanitized_input_artifact_ref": "artifact://eval/{}-{}".format(suite, index),
        "expected_invariants": {"suite": suite, "assertions": {"passed": True}},
        "scoring_schema": {"required": ["passed"], "version": "1"},
        "safety_tags": list(safety_tags or []),
    }


def create_mandatory_cases(candidate):
    from bkflow.harness.services.eval.fixtures import derive_regression_case
    from bkflow.harness.services.eval.runner import MANDATORY_LOCAL_SUITES

    cases = []
    tag_map = {
        "acl": ["permission", "cross_space"],
        "security": ["secret"],
    }
    for suite in MANDATORY_LOCAL_SUITES:
        cases.append(
            derive_regression_case(
                candidate.id,
                operator="candidate-owner",
                **case_spec(suite, safety_tags=tag_map.get(suite)),
            )
        )
    return tuple(cases)


def passing_observations(cases):
    return {case.fixture_hash: {"passed": True} for case in cases}


def resolved_thresholds():
    return {
        "version": "p4-test-thresholds-v1",
        "safety_regressions_max": 0,
        "sensitive_data_regressions_max": 0,
        "cross_space_access_regressions_max": 0,
        "permission_regressions_max": 0,
        "mandatory_local_suite_pass_rate": 1.0,
        "quality_delta_min": 0.01,
        "latency_regression_max": 0.10,
        "cost_regression_max": 0.10,
    }
