"""Persistence contracts for P3 execution aggregates."""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from bkflow.harness import models as harness_models
from bkflow.harness.constants import HarnessAction, HarnessRunStatus, RiskLevel
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.evidence import EVIDENCE_REDACTION_VERSION


@pytest.fixture
def execution_graph(db):
    """Persist one published manifest graph for execution model tests."""
    run = harness_models.HarnessRun.objects.create(
        platform="bkaidev",
        platform_app="trusted-app",
        actor="dannydeng",
        space_id=904,
        scope=canonical_scope("project", "904"),
        environment="stag",
        status=HarnessRunStatus.PUBLISHED,
        policy_version="risk-2026.09",
        mcp_contract_version="1.3.0",
    )
    revision = harness_models.WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={"goal": "restart service"},
        canonical_a2flow={"version": "2.0", "nodes": []},
        plan_hash="a" * 64,
    )
    manifest = harness_models.ReleaseManifest.objects.create(
        run=run,
        revision=revision,
        plan_hash=revision.plan_hash,
        draft_template_id=42,
        draft_snapshot_id=84,
        draft_tree_fingerprint={"sha256": "b" * 64, "node_count": 1},
        capability_snapshot=[],
        validation_evidence_refs=["evidence://validation/report-1"],
        debug_evidence_refs=["evidence://debug/session-1"],
        postcondition_spec={"kind": "task_state", "expected": "FINISHED"},
        risk_manifest={"highest": RiskLevel.L2},
        required_approvals=[],
        policy_version=run.policy_version,
        target_environment=run.environment,
    )
    harness_models.ReleasePublication.objects.create(
        manifest=manifest,
        published_template_id=42,
        published_snapshot_id=85,
        published_version="2026.09.05.1",
        publish_idempotency_ref="idempotency://publish/execution-fixture",
        published_at=timezone.now(),
    )
    return run, revision, manifest


def execution_values(run, revision, manifest, **overrides):
    """Build one initial logical execution payload."""
    values = {
        "manifest": manifest,
        "run": run,
        "revision": revision,
        "published_template_id": 42,
        "published_snapshot_id": 85,
        "published_version": "2026.09.05.1",
        "status": harness_models.ExecutionRun.Status.PENDING,
        "start_idempotency_key": "start-execution-1",
        "platform": run.platform,
        "platform_app": run.platform_app,
        "actor": run.actor,
        "space_id": run.space_id,
        "scope": run.scope,
        "target_environment": run.environment,
        "policy_version": run.policy_version,
        "postcondition_status": harness_models.ExecutionRun.PostconditionStatus.PENDING,
    }
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_execution_is_unique_per_manifest_start_key_and_matches_publication(execution_graph):
    """One start idempotency key identifies one exact published snapshot execution."""
    run, revision, manifest = execution_graph
    harness_models.ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    with pytest.raises((ValidationError, IntegrityError)), transaction.atomic():
        harness_models.ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    with pytest.raises(ValidationError):
        harness_models.ExecutionRun.objects.create(
            **execution_values(
                run,
                revision,
                manifest,
                start_idempotency_key="start-execution-2",
                published_snapshot_id=999,
            )
        )
    with pytest.raises(ValidationError):
        harness_models.ExecutionRun.objects.create(
            **execution_values(
                run,
                revision,
                manifest,
                start_idempotency_key="start-execution-invalid-coordinate",
                published_template_id=0,
            )
        )


@pytest.mark.django_db
def test_execution_task_ref_is_write_once_and_uncertain_state_requires_readback(execution_graph):
    """Persist dispatch ambiguity for readback instead of blindly repeating side effects."""
    run, revision, manifest = execution_graph
    execution = harness_models.ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    execution.task_ref = "12001"
    with pytest.raises(ValidationError):
        execution.save(update_fields=["task_ref"])
    execution.task_ref = None
    execution.status = execution.Status.CREATE_DISPATCHING
    execution.save(update_fields=["status"])
    execution.status = execution.Status.CREATE_UNCERTAIN
    execution.save(update_fields=["status"])
    execution.status = execution.Status.START_DISPATCHING
    with pytest.raises(ValidationError):
        execution.save(update_fields=["status"])

    execution.status = execution.Status.CREATED
    execution.task_ref = "12001"
    execution.save(update_fields=["status", "task_ref"])
    execution.task_ref = "12002"
    with pytest.raises(ValidationError):
        execution.save(update_fields=["task_ref"])


