"""Type-specific zero-regression promotion gate."""

from dataclasses import dataclass

import pytest

from bkflow.harness.services.eval.gate import CandidateEvalGate
from bkflow.harness.services.eval.runner import (
    SignedEvalVerification,
    build_eval_package,
    import_signed_bkaidev_result,
    run_local_eval,
)
from tests.interface.harness.eval.p4_eval_support import (
    approved_knowledge_candidate,
    create_mandatory_cases,
    passing_observations,
    resolved_thresholds,
)


@dataclass
class SignatureVerifier:
    verification: object

    def verify(self, document):
        return self.verification


def _signed_document(candidate, package, cases, **metric_overrides):
    metrics = {
        "case_count": len(cases),
        "passed_case_count": len(cases),
        "quality_delta": 0.05,
        "latency_regression": 0.02,
        "cost_regression": 0.03,
        "safety_regressions": 0,
        "sensitive_data_regressions": 0,
        "cross_space_access_regressions": 0,
        "permission_regressions": 0,
    }
    metrics.update(metric_overrides)
    return {
        "schema_version": "p4-bkaidev-eval-result-v1",
        "candidate_ref": "candidate://improvement/{}".format(candidate.id),
        "package_hash": package["package_hash"],
        "bkaidev_agent_release": "agent-release-42",
        "mcp_contract_version": "1.4.0",
        "base_release_version": candidate.current_version,
        "candidate_release_version": candidate.target_version,
        "case_results": [{"fixture_hash": case.fixture_hash, "passed": True} for case in cases],
        "aggregate_metrics": metrics,
        "signature": {"algorithm": "platform-managed", "value": "opaque-to-verifier"},
    }


def _verification():
    return SignedEvalVerification(
        signer_ref="signer://bkaidev/eval-service",
        receipt_ref="eval-receipt://bkaidev/result-1",
        signed_result_ref="eval-result://bkaidev/result-1",
        signed_result_digest="e" * 64,
    )


@pytest.mark.django_db
def test_model_affecting_knowledge_candidate_requires_local_and_signed_external_passes():
    candidate = approved_knowledge_candidate()
    cases = create_mandatory_cases(candidate)
    thresholds = resolved_thresholds()
    run_local_eval(
        candidate.id,
        bkaidev_agent_release="agent-release-42",
        observations=passing_observations(cases),
        thresholds=thresholds,
    )
    gate = CandidateEvalGate(thresholds)
    assert gate.evaluate(candidate).reasons == ("SIGNED_BKAIDEV_EVAL_REQUIRED",)

    package = build_eval_package(candidate, bkaidev_agent_release="agent-release-42")
    import_signed_bkaidev_result(
        candidate.id,
        document=_signed_document(candidate, package, cases),
        verifier=SignatureVerifier(_verification()),
        thresholds=thresholds,
    )

    assert gate.evaluate(candidate).passed is True
    assert gate.candidate_gate_passed(candidate) is True


@pytest.mark.django_db
def test_safety_regression_blocks_even_when_quality_improves():
    candidate = approved_knowledge_candidate()
    cases = create_mandatory_cases(candidate)
    thresholds = resolved_thresholds()
    run_local_eval(
        candidate.id,
        bkaidev_agent_release="agent-release-42",
        observations=passing_observations(cases),
        thresholds=thresholds,
    )
    package = build_eval_package(candidate, bkaidev_agent_release="agent-release-42")
    document = _signed_document(
        candidate,
        package,
        cases,
        quality_delta=0.99,
        sensitive_data_regressions=1,
        safety_regressions=1,
    )
    import_signed_bkaidev_result(
        candidate.id,
        document=document,
        verifier=SignatureVerifier(_verification()),
        thresholds=thresholds,
    )

    decision = CandidateEvalGate(thresholds).evaluate(candidate)
    assert decision.passed is False
    assert "SAFETY_REGRESSION" in decision.reasons


@pytest.mark.django_db
def test_unresolved_frozen_thresholds_fail_closed():
    candidate = approved_knowledge_candidate()

    decision = CandidateEvalGate().evaluate(candidate)

    assert decision.passed is False
    assert decision.reasons == ("THRESHOLDS_UNRESOLVED",)
