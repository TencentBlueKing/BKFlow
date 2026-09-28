"""Task9 segment one: closed control contracts and safe application adapter DTOs."""

import copy
import hashlib
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

import pytest
from django.db import connection
from django.utils import timezone

from bkflow.harness.constants import HarnessAction
from bkflow.harness.models import (
    ApprovalRequest,
    EvidenceBundle,
    EvidenceEvent,
    ExecutionRun,
    HarnessIdempotencyRecord,
    TokenLease,
)
from bkflow.harness.services.approval import (
    ApprovalVerifier,
    InMemoryApprovalReplayGuard,
)
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.execution.adapter import (
    ApplicationTaskAdapter,
    ControlActionUnavailable,
    ControlDispatchReceipt,
    ControlDispatchUncertain,
    ControlObservation,
    ControlReadbackObservation,
    ExecutionObservation,
    ExecutionReadAdapter,
    ReadbackUnavailable,
    TaskNotFound,
)
from bkflow.harness.services.execution.contracts import (
    StartExecutionRejected,
    validate_control_execution_request,
)
from bkflow.harness.services.execution.control import (
    _journal_payload,
    _receipt_is_acknowledged,
    control_workflow_execution_with_context,
)
from bkflow.harness.services.execution.postconditions import NodeOutputEvidence
from bkflow.harness.services.execution.read import get_workflow_execution_with_context
from bkflow.harness.services.idempotency import complete_idempotency
from bkflow.space.configs import HarnessExecutionEnabledConfig
from bkflow.space.models import SpaceConfig
from tests.interface.harness.execution import test_start_execution as start_cases

EXECUTION_ID = "00000000-0000-0000-0000-000000000001"
EXPECTED_MANIFEST_HASH = "a" * 64
CONTROL_IDENTITY = {"execution_id": EXECUTION_ID, "expected_manifest_hash": EXPECTED_MANIFEST_HASH}


@pytest.mark.parametrize(
    "payload",
    [
        {**CONTROL_IDENTITY, "action": "pause", "idempotency_key": "control-1"},
        {**CONTROL_IDENTITY, "action": "resume", "idempotency_key": "control-1"},
        {**CONTROL_IDENTITY, "action": "revoke", "idempotency_key": "control-1"},
        {
            **CONTROL_IDENTITY,
            "action": "retry",
            "idempotency_key": "control-1",
            "template_node_id": "A",
            "loop": False,
            "inputs": {"region": "gz"},
        },
        {
            **CONTROL_IDENTITY,
            "action": "skip",
            "idempotency_key": "control-1",
            "template_node_id": "A",
            "loop": False,
        },
        {
            **CONTROL_IDENTITY,
            "action": "callback",
            "idempotency_key": "control-1",
            "template_node_id": "A",
            "callback_data": {"result": "ok"},
        },
        {
            **CONTROL_IDENTITY,
            "action": "forced_fail",
            "idempotency_key": "control-1",
            "template_node_id": "A",
            "reason_code": "operator_requested",
        },
        {
            **CONTROL_IDENTITY,
            "action": "skip_exg",
            "idempotency_key": "control-1",
            "template_gateway_id": "gateway-A",
            "template_flow_id": "flow-A",
        },
        {
            **CONTROL_IDENTITY,
            "action": "skip_cpg",
            "idempotency_key": "control-1",
            "template_gateway_id": "gateway-A",
            "template_flow_ids": ["flow-A", "flow-B"],
            "template_converge_gateway_id": "gateway-B",
        },
    ],
)
def test_all_nine_control_actions_have_exact_closed_wire_schemas(payload):
    parsed = validate_control_execution_request(payload)

    assert parsed.action == payload["action"]
    assert parsed.action_payload() == payload


def test_control_approval_fields_are_an_all_or_nothing_closed_pair():
    payload = {**CONTROL_IDENTITY, "action": "pause", "idempotency_key": "control-1"}
    approved = validate_control_execution_request(
        {
            **payload,
            "approval_request_id": "00000000-0000-0000-0000-000000000002",
            "approval_receipt_ref": "approval://bkaidev/control-receipt",
        }
    )

    assert approved.has_approval is True
    assert approved.action_payload() == payload
    with pytest.raises(StartExecutionRejected):
        validate_control_execution_request({**payload, "approval_request_id": approved.approval_request_id})


def test_retry_inputs_are_optional_but_loop_is_required_and_strict_boolean():
    payload = {
        **CONTROL_IDENTITY,
        "action": "retry",
        "idempotency_key": "control-1",
        "template_node_id": "A",
        "loop": False,
    }

    assert validate_control_execution_request(payload).action_payload() == payload
    for invalid in ({key: value for key, value in payload.items() if key != "loop"}, {**payload, "loop": 0}):
        with pytest.raises(StartExecutionRejected):
            validate_control_execution_request(invalid)


@pytest.mark.parametrize(
    "mutation",
    [
        {"task_ref": "8101"},
        {"runtime_node_id": "runtime-A"},
        {"node_id": "A"},
        {"flow_id": "flow-A"},
        {"operator": "attacker"},
        {"identity": "attacker"},
        {"credential": "raw"},
        {"token": "raw"},
        {"loop": True},
        {"suppress_failure_side_effects": True},
        {"send_post_set_state_signal": False},
    ],
)
def test_control_contract_rejects_caller_authority_and_low_level_flags(mutation):
    payload = {**CONTROL_IDENTITY, "action": "pause", "idempotency_key": "control-1", **mutation}

    with pytest.raises(StartExecutionRejected) as error:
        validate_control_execution_request(payload)

    assert error.value.code == "SCHEMA_VALIDATION_ERROR"


@pytest.mark.parametrize(
    "inputs",
    [
        {"password": "SECRET_SENTINEL"},
        {"safe": "x" * (70 * 1024)},
        {"safe": float("nan")},
    ],
)
def test_retry_inputs_are_bounded_strict_json_and_non_secret(inputs):
    payload = {
        **CONTROL_IDENTITY,
        "action": "retry",
        "idempotency_key": "control-1",
        "template_node_id": "A",
        "loop": False,
        "inputs": inputs,
    }

    with pytest.raises(StartExecutionRejected) as error:
        validate_control_execution_request(payload)

    assert error.value.code == "SCHEMA_VALIDATION_ERROR"


def test_callback_data_and_forced_fail_reason_are_closed_and_non_secret():
    with pytest.raises(StartExecutionRejected):
        validate_control_execution_request(
            {
                **CONTROL_IDENTITY,
                "action": "callback",
                "idempotency_key": "control-1",
                "template_node_id": "A",
                "callback_data": {"authorization": "DOWNSTREAM_SENTINEL"},
            }
        )
    for reason_code in ("free-form-reason", {"unsafe": "shape"}):
        with pytest.raises(StartExecutionRejected):
            validate_control_execution_request(
                {
                    **CONTROL_IDENTITY,
                    "action": "forced_fail",
                    "idempotency_key": "control-1",
                    "template_node_id": "A",
                    "reason_code": reason_code,
                }
            )


def test_gateway_flow_list_rejects_non_string_items_as_schema_error():
    with pytest.raises(StartExecutionRejected):
        validate_control_execution_request(
            {
                **CONTROL_IDENTITY,
                "action": "skip_cpg",
                "idempotency_key": "control-1",
                "template_gateway_id": "gateway-A",
                "template_flow_ids": [{"runtime": "flow-A"}],
                "template_converge_gateway_id": "gateway-B",
            }
        )


def adapter(client, **overrides):
    values = {
        "space_id": 905,
        "actor": "dannydeng",
        "task_creator": mock.Mock(),
        "client_factory": lambda **_kwargs: client,
    }
    values.update(overrides)
    return ApplicationTaskAdapter(**values)


@pytest.mark.parametrize(
    ("action", "root_state"),
    [("pause", "RUNNING"), ("resume", "SUSPENDED"), ("revoke", "RUNNING"), ("revoke", "SUSPENDED")],
)
def test_application_adapter_preserves_legal_real_task_wire_state_for_control(action, root_state):
    client = mock.Mock()
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": root_state, "children": {}}}
    request = validate_control_execution_request({**CONTROL_IDENTITY, "action": action, "idempotency_key": "control-1"})

    observation = adapter(client).control_preflight("8101", request)

    assert observation.root_state == root_state
    assert observation.task_ref == "8101"
    assert observation.runtime_node_id is None


@pytest.mark.parametrize(
    ("action", "root_state"),
    [
        ("pause", "CREATED"),
        ("pause", "SUSPENDED"),
        ("pause", "FAILED"),
        ("pause", "NODE_SUSPENDED"),
        ("resume", "NODE_SUSPENDED"),
        ("resume", "RUNNING"),
        ("resume", "FAILED"),
        ("revoke", "EXPIRED"),
    ],
)
def test_application_adapter_denies_illegal_task_wire_states_without_normalizing_node_suspended(action, root_state):
    client = mock.Mock()
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": root_state, "children": {}}}
    request = validate_control_execution_request({**CONTROL_IDENTITY, "action": action, "idempotency_key": "control-1"})

    with pytest.raises(ControlActionUnavailable):
        adapter(client).control_preflight("8101", request)


def test_application_adapter_maps_real_http_404_to_task_not_found_without_body_disclosure():
    client = mock.Mock()
    client.get_task_states.return_value = {
        "result": False,
        "http_status": 404,
        "message": "DOWNSTREAM_SENTINEL",
    }
    request = validate_control_execution_request(
        {**CONTROL_IDENTITY, "action": "pause", "idempotency_key": "control-1"}
    )

    with pytest.raises(TaskNotFound) as error:
        adapter(client).control_preflight("8101", request)

    assert "DOWNSTREAM_SENTINEL" not in repr(error.value)


