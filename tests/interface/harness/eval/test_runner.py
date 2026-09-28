"""Local deterministic Eval package and invariant runner."""

import pytest

from bkflow.harness.models import HarnessEvalRun
from bkflow.harness.services.eval.runner import build_eval_package, run_local_eval
from tests.interface.harness.eval.p4_eval_support import (
    approved_knowledge_candidate,
    create_mandatory_cases,
    passing_observations,
    resolved_thresholds,
)


@pytest.mark.django_db
def test_package_pins_cases_releases_contract_agent_release_and_knowledge_snapshot():
    candidate = approved_knowledge_candidate()
    cases = create_mandatory_cases(candidate)

    first = build_eval_package(candidate, bkaidev_agent_release="agent-release-42")
    second = build_eval_package(candidate, bkaidev_agent_release="agent-release-42")

    assert first == second
    assert first["package_hash"] == second["package_hash"]
    assert first["mcp_contract_version"] == "1.4.0"
    assert first["bkaidev_agent_release"] == "agent-release-42"
    assert first["versions"] == {"base": "snapshot-1", "candidate": "snapshot-2"}
    assert first["knowledge_snapshots"] == [
        {"source_ref": candidate.knowledge_candidate.target_source_ref, "base": "snapshot-1", "candidate": "snapshot-2"}
    ]
    assert {item["fixture_hash"] for item in first["cases"]} == {case.fixture_hash for case in cases}


@pytest.mark.django_db
def test_local_runner_covers_every_mandatory_suite_without_an_llm():
    candidate = approved_knowledge_candidate()
    cases = create_mandatory_cases(candidate)

    eval_run = run_local_eval(
        candidate.id,
        bkaidev_agent_release="agent-release-42",
        observations=passing_observations(cases),
        thresholds=resolved_thresholds(),
    )

    assert eval_run.runner_mode == HarnessEvalRun.RunnerMode.LOCAL_DETERMINISTIC
    assert eval_run.status == HarnessEvalRun.Status.PASSED
    assert eval_run.safety_result == HarnessEvalRun.SafetyResult.PASSED
    assert eval_run.aggregate_metrics["mandatory_suite_pass_rate"] == 1.0
    assert set(eval_run.aggregate_metrics["suite_results"]) == {
        "resolver",
        "schema",
        "validation",
        "acl",
        "policy",
        "postcondition",
        "security",
    }
    assert eval_run.signed_result_ref is None


@pytest.mark.django_db
def test_local_safety_failure_cannot_be_offset_by_other_passing_cases():
    candidate = approved_knowledge_candidate()
    cases = create_mandatory_cases(candidate)
    observations = passing_observations(cases)
    security = next(case for case in cases if case.expected_invariants["suite"] == "security")
    observations[security.fixture_hash] = {"passed": False}

    eval_run = run_local_eval(
        candidate.id,
        bkaidev_agent_release="agent-release-42",
        observations=observations,
        thresholds=resolved_thresholds(),
    )

    assert eval_run.status == HarnessEvalRun.Status.FAILED
    assert eval_run.aggregate_metrics["sensitive_data_regressions"] == 1
    assert eval_run.aggregate_metrics["passed_case_count"] == len(cases) - 1
