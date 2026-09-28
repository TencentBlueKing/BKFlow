"""Owned, bounded execution readback and convergence contracts."""

import datetime
from dataclasses import replace
from unittest import mock

import pytest
from django.db import connection
from django.utils import timezone

from bkflow.admin.models import ModuleInfo
from bkflow.harness.constants import HarnessAction, HarnessRunStatus
from bkflow.harness.models import (
    EvidenceBundle,
    EvidenceEvent,
    ExecutionRun,
    TokenLease,
)
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.execution.adapter import (
    ExecutionObservation,
    ExecutionReadAdapter,
    ReadbackUnavailable,
    TaskNotFound,
)
from bkflow.harness.services.execution.postconditions import NodeOutputEvidence
from bkflow.harness.services.execution.read import get_workflow_execution_with_context
from bkflow.space.configs import HarnessExecutionEnabledConfig
from bkflow.space.models import SpaceConfig
from bkflow.template.models import TemplateSnapshot
from tests.interface.harness.execution.test_start_execution import (
    RecordingAdapter,
    approved_payload,
    approved_verifier,
    start,
)

pytest_plugins = ("tests.interface.harness.execution.test_start_execution",)


class FixedReadAdapter:
    def __init__(self, state="RUNNING", outputs=None, error=None):
        self.state = state
        self.outputs = outputs or {}
        self.error = error
        self.calls = []
        self.transaction_states = []

    def observe(self, task_ref, pipeline_tree, required_outputs):
        self.calls.append((task_ref, tuple(required_outputs)))
        self.transaction_states.append(connection.in_atomic_block)
        if self.error:
            raise self.error
        return ExecutionObservation(state=self.state, node_outputs=self.outputs)


def started_execution(case):
    first = start(case)
    verifier, _ = approved_verifier(case, first)
    response = start(
        case,
        approved_payload(case, first),
        approval_verifier=verifier,
        adapter=RecordingAdapter(),
    )
    assert response["ok"] is True
    return ExecutionRun.objects.get()


def request(execution, **overrides):
    value = {"execution_id": str(execution.id), "limit": 20}
    value.update(overrides)
    return value


def execution_at_state(case, status, *, key="execution-read-fixture", task_ref="8102"):
    publication = case.publication
    execution = ExecutionRun.objects.create(
        manifest=case.manifest,
        run=case.run,
        revision=case.manifest.revision,
        published_template_id=publication.published_template_id,
        published_snapshot_id=publication.published_snapshot_id,
        published_version=publication.published_version,
        start_idempotency_key=key,
        platform=case.context.platform_key,
        platform_app=case.context.platform_app,
        actor=case.context.actor,
        space_id=case.context.space_id,
        scope=case.run.scope,
        target_environment=case.context.target_environment,
        policy_version=case.context.policy_version,
    )
    if status == ExecutionRun.Status.PENDING:
        return execution
    execution.status = ExecutionRun.Status.CREATE_DISPATCHING
    execution.save(update_fields=["status", "update_at"])
    if status == ExecutionRun.Status.CREATE_DISPATCHING:
        return execution
    execution.status = ExecutionRun.Status.CREATED
    execution.task_ref = task_ref
    execution.save(update_fields=["status", "task_ref", "update_at"])
    if status == ExecutionRun.Status.CREATED:
        return execution
    execution.status = ExecutionRun.Status.START_DISPATCHING
    execution.save(update_fields=["status", "update_at"])
    if status == ExecutionRun.Status.START_DISPATCHING:
        return execution
    if status == ExecutionRun.Status.START_UNCERTAIN:
        execution.status = ExecutionRun.Status.START_UNCERTAIN
        execution.save(update_fields=["status", "update_at"])
        return execution
    execution.status = ExecutionRun.Status.EXECUTING
    execution.save(update_fields=["status", "update_at"])
    return execution