@pytest.mark.parametrize("root_state", ["FAILED", "NODE_SUSPENDED"])
def test_revoke_accepts_projected_failure_states_and_dispatches_once_as_trusted_actor(root_state):
    client = mock.Mock()
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": root_state}}
    client.operate_task.return_value = {"result": True, "message": "DOWNSTREAM_SENTINEL"}
    application = adapter(client)
    request = validate_control_execution_request(
        {**CONTROL_IDENTITY, "action": "revoke", "idempotency_key": "control-1"}
    )

    observation = application.control_preflight("8101", request)
    receipt = application.control_dispatch("8101", request, observation)

    assert observation.root_state == root_state
    assert receipt == ControlDispatchReceipt(acknowledged=True)
    assert "DOWNSTREAM_SENTINEL" not in repr(receipt)
    client.operate_task.assert_called_once_with("8101", "revoke", {"operator": "dannydeng"})


def node_client(version="v7"):
    client = mock.Mock()
    node = {"id": "runtime-A", "state": "FAILED", "children": {}}
    if version is not None:
        node["version"] = version
    client.get_task_states.return_value = {
        "result": True,
        "data": {"id": "root", "state": "FAILED", "children": {"A": node}},
    }
    client.get_node_id_map.return_value = {"result": True, "data": {"A": "runtime-A"}}
    return client


def retry_request():
    return validate_control_execution_request(
        {
            **CONTROL_IDENTITY,
            "action": "retry",
            "idempotency_key": "control-1",
            "template_node_id": "A",
            "loop": False,
        }
    )


def published_tree(**node_overrides):
    node = {"id": "A", "type": "ServiceActivity", "retryable": True, "skippable": True}
    node.update(node_overrides)
    return {"activities": {"A": node}, "gateways": {}, "flows": {}}


def test_application_adapter_maps_template_node_to_exact_runtime_state_and_version():
    observation = adapter(node_client()).control_preflight("8101", retry_request(), published_tree())

    assert isinstance(observation, ControlObservation)
    assert observation.root_state == "FAILED"
    assert observation.task_ref == "8101"
    assert observation.action == "retry"
    assert observation.template_node_id == "A"
    assert observation.runtime_node_id == "runtime-A"
    assert observation.node_state == "FAILED"
    assert observation.node_version == "v7"
    assert observation.published_node_type == "ServiceActivity"
    assert observation.published_retryable is True
    assert observation.published_skippable is True


def test_application_adapter_requires_node_version_for_safe_control_preflight():
    with pytest.raises(ReadbackUnavailable):
        adapter(node_client(version=None)).control_preflight("8101", retry_request(), published_tree())


@pytest.mark.parametrize(
    ("control_request", "tree"),
    [
        (retry_request(), published_tree(retryable=False)),
        (
            validate_control_execution_request(
                {
                    **CONTROL_IDENTITY,
                    "action": "retry",
                    "idempotency_key": "control-1",
                    "template_node_id": "A",
                    "loop": True,
                }
            ),
            published_tree(),
        ),
        (
            validate_control_execution_request(
                {
                    **CONTROL_IDENTITY,
                    "action": "skip",
                    "idempotency_key": "control-1",
                    "template_node_id": "A",
                    "loop": False,
                }
            ),
            published_tree(skippable=False),
        ),
    ],
)
def test_node_preflight_requires_published_capability_and_denies_unproven_loop_controls(control_request, tree):
    with pytest.raises(ControlActionUnavailable):
        adapter(node_client()).control_preflight("8101", control_request, tree)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "action": "callback",
            "template_node_id": "A",
            "callback_data": {},
        },
        {
            "action": "skip_exg",
            "template_gateway_id": "gateway-A",
            "template_flow_id": "flow-A",
        },
        {
            "action": "skip_cpg",
            "template_gateway_id": "gateway-A",
            "template_flow_ids": ["flow-A"],
            "template_converge_gateway_id": "gateway-B",
        },
    ],
)
def test_callback_and_gateway_actions_are_fixed_deny_before_task_api(payload):
    client = mock.Mock()
    request = validate_control_execution_request({**CONTROL_IDENTITY, "idempotency_key": "control-1", **payload})

    with pytest.raises(ControlActionUnavailable):
        adapter(client).control_preflight("8101", request, published_tree())

    client.get_task_states.assert_not_called()
    client.get_node_id_map.assert_not_called()


def test_control_sdk_runtime_mode_is_denied():
    with pytest.raises(ValueError, match="runtime authorization mode is unavailable"):
        ApplicationTaskAdapter(runtime_authorization_mode="brokered_sdk_token", space_id=905, actor="dannydeng")


def test_task_and_node_dispatch_use_trusted_actor_and_return_safe_receipts():
    task_client = mock.Mock()
    task_client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": "RUNNING"}}
    task_client.operate_task.return_value = {"result": True, "data": {"secret": "DOWNSTREAM_SENTINEL"}}
    task_application = adapter(task_client)
    pause = validate_control_execution_request({**CONTROL_IDENTITY, "action": "pause", "idempotency_key": "control-1"})
    task_observation = task_application.control_preflight("8101", pause)

    task_receipt = task_application.control_dispatch("8101", pause, task_observation)

    runtime_client = node_client()
    runtime_client.node_operate.return_value = {"result": True, "message": "DOWNSTREAM_SENTINEL"}
    node_application = adapter(runtime_client)
    node_request = retry_request()
    node_observation = node_application.control_preflight("8101", node_request, published_tree())
    node_receipt = node_application.control_dispatch(
        "8101", node_request, node_observation, pipeline_tree=published_tree()
    )

    assert task_receipt == ControlDispatchReceipt(acknowledged=True)
    assert node_receipt == ControlDispatchReceipt(acknowledged=True)
    assert "DOWNSTREAM_SENTINEL" not in repr(task_receipt) + repr(node_receipt)
    task_client.operate_task.assert_called_once_with("8101", "pause", {"operator": "dannydeng"})
    runtime_client.node_operate.assert_called_once_with(
        "8101", "runtime-A", "retry", {"operator": "dannydeng", "loop": False}
    )


def test_control_dispatch_rejects_forged_cross_task_and_stale_capability_observations_before_client_call():
    client = node_client()
    application = adapter(client)
    request = retry_request()
    tree = published_tree()
    observation = application.control_preflight("8101", request, tree)
    client.reset_mock()

    with pytest.raises(ControlActionUnavailable):
        application.control_dispatch("8101", request, object(), pipeline_tree=tree)
    with pytest.raises(ControlActionUnavailable):
        application.control_dispatch("8102", request, observation, pipeline_tree=tree)
    with pytest.raises(ControlActionUnavailable):
        application.control_dispatch(
            "8101", request, replace(observation, node_version="Bearer raw"), pipeline_tree=tree
        )
    with pytest.raises(ControlActionUnavailable):
        application.control_dispatch("8101", request, observation, pipeline_tree=published_tree(retryable=False))

    client.node_operate.assert_not_called()


def test_control_dispatch_rereads_runtime_node_version_and_denies_drift_without_mutation():
    client = node_client()
    original = copy.deepcopy(client.get_task_states.return_value)
    drifted = copy.deepcopy(original)
    drifted["data"]["children"]["A"]["version"] = "v8"
    client.get_task_states.side_effect = [original, drifted]
    application = adapter(client)
    request = retry_request()
    tree = published_tree()

    observation = application.control_preflight("8101", request, tree)
    with pytest.raises(ControlActionUnavailable):
        application.control_dispatch("8101", request, observation, pipeline_tree=tree)

    client.node_operate.assert_not_called()


def test_control_dispatch_rereads_task_source_state_and_denies_drift_without_mutation():
    client = mock.Mock()
    client.get_task_states.side_effect = [
        {"result": True, "data": {"id": "root", "state": "RUNNING"}},
        {"result": True, "data": {"id": "root", "state": "SUSPENDED"}},
    ]
    application = adapter(client)
    request = validate_control_execution_request(
        {**CONTROL_IDENTITY, "action": "pause", "idempotency_key": "control-1"}
    )

    observation = application.control_preflight("8101", request)
    with pytest.raises(ControlActionUnavailable):
        application.control_dispatch("8101", request, observation)

    client.operate_task.assert_not_called()


@pytest.mark.parametrize(
    "result",
    [
        {"result": False, "message": "DOWNSTREAM_SENTINEL"},
        {"result": "true", "data": "DOWNSTREAM_SENTINEL"},
        "DOWNSTREAM_SENTINEL",
    ],
)
def test_downstream_control_failure_is_uncertain_without_payload_disclosure(result):
    client = mock.Mock()
    client.operate_task.return_value = result
    application = adapter(client)
    request = validate_control_execution_request(
        {**CONTROL_IDENTITY, "action": "pause", "idempotency_key": "control-1"}
    )

    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": "RUNNING"}}
    observation = application.control_preflight("8101", request)

    with pytest.raises(ControlDispatchUncertain) as error:
        application.control_dispatch("8101", request, observation)

    assert "DOWNSTREAM_SENTINEL" not in repr(error.value)


class ControlReceiptBackend:
    def __init__(self, claims, *, expires_at=None, mutate=None):
        self.claims = copy.deepcopy(claims)
        self.expires_at = expires_at or (timezone.now() + timezone.timedelta(minutes=5))
        self.mutate = mutate
        self.calls = []
        self.transaction_states = []

    def verify(self, receipt_ref):
        self.calls.append(receipt_ref)
        self.transaction_states.append(connection.in_atomic_block)
        result = {
            "allowed": True,
            "provider": "bkaidev",
            "receipt_ref": receipt_ref,
            "claims": copy.deepcopy(self.claims),
            "expires_at": self.expires_at,
            "revoked": False,
            "reason": "approved",
            "verifier_version": "bkaidev-v1",
        }
        if self.mutate:
            self.mutate(result)
        return result


