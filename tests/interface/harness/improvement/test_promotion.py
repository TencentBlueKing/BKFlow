"""Verified external publication acknowledgment and rollback."""

from dataclasses import dataclass

import pytest

from bkflow.harness import models as harness_models
from bkflow.harness.constants import (
    FeedbackAttributionCategory,
    ImprovementCandidateStatus,
    ImprovementCandidateType,
)
from bkflow.harness.services.improvement.governance import (
    review_candidate,
    submit_candidate,
)
from bkflow.harness.services.improvement.promotion import (
    CandidatePromotionError,
    PromotionReadback,
    VerifiedPromotionReceipt,
    acknowledge_promotion,
    create_provider_draft,
    rollback_promotion,
)
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    create_space_binding,
    feedback_values,
)


@dataclass
class AllowPolicy:
    allowed: bool = True

    def allows(self, candidate):
        return self.allowed


@dataclass
class Gate:
    passed: bool = True

    def candidate_gate_passed(self, candidate):
        return self.passed


class Verifier:
    def __init__(self, receipt):
        self.receipt = receipt

    def verify(self, receipt_ref, candidate):
        assert receipt_ref == self.receipt.receipt_ref
        return self.receipt


class ReadbackProvider:
    def __init__(self, readbacks):
        self.readbacks = list(readbacks)

    def read_back(self, candidate, expected_version, expected_source_ref, immutable_change_ref):
        assert expected_version
        assert immutable_change_ref
        return self.readbacks.pop(0)


class DraftProvider:
    def __init__(self):
        self.calls = []

    def create_draft(self, candidate, package):
        self.calls.append((candidate.id, package["package_hash"]))
        return "external-draft://knowledge/draft-1"


def _approved_candidate(*, knowledge=True):
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    overrides = {"owner_ref": "candidate-owner", "reviewer_ref": "candidate-reviewer"}
    binding = None
    if not knowledge:
        overrides.update(
            {
                "candidate_type": ImprovementCandidateType.REGISTRY,
                "attribution": FeedbackAttributionCategory.RESOLVER,
                "target_system": "capability-registry",
                "target_tier": None,
                "target_platform_key": None,
                "target_space_id": None,
            }
        )
    candidate = harness_models.ImprovementCandidate.objects.create(**candidate_values(feedback, **overrides))
    if knowledge:
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
    candidate = review_candidate(candidate.id, operator="candidate-reviewer", decision="APPROVE")
    return candidate, binding


def _receipt(candidate, *, source_ref=None, target_version=None, change_ref="change://review/42"):
    return VerifiedPromotionReceipt(
        receipt_ref="promotion-receipt://provider/receipt-1",
        candidate_ref="candidate://improvement/{}".format(candidate.id),
        target_system=candidate.target_system,
        source_ref=source_ref,
        target_version=target_version or candidate.target_version,
        snapshot_version=target_version or candidate.target_version,
        immutable_change_ref=change_ref,
    )


@pytest.mark.django_db
def test_approved_knowledge_candidate_can_create_external_draft_but_not_publish():
    candidate, _binding = _approved_candidate()
    provider = DraftProvider()

    draft_ref = create_provider_draft(candidate.id, operator="candidate-owner", provider=provider)

    candidate.refresh_from_db()
    assert draft_ref == "external-draft://knowledge/draft-1"
    assert candidate.status == ImprovementCandidateStatus.APPROVED
    assert len(provider.calls) == 1


@pytest.mark.django_db
def test_knowledge_acknowledgment_verifies_readback_and_records_previous_snapshot():
    candidate, binding = _approved_candidate()
    receipt = _receipt(candidate, source_ref=binding.source_ref)
    readback = PromotionReadback(
        target_system=candidate.target_system,
        source_ref=binding.source_ref,
        target_version="snapshot-2",
        snapshot_version="snapshot-2",
        immutable_change_ref=receipt.immutable_change_ref,
    )

    published = acknowledge_promotion(
        candidate.id,
        operator="candidate-owner",
        receipt_ref=receipt.receipt_ref,
        expected_target_version="snapshot-2",
        policy=AllowPolicy(),
        gate=Gate(),
        verifier=Verifier(receipt),
        readback_provider=ReadbackProvider([readback]),
    )

    binding.refresh_from_db()
    assert published.status == ImprovementCandidateStatus.PUBLISHED
    assert len(published.promotion_receipt_digest) == 64
    assert binding.snapshot_version == "snapshot-2"
    event = published.source_feedback.run.evidence_events.get(event_type="IMPROVEMENT_CANDIDATE_PUBLISHED")
    assert event.redacted_payload["previous_version"] == "snapshot-1"
    assert event.redacted_payload["target_version"] == "snapshot-2"
    assert "receipt_ref" not in event.redacted_payload


@pytest.mark.django_db
def test_mismatched_or_unreadable_knowledge_snapshot_is_rejected_atomically():
    candidate, binding = _approved_candidate()
    receipt = _receipt(candidate, source_ref=binding.source_ref)
    mismatch = PromotionReadback(
        target_system=candidate.target_system,
        source_ref=binding.source_ref,
        target_version="snapshot-other",
        snapshot_version="snapshot-other",
        immutable_change_ref=receipt.immutable_change_ref,
    )

    with pytest.raises(CandidatePromotionError, match="READBACK_MISMATCH"):
        acknowledge_promotion(
            candidate.id,
            operator="candidate-owner",
            receipt_ref=receipt.receipt_ref,
            expected_target_version="snapshot-2",
            policy=AllowPolicy(),
            gate=Gate(),
            verifier=Verifier(receipt),
            readback_provider=ReadbackProvider([mismatch]),
        )

    candidate.refresh_from_db()
    binding.refresh_from_db()
    assert candidate.status == ImprovementCandidateStatus.APPROVED
    assert binding.snapshot_version == "snapshot-1"


