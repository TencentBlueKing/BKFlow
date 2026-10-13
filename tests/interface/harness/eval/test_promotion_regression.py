"""P4 promotion regression over local contract stubs, never live external evidence."""

from dataclasses import dataclass

import pytest

from bkflow.harness.constants import ImprovementCandidateStatus
from bkflow.harness.services.eval.gate import CandidateEvalGate
from bkflow.harness.services.eval.runner import (
    SignedEvalVerification,
    build_eval_package,
    import_signed_bkaidev_result,
    run_local_eval,
)
from bkflow.harness.services.improvement.promotion import (
    CandidatePromotionError,
    PromotionReadback,
    VerifiedPromotionReceipt,
    acknowledge_promotion,
    rollback_promotion,
)
from tests.interface.harness.eval.p4_eval_support import (
    approved_knowledge_candidate,
    create_mandatory_cases,
    passing_observations,
    resolved_thresholds,
)


@dataclass(frozen=True)
class _SignatureVerifier:
    def verify(self, document):
        return SignedEvalVerification(
            signer_ref="signer://p4-contract-stub/bkaidev",
            receipt_ref="eval-receipt://p4-contract-stub/result-1",
            signed_result_ref="eval-result://p4-contract-stub/result-1",
            signed_result_digest="e" * 64,
        )


@dataclass(frozen=True)
class _AllowPolicy:
    def allows(self, candidate):
        return True


class _PromotionVerifier:
    def __init__(self, receipt):
        self.receipt = receipt

    def verify(self, receipt_ref, candidate):
        assert receipt_ref == self.receipt.receipt_ref
        return self.receipt


class _Readbacks:
    def __init__(self, *readbacks):
        self.readbacks = list(readbacks)

    def read_back(self, candidate, expected_version, expected_source_ref, immutable_change_ref):
        assert expected_version
        assert immutable_change_ref
        return self.readbacks.pop(0)


def _signed_document(candidate, package, cases, **overrides):
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
    metrics.update(overrides)
    return {
        "schema_version": "p4-bkaidev-eval-result-v1",
        "candidate_ref": "candidate://improvement/{}".format(candidate.id),
        "package_hash": package["package_hash"],
        "bkaidev_agent_release": "agent-release-p4-contract-stub",
        "mcp_contract_version": "1.4.0",
        "base_release_version": candidate.current_version,
        "candidate_release_version": candidate.target_version,
        "case_results": [{"fixture_hash": case.fixture_hash, "passed": True} for case in cases],
        "aggregate_metrics": metrics,
        "signature": {"algorithm": "contract-stub", "value": "opaque-to-test-verifier"},
    }


def _prepare_eval(candidate, **metric_overrides):
    cases = create_mandatory_cases(candidate)
    thresholds = resolved_thresholds()
    run_local_eval(
        candidate.id,
        bkaidev_agent_release="agent-release-p4-contract-stub",
        observations=passing_observations(cases),
        thresholds=thresholds,
    )
    package = build_eval_package(candidate, bkaidev_agent_release="agent-release-p4-contract-stub")
    import_signed_bkaidev_result(
        candidate.id,
        document=_signed_document(candidate, package, cases, **metric_overrides),
        verifier=_SignatureVerifier(),
        thresholds=thresholds,
    )
    return CandidateEvalGate(thresholds)


def _receipt(candidate):
    return VerifiedPromotionReceipt(
        receipt_ref="promotion-receipt://p4-contract-stub/publication-1",
        candidate_ref="candidate://improvement/{}".format(candidate.id),
        target_system=candidate.target_system,
        source_ref=candidate.knowledge_candidate.target_source_ref,
        target_version=candidate.target_version,
        snapshot_version=candidate.target_version,
        immutable_change_ref="change://p4-contract-stub/publication-1",
    )


def _readback(candidate, version, change_ref):
    return PromotionReadback(
        target_system=candidate.target_system,
        source_ref=candidate.knowledge_candidate.target_source_ref,
        target_version=version,
        snapshot_version=version,
        immutable_change_ref=change_ref,
    )


@pytest.mark.django_db
def test_signed_eval_publication_and_rollback_protocol_is_complete_only_under_explicit_contract_stubs():
    """Exercise all proof checks while keeping the result distinct from a live Provider acceptance."""
    candidate = approved_knowledge_candidate()
    gate = _prepare_eval(candidate)
    assert gate.evaluate(candidate).passed is True
    binding = candidate.knowledge_candidate.target_binding
    receipt = _receipt(candidate)

    published = acknowledge_promotion(
        candidate.id,
        operator=candidate.owner_ref,
        receipt_ref=receipt.receipt_ref,
        expected_target_version=candidate.target_version,
        policy=_AllowPolicy(),
        gate=gate,
        verifier=_PromotionVerifier(receipt),
        readback_provider=_Readbacks(_readback(candidate, "snapshot-2", receipt.immutable_change_ref)),
    )

    binding.refresh_from_db()
    assert published.status == ImprovementCandidateStatus.PUBLISHED
    assert binding.snapshot_version == "snapshot-2"
    rollback_ref = "change://p4-contract-stub/rollback-1"
    retired = rollback_promotion(
        published.id,
        operator=published.owner_ref,
        reason="Contract-stub regression rollback.",
        immutable_change_ref=rollback_ref,
        policy=_AllowPolicy(),
        readback_provider=_Readbacks(_readback(published, "snapshot-1", rollback_ref)),
    )

    binding.refresh_from_db()
    assert retired.status == ImprovementCandidateStatus.RETIRED
    assert binding.snapshot_version == "snapshot-1"
    assert retired.promotion_receipt_digest
    event_types = set(retired.source_feedback.run.evidence_events.values_list("event_type", flat=True))
    assert {"BKAIDEV_EVAL_IMPORTED", "IMPROVEMENT_CANDIDATE_PUBLISHED", "IMPROVEMENT_CANDIDATE_ROLLED_BACK"}.issubset(
        event_types
    )


@pytest.mark.django_db
def test_signed_safety_regression_blocks_promotion_before_any_destination_verifier_call():
    candidate = approved_knowledge_candidate()
    gate = _prepare_eval(candidate, safety_regressions=1, sensitive_data_regressions=1)
    receipt = _receipt(candidate)

    decision = gate.evaluate(candidate)
    assert decision.passed is False
    assert "SAFETY_REGRESSION" in decision.reasons
    with pytest.raises(CandidatePromotionError, match="EVAL_GATE_REQUIRED"):
        acknowledge_promotion(
            candidate.id,
            operator=candidate.owner_ref,
            receipt_ref=receipt.receipt_ref,
            expected_target_version=candidate.target_version,
            policy=_AllowPolicy(),
            gate=gate,
            verifier=_PromotionVerifier(receipt),
            readback_provider=_Readbacks(),
        )
    candidate.refresh_from_db()
    assert candidate.status == ImprovementCandidateStatus.APPROVED
