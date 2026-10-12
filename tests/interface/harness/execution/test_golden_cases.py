"""Twenty-six table-driven P3 execution Golden Cases backed by real services."""

import copy
import datetime
import hashlib
import inspect

import pytest
from django.db import DatabaseError, connection
from django.utils import timezone

from bkflow.harness.constants import HarnessAction
from bkflow.harness.models import (
    ApprovalRequest,
    EvidenceEvent,
    ExecutionRun,
    HarnessIdempotencyRecord,
    ReleaseManifest,
    TokenLease,
)
from bkflow.harness.services.approval import (
    ApprovalVerifier,
    InMemoryApprovalReplayGuard,
)
from bkflow.harness.services.execution.adapter import (
    ControlDispatchReceipt,
    ControlObservation,
    ControlReadbackObservation,
    CreateDispatchUncertain,
    StartDispatchUncertain,
    TaskNotFound,
)
from bkflow.harness.services.execution.postconditions import NodeOutputEvidence
from bkflow.harness.services.release.policy import ReleasePolicy
from bkflow.space.configs import (
    FlowVersioning,
    HarnessExecutionEnabledConfig,
    SpaceConfigValueType,
)
from bkflow.space.models import SpaceConfig
from tests.interface.harness import p3_golden_support as golden
from tests.interface.harness.execution import test_control_execution as control_cases
from tests.interface.harness.execution import test_get_execution as read_cases
from tests.interface.harness.execution import test_start_execution as start_cases
from tests.interface.harness.release import test_prepare_release as prepare_cases
from tests.interface.harness.release import test_publish_workflow as publish_cases

START_CASES = [case for case in golden.EXECUTION_CASES if case["setup"]["driver"] == "start"]
READ_CASES = [case for case in golden.EXECUTION_CASES if case["setup"]["driver"] == "read"]
POSTCONDITION_CASES = [case for case in golden.EXECUTION_CASES if case["setup"]["driver"] == "postcondition"]
CONTROL_CASES = [case for case in golden.EXECUTION_CASES if case["setup"]["driver"] == "control"]

OUTPUT_EQUALS_SPEC = {
    "version": "harness-postconditions-p3-v1",
    "operator": "all",
    "predicates": [{"type": "OUTPUT_EQUALS", "node_id": "A", "output_key": "result", "expected_json": "ok"}],
}
WEBHOOK_SPEC = {
    "version": "harness-postconditions-p3-v1",
    "operator": "all",
    "predicates": [{"type": "WEBHOOK_DELIVERED", "event_type": "task_finished", "correlation_id": "golden-webhook"}],
}


@pytest.fixture
def golden_execution_builder(db):
    """Build a published graph; optional specs are server-owned before prepare."""

    def build(postcondition_spec=None):
        if postcondition_spec is None:
            return start_cases.execution_case.__wrapped__(db)
        builder = prepare_cases.release_case.__wrapped__(db)
        case = builder()
        SpaceConfig.objects.update_or_create(
            space_id=case.context.space_id,
            name=FlowVersioning.name,
            defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": "true"},
        )
        policy = ReleasePolicy(profiles={case.context.policy_version: postcondition_spec})
        prepared = prepare_cases.prepare(case, release_policy=policy)
        assert prepared["ok"] is True
        case.run.refresh_from_db()
        manifest = ReleaseManifest.objects.get(run=case.run)
        case.manifest = manifest
        case.publish_request = {
            "run_id": str(case.run.run_id),
            "manifest_id": str(manifest.id),
            "manifest_hash": manifest.manifest_hash,
            "version": "1.0.0",
            "description": "Golden custom policy publication",
            "idempotency_key": "golden-custom-publish",
        }
        first = publish_cases.publish(case, release_policy=policy)
        approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
        verifier = ApprovalVerifier(
            backend=publish_cases.ReceiptBackend(publish_cases.expected_claims(case, approval)),
            replay_guard=InMemoryApprovalReplayGuard(),
        )
        published = publish_cases.publish(
            case,
            {
                **case.publish_request,
                "approval_request_id": str(approval.id),
                "approval_receipt_ref": publish_cases.RECEIPT_REF,
            },
            release_policy=policy,
            approval_verifier=verifier,
        )
        assert published["ok"] is True
        case.run.refresh_from_db()
        case.publication = manifest.publication
        SpaceConfig.objects.update_or_create(
            space_id=case.context.space_id,
            name=HarnessExecutionEnabledConfig.name,
            defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": "true"},
        )
        case.start_request = {
            "run_id": str(case.run.run_id),
            "manifest_id": str(manifest.id),
            "publication_id": str(case.publication.id),
            "expected_plan_hash": manifest.plan_hash,
            "name": "Golden custom execution",
            "constants": {},
            "idempotency_key": "golden-custom-start",
        }
        case.release_policy = policy
        return case

    return build