@pytest.fixture
def control_case(db):
    case = start_cases.execution_case.__wrapped__(db)
    first = start_cases.start(case)
    payload = start_cases.approved_payload(case, first)
    verifier, _ = start_cases.approved_verifier(case, first)
    response = start_cases.start(case, payload, approval_verifier=verifier)
    assert response["ok"] is True
    case.run.refresh_from_db()
    case.execution = ExecutionRun.objects.get()
    case.control_request = {
        "execution_id": str(case.execution.id),
        "expected_manifest_hash": case.manifest.manifest_hash,
        "action": "pause",
        "idempotency_key": "control-workflow-1",
    }
    return case


def service_client(*, operation_result=None, root_state="RUNNING"):
    client = mock.Mock()
    client.get_task_states.return_value = {
        "result": True,
        "data": {"id": "root", "state": root_state},
    }
    client.operate_task.return_value = operation_result or {"result": True}
    return client


def service_adapter(case, client):
    return ApplicationTaskAdapter(
        space_id=case.context.space_id,
        actor=case.context.actor,
        client_factory=lambda **kwargs: client,
    )


def control(case, payload=None, **kwargs):
    return control_workflow_execution_with_context(
        case.context,
        payload or case.control_request,
        **kwargs,
    )


def control_claims(case, approval):
    return {
        "actor": case.context.actor,
        "platform_app": case.context.platform_app,
        "space_id": case.context.space_id,
        "scope": case.run.scope,
        "environment": case.context.target_environment,
        "plan_hash": case.manifest.plan_hash,
        "action": approval.action,
        "action_digest": approval.action_digest,
    }


@pytest.mark.django_db
def test_control_flag_off_precedes_authority_engine_approval_and_all_writes(control_case):
    case = control_case
    SpaceConfig.objects.filter(
        space_id=case.context.space_id,
        name=HarnessExecutionEnabledConfig.name,
    ).update(text_value="false")
    client = service_client()
    response = control(case, adapter=service_adapter(case, client))

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    assert ApprovalRequest.objects.filter(action=HarnessAction.PAUSE).count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.get_task_states.assert_not_called()


@pytest.mark.django_db
def test_control_missing_receipt_creates_exact_pending_approval_only(control_case):
    case = control_case
    client = service_client()
    evidence_count = EvidenceEvent.objects.filter(execution=case.execution).count()
    response = control(case, adapter=service_adapter(case, client))

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_REQUIRED"
    approval = ApprovalRequest.objects.get(pk=response["approval_request_id"])
    assert approval.action == HarnessAction.PAUSE
    assert approval.status == ApprovalRequest.Status.PENDING
    assert approval.manifest_id == case.manifest.id
    assert approval.run_id == case.run.id
    assert approval.revision_id == case.manifest.revision_id
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    assert EvidenceEvent.objects.filter(execution=case.execution).count() == evidence_count
    client.operate_task.assert_not_called()


@pytest.mark.django_db
def test_control_cross_context_is_forbidden_before_engine_or_approval(control_case):
    case = control_case
    client = service_client()
    response = control_workflow_execution_with_context(
        replace(case.context, actor="attacker"),
        case.control_request,
        adapter=service_adapter(case, client),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert ApprovalRequest.objects.filter(action=HarnessAction.PAUSE).count() == 0
    client.get_task_states.assert_not_called()


@pytest.mark.django_db
def test_control_forged_approval_is_invalid_without_dispatch(control_case):
    case = control_case
    client = service_client()
    first = control(case, adapter=service_adapter(case, client))
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    claims = control_claims(case, approval)
    claims["actor"] = "attacker"
    verifier = ApprovalVerifier(
        backend=ControlReceiptBackend(claims),
        replay_guard=InMemoryApprovalReplayGuard(),
    )
    response = control(
        case,
        {
            **case.control_request,
            "approval_request_id": str(approval.id),
            "approval_receipt_ref": "approval://bkaidev/control-forged",
        },
        adapter=service_adapter(case, client),
        approval_verifier=verifier,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_INVALID"
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.PENDING
    client.operate_task.assert_not_called()


def approved_control(case, client, *, receipt_ref="approval://bkaidev/control-approved", **kwargs):
    adapter_instance = service_adapter(case, client)
    first = control(case, adapter=adapter_instance)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    backend = ControlReceiptBackend(control_claims(case, approval), **kwargs.pop("backend_kwargs", {}))
    verifier = ApprovalVerifier(backend=backend, replay_guard=kwargs.pop("replay_guard", InMemoryApprovalReplayGuard()))
    payload = {
        **case.control_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": receipt_ref,
    }
    response = control(
        case,
        payload,
        adapter=adapter_instance,
        approval_verifier=verifier,
        **kwargs,
    )
    return response, payload, approval, backend, verifier


class FixedControlReadAdapter:
    def __init__(self, observation=None, error=None):
        self.observation = observation
        self.error = error
        self.calls = []

    def observe_control(self, task_ref, pipeline_tree, *, template_node_id=None):
        self.calls.append((task_ref, template_node_id))
        if self.error is not None:
            raise self.error
        return self.observation


def read_control(case, adapter_instance):
    return get_workflow_execution_with_context(
        case.context,
        {"execution_id": str(case.execution.id), "limit": 20},
        adapter=adapter_instance,
    )


def seed_node_control_attempt(case, action, *, record_status="IN_FLIGHT", payload_overrides=None):
    idempotency_key = "node-control-{}".format(action)
    record = HarnessIdempotencyRecord.objects.create(
        platform_app=case.context.platform_app,
        actor=case.context.actor,
        space_id=case.context.space_id,
        tool_name="control_workflow_execution",
        run_scope="run:{}".format(case.run.run_id),
        run=case.run,
        idempotency_key=idempotency_key,
        request_hash="e" * 64,
        status=record_status,
        response_snapshot=(
            {
                "ok": False,
                "errors": [{"code": "RETRYABLE_INFRA"}],
                "next_actions": ["manual_reconcile_execution"],
            }
            if record_status == "COMPLETED"
            else {}
        ),
        resource_reference=str(case.execution.id),
    )
    idempotency_ref = "idempotency://execution/{}".format(record.id)
    case.execution.control_idempotency_refs = [idempotency_ref]
    case.execution.status = ExecutionRun.Status.CONTROL_DISPATCHING
    case.execution.save(update_fields=["control_idempotency_refs", "status", "update_at"])
    expected = {
        "retry": "NODE_VERSION_ADVANCED",
        "skip": "NODE_VERSION_ADVANCED",
        "forced_fail": "NODE_FAILED",
    }[action]
    payload = {
        "version": "control-attempt-v1",
        "action": action,
        "attempt": 1,
        "idempotency_ref": idempotency_ref,
        "action_digest": "d" * 64,
        "pre_execution_status": ExecutionRun.Status.EXECUTING,
        "pre_state": {
            "root_state": "FAILED" if action in {"retry", "skip"} else "RUNNING",
            "template_node_id": "A",
            "node_state": "FAILED" if action in {"retry", "skip"} else "RUNNING",
            "node_version": "v7",
            "runtime_mapping_fingerprint": hashlib.sha256(b"A\0runtime-A").hexdigest(),
        },
        "template_target": {"template_node_id": "A"},
        "expected_readback": expected,
        "input_fields": [],
        "input_digest": hashlib.sha256(b"{}").hexdigest(),
    }
    if payload_overrides:
        payload.update(payload_overrides)
    record_evidence(
        run=case.run,
        revision=case.execution.revision,
        execution=case.execution,
        event_type="EXECUTION_CONTROL_DISPATCHING",
        action=action,
        payload=payload,
        actor=case.context.actor,
        correlation_id=case.context.correlation_id,
    )
    return record


def seed_task_control_attempt(case, action, pre_execution_status, root_state):
    if pre_execution_status == ExecutionRun.Status.PAUSED:
        case.execution.status = ExecutionRun.Status.PAUSED
        case.execution.save(update_fields=["status", "update_at"])
    record = HarnessIdempotencyRecord.objects.create(
        platform_app=case.context.platform_app,
        actor=case.context.actor,
        space_id=case.context.space_id,
        tool_name="control_workflow_execution",
        run_scope="run:{}".format(case.run.run_id),
        run=case.run,
        idempotency_key="task-control-{}".format(action),
        request_hash="e" * 64,
        status="IN_FLIGHT",
        response_snapshot={},
        resource_reference=str(case.execution.id),
    )
    idempotency_ref = "idempotency://execution/{}".format(record.id)
    case.execution.control_idempotency_refs = [idempotency_ref]
    case.execution.status = ExecutionRun.Status.CONTROL_DISPATCHING
    case.execution.save(update_fields=["control_idempotency_refs", "status", "update_at"])
    record_evidence(
        run=case.run,
        revision=case.execution.revision,
        execution=case.execution,
        event_type="EXECUTION_CONTROL_DISPATCHING",
        action=action,
        payload={
            "version": "control-attempt-v1",
            "action": action,
            "attempt": 1,
            "idempotency_ref": idempotency_ref,
            "action_digest": "d" * 64,
            "pre_execution_status": pre_execution_status,
            "pre_state": {
                "root_state": root_state,
                "template_node_id": None,
                "node_state": None,
                "node_version": None,
                "runtime_mapping_fingerprint": None,
            },
            "template_target": {},
            "expected_readback": {"pause": "SUSPENDED", "resume": "RUNNING", "revoke": "REVOKED"}[action],
            "input_fields": [],
            "input_digest": hashlib.sha256(b"{}").hexdigest(),
        },
        actor=case.context.actor,
        correlation_id=case.context.correlation_id,
    )
    return record


@pytest.mark.django_db
def test_expected_manifest_hash_mismatch_is_stale_before_preflight_or_approval(control_case):
    case = control_case
    client = service_client()
    response = control(
        case,
        {**case.control_request, "expected_manifest_hash": "f" * 64},
        adapter=service_adapter(case, client),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ApprovalRequest.objects.filter(action=HarnessAction.PAUSE).count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.get_task_states.assert_not_called()


@pytest.mark.django_db
def test_expected_manifest_hash_mismatch_does_not_revoke_existing_control_approval(control_case):
    case = control_case
    client = service_client()
    first = control(case, adapter=service_adapter(case, client))
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])

    response = control(
        case,
        {
            **case.control_request,
            "expected_manifest_hash": "f" * 64,
            "approval_request_id": str(approval.id),
            "approval_receipt_ref": "approval://bkaidev/stale-caller",
        },
        adapter=service_adapter(case, client),
    )

    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.PENDING
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.operate_task.assert_not_called()


@pytest.mark.django_db
def test_control_approval_action_digest_mismatch_is_invalid_before_verifier_or_dispatch(control_case):
    case = control_case
    client = service_client()
    first = control(case, adapter=service_adapter(case, client))
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    backend = ControlReceiptBackend(control_claims(case, approval))

    response = control(
        case,
        {
            **case.control_request,
            "action": "revoke",
            "approval_request_id": str(approval.id),
            "approval_receipt_ref": "approval://bkaidev/wrong-digest",
        },
        adapter=service_adapter(case, client),
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()),
    )

    assert response["errors"][0]["code"] == "APPROVAL_INVALID"
    assert backend.calls == []
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.PENDING
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.operate_task.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("outcome", ["ack", "business_false", "exception"])
def test_approved_control_dispatches_once_then_persists_safe_uncertain_barrier(control_case, outcome):
    case = control_case
    client = service_client()
    if outcome == "business_false":
        client.operate_task.return_value = {"result": False, "message": "DOWNSTREAM_SENTINEL"}
    elif outcome == "exception":
        client.operate_task.side_effect = RuntimeError("DOWNSTREAM_SENTINEL")

    response, payload, approval, backend, _ = approved_control(case, client)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["next_actions"] == ["manual_reconcile_execution"]
    approval.refresh_from_db()
    case.execution.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.VERIFIED
    assert case.execution.status == ExecutionRun.Status.CONTROL_UNCERTAIN
    record = HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution")
    assert record.status == "COMPLETED"
    assert record.run_id == case.run.id
    assert record.resource_reference == str(case.execution.id)
    assert record.response_snapshot == response
    assert len(case.execution.control_idempotency_refs) == 1
    journal = EvidenceEvent.objects.get(
        execution=case.execution,
        event_type="EXECUTION_CONTROL_DISPATCHING",
    )
    assert journal.action == HarnessAction.PAUSE
    assert journal.redacted_payload["action_digest"] == approval.action_digest
    assert journal.redacted_payload["input_fields"] == []
    serialized = repr(response) + repr(journal.redacted_payload) + repr(record.response_snapshot)
    assert payload["approval_receipt_ref"] not in serialized
    assert "DOWNSTREAM_SENTINEL" not in serialized
    client.operate_task.assert_called_once_with(case.execution.task_ref, "pause", {"operator": case.context.actor})
    assert backend.transaction_states == [False]