@pytest.mark.django_db
def test_knowledge_rollback_restores_the_recorded_previous_snapshot_after_readback():
    candidate, binding = _approved_candidate()
    receipt = _receipt(candidate, source_ref=binding.source_ref)
    promoted = PromotionReadback(
        target_system=candidate.target_system,
        source_ref=binding.source_ref,
        target_version="snapshot-2",
        snapshot_version="snapshot-2",
        immutable_change_ref=receipt.immutable_change_ref,
    )
    published = acknowledge_promotion(
        candidate.id,
        operator="candidate-owner",
        receipt_ref=receipt.receipt_ref,
        expected_target_version="snapshot-2",
        policy=AllowPolicy(),
        gate=Gate(),
        verifier=Verifier(receipt),
        readback_provider=ReadbackProvider([promoted]),
    )
    rolled_back = PromotionReadback(
        target_system=candidate.target_system,
        source_ref=binding.source_ref,
        target_version="snapshot-1",
        snapshot_version="snapshot-1",
        immutable_change_ref="change://rollback/43",
    )

    rollback_promotion(
        published.id,
        operator="candidate-owner",
        reason="Owner restored the prior governed snapshot.",
        immutable_change_ref="change://rollback/43",
        policy=AllowPolicy(False),
        readback_provider=ReadbackProvider([rolled_back]),
    )

    binding.refresh_from_db()
    assert binding.snapshot_version == "snapshot-1"


@pytest.mark.django_db
def test_non_knowledge_publication_requires_eval_gate_and_immutable_change_ref():
    candidate, _binding = _approved_candidate(knowledge=False)
    missing_change = _receipt(candidate, change_ref=None)
    readback = PromotionReadback(
        target_system=candidate.target_system,
        source_ref=None,
        target_version="snapshot-2",
        snapshot_version="snapshot-2",
        immutable_change_ref=None,
    )

    with pytest.raises(CandidatePromotionError, match="EVAL_GATE_REQUIRED"):
        acknowledge_promotion(
            candidate.id,
            operator="candidate-owner",
            receipt_ref=missing_change.receipt_ref,
            expected_target_version="snapshot-2",
            policy=AllowPolicy(),
            gate=Gate(False),
            verifier=Verifier(missing_change),
            readback_provider=ReadbackProvider([readback]),
        )
    with pytest.raises(CandidatePromotionError, match="RECEIPT_INVALID"):
        acknowledge_promotion(
            candidate.id,
            operator="candidate-owner",
            receipt_ref=missing_change.receipt_ref,
            expected_target_version="snapshot-2",
            policy=AllowPolicy(),
            gate=Gate(),
            verifier=Verifier(missing_change),
            readback_provider=ReadbackProvider([readback]),
        )


@pytest.mark.django_db
def test_non_knowledge_ack_and_verified_rollback_reach_published_then_retired():
    candidate, _binding = _approved_candidate(knowledge=False)
    receipt = _receipt(candidate)
    promoted = PromotionReadback(
        target_system=candidate.target_system,
        source_ref=None,
        target_version="snapshot-2",
        snapshot_version="snapshot-2",
        immutable_change_ref=receipt.immutable_change_ref,
    )
    published = acknowledge_promotion(
        candidate.id,
        operator="candidate-owner",
        receipt_ref=receipt.receipt_ref,
        expected_target_version="snapshot-2",
        policy=AllowPolicy(),
        gate=Gate(),
        verifier=Verifier(receipt),
        readback_provider=ReadbackProvider([promoted]),
    )
    rolled_back = PromotionReadback(
        target_system=candidate.target_system,
        source_ref=None,
        target_version="snapshot-1",
        snapshot_version="snapshot-1",
        immutable_change_ref="change://rollback/43",
    )

    retired = rollback_promotion(
        published.id,
        operator="candidate-owner",
        reason="Regression detected by the governed canary.",
        immutable_change_ref="change://rollback/43",
        policy=AllowPolicy(),
        readback_provider=ReadbackProvider([rolled_back]),
    )

    assert retired.status == ImprovementCandidateStatus.RETIRED
    rollback_event = retired.source_feedback.run.evidence_events.get(event_type="IMPROVEMENT_CANDIDATE_ROLLED_BACK")
    assert rollback_event.redacted_payload["target_version"] == "snapshot-1"
    assert rollback_event.redacted_payload["operator"] == "candidate-owner"


@pytest.mark.django_db
def test_promotion_flag_is_independent_and_denies_by_default_policy():
    candidate, binding = _approved_candidate()
    receipt = _receipt(candidate, source_ref=binding.source_ref)

    with pytest.raises(CandidatePromotionError, match="PROMOTION_DISABLED"):
        acknowledge_promotion(
            candidate.id,
            operator="candidate-owner",
            receipt_ref=receipt.receipt_ref,
            expected_target_version="snapshot-2",
            policy=AllowPolicy(False),
            gate=Gate(),
            verifier=Verifier(receipt),
            readback_provider=ReadbackProvider([]),
        )