def _runtime(case, *, execution=None, approval=None, receipt_ref=None):
    values = {
        "run_id": str(case.run.run_id),
        "revision_id": str(case.revision.id),
        "plan_hash": case.revision.plan_hash,
        "manifest_id": str(case.manifest.id),
        "manifest_hash": case.manifest.manifest_hash,
        "publication_id": str(case.publication.id),
        "execution_id": str(execution.id) if execution else "00000000-0000-0000-0000-000000000000",
        "approval_request_id": str(approval.id) if approval else "00000000-0000-0000-0000-000000000000",
        "approval_receipt_ref": receipt_ref or "approval://golden/pending",
    }
    return values


def _lease_state(execution):
    statuses = list(TokenLease._base_manager.filter(execution=execution).values_list("status", flat=True))
    if not statuses:
        return "none"
    if TokenLease.Status.ACTIVE in statuses:
        return "active"
    return "revoked" if TokenLease.Status.REVOKED in statuses else "expired"


def _seed_lease(case, execution, action):
    now = timezone.now()
    return TokenLease.objects.create(
        execution=execution,
        platform_app=execution.platform_app,
        actor=execution.actor,
        space_id=execution.space_id,
        resource_type=TokenLease.Resource.TASK,
        resource_id=execution.task_ref,
        permission=TokenLease.Permission.OPERATE,
        action=action,
        action_digest="a" * 64,
        issuer_ref="issuer://bkflow/golden-execution",
        token_fingerprint="b" * 64,
        issued_at=now,
        expires_at=now + datetime.timedelta(minutes=5),
        status=TokenLease.Status.ACTIVE,
    )


def _execution_result(case, response, tool, payload, before_ids, adapter_counts, trace, *, execution=None):
    return golden.ScenarioResult(
        response=response,
        context=case.context,
        run=case.run,
        revision=case.revision,
        template=case.template,
        snapshot=case.snapshot,
        tool=tool,
        payload=payload,
        event_types=golden.new_event_types(before_ids, run=case.run),
        mutation_counts={"publish": 0, **adapter_counts},
        execution=execution,
        token_lease_result=_lease_state(execution) if execution is not None else "none",
        service_trace=tuple(trace),
    )


def _idempotency_snapshot(execution, tool):
    record = HarnessIdempotencyRecord.objects.get(
        run=execution.run,
        tool_name=tool,
        resource_reference=str(execution.id),
    )
    return record.status, record.resource_reference


def _start_snapshot(execution, adapter):
    execution.refresh_from_db()
    actions = [item[0] for item in adapter.calls]
    status, resource = _idempotency_snapshot(execution, HarnessAction.START_WORKFLOW_EXECUTION)
    assert resource == str(execution.id)
    return {
        "execution_status": execution.status,
        "task_ref": execution.task_ref or "",
        "idempotency_status": status,
        "mutations": {
            "create": actions.count("create"),
            "start": actions.count("start"),
            "read": actions.count("read"),
        },
    }


def _control_snapshot(execution, adapter, logical_reads):
    execution.refresh_from_db()
    status, resource = _idempotency_snapshot(execution, "control_workflow_execution")
    assert resource == str(execution.id)
    return {
        "execution_status": execution.status,
        "idempotency_status": status,
        "mutations": {"control": adapter.dispatch_calls, "read": logical_reads},
    }