@pytest.mark.django_db(transaction=True)
def test_completed_control_same_key_replays_without_verifier_or_engine_and_new_key_does_not_redispatch(control_case):
    case = control_case
    client = service_client()
    response, payload, _, backend, verifier = approved_control(case, client)
    client.reset_mock()

    replay = control(
        case,
        payload,
        adapter=service_adapter(case, client),
        approval_verifier=verifier,
    )
    blocked = control(
        case,
        {**case.control_request, "idempotency_key": "control-workflow-2"},
        adapter=service_adapter(case, client),
    )

    assert replay == response
    assert blocked["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert blocked["next_actions"] == ["manual_reconcile_execution"]
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 1
    assert backend.calls == [payload["approval_receipt_ref"]]
    client.get_task_states.assert_not_called()
    client.operate_task.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_crash_after_barrier_keeps_one_attempt_and_all_retries_manual_without_dispatch(control_case):
    case = control_case
    client = service_client()

    response, payload, _, _, verifier = approved_control(
        case,
        client,
        test_after_barrier_hook=lambda: (_ for _ in ()).throw(RuntimeError("crash after barrier")),
    )
    case.execution.refresh_from_db()
    record = HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution")

    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert record.status == "IN_FLIGHT"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert (
        EvidenceEvent.objects.filter(
            execution=case.execution,
            event_type="EXECUTION_CONTROL_DISPATCHING",
        ).count()
        == 1
    )
    client.operate_task.assert_not_called()

    retry = control(
        case,
        payload,
        adapter=service_adapter(case, client),
        approval_verifier=verifier,
    )
    new_key = control(
        case,
        {**case.control_request, "idempotency_key": "control-workflow-2"},
        adapter=service_adapter(case, client),
    )
    assert retry["next_actions"] == ["manual_reconcile_execution"]
    assert new_key["next_actions"] == ["manual_reconcile_execution"]
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 1
    client.operate_task.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_crash_after_dispatch_keeps_durable_attempt_and_never_dispatches_again(control_case):
    case = control_case
    client = service_client()
    response, payload, _, _, verifier = approved_control(
        case,
        client,
        test_after_dispatch_hook=lambda: (_ for _ in ()).throw(RuntimeError("crash after dispatch")),
    )
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution").status == "IN_FLIGHT"
    client.operate_task.assert_called_once()

    control(case, payload, adapter=service_adapter(case, client), approval_verifier=verifier)
    assert client.operate_task.call_count == 1


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["expired", "replayed"])
def test_control_expired_or_replayed_receipt_is_invalid_without_barrier(control_case, mode):
    case = control_case
    client = service_client()
    first = control(case, adapter=service_adapter(case, client))
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    receipt_ref = "approval://bkaidev/control-{}".format(mode)
    replay_guard = InMemoryApprovalReplayGuard()
    if mode == "replayed":
        replay_guard.claim_once(hashlib.sha256(receipt_ref.encode()).hexdigest(), "unused", timezone.now())
    backend = ControlReceiptBackend(
        control_claims(case, approval),
        expires_at=(timezone.now() - timezone.timedelta(seconds=1) if mode == "expired" else None),
    )
    response = control(
        case,
        {
            **case.control_request,
            "approval_request_id": str(approval.id),
            "approval_receipt_ref": receipt_ref,
        },
        adapter=service_adapter(case, client),
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=replay_guard),
    )

    assert response["errors"][0]["code"] == "APPROVAL_INVALID"
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.operate_task.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_stable_execution_with_control_history_accepts_a_new_logical_control(control_case):
    case = control_case
    first_client = service_client()
    approved_control(case, first_client)
    case.execution.refresh_from_db()
    previous_refs = list(case.execution.control_idempotency_refs)
    case.execution.status = ExecutionRun.Status.EXECUTING
    case.execution.save(update_fields=["status", "update_at"])

    second_client = service_client()
    response = control(
        case,
        {**case.control_request, "idempotency_key": "control-workflow-2"},
        adapter=service_adapter(case, second_client),
    )

    assert response["errors"][0]["code"] == "APPROVAL_REQUIRED"
    assert case.execution.control_idempotency_refs == previous_refs
    assert ApprovalRequest.objects.get(pk=response["approval_request_id"]).status == ApprovalRequest.Status.PENDING
    second_client.operate_task.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_cross_tool_inflight_barrier_blocks_control_before_dispatch(control_case):
    case = control_case
    client = service_client()
    first = control(case, adapter=service_adapter(case, client))
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    payload = {
        **case.control_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": "approval://bkaidev/control-cross-tool",
    }
    backend = ControlReceiptBackend(control_claims(case, approval))
    verifier = ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard())
    HarnessIdempotencyRecord.objects.create(
        platform_app=case.context.platform_app,
        actor=case.context.actor,
        space_id=case.context.space_id,
        tool_name=HarnessAction.START_WORKFLOW_EXECUTION,
        run_scope="run:{}".format(case.run.run_id),
        run=case.run,
        idempotency_key="cross-tool-pending",
        request_hash="e" * 64,
        status="IN_FLIGHT",
        resource_reference=str(case.execution.id),
    )

    response = control(
        case,
        payload,
        adapter=service_adapter(case, client),
        approval_verifier=verifier,
    )

    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["next_actions"] == ["manual_reconcile_execution"]
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    assert (
        EvidenceEvent.objects.filter(
            execution=case.execution,
            event_type="EXECUTION_CONTROL_DISPATCHING",
        ).count()
        == 0
    )
    client.operate_task.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_completed_key_with_different_control_intent_is_conflict_without_new_approval_or_dispatch(control_case):
    case = control_case
    client = service_client()
    approved_control(case, client)
    approval_count = ApprovalRequest.objects.count()
    client.reset_mock()

    response = control(
        case,
        {**case.control_request, "action": "revoke"},
        adapter=service_adapter(case, client),
    )

    assert response["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"
    assert ApprovalRequest.objects.count() == approval_count
    client.get_task_states.assert_not_called()
    client.operate_task.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action_payload",
    [
        {
            "action": "callback",
            "template_node_id": "A",
            "callback_data": {},
        },
        {
            "action": "skip_exg",
            "template_gateway_id": "gateway-A",
            "template_flow_id": "flow-A",
        },
    ],
)
def test_fixed_deny_control_actions_fail_before_approval_or_task_read(control_case, action_payload):
    case = control_case
    client = service_client()
    response = control(
        case,
        {**case.control_request, **action_payload},
        adapter=service_adapter(case, client),
    )

    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ApprovalRequest.objects.filter(action=action_payload["action"]).count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.get_task_states.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_paused_execution_with_suspended_wire_state_can_revoke_through_service(control_case):
    case = control_case
    case.execution.status = ExecutionRun.Status.PAUSED
    case.execution.save(update_fields=["status", "update_at"])
    case.control_request["action"] = "revoke"
    client = service_client(root_state="SUSPENDED")

    response, _, _, _, _ = approved_control(case, client)

    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    case.execution.refresh_from_db()
    assert case.execution.status == ExecutionRun.Status.CONTROL_UNCERTAIN
    client.operate_task.assert_called_once_with(case.execution.task_ref, "revoke", {"operator": case.context.actor})


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("target_count", "expected_code", "expected_count", "expected_dispatches"),
    [
        (98, "RETRYABLE_INFRA", 99, 1),
        (99, "RETRYABLE_INFRA", 99, 0),
    ],
)
def test_control_journal_reserves_one_evidence_slot_for_terminal_event(
    control_case,
    target_count,
    expected_code,
    expected_count,
    expected_dispatches,
):
    case = control_case
    existing = EvidenceEvent.objects.filter(execution=case.execution).count()
    for index in range(existing, target_count):
        record_evidence(
            run=case.run,
            revision=case.execution.revision,
            execution=case.execution,
            event_type="CONTROL_BUDGET_FILL",
            action="poll",
            payload={"index": index},
            actor=case.context.actor,
            correlation_id=case.context.correlation_id,
        )
    client = service_client()

    response, _, _, _, _ = approved_control(case, client)

    assert response["errors"][0]["code"] == expected_code
    assert EvidenceEvent.objects.filter(execution=case.execution).count() == expected_count
    assert client.operate_task.call_count == expected_dispatches
    if target_count == 99:
        case.execution.refresh_from_db()
        assert case.execution.status == ExecutionRun.Status.EXECUTING
        assert case.execution.control_idempotency_refs == []
        assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
        assert (
            EvidenceEvent.objects.filter(
                execution=case.execution,
                event_type="EXECUTION_CONTROL_DISPATCHING",
            ).count()
            == 0
        )


