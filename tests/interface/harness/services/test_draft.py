"""Draft-only Harness request boundary contracts."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    HarnessIdempotencyRecord,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import canonical_scope, sha256_json
from bkflow.harness.services.draft import _context_matches, create_workflow_draft
from bkflow.harness.services.validator import WorkflowValidator


def _context(**overrides):
    """Build the trusted server context used by the focused draft contracts."""
    values = {
        "platform_key": "platform",
        "platform_app": "app",
        "actor": "operator",
        "space_id": 1,
        "scope_type": "project",
        "scope_value": "1",
        "target_environment": "stag",
        "policy_version": "p0",
        "mcp_contract_version": "p0",
        "correlation_id": "draft-test",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


def _run(**overrides):
    """Persist one server-owned run without admitting model-controlled context."""
    values = {
        "platform": "platform",
        "platform_app": "app",
        "actor": "operator",
        "space_id": 1,
        "scope": canonical_scope("project", "1"),
        "environment": "stag",
        "status": "VALIDATING",
        "policy_version": "p0",
        "mcp_contract_version": "p0",
        "client_context": {},
    }
    values.update(overrides)
    return HarnessRun.objects.create(**values)


@pytest.mark.django_db
def test_draft_context_match_rejects_scopes_that_only_share_delimited_text():
    """Draft authorization must not treat a delimiter moved between scope fields as the same scope."""
    run = _run(scope=canonical_scope("a:b", "c"))

    assert _context_matches(run, _context(scope_type="a", scope_value="b:c")) is False


def test_draft_request_rejects_a2flow_and_auto_release_before_database_access():
    """The Harness endpoint accepts only validated artifact identifiers, never client workflow authority."""
    response = create_workflow_draft(
        _context(),
        {
            "run_id": "run",
            "revision_id": "revision",
            "plan_hash": "hash",
            "idempotency_key": "key",
            "auto_release": True,
        },
    )
    assert response["ok"] is False
    error = response["errors"][0]
    assert error["code"] == "CAPABILITY_FORBIDDEN"
    assert set(response) == {
        "ok",
        "run_id",
        "revision_id",
        "plan_hash",
        "status",
        "summary",
        "artifact_refs",
        "errors",
        "next_actions",
        "correlation_id",
    }
    assert set(error) == {"category", "code", "path", "repairable", "retryable", "message", "suggested_action"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "idempotency_key",
    ["credential://id/C2-DRAFT-SENTINEL", "api_token=C2-DRAFT-SENTINEL", "bad\ud800", "x" * 256],
)
def test_draft_rejects_unsafe_idempotency_key_before_lock_hash_or_record(idempotency_key):
    """Draft idempotency must apply the same secret, UTF-8 and persistence bounds as validation."""
    run = _run()

    response = create_workflow_draft(
        _context(),
        {
            "run_id": str(run.run_id),
            "revision_id": "00000000-0000-0000-0000-000000000000",
            "plan_hash": "a" * 64,
            "idempotency_key": idempotency_key,
        },
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert response["errors"][0]["path"] == "idempotency_key"
    assert "C2-DRAFT-SENTINEL" not in str(response)
    assert HarnessIdempotencyRecord.objects.count() == 0


@pytest.mark.django_db
def test_draft_rejects_a_run_from_a_different_server_environment_before_revision_lookup():
    """A matching app and scope cannot bypass the environment stored with a run."""
    run = _run(environment="prod")

    response = create_workflow_draft(
        _context(),
        {
            "run_id": str(run.run_id),
            "revision_id": "00000000-0000-0000-0000-000000000000",
            "plan_hash": "a" * 64,
            "idempotency_key": "idempotency-key",
        },
    )
    assert response["errors"][0]["category"] == "PERMISSION"


@pytest.mark.django_db
def test_draft_replays_completed_idempotency_after_the_run_is_draft_ready():
    """A retry never tries to materialize another template after the transition."""
    run = _run(status="DRAFT_READY")
    request = {
        "run_id": str(run.run_id),
        "revision_id": "00000000-0000-0000-0000-000000000000",
        "plan_hash": "a" * 64,
        "idempotency_key": "draft-retry",
    }
    expected = {
        "ok": True,
        "status": "DRAFT_READY",
        "artifact_refs": [{"template_id": 12, "pipeline_tree_hash": "tree"}],
    }
    HarnessIdempotencyRecord.objects.create(
        platform_app="app",
        actor="operator",
        space_id=1,
        tool_name="create_workflow_draft",
        run_scope="run:{}".format(run.run_id),
        idempotency_key=request["idempotency_key"],
        request_hash=sha256_json(request),
        status="COMPLETED",
        response_snapshot=expected,
        run=run,
        resource_reference="12",
    )

    assert create_workflow_draft(_context(), request) == expected


@pytest.mark.django_db
@patch("bkflow.harness.services.draft.update_template_draft_from_pipeline_tree")
@patch("bkflow.harness.services.draft._managed_template")
@patch.object(WorkflowValidator, "_validate_pipeline_tree")
@patch.object(WorkflowValidator, "_convert")
@patch.object(WorkflowValidator, "_plan_hash")
def test_later_validated_revision_updates_the_same_managed_draft(
    plan_hash, convert, validate_tree, managed_template, update_draft
):
    """A repaired revision reuses the run's draft rather than creating a new template."""
    run = _run(
        status="DRAFT_READY",
        artifact_references=[{"type": "harness_draft", "template_id": 12, "revision_id": "old"}],
    )
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=2,
        intent_spec={},
        canonical_a2flow={"name": "repaired", "nodes": []},
        plan_hash="b" * 64,
    )
    ValidationReport.objects.create(
        run=run,
        revision=revision,
        checkpoint="VALIDATE",
        validator_version=WorkflowValidator.VERSION,
        result={"valid": True, "converter_fingerprint": "converter", "pipeline_tree_hash": "tree"},
        risk_manifest={},
        errors=[],
        warnings=[],
        correlation_id="draft-test",
    )
    plan_hash.return_value = revision.plan_hash
    convert.return_value = SimpleNamespace(pipeline_tree={"id": "tree"}, converter_fingerprint="converter")
    managed_template.return_value = MagicMock(id=12)

    with patch("bkflow.harness.services.draft.sha256_json", return_value="tree"):
        response = create_workflow_draft(
            _context(),
            {
                "run_id": str(run.run_id),
                "revision_id": str(revision.id),
                "plan_hash": revision.plan_hash,
                "idempotency_key": "later-revision",
            },
        )

    assert response["artifact_refs"][0]["template_id"] == 12
    update_draft.assert_called_once()
    run.refresh_from_db()
    assert run.status == "DRAFT_READY"
    assert run.artifact_references == [
        {"type": "harness_draft", "template_id": 12, "revision_id": str(revision.id), "pipeline_tree_hash": "tree"}
    ]
