"""Dry-run-by-default import of one signed fixed-release BKAIDev Eval result."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bkflow.harness.models import ImprovementCandidate
from bkflow.harness.services.eval.gate import FROZEN_PROMOTION_THRESHOLDS
from bkflow.harness.services.eval.runner import (
    DenySignedEvalVerifier,
    EvalRunError,
    import_signed_bkaidev_result,
)

MAX_SIGNED_RESULT_BYTES = 1024 * 1024


def production_signature_verifier():
    return DenySignedEvalVerifier()


def _load_document(value):
    path = Path(value)
    try:
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise ValueError
        raw = path.read_bytes()
        if len(raw) > MAX_SIGNED_RESULT_BYTES:
            raise ValueError
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise CommandError("SIGNED_EVAL_DOCUMENT_INVALID")
    return document


class Command(BaseCommand):
    help = "Verify and import one signed BKAIDev Eval result; dry-run unless --apply is present."

    def add_arguments(self, parser):
        parser.add_argument("--candidate-id", required=True)
        parser.add_argument("--input", required=True)
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        document = _load_document(options["input"])
        try:
            candidate = ImprovementCandidate.objects.get(pk=options["candidate_id"])
        except (ImprovementCandidate.DoesNotExist, ValueError):
            raise CommandError("CANDIDATE_NOT_FOUND")
        if not options["apply"]:
            self.stdout.write("harness_eval_import mode=dry-run candidate_id={}".format(candidate.id))
            return
        try:
            eval_run = import_signed_bkaidev_result(
                candidate.id,
                document=document,
                verifier=production_signature_verifier(),
                thresholds=FROZEN_PROMOTION_THRESHOLDS,
            )
        except EvalRunError as error:
            raise CommandError(error.code)
        self.stdout.write(
            "harness_eval_import mode=apply eval_run_id={} status={}".format(eval_run.id, eval_run.status)
        )
