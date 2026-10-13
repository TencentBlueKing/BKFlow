"""Export one sanitized, hash-addressed Eval package for a fixed BKAIDev release."""

from django.core.management.base import BaseCommand, CommandError

from bkflow.harness.management.commands.export_harness_candidates import (
    _safe_output_directory,
)
from bkflow.harness.models import ImprovementCandidate
from bkflow.harness.services.canonical import canonical_json_bytes
from bkflow.harness.services.eval.runner import EvalRunError, build_eval_package


class Command(BaseCommand):
    help = "Export an exact Harness Eval package without running an LLM."

    def add_arguments(self, parser):
        parser.add_argument("--candidate-id", required=True)
        parser.add_argument("--bkaidev-agent-release", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        output = _safe_output_directory(options["output"])
        try:
            candidate = ImprovementCandidate.objects.select_related("source_feedback__run").get(
                pk=options["candidate_id"]
            )
            package = build_eval_package(
                candidate,
                bkaidev_agent_release=options["bkaidev_agent_release"],
            )
        except (ImprovementCandidate.DoesNotExist, ValueError) as error:
            code = error.code if isinstance(error, EvalRunError) else "EVAL_EXPORT_INVALID"
            raise CommandError(code)
        destination = output / "{}.eval.json".format(candidate.id)
        if destination.exists() or destination.is_symlink():
            raise CommandError("UNSAFE_OUTPUT_PATH")
        try:
            with destination.open("xb") as package_file:
                package_file.write(canonical_json_bytes(package))
                package_file.write(b"\n")
        except OSError:
            raise CommandError("EVAL_EXPORT_FAILED")
        self.stdout.write("harness_eval_export count=1 package_hash={}".format(package["package_hash"]))