@pytest.mark.django_db
def test_execution_terminal_timestamp_and_set_based_mutations_are_closed(execution_graph):
    """Only locked instance transitions may mutate saga state and terminal evidence."""
    run, revision, manifest = execution_graph
    execution = harness_models.ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    with pytest.raises(ValidationError):
        harness_models.ExecutionRun.objects.filter(pk=execution.pk).update(status=execution.Status.FAILED)
    with pytest.raises(ValidationError):
        execution.delete()
    execution.status = execution.Status.FAILED
    with pytest.raises(ValidationError):
        execution.save(update_fields=["status"])
    execution.postcondition_status = execution.PostconditionStatus.UNAVAILABLE
    execution.terminal_at = timezone.now()
    execution.save(update_fields=["status", "postcondition_status", "terminal_at"])
    execution.heartbeat_at = timezone.now()
    with pytest.raises(ValidationError):
        execution.save(update_fields=["heartbeat_at"])
    execution.refresh_from_db()
    execution.status = execution.Status.PENDING
    execution.postcondition_status = execution.PostconditionStatus.PENDING
    execution.terminal_at = None
    with pytest.raises(ValidationError):
        execution.save(update_fields=["status", "postcondition_status", "terminal_at"])

    fresh = harness_models.ExecutionRun.objects.create(
        **execution_values(run, revision, manifest, start_idempotency_key="start-false-success")
    )
    fresh.status = fresh.Status.SUCCEEDED
    fresh.task_ref = "12003"
    fresh.postcondition_status = fresh.PostconditionStatus.FAILED
    fresh.terminal_at = timezone.now()
    with pytest.raises(ValidationError):
        fresh.full_clean()


def evidence_values(run, revision, execution, **overrides):
    """Build one execution-owned EvidenceEvent payload."""
    values = {
        "run": run,
        "revision": revision,
        "execution": execution,
        "event_type": "EXECUTION_CREATED",
        "action": HarnessAction.START_WORKFLOW_EXECUTION,
        "redacted_payload": {"status": "PENDING"},
        "artifact_refs": [],
        "actor": run.actor,
        "correlation_id": "p3-execution-model",
        "redaction_version": EVIDENCE_REDACTION_VERSION,
    }
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_evidence_event_has_at_most_one_debug_or_execution_owner(execution_graph):
    """Execution evidence is referentially owned and never also attached to a debug session."""
    run, revision, manifest = execution_graph
    execution = harness_models.ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    event = harness_models.EvidenceEvent.objects.create(**evidence_values(run, revision, execution))
    assert event.execution_id == execution.id

    event.debug_session_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        event.full_clean()