def _approved_start(case, fixture_case, trace, *, payload=None):
    tool, pending_payload = golden.materialize_request(fixture_case, **_runtime(case))
    pending_payload.pop("approval_request_id", None)
    pending_payload.pop("approval_receipt_ref", None)
    first = golden.invoke_service(
        trace,
        tool,
        case.context,
        pending_payload,
        resolver=case.resolver,
        release_policy=case.release_policy,
        converter_class=prepare_cases.ReleaseConverter,
        credential_resolver=start_cases.RecordingCredentialResolver(),
        adapter=start_cases.RecordingAdapter(),
    )
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    receipt_ref = fixture_case["approval"]["receipt_ref"]
    tool, approved_payload = golden.materialize_request(
        fixture_case,
        **_runtime(case, approval=approval, receipt_ref=receipt_ref),
    )
    if payload:
        approved_payload.update(payload)
    backend = publish_cases.ReceiptBackend(start_cases.start_claims(case, approval))
    verifier = ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard())
    return tool, approved_payload, verifier


def _execute_start(fixture_case, builder, monkeypatch):
    golden.assert_case_declarations(fixture_case)
    case = builder()
    golden.apply_declared_policy(case.context.space_id, fixture_case)
    sequence = fixture_case["engine_sequence"]
    trace = []
    tool, payload, verifier = _approved_start(case, fixture_case, trace)
    before_ids = set(EvidenceEvent._base_manager.values_list("id", flat=True))
    adapter = start_cases.RecordingAdapter()
    kwargs = {}
    intermediate = {}
    create_steps = [item for item in sequence if item.startswith("create:")]
    if create_steps and create_steps[0].split(":", 1)[1].isdigit():
        task_ref = create_steps[0].split(":", 1)[1]

        def create_with_declared_ref(*, publication, request, credentials):
            adapter.calls.append(("create", publication.published_snapshot_id, copy.deepcopy(credentials)))
            adapter.transaction_states.append(connection.in_atomic_block)
            return task_ref

        adapter.create = create_with_declared_ref
    late_receipts = [item.split(":", 1)[1] for item in sequence if item.startswith("late_receipt:")]
    if late_receipts:
        task_ref = late_receipts[0]

        def create_with_late_receipt(*, publication, request, credentials):
            adapter.calls.append(("create", publication.published_snapshot_id, copy.deepcopy(credentials)))
            adapter.transaction_states.append(connection.in_atomic_block)
            return task_ref

        adapter.create = create_with_late_receipt
    if "crash_before_create" in sequence:
        kwargs["test_after_create_barrier_hook"] = lambda _execution: (_ for _ in ()).throw(
            RuntimeError("golden crash before create")
        )
    elif "create:uncertain" in sequence and "late_receipt:8103" not in sequence:
        adapter.create_error = CreateDispatchUncertain()
    elif "persist_task_ref_crash" in sequence:
        original = ExecutionRun.save
        failed = {"value": False}

        def fail_task_ref(instance, *args, **values):
            if instance.task_ref and instance.status == ExecutionRun.Status.CREATED and not failed["value"]:
                failed["value"] = True
                raise DatabaseError("golden task-ref persist crash")
            return original(instance, *args, **values)

        monkeypatch.setattr(ExecutionRun, "save", fail_task_ref)
    elif any(item.startswith("late_receipt:") for item in sequence):

        def stale_nested(execution):
            stale_at = timezone.now() - datetime.timedelta(minutes=5)
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE {} SET update_at = %s WHERE id = %s".format(ExecutionRun._meta.db_table),
                    [stale_at, execution.id.hex],
                )
            nested_response = golden.invoke_service(
                trace,
                tool,
                case.context,
                payload,
                resolver=case.resolver,
                release_policy=case.release_policy,
                converter_class=prepare_cases.ReleaseConverter,
                credential_resolver=start_cases.RecordingCredentialResolver(),
                approval_verifier=verifier,
                adapter=adapter,
            )
            assert golden.response_code(nested_response) == "RETRYABLE_INFRA"
            intermediate["after_fault"] = _start_snapshot(execution, adapter)

        kwargs["test_after_create_barrier_hook"] = stale_nested
    elif "crash_before_start" in sequence:
        kwargs["test_after_task_persist_hook"] = lambda _execution: (_ for _ in ()).throw(
            RuntimeError("golden crash before start")
        )
    elif "start:uncertain" in sequence and "read:RUNNING" in sequence:
        adapter.start_error = StartDispatchUncertain()
        adapter._read_state = "RUNNING"
    elif "start:uncertain" in sequence and "read:unavailable" in sequence:
        adapter.start_error = StartDispatchUncertain()
        adapter._read_state = RuntimeError("golden readback unavailable")
    response = golden.invoke_service(
        trace,
        tool,
        case.context,
        payload,
        resolver=case.resolver,
        release_policy=case.release_policy,
        converter_class=prepare_cases.ReleaseConverter,
        credential_resolver=start_cases.RecordingCredentialResolver(),
        approval_verifier=verifier,
        adapter=adapter,
        **kwargs,
    )
    execution = ExecutionRun.objects.filter(run=case.run).first()
    needs_explicit_retry = any(
        marker in sequence
        for marker in (
            "crash_before_create",
            "persist_task_ref_crash",
            "crash_before_start",
            "read:unavailable",
        )
    ) or ("create:uncertain" in sequence and not any(item.startswith("late_receipt:") for item in sequence))
    if needs_explicit_retry:
        intermediate["after_fault"] = _start_snapshot(execution, adapter)
        if "read:unavailable" in sequence:
            adapter._read_state = "RUNNING"
        response = golden.invoke_service(
            trace,
            tool,
            case.context,
            payload,
            resolver=case.resolver,
            release_policy=case.release_policy,
            converter_class=prepare_cases.ReleaseConverter,
            credential_resolver=start_cases.RecordingCredentialResolver(),
            approval_verifier=verifier,
            adapter=adapter,
        )
        intermediate["after_retry"] = _start_snapshot(execution, adapter)
    elif any(item.startswith("late_receipt:") for item in sequence):
        intermediate["after_retry"] = _start_snapshot(execution, adapter)
    if intermediate:
        assert intermediate["after_fault"] == fixture_case["after_fault"]
        assert intermediate["after_retry"] == fixture_case["after_retry"]
    action_names = [item[0] for item in adapter.calls]
    return _execution_result(
        case,
        response,
        tool,
        payload,
        before_ids,
        {
            "create": action_names.count("create"),
            "start": action_names.count("start"),
            "control": 0,
            "read": action_names.count("read"),
        },
        trace,
        execution=execution,
    )