@pytest.mark.django_db(transaction=True)
def test_control_engine_and_verifier_calls_are_outside_database_transactions(control_case):
    case = control_case
    client = service_client()
    transaction_states = []
    original_get = client.get_task_states.return_value
    original_operate = client.operate_task.return_value
    client.get_task_states.side_effect = lambda *args, **kwargs: (
        transaction_states.append(("read", connection.in_atomic_block)) or copy.deepcopy(original_get)
    )
    client.operate_task.side_effect = lambda *args, **kwargs: (
        transaction_states.append(("dispatch", connection.in_atomic_block)) or copy.deepcopy(original_operate)
    )

    response, _, _, backend, _ = approved_control(case, client)

    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert backend.transaction_states == [False]
    assert transaction_states
    assert all(in_atomic is False for _, in_atomic in transaction_states)


@pytest.mark.django_db(transaction=True)
def test_control_snapshot_drift_revokes_pending_approval_without_barrier_or_dispatch(control_case):
    case = control_case
    client = service_client()
    first = control(case, adapter=service_adapter(case, client))
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    payload = {
        **case.control_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": "approval://bkaidev/control-drift",
    }
    backend = ControlReceiptBackend(control_claims(case, approval))
    case.snapshot.__class__.objects.filter(pk=case.execution.published_snapshot_id).update(data={"activities": {}})

    response = control(
        case,
        payload,
        adapter=service_adapter(case, client),
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()),
    )

    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.REVOKED
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.operate_task.assert_not_called()


@pytest.mark.django_db
def test_control_task_404_is_validation_stale_without_approval_or_barrier(control_case):
    case = control_case
    client = service_client()
    client.get_task_states.return_value = {"result": False, "http_status": 404, "message": "SECRET_SENTINEL"}

    response = control(case, adapter=service_adapter(case, client))

    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert "SECRET_SENTINEL" not in repr(response)
    assert ApprovalRequest.objects.filter(action=HarnessAction.PAUSE).count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0


@pytest.mark.django_db
def test_retry_inputs_are_denied_before_engine_approval_evidence_or_barrier(control_case):
    case = control_case
    client = service_client()
    evidence_count = EvidenceEvent.objects.filter(execution=case.execution).count()

    response = control(
        case,
        {
            **case.control_request,
            "action": "retry",
            "template_node_id": "A",
            "loop": False,
            "inputs": {"region": "gz"},
        },
        adapter=service_adapter(case, client),
    )

    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ApprovalRequest.objects.filter(action=HarnessAction.RETRY).count() == 0
    assert EvidenceEvent.objects.filter(execution=case.execution).count() == evidence_count
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.get_task_states.assert_not_called()
    client.get_node_id_map.assert_not_called()
    client.node_operate.assert_not_called()


