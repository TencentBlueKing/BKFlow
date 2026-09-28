"""Harness step/global debug dispatch contracts."""

import copy
import datetime
import hashlib

import pytest

from bkflow.harness.constants import DebugMode, DebugSessionStatus
from bkflow.harness.models import (
    DebugSession,
    EvidenceEvent,
    HarnessIdempotencyRecord,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.debug.approval import DebugApprovalDecision
from bkflow.harness.services.debug.facade import (
    run_debug_with_context,
    start_debug_session_with_context,
)
from bkflow.harness.services.token_broker import TokenBroker
from bkflow.space.models import Space
from bkflow.template.models import (
    DebugContext,
    DebugNodeState,
    Template,
    TemplateSnapshot,
)
from tests.interface.template.debug.test_step_run import TREE_GATEWAY

pytest_plugins = ("tests.interface.harness.debug.test_start_session",)


def _started(start_case, *, mode=DebugMode.STEP):
    context, _run, _revision, _template, request, resolver = start_case
    response = start_debug_session_with_context(context, {**request, "mode": mode}, resolver=resolver)
    assert response["ok"] is True
    return context, DebugSession.objects.get(), resolver


def _step_request(session, **overrides):
    values = {
        "session_id": str(session.id),
        "expected_plan_hash": session.plan_hash,
        "mode": "step",
        "execution_mode": "mock",
        "node_id": "A",
        "input_overrides": {},
        "mock_result": "success",
        "mock_outputs": {"result": "mocked"},
        "mock_error": "",
        "idempotency_key": "run-step-1",
    }
    values.update(overrides)
    return values


TOO_DEEP = {"leaf": "ok"}
for _depth in range(10):
    TOO_DEEP = {"nested": TOO_DEEP}
TOO_MANY = {"items": list(range(101))}
TOO_LARGE = {"part_{:02d}".format(index): "x" * 4000 for index in range(20)}


@pytest.mark.django_db
def test_mock_step_success_updates_globals_emits_evidence_and_replays(start_case):
    context, session, resolver = _started(start_case)
    request = _step_request(session)

    first = run_debug_with_context(context, request, resolver=resolver)
    replay = run_debug_with_context(context, request, resolver=resolver)

    assert replay == first
    assert first["ok"] is True
    assert first["status"] == "DEBUGGING"
    assert first["next_actions"] == ["run_debug", "get_debug_session"]
    result = first["artifact_refs"][0]
    assert result == {
        "type": "debug_run",
        "session_id": str(session.id),
        "mode": "step",
        "node_id": "A",
        "execution_mode": "mock",
        "status": "finished",
        "outputs": {"result": "mocked"},
        "updated_global_vars": {"${result}": "mocked"},
        "engine_ref": None,
    }
    assert DebugContext.objects.get(pk=session.debug_context_id).global_vars == {"${result}": "mocked"}
    assert list(EvidenceEvent.objects.filter(action="run_debug").values_list("event_type", flat=True)) == [
        "DEBUG_RUN_STARTED",
        "DEBUG_RUN_COMPLETED",
    ]
    assert HarnessIdempotencyRecord.objects.filter(tool_name="run_debug", status="COMPLETED").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("mutation", ["artifact_template", "superseded_revision"])
def test_run_rejects_artifact_or_latest_revision_drift_before_barrier(start_case, mutation):
    """Stale managed identity has no Adapter, Evidence, or idempotency side effect."""
    context, session, resolver = _started(start_case)
    if mutation == "artifact_template":
        artifacts = copy.deepcopy(session.run.artifact_references)
        artifacts[0]["template_id"] = session.template_id + 1
        session.run.artifact_references = artifacts
        session.run.save(update_fields=["artifact_references"])
    else:
        WorkflowPlanRevision.objects.create(
            run=session.run,
            sequence=session.revision.sequence + 1,
            parent_revision=session.revision,
            intent_spec={"goal": "superseding revision"},
            canonical_a2flow={"version": "2.0", "nodes": []},
            plan_hash="f" * 64,
        )
    evidence_count = EvidenceEvent.objects.count()
    idempotency_count = HarnessIdempotencyRecord.objects.count()

    class ForbiddenAdapter:
        def __init__(self, **_kwargs):
            raise AssertionError("stale identity must not construct an Adapter")

    response = run_debug_with_context(
        context,
        _step_request(session),
        resolver=resolver,
        adapter_class=ForbiddenAdapter,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert EvidenceEvent.objects.count() == evidence_count
    assert HarnessIdempotencyRecord.objects.count() == idempotency_count


@pytest.mark.django_db
def test_stale_same_key_is_revalidated_before_completed_replay(start_case):
    """A prior success cannot be replayed after its revision is superseded."""
    context, session, resolver = _started(start_case)
    request = _step_request(session)
    first = run_debug_with_context(context, request, resolver=resolver)
    assert first["ok"] is True
    WorkflowPlanRevision.objects.create(
        run=session.run,
        sequence=session.revision.sequence + 1,
        parent_revision=session.revision,
        intent_spec={"goal": "superseding revision"},
        canonical_a2flow={"version": "2.0", "nodes": []},
        plan_hash="e" * 64,
    )
    evidence_count = EvidenceEvent.objects.count()
    idempotency_count = HarnessIdempotencyRecord.objects.count()

    class ForbiddenAdapter:
        def __init__(self, **_kwargs):
            raise AssertionError("stale replay must not construct an Adapter")

    stale = run_debug_with_context(
        context,
        request,
        resolver=resolver,
        adapter_class=ForbiddenAdapter,
    )

    assert stale["ok"] is False
    assert stale["errors"][0]["code"] == "VALIDATION_STALE"
    assert EvidenceEvent.objects.count() == evidence_count
    assert HarnessIdempotencyRecord.objects.count() == idempotency_count


@pytest.mark.django_db
def test_mock_failure_is_a_bounded_sdk_translation_and_closes_to_draft(start_case, mocker):
    context, session, resolver = _started(start_case)
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="mock-failure-space",
    )
    mocker.patch("bkflow.permission.services.token_issuer.TokenResourceValidator.validate", return_value=None)
    TokenBroker().acquire_debug_lease(context, session)
    failed = run_debug_with_context(
        context,
        _step_request(
            session,
            mock_result="fail",
            mock_outputs={},
            mock_error="expected failure",
            idempotency_key="run-step-fail",
        ),
        resolver=resolver,
    )
    assert failed["ok"] is True
    assert failed["artifact_refs"][0]["status"] == "failed"
    assert failed["artifact_refs"][0]["error"] == {
        "code": "DEBUG_EXECUTION_FAILED",
        "message": "Debug execution failed.",
    }
    assert EvidenceEvent.objects.filter(event_type="DEBUG_RUN_FAILED", action="run_debug").count() == 1
    session.refresh_from_db()
    session.run.refresh_from_db()
    assert session.status == DebugSessionStatus.FAILED
    assert session.run.status == "DRAFT_READY"
    assert not session.token_leases.filter(status="ACTIVE").exists()
    assert failed["next_actions"] == ["get_debug_session"]


@pytest.mark.django_db
def test_result_projection_redacts_sdk_context_residue_before_response_snapshot(start_case, caplog):
    """A legacy DebugContext credential cannot enter Envelope or durable replay."""
    sentinel = "task6-sdk-residue-secret"
    context, session, resolver = _started(start_case)
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    debug_context.global_vars = {"password": sentinel, "safe": "visible"}
    debug_context.save(update_fields=["global_vars"])

    response = run_debug_with_context(context, _step_request(session), resolver=resolver)
    replay = HarnessIdempotencyRecord.objects.get(tool_name="run_debug").response_snapshot

    assert response["ok"] is True
    assert response["artifact_refs"][0]["updated_global_vars"] == {
        "${result}": "mocked",
        "password": "[REDACTED]",
        "safe": "visible",
    }
    serialized = str(response) + str(replay) + str(list(EvidenceEvent.objects.values())) + caplog.text
    assert sentinel not in serialized


@pytest.mark.django_db
def test_result_projection_redacts_every_untrusted_sdk_result_field(start_case, caplog):
    """Outputs, globals, gateway expressions and errors share one safe projection."""
    sentinel = "task6-untrusted-result-secret"
    context, session, resolver = _started(start_case)

    class UnsafeResultAdapter:
        def __init__(self, **_kwargs):
            pass

        def run_step(self, _request, **_kwargs):
            return {
                "status": "failed",
                "outputs": {
                    "api_token": sentinel,
                    "access_key": sentinel,
                    "auth": sentinel,
                    "header": sentinel,
                    "credential_ref": "credential://id/{}".format(sentinel),
                },
                "updated_global_vars": {"message": "Bearer {}".format(sentinel)},
                "error_detail": {"message": "password={}".format(sentinel)},
                "selected_flow_ids": ["flow-safe"],
                "condition_results": [
                    {
                        "flow_id": "flow-safe",
                        "resolved_expression": "credential://{}".format(sentinel),
                    }
                ],
            }

    response = run_debug_with_context(
        context,
        _step_request(session, idempotency_key="run-unsafe-result"),
        resolver=resolver,
        adapter_class=UnsafeResultAdapter,
    )

    artifact = response["artifact_refs"][0]
    assert artifact["outputs"] == {
        "access_key": "[REDACTED]",
        "api_token": "[REDACTED]",
        "auth": "[REDACTED]",
        "credential_ref": "[REDACTED]",
        "header": "[REDACTED]",
    }
    assert artifact["updated_global_vars"] == {"message": "[REDACTED]"}
    assert artifact["condition_results"] == [{"flow_id": "flow-safe", "resolved_expression": "[REDACTED]"}]
    assert artifact["error"] == {
        "code": "DEBUG_EXECUTION_FAILED",
        "message": "Debug execution failed.",
    }
    serialized = (
        str(response)
        + str(HarnessIdempotencyRecord.objects.get(tool_name="run_debug").response_snapshot)
        + str(list(EvidenceEvent.objects.values()))
        + caplog.text
    )
    assert sentinel not in serialized


@pytest.mark.django_db
def test_oversized_sdk_result_returns_omission_metadata_without_fake_artifact(start_case):
    """An unsafe inline size is omitted without a truncated digest or fictional ref."""
    context, session, resolver = _started(start_case)

    class LargeResultAdapter:
        def __init__(self, **_kwargs):
            pass

        def run_step(self, _request, **_kwargs):
            return {
                "status": "finished",
                "outputs": {"large": "x" * 20000},
                "updated_global_vars": {},
            }

    response = run_debug_with_context(
        context,
        _step_request(session, idempotency_key="run-large-result"),
        resolver=resolver,
        adapter_class=LargeResultAdapter,
    )

    projection = response["artifact_refs"][0]["outputs"]
    assert projection == {
        "omitted": True,
        "reason": "projection_budget_exceeded",
        "redaction_version": "builtin-credential-v1",
    }
    assert "artifact_ref" not in projection
    assert "x" * 100 not in str(response)
    event = EvidenceEvent.objects.get(event_type="DEBUG_RUN_COMPLETED", action="run_debug")
    assert event.redacted_payload["output_omitted"] is True
    assert event.redacted_payload["output_omission_reason"] == "projection_budget_exceeded"
    assert "output_fingerprint" not in event.redacted_payload


@pytest.mark.django_db
def test_step_dependency_missing_is_safe_failure_without_result_evidence(start_case):
    context, session, resolver = _started(start_case)
    response = run_debug_with_context(
        context,
        _step_request(session, node_id="B", mock_outputs={}, idempotency_key="run-step-missing"),
        resolver=resolver,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_DEPENDENCY"
    assert DebugNodeState.objects.get(debug_context_id=session.debug_context_id, node_id="B").status == "not_run"
    assert not EvidenceEvent.objects.filter(event_type="DEBUG_RUN_COMPLETED", action="run_debug").exists()


@pytest.mark.django_db
def test_run_request_is_tagged_closed_and_same_key_cannot_change_inputs(start_case):
    context, session, resolver = _started(start_case)
    request = _step_request(session)
    invalid = run_debug_with_context(context, {**request, "actor": context.actor}, resolver=resolver)
    assert invalid["ok"] is False
    assert invalid["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"

    assert run_debug_with_context(context, request, resolver=resolver)["ok"] is True
    conflict = run_debug_with_context(
        context,
        {**request, "mock_outputs": {"result": "changed"}},
        resolver=resolver,
    )
    assert conflict["ok"] is False
    assert conflict["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mutation",
    [
        {"mock_outputs": {"api_token": "raw-secret"}},
        {"mock_outputs": {"api_key": "raw-secret"}},
        {"mock_outputs": {"access_key": "raw-secret"}},
        {"mock_outputs": {"auth": "raw-secret"}},
        {"mock_outputs": {"cookie": "raw-secret"}},
        {"mock_outputs": {"private_key": "raw-secret"}},
        {"input_overrides": {"nested": {"password": "raw-secret"}}},
        {"mock_outputs": {"message": "credential://id/raw-secret"}},
        {"mock_outputs": {"message": "Basic dXNlcjpwYXNz"}},
        {"mock_outputs": {"message": "Cookie: session=raw-secret"}},
        {"mock_outputs": {"message": "-----BEGIN PRIVATE KEY-----\nraw-secret\n-----END PRIVATE KEY-----"}},
        {"mock_error": "Bearer raw-secret"},
        {"node_id": "credential://id/raw-secret"},
        {"input_overrides": {"payload": object()}},
        {"input_overrides": {"ratio": float("nan")}},
        {"input_overrides": TOO_DEEP},
        {"input_overrides": TOO_MANY},
        {"input_overrides": TOO_LARGE},
        {
            "execution_mode": "real",
            "approval_receipt_ref": "approval://user:secret@trusted/receipt",
        },
        {
            "execution_mode": "real",
            "approval_receipt_ref": "approval://trusted/receipt?token=raw-secret",
        },
        {
            "execution_mode": "real",
            "approval_receipt_ref": "approval://trusted/receipt#raw-secret",
        },
    ],
)
def test_run_request_rejects_secret_shaped_or_non_json_values_before_dispatch(start_case, mutation, mocker):
    context, session, resolver = _started(start_case)
    dispatch = mocker.patch("bkflow.template.debug.service.DebugService.step_run")
    evidence_count = EvidenceEvent.objects.count()
    idempotency_count = HarnessIdempotencyRecord.objects.count()

    response = run_debug_with_context(context, _step_request(session, **mutation), resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    dispatch.assert_not_called()
    assert EvidenceEvent.objects.count() == evidence_count
    assert HarnessIdempotencyRecord.objects.count() == idempotency_count


@pytest.mark.django_db
@pytest.mark.parametrize("inputs", [{"password": "raw"}, TOO_DEEP, TOO_MANY, TOO_LARGE])
def test_global_inputs_obey_the_same_bounded_non_secret_json_gate(start_case, inputs, mocker):
    context, session, resolver = _started(start_case, mode=DebugMode.GLOBAL)
    dispatch = mocker.patch("bkflow.template.debug.service.DebugService.global_run")
    request = {
        "session_id": str(session.id),
        "expected_plan_hash": session.plan_hash,
        "mode": "global",
        "execution_mode": "mock",
        "inputs": inputs,
        "idempotency_key": "run-global-invalid",
    }
    evidence_count = EvidenceEvent.objects.count()
    idempotency_count = HarnessIdempotencyRecord.objects.count()

    response = run_debug_with_context(context, request, resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    dispatch.assert_not_called()
    assert EvidenceEvent.objects.count() == evidence_count
    assert HarnessIdempotencyRecord.objects.count() == idempotency_count


@pytest.mark.django_db
@pytest.mark.parametrize("mutation", ["foreign", "expired", "plan", "tree", "schema"])
def test_each_run_revalidates_authority_session_plan_tree_and_schema(start_case, mutation, mocker):
    context, session, resolver = _started(start_case)
    request = _step_request(session)
    if mutation == "foreign":
        context = context.__class__(**{**context.__dict__, "actor": "foreign"})
    elif mutation == "expired":
        mocker.patch(
            "bkflow.harness.services.debug.run.timezone.now",
            return_value=session.expires_at + datetime.timedelta(seconds=1),
        )
    elif mutation == "plan":
        request["expected_plan_hash"] = "f" * 64
    elif mutation == "tree":
        template = Template.objects.get(pk=session.template_id)
        snapshot = TemplateSnapshot.objects.get(pk=template.snapshot_id)
        changed = copy.deepcopy(snapshot.data)
        changed["activities"]["A"]["component"]["data"] = {"changed": {"value": True}}
        snapshot.data = changed
        snapshot.save(update_fields=["data"])
    else:
        resolver.capability.schema_hash = "d" * 64

    response = run_debug_with_context(context, request, resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] in {"CAPABILITY_FORBIDDEN", "DEBUG_SESSION", "VALIDATION_STALE"}
    assert not EvidenceEvent.objects.filter(action="run_debug").exists()


@pytest.mark.django_db
def test_global_requires_mock_forces_all_activities_and_returns_fast_ack(start_case, mocker):
    context, session, resolver = _started(start_case, mode=DebugMode.GLOBAL)
    task_client = mocker.MagicMock()
    task_client.create_task.return_value = {"result": True, "data": {"id": 7001}}
    task_client.operate_task.return_value = {"result": True}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=task_client)
    request = {
        "session_id": str(session.id),
        "expected_plan_hash": session.plan_hash,
        "mode": "global",
        "execution_mode": "mock",
        "inputs": {"${input}": "value"},
        "idempotency_key": "run-global-1",
    }

    response = run_debug_with_context(context, request, resolver=resolver)
    replay = run_debug_with_context(context, request, resolver=resolver)

    assert response["ok"] is True
    assert replay == response
    assert response["artifact_refs"][0]["status"] == "running"
    assert response["artifact_refs"][0]["engine_ref"] == {"task_id": 7001}
    assert response["next_actions"] == ["get_debug_session"]
    assert set(
        DebugNodeState.objects.filter(debug_context_id=session.debug_context_id).values_list(
            "execution_mode", flat=True
        )
    ) == {"mock"}
    session.refresh_from_db()
    assert session.status == DebugSessionStatus.RUNNING
    assert session.current_task_id == 7001
    assert EvidenceEvent.objects.filter(event_type="DEBUG_RUN_STARTED", action="run_debug").count() == 1
    assert not EvidenceEvent.objects.filter(
        event_type__in=["DEBUG_RUN_COMPLETED", "DEBUG_RUN_FAILED"], action="run_debug"
    ).exists()


@pytest.mark.django_db
def test_global_real_is_rejected_before_engine_access(start_case, mocker):
    context, session, resolver = _started(start_case, mode=DebugMode.GLOBAL)
    client = mocker.patch("bkflow.template.debug.service.DebugService.global_run")
    request = {
        "session_id": str(session.id),
        "expected_plan_hash": session.plan_hash,
        "mode": "global",
        "execution_mode": "real",
        "inputs": {},
        "idempotency_key": "run-global-real",
    }

    response = run_debug_with_context(context, request, resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_REQUIRED"
    assert response["errors"][0]["category"] == "APPROVAL"
    assert response["errors"][0]["suggested_action"] == "request_debug_approval"
    client.assert_not_called()


@pytest.mark.django_db
def test_engine_dispatch_is_barriered_before_post_ack_database_failure(start_case, mocker):
    """A committed in-flight claim prevents same-key Engine duplication after an ack."""
    context, session, resolver = _started(start_case, mode=DebugMode.GLOBAL)
    task_client = mocker.MagicMock()
    task_client.create_task.return_value = {"result": True, "data": {"id": 7101}}
    task_client.operate_task.return_value = {"result": True}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=task_client)
    original_save = HarnessIdempotencyRecord.save

    def fail_completed(record, *args, **kwargs):
        if record.status == "COMPLETED":
            raise RuntimeError("post-ack database failure")
        return original_save(record, *args, **kwargs)

    mocker.patch.object(HarnessIdempotencyRecord, "save", fail_completed)
    request = {
        "session_id": str(session.id),
        "expected_plan_hash": session.plan_hash,
        "mode": "global",
        "execution_mode": "mock",
        "inputs": {},
        "idempotency_key": "run-global-post-ack-failure",
    }

    first = run_debug_with_context(context, request, resolver=resolver)
    retry = run_debug_with_context(context, request, resolver=resolver)
    new_key_retry = run_debug_with_context(
        context,
        {**request, "idempotency_key": "run-global-post-ack-failure-new-key"},
        resolver=resolver,
    )

    assert first["ok"] is retry["ok"] is new_key_retry["ok"] is False
    assert {
        first["errors"][0]["code"],
        retry["errors"][0]["code"],
        new_key_retry["errors"][0]["code"],
    } == {"RETRYABLE_INFRA"}
    assert task_client.create_task.call_count == 1
    assert task_client.operate_task.call_count == 1
    barrier = HarnessIdempotencyRecord.objects.get(tool_name="run_debug", idempotency_key=request["idempotency_key"])
    assert barrier.status == "IN_FLIGHT"
    assert barrier.response_snapshot == {}
    assert barrier.run_id == session.run_id
    assert barrier.resource_reference == str(session.id)
    assert HarnessIdempotencyRecord.objects.filter(tool_name="run_debug").count() == 1
    session.refresh_from_db()
    assert session.status == DebugSessionStatus.ACTIVE
    assert not EvidenceEvent.objects.filter(action="run_debug").exists()


@pytest.mark.django_db
def test_barrier_binding_failure_rolls_back_the_empty_idempotency_claim(start_case, mocker):
    """A pre-dispatch binding error cannot strand an unowned IN_FLIGHT row."""
    context, session, resolver = _started(start_case)
    dispatch = mocker.patch("bkflow.template.debug.service.DebugService.step_run")
    mocker.patch(
        "bkflow.harness.services.idempotency.bind_inflight_idempotency",
        side_effect=RuntimeError("barrier binding failed"),
    )

    response = run_debug_with_context(context, _step_request(session), resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    dispatch.assert_not_called()
    assert not HarnessIdempotencyRecord.objects.filter(tool_name="run_debug").exists()


@pytest.mark.django_db
def test_gateway_step_evaluates_locally_and_returns_selected_flow(start_case, mocker):
    context, run, _revision, template, start_request, resolver = start_case
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="run-gateway-space",
    )
    mocker.patch("bkflow.permission.services.token_issuer.TokenResourceValidator.validate", return_value=None)
    snapshot = TemplateSnapshot.objects.get(pk=template.snapshot_id)
    snapshot.data = copy.deepcopy(TREE_GATEWAY)
    snapshot.save(update_fields=["data"])
    artifacts = copy.deepcopy(run.artifact_references)
    artifacts[0]["pipeline_tree_hash"] = sha256_json(TREE_GATEWAY)
    run.artifact_references = artifacts
    run.save(update_fields=["artifact_references"])
    report = run.validation_reports.get(checkpoint="VALIDATE")
    report.result["pipeline_tree_hash"] = artifacts[0]["pipeline_tree_hash"]
    report.save(update_fields=["result"])
    assert start_debug_session_with_context(context, start_request, resolver=resolver)["ok"] is True
    session = DebugSession.objects.get()
    broker = TokenBroker()
    broker.acquire_debug_lease(context, session)
    verifier = mocker.MagicMock()
    verifier.verify.return_value = DebugApprovalDecision(
        True,
        "test-provider",
        hashlib.sha256(b"approval://trusted/gateway-1").hexdigest(),
        "b" * 64,
        "approved",
    )
    engine = mocker.patch("bkflow.template.debug.service.DebugService._task_client")
    mocker.patch("bkflow.harness.services.debug.run.is_harness_real_step_enabled", return_value=True)

    response = run_debug_with_context(
        context,
        _step_request(
            session,
            node_id="G",
            execution_mode="real",
            input_overrides={"${g1}": 1},
            mock_outputs={},
            approval_receipt_ref="approval://trusted/gateway-1",
            idempotency_key="run-gateway",
        ),
        resolver=resolver,
        approval_verifier=verifier,
        token_broker=broker,
        allow_real=True,
    )

    assert response["ok"] is True
    artifact = response["artifact_refs"][0]
    assert artifact["status"] == "finished"
    assert artifact["selected_flow_ids"] == ["flow_positive"]
    engine.assert_not_called()