@pytest.mark.django_db
def test_closed_request_and_foreign_context_fail_before_engine(execution_case):
    execution = started_execution(execution_case)
    adapter = FixedReadAdapter()

    invalid = get_workflow_execution_with_context(
        execution_case.context,
        request(execution, unexpected=True),
        adapter=adapter,
    )
    foreign = get_workflow_execution_with_context(
        replace(execution_case.context, actor="foreign-user"),
        request(execution),
        adapter=adapter,
    )

    assert invalid["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert foreign["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert adapter.calls == []


@pytest.mark.django_db
def test_execution_disabled_is_strictly_persistence_only(execution_case):
    execution = started_execution(execution_case)
    SpaceConfig.objects.filter(
        space_id=execution_case.context.space_id,
        name=HarnessExecutionEnabledConfig.name,
    ).update(text_value="false")
    before = {
        "execution": ExecutionRun.objects.values().get(pk=execution.pk),
        "events": list(EvidenceEvent.objects.values_list("id", flat=True)),
        "bundles": EvidenceBundle.objects.count(),
        "leases": list(TokenLease.objects.values()),
    }
    adapter = FixedReadAdapter(error=AssertionError("Engine must not run"))
    broker = mock.Mock()
    broker.revoke_execution_leases.side_effect = AssertionError("Token broker must not run")

    response = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=adapter,
        token_broker=broker,
    )

    assert response["ok"] is True
    assert response["artifact_refs"][0]["refresh"] == {
        "available": False,
        "reason": "execution_disabled",
    }
    assert response["next_actions"] == ["get_workflow_execution"]
    assert ExecutionRun.objects.values().get(pk=execution.pk) == before["execution"]
    assert list(EvidenceEvent.objects.values_list("id", flat=True)) == before["events"]
    assert EvidenceBundle.objects.count() == before["bundles"]
    assert list(TokenLease.objects.values()) == before["leases"]
    assert adapter.calls == []
    broker.revoke_execution_leases.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "engine_state,expected_status",
    [
        ("RUNNING", ExecutionRun.Status.EXECUTING),
        ("SUSPENDED", ExecutionRun.Status.PAUSED),
        ("FAILED", ExecutionRun.Status.EXECUTING),
    ],
)
def test_running_paused_and_recoverable_engine_failed_are_projected(execution_case, engine_state, expected_status):
    execution = started_execution(execution_case)
    adapter = FixedReadAdapter(state=engine_state)

    response = get_workflow_execution_with_context(execution_case.context, request(execution), adapter=adapter)

    execution.refresh_from_db()
    assert response["ok"] is True
    assert execution.status == expected_status
    assert execution.last_engine_state == engine_state
    assert execution.terminal_at is None
    assert execution.postcondition_status == ExecutionRun.PostconditionStatus.PENDING
    assert adapter.transaction_states == [False]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        ExecutionRun.Status.CREATED,
        ExecutionRun.Status.START_DISPATCHING,
        ExecutionRun.Status.START_UNCERTAIN,
    ],
)
def test_ready_readback_does_not_cross_the_start_dispatch_barrier(execution_case, status):
    execution = execution_at_state(execution_case, status)

    response = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=FixedReadAdapter(state="READY"),
    )

    execution.refresh_from_db()
    execution.run.refresh_from_db()
    assert response["ok"] is True
    assert execution.status == status
    assert execution.run.status == HarnessRunStatus.PUBLISHED
    assert execution.last_engine_state is None
    assert execution.heartbeat_at is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "start_status,engine_state,expected_status",
    [
        (ExecutionRun.Status.START_DISPATCHING, "RUNNING", ExecutionRun.Status.EXECUTING),
        (ExecutionRun.Status.START_UNCERTAIN, "RUNNING", ExecutionRun.Status.EXECUTING),
        (ExecutionRun.Status.START_UNCERTAIN, "SUSPENDED", ExecutionRun.Status.PAUSED),
    ],
)
def test_proven_started_readback_converges_the_start_saga(
    execution_case,
    start_status,
    engine_state,
    expected_status,
):
    execution = execution_at_state(execution_case, start_status)

    response = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=FixedReadAdapter(state=engine_state),
    )

    execution.refresh_from_db()
    assert response["ok"] is True
    assert execution.status == expected_status
    assert execution.last_engine_state == engine_state


