"""Apply-gated wrapper for externally verified candidate promotion acknowledgment."""

from django.core.management.base import BaseCommand, CommandError

from bkflow.harness.models import ImprovementCandidate
from bkflow.harness.services.eval.gate import CandidateEvalGate
from bkflow.harness.services.evidence import is_safe_evidence_ref
from bkflow.harness.services.improvement.promotion import (
    CandidatePromotionError,
    DenyPromotionReadbackProvider,
    DenyPromotionVerifier,
    SpaceConfigPromotionPolicy,
    acknowledge_promotion,
)
from bkflow.harness.services.knowledge.security import is_bounded_non_secret_text


def production_policy():
    return SpaceConfigPromotionPolicy()


def production_gate():
    return CandidateEvalGate()


def production_verifier():
    return DenyPromotionVerifier()


def production_readback_provider():
    return DenyPromotionReadbackProvider()


class Command(BaseCommand):
    help = "Verify and acknowledge one exact external Harness candidate promotion."

    def add_arguments(self, parser):
        parser.add_argument("--candidate-id", required=True)
        parser.add_argument("--receipt-ref", required=True)
        parser.add_argument("--expected-target-version", required=True)
        parser.add_argument("--operator")
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        try:
            candidate = ImprovementCandidate.objects.get(pk=options["candidate_id"])
        except (ImprovementCandidate.DoesNotExist, ValueError):
            raise CommandError("CANDIDATE_NOT_FOUND")
        if not is_safe_evidence_ref(options["receipt_ref"]) or not is_bounded_non_secret_text(
            options["expected_target_version"], 128
        ):
            raise CommandError("PROMOTION_ACKNOWLEDGMENT_INVALID")
        if not options["apply"]:
            self.stdout.write(
                "candidate_promotion_ack mode=dry-run candidate_id={} status={}".format(candidate.id, candidate.status)
            )
            return
        if not is_bounded_non_secret_text(options.get("operator"), 128):
            raise CommandError("OPERATOR_REQUIRED")
        try:
            published = acknowledge_promotion(
                candidate.id,
                operator=options["operator"],
                receipt_ref=options["receipt_ref"],
                expected_target_version=options["expected_target_version"],
                policy=production_policy(),
                gate=production_gate(),
                verifier=production_verifier(),
                readback_provider=production_readback_provider(),
            )
        except CandidatePromotionError as error:
            raise CommandError(error.code)
        self.stdout.write(
            "candidate_promotion_ack mode=apply candidate_id={} status={}".format(published.id, published.status)
        )
