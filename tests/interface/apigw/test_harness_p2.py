"""P2 Harness debug APIGW transport contracts."""

import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.apigw.serializers.harness.debug import (
    ControlDebugSessionSerializer,
    GetDebugSessionSerializer,
    RunDebugSerializer,
    StartDebugSessionSerializer,
)
from bkflow.apigw.views.harness.debug import (
    control_debug_session,
    get_debug_session,
    run_debug,
    start_debug_session,
)
from bkflow.harness.permissions import HarnessPermission
from bkflow.harness.services.facade import P2_ACTION_RISK, HarnessFacade
from bkflow.space.configs import (
    HarnessDebugEnabledConfig,
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
    HarnessRealStepEnabledConfig,
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
SESSION_ID = "00000000-0000-0000-0000-000000000003"
PLAN_HASH = "a" * 64

P2_CASES = {
    "start_debug_session": {
        "path": "start_debug_session",
        "serializer": StartDebugSessionSerializer,
        "payload": {
            "run_id": RUN_ID,
            "revision_id": REVISION_ID,
            "expected_plan_hash": PLAN_HASH,
            "mode": "step",
            "idempotency_key": "start-debug-http-1",
        },
    },
    "run_debug": {
        "path": "run_debug",
        "serializer": RunDebugSerializer,
        "payload": {
            "session_id": SESSION_ID,
            "expected_plan_hash": PLAN_HASH,
            "mode": "step",
            "execution_mode": "mock",
            "node_id": "node_a",
            "input_overrides": {},
            "mock_result": "success",
            "mock_outputs": {"result": "ok"},
            "mock_error": "",
            "idempotency_key": "run-debug-http-1",
        },
    },
    "get_debug_session": {
        "path": "get_debug_session",
        "serializer": GetDebugSessionSerializer,
        "payload": {"session_id": SESSION_ID, "limit": 20},
    },
    "control_debug_session": {
        "path": "control_debug_session",
        "serializer": ControlDebugSessionSerializer,
        "payload": {
            "session_id": SESSION_ID,
            "expected_plan_hash": PLAN_HASH,
            "action": "reset",
            "node_ids": ["node_a"],
            "idempotency_key": "control-debug-http-1",
        },
    },
}


@pytest.fixture
def authorized_p2_space(db):
    """Create the complete gateway-owned deployment for contract 1.2.0."""
    space = Space.objects.create(
        name="Harness P2 transport space",
        app_code="trusted-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    configs = (
        (HarnessEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (HarnessDebugEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (HarnessRealStepEnabledConfig.name, SpaceConfigValueType.TEXT.value, "false", {}),
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
                "mcp_contract_version": "1.2.0",
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


def _path(space, name):
    return "/apigw/space/{}/harness/{}/".format(space.id, name)


def _request(path, payload, *, app_code="trusted-app", username="trusted-user", idempotency_header=None):
    headers = {"HTTP_X_REQUEST_ID": "debug-http-test"}
    if idempotency_header is not None:
        headers["HTTP_X_IDEMPOTENCY_KEY"] = idempotency_header
    request = APIRequestFactory().post(path, payload, format="json", **headers)
    request.app = SimpleNamespace(bk_app_code=app_code, verified=True)
    force_authenticate(request, user=SimpleNamespace(username=username, is_authenticated=True))
    return request


def _domain_envelope(context, *, ok=True, code=None):
    errors = []
    if code:
        errors = [
            {
                "category": "unsafe-category",
                "code": code,
                "path": "provider.secret",
                "repairable": False,
                "retryable": False,
                "message": "credential://raw-downstream-secret",
                "suggested_action": "unsafe-action",
            }
        ]
    return {
        "ok": ok,
        "run_id": RUN_ID,
        "revision_id": REVISION_ID,
        "plan_hash": PLAN_HASH,
        "status": "DEBUGGING" if ok else None,
        "summary": "safe domain summary",
        "artifact_refs": [] if not ok else [{"type": "debug_fixture", "session_id": SESSION_ID}],
        "errors": errors,
        "next_actions": ["unsafe-next-action"],
        "correlation_id": context.correlation_id,
    }


@pytest.mark.parametrize("case", P2_CASES.values(), ids=P2_CASES)
def test_p2_serializers_are_closed_and_accept_only_tagged_requests(case):
    """Transport parsing preserves the exact P2 tagged unions and rejects authority."""
    serializer = case["serializer"](data=case["payload"])
    assert serializer.is_valid(), serializer.errors
    assert case["serializer"](data={**case["payload"], "actor": "forged"}).is_valid() is False

    if case["path"] == "run_debug":
        assert case["serializer"](data={**case["payload"], "inputs": {}}).is_valid() is False
    if case["path"] == "control_debug_session":
        assert case["serializer"](data={**case["payload"], "node_id": "unexpected"}).is_valid() is False


@pytest.mark.parametrize("raw_limit", ["20", True, False])
def test_get_serializer_rejects_wire_values_that_only_coerce_to_integer(raw_limit):
    """JSON strings and booleans cannot masquerade as the integer history limit."""
    payload = {**P2_CASES["get_debug_session"]["payload"], "limit": raw_limit}

    assert GetDebugSessionSerializer(data=payload).is_valid() is False


@pytest.mark.parametrize("raw_enabled", ["false", "1", "0", 1, 0])
def test_control_serializer_rejects_wire_values_that_only_coerce_to_boolean(raw_enabled):
    """Only JSON true/false may select a node Mock state."""
    payload = {
        "session_id": SESSION_ID,
        "expected_plan_hash": PLAN_HASH,
        "action": "set_node_mock",
        "node_id": "node_a",
        "enabled": raw_enabled,
        "mock_result": "success",
        "mock_outputs": {},
        "mock_error": "",
        "idempotency_key": "strict-control-wire-1",
    }

    assert ControlDebugSessionSerializer(data=payload).is_valid() is False


@pytest.mark.parametrize(
    "serializer,payload",
    [
        (
            GetDebugSessionSerializer,
            {"session_id": SESSION_ID, "cursor": 123},
        ),
        (
            RunDebugSerializer,
            {**P2_CASES["run_debug"]["payload"], "node_id": 123},
        ),
        (
            StartDebugSessionSerializer,
            {**P2_CASES["start_debug_session"]["payload"], "idempotency_key": 123},
        ),
    ],
    ids=("numeric-cursor", "numeric-node-id", "numeric-idempotency-key"),
)
def test_p2_serializers_validate_raw_wire_types_before_drf_string_coercion(serializer, payload):
    """Every P2 primitive reaches the exact domain contract with its original JSON type."""
    assert serializer(data=payload).is_valid() is False


def test_p2_serializers_keep_exact_json_integer_and_boolean_boundaries():
    """The strict gate still accepts genuine JSON integers and booleans."""
    get_payload = {**P2_CASES["get_debug_session"]["payload"], "limit": 20}
    control_payload = {
        "session_id": SESSION_ID,
        "expected_plan_hash": PLAN_HASH,
        "action": "set_node_mock",
        "node_id": "node_a",
        "enabled": False,
        "mock_result": "success",
        "mock_outputs": {},
        "mock_error": "",
        "idempotency_key": "strict-control-wire-2",
    }

    assert GetDebugSessionSerializer(data=get_payload).is_valid() is True
    assert ControlDebugSessionSerializer(data=control_payload).is_valid() is True


@pytest.mark.django_db
@pytest.mark.parametrize("tool", P2_CASES)
def test_p2_routes_use_only_trusted_context_and_harness_facade(
    monkeypatch,
    authorized_p2_space,
    tool,
):
    """A P2 route invokes one Facade method without touching SDK or Token views."""
    case = P2_CASES[tool]
    downstream = Mock(side_effect=lambda context, _payload: _domain_envelope(context))
    forbidden = Mock(side_effect=AssertionError("transport must not call DebugService or Token APIs"))
    monkeypatch.setattr(HarnessFacade, tool, downstream)
    monkeypatch.setattr("bkflow.template.debug.service.DebugService.step_run", forbidden)
    monkeypatch.setattr("bkflow.permission.token_issuer.issue_resource_token", forbidden)
    path = _path(authorized_p2_space, case["path"])
    idempotency_key = case["payload"].get("idempotency_key")

    response = resolve(path).func(
        _request(path, case["payload"], idempotency_header=idempotency_key),
        space_id=str(authorized_p2_space.id),
    )

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is True
    context, request_payload = downstream.call_args.args
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
        authorized_p2_space.id,
        "project",
        "scope-1",
        "stag",
        "1.2.0",
    )
    assert request_payload == case["payload"]
    assert response.data["correlation_id"] == "debug-http-test"
    forbidden.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "app_code,username,expected_code",
    [
        ("wrong-app", "trusted-user", "HARNESS_APP_SPACE_FORBIDDEN"),
        ("trusted-app", "wrong-user", "HARNESS_USER_SPACE_FORBIDDEN"),
    ],
)
def test_p2_permission_binds_authenticated_app_user_and_route_space(
    monkeypatch,
    authorized_p2_space,
    app_code,
    username,
    expected_code,
):
    """Neither the body nor another gateway identity can widen route ownership."""
    downstream = Mock()
    monkeypatch.setattr(HarnessFacade, "start_debug_session", downstream)
    case = P2_CASES["start_debug_session"]
    path = _path(authorized_p2_space, case["path"])

    response = resolve(path).func(
        _request(path, case["payload"], app_code=app_code, username=username),
        space_id=str(authorized_p2_space.id),
    )

    assert response.status_code == 200
    assert response.data["errors"][0]["code"] == expected_code
    assert response.data["errors"][0]["category"] == "PERMISSION"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_contract_1_1_rejects_p2_before_body_or_facade(monkeypatch, authorized_p2_space):
    """A five-Tool connection cannot discover or execute a P2 operation."""
    deployment = SpaceConfig.objects.get(space_id=authorized_p2_space.id, name=HarnessDeploymentConfig.name)
    deployment.json_value = {**deployment.json_value, "mcp_contract_version": "1.1.0"}
    deployment.save(update_fields=["json_value"])
    downstream = Mock()
    monkeypatch.setattr(HarnessFacade, "start_debug_session", downstream)
    path = _path(authorized_p2_space, "start_debug_session")

    response = resolve(path).func(
        _request(path, {"actor": "forged"}),
        space_id=str(authorized_p2_space.id),
    )

    assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_debug_flag_off_keeps_get_readable_and_rejects_three_mutations(monkeypatch, authorized_p2_space):
    """Rollout disable preserves persisted reads but blocks every new debug mutation."""
    flag = SpaceConfig.objects.get(space_id=authorized_p2_space.id, name=HarnessDebugEnabledConfig.name)
    flag.text_value = "false"
    flag.save(update_fields=["text_value"])
    mocks = {}
    for tool in P2_CASES:
        mocks[tool] = Mock(side_effect=lambda context, _payload: _domain_envelope(context))
        monkeypatch.setattr(HarnessFacade, tool, mocks[tool])

    for tool in ("start_debug_session", "run_debug", "control_debug_session"):
        case = P2_CASES[tool]
        path = _path(authorized_p2_space, case["path"])
        response = resolve(path).func(_request(path, case["payload"]), space_id=str(authorized_p2_space.id))
        assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
        mocks[tool].assert_not_called()

    case = P2_CASES["get_debug_session"]
    path = _path(authorized_p2_space, case["path"])
    response = resolve(path).func(_request(path, case["payload"]), space_id=str(authorized_p2_space.id))
    assert response.data["ok"] is True
    mocks["get_debug_session"].assert_called_once()


@pytest.mark.django_db
def test_debug_flag_off_get_does_not_construct_provider_service(monkeypatch, authorized_p2_space):
    """The compatibility read path cannot eagerly touch a capability catalog."""
    flag = SpaceConfig.objects.get(space_id=authorized_p2_space.id, name=HarnessDebugEnabledConfig.name)
    flag.text_value = "false"
    flag.save(update_fields=["text_value"])
    forbidden = Mock(side_effect=AssertionError("flag-off read must not construct provider services"))
    downstream = Mock(side_effect=lambda context, _payload, _service: _domain_envelope(context))
    monkeypatch.setattr(HarnessFacade, "_service", forbidden)
    monkeypatch.setattr(
        "bkflow.harness.services.debug.facade.get_debug_session_with_context",
        downstream,
    )
    case = P2_CASES["get_debug_session"]
    path = _path(authorized_p2_space, case["path"])

    response = resolve(path).func(_request(path, case["payload"]), space_id=str(authorized_p2_space.id))

    assert response.data["ok"] is True
    forbidden.assert_not_called()
    assert downstream.call_args.args[2] is None


@pytest.mark.django_db
def test_success_preserves_only_negotiated_bounded_next_actions(monkeypatch, authorized_p2_space):
    """Transport navigation is useful without reflecting arbitrary downstream commands."""
    case = P2_CASES["run_debug"]
    path = _path(authorized_p2_space, case["path"])

    def domain(context, _payload):
        result = _domain_envelope(context)
        result["next_actions"] = ["get_debug_session", "get_debug_session", "unknown_tool", 42]
        return result

    monkeypatch.setattr(HarnessFacade, "run_debug", Mock(side_effect=domain))

    response = resolve(path).func(_request(path, case["payload"]), space_id=str(authorized_p2_space.id))

    assert response.data["ok"] is True
    assert response.data["next_actions"] == ["get_debug_session"]


@pytest.mark.django_db
def test_success_allows_only_exact_redacted_values_under_sensitive_artifact_keys(
    monkeypatch,
    authorized_p2_space,
):
    """Task7 projections retain useful key shape but can never carry the original secret."""
    case = P2_CASES["get_debug_session"]
    path = _path(authorized_p2_space, case["path"])

    def domain(context, _payload):
        result = _domain_envelope(context)
        result["artifact_refs"] = [
            {
                "type": "debug_session",
                "context": {"global_vars": {"password": "[REDACTED]", "safe": "visible"}},
            }
        ]
        return result

    downstream = Mock(side_effect=domain)
    monkeypatch.setattr(HarnessFacade, "get_debug_session", downstream)
    safe = resolve(path).func(_request(path, case["payload"]), space_id=str(authorized_p2_space.id))

    assert safe.data["ok"] is True
    assert safe.data["artifact_refs"][0]["context"]["global_vars"]["password"] == "[REDACTED]"

    def unsafe_domain(context, _payload):
        result = domain(context, _payload)
        result["artifact_refs"][0]["context"]["global_vars"]["password"] = "raw-secret-value"
        return result

    downstream.side_effect = unsafe_domain
    unsafe = resolve(path).func(_request(path, case["payload"]), space_id=str(authorized_p2_space.id))

    assert unsafe.data["ok"] is False
    assert unsafe.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert "raw-secret-value" not in str(unsafe.data)


@pytest.mark.django_db
def test_idempotency_header_is_only_an_optional_consistency_guard(monkeypatch, authorized_p2_space):
    """The header may confirm a write key but can neither replace nor conflict with the body."""
    case = P2_CASES["start_debug_session"]
    path = _path(authorized_p2_space, case["path"])
    downstream = Mock(side_effect=lambda context, _payload: _domain_envelope(context))
    monkeypatch.setattr(HarnessFacade, "start_debug_session", downstream)

    matching = resolve(path).func(
        _request(path, case["payload"], idempotency_header=case["payload"]["idempotency_key"]),
        space_id=str(authorized_p2_space.id),
    )
    conflicting = resolve(path).func(
        _request(path, case["payload"], idempotency_header="different-key"),
        space_id=str(authorized_p2_space.id),
    )
    missing_body = copy.deepcopy(case["payload"])
    missing_body.pop("idempotency_key")
    replacement = resolve(path).func(
        _request(path, missing_body, idempotency_header="header-only-key"),
        space_id=str(authorized_p2_space.id),
    )

    assert matching.data["ok"] is True
    assert conflicting.data["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert replacement.data["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    downstream.assert_called_once()
    assert downstream.call_args.args[1]["idempotency_key"] == case["payload"]["idempotency_key"]


@pytest.mark.django_db
def test_read_tool_rejects_meaningless_idempotency_header(monkeypatch, authorized_p2_space):
    """A read request cannot imply write or replay semantics through a transport header."""
    downstream = Mock()
    monkeypatch.setattr(HarnessFacade, "get_debug_session", downstream)
    case = P2_CASES["get_debug_session"]
    path = _path(authorized_p2_space, case["path"])

    response = resolve(path).func(
        _request(path, case["payload"], idempotency_header="read-key"),
        space_id=str(authorized_p2_space.id),
    )

    assert response.data["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    downstream.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("failure", ["domain", "exception"])
def test_p2_errors_are_normalized_without_downstream_text(monkeypatch, authorized_p2_space, failure):
    """Domain and unexpected errors leave through the fixed safe Envelope taxonomy."""
    sentinel = "credential://raw-downstream-secret"
    if failure == "domain":
        downstream = Mock(
            side_effect=lambda context, _payload: _domain_envelope(
                context,
                ok=False,
                code="DEBUG_EXECUTION_FAILED",
            )
        )
        expected_code = "DEBUG_EXECUTION_FAILED"
    else:
        downstream = Mock(side_effect=RuntimeError(sentinel))
        expected_code = "RETRYABLE_INFRA"
    monkeypatch.setattr(HarnessFacade, "run_debug", downstream)
    case = P2_CASES["run_debug"]
    path = _path(authorized_p2_space, case["path"])

    response = resolve(path).func(_request(path, case["payload"]), space_id=str(authorized_p2_space.id))

    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == expected_code
    assert sentinel not in str(response.data)


def test_p2_views_are_post_only_and_use_one_harness_permission():
    """No legacy permission, SDK verb, or alternate control path is attached."""
    assert P2_ACTION_RISK == {
        "start_debug_session": "L1",
        "run_debug": "L2",
        "get_debug_session": "L0",
        "control_debug_session": "L1",
    }
    for view in (start_debug_session, run_debug, get_debug_session, control_debug_session):
        assert view.cls.permission_classes == [HarnessPermission]
        assert set(view.cls.http_method_names) == {"options", "post"}