@pytest.mark.django_db
def test_finished_readback_converges_start_uncertain_before_terminalizing(execution_case):
    execution = execution_at_state(execution_case, ExecutionRun.Status.START_UNCERTAIN)

    response = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=FixedReadAdapter(
            state="FINISHED",
            outputs={"A": NodeOutputEvidence.available({"result": "ok"})},
        ),
    )

    execution.refresh_from_db()
    assert response["ok"] is True
    assert execution.status == ExecutionRun.Status.SUCCEEDED
    assert execution.last_engine_state == "FINISHED"


@pytest.mark.django_db
def test_one_terminal_execution_does_not_terminalize_a_run_with_active_siblings(execution_case):
    succeeded = execution_at_state(
        execution_case,
        ExecutionRun.Status.EXECUTING,
        key="execution-read-success",
        task_ref="8102",
    )
    failed = execution_at_state(
        execution_case,
        ExecutionRun.Status.EXECUTING,
        key="execution-read-failure",
        task_ref="8103",
    )

    first = get_workflow_execution_with_context(
        execution_case.context,
        request(succeeded),
        adapter=FixedReadAdapter(
            state="FINISHED",
            outputs={"A": NodeOutputEvidence.available({"result": "ok"})},
        ),
    )
    execution_case.run.refresh_from_db()
    assert first["ok"] is True
    assert first["status"] == HarnessRunStatus.EXECUTING
    assert execution_case.run.status == HarnessRunStatus.EXECUTING

    second = get_workflow_execution_with_context(
        execution_case.context,
        request(failed),
        adapter=FixedReadAdapter(
            state="FINISHED",
            outputs={"A": NodeOutputEvidence.available({})},
        ),
    )
    execution_case.run.refresh_from_db()
    assert second["ok"] is False
    assert second["status"] == HarnessRunStatus.FAILED
    assert execution_case.run.status == HarnessRunStatus.FAILED


@pytest.mark.django_db
def test_finished_outputs_pass_and_revoke_execution_leases_before_terminal(execution_case):
    execution = started_execution(execution_case)
    now = timezone.now()
    TokenLease.objects.create(
        execution=execution,
        platform_app=execution.platform_app,
        actor=execution.actor,
        space_id=execution.space_id,
        resource_type=TokenLease.Resource.TASK,
        resource_id=execution.task_ref,
        permission=TokenLease.Permission.OPERATE,
        action=HarnessAction.START_WORKFLOW_EXECUTION,
        action_digest="a" * 64,
        issuer_ref="issuer://bkflow/execution/read-lease",
        token_fingerprint="b" * 64,
        issued_at=now,
        expires_at=now + datetime.timedelta(minutes=5),
        status=TokenLease.Status.ACTIVE,
    )
    adapter = FixedReadAdapter(
        state="FINISHED",
        outputs={"A": NodeOutputEvidence.available({"result": {"ok": True}})},
    )

    response = get_workflow_execution_with_context(execution_case.context, request(execution), adapter=adapter)

    execution.refresh_from_db()
    execution.run.refresh_from_db()
    assert response["ok"] is True
    assert response["status"] == HarnessRunStatus.SUCCEEDED
    assert execution.status == ExecutionRun.Status.SUCCEEDED
    assert execution.run.status == HarnessRunStatus.SUCCEEDED
    assert execution.postcondition_status == ExecutionRun.PostconditionStatus.PASSED
    assert TokenLease.objects.get(execution=execution).status == TokenLease.Status.REVOKED
    assert EvidenceEvent.objects.filter(execution=execution, event_type="EXECUTION_SUCCEEDED").count() == 1
    assert EvidenceBundle.objects.filter(execution=execution, outcome="SUCCEEDED").count() == 1


