"""Safety boundaries for read-only candidate package export."""

import json
import os

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from bkflow.harness import models as harness_models
from bkflow.harness.constants import ImprovementCandidateStatus
from bkflow.harness.services.improvement.governance import (
    review_candidate,
    submit_candidate,
)
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    feedback_values,
)


def _candidate(status=ImprovementCandidateStatus.IN_REVIEW):
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    candidate = harness_models.ImprovementCandidate.objects.create(
        **candidate_values(
            feedback,
            owner_ref="knowledge-owner",
            reviewer_ref="knowledge-reviewer",
        )
    )
    if status != ImprovementCandidateStatus.DRAFT:
        candidate = submit_candidate(candidate.id, operator="knowledge-owner")
    if status == ImprovementCandidateStatus.APPROVED:
        candidate = review_candidate(candidate.id, operator="knowledge-reviewer", decision="APPROVE")
    return candidate


@pytest.mark.django_db
def test_exact_export_writes_reviewable_package_without_changing_status(tmp_path):
    candidate = _candidate()

    call_command("export_harness_candidates", candidate_id=str(candidate.id), output=str(tmp_path))

    output = tmp_path / "{}.json".format(candidate.id)
    document = json.loads(output.read_text(encoding="utf-8"))
    candidate.refresh_from_db()
    assert document["candidate"]["candidate_ref"].endswith(str(candidate.id))
    assert candidate.status == ImprovementCandidateStatus.IN_REVIEW


@pytest.mark.django_db
def test_exact_export_rejects_draft_and_unsafe_output_path(tmp_path):
    candidate = _candidate(status=ImprovementCandidateStatus.DRAFT)
    with pytest.raises(CommandError, match="CANDIDATE_NOT_REVIEWABLE"):
        call_command("export_harness_candidates", candidate_id=str(candidate.id), output=str(tmp_path))

    submit_candidate(candidate.id, operator="knowledge-owner")
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    os.symlink(target, link)
    with pytest.raises(CommandError, match="UNSAFE_OUTPUT_PATH"):
        call_command("export_harness_candidates", candidate_id=str(candidate.id), output=str(link))


@pytest.mark.django_db
def test_batch_requires_all_filters_and_defaults_to_dry_run(tmp_path, capsys):
    candidate = _candidate()

    with pytest.raises(CommandError, match="BATCH_FILTERS_REQUIRED"):
        call_command(
            "export_harness_candidates",
            candidate_type=candidate.candidate_type,
            status=candidate.status,
            output=str(tmp_path),
        )

    call_command(
        "export_harness_candidates",
        candidate_type=candidate.candidate_type,
        status=candidate.status,
        space_id=candidate.source_feedback.space_id,
        output=str(tmp_path),
    )

    candidate.refresh_from_db()
    assert list(tmp_path.iterdir()) == []
    assert "mode=dry-run" in capsys.readouterr().out
    assert candidate.status == ImprovementCandidateStatus.IN_REVIEW
