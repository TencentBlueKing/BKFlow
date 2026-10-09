"""P3 release and execution Harness APIGW transport contracts."""

import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.apigw.serializers.harness.release_execution import (
    ControlWorkflowExecutionSerializer,
    GetWorkflowExecutionSerializer,
    PrepareReleaseSerializer,
    PublishWorkflowSerializer,
    StartWorkflowExecutionSerializer,
)
from bkflow.harness.permissions import HarnessPermission
from bkflow.harness.services.facade import P3_ACTION_RISK, HarnessFacade
from bkflow.space.configs import (
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
    HarnessExecutionEnabledConfig,
    HarnessPublishEnabledConfig,
    SpaceConfigValueType,
    SuperusersConfig,
)
from bkflow.space.models import Space, SpaceConfig

ENVELOPE_KEYS = {
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
RUN_ID = "00000000-0000-0000-0000-000000000001"
REVISION_ID = "00000000-0000-0000-0000-000000000002"
MANIFEST_ID = "00000000-0000-0000-0000-000000000003"
PUBLICATION_ID = "00000000-0000-0000-0000-000000000004"
EXECUTION_ID = "00000000-0000-0000-0000-000000000005"
APPROVAL_ID = "00000000-0000-0000-0000-000000000006"
PLAN_HASH = "a" * 64
MANIFEST_HASH = "b" * 64

P3_CASES = {
    "prepare_release": {
        "serializer": PrepareReleaseSerializer,
        "payload": {
            "run_id": RUN_ID,
            "revision_id": REVISION_ID,
            "expected_plan_hash": PLAN_HASH,
            "idempotency_key": "prepare-release-1",
        },
    },
    "publish_workflow": {
        "serializer": PublishWorkflowSerializer,
        "payload": {
            "run_id": RUN_ID,
            "manifest_id": MANIFEST_ID,
            "manifest_hash": MANIFEST_HASH,
            "version": "1.0.0",
            "description": "Harness publication",
            "idempotency_key": "publish-workflow-1",
        },
    },
    "start_workflow_execution": {
        "serializer": StartWorkflowExecutionSerializer,
        "payload": {
            "run_id": RUN_ID,
            "manifest_id": MANIFEST_ID,
            "publication_id": PUBLICATION_ID,
            "expected_plan_hash": PLAN_HASH,
            "name": "Harness execution",
            "constants": {},
            "idempotency_key": "start-execution-1",
        },
    },
    "get_workflow_execution": {
        "serializer": GetWorkflowExecutionSerializer,
        "payload": {"execution_id": EXECUTION_ID, "limit": 20},
    },
    "control_workflow_execution": {
        "serializer": ControlWorkflowExecutionSerializer,
        "payload": {
            "execution_id": EXECUTION_ID,
            "expected_manifest_hash": MANIFEST_HASH,
            "action": "pause",
            "idempotency_key": "pause-execution-1",
        },
    },
}


@pytest.fixture
def authorized_p3_space(db):
    space = Space.objects.create(
        name="Harness P3 transport space",
        app_code="trusted-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    configs = (
        (HarnessEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (HarnessPublishEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (HarnessExecutionEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (SuperusersConfig.name, SpaceConfigValueType.JSON.value, "", ["trusted-user"]),
        (
            HarnessDeploymentConfig.name,
            SpaceConfigValueType.JSON.value,
            "",
            {
                "platform_key": "bkaidev",
                "allowed_scope_types": ["project"],
                "scope_type": "project",
                "scope_value": "scope-1",
                "target_environment": "stag",
                "risk_policy_version": "risk-2026.09",
                "mcp_contract_version": "1.3.0",
            },
        ),
    )
    for name, value_type, text_value, json_value in configs:
        SpaceConfig.objects.create(
            space_id=space.id,
            name=name,
            value_type=value_type,
            text_value=text_value,
            json_value=json_value,
        )
    return space


def _path(space, tool):
    return "/apigw/space/{}/harness/{}/".format(space.id, tool)


def _request(path, payload, *, app_code="trusted-app", username="trusted-user", idempotency_header=None):
    headers = {"HTTP_X_REQUEST_ID": "p3-http-test"}
    if idempotency_header is not None:
        headers["HTTP_X_IDEMPOTENCY_KEY"] = idempotency_header
    request = APIRequestFactory().post(path, payload, format="json", **headers)
    request.app = SimpleNamespace(bk_app_code=app_code, verified=True)
    force_authenticate(request, user=SimpleNamespace(username=username, is_authenticated=True))
    return request


def _domain_envelope(context, *, ok=True, approval_request_id=None, artifact_refs=None):
    result = {
        "ok": ok,
        "run_id": RUN_ID,
        "revision_id": REVISION_ID,
        "plan_hash": PLAN_HASH,
        "status": "RELEASE_READY" if ok else "APPROVAL_PENDING",
        "summary": "downstream summary",
        "artifact_refs": artifact_refs or [],
        "errors": []
        if ok
        else [
            {
                "category": "APPROVAL_REQUIRED",
                "code": "APPROVAL_REQUIRED",
                "path": "approval_receipt_ref",
                "repairable": False,
                "retryable": False,
                "message": "downstream secret must not pass",
                "suggested_action": "unsafe-action",
            }
        ],
        "next_actions": [],
        "correlation_id": context.correlation_id,
    }
    if approval_request_id is not None:
        result["approval_request_id"] = approval_request_id
    return result


@pytest.mark.parametrize("tool", P3_CASES)
def test_p3_serializers_accept_only_exact_domain_requests(tool):
    case = P3_CASES[tool]
    assert case["serializer"](data=case["payload"]).is_valid(), tool
    assert case["serializer"](data={**case["payload"], "actor": "forged"}).is_valid() is False


@pytest.mark.parametrize("tool", ("publish_workflow", "start_workflow_execution", "control_workflow_execution"))
def test_only_approval_bound_operations_accept_the_complete_approval_pair(tool):
    case = P3_CASES[tool]
    approved = {
        **case["payload"],
        "approval_request_id": APPROVAL_ID,
        "approval_receipt_ref": "approval://receipt/p3-1",
    }
    assert case["serializer"](data=approved).is_valid()
    approved.pop("approval_receipt_ref")
    assert case["serializer"](data=approved).is_valid() is False

    for denied_tool in ("prepare_release", "get_workflow_execution"):
        denied = {**P3_CASES[denied_tool]["payload"], "approval_request_id": APPROVAL_ID}
        assert P3_CASES[denied_tool]["serializer"](data=denied).is_valid() is False


@pytest.mark.parametrize(
    "serializer,payload",
    [
        (PrepareReleaseSerializer, {**P3_CASES["prepare_release"]["payload"], "run_id": 1}),
        (GetWorkflowExecutionSerializer, {"execution_id": EXECUTION_ID, "limit": "20"}),
        (
            ControlWorkflowExecutionSerializer,
            {
                "execution_id": EXECUTION_ID,
                "expected_manifest_hash": MANIFEST_HASH,
                "action": "retry",
                "template_node_id": "node-a",
                "loop": 1,
                "idempotency_key": "retry-1",
            },
        ),
    ],
)
def test_p3_serializers_validate_strict_wire_types_before_drf_coercion(serializer, payload):
    assert serializer(data=payload).is_valid() is False


@pytest.mark.parametrize(
    "action,fields",
    [
        ("pause", {}),
        ("resume", {}),
        ("revoke", {}),
        ("retry", {"template_node_id": "node-a", "loop": False}),
        ("skip", {"template_node_id": "node-a", "loop": True}),
        ("callback", {"template_node_id": "node-a", "callback_data": {"result": "ok"}}),
        ("forced_fail", {"template_node_id": "node-a", "reason_code": "operator_requested"}),
        ("skip_exg", {"template_gateway_id": "gateway-a", "template_flow_id": "flow-a"}),
        (
            "skip_cpg",
            {
                "template_gateway_id": "gateway-a",
                "template_flow_ids": ["flow-a", "flow-b"],
                "template_converge_gateway_id": "gateway-b",
            },
        ),
    ],
)
def test_control_serializer_freezes_all_nine_tagged_action_shapes(action, fields):
    payload = {
        "execution_id": EXECUTION_ID,
        "expected_manifest_hash": MANIFEST_HASH,
        "action": action,
        "idempotency_key": "control-{}-1".format(action),
        **fields,
    }

    assert ControlWorkflowExecutionSerializer(data=payload).is_valid()
    assert ControlWorkflowExecutionSerializer(data={**payload, "runtime_node_id": "forged"}).is_valid() is False


def test_control_serializer_rejects_cross_tag_and_unknown_actions():
    pause_with_node = {**P3_CASES["control_workflow_execution"]["payload"], "template_node_id": "node-a"}
    unknown = {**P3_CASES["control_workflow_execution"]["payload"], "action": "delete"}

    assert ControlWorkflowExecutionSerializer(data=pause_with_node).is_valid() is False
    assert ControlWorkflowExecutionSerializer(data=unknown).is_valid() is False


def test_transport_preserves_receipt_and_human_text_bytes_for_domain_hashing():
    receipt = "approval://receipt/p3-1 "
    payload = {
        **P3_CASES["publish_workflow"]["payload"],
        "description": " release candidate ",
        "approval_request_id": APPROVAL_ID,
        "approval_receipt_ref": receipt,
    }
    serializer = PublishWorkflowSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["description"] == " release candidate "
    assert serializer.validated_data["approval_receipt_ref"] == receipt


@pytest.mark.django_db
@pytest.mark.parametrize("tool", P3_CASES)
def test_p3_routes_invoke_only_the_facade_with_trusted_context(monkeypatch, authorized_p3_space, tool):
    case = P3_CASES[tool]
    downstream = Mock(side_effect=lambda context, _payload: _domain_envelope(context))
    forbidden = Mock(side_effect=AssertionError("APIGW transport bypassed the Harness facade"))
    monkeypatch.setattr(HarnessFacade, tool, downstream)
    monkeypatch.setattr("bkflow.template.models.Template.release_template", forbidden)
    monkeypatch.setattr("bkflow.contrib.api.collections.task.TaskComponentClient.operate_task", forbidden)
    path = _path(authorized_p3_space, tool)
    idempotency_key = case["payload"].get("idempotency_key")

    response = resolve(path).func(
        _request(path, case["payload"], idempotency_header=idempotency_key),
        space_id=str(authorized_p3_space.id),
    )

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is True
    context, payload = downstream.call_args.args
    assert (
        context.platform_key,
        context.platform_app,
        context.actor,
        context.space_id,
        context.scope_type,
        context.scope_value,
        context.target_environment,
        context.mcp_contract_version,
    ) == (
        "bkaidev",
        "trusted-app",
        "trusted-user",
        authorized_p3_space.id,
        "project",
        "scope-1",
        "stag",
        "1.3.0",
    )
    assert payload == case["payload"]
    forbidden.assert_not_called()


@pytest.mark.django_db
def test_old_contract_rejects_p3_before_body_or_facade(monkeypatch, authorized_p3_space):
    deployment = SpaceConfig.objects.get(space_id=authorized_p3_space.id, name=HarnessDeploymentConfig.name)
    deployment.json_value["mcp_contract_version"] = "1.2.0"
    deployment.save(update_fields=["json_value"])
    downstream = Mock(side_effect=AssertionError("old contracts must fail before facade"))
    monkeypatch.setattr(HarnessFacade, "prepare_release", downstream)
    path = _path(authorized_p3_space, "prepare_release")

    response = resolve(path).func(_request(path, {"secret": "Bearer sentinel"}), space_id=str(authorized_p3_space.id))

    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    downstream.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,flag",
    [
        ("prepare_release", HarnessPublishEnabledConfig.name),
        ("publish_workflow", HarnessPublishEnabledConfig.name),
        ("start_workflow_execution", HarnessExecutionEnabledConfig.name),
        ("control_workflow_execution", HarnessExecutionEnabledConfig.name),
    ],
)
def test_mutating_p3_feature_flags_fail_before_facade(monkeypatch, authorized_p3_space, tool, flag):
    SpaceConfig.objects.filter(space_id=authorized_p3_space.id, name=flag).update(text_value="false")
    downstream = Mock(side_effect=AssertionError("disabled tool reached facade"))
    monkeypatch.setattr(HarnessFacade, tool, downstream)
    case = P3_CASES[tool]
    path = _path(authorized_p3_space, tool)

    response = resolve(path).func(_request(path, case["payload"]), space_id=str(authorized_p3_space.id))

    assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_get_execution_remains_persistence_readable_when_execution_flag_is_off(monkeypatch, authorized_p3_space):
    SpaceConfig.objects.filter(space_id=authorized_p3_space.id, name=HarnessExecutionEnabledConfig.name).update(
        text_value="false"
    )
    downstream = Mock(side_effect=lambda context, _payload: _domain_envelope(context))
    monkeypatch.setattr(HarnessFacade, "get_workflow_execution", downstream)
    path = _path(authorized_p3_space, "get_workflow_execution")

    response = resolve(path).func(
        _request(path, P3_CASES["get_workflow_execution"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert response.data["ok"] is True
    downstream.assert_called_once()


@pytest.mark.django_db
def test_production_facade_does_not_invent_a_release_policy(authorized_p3_space):
    path = _path(authorized_p3_space, "prepare_release")

    response = resolve(path).func(
        _request(path, P3_CASES["prepare_release"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "RELEASE_POLICY_UNAVAILABLE"
    assert response.data["errors"][0]["category"] == "VALIDATION"
    assert response.data["artifact_refs"] == []


@pytest.mark.django_db
def test_approval_request_is_normalized_into_the_fixed_safe_envelope(monkeypatch, authorized_p3_space):
    sentinel = "Bearer plaintext-approval-sentinel"
    downstream = Mock(
        side_effect=lambda context, _payload: _domain_envelope(
            context,
            ok=False,
            approval_request_id=APPROVAL_ID,
        )
    )
    monkeypatch.setattr(HarnessFacade, "publish_workflow", downstream)
    path = _path(authorized_p3_space, "publish_workflow")

    response = resolve(path).func(
        _request(path, P3_CASES["publish_workflow"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["errors"][0]["code"] == "APPROVAL_REQUIRED"
    assert response.data["artifact_refs"] == [{"type": "approval_request", "approval_request_id": APPROVAL_ID}]
    assert sentinel not in repr(response.data)
    assert "plaintext-approval-sentinel" not in repr(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ok,approval_request_id", [(False, "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"), (True, APPROVAL_ID)]
)
def test_noncanonical_or_success_state_approval_handle_fails_closed(
    monkeypatch, authorized_p3_space, ok, approval_request_id
):
    downstream = Mock(
        side_effect=lambda context, _payload: _domain_envelope(context, ok=ok, approval_request_id=approval_request_id)
    )
    monkeypatch.setattr(HarnessFacade, "publish_workflow", downstream)
    path = _path(authorized_p3_space, "publish_workflow")

    response = resolve(path).func(
        _request(path, P3_CASES["publish_workflow"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert approval_request_id not in repr(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize("code", ("APPROVAL_INVALID", "RETRYABLE_INFRA"))
def test_only_an_exact_approval_required_failure_can_project_an_approval_handle(monkeypatch, authorized_p3_space, code):
    def domain(context, _payload):
        result = _domain_envelope(context, ok=False, approval_request_id=APPROVAL_ID)
        result["errors"][0]["code"] = code
        return result

    monkeypatch.setattr(HarnessFacade, "publish_workflow", Mock(side_effect=domain))
    path = _path(authorized_p3_space, "publish_workflow")

    response = resolve(path).func(
        _request(path, P3_CASES["publish_workflow"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert APPROVAL_ID not in repr(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,ok,code",
    [
        ("publish_workflow", True, None),
        ("get_workflow_execution", True, None),
        ("get_workflow_execution", False, "VALIDATION_STALE"),
    ],
)
def test_raw_domain_artifacts_can_never_project_an_approval_handle(monkeypatch, authorized_p3_space, tool, ok, code):
    def domain(context, _payload):
        result = _domain_envelope(
            context,
            ok=ok,
            artifact_refs=[{"type": "approval_request", "approval_request_id": APPROVAL_ID}],
        )
        if code is not None:
            result["errors"][0]["code"] = code
        return result

    monkeypatch.setattr(HarnessFacade, tool, Mock(side_effect=domain))
    path = _path(authorized_p3_space, tool)

    response = resolve(path).func(_request(path, P3_CASES[tool]["payload"]), space_id=str(authorized_p3_space.id))

    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response.data["artifact_refs"] == []
    assert APPROVAL_ID not in repr(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "artifact",
    [
        {"type": "safe_artifact", "payload": {"approval_request_id": "00000000-0000-0000-0000-000000000007"}},
        {"type": "safe_artifact", "payload": {"type": "approval_request", "value": "opaque"}},
    ],
)
def test_nested_or_conflicting_raw_approval_artifact_fails_closed(monkeypatch, authorized_p3_space, artifact):
    downstream = Mock(
        side_effect=lambda context, _payload: _domain_envelope(
            context,
            ok=False,
            approval_request_id=APPROVAL_ID,
            artifact_refs=[artifact],
        )
    )
    monkeypatch.setattr(HarnessFacade, "publish_workflow", downstream)
    path = _path(authorized_p3_space, "publish_workflow")

    response = resolve(path).func(
        _request(path, P3_CASES["publish_workflow"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response.data["artifact_refs"] == []
    assert APPROVAL_ID not in repr(response.data)


@pytest.mark.django_db
def test_failure_uses_only_taxonomy_and_fixed_remediation_actions(monkeypatch, authorized_p3_space):
    def domain(context, _payload):
        result = _domain_envelope(context, ok=False, approval_request_id=APPROVAL_ID)
        result["next_actions"] = ["obtain_approval", "manual_reconcile_execution", "run_arbitrary_command"]
        return result

    monkeypatch.setattr(HarnessFacade, "publish_workflow", Mock(side_effect=domain))
    path = _path(authorized_p3_space, "publish_workflow")

    response = resolve(path).func(
        _request(path, P3_CASES["publish_workflow"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert response.data["next_actions"] == [
        "request_debug_approval",
        "obtain_approval",
        "manual_reconcile_execution",
    ]
    assert "run_arbitrary_command" not in repr(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize("raw_next_actions", ({"malformed": True}, ["obtain_approval"] * 17))
def test_permission_error_stops_mixed_failures_even_when_raw_remediation_is_invalid(
    monkeypatch, authorized_p3_space, raw_next_actions
):
    error_codes = [
        "CAPABILITY_NOT_FOUND",
        "AMBIGUOUS_CAPABILITY",
        "CAPABILITY_SCHEMA_UNAVAILABLE",
        "TRUSTED_CONTEXT_STALE",
        "SCHEMA_DRIFT",
        "SCHEMA_VALIDATION_ERROR",
        "PLAN_HASH_MISMATCH",
        "VALIDATION_STALE",
        "DEBUG_CONFLICT",
        "APPROVAL_REQUIRED",
        "TOKEN_LEASE",
        "DEBUG_DEPENDENCY",
        "RELEASE_POLICY_UNAVAILABLE",
        "VERSION_CONFLICT",
        "EXECUTION_REJECTED",
        "RETRYABLE_INFRA",
        "HARNESS_ACCESS_DENIED",
        "HARNESS_TOOL_UNAVAILABLE",
    ]

    def domain(context, _payload):
        result = _domain_envelope(context, ok=False)
        result["errors"] = [
            {"code": code, "path": "request", "repairable": False, "retryable": False} for code in error_codes
        ]
        result["next_actions"] = raw_next_actions
        return result

    monkeypatch.setattr(HarnessFacade, "get_workflow_execution", Mock(side_effect=domain))
    path = _path(authorized_p3_space, "get_workflow_execution")

    response = resolve(path).func(
        _request(path, P3_CASES["get_workflow_execution"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert response.data["next_actions"] == []
    assert "denied" in response.data["summary"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool", ("prepare_release", "publish_workflow", "start_workflow_execution", "control_workflow_execution")
)
def test_write_idempotency_header_must_match_body(monkeypatch, authorized_p3_space, tool):
    downstream = Mock(side_effect=lambda context, _payload: _domain_envelope(context))
    monkeypatch.setattr(HarnessFacade, tool, downstream)
    case = P3_CASES[tool]
    path = _path(authorized_p3_space, tool)

    response = resolve(path).func(
        _request(path, case["payload"], idempotency_header="different"),
        space_id=str(authorized_p3_space.id),
    )

    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_get_execution_rejects_idempotency_header(monkeypatch, authorized_p3_space):
    downstream = Mock(side_effect=lambda context, _payload: _domain_envelope(context))
    monkeypatch.setattr(HarnessFacade, "get_workflow_execution", downstream)
    path = _path(authorized_p3_space, "get_workflow_execution")

    response = resolve(path).func(
        _request(path, P3_CASES["get_workflow_execution"]["payload"], idempotency_header="read-key"),
        space_id=str(authorized_p3_space.id),
    )

    assert response.data["ok"] is False
    downstream.assert_not_called()


@pytest.mark.django_db
def test_p3_response_budget_and_secret_boundary_fail_closed(monkeypatch, authorized_p3_space):
    downstream = Mock(
        side_effect=lambda context, _payload: _domain_envelope(
            context,
            artifact_refs=[{"type": "execution", "payload": "x" * 70000, "credential": "Bearer sentinel"}],
        )
    )
    monkeypatch.setattr(HarnessFacade, "get_workflow_execution", downstream)
    path = _path(authorized_p3_space, "get_workflow_execution")

    response = resolve(path).func(
        _request(path, P3_CASES["get_workflow_execution"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert "sentinel" not in repr(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize("artifact_count,expected_ok", [(4, True), (5, False)])
def test_real_drf_renderer_enforces_the_64_kib_response_budget(
    monkeypatch, authorized_p3_space, artifact_count, expected_ok
):
    artifacts = [{"type": "bounded_chunk", "index": index, "payload": "x" * 15000} for index in range(artifact_count)]
    downstream = Mock(side_effect=lambda context, _payload: _domain_envelope(context, artifact_refs=artifacts))
    monkeypatch.setattr(HarnessFacade, "get_workflow_execution", downstream)
    path = _path(authorized_p3_space, "get_workflow_execution")

    response = resolve(path).func(
        _request(path, P3_CASES["get_workflow_execution"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert response.data["ok"] is expected_ok
    if not expected_ok:
        assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "code,category",
    [
        ("RELEASE_POLICY_UNAVAILABLE", "VALIDATION"),
        ("VERSION_CONFLICT", "VALIDATION"),
        ("EXECUTION_REJECTED", "RUNTIME"),
        ("EXECUTION_FAILED", "RUNTIME"),
        ("POSTCONDITION_FAILED", "POSTCONDITION"),
    ],
)
def test_p3_error_taxonomy_is_not_downgraded_to_retryable_infrastructure(
    monkeypatch, authorized_p3_space, code, category
):
    def domain(context, _payload):
        result = _domain_envelope(context, ok=False)
        result["errors"][0]["code"] = code
        return result

    monkeypatch.setattr(HarnessFacade, "get_workflow_execution", Mock(side_effect=domain))
    path = _path(authorized_p3_space, "get_workflow_execution")

    response = resolve(path).func(
        _request(path, P3_CASES["get_workflow_execution"]["payload"]), space_id=str(authorized_p3_space.id)
    )

    assert response.data["errors"][0]["code"] == code
    assert response.data["errors"][0]["category"] == category


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,fields,expected_risk",
    [
        ("pause", {}, "L2"),
        ("forced_fail", {"template_node_id": "node-a", "reason_code": "operator_requested"}, "L3"),
    ],
)
def test_control_audit_uses_the_normalized_action_risk(
    monkeypatch, caplog, authorized_p3_space, action, fields, expected_risk
):
    caplog.set_level("INFO", logger="bkflow.harness")
    downstream = Mock(side_effect=lambda context, _payload: _domain_envelope(context))
    monkeypatch.setattr(HarnessFacade, "control_workflow_execution", downstream)
    payload = {
        "execution_id": EXECUTION_ID,
        "expected_manifest_hash": MANIFEST_HASH,
        "action": action,
        "idempotency_key": "audit-{}-1".format(action),
        **fields,
    }
    path = _path(authorized_p3_space, "control_workflow_execution")

    response = resolve(path).func(_request(path, payload), space_id=str(authorized_p3_space.id))

    assert response.data["ok"] is True
    audit = [record.harness_audit for record in caplog.records if hasattr(record, "harness_audit")][-1]
    assert audit["risk"] == expected_risk


@pytest.mark.parametrize("tool", P3_CASES)
def test_p3_views_are_post_only_and_reuse_harness_permission(tool):
    view = resolve("/apigw/space/1/harness/{}/".format(tool)).func
    assert set(view.cls.http_method_names) == {"post", "options"}
    assert HarnessPermission in view.cls.permission_classes
    assert P3_ACTION_RISK[tool] in {"L0", "L2", "L3"}


def test_facade_methods_delegate_to_context_bound_domain_services(monkeypatch):
    context = SimpleNamespace(space_id=1, actor="actor", scope_type="project", scope_value="scope")
    service = object()
    facade = HarnessFacade()
    monkeypatch.setattr(facade, "_service", Mock(return_value=service))
    calls = {}

    def capture(name):
        def wrapped(*args):
            calls[name] = args
            return {"tool": name}

        return wrapped

    monkeypatch.setattr("bkflow.harness.services.release.facade.prepare_release_with_context", capture("prepare"))
    monkeypatch.setattr("bkflow.harness.services.release.publish.publish_workflow_with_context", capture("publish"))
    monkeypatch.setattr(
        "bkflow.harness.services.execution.saga.start_workflow_execution_with_context", capture("start")
    )
    monkeypatch.setattr("bkflow.harness.services.execution.read.get_workflow_execution_with_context", capture("get"))
    monkeypatch.setattr(
        "bkflow.harness.services.execution.control.control_workflow_execution_with_context", capture("control")
    )

    for tool in P3_CASES:
        assert getattr(facade, tool)(context, copy.deepcopy(P3_CASES[tool]["payload"]))

    assert calls["prepare"] == (context, P3_CASES["prepare_release"]["payload"], service)
    assert calls["publish"] == (context, P3_CASES["publish_workflow"]["payload"], service)
    assert calls["start"] == (context, P3_CASES["start_workflow_execution"]["payload"], service)
    assert calls["get"] == (context, P3_CASES["get_workflow_execution"]["payload"])
    assert calls["control"] == (context, P3_CASES["control_workflow_execution"]["payload"])