@pytest.mark.django_db
def test_finished_false_postcondition_is_failed_with_safe_bundle(execution_case):
    execution = started_execution(execution_case)
    adapter = FixedReadAdapter(
        state="FINISHED",
        outputs={"A": NodeOutputEvidence.available({"unrelated": "raw-downstream-secret"})},
    )

    response = get_workflow_execution_with_context(execution_case.context, request(execution), adapter=adapter)

    execution.refresh_from_db()
    execution.run.refresh_from_db()
    assert response["ok"] is False
    assert response["errors"][0]["category"] == "POSTCONDITION"
    assert execution.status == ExecutionRun.Status.FAILED
    assert execution.run.status == HarnessRunStatus.FAILED
    assert execution.postcondition_status == ExecutionRun.PostconditionStatus.FAILED
    assert EvidenceBundle.objects.filter(execution=execution, outcome="FAILED").count() == 1
    assert "raw-downstream-secret" not in str(response) + str(execution.postcondition_report)


@pytest.mark.django_db
def test_snapshot_drift_after_engine_read_does_not_revoke_leases_or_terminalize(execution_case):
    execution = started_execution(execution_case)

    class DriftingAdapter(FixedReadAdapter):
        def observe(self, task_ref, pipeline_tree, required_outputs):
            TemplateSnapshot.objects.filter(pk=execution.published_snapshot_id).update(data={"activities": {}})
            return super().observe(task_ref, pipeline_tree, required_outputs)

    broker = mock.Mock()
    response = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=DriftingAdapter(
            state="FINISHED",
            outputs={"A": NodeOutputEvidence.available({"result": "ok"})},
        ),
        token_broker=broker,
    )

    execution.refresh_from_db()
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert execution.status == ExecutionRun.Status.EXECUTING
    broker.revoke_execution_leases.assert_not_called()


@pytest.mark.django_db
def test_unavailable_finished_evidence_uses_one_immutable_server_deadline(execution_case):
    execution = started_execution(execution_case)
    observed_at = timezone.now()
    adapter = FixedReadAdapter(
        state="FINISHED",
        outputs={"A": NodeOutputEvidence.unavailable("node_detail_unavailable")},
    )

    first = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=adapter,
        clock=lambda: observed_at,
    )
    execution.refresh_from_db()
    first_report = execution.postcondition_report
    events_after_first = EvidenceEvent.objects.filter(execution=execution).count()
    second = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=adapter,
        clock=lambda: observed_at + datetime.timedelta(seconds=30),
    )
    execution.refresh_from_db()

    assert first["ok"] is True and second["ok"] is True
    assert execution.status == ExecutionRun.Status.EXECUTING
    assert execution.postcondition_status == ExecutionRun.PostconditionStatus.RUNNING
    assert execution.postcondition_report["terminal_observed_at"] == first_report["terminal_observed_at"]
    assert execution.postcondition_report["deadline_at"] == first_report["deadline_at"]
    assert EvidenceEvent.objects.filter(execution=execution).count() == events_after_first

    expired = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=adapter,
        clock=lambda: observed_at + datetime.timedelta(minutes=6),
    )
    execution.refresh_from_db()
    assert expired["ok"] is False
    assert expired["errors"][0]["category"] == "POSTCONDITION"
    assert execution.status == ExecutionRun.Status.FAILED
    assert execution.postcondition_status == ExecutionRun.PostconditionStatus.UNAVAILABLE
    assert execution.postcondition_report["deadline_at"] == first_report["deadline_at"]


@pytest.mark.django_db
@pytest.mark.parametrize("engine_state", ["REVOKED", "CANCELLED"])
def test_revoked_or_cancelled_engine_execution_becomes_cancelled(execution_case, engine_state):
    execution = started_execution(execution_case)

    response = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=FixedReadAdapter(state=engine_state),
    )

    execution.refresh_from_db()
    execution.run.refresh_from_db()
    assert response["ok"] is True
    assert execution.status == ExecutionRun.Status.CANCELLED
    assert execution.run.status == HarnessRunStatus.CANCELLED
    assert execution.postcondition_status == ExecutionRun.PostconditionStatus.UNAVAILABLE
    assert EvidenceBundle.objects.filter(execution=execution, outcome="CANCELLED").count() == 1


