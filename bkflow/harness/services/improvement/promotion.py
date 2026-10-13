"""External-only promotion acknowledgment and verified rollback for P4 candidates."""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from bkflow.harness.constants import (
    ImprovementCandidateStatus,
    ImprovementCandidateType,
)
from bkflow.harness.models import (
    ImprovementCandidate,
    KnowledgeCandidate,
    KnowledgeSourceBinding,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.contract_versions import (
    is_harness_candidate_promotion_enabled,
)
from bkflow.harness.services.evidence import is_safe_evidence_ref, record_evidence
from bkflow.harness.services.improvement.governance import _save_status
from bkflow.harness.services.improvement.package import build_candidate_review_package
from bkflow.harness.services.knowledge.security import is_bounded_non_secret_text


class CandidatePromotionError(ValueError):
    """Stable, non-reflective rejection at an external governance boundary."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VerifiedPromotionReceipt:
    """Normalized receipt facts returned by an authenticated destination verifier."""

    receipt_ref: str
    candidate_ref: str
    target_system: str
    source_ref: object
    target_version: str
    snapshot_version: str
    immutable_change_ref: object


@dataclass(frozen=True)
class PromotionReadback:
    """Exact destination state read independently after external publication or rollback."""

    target_system: str
    source_ref: object
    target_version: str
    snapshot_version: str
    immutable_change_ref: object


class SpaceConfigPromotionPolicy:
    """Production policy backed only by the private Owner-controlled feature switch."""

    def allows(self, candidate):
        return is_harness_candidate_promotion_enabled(candidate.source_feedback.space_id)


class DenyPromotionGate:
    """Fail closed until Task 8 connects complete local and signed external Eval evidence."""

    def candidate_gate_passed(self, candidate):
        return False


class DenyPromotionVerifier:
    """Fail closed until an authenticated destination receipt verifier is configured."""

    def verify(self, receipt_ref, candidate):
        raise CandidatePromotionError("RECEIPT_UNREADABLE")


class DenyPromotionReadbackProvider:
    """Fail closed until an authenticated destination readback adapter is configured."""

    def read_back(self, candidate, expected_version, expected_source_ref, immutable_change_ref):
        raise CandidatePromotionError("READBACK_UNAVAILABLE")


def _policy_allows(policy, candidate):
    try:
        return policy.allows(candidate) is True
    except Exception:
        return False


def _gate_passed(gate, candidate):
    try:
        return gate.candidate_gate_passed(candidate) is True
    except Exception:
        return False


def _knowledge(candidate):
    if candidate.candidate_type != ImprovementCandidateType.KNOWLEDGE:
        return None
    try:
        return candidate.knowledge_candidate
    except KnowledgeCandidate.DoesNotExist:
        raise CandidatePromotionError("KNOWLEDGE_TARGET_MISSING") from None


def _event(candidate, event_type, operator, payload):
    body = {
        "candidate_ref": "candidate://improvement/{}".format(candidate.id),
        "candidate_revision": candidate.revision_number,
        "operator": operator,
    }
    body.update(payload)
    return record_evidence(
        run=candidate.source_feedback.run,
        revision=candidate.source_feedback.revision,
        event_type=event_type,
        action="promote_improvement_candidate",
        payload=body,
        actor=candidate.source_feedback.actor,
        correlation_id="candidate-promotion-{}".format(candidate.id),
    )


def _validate_receipt(receipt, receipt_ref, candidate, expected_source_ref, expected_target_version):
    if (
        not isinstance(receipt, VerifiedPromotionReceipt)
        or receipt.receipt_ref != receipt_ref
        or not is_safe_evidence_ref(receipt_ref)
        or receipt.candidate_ref != "candidate://improvement/{}".format(candidate.id)
        or receipt.target_system != candidate.target_system
        or receipt.source_ref != expected_source_ref
        or receipt.target_version != expected_target_version
        or receipt.snapshot_version != expected_target_version
        or not is_safe_evidence_ref(receipt.immutable_change_ref)
    ):
        raise CandidatePromotionError("RECEIPT_INVALID")


def _read_back(readback_provider, candidate, expected_version, expected_source_ref, immutable_change_ref):
    try:
        readback = readback_provider.read_back(
            candidate,
            expected_version,
            expected_source_ref,
            immutable_change_ref,
        )
    except CandidatePromotionError:
        raise
    except Exception:
        raise CandidatePromotionError("READBACK_UNAVAILABLE") from None
    if (
        not isinstance(readback, PromotionReadback)
        or readback.target_system != candidate.target_system
        or readback.source_ref != expected_source_ref
        or readback.target_version != expected_version
        or readback.snapshot_version != expected_version
        or readback.immutable_change_ref != immutable_change_ref
        or not is_safe_evidence_ref(readback.immutable_change_ref)
    ):
        raise CandidatePromotionError("READBACK_MISMATCH")
    return readback


def create_provider_draft(candidate_id, *, operator, provider):
    """Ask a knowledge provider for a draft only; never acknowledge or publish it locally."""
    candidate = ImprovementCandidate.objects.select_related("source_feedback__run").get(pk=candidate_id)
    if candidate.status != ImprovementCandidateStatus.APPROVED:
        raise CandidatePromotionError("CANDIDATE_NOT_APPROVED")
    if candidate.owner_ref is None or operator != candidate.owner_ref:
        raise CandidatePromotionError("OWNER_REQUIRED")
    _knowledge(candidate)
    try:
        draft_ref = provider.create_draft(candidate, build_candidate_review_package(candidate))
    except Exception:
        raise CandidatePromotionError("PROVIDER_DRAFT_FAILED") from None
    if not is_safe_evidence_ref(draft_ref):
        raise CandidatePromotionError("PROVIDER_DRAFT_FAILED")
    with transaction.atomic():
        locked = (
            ImprovementCandidate.objects.select_for_update().select_related("source_feedback__run").get(pk=candidate_id)
        )
        if locked.status != ImprovementCandidateStatus.APPROVED or locked.owner_ref != operator:
            raise CandidatePromotionError("CANDIDATE_STATE_CHANGED")
        _event(
            locked,
            "IMPROVEMENT_CANDIDATE_EXTERNAL_DRAFTED",
            operator,
            {"draft_ref": draft_ref, "status": locked.status},
        )
    return draft_ref


def acknowledge_promotion(
    candidate_id,
    *,
    operator,
    receipt_ref,
    expected_target_version,
    policy,
    gate,
    verifier,
    readback_provider,
):
    """Record PUBLISHED only after feature, Eval, receipt, and exact readback checks all pass."""
    candidate = ImprovementCandidate.objects.select_related("source_feedback__run").get(pk=candidate_id)
    if candidate.status != ImprovementCandidateStatus.APPROVED:
        raise CandidatePromotionError("CANDIDATE_NOT_APPROVED")
    if candidate.owner_ref is None or operator != candidate.owner_ref:
        raise CandidatePromotionError("OWNER_REQUIRED")
    if expected_target_version != candidate.target_version:
        raise CandidatePromotionError("TARGET_VERSION_MISMATCH")
    if not _policy_allows(policy, candidate):
        raise CandidatePromotionError("PROMOTION_DISABLED")
    if not _gate_passed(gate, candidate):
        raise CandidatePromotionError("EVAL_GATE_REQUIRED")
    if not is_safe_evidence_ref(receipt_ref):
        raise CandidatePromotionError("RECEIPT_INVALID")

    knowledge = _knowledge(candidate)
    expected_source_ref = knowledge.target_source_ref if knowledge is not None else None
    try:
        receipt = verifier.verify(receipt_ref, candidate)
    except CandidatePromotionError:
        raise
    except Exception:
        raise CandidatePromotionError("RECEIPT_UNREADABLE") from None
    _validate_receipt(receipt, receipt_ref, candidate, expected_source_ref, expected_target_version)
    _read_back(
        readback_provider,
        candidate,
        expected_target_version,
        expected_source_ref,
        receipt.immutable_change_ref,
    )
    receipt_digest = sha256_json(
        {
            "receipt_ref": receipt.receipt_ref,
            "candidate_ref": receipt.candidate_ref,
            "target_system": receipt.target_system,
            "source_ref": receipt.source_ref,
            "target_version": receipt.target_version,
            "snapshot_version": receipt.snapshot_version,
            "immutable_change_ref": receipt.immutable_change_ref,
        }
    )

    with transaction.atomic():
        locked = (
            ImprovementCandidate.objects.select_for_update().select_related("source_feedback__run").get(pk=candidate_id)
        )
        if locked.status != ImprovementCandidateStatus.APPROVED or locked.owner_ref != operator:
            raise CandidatePromotionError("CANDIDATE_STATE_CHANGED")
        if not _policy_allows(policy, locked) or not _gate_passed(gate, locked):
            raise CandidatePromotionError("PROMOTION_GUARD_CHANGED")
        locked_knowledge = _knowledge(locked)
        previous_version = locked.current_version
        source_ref = None
        if locked_knowledge is not None:
            binding = KnowledgeSourceBinding.objects.select_for_update().get(pk=locked_knowledge.target_binding_id)
            if binding.source_ref != expected_source_ref or binding.snapshot_version != locked.current_version:
                raise CandidatePromotionError("KNOWLEDGE_BINDING_CHANGED")
            previous_version = binding.snapshot_version
            source_ref = binding.source_ref
            binding.snapshot_version = expected_target_version
            binding.last_verified_at = timezone.now()
            binding.save(update_fields=["snapshot_version", "last_verified_at"])
        _save_status(locked, ImprovementCandidateStatus.PUBLISHED, receipt_digest=receipt_digest)
        _event(
            locked,
            "IMPROVEMENT_CANDIDATE_PUBLISHED",
            operator,
            {
                "target_system": locked.target_system,
                "source_ref": source_ref,
                "previous_version": previous_version,
                "target_version": expected_target_version,
                "immutable_change_ref": receipt.immutable_change_ref,
                "receipt_digest": receipt_digest,
                "status": locked.status,
            },
        )
        return locked


def rollback_promotion(
    candidate_id,
    *,
    operator,
    reason,
    immutable_change_ref,
    policy,
    readback_provider,
):
    """Retire only after the Owner's external rollback is independently read back."""
    del policy  # Rollback stays available even when the promotion flag has since been disabled.
    candidate = ImprovementCandidate.objects.select_related("source_feedback__run").get(pk=candidate_id)
    if candidate.status != ImprovementCandidateStatus.PUBLISHED:
        raise CandidatePromotionError("CANDIDATE_NOT_PUBLISHED")
    if candidate.owner_ref is None or operator != candidate.owner_ref:
        raise CandidatePromotionError("OWNER_REQUIRED")
    if not is_bounded_non_secret_text(reason, 1024) or not is_safe_evidence_ref(immutable_change_ref):
        raise CandidatePromotionError("ROLLBACK_EVIDENCE_INVALID")
    publication = candidate.source_feedback.run.evidence_events.filter(
        event_type="IMPROVEMENT_CANDIDATE_PUBLISHED",
        redacted_payload__candidate_ref="candidate://improvement/{}".format(candidate.id),
    ).last()
    if publication is None:
        raise CandidatePromotionError("PUBLICATION_EVIDENCE_MISSING")
    previous_version = publication.redacted_payload.get("previous_version")
    expected_source_ref = publication.redacted_payload.get("source_ref")
    if not is_bounded_non_secret_text(previous_version, 128):
        raise CandidatePromotionError("PUBLICATION_EVIDENCE_INVALID")
    _read_back(
        readback_provider,
        candidate,
        previous_version,
        expected_source_ref,
        immutable_change_ref,
    )

    with transaction.atomic():
        locked = (
            ImprovementCandidate.objects.select_for_update().select_related("source_feedback__run").get(pk=candidate_id)
        )
        if locked.status != ImprovementCandidateStatus.PUBLISHED or locked.owner_ref != operator:
            raise CandidatePromotionError("CANDIDATE_STATE_CHANGED")
        locked_knowledge = _knowledge(locked)
        if locked_knowledge is not None:
            binding = KnowledgeSourceBinding.objects.select_for_update().get(pk=locked_knowledge.target_binding_id)
            if binding.source_ref != expected_source_ref or binding.snapshot_version != locked.target_version:
                raise CandidatePromotionError("KNOWLEDGE_BINDING_CHANGED")
            binding.snapshot_version = previous_version
            binding.last_verified_at = timezone.now()
            binding.save(update_fields=["snapshot_version", "last_verified_at"])
        _save_status(locked, ImprovementCandidateStatus.RETIRED)
        _event(
            locked,
            "IMPROVEMENT_CANDIDATE_ROLLED_BACK",
            operator,
            {
                "target_system": locked.target_system,
                "source_ref": expected_source_ref,
                "target_version": previous_version,
                "reason": reason,
                "immutable_change_ref": immutable_change_ref,
                "verified_readback": True,
                "status": locked.status,
            },
        )
        return locked
