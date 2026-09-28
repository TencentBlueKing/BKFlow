"""Deterministic terminal EvidenceBundle finalization contracts."""

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from bkflow.harness.constants import HarnessAction
from bkflow.harness.models import EvidenceBundle, EvidenceEvent, ExecutionRun
from bkflow.harness.services import evidence as evidence_service
from bkflow.harness.services.evidence import EVIDENCE_REDACTION_VERSION

pytest_plugins = ("tests.interface.harness.execution.test_models",)


def terminal_execution(run, revision, manifest):
    """Drive one execution through the durable lifecycle into FAILED."""
    from tests.interface.harness.execution.test_models import execution_values

    execution = ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    execution.status = execution.Status.CREATE_DISPATCHING
    execution.save(update_fields=["status"])
    execution.status = execution.Status.CREATED
    execution.task_ref = "12001"
    execution.save(update_fields=["status", "task_ref"])
    execution.status = execution.Status.FAILED
    execution.postcondition_status = execution.PostconditionStatus.FAILED
    execution.postcondition_report = {"reason": "task failed"}
    execution.terminal_at = timezone.now()
    execution.save(update_fields=["status", "postcondition_status", "postcondition_report", "terminal_at"])
    return execution


@pytest.mark.django_db
def test_finalize_requires_terminal_execution_and_completed_postcondition(execution_graph):
    """An in-flight saga cannot produce final evidence."""
    run, revision, manifest = execution_graph
    from tests.interface.harness.execution.test_models import execution_values

    execution = ExecutionRun.objects.create(**execution_values(run, revision, manifest))
    finalizer = getattr(evidence_service, "finalize_evidence_bundle", None)
    assert finalizer is not None
    with pytest.raises(ValidationError):
        finalizer(execution)


@pytest.mark.django_db
def test_finalize_orders_events_deterministically_and_replays_existing_bundle(execution_graph):
    """Retry returns the same immutable bundle with stable event order and digest."""
    run, revision, manifest = execution_graph
    execution = terminal_execution(run, revision, manifest)
    later = EvidenceEvent.objects.create(
        run=run,
        revision=revision,
        execution=execution,
        event_type="EXECUTION_FAILED",
        action=HarnessAction.START_WORKFLOW_EXECUTION,
        redacted_payload={"status": "FAILED"},
        actor=run.actor,
        correlation_id="p3-bundle",
        occurred_at=timezone.now(),
    )
    earlier = EvidenceEvent.objects.create(
        run=run,
        revision=revision,
        execution=execution,
        event_type="EXECUTION_CREATED",
        action=HarnessAction.START_WORKFLOW_EXECUTION,
        redacted_payload={"status": "CREATED"},
        actor=run.actor,
        correlation_id="p3-bundle",
        occurred_at=later.occurred_at - timezone.timedelta(seconds=1),
    )

    with CaptureQueriesContext(connection) as captured:
        first = evidence_service.finalize_evidence_bundle(execution)
    replay = evidence_service.finalize_evidence_bundle(execution)

    assert first.id == replay.id
    assert first.evidence_event_refs == [str(earlier.id), str(later.id)]
    assert first.bundle_hash == replay.bundle_hash
    assert EvidenceBundle.objects.count() == 1
    event_selects = [
        query["sql"].lower()
        for query in captured.captured_queries
        if "select" in query["sql"].lower() and "harness_evidenceevent" in query["sql"].lower()
    ]
    assert event_selects
    assert all("redacted_payload" not in query for query in event_selects)


@pytest.mark.django_db
def test_secret_event_is_redacted_before_finalization(execution_graph):
    """Bundle metadata and inline Evidence never contain raw credentials."""
    run, revision, manifest = execution_graph
    execution = terminal_execution(run, revision, manifest)
    event = evidence_service.record_evidence(
        run=run,
        revision=revision,
        execution=execution,
        event_type="EXECUTION_FAILED",
        action=HarnessAction.START_WORKFLOW_EXECUTION,
        payload={"password": "raw-secret", "detail": "bounded"},
        actor=run.actor,
        correlation_id="p3-bundle-secret",
    )

    bundle = evidence_service.finalize_evidence_bundle(execution)
    serialized = str(bundle.evidence_event_refs) + str(bundle.artifact_refs) + str(event.redacted_payload)
    assert "raw-secret" not in serialized
    assert bundle.artifact_refs == []
    assert event.redacted_payload["password"] != "raw-secret"
    assert bundle.redaction_version == EVIDENCE_REDACTION_VERSION