def _start_precondition(case, trace):
    first = golden.invoke_service(
        trace,
        HarnessAction.START_WORKFLOW_EXECUTION,
        case.context,
        case.start_request,
        resolver=case.resolver,
        release_policy=case.release_policy,
        converter_class=prepare_cases.ReleaseConverter,
        credential_resolver=start_cases.RecordingCredentialResolver(),
        adapter=start_cases.RecordingAdapter(),
    )
    verifier, _ = start_cases.approved_verifier(case, first)
    response = golden.invoke_service(
        trace,
        HarnessAction.START_WORKFLOW_EXECUTION,
        case.context,
        start_cases.approved_payload(case, first),
        resolver=case.resolver,
        release_policy=case.release_policy,
        converter_class=prepare_cases.ReleaseConverter,
        credential_resolver=start_cases.RecordingCredentialResolver(),
        approval_verifier=verifier,
        adapter=start_cases.RecordingAdapter(),
    )
    assert response["ok"] is True
    case.run.refresh_from_db()
    return ExecutionRun.objects.get(run=case.run)


def _execute_read(fixture_case, builder):
    golden.assert_case_declarations(fixture_case)
    setup = fixture_case["setup"]
    sequence = fixture_case["engine_sequence"]
    spec = OUTPUT_EQUALS_SPEC if "output:A.result=unexpected" in sequence else None
    case = builder(spec)
    trace = []
    execution = _start_precondition(case, trace)
    golden.apply_declared_policy(case.context.space_id, fixture_case)
    if setup.get("seed_events"):
        from bkflow.harness.services.evidence import record_evidence

        for index in range(setup["seed_events"]):
            record_evidence(
                run=case.run,
                revision=case.revision,
                execution=execution,
                event_type="EXECUTION_READ_FIXTURE",
                action="golden_fixture",
                payload={"index": index},
                actor=case.context.actor,
                correlation_id=case.context.correlation_id,
            )
    if "read:FINISHED" in sequence:
        _seed_lease(case, execution, HarnessAction.START_WORKFLOW_EXECUTION)
    before_ids = set(EvidenceEvent._base_manager.values_list("id", flat=True))
    tool, payload = golden.materialize_request(fixture_case, **_runtime(case, execution=execution))
    error = TaskNotFound() if "read:404" in sequence else None
    outputs = {}
    if "output:A.result=ok" in sequence:
        outputs = {"A": NodeOutputEvidence.available({"result": "ok"})}
    elif "output:A.result=missing" in sequence:
        outputs = {"A": NodeOutputEvidence.available({})}
    elif "output:A.result=unexpected" in sequence:
        outputs = {"A": NodeOutputEvidence.available({"result": "unexpected"})}
    adapter = read_cases.FixedReadAdapter(
        state=(
            next((item.split(":", 1)[1] for item in sequence if item.startswith("read:")), "RUNNING")
            if error is None
            else "RUNNING"
        ),
        outputs=outputs,
        error=error,
    )
    response = golden.invoke_service(trace, tool, case.context, payload, adapter=adapter)
    expected_history = fixture_case["expected"].get("history")
    if expected_history is not None:
        first_history = response["artifact_refs"][0]["history"]
        stable = golden.invoke_service(trace, tool, case.context, payload, adapter=adapter)
        stable_history = stable["artifact_refs"][0]["history"]
        assert len(first_history["items"]) == expected_history["items"]
        assert bool(first_history["next_cursor"]) is expected_history["has_cursor"]
        assert stable_history == first_history
        next_page = golden.invoke_service(
            trace,
            tool,
            case.context,
            {**payload, "cursor": first_history["next_cursor"]},
            adapter=adapter,
        )
        first_ids = [item["event_id"] for item in first_history["items"]]
        next_ids = [item["event_id"] for item in next_page["artifact_refs"][0]["history"]["items"]]
        assert first_ids
        assert next_ids
        assert set(first_ids).isdisjoint(next_ids)
    return _execution_result(
        case,
        response,
        tool,
        payload,
        before_ids,
        {"create": 0, "start": 0, "control": 0, "read": len(adapter.calls)},
        trace,
        execution=execution,
    )