@pytest.mark.django_db
def test_readback_outage_before_barrier_is_retryable_without_revoking_pending_approval(control_case):
    case = control_case
    client = service_client()
    first = control(case, adapter=service_adapter(case, client))
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    client.reset_mock()
    client.get_task_states.return_value = {"result": False, "message": "DOWNSTREAM_SENTINEL"}
    backend = ControlReceiptBackend(control_claims(case, approval))

    response = control(
        case,
        {
            **case.control_request,
            "approval_request_id": str(approval.id),
            "approval_receipt_ref": "approval://bkaidev/readback-outage",
        },
        adapter=service_adapter(case, client),
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()),
    )

    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert "manual_reconcile_execution" not in response["next_actions"]
    assert "DOWNSTREAM_SENTINEL" not in repr(response)
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.PENDING
    assert backend.calls == []
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.operate_task.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_readback_outage_after_barrier_keeps_verified_authority_and_manual_barrier(control_case):
    case = control_case
    observation = ControlObservation(task_ref=case.execution.task_ref, root_state="RUNNING", action="pause")
    adapter_instance = mock.Mock(spec=ApplicationTaskAdapter)
    adapter_instance.control_preflight.return_value = observation
    adapter_instance.control_dispatch.side_effect = ReadbackUnavailable()
    first = control(case, adapter=adapter_instance)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    backend = ControlReceiptBackend(control_claims(case, approval))

    response = control(
        case,
        {
            **case.control_request,
            "approval_request_id": str(approval.id),
            "approval_receipt_ref": "approval://bkaidev/readback-after-barrier",
        },
        adapter=adapter_instance,
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()),
    )

    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["next_actions"] == ["manual_reconcile_execution"]
    approval.refresh_from_db()
    case.execution.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.VERIFIED
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution").status == "IN_FLIGHT"
    assert (
        EvidenceEvent.objects.filter(
            execution=case.execution,
            event_type="EXECUTION_CONTROL_DISPATCHING",
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_invalidation_failure_is_normalized_without_leaking_or_claiming_revocation(control_case):
    case = control_case
    client = service_client()
    first = control(case, adapter=service_adapter(case, client))
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    payload = {
        **case.control_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": "approval://bkaidev/invalidation-failure",
    }
    case.snapshot.__class__.objects.filter(pk=case.execution.published_snapshot_id).update(data={"activities": {}})

    with mock.patch(
        "bkflow.harness.services.execution.control._invalidate_control_approval",
        side_effect=RuntimeError("INVALIDATION_SENTINEL"),
    ):
        response = control(case, payload, adapter=service_adapter(case, client))

    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert "INVALIDATION_SENTINEL" not in repr(response)
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.PENDING
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.operate_task.assert_not_called()


@pytest.mark.parametrize("acknowledged", [False, 0, 1, "true", None])
def test_control_receipt_requires_exact_true_boolean_acknowledgement(acknowledged):
    assert _receipt_is_acknowledged(ControlDispatchReceipt(acknowledged=acknowledged)) is False


def test_control_receipt_accepts_exact_true_boolean_acknowledgement():
    assert _receipt_is_acknowledged(ControlDispatchReceipt(acknowledged=True)) is True


def test_control_readback_preserves_raw_node_suspended_and_hides_runtime_node_id():
    client = node_client(version="v8")
    client.get_task_states.return_value["data"]["state"] = "NODE_SUSPENDED"
    client.get_task_states.return_value["data"]["children"]["A"]["state"] = "SUSPENDED"
    read_adapter = ExecutionReadAdapter(space_id=905, client_factory=lambda **_kwargs: client)

    observation = read_adapter.observe_control("8101", published_tree(), template_node_id="A")

    assert observation == ControlReadbackObservation(
        root_state="NODE_SUSPENDED",
        template_node_id="A",
        node_state="SUSPENDED",
        node_version="v8",
        runtime_mapping_fingerprint=hashlib.sha256(b"A\0runtime-A").hexdigest(),
    )
    assert "runtime-A" not in repr(observation)


@pytest.mark.django_db(transaction=True)
def test_get_does_not_cross_control_dispatch_barrier_before_dispatch(control_case):
    case = control_case
    client = service_client(root_state="RUNNING")
    response, _, _, _, _ = approved_control(
        case,
        client,
        test_after_barrier_hook=lambda: (_ for _ in ()).throw(RuntimeError("crash before dispatch")),
    )
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    record = HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution")
    assert record.status == "IN_FLIGHT"

    refreshed = get_workflow_execution_with_context(
        case.context,
        {"execution_id": str(case.execution.id), "limit": 20},
        adapter=ExecutionReadAdapter(space_id=case.context.space_id, client_factory=lambda **_kwargs: client),
    )

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert refreshed["ok"] is True
    assert refreshed["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert refreshed["next_actions"] == ["manual_reconcile_execution"]
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"


@pytest.mark.django_db(transaction=True)
def test_get_matching_pause_readback_completes_inflight_control_without_redispatch(control_case):
    case = control_case
    client = service_client(root_state="RUNNING")
    response, _, _, _, _ = approved_control(
        case,
        client,
        test_after_dispatch_hook=lambda: (_ for _ in ()).throw(RuntimeError("crash after dispatch")),
    )
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": "SUSPENDED"}}

    refreshed = get_workflow_execution_with_context(
        case.context,
        {"execution_id": str(case.execution.id), "limit": 20},
        adapter=ExecutionReadAdapter(space_id=case.context.space_id, client_factory=lambda **_kwargs: client),
    )

    case.execution.refresh_from_db()
    record = HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution")
    assert refreshed["ok"] is True
    assert refreshed["artifact_refs"][0]["refresh"]["reason"] == "control_reconciled"
    assert case.execution.status == ExecutionRun.Status.PAUSED
    assert record.status == "COMPLETED"
    assert record.response_snapshot["ok"] is True
    assert record.response_snapshot["artifact_refs"] == [
        {
            "type": "workflow_execution_control",
            "execution_id": str(case.execution.id),
            "execution_status": ExecutionRun.Status.PAUSED,
            "action": "pause",
            "reconciled": True,
        }
    ]
    client.operate_task.assert_called_once()


def test_node_control_journal_binds_only_the_runtime_mapping_fingerprint():
    request = retry_request()
    observation = ControlObservation(
        task_ref="8101",
        root_state="FAILED",
        action="retry",
        template_node_id="A",
        runtime_node_id="runtime-A",
        node_state="FAILED",
        node_version="v7",
        published_node_type="ServiceActivity",
        published_retryable=True,
        published_skippable=True,
    )
    journal = _journal_payload(
        request,
        SimpleNamespace(action_digest="d" * 64),
        observation,
        "idempotency://execution/7",
        1,
        ExecutionRun.Status.EXECUTING,
    )

    assert journal["action"] == "retry"
    assert journal["pre_state"]["runtime_mapping_fingerprint"] == hashlib.sha256(b"A\0runtime-A").hexdigest()
    assert "runtime-A" not in repr(journal)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("dispatch_outcome", ["ack", "false", "exception"])
def test_pause_eventually_converges_after_each_ambiguous_dispatch_outcome(control_case, dispatch_outcome):
    case = control_case
    client = service_client(root_state="RUNNING")
    if dispatch_outcome == "false":
        client.operate_task.return_value = {"result": False, "message": "DOWNSTREAM_SENTINEL"}
    elif dispatch_outcome == "exception":
        client.operate_task.side_effect = RuntimeError("DOWNSTREAM_SENTINEL")
    response, _, _, _, _ = approved_control(case, client)
    record = HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution")
    manual_snapshot = copy.deepcopy(record.response_snapshot)
    assert response == manual_snapshot
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": "SUSPENDED"}}

    refreshed = read_control(
        case,
        ExecutionReadAdapter(space_id=case.context.space_id, client_factory=lambda **_kwargs: client),
    )

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert refreshed["artifact_refs"][0]["refresh"]["reason"] == "control_reconciled"
    assert case.execution.status == ExecutionRun.Status.PAUSED
    assert record.status == "COMPLETED"
    assert record.response_snapshot == manual_snapshot
    assert "DOWNSTREAM_SENTINEL" not in repr(refreshed) + repr(record.response_snapshot)
    assert client.operate_task.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_resume_readback_requires_raw_running_and_converges_to_executing(control_case):
    case = control_case
    case.execution.status = ExecutionRun.Status.PAUSED
    case.execution.save(update_fields=["status", "update_at"])
    case.control_request["action"] = "resume"
    client = service_client(root_state="SUSPENDED")
    approved_control(case, client)
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": "RUNNING"}}

    response = read_control(
        case,
        ExecutionReadAdapter(space_id=case.context.space_id, client_factory=lambda **_kwargs: client),
    )

    case.execution.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciled"
    assert case.execution.status == ExecutionRun.Status.EXECUTING
    assert case.execution.last_engine_state == "RUNNING"


@pytest.mark.django_db(transaction=True)
def test_revoke_readback_terminalizes_and_revokes_lease_before_bundle(control_case):
    case = control_case
    case.control_request["action"] = "revoke"
    client = service_client(root_state="RUNNING")
    approved_control(case, client)
    now = timezone.now()
    lease = TokenLease.objects.create(
        execution=case.execution,
        platform_app=case.execution.platform_app,
        actor=case.execution.actor,
        space_id=case.execution.space_id,
        resource_type=TokenLease.Resource.TASK,
        resource_id=case.execution.task_ref,
        permission=TokenLease.Permission.OPERATE,
        action=HarnessAction.REVOKE,
        action_digest="c" * 64,
        issuer_ref="issuer://bkflow/execution/revoke-readback",
        token_fingerprint="b" * 64,
        issued_at=now,
        expires_at=now + timezone.timedelta(minutes=5),
        status=TokenLease.Status.ACTIVE,
    )
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": "REVOKED"}}

    response = read_control(
        case,
        ExecutionReadAdapter(space_id=case.context.space_id, client_factory=lambda **_kwargs: client),
    )

    case.execution.refresh_from_db()
    lease.refresh_from_db()
    assert response["ok"] is True
    assert case.execution.status == ExecutionRun.Status.CANCELLED
    assert lease.status == TokenLease.Status.REVOKED
    assert EvidenceBundle.objects.filter(execution=case.execution, outcome="CANCELLED").exists()
    assert EvidenceEvent.objects.filter(execution=case.execution, event_type="EXECUTION_CANCELLED").count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "action,node_state",
    [
        ("retry", "READY"),
        ("retry", "RUNNING"),
        ("retry", "SUSPENDED"),
        ("retry", "FINISHED"),
        ("retry", "FAILED"),
        ("retry", "REVOKED"),
        ("skip", "FINISHED"),
        ("forced_fail", "FAILED"),
    ],
)
def test_node_control_requires_same_mapping_changed_version_and_action_specific_state(control_case, action, node_state):
    case = control_case
    record = seed_node_control_attempt(case, action)
    adapter_instance = FixedControlReadAdapter(
        ControlReadbackObservation(
            root_state="RUNNING",
            template_node_id="A",
            node_state=node_state,
            node_version="v8",
            runtime_mapping_fingerprint=hashlib.sha256(b"A\0runtime-A").hexdigest(),
        )
    )

    response = read_control(case, adapter_instance)

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciled"
    assert case.execution.status == ExecutionRun.Status.EXECUTING
    assert record.status == "COMPLETED"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "action,observation",
    [
        (
            "retry",
            ControlReadbackObservation(
                root_state="RUNNING",
                template_node_id="A",
                node_state="RUNNING",
                node_version="v8",
                runtime_mapping_fingerprint="f" * 64,
            ),
        ),
        (
            "retry",
            ControlReadbackObservation(
                root_state="RUNNING",
                template_node_id="A",
                node_state="RUNNING",
                node_version="v7",
                runtime_mapping_fingerprint=hashlib.sha256(b"A\0runtime-A").hexdigest(),
            ),
        ),
        (
            "retry",
            ControlReadbackObservation(
                root_state="NODE_SUSPENDED",
                template_node_id="A",
                node_state="NODE_SUSPENDED",
                node_version="v8",
                runtime_mapping_fingerprint=hashlib.sha256(b"A\0runtime-A").hexdigest(),
            ),
        ),
        (
            "skip",
            ControlReadbackObservation(
                root_state="RUNNING",
                template_node_id="A",
                node_state="RUNNING",
                node_version="v8",
                runtime_mapping_fingerprint=hashlib.sha256(b"A\0runtime-A").hexdigest(),
            ),
        ),
        (
            "forced_fail",
            ControlReadbackObservation(
                root_state="RUNNING",
                template_node_id="A",
                node_state="FINISHED",
                node_version="v8",
                runtime_mapping_fingerprint=hashlib.sha256(b"A\0runtime-A").hexdigest(),
            ),
        ),
    ],
)
def test_node_mapping_version_or_state_drift_remains_manual_without_completing(control_case, action, observation):
    case = control_case
    record = seed_node_control_attempt(case, action)

    response = read_control(case, FixedControlReadAdapter(observation))

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"


@pytest.mark.django_db(transaction=True)
def test_task_control_readback_with_node_facts_cannot_prove_root_transition(control_case):
    case = control_case
    record = seed_task_control_attempt(case, "pause", ExecutionRun.Status.EXECUTING, "RUNNING")
    forged = ControlReadbackObservation(
        root_state="SUSPENDED",
        node_state="FINISHED",
        node_version="v8",
        runtime_mapping_fingerprint="f" * 64,
    )

    response = read_control(case, FixedControlReadAdapter(forged))

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("action,source_state", [("pause", "RUNNING"), ("resume", "SUSPENDED")])
@pytest.mark.parametrize("wire_state", ["FAILED", "NODE_SUSPENDED"])
def test_failed_or_node_suspended_root_never_proves_pause_or_resume(
    control_case,
    action,
    source_state,
    wire_state,
):
    case = control_case
    if action == "resume":
        case.execution.status = ExecutionRun.Status.PAUSED
        case.execution.save(update_fields=["status", "update_at"])
        case.control_request["action"] = "resume"
    client = service_client(root_state=source_state)
    approved_control(
        case,
        client,
        test_after_dispatch_hook=lambda: (_ for _ in ()).throw(RuntimeError("crash after dispatch")),
    )
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": wire_state}}

    response = read_control(
        case,
        ExecutionReadAdapter(space_id=case.context.space_id, client_factory=lambda **_kwargs: client),
    )

    case.execution.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "tamper",
    [
        {"attempt": 2},
        {"action": "pause"},
        {"action": {"unsafe": "shape"}},
        {"expected_readback": "FINISHED"},
        {"input_fields": [{"unsafe": "shape"}]},
        {"credential": "SECRET_SENTINEL"},
    ],
)
def test_malformed_or_mismatched_control_journal_is_manual_before_readback(control_case, tamper):
    case = control_case
    record = seed_node_control_attempt(case, "retry", payload_overrides=tamper)
    adapter_instance = FixedControlReadAdapter(error=AssertionError("readback must not run"))
    before_events = EvidenceEvent.objects.filter(execution=case.execution).count()

    response = read_control(case, adapter_instance)

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"
    assert EvidenceEvent.objects.filter(execution=case.execution).count() == before_events
    assert adapter_instance.calls == []
    assert "SECRET_SENTINEL" not in repr(response) + repr(record.response_snapshot)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "field,value",
    [("tool_name", "start_workflow_execution"), ("actor", "foreign-user"), ("resource_reference", "foreign")],
)
def test_misbound_control_idempotency_record_is_manual_before_readback(control_case, field, value):
    case = control_case
    record = seed_node_control_attempt(case, "retry")
    HarnessIdempotencyRecord.objects.filter(pk=record.pk).update(**{field: value})
    adapter_instance = FixedControlReadAdapter(error=AssertionError("readback must not run"))

    response = read_control(case, adapter_instance)

    case.execution.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert adapter_instance.calls == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["missing_journal", "wrong_ref_scheme"])