@pytest.mark.django_db
def test_terminal_replay_is_idempotent_without_engine_or_duplicate_evidence(execution_case):
    execution = started_execution(execution_case)
    first_adapter = FixedReadAdapter(
        state="FINISHED",
        outputs={"A": NodeOutputEvidence.available({"result": "ok"})},
    )
    first = get_workflow_execution_with_context(execution_case.context, request(execution), adapter=first_adapter)
    event_ids = list(EvidenceEvent.objects.filter(execution=execution).values_list("id", flat=True))
    bundle_id = EvidenceBundle.objects.get(execution=execution).id
    forbidden = FixedReadAdapter(error=AssertionError("terminal execution must not call Engine"))

    second = get_workflow_execution_with_context(execution_case.context, request(execution), adapter=forbidden)

    assert first["ok"] is True and second["ok"] is True
    assert forbidden.calls == []
    assert list(EvidenceEvent.objects.filter(execution=execution).values_list("id", flat=True)) == event_ids
    assert EvidenceBundle.objects.get(execution=execution).id == bundle_id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error,expected_code",
    [
        (TaskNotFound(), "VALIDATION_STALE"),
        (ReadbackUnavailable(), "RETRYABLE_INFRA"),
    ],
)
def test_task_missing_and_transient_read_failure_are_safe_and_non_mutating(execution_case, error, expected_code):
    execution = started_execution(execution_case)
    before = ExecutionRun.objects.values().get(pk=execution.pk)

    response = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=FixedReadAdapter(error=error),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == expected_code
    assert ExecutionRun.objects.values().get(pk=execution.pk) == before


@pytest.mark.django_db
def test_evidence_history_is_bounded_and_cursor_paginated(execution_case):
    execution = started_execution(execution_case)
    for index in range(3):
        record_evidence(
            run=execution.run,
            revision=execution.revision,
            execution=execution,
            event_type="EXECUTION_READ_FIXTURE",
            action="fixture",
            payload={"index": index},
            actor=execution.actor,
            correlation_id=execution_case.context.correlation_id,
        )
    adapter = FixedReadAdapter(state="RUNNING")

    first = get_workflow_execution_with_context(
        execution_case.context,
        request(execution, limit=2),
        adapter=adapter,
    )
    cursor = first["artifact_refs"][0]["history"]["next_cursor"]
    second = get_workflow_execution_with_context(
        execution_case.context,
        request(execution, limit=100, cursor=cursor),
        adapter=adapter,
    )

    first_ids = [item["event_id"] for item in first["artifact_refs"][0]["history"]["items"]]
    second_ids = [item["event_id"] for item in second["artifact_refs"][0]["history"]["items"]]
    assert first_ids and second_ids
    assert set(first_ids).isdisjoint(second_ids)
    assert first_ids + second_ids == [
        str(value)
        for value in EvidenceEvent.objects.filter(execution=execution)
        .order_by("occurred_at", "id")
        .values_list("id", flat=True)
    ]


def test_application_read_adapter_uses_only_real_bounded_read_apis():
    client = mock.Mock()
    client.get_task_states.return_value = {
        "result": True,
        "data": {
            "id": "runtime-root",
            "state": "FINISHED",
            "children": {
                "node-A": {"id": "runtime-A", "state": "FINISHED", "children": {}},
            },
        },
    }
    client.get_node_id_map.return_value = {"result": True, "data": {"A": "runtime-A"}}
    client.get_task_node_detail.return_value = {
        "result": True,
        "data": {
            "outputs": [
                {"key": "result", "value": {"ok": True}},
                {"key": "unrequested", "value": "must-not-project"},
            ],
            "history": ["must-not-project"],
            "ex_data": "must-not-project",
        },
    }
    adapter = ExecutionReadAdapter(space_id=1, client_factory=lambda **_kwargs: client)
    pipeline_tree = {
        "activities": {"A": {}},
        "gateways": {},
        "constants": {
            "${result}": {
                "source_type": "component_outputs",
                "source_info": {"A": ["result"]},
            }
        },
    }

    observation = adapter.observe("8101", pipeline_tree, (("A", "result"),))

    assert observation.state == "FINISHED"
    assert observation.node_outputs["A"].outputs == {"result": {"ok": True}}
    client.get_task_states.assert_called_once_with("8101")
    client.get_node_id_map.assert_called_once_with("8101")
    client.get_task_node_detail.assert_called_once_with("8101", "runtime-A", data={"include_data": True})
    assert not hasattr(client, "get_node_outputs") or client.get_node_outputs.call_count == 0
    client.render_context_with_node_outputs.assert_not_called()