def _execute_webhook_deadline(fixture_case, builder):
    golden.assert_case_declarations(fixture_case)
    engine_sequence = fixture_case["engine_sequence"]
    read_token = next(item for item in engine_sequence if item.startswith("read:"))
    read_state, _node_version = _parse_state_token(read_token, "read:")
    assert "webhook:unavailable" in engine_sequence
    case = builder(WEBHOOK_SPEC)
    trace = []
    execution = _start_precondition(case, trace)
    golden.apply_declared_policy(case.context.space_id, fixture_case)
    _seed_lease(case, execution, HarnessAction.START_WORKFLOW_EXECUTION)
    tool, payload = golden.materialize_request(fixture_case, **_runtime(case, execution=execution))
    before_ids = set(EvidenceEvent._base_manager.values_list("id", flat=True))
    observed_at = timezone.now()
    adapter = read_cases.FixedReadAdapter(state=read_state)
    first = golden.invoke_service(
        trace,
        tool,
        case.context,
        payload,
        adapter=adapter,
        clock=lambda: observed_at,
    )
    assert first["ok"] is True
    response = golden.invoke_service(
        trace,
        tool,
        case.context,
        payload,
        adapter=adapter,
        clock=lambda: observed_at + datetime.timedelta(minutes=6),
    )
    return _execution_result(
        case,
        response,
        tool,
        payload,
        before_ids,
        {"create": 0, "start": 0, "control": 0, "read": len(adapter.calls)},
        trace,
        execution=execution,
    )


def _parse_state_token(token, prefix):
    assert token.startswith(prefix)
    value = token[len(prefix) :]
    state, separator, version = value.partition("/")
    assert state
    return state, version if separator else None


