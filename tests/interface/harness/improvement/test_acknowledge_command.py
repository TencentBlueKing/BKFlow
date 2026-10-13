"""Apply-gated command wrapper for verified external promotion receipts."""

from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

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
    PromotionReadback,
    VerifiedPromotionReceipt,
)
from tests.interface.harness.improvement.test_promotion import (
    AllowPolicy,
    Gate,
    ReadbackProvider,
    Verifier,
)
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    feedback_values,
)


def _approved_registry_candidate():
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    candidate = harness_models.ImprovementCandidate.objects.create(
        **candidate_values(
            feedback,
            candidate_type=ImprovementCandidateType.REGISTRY,
            attribution=FeedbackAttributionCategory.RESOLVER,
            owner_ref="candidate-owner",
            reviewer_ref="candidate-reviewer",
            target_system="capability-registry",
            target_tier=None,
            target_platform_key=None,
            target_space_id=None,
        )
    )
    submit_candidate(candidate.id, operator="candidate-owner")
    return review_candidate(candidate.id, operator="candidate-reviewer", decision="APPROVE")


@pytest.mark.django_db
def test_command_is_dry_run_without_apply_and_never_changes_status(capsys):
    candidate = _approved_registry_candidate()

    call_command(
        "acknowledge_harness_promotion",
        candidate_id=str(candidate.id),
        receipt_ref="promotion-receipt://provider/receipt-1",
        expected_target_version="snapshot-2",
    )

    candidate.refresh_from_db()
    assert candidate.status == ImprovementCandidateStatus.APPROVED
    assert "mode=dry-run" in capsys.readouterr().out


@pytest.mark.django_db
def test_apply_command_uses_verified_adapters_and_publishes_exact_candidate():
    candidate = _approved_registry_candidate()
    receipt = VerifiedPromotionReceipt(
        receipt_ref="promotion-receipt://provider/receipt-1",
        candidate_ref="candidate://improvement/{}".format(candidate.id),
        target_system=candidate.target_system,
        source_ref=None,
        target_version="snapshot-2",
        snapshot_version="snapshot-2",
        immutable_change_ref="change://review/42",
    )
    readback = PromotionReadback(
        target_system=candidate.target_system,
        source_ref=None,
        target_version="snapshot-2",
        snapshot_version="snapshot-2",
        immutable_change_ref="change://review/42",
    )

    with patch(
        "bkflow.harness.management.commands.acknowledge_harness_promotion.production_policy",
        return_value=AllowPolicy(),
    ), patch(
        "bkflow.harness.management.commands.acknowledge_harness_promotion.production_gate",
        return_value=Gate(),
    ), patch(
        "bkflow.harness.management.commands.acknowledge_harness_promotion.production_verifier",
        return_value=Verifier(receipt),
    ), patch(
        "bkflow.harness.management.commands.acknowledge_harness_promotion.production_readback_provider",
        return_value=ReadbackProvider([readback]),
    ):
        call_command(
            "acknowledge_harness_promotion",
            candidate_id=str(candidate.id),
            receipt_ref=receipt.receipt_ref,
            expected_target_version="snapshot-2",
            operator="candidate-owner",
            apply=True,
        )

    candidate.refresh_from_db()
    assert candidate.status == ImprovementCandidateStatus.PUBLISHED


@pytest.mark.django_db
def test_apply_command_requires_operator_and_safe_receipt_ref():
    candidate = _approved_registry_candidate()
    with pytest.raises(CommandError, match="OPERATOR_REQUIRED"):
        call_command(
            "acknowledge_harness_promotion",
            candidate_id=str(candidate.id),
            receipt_ref="promotion-receipt://provider/receipt-1",
            expected_target_version="snapshot-2",
            apply=True,
        )
    with pytest.raises(CommandError, match="PROMOTION_ACKNOWLEDGMENT_INVALID"):
        call_command(
            "acknowledge_harness_promotion",
            candidate_id=str(candidate.id),
            receipt_ref="https://provider.example/receipt?token=secret",
            expected_target_version="snapshot-2",
            operator="candidate-owner",
            apply=True,
        )
