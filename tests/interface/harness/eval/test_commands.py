"""Safe Eval package export and signed BKAIDev result import commands."""

import json
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from bkflow.harness.models import HarnessEvalRun
from bkflow.harness.services.eval.runner import build_eval_package
from tests.interface.harness.eval.p4_eval_support import (
    approved_knowledge_candidate,
    create_mandatory_cases,
)
from tests.interface.harness.eval.test_gate import (
    SignatureVerifier,
    _signed_document,
    _verification,
)


@pytest.mark.django_db
def test_export_command_writes_one_sanitized_hash_addressed_package(tmp_path):
    candidate = approved_knowledge_candidate()
    create_mandatory_cases(candidate)

    call_command(
        "export_harness_eval_package",
        candidate_id=str(candidate.id),
        bkaidev_agent_release="agent-release-42",
        output=str(tmp_path),
    )

    document = json.loads((tmp_path / "{}.eval.json".format(candidate.id)).read_text(encoding="utf-8"))
    assert document["package_hash"]
    assert document["bkaidev_agent_release"] == "agent-release-42"
    assert "redacted_summary" not in json.dumps(document)


@pytest.mark.django_db
def test_import_command_defaults_to_dry_run_then_requires_verified_signature_on_apply(tmp_path, capsys):
    candidate = approved_knowledge_candidate()
    cases = create_mandatory_cases(candidate)
    package = build_eval_package(candidate, bkaidev_agent_release="agent-release-42")
    document = _signed_document(candidate, package, cases)
    input_path = tmp_path / "result.json"
    input_path.write_text(json.dumps(document), encoding="utf-8")

    call_command("import_harness_eval_result", candidate_id=str(candidate.id), input=str(input_path))
    assert HarnessEvalRun.objects.filter(candidate=candidate).count() == 0
    assert "mode=dry-run" in capsys.readouterr().out

    with pytest.raises(CommandError, match="SIGNED_EVAL_UNVERIFIED"):
        call_command(
            "import_harness_eval_result",
            candidate_id=str(candidate.id),
            input=str(input_path),
            apply=True,
        )

    with patch(
        "bkflow.harness.management.commands.import_harness_eval_result.production_signature_verifier",
        return_value=SignatureVerifier(_verification()),
    ):
        call_command(
            "import_harness_eval_result",
            candidate_id=str(candidate.id),
            input=str(input_path),
            apply=True,
        )
    assert HarnessEvalRun.objects.get(candidate=candidate).runner_mode == HarnessEvalRun.RunnerMode.SIGNED_BKAIDEV


@pytest.mark.django_db
def test_partial_or_package_mismatched_result_cannot_be_imported(tmp_path):
    candidate = approved_knowledge_candidate()
    cases = create_mandatory_cases(candidate)
    package = build_eval_package(candidate, bkaidev_agent_release="agent-release-42")
    document = _signed_document(candidate, package, cases)
    document["case_results"].pop()
    input_path = tmp_path / "partial.json"
    input_path.write_text(json.dumps(document), encoding="utf-8")

    with patch(
        "bkflow.harness.management.commands.import_harness_eval_result.production_signature_verifier",
        return_value=SignatureVerifier(_verification()),
    ), pytest.raises(CommandError, match="EVAL_CASE_SET_MISMATCH"):
        call_command(
            "import_harness_eval_result",
            candidate_id=str(candidate.id),
            input=str(input_path),
            apply=True,
        )