class GoldenControlAdapter:
    """A closed Engine double driven only by the declared Engine sequence."""

    def __init__(self, engine_sequence):
        self.engine_sequence = tuple(engine_sequence)
        self.preflight_calls = 0
        self.dispatch_calls = 0

    def control_preflight(self, task_ref, request, pipeline_tree):
        self.preflight_calls += 1
        root_state, node_version = _parse_state_token(self.engine_sequence[0], "preflight:")
        values = {
            "task_ref": task_ref,
            "root_state": root_state,
            "action": request.action,
        }
        if request.template_node_id is not None:
            values.update(
                template_node_id=request.template_node_id,
                runtime_node_id="runtime-A",
                node_state=root_state,
                node_version=node_version,
                published_node_type="ServiceActivity",
                published_retryable=True,
                published_skippable=True,
            )
        return ControlObservation(**values)

    def control_dispatch(self, task_ref, request, observation, pipeline_tree):
        assert "control:ack" in self.engine_sequence
        self.dispatch_calls += 1
        return ControlDispatchReceipt(acknowledged=True)


def _control_readback(engine_sequence, action):
    read_token = next(item for item in engine_sequence if item.startswith("read:"))
    state, node_version = _parse_state_token(read_token, "read:")
    if action in {"pause", "resume", "revoke"}:
        return ControlReadbackObservation(root_state=state)
    return ControlReadbackObservation(
        root_state="RUNNING",
        template_node_id="A",
        node_state=state,
        node_version=node_version,
        runtime_mapping_fingerprint=hashlib.sha256(b"A\0runtime-A").hexdigest(),
    )


def _execute_control(fixture_case, builder):
    golden.assert_case_declarations(fixture_case)
    setup = fixture_case["setup"]
    engine_sequence = fixture_case["engine_sequence"]
    case = builder()
    trace = []
    execution = _start_precondition(case, trace)
    golden.apply_declared_policy(case.context.space_id, fixture_case)
    if setup.get("execution_status") == ExecutionRun.Status.PAUSED:
        execution.status = ExecutionRun.Status.PAUSED
        execution.save(update_fields=["status", "update_at"])
    tool, pending_payload = golden.materialize_request(fixture_case, **_runtime(case, execution=execution))
    action = pending_payload["action"]
    _seed_lease(case, execution, action)
    adapter = GoldenControlAdapter(engine_sequence)
    pending_payload.pop("approval_request_id", None)
    pending_payload.pop("approval_receipt_ref", None)
    first = golden.invoke_service(trace, tool, case.context, pending_payload, adapter=adapter)
    assert "approval_request_id" in first, first
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    receipt_ref = fixture_case["approval"]["receipt_ref"]
    tool, payload = golden.materialize_request(
        fixture_case,
        **_runtime(case, execution=execution, approval=approval, receipt_ref=receipt_ref),
    )
    backend = control_cases.ControlReceiptBackend(control_cases.control_claims(case, approval))
    verifier = ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard())
    before_ids = set(EvidenceEvent._base_manager.values_list("id", flat=True))
    kwargs = {}
    if "crash_before_control" in engine_sequence:
        kwargs["test_after_barrier_hook"] = lambda: (_ for _ in ()).throw(RuntimeError("golden control barrier crash"))
    if "crash_after_dispatch" in engine_sequence:
        kwargs["test_after_dispatch_hook"] = lambda: (_ for _ in ()).throw(
            RuntimeError("golden control dispatch crash")
        )
    response = golden.invoke_service(
        trace,
        tool,
        case.context,
        payload,
        adapter=adapter,
        approval_verifier=verifier,
        **kwargs,
    )
    intermediate = {}
    if "crash_before_control" in engine_sequence or "crash_after_dispatch" in engine_sequence:
        intermediate["after_fault"] = _control_snapshot(execution, adapter, 0)
    if "crash_before_control" in engine_sequence:
        response = golden.invoke_service(
            trace,
            tool,
            case.context,
            payload,
            adapter=adapter,
            approval_verifier=verifier,
        )
        intermediate["after_retry"] = _control_snapshot(execution, adapter, 0)
    logical_reads = 0
    if any(item.startswith("read:") for item in engine_sequence):
        read_adapter = control_cases.FixedControlReadAdapter(_control_readback(engine_sequence, action))
        response = golden.invoke_service(
            trace,
            "get_workflow_execution",
            case.context,
            {"execution_id": str(execution.id), "limit": 20},
            adapter=read_adapter,
        )
        logical_reads = len(read_adapter.calls)
        if "crash_after_dispatch" in engine_sequence:
            intermediate["after_retry"] = _control_snapshot(execution, adapter, logical_reads)
    if intermediate:
        assert intermediate["after_fault"] == fixture_case["after_fault"]
        assert intermediate["after_retry"] == fixture_case["after_retry"]
    return _execution_result(
        case,
        response,
        tool,
        payload,
        before_ids,
        {
            "create": 0,
            "start": 0,
            "control": adapter.dispatch_calls,
            "read": logical_reads,
        },
        trace,
        execution=execution,
    )