def test_missing_journal_or_wrong_last_ref_is_manual_before_readback(control_case, mode):
    case = control_case
    record = HarnessIdempotencyRecord.objects.create(
        platform_app=case.context.platform_app,
        actor=case.context.actor,
        space_id=case.context.space_id,
        tool_name="control_workflow_execution",
        run_scope="run:{}".format(case.run.run_id),
        run=case.run,
        idempotency_key="broken-control-ref",
        request_hash="e" * 64,
        status="IN_FLIGHT",
        response_snapshot={},
        resource_reference=str(case.execution.id),
    )
    case.execution.control_idempotency_refs = [
        "idempotency://execution/{}".format(record.id)
        if mode == "missing_journal"
        else "artifact://control/not-an-idempotency-record"
    ]
    case.execution.status = ExecutionRun.Status.CONTROL_DISPATCHING
    case.execution.save(update_fields=["control_idempotency_refs", "status", "update_at"])
    adapter_instance = FixedControlReadAdapter(error=AssertionError("readback must not run"))

    response = read_control(case, adapter_instance)

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"
    assert adapter_instance.calls == []


@pytest.mark.django_db(transaction=True)
def test_control_recovery_flag_off_is_persistence_only(control_case):
    case = control_case
    record = seed_node_control_attempt(case, "retry")
    SpaceConfig.objects.filter(
        space_id=case.context.space_id,
        name=HarnessExecutionEnabledConfig.name,
    ).update(text_value="false")
    adapter_instance = FixedControlReadAdapter(error=AssertionError("readback must not run"))

    response = read_control(case, adapter_instance)

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"] == {"available": False, "reason": "execution_disabled"}
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"
    assert adapter_instance.calls == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "error,expected_code", [(TaskNotFound(), "VALIDATION_STALE"), (ReadbackUnavailable(), "RETRYABLE_INFRA")]
)
def test_control_readback_missing_or_unavailable_preserves_barrier(control_case, error, expected_code):
    case = control_case
    record = seed_node_control_attempt(case, "retry")

    response = read_control(case, FixedControlReadAdapter(error=error))

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["errors"][0]["code"] == expected_code
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"


@pytest.mark.django_db(transaction=True)
def test_completed_manual_snapshot_is_immutable_but_convergence_allows_a_new_control_key(control_case):
    case = control_case
    client = service_client(root_state="RUNNING")
    original, _, _, _, _ = approved_control(case, client)
    record = HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution")
    assert record.status == "COMPLETED"
    client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": "SUSPENDED"}}

    read_control(
        case,
        ExecutionReadAdapter(space_id=case.context.space_id, client_factory=lambda **_kwargs: client),
    )
    record.refresh_from_db()
    case.execution.refresh_from_db()
    case.control_request = {
        **case.control_request,
        "action": "resume",
        "idempotency_key": "control-workflow-2",
    }
    next_control = control(case, adapter=service_adapter(case, service_client(root_state="SUSPENDED")))

    assert record.response_snapshot == original
    assert case.execution.status == ExecutionRun.Status.PAUSED
    assert next_control["errors"][0]["code"] == "APPROVAL_REQUIRED"


@pytest.mark.django_db(transaction=True)
def test_get_inside_after_dispatch_hook_completes_barrier_for_original_control(control_case):
    case = control_case
    client = service_client(root_state="RUNNING")
    nested = []

    def reconcile_after_dispatch():
        client.get_task_states.return_value = {"result": True, "data": {"id": "root", "state": "SUSPENDED"}}
        nested.append(
            read_control(
                case,
                ExecutionReadAdapter(space_id=case.context.space_id, client_factory=lambda **_kwargs: client),
            )
        )

    response, _, _, _, _ = approved_control(case, client, test_after_dispatch_hook=reconcile_after_dispatch)

    record = HarnessIdempotencyRecord.objects.get(tool_name="control_workflow_execution")
    case.execution.refresh_from_db()
    assert nested[0]["artifact_refs"][0]["refresh"]["reason"] == "control_reconciled"
    assert response == record.response_snapshot
    assert response["ok"] is True
    assert record.status == "COMPLETED"
    assert case.execution.status == ExecutionRun.Status.PAUSED
    assert client.operate_task.call_count == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "action,pre_status,root_state,node_state",
    [
        ("pause", ExecutionRun.Status.EXECUTING, "SUSPENDED", None),
        ("resume", ExecutionRun.Status.PAUSED, "RUNNING", None),
        ("revoke", ExecutionRun.Status.EXECUTING, "READY", None),
        ("retry", ExecutionRun.Status.EXECUTING, "FAILED", "RUNNING"),
        ("skip", ExecutionRun.Status.EXECUTING, "FAILED", "RUNNING"),
        ("forced_fail", ExecutionRun.Status.EXECUTING, "RUNNING", "FAILED"),
    ],
)
def test_journal_rejects_action_specific_prestate_tamper_before_readback(
    control_case,
    action,
    pre_status,
    root_state,
    node_state,
):
    case = control_case
    if action in {"pause", "resume", "revoke"}:
        record = seed_task_control_attempt(case, action, pre_status, root_state)
    else:
        record = seed_node_control_attempt(
            case,
            action,
            payload_overrides={
                "pre_state": {
                    "root_state": root_state,
                    "template_node_id": "A",
                    "node_state": node_state,
                    "node_version": "v7",
                    "runtime_mapping_fingerprint": hashlib.sha256(b"A\0runtime-A").hexdigest(),
                }
            },
        )
    adapter_instance = FixedControlReadAdapter(error=AssertionError("readback must not run"))

    response = read_control(case, adapter_instance)

    record.refresh_from_db()
    case.execution.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"
    assert adapter_instance.calls == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "action,wrong_root,node_state",
    [
        ("retry", "RUNNING", "FAILED"),
        ("retry", "SUSPENDED", "FAILED"),
        ("skip", "FINISHED", "FAILED"),
        ("forced_fail", "FAILED", "RUNNING"),
    ],
)
def test_node_journal_wrong_pre_root_is_manual_with_zero_side_effects(
    control_case,
    action,
    wrong_root,
    node_state,
):
    case = control_case
    record = seed_node_control_attempt(
        case,
        action,
        payload_overrides={
            "pre_state": {
                "root_state": wrong_root,
                "template_node_id": "A",
                "node_state": node_state,
                "node_version": "v7",
                "runtime_mapping_fingerprint": hashlib.sha256(b"A\0runtime-A").hexdigest(),
            }
        },
    )
    adapter_instance = FixedControlReadAdapter(error=AssertionError("readback must not run"))
    before_execution = list(
        ExecutionRun.objects.filter(pk=case.execution.pk).values(
            "status",
            "last_engine_state",
            "heartbeat_at",
            "terminal_at",
            "control_idempotency_refs",
        )
    )
    before_record = list(HarnessIdempotencyRecord.objects.filter(pk=record.pk).values("status", "response_snapshot"))
    before_evidence = list(EvidenceEvent.objects.filter(execution=case.execution).values_list("id", flat=True))
    before_leases = list(TokenLease.objects.filter(execution=case.execution).values_list("id", "status", "revoked_at"))
    before_bundles = list(EvidenceBundle.objects.filter(execution=case.execution).values_list("id", flat=True))

    response = read_control(case, adapter_instance)

    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert adapter_instance.calls == []
    assert (
        list(
            ExecutionRun.objects.filter(pk=case.execution.pk).values(
                "status",
                "last_engine_state",
                "heartbeat_at",
                "terminal_at",
                "control_idempotency_refs",
            )
        )
        == before_execution
    )
    assert (
        list(HarnessIdempotencyRecord.objects.filter(pk=record.pk).values("status", "response_snapshot"))
        == before_record
    )
    assert list(EvidenceEvent.objects.filter(execution=case.execution).values_list("id", flat=True)) == before_evidence
    assert (
        list(TokenLease.objects.filter(execution=case.execution).values_list("id", "status", "revoked_at"))
        == before_leases
    )
    assert list(EvidenceBundle.objects.filter(execution=case.execution).values_list("id", flat=True)) == before_bundles