@pytest.mark.parametrize(
    "wire_state,normalized_state",
    [
        ("CREATED", "READY"),
        ("NODE_SUSPENDED", "SUSPENDED"),
    ],
)
def test_application_read_adapter_normalizes_real_task_wire_states(wire_state, normalized_state):
    client = mock.Mock()
    client.get_task_states.return_value = {
        "result": True,
        "data": {"state": wire_state, "children": {}},
    }
    adapter = ExecutionReadAdapter(space_id=1, client_factory=lambda **_kwargs: client)

    observation = adapter.observe("8101", {"activities": {}, "gateways": {}, "constants": {}}, ())

    assert observation.state == normalized_state
    assert observation.node_outputs == {}


def test_application_read_adapter_maps_only_transport_http_status_404_to_not_found():
    client = mock.Mock()
    adapter = ExecutionReadAdapter(space_id=1, client_factory=lambda **_kwargs: client)
    pipeline_tree = {"activities": {}, "gateways": {}, "constants": {}}
    client.get_task_states.return_value = {
        "result": False,
        "message": "Request API error, status_code: 404",
        "http_status": 404,
    }

    with pytest.raises(TaskNotFound):
        adapter.observe("8101", pipeline_tree, ())

    client.get_task_states.return_value = {
        "result": False,
        "code": "404",
        "message": "application-level error",
    }
    with pytest.raises(ReadbackUnavailable):
        adapter.observe("8101", pipeline_tree, ())


@pytest.mark.django_db
@mock.patch("bkflow.contrib.api.http.requests.get")
def test_real_http_404_flows_through_task_client_to_safe_stale_envelope(mock_get, execution_case, caplog):
    execution = started_execution(execution_case)
    response_secret = "TASK_HTTP_404_RESPONSE_BODY_SENTINEL"
    internal_token = "TASK_HTTP_404_INTERNAL_TOKEN_SENTINEL"
    ModuleInfo.objects.update_or_create(
        space_id=execution.space_id,
        defaults={
            "code": "task",
            "url": "http://task.example",
            "token": internal_token,
            "type": "TASK",
            "isolation_level": "only_calculation",
        },
    )
    response = mock.Mock()
    response.ok = False
    response.status_code = 404
    response.json.return_value = {"detail": response_secret}
    response.content = response_secret.encode()
    mock_get.return_value = response
    before_execution = ExecutionRun.objects.values().get(pk=execution.pk)
    before_events = list(EvidenceEvent.objects.filter(execution=execution).values())
    caplog.set_level("DEBUG", logger="component")

    envelope = get_workflow_execution_with_context(execution_case.context, request(execution))

    assert envelope["ok"] is False
    assert envelope["errors"][0]["code"] == "VALIDATION_STALE"
    assert ExecutionRun.objects.values().get(pk=execution.pk) == before_execution
    assert list(EvidenceEvent.objects.filter(execution=execution).values()) == before_events
    serialized_db = repr(before_execution) + repr(before_events)
    assert response_secret not in repr(envelope)
    assert response_secret not in serialized_db
    assert response_secret not in caplog.text
    assert internal_token not in caplog.text