@pytest.mark.django_db
def test_finalized_bundle_validates_ordered_event_ownership_and_is_append_only(execution_graph):
    """Finalize one deterministic bundle only from Evidence belonging to the execution."""
    run, revision, manifest = execution_graph
    execution = harness_models.ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    event = harness_models.EvidenceEvent.objects.create(**evidence_values(run, revision, execution))
    with pytest.raises(ValidationError):
        harness_models.EvidenceBundle.objects.create(
            run=run,
            revision=revision,
            execution=execution,
            evidence_event_refs=[str(event.id)],
            artifact_refs=[],
            redaction_version=EVIDENCE_REDACTION_VERSION,
            outcome=harness_models.EvidenceBundle.Outcome.FAILED,
            finalized_at=timezone.now(),
            retention_class=harness_models.EvidenceBundle.RetentionClass.STANDARD,
        )

    run.status = HarnessRunStatus.FAILED
    run.save(update_fields=["status"])
    root_event = harness_models.EvidenceEvent.objects.create(
        **evidence_values(run, revision, None, event_type="RUN_FAILED")
    )
    root_bundle = harness_models.EvidenceBundle.objects.create(
        run=run,
        revision=revision,
        evidence_event_refs=[str(root_event.id)],
        artifact_refs=[],
        redaction_version=EVIDENCE_REDACTION_VERSION,
        outcome=harness_models.EvidenceBundle.Outcome.FAILED,
        finalized_at=timezone.now(),
        retention_class=harness_models.EvidenceBundle.RetentionClass.STANDARD,
    )
    assert root_bundle.execution_id is None
    execution.status = execution.Status.FAILED
    execution.postcondition_status = execution.PostconditionStatus.FAILED
    execution.postcondition_report = {"reason": "task failed"}
    execution.terminal_at = timezone.now()
    execution.save(update_fields=["status", "postcondition_status", "postcondition_report", "terminal_at"])
    with pytest.raises(ValidationError):
        harness_models.EvidenceBundle.objects.create(
            run=run,
            revision=revision,
            execution=execution,
            evidence_event_refs=[str(event.id)],
            artifact_refs=[],
            redaction_version=EVIDENCE_REDACTION_VERSION,
            outcome=harness_models.EvidenceBundle.Outcome.SUCCEEDED,
            finalized_at=timezone.now(),
            retention_class=harness_models.EvidenceBundle.RetentionClass.STANDARD,
        )
    bundle = harness_models.EvidenceBundle.objects.create(
        run=run,
        revision=revision,
        execution=execution,
        evidence_event_refs=[str(event.id)],
        artifact_refs=["artifact://execution/summary-1"],
        redaction_version=EVIDENCE_REDACTION_VERSION,
        outcome=harness_models.EvidenceBundle.Outcome.FAILED,
        finalized_at=timezone.now(),
        retention_class=harness_models.EvidenceBundle.RetentionClass.STANDARD,
    )
    assert len(bundle.bundle_hash) == 64
    bundle.is_deleted = True
    with pytest.raises(ValidationError):
        bundle.full_clean()
    bundle.is_deleted = False
    with pytest.raises(ValidationError):
        bundle.save()
    with pytest.raises(ValidationError):
        harness_models.EvidenceBundle.objects.filter(pk=bundle.pk).delete()

    with pytest.raises(ValidationError):
        harness_models.EvidenceBundle.objects.create(
            run=run,
            revision=revision,
            evidence_event_refs=[str(uuid.uuid4())],
            artifact_refs=[],
            redaction_version=EVIDENCE_REDACTION_VERSION,
            outcome=harness_models.EvidenceBundle.Outcome.FAILED,
            finalized_at=timezone.now(),
            retention_class=harness_models.EvidenceBundle.RetentionClass.STANDARD,
        )


@pytest.mark.django_db
def test_token_lease_owner_xor_supports_action_bound_execution(execution_graph):
    """Exactly one owner is selected using portable null checks and no plaintext token field."""
    run, revision, manifest = execution_graph
    execution = harness_models.ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    execution.status = execution.Status.CREATE_DISPATCHING
    execution.save(update_fields=["status"])
    execution.status = execution.Status.CREATED
    execution.task_ref = "12001"
    execution.save(update_fields=["status", "task_ref"])
    now = timezone.now()
    lease = harness_models.TokenLease.objects.create(
        execution=execution,
        platform_app=run.platform_app,
        actor=run.actor,
        space_id=run.space_id,
        resource_type=harness_models.TokenLease.Resource.TASK,
        resource_id="12001",
        permission=harness_models.TokenLease.Permission.OPERATE,
        action=HarnessAction.PAUSE,
        action_digest="e" * 64,
        issuer_ref="issuer://bkflow/platform-app",
        token_fingerprint="f" * 64,
        issued_at=now,
        expires_at=now + timezone.timedelta(minutes=5),
        status=harness_models.TokenLease.Status.ACTIVE,
    )
    assert lease.session_id is None
    assert lease.execution_id == execution.id
    assert not any(field.name in {"token", "secret"} for field in lease._meta.fields)

    execution.status = execution.Status.FAILED
    execution.postcondition_status = execution.PostconditionStatus.UNAVAILABLE
    execution.terminal_at = timezone.now()
    with pytest.raises(ValidationError):
        execution.save(update_fields=["status", "postcondition_status", "terminal_at"])
    lease.status = lease.Status.REVOKED
    lease.revoked_at = timezone.now()
    lease.save(update_fields=["status", "revoked_at"])
    execution.save(update_fields=["status", "postcondition_status", "terminal_at"])

    with pytest.raises(ValidationError):
        harness_models.TokenLease.objects.create(
            platform_app=run.platform_app,
            actor=run.actor,
            space_id=run.space_id,
            resource_type=harness_models.TokenLease.Resource.TASK,
            resource_id="12001",
            permission=harness_models.TokenLease.Permission.OPERATE,
            action=HarnessAction.PAUSE,
            action_digest="e" * 64,
            issuer_ref="issuer://bkflow/platform-app",
            token_fingerprint="0" * 64,
            issued_at=now,
            expires_at=now + timezone.timedelta(minutes=5),
            status=harness_models.TokenLease.Status.ACTIVE,
        )