class InterleavingExecutionReadAdapter:
    def __init__(self, barrier, observation, control_observation):
        self.barrier = barrier
        self.observation = observation
        self.control_observation = control_observation
        self.calls = []

    def observe(self, task_ref, pipeline_tree, required_outputs):
        self.calls.append("observe")
        self.barrier()
        return self.observation

    def observe_control(self, task_ref, pipeline_tree, *, template_node_id=None):
        self.calls.append("observe_control")
        return self.control_observation


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "old_observation",
    [
        ExecutionObservation(state="RUNNING", node_outputs={}),
        ExecutionObservation(
            state="FINISHED",
            node_outputs={"A": NodeOutputEvidence.unavailable("node_detail_unavailable")},
        ),
        ExecutionObservation(
            state="FINISHED",
            node_outputs={"A": NodeOutputEvidence.available({"result": "ok"})},
        ),
    ],
    ids=["live", "waiting", "terminal"],
)
def test_stale_get_write_paths_yield_to_a_new_control_barrier(control_case, old_observation):
    case = control_case
    seeded = []

    def create_control_barrier():
        seeded.append(seed_task_control_attempt(case, "pause", ExecutionRun.Status.EXECUTING, "RUNNING"))

    broker = mock.Mock()
    adapter_instance = InterleavingExecutionReadAdapter(
        create_control_barrier,
        old_observation,
        ControlReadbackObservation(root_state="SUSPENDED"),
    )

    response = get_workflow_execution_with_context(
        case.context,
        {"execution_id": str(case.execution.id), "limit": 20},
        adapter=adapter_instance,
        token_broker=broker,
    )

    case.execution.refresh_from_db()
    seeded[0].refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciled"
    assert case.execution.status == ExecutionRun.Status.PAUSED
    assert seeded[0].status == "COMPLETED"
    assert adapter_instance.calls == ["observe", "observe_control"]
    assert not EvidenceEvent.objects.filter(
        execution=case.execution,
        event_type__in=["EXECUTION_SUCCEEDED", "EXECUTION_FAILED", "EXECUTION_CANCELLED"],
    ).exists()
    broker.revoke_execution_leases.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "action,node_state,invalid_root",
    [
        ("retry", "FAILED", "FINISHED"),
        ("retry", "FAILED", "REVOKED"),
        ("retry", "FAILED", "EXPIRED"),
        ("retry", "FAILED", "SUSPENDED"),
        ("skip", "FAILED", "FINISHED"),
        ("skip", "FAILED", "REVOKED"),
        ("forced_fail", "RUNNING", "FAILED"),
        ("forced_fail", "RUNNING", "SUSPENDED"),
    ],
)
def test_node_control_rejects_wrong_root_before_approval_barrier_or_mutation(
    control_case,
    action,
    node_state,
    invalid_root,
):
    case = control_case
    client = node_client(version="v7")
    client.get_task_states.return_value["data"]["state"] = invalid_root
    client.get_task_states.return_value["data"]["children"]["A"]["state"] = node_state
    request_payload = {
        **case.control_request,
        "action": action,
        "template_node_id": "A",
        "idempotency_key": "wrong-root-{}-{}".format(action, invalid_root.lower()),
    }
    if action in {"retry", "skip"}:
        request_payload["loop"] = False
    if action == "forced_fail":
        request_payload["reason_code"] = "operator_requested"

    response = control(case, request_payload, adapter=service_adapter(case, client))

    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ApprovalRequest.objects.filter(action=action).count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name="control_workflow_execution").count() == 0
    client.get_node_id_map.assert_not_called()
    client.node_operate.assert_not_called()


def _seed_two_task_control_journals(case, mode):
    first = seed_task_control_attempt(case, "pause", ExecutionRun.Status.EXECUTING, "RUNNING")
    complete_idempotency(
        first,
        {"ok": False, "errors": [{"code": "RETRYABLE_INFRA"}]},
        run=case.run,
        resource_reference=str(case.execution.id),
    )
    second = HarnessIdempotencyRecord.objects.create(
        platform_app=case.context.platform_app,
        actor=case.context.actor,
        space_id=case.context.space_id,
        tool_name="control_workflow_execution",
        run_scope="run:{}".format(case.run.run_id),
        run=case.run,
        idempotency_key="task-control-second",
        request_hash="f" * 64,
        status="IN_FLIGHT",
        response_snapshot={},
        resource_reference=str(case.execution.id),
    )
    first_ref = case.execution.control_idempotency_refs[0]
    second_ref = "idempotency://execution/{}".format(second.id)
    case.execution.control_idempotency_refs = [first_ref, second_ref]
    case.execution.save(update_fields=["control_idempotency_refs", "update_at"])
    if mode != "missing":
        event_ref = first_ref if mode == "wrong_ref" else second_ref
        record_evidence(
            run=case.run,
            revision=case.execution.revision,
            execution=case.execution,
            event_type="EXECUTION_CONTROL_DISPATCHING",
            action="pause",
            payload={
                "version": "control-attempt-v1",
                "action": "pause",
                "attempt": 2,
                "idempotency_ref": event_ref,
                "action_digest": "d" * 64,
                "pre_execution_status": ExecutionRun.Status.EXECUTING,
                "pre_state": {
                    "root_state": "RUNNING",
                    "template_node_id": None,
                    "node_state": None,
                    "node_version": None,
                    "runtime_mapping_fingerprint": None,
                },
                "template_target": {},
                "expected_readback": "SUSPENDED",
                "input_fields": [],
                "input_digest": hashlib.sha256(b"{}").hexdigest(),
            },
            actor=case.context.actor,
            correlation_id=case.context.correlation_id,
        )
    if mode in {"extra", "duplicate"}:
        payload = copy.deepcopy(
            EvidenceEvent.objects.filter(
                execution=case.execution,
                event_type="EXECUTION_CONTROL_DISPATCHING",
            )
            .order_by("-occurred_at", "-id")
            .first()
            .redacted_payload
        )
        if mode == "extra":
            payload["attempt"] = 3
        record_evidence(
            run=case.run,
            revision=case.execution.revision,
            execution=case.execution,
            event_type="EXECUTION_CONTROL_DISPATCHING",
            action="pause",
            payload=payload,
            actor=case.context.actor,
            correlation_id=case.context.correlation_id,
        )
    return second


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["wrong_ref", "extra", "missing", "duplicate"])
def test_control_recovery_requires_complete_ordered_journal_sequence(control_case, mode):
    case = control_case
    record = _seed_two_task_control_journals(case, mode)
    adapter_instance = FixedControlReadAdapter(error=AssertionError("readback must not run"))
    before = list(
        EvidenceEvent.objects.filter(execution=case.execution)
        .order_by("occurred_at", "id")
        .values_list("id", flat=True)
    )

    response = read_control(case, adapter_instance)

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"
    assert adapter_instance.calls == []
    assert (
        list(
            EvidenceEvent.objects.filter(execution=case.execution)
            .order_by("occurred_at", "id")
            .values_list("id", flat=True)
        )
        == before
    )


@pytest.mark.django_db(transaction=True)
def test_second_get_that_waited_for_completed_control_returns_reconciled_state(control_case):
    case = control_case
    record = seed_task_control_attempt(case, "pause", ExecutionRun.Status.EXECUTING, "RUNNING")
    observation = ControlReadbackObservation(root_state="SUSPENDED")
    nested = []

    class WaitingReadAdapter:
        def observe_control(self, task_ref, pipeline_tree, *, template_node_id=None):
            if not nested:
                nested.append(read_control(case, FixedControlReadAdapter(observation)))
            return observation

    outer = read_control(case, WaitingReadAdapter())

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert nested[0]["artifact_refs"][0]["refresh"]["reason"] == "control_reconciled"
    assert outer["artifact_refs"][0]["refresh"]["reason"] == "control_reconciled"
    assert case.execution.status == ExecutionRun.Status.PAUSED
    assert record.status == "COMPLETED"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("root_state", ["FINISHED", "REVOKED", "EXPIRED"])
def test_terminal_root_never_reopens_execution_from_node_control_recovery(control_case, root_state):
    case = control_case
    record = seed_node_control_attempt(case, "retry")
    observation = ControlReadbackObservation(
        root_state=root_state,
        template_node_id="A",
        node_state="RUNNING",
        node_version="v8",
        runtime_mapping_fingerprint=hashlib.sha256(b"A\0runtime-A").hexdigest(),
    )

    response = read_control(case, FixedControlReadAdapter(observation))

    case.execution.refresh_from_db()
    record.refresh_from_db()
    assert response["artifact_refs"][0]["refresh"]["reason"] == "control_reconciliation_required"
    assert case.execution.status == ExecutionRun.Status.CONTROL_DISPATCHING
    assert record.status == "IN_FLIGHT"