@pytest.mark.django_db
def test_real_expired_task_wire_state_fails_closed_as_lost_execution_evidence(execution_case):
    execution = started_execution(execution_case)
    client = mock.Mock()
    client.get_task_states.return_value = {
        "result": True,
        "data": {"state": "EXPIRED", "children": {}},
    }

    response = get_workflow_execution_with_context(
        execution_case.context,
        request(execution),
        adapter=ExecutionReadAdapter(space_id=execution.space_id, client_factory=lambda **_kwargs: client),
    )

    execution.refresh_from_db()
    assert response["ok"] is False
    assert response["errors"][0]["category"] == "EXECUTION"
    assert execution.status == ExecutionRun.Status.FAILED
    assert execution.last_engine_state == "EXPIRED"
    assert execution.postcondition_status == ExecutionRun.PostconditionStatus.UNAVAILABLE


def test_application_read_adapter_fails_closed_on_undeclared_nodes_and_oversized_maps():
    client = mock.Mock()
    client.get_task_states.return_value = {"result": True, "data": {"state": "FINISHED"}}
    adapter = ExecutionReadAdapter(space_id=1, client_factory=lambda **_kwargs: client)

    with pytest.raises(ValueError, match="declared"):
        adapter.observe("8101", {"activities": {}, "gateways": {}}, (("A", "result"),))

    with pytest.raises(ValueError, match="output"):
        adapter.observe(
            "8101",
            {"activities": {"A": {}}, "gateways": {}, "constants": {}},
            (("A", "result"),),
        )

    client.get_node_id_map.return_value = {
        "result": True,
        "data": {"node-{}".format(index): "runtime-{}".format(index) for index in range(1001)},
    }
    observation = adapter.observe(
        "8101",
        {
            "activities": {"A": {}},
            "gateways": {},
            "constants": {
                "${result}": {
                    "source_type": "component_outputs",
                    "source_info": {"A": ["result"]},
                }
            },
        },
        (("A", "result"),),
    )
    assert observation.node_outputs["A"].is_available is False
    client.get_task_node_detail.assert_not_called()


@pytest.mark.parametrize("node_state", ["CREATED", "READY", None])
def test_finished_root_does_not_read_detail_for_unexecuted_or_missing_target_node(node_state):
    client = mock.Mock()
    children = {} if node_state is None else {"node-A": {"id": "runtime-A", "state": node_state, "children": {}}}
    client.get_task_states.return_value = {
        "result": True,
        "data": {"id": "runtime-root", "state": "FINISHED", "children": children},
    }
    client.get_node_id_map.return_value = {"result": True, "data": {"A": "runtime-A"}}
    adapter = ExecutionReadAdapter(space_id=1, client_factory=lambda **_kwargs: client)
    pipeline_tree = {
        "activities": {"A": {}},
        "gateways": {},
        "constants": {
            "${result}": {
                "source_type": "component_outputs",
                "source_info": {"A": ["result"]},
            }
        },
    }

    observation = adapter.observe("8101", pipeline_tree, (("A", "result"),))

    assert observation.state == "FINISHED"
    assert observation.node_outputs["A"].is_available is False
    assert observation.node_outputs["A"].reason in {"node_not_executed", "node_state_unavailable"}
    client.get_task_node_detail.assert_not_called()


@pytest.mark.parametrize(
    "unsafe_value",
    [float("nan"), ("non-json-tuple",)],
)
def test_application_read_adapter_rejects_non_wire_engine_values(unsafe_value):
    client = mock.Mock()
    client.get_task_states.return_value = {
        "result": True,
        "data": {"state": "FINISHED", "unsafe": unsafe_value},
    }
    adapter = ExecutionReadAdapter(space_id=1, client_factory=lambda **_kwargs: client)

    with pytest.raises(ReadbackUnavailable):
        adapter.observe("8101", {"activities": {}, "gateways": {}}, ())


def test_application_read_adapter_rejects_huge_integer_before_projection():
    client = mock.Mock()
    client.get_task_states.return_value = {
        "result": True,
        "data": {
            "state": "FINISHED",
            "oversized_integer": 1 << (400 * 1024 * 8),
        },
    }
    adapter = ExecutionReadAdapter(space_id=1, client_factory=lambda **_kwargs: client)

    with pytest.raises(ReadbackUnavailable):
        adapter.observe("8101", {"activities": {}, "gateways": {}, "constants": {}}, ())