def test_execution_partition_is_exact_and_disjoint_from_release_and_secret():
    golden.validate_fixture_structure()
    assert len(START_CASES) == 8
    assert len(READ_CASES) == 9
    assert len(POSTCONDITION_CASES) == 1
    assert len(CONTROL_CASES) == 8


def test_recovery_rows_declare_intermediate_and_retry_durable_facts():
    recovery_markers = {
        "late_receipt:8103",
        "persist_task_ref_crash",
        "crash_before_start",
        "read:unavailable",
    }
    for case in START_CASES:
        if recovery_markers.intersection(case["engine_sequence"]):
            assert "after_fault" in case
            assert "after_retry" in case
            assert "task_ref" in case["expected"]
    for case in CONTROL_CASES:
        if "crash_before_control" in case["engine_sequence"] or "crash_after_dispatch" in case["engine_sequence"]:
            assert "after_fault" in case
            assert "after_retry" in case


def test_trace_contract_counts_pending_approval_and_recovery_public_calls():
    assert golden.expected_service_trace(START_CASES[0]) == (
        "start_workflow_execution",
        "start_workflow_execution",
    )
    assert golden.expected_service_trace(CONTROL_CASES[0]) == (
        "start_workflow_execution",
        "start_workflow_execution",
        "control_workflow_execution",
        "control_workflow_execution",
        "get_workflow_execution",
    )
    barrier_case = next(case for case in CONTROL_CASES if "crash_before_control" in case["engine_sequence"])
    assert golden.expected_service_trace(barrier_case) == (
        "start_workflow_execution",
        "start_workflow_execution",
        "control_workflow_execution",
        "control_workflow_execution",
        "control_workflow_execution",
    )


def test_flag_off_is_declared_only_by_the_golden_policy():
    case = next(item for item in READ_CASES if item["policy"]["execution_enabled"] is False)
    assert "execution_flag" not in case["setup"]
    assert case["policy"]["execution_enabled"] is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("fixture_case", START_CASES, ids=lambda case: case["id"])
def test_create_start_golden_case_drives_saga_and_durable_state(fixture_case, golden_execution_builder, monkeypatch):
    result = _execute_start(fixture_case, golden_execution_builder, monkeypatch)
    golden.assert_common_contract(fixture_case, result)
    assert result.execution is not None


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("fixture_case", READ_CASES, ids=lambda case: case["id"])
def test_readback_golden_case_drives_projection_and_durable_state(fixture_case, golden_execution_builder):
    result = _execute_read(fixture_case, golden_execution_builder)
    golden.assert_common_contract(fixture_case, result)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("fixture_case", POSTCONDITION_CASES, ids=lambda case: case["id"])
def test_webhook_deadline_golden_case_drives_false_success_guard(fixture_case, golden_execution_builder):
    result = _execute_webhook_deadline(fixture_case, golden_execution_builder)
    golden.assert_common_contract(fixture_case, result)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("fixture_case", CONTROL_CASES, ids=lambda case: case["id"])
def test_control_golden_case_drives_control_and_recovery_state(fixture_case, golden_execution_builder):
    result = _execute_control(fixture_case, golden_execution_builder)
    golden.assert_common_contract(fixture_case, result)


@pytest.mark.django_db
def test_execution_runners_do_not_branch_on_case_id():
    sources = "".join(
        inspect.getsource(function)
        for function in (_execute_start, _execute_read, _execute_webhook_deadline, _execute_control)
    )
    assert '["id"]' not in sources
    assert "['id']" not in sources