@pytest.mark.django_db
def test_execution_evidence_cannot_be_appended_after_bundle_finalization(execution_graph):
    """The execution lock closes the event stream before the immutable bundle is written."""
    run, revision, manifest = execution_graph
    execution = terminal_execution(run, revision, manifest)
    evidence_service.record_evidence(
        run=run,
        revision=revision,
        execution=execution,
        event_type="EXECUTION_FAILED",
        action=HarnessAction.START_WORKFLOW_EXECUTION,
        payload={"status": "FAILED"},
        actor=run.actor,
        correlation_id="p3-bundle-closed",
    )
    evidence_service.finalize_evidence_bundle(execution)

    with pytest.raises(ValidationError):
        evidence_service.record_evidence(
            run=run,
            revision=revision,
            execution=execution,
            event_type="EXECUTION_LATE_EVENT",
            action=HarnessAction.GET_WORKFLOW_EXECUTION,
            payload={"status": "FAILED"},
            actor=run.actor,
            correlation_id="p3-bundle-closed",
        )

    with pytest.raises(ValidationError):
        EvidenceEvent.objects.create(
            run=run,
            revision=revision,
            execution=execution,
            event_type="EXECUTION_DIRECT_LATE_EVENT",
            action=HarnessAction.GET_WORKFLOW_EXECUTION,
            redacted_payload={"status": "FAILED"},
            actor=run.actor,
            correlation_id="p3-bundle-closed",
        )

    assert EvidenceEvent.objects.filter(execution=execution).count() == 1


@pytest.mark.django_db
def test_oversized_execution_evidence_fails_before_artifact_side_effect(execution_graph):
    """Execution artifacts require a durable outbox before an external writer may run."""
    run, revision, manifest = execution_graph
    execution = terminal_execution(run, revision, manifest)
    written = []

    with pytest.raises(ValidationError):
        evidence_service.record_evidence(
            run=run,
            revision=revision,
            execution=execution,
            event_type="EXECUTION_FAILED",
            action=HarnessAction.START_WORKFLOW_EXECUTION,
            payload={"detail": "x" * 20000},
            actor=run.actor,
            correlation_id="p3-bundle-oversized-event",
            artifact_writer=lambda payload: written.append(payload) or "artifact://execution/summary",
        )

    assert written == []
    assert EvidenceEvent.objects.filter(execution=execution).count() == 0


@pytest.mark.django_db
def test_over_budget_bundle_fails_before_external_artifact_side_effect(execution_graph, monkeypatch):
    """Without an outbox protocol, overflow is rejected instead of writing inside the DB lock."""
    run, revision, manifest = execution_graph
    execution = terminal_execution(run, revision, manifest)
    for index in range(3):
        EvidenceEvent.objects.create(
            run=run,
            revision=revision,
            execution=execution,
            event_type="EXECUTION_EVENT_{}".format(index),
            action=HarnessAction.GET_WORKFLOW_EXECUTION,
            redacted_payload={"index": index},
            artifact_refs=["artifact://execution/ref-{}".format(index)],
            actor=run.actor,
            correlation_id="p3-bundle-overflow",
        )
    monkeypatch.setattr(evidence_service, "MAX_EVIDENCE_ITEMS", 2)
    written = []

    with pytest.raises(ValidationError):
        evidence_service.finalize_evidence_bundle(
            execution,
            artifact_writer=lambda payload: written.append(payload) or "artifact://execution/overflow",
        )

    assert written == []
    assert EvidenceBundle.objects.count() == 0


@pytest.mark.django_db
def test_execution_owned_evidence_rejects_unlocked_bulk_insert(execution_graph):
    """Batch insertion cannot bypass the execution lock shared with finalization."""
    run, revision, manifest = execution_graph
    execution = terminal_execution(run, revision, manifest)
    event = EvidenceEvent(
        run=run,
        revision=revision,
        execution=execution,
        event_type="EXECUTION_FAILED",
        action=HarnessAction.START_WORKFLOW_EXECUTION,
        redacted_payload={"status": "FAILED"},
        actor=run.actor,
        correlation_id="p3-bundle-bulk",
    )

    with pytest.raises(ValidationError):
        EvidenceEvent.objects.bulk_create([event])

    assert EvidenceEvent.objects.filter(execution=execution).count() == 0
