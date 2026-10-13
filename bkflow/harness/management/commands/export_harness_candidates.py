"""Export reviewable P4 candidate packages without changing candidate lifecycle state."""

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bkflow.harness.constants import (
    ImprovementCandidateStatus,
    ImprovementCandidateType,
)
from bkflow.harness.models import ImprovementCandidate
from bkflow.harness.services.canonical import canonical_json_bytes
from bkflow.harness.services.improvement.package import build_candidate_review_package

_REVIEWABLE = {ImprovementCandidateStatus.IN_REVIEW, ImprovementCandidateStatus.APPROVED}


def _safe_output_directory(value):
    path = Path(value)
    try:
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            raise ValueError
        resolved = path.resolve(strict=True)
        if resolved != path or resolved.stat().st_uid != os.geteuid() or resolved.stat().st_mode & 0o002:
            raise ValueError
    except (OSError, RuntimeError, ValueError):
        raise CommandError("UNSAFE_OUTPUT_PATH")
    return resolved


def _write_package(output, candidate):
    destination = output / "{}.json".format(candidate.id)
    if destination.exists() or destination.is_symlink() or destination.parent != output:
        raise CommandError("UNSAFE_OUTPUT_PATH")
    try:
        with destination.open("xb") as package_file:
            package_file.write(canonical_json_bytes(build_candidate_review_package(candidate)))
            package_file.write(b"\n")
    except OSError:
        raise CommandError("CANDIDATE_EXPORT_FAILED")


class Command(BaseCommand):
    help = "Export bounded improvement review packages without changing candidate state."

    def add_arguments(self, parser):
        parser.add_argument("--candidate-id")
        parser.add_argument("--candidate-type", choices=ImprovementCandidateType.values)
        parser.add_argument("--status", choices=ImprovementCandidateStatus.values)
        parser.add_argument("--space-id", type=int)
        parser.add_argument("--output", required=True)
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        output = _safe_output_directory(options["output"])
        candidate_id = options.get("candidate_id")
        batch_values = (options.get("candidate_type"), options.get("status"), options.get("space_id"))
        if candidate_id:
            if any(value is not None for value in batch_values) or options["apply"]:
                raise CommandError("INVALID_EXPORT_SELECTOR")
            try:
                candidate = ImprovementCandidate.objects.select_related("source_feedback").get(pk=candidate_id)
            except (ImprovementCandidate.DoesNotExist, ValueError):
                raise CommandError("CANDIDATE_NOT_FOUND")
            if candidate.status not in _REVIEWABLE:
                raise CommandError("CANDIDATE_NOT_REVIEWABLE")
            _write_package(output, candidate)
            self.stdout.write("candidate_export mode=exact count=1")
            return

        if not all(value is not None for value in batch_values):
            raise CommandError("BATCH_FILTERS_REQUIRED")
        candidate_type, status, space_id = batch_values
        if status not in _REVIEWABLE:
            raise CommandError("CANDIDATE_NOT_REVIEWABLE")
        candidates = tuple(
            ImprovementCandidate.objects.select_related("source_feedback")
            .filter(
                candidate_type=candidate_type,
                status=status,
                source_feedback__space_id=space_id,
            )
            .order_by("id")
        )
        if not options["apply"]:
            self.stdout.write("candidate_export mode=dry-run count={}".format(len(candidates)))
            return
        for candidate in candidates:
            _write_package(output, candidate)
        self.stdout.write("candidate_export mode=batch count={}".format(len(candidates)))
