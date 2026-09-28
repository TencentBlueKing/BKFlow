"""P0 Harness APIGW transport contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.apigw.serializers.harness.capabilities import (
    PluginSchemaSerializer,
    SearchCapabilitiesSerializer,
)
from bkflow.apigw.serializers.harness.workflow import (
    CreateDraftSerializer,
    ValidateWorkflowSerializer,
)
from bkflow.apigw.views.harness.capabilities import (
    get_plugin_schema,
    search_workflow_capabilities,
)
from bkflow.apigw.views.harness.common import envelope
from bkflow.apigw.views.harness.workflow import create_workflow_draft, validate_workflow
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    HarnessIdempotencyRecord,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.permissions import HarnessPermission
from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.facade import P0_TOOL_OPERATION_MAP, HarnessFacade
from bkflow.harness.services.resolver import CapabilityResolutionError
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.space.configs import (
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
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
ERROR_KEYS = {"category", "code", "path", "repairable", "retryable", "message", "suggested_action"}
SENTINEL = "credential://id/991-SENTINEL-provider-traceback-token"


class _FreshCatalogService:
    """A provider-I/O fixture: the Facade still constructs the real resolver."""

    def __init__(self, plugins, schemas, failure=None):
        self.plugins = plugins
        self.schemas = schemas
        self.failure = failure
        self.list_calls = 0

    def manifest_identity_exists(self, plugin_type, source_key, code):
        return any(
            (item["plugin_type"], item.get("source_key"), item["code"]) == (plugin_type, source_key, code)
            for item in self.plugins
        )

    def list_plugins(self, limit, offset, plugin_source=None, refresh=False, strict=False):
        self.list_calls += 1
        items = [dict(item) for item in self.plugins]
        return items[offset : offset + limit], len(items)

    def get_plugin_schema(
        self,
        code,
        version,
        plugin_type,
        source_key,
        refresh=False,
        exact_source=False,
        include_conversion_metadata=False,
    ):
        if self.failure:
            raise self.failure
        key = (plugin_type, source_key, code, version)
        schema = dict(self.schemas[key])
        if include_conversion_metadata:
            if plugin_type == "component":
                schema["conversion_metadata"] = {
                    "kind": "component",
                    "wrapper_code": code,
                    "wrapper_version": version,
                }
            elif plugin_type == "remote_plugin":
                schema["conversion_metadata"] = {
                    "kind": "remote_plugin",
                    "wrapper_code": "remote_plugin",
                    "wrapper_version": "1.0.0",
                    "remote_plugin_version": version,
                }
            else:
                schema["conversion_metadata"] = {
                    "kind": "uniform_api",
                    "wrapper_code": "uniform_api",
                    "wrapper_version": "1.0.0",
                    "source_key": source_key,
                    "plugin_id": code,
                    "plugin_version": version,
                    "url": "https://provider.example.com/{}".format(source_key or "legacy"),
                    "method": "POST",
                    "credential_key": "server-only-credential",
                }
        return schema


def _catalog_service(*definitions, failure=None):
    """Build source rows whose exact version/source identity is the only schema lookup key."""
    plugins = []
    schemas = {}
    for plugin_type, source_key, code, version, inputs in definitions:
        plugins.append(
            {
                "plugin_type": plugin_type,
                "source_key": source_key,
                "code": code,
                "version": version,
                "resolved_version": version,
                "name": code,
                "description": "governed {}".format(code),
            }
        )
        schemas[(plugin_type, source_key, code, version)] = {
            "resolved_version": version,
            "inputs": inputs,
            "outputs": [{"key": "result", "type": "string"}],
        }
    return _FreshCatalogService(plugins, schemas, failure=failure)


@pytest.fixture
def authorized_harness_space(db):
    """Create the complete, server-owned authorization binding for a real view call."""
    space = Space.objects.create(
        name="Harness facade transport space",
        app_code="trusted-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    configs = (
        (HarnessEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (SuperusersConfig.name, SpaceConfigValueType.JSON.value, "", ["trusted-user"]),
        (
            HarnessDeploymentConfig.name,
            SpaceConfigValueType.JSON.value,
            "",
            {
                "platform_key": "bkaidev",
                "allowed_scope_types": ["biz"],
                "scope_type": None,
                "scope_value": None,
                "target_environment": "stag",
                "risk_policy_version": "risk-2026.09",
                "mcp_contract_version": "1.0.0",
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


def _request_for(
    path,
    payload,
    correlation_id="gateway-trace",
    app_code="trusted-app",
    verified=True,
    username="trusted-user",
    authenticated=True,
):
    """Construct an actual DRF request with only gateway-owned identity attributes."""
    factory = APIRequestFactory()
    if isinstance(payload, bytes):
        request = factory.generic(
            "POST", path, payload, content_type="application/json", HTTP_X_REQUEST_ID=correlation_id
        )
    else:
        request = factory.post(path, payload, format="json", HTTP_X_REQUEST_ID=correlation_id)
    request.app = SimpleNamespace(bk_app_code=app_code, verified=verified)
    if authenticated:
        force_authenticate(request, user=SimpleNamespace(username=username, is_authenticated=True))
    return request


def _domain_envelope(correlation_id, *, ok=False, code=None, category=None):
    """Build the frozen downstream service result returned at a Task 5--7 boundary."""
    errors = []
    if code:
        errors = [
            {
                "category": category,
                "code": code,
                "path": "run_id",
                "repairable": False,
                "retryable": False,
                "message": "A safe domain error.",
                "suggested_action": "validate_workflow",
            }
        ]
    return {
        "ok": ok,
        "run_id": None,
        "revision_id": None,
        "plan_hash": None,
        "status": "VALIDATING" if ok else None,
        "summary": "A safe result.",
        "artifact_refs": [],
        "errors": errors,
        "next_actions": [] if ok else ["validate_workflow"],
        "correlation_id": correlation_id,
    }


def _assert_no_persisted_sentinel(sentinel):
    """Assert a rejected transport request never reaches any Harness durable record."""
    records = []
    for model in (HarnessRun, WorkflowPlanRevision, ValidationReport, HarnessIdempotencyRecord):
        for row in model.objects.all():
            records.append(str(row.__dict__))
    assert sentinel not in "\n".join(records)


def _assert_audit_record(record, *, tool, risk, result):
    """Assert the structured audit event contains only the fixed public metadata fields."""
    event = record.harness_audit
    assert set(event) == {
        "tool",
        "risk",
        "caller",
        "space",
        "run",
        "revision",
        "correlation",
        "result",
        "duration_ms",
    }
    assert event["tool"] == tool
    assert event["risk"] == risk
    assert event["caller"] == "trusted-user"
    assert event["space"] == 1
    assert event["correlation"] == "gateway-trace"
    assert event["result"] is result
    assert isinstance(event["duration_ms"], int)
    assert event["duration_ms"] >= 0
    for value in event.values():
        if isinstance(value, str):
            assert len(value) <= 128


def _context():
    return TrustedHarnessContext("platform", "app", "user", 1, "project", "1", "stag", "p0", "1.0.0", "trace")


@pytest.mark.parametrize(
    "serializer,payload",
    [
        (SearchCapabilitiesSerializer, {"query": "restart", "actor": "forged"}),
        (
            PluginSchemaSerializer,
            {"capability_ref": "cap_v1_x", "expected_schema_hash": "a" * 64, "token": "secret"},
        ),
        (
            ValidateWorkflowSerializer,
            {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "k", "space_id": 2},
        ),
        (
            CreateDraftSerializer,
            {
                "run_id": "00000000-0000-0000-0000-000000000000",
                "revision_id": "00000000-0000-0000-0000-000000000000",
                "plan_hash": "a" * 64,
                "idempotency_key": "k",
                "auto_release": True,
            },
        ),
    ],
)
def test_transport_rejects_unknown_authority_fields(serializer, payload):
    """Model input never supplies platform, identity, release or credential authority."""
    assert serializer(data=payload).is_valid() is False


def test_transport_envelope_has_exact_safe_shape():
    """DRF parse failures use the same frozen shape as domain errors."""
    result = envelope(_context(), None)
    assert set(result) == ENVELOPE_KEYS
    assert set(result["errors"][0]) == ERROR_KEYS
    assert "secret" not in str(result).lower()


@pytest.mark.parametrize(
    "mutation,request_kwargs,expected_code",
    [
        ("disabled", {}, "HARNESS_DISABLED"),
        (None, {"verified": False}, "HARNESS_APP_UNAUTHENTICATED"),
        (None, {"authenticated": False}, "HARNESS_USER_UNAUTHENTICATED"),
        (None, {"app_code": "wrong-app"}, "HARNESS_APP_SPACE_FORBIDDEN"),
        (None, {"username": "wrong-user"}, "HARNESS_USER_SPACE_FORBIDDEN"),
    ],
)
def test_real_route_permission_denials_return_frozen_envelope_and_audit(
    monkeypatch, caplog, authorized_harness_space, mutation, request_kwargs, expected_code
):
    """DRF permission rejection must not fall through to its default detail-only response."""
    if mutation == "disabled":
        config = SpaceConfig.objects.get(space_id=authorized_harness_space.id, name=HarnessEnabledConfig.name)
        config.text_value = "false"
        config.save(update_fields=["text_value"])
    downstream = Mock()
    monkeypatch.setattr("bkflow.harness.services.facade.CapabilityProjection.search", downstream)
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/search_workflow_capabilities/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"query": "restart"}, **request_kwargs), space_id=str(authorized_harness_space.id)
    )

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert set(response.data["errors"][0]) == ERROR_KEYS
    assert response.data["errors"][0]["category"] == "PERMISSION"
    assert response.data["errors"][0]["code"] == expected_code
    assert response.data["correlation_id"] == "gateway-trace"
    downstream.assert_not_called()
    assert caplog.records[-1].harness_audit["tool"] == "search_workflow_capabilities"
    assert caplog.records[-1].harness_audit["result"] is False


def test_exactly_four_post_views_use_only_harness_permission():
    """No legacy permission or fifth control operation is attached to the P0 endpoints."""
    views = [search_workflow_capabilities, get_plugin_schema, validate_workflow, create_workflow_draft]
    assert set(P0_TOOL_OPERATION_MAP) == {
        "search_workflow_capabilities",
        "get_plugin_schema",
        "validate_workflow",
        "create_workflow_draft",
    }
    for view in views:
        assert view.cls.permission_classes == [HarnessPermission]
        assert set(view.cls.http_method_names) == {"options", "post"}


@pytest.mark.parametrize(
    "path,tool",
    [
        ("/apigw/space/1/harness/search_workflow_capabilities/", "search_workflow_capabilities"),
        ("/apigw/space/1/harness/get_plugin_schema/", "get_plugin_schema"),
        ("/apigw/space/1/harness/validate_workflow/", "validate_workflow"),
        ("/apigw/space/1/harness/create_workflow_draft/", "create_workflow_draft"),
    ],
)
def test_harness_routes_resolve_only_to_the_four_prefixed_control_views(path, tool):
    """Task 9 can map these stable paths without exposing a fifth P0 operation."""
    match = resolve(path)
    assert match.func.cls.permission_classes == [HarnessPermission]
    assert tool in P0_TOOL_OPERATION_MAP


def test_real_search_view_wraps_task5_summary_in_the_frozen_envelope(monkeypatch, authorized_harness_space):
    """A real route must adapt a Task 5 list result without bypassing the Facade."""
    downstream = Mock(
        return_value={"capabilities": [{"code": "restart", "version": "2.0"}], "errors": [], "next_actions": []}
    )
    monkeypatch.setattr("bkflow.harness.services.facade.CapabilityProjection.search", downstream)
    path = "/apigw/space/{}/harness/search_workflow_capabilities/".format(authorized_harness_space.id)

    response = resolve(path).func(_request_for(path, {"query": "restart"}), space_id=str(authorized_harness_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is True
    assert response.data["correlation_id"] == "gateway-trace"
    downstream.assert_called_once()


@pytest.mark.django_db
def test_real_capability_search_route_preserves_task5_required_credentials_card(monkeypatch, authorized_harness_space):
    """A governed Task 5 card retains its fixed public credential-kind field."""
    from pipeline.component_framework.models import ComponentModel

    ComponentModel.objects.create(code="restart", version="1.0.0", name="ops-restart", status=True)
    component = Mock()
    component.desc = "restart a service"
    component.inputs_format.return_value = []
    component.outputs_format.return_value = []
    monkeypatch.setattr(
        "bkflow.plugin.services.plugin_schema_service.ComponentLibrary.get_component_class",
        Mock(return_value=component),
    )
    path = "/apigw/space/{}/harness/search_workflow_capabilities/".format(authorized_harness_space.id)

    response = resolve(path).func(_request_for(path, {"query": "restart"}), space_id=str(authorized_harness_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is True
    card = response.data["artifact_refs"][0]["payload"][0]
    assert card["required_credentials"] == []
    assert set(card) == {
        "capability_ref",
        "display_name",
        "summary",
        "plugin_type",
        "resolved_version",
        "schema_hash",
        "lifecycle",
        "risk_level",
        "side_effects",
        "required_credentials",
        "matched_terms",
        "score",
    }


def test_real_search_route_lifts_projection_ambiguity_into_the_frozen_error_contract(
    monkeypatch, authorized_harness_space
):
    """A projection ambiguity cannot be hidden in a successful artifact payload."""
    downstream = Mock(
        return_value={
            "capabilities": [{"code": "restart"}],
            "errors": [{"code": "AMBIGUOUS_CAPABILITY", "retryable": True}],
            "next_actions": [{"action": "clarify_capability"}],
        }
    )
    monkeypatch.setattr("bkflow.harness.services.facade.CapabilityProjection.search", downstream)
    path = "/apigw/space/{}/harness/search_workflow_capabilities/".format(authorized_harness_space.id)

    response = resolve(path).func(_request_for(path, {"query": "restart"}), space_id=str(authorized_harness_space.id))

    assert response.status_code == 200
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "AMBIGUOUS_CAPABILITY"
    assert response.data["errors"][0]["category"] == "AMBIGUOUS_CAPABILITY"
    assert response.data["next_actions"] == ["clarify_capability"]
    assert response.data["artifact_refs"][0]["payload"] == [{"code": "restart"}]


@pytest.mark.parametrize(
    "error,code,category",
    [
        (CapabilityResolutionError("CAPABILITY_NOT_FOUND"), "CAPABILITY_NOT_FOUND", "CAPABILITY_NOT_FOUND"),
        (CapabilityResolutionError("CAPABILITY_FORBIDDEN"), "CAPABILITY_FORBIDDEN", "PERMISSION"),
        (CapabilityResolutionError("SCHEMA_DRIFT"), "SCHEMA_DRIFT", "SCHEMA_DRIFT"),
        (CapabilityResolutionError("RETRYABLE_INFRA"), "RETRYABLE_INFRA", "RETRYABLE_INFRA"),
    ],
)
def test_real_schema_route_preserves_resolver_failure_semantics(
    monkeypatch, authorized_harness_space, error, code, category
):
    """A fresh resolver keeps deletion, access loss, drift and outage distinct."""
    service = _catalog_service(("uniform_api", "v4-source", "restart", "1.0", []))
    monkeypatch.setattr(HarnessFacade, "_service", lambda self, context: service)
    monkeypatch.setattr("bkflow.harness.services.facade.CapabilityResolver.resolve", Mock(side_effect=error))
    path = "/apigw/space/{}/harness/get_plugin_schema/".format(authorized_harness_space.id)
    capability_ref = encode_capability_ref("uniform_api", "v4-source", "restart", "1.0")

    response = resolve(path).func(
        _request_for(path, {"capability_ref": capability_ref, "expected_schema_hash": "a" * 64}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == code
    assert response.data["errors"][0]["category"] == category


def test_search_select_then_schema_preserves_legacy_and_v4_same_code_sources_exact(
    monkeypatch, authorized_harness_space
):
    """The selected opaque card fixes legacy None versus V4 source identities end to end."""
    catalog = [
        {
            "plugin_type": "uniform_api",
            "source_key": None,
            "code": "shared",
            "version": "1.0",
            "wrapper_version": "1.0.0",
            "name": "shared",
            "description": "legacy source",
        },
        {
            "plugin_type": "uniform_api",
            "source_key": "v4-source",
            "code": "shared",
            "version": "2.0",
            "wrapper_version": "1.0.0",
            "name": "shared",
            "description": "v4 source",
        },
    ]

    def list_uniform(self, keyword=None, plugin_source=None, refresh=False, strict=False):
        return [dict(item) for item in catalog]

    def fill_schema(self, plugin_info, strict=False, refresh=False):
        plugin_info["inputs"] = (
            [{"key": "legacy_input"}] if plugin_info.get("source_key") is None else [{"key": "v4_input"}]
        )
        plugin_info["outputs"] = [{"key": "result", "type": "string"}]
        plugin_info["_conversion_api_meta"] = {
            "url": "https://provider.example.com/{}".format(plugin_info.get("source_key") or "legacy"),
            "method": "POST",
            "credential_key": "server-only-credential",
        }

    monkeypatch.setattr(PluginSchemaService, "_list_component_plugins", lambda self, keyword=None: [])
    monkeypatch.setattr(PluginSchemaService, "_list_remote_plugins", lambda self, keyword=None: [])
    monkeypatch.setattr(PluginSchemaService, "_list_uniform_api_plugins", list_uniform)
    monkeypatch.setattr(PluginSchemaService, "_fill_schema_single", fill_schema)
    search_path = "/apigw/space/{}/harness/search_workflow_capabilities/".format(authorized_harness_space.id)
    path = "/apigw/space/{}/harness/get_plugin_schema/".format(authorized_harness_space.id)
    cards = (
        resolve(search_path)
        .func(_request_for(search_path, {"query": "shared"}), space_id=str(authorized_harness_space.id))
        .data["artifact_refs"][0]["payload"]
    )

    assert len(cards) == 2
    for card in cards:
        response = resolve(path).func(
            _request_for(
                path,
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            ),
            space_id=str(authorized_harness_space.id),
        )
        payload = response.data["artifact_refs"][0]["payload"]
        assert response.data["ok"] is True
        assert payload["capability_ref"] == card["capability_ref"]
        assert payload["resolved_version"] == card["resolved_version"]
        expected_inputs = [{"key": "legacy_input"}] if card["resolved_version"] == "1.0" else [{"key": "v4_input"}]
        assert payload["inputs"] == expected_inputs
        assert set(payload) == {
            "capability_ref",
            "plugin_type",
            "resolved_version",
            "schema_hash",
            "risk_level",
            "inputs",
            "outputs",
        }


@pytest.mark.parametrize(
    "path_suffix,payload,service_path,code,category",
    [
        (
            "validate_workflow",
            {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "validate-key"},
            "bkflow.harness.services.facade.WorkflowValidator.validate_workflow",
            "SCHEMA_DRIFT",
            "SCHEMA_DRIFT",
        ),
    ],
)
def test_real_views_preserve_task5_to_task7_domain_envelopes(
    monkeypatch, authorized_harness_space, path_suffix, payload, service_path, code, category
):
    """Real URL, permission and Facade dispatch preserve each governed service result."""
    downstream_result = _domain_envelope("gateway-trace", code=code, category=category)
    downstream = Mock(return_value=downstream_result)
    monkeypatch.setattr(service_path, downstream)
    path = "/apigw/space/{}/harness/{}/".format(authorized_harness_space.id, path_suffix)

    response = resolve(path).func(_request_for(path, payload), space_id=str(authorized_harness_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["correlation_id"] == "gateway-trace"
    assert set(response.data["errors"][0]) == ERROR_KEYS
    assert response.data["errors"][0]["category"] == category
    assert response.data["errors"][0]["code"] == code
    downstream.assert_called_once()


def test_real_draft_view_preserves_a_same_key_replay(monkeypatch, authorized_harness_space):
    """A repeated write result is returned unchanged through the actual route and Facade."""
    result = _domain_envelope("gateway-trace", ok=True)
    downstream = Mock(side_effect=[result, result])
    monkeypatch.setattr("bkflow.harness.services.facade.create_workflow_draft", downstream)
    path = "/apigw/space/{}/harness/create_workflow_draft/".format(authorized_harness_space.id)
    payload = {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "revision_id": "00000000-0000-0000-0000-000000000002",
        "plan_hash": "a" * 64,
        "idempotency_key": "same-key",
    }

    first = resolve(path).func(_request_for(path, payload), space_id=str(authorized_harness_space.id))
    replay = resolve(path).func(_request_for(path, payload), space_id=str(authorized_harness_space.id))

    assert first.status_code == replay.status_code == 200
    assert first.data == replay.data
    assert replay.data["ok"] is True
    assert set(replay.data) == ENVELOPE_KEYS
    assert downstream.call_count == 2
    assert downstream.call_args.args[0].space_id == authorized_harness_space.id
    assert downstream.call_args.args[0].platform_app == "trusted-app"


@pytest.mark.parametrize(
    "code,category",
    [
        ("VALIDATION_STALE", "SCHEMA_DRIFT"),
        ("IDEMPOTENCY_CONFLICT", "USER_INPUT"),
        ("CAPABILITY_FORBIDDEN", "PERMISSION"),
    ],
)
def test_real_draft_view_preserves_stale_conflict_and_cross_space_results(
    monkeypatch, authorized_harness_space, code, category
):
    """Task 7 error envelopes retain their semantics, including a cross-space run denial."""
    downstream = Mock(return_value=_domain_envelope("gateway-trace", code=code, category=category))
    monkeypatch.setattr("bkflow.harness.services.facade.create_workflow_draft", downstream)
    path = "/apigw/space/{}/harness/create_workflow_draft/".format(authorized_harness_space.id)
    payload = {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "revision_id": "00000000-0000-0000-0000-000000000002",
        "plan_hash": "a" * 64,
        "idempotency_key": "conflicting-key",
    }

    response = resolve(path).func(_request_for(path, payload), space_id=str(authorized_harness_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["correlation_id"] == "gateway-trace"
    assert set(response.data["errors"][0]) == ERROR_KEYS
    assert response.data["errors"][0]["category"] == category
    assert response.data["errors"][0]["code"] == code
    downstream.assert_called_once()


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "restart", "provider_detail": SENTINEL},
        {"query": "x" * 1000000},
        b'{"query":"\\ud800"}',
    ],
)
def test_rejected_transport_input_is_audited_redacted_and_never_calls_task5(
    monkeypatch, caplog, authorized_harness_space, payload
):
    """A body that violates the transport boundary cannot invoke or leak through Task 5."""
    downstream = Mock()
    monkeypatch.setattr("bkflow.harness.services.facade.CapabilityProjection.search", downstream)
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/search_workflow_capabilities/".format(authorized_harness_space.id)

    response = resolve(path).func(_request_for(path, payload), space_id=str(authorized_harness_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert set(response.data["errors"][0]) == ERROR_KEYS
    assert response.data["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert SENTINEL not in str(response.data)
    assert SENTINEL not in caplog.text
    downstream.assert_not_called()
    _assert_audit_record(caplog.records[-1], tool="search_workflow_capabilities", risk="L0", result=False)
    _assert_no_persisted_sentinel(SENTINEL)


@pytest.mark.parametrize(
    "value",
    [
        {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": 1}}}}}}}}},
        {"many": list(range(101))},
        {"large": "x" * 70000},
    ],
)
def test_workflow_serializer_rejects_unbounded_json_before_domain_parsing(value):
    """Nested, wide and canonical-byte-heavy workflow JSON is refused at the transport boundary."""
    serializer = ValidateWorkflowSerializer(
        data={"intent_spec": value, "a2flow": {}, "bindings": [], "idempotency_key": "bounded-key"}
    )

    assert serializer.is_valid() is False


def test_downstream_exception_is_a_safe_audited_retryable_envelope(monkeypatch, caplog, authorized_harness_space):
    """Provider traceback text must not escape an unexpected Task 6 service failure."""
    downstream = Mock(side_effect=RuntimeError(SENTINEL))
    monkeypatch.setattr("bkflow.harness.services.facade.WorkflowValidator.validate_workflow", downstream)
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/validate_workflow/".format(authorized_harness_space.id)
    payload = {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "provider-failure"}

    response = resolve(path).func(_request_for(path, payload), space_id=str(authorized_harness_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert set(response.data["errors"][0]) == ERROR_KEYS
    assert response.data["errors"][0]["category"] == "RETRYABLE_INFRA"
    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert SENTINEL not in str(response.data)
    assert SENTINEL not in caplog.text
    _assert_audit_record(caplog.records[-1], tool="validate_workflow", risk="L0", result=False)
    _assert_no_persisted_sentinel(SENTINEL)


def test_downstream_error_message_is_not_reflected_in_response_or_audit(monkeypatch, caplog, authorized_harness_space):
    """A compromised downstream message cannot disclose provider or credential material."""
    downstream_result = _domain_envelope("gateway-trace", code="SCHEMA_DRIFT", category="SCHEMA_DRIFT")
    downstream_result["errors"][0]["message"] = SENTINEL
    downstream = Mock(return_value=downstream_result)
    monkeypatch.setattr("bkflow.harness.services.facade.WorkflowValidator.validate_workflow", downstream)
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/validate_workflow/".format(authorized_harness_space.id)
    payload = {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "safe-message"}

    response = resolve(path).func(_request_for(path, payload), space_id=str(authorized_harness_space.id))

    assert response.status_code == 200
    assert response.data["errors"][0]["code"] == "SCHEMA_DRIFT"
    assert SENTINEL not in str(response.data)
    assert SENTINEL not in caplog.text
    _assert_audit_record(caplog.records[-1], tool="validate_workflow", risk="L0", result=False)
    _assert_no_persisted_sentinel(SENTINEL)


@pytest.mark.parametrize("field", ["code", "message", "path", "artifact_refs", "next_actions"])
def test_untrusted_domain_error_fields_never_escape_the_frozen_adapter(
    monkeypatch, caplog, authorized_harness_space, field
):
    """An unsafe code, coordinate, message, artifact or action is regenerated or discarded."""
    downstream_result = _domain_envelope("gateway-trace", code="SCHEMA_DRIFT", category="SCHEMA_DRIFT")
    if field == "artifact_refs":
        downstream_result[field] = [{"provider_detail": SENTINEL}]
    elif field == "next_actions":
        downstream_result[field] = [SENTINEL]
    else:
        downstream_result["errors"][0][field] = SENTINEL
    downstream = Mock(return_value=downstream_result)
    monkeypatch.setattr("bkflow.harness.services.facade.WorkflowValidator.validate_workflow", downstream)
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/validate_workflow/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "safe-error"}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    expected_code = "RETRYABLE_INFRA" if field == "code" else "SCHEMA_DRIFT"
    assert response.data["errors"][0]["code"] == expected_code
    assert SENTINEL not in str(response.data)
    assert SENTINEL not in caplog.text
    _assert_no_persisted_sentinel(SENTINEL)


@pytest.mark.parametrize("ok", [True, False])
def test_artifact_mapping_keys_are_recursively_redacted_on_success_and_failure(
    monkeypatch, caplog, authorized_harness_space, ok
):
    """A credential-like artifact key never survives either success or failure transport output."""
    result = _domain_envelope("gateway-trace", ok=ok, code=None if ok else "SCHEMA_DRIFT", category="SCHEMA_DRIFT")
    result["artifact_refs"] = [{SENTINEL: {"provider_traceback": "fixed"}}]
    downstream = Mock(return_value=result)
    monkeypatch.setattr("bkflow.harness.services.facade.WorkflowValidator.validate_workflow", downstream)
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/validate_workflow/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "safe-artifact"}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert SENTINEL not in str(response.data)
    assert SENTINEL not in caplog.text
    _assert_no_persisted_sentinel(SENTINEL)


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "authorization=C2-ARTIFACT-SENTINEL",
        "api_token: C2-ARTIFACT-SENTINEL",
        "X_BKAPI_AUTHORIZATION C2-ARTIFACT-SENTINEL",
    ],
)
def test_artifact_safe_keys_cannot_carry_secret_shaped_assignment_values(
    monkeypatch, caplog, authorized_harness_space, unsafe_value
):
    """The transport applies shared value safety even when every artifact key is innocuous."""
    result = _domain_envelope("gateway-trace", ok=True)
    result["artifact_refs"] = [{"type": "evidence", "payload": {"description": unsafe_value}}]
    monkeypatch.setattr("bkflow.harness.services.facade.WorkflowValidator.validate_workflow", Mock(return_value=result))
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/validate_workflow/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "safe-artifact"}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert "C2-ARTIFACT-SENTINEL" not in str(response.data)
    assert "C2-ARTIFACT-SENTINEL" not in caplog.text


def test_artifact_required_credentials_only_allows_public_credential_kind_strings(
    monkeypatch, authorized_harness_space
):
    """The fixed Task 5 credential-kind list is the sole credential-named artifact exemption."""
    result = _domain_envelope("gateway-trace", ok=True)
    result["artifact_refs"] = [
        {"type": "capability_search", "payload": [{"required_credentials": ["oauth2", "service_account"]}]}
    ]
    monkeypatch.setattr("bkflow.harness.services.facade.WorkflowValidator.validate_workflow", Mock(return_value=result))
    path = "/apigw/space/{}/harness/validate_workflow/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "safe-kinds"}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert response.data["ok"] is True
    assert response.data["artifact_refs"] == result["artifact_refs"]


@pytest.mark.parametrize("required_credentials", [[SENTINEL], ["access_token"], [{"kind": "oauth2"}]])
def test_artifact_required_credentials_rejects_secret_or_non_list_kind_values(
    monkeypatch, caplog, authorized_harness_space, required_credentials
):
    """The public credential-kind exception cannot carry secrets or arbitrary nested values."""
    result = _domain_envelope("gateway-trace", ok=True)
    result["artifact_refs"] = [
        {"type": "capability_search", "payload": [{"required_credentials": required_credentials}]}
    ]
    monkeypatch.setattr("bkflow.harness.services.facade.WorkflowValidator.validate_workflow", Mock(return_value=result))
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/validate_workflow/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "unsafe-kinds"}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert SENTINEL not in str(response.data)
    assert SENTINEL not in caplog.text
    _assert_no_persisted_sentinel(SENTINEL)


@pytest.mark.parametrize("hostile_key", ["credential_id", "token", "secret", "traceback", "provider_detail"])
def test_artifact_hostile_credential_or_provider_detail_keys_are_rejected(
    monkeypatch, authorized_harness_space, hostile_key
):
    """No generic credential, token, traceback or provider-detail key becomes an artifact allowlist."""
    result = _domain_envelope("gateway-trace", ok=True)
    result["artifact_refs"] = [{"type": "capability_search", "payload": [{hostile_key: "opaque"}]}]
    monkeypatch.setattr("bkflow.harness.services.facade.WorkflowValidator.validate_workflow", Mock(return_value=result))
    path = "/apigw/space/{}/harness/validate_workflow/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "unsafe-key"}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"


def test_schema_conversion_credentials_are_never_exposed_by_the_read_facade(monkeypatch, authorized_harness_space):
    """Harness schema reads return public schema facts, never server-only converter credential metadata."""
    service = _catalog_service(("uniform_api", "v4-source", "restart", "1.0", [{"key": "target"}]))
    monkeypatch.setattr(HarnessFacade, "_service", lambda self, context: service)
    path = "/apigw/space/{}/harness/get_plugin_schema/".format(authorized_harness_space.id)
    capability_ref = encode_capability_ref("uniform_api", "v4-source", "restart", "1.0")
    expected_hash = schema_hash({"inputs": [{"key": "target"}], "outputs": [{"key": "result", "type": "string"}]})

    response = resolve(path).func(
        _request_for(path, {"capability_ref": capability_ref, "expected_schema_hash": expected_hash}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert SENTINEL not in str(response.data)
    assert "conversion_metadata" not in str(response.data)
    assert "credential_key" not in str(response.data)
    assert response.data["artifact_refs"][0]["payload"]["schema_hash"] == expected_hash


def test_schema_transport_rejects_raw_or_mixed_identity_without_calling_the_catalog(
    monkeypatch, authorized_harness_space
):
    """The public Schema contract consumes a search card, never model-supplied identity fields."""
    service = _catalog_service(("component", None, "restart", "1.0", []))
    monkeypatch.setattr(HarnessFacade, "_service", lambda self, context: service)
    path = "/apigw/space/{}/harness/get_plugin_schema/".format(authorized_harness_space.id)
    capability_ref = encode_capability_ref("component", None, "restart", "1.0")

    response = resolve(path).func(
        _request_for(
            path,
            {
                "capability_ref": capability_ref,
                "expected_schema_hash": "a" * 64,
                "code": "restart",
                "source_key": "forged",
            },
        ),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert response.data["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert service.list_calls == 0


@pytest.mark.parametrize(
    "catalog,capability_ref,expected_hash,code",
    [
        (
            _catalog_service(("component", None, "restart", "1.0", [])),
            encode_capability_ref("component", None, "restart", "1.0")[:-1] + "A",
            "a" * 64,
            "CAPABILITY_NOT_FOUND",
        ),
        (
            _catalog_service(("component", None, "restart", "1.0", [])),
            encode_capability_ref("component", None, "restart", "1.0"),
            "0" * 64,
            "SCHEMA_DRIFT",
        ),
        (
            _catalog_service(),
            encode_capability_ref("component", None, "restart", "1.0"),
            "a" * 64,
            "CAPABILITY_FORBIDDEN",
        ),
    ],
)
def test_schema_route_fresh_resolver_rejects_tamper_hash_drift_and_revoked_catalog(
    monkeypatch, authorized_harness_space, catalog, capability_ref, expected_hash, code
):
    """Schema reads re-resolve the selected card rather than trusting agent-held identity state."""
    monkeypatch.setattr(HarnessFacade, "_service", lambda self, context: catalog)
    path = "/apigw/space/{}/harness/get_plugin_schema/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"capability_ref": capability_ref, "expected_schema_hash": expected_hash}),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == code
    assert "restart" not in str(response.data["artifact_refs"])


def test_untrusted_correlation_header_is_replaced_before_the_envelope_or_audit(authorized_harness_space, caplog):
    """Gateway correlation input is opaque, bounded metadata and cannot carry a provider secret."""
    caplog.set_level("INFO", logger="bkflow.harness")
    path = "/apigw/space/{}/harness/search_workflow_capabilities/".format(authorized_harness_space.id)

    response = resolve(path).func(
        _request_for(path, {"query": "restart", "forged": SENTINEL}, correlation_id=SENTINEL),
        space_id=str(authorized_harness_space.id),
    )

    assert response.status_code == 200
    assert response.data["correlation_id"] != SENTINEL
    assert SENTINEL not in caplog.text
