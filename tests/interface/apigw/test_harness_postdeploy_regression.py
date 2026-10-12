"""Real P0 transport regressions: public HTTP inputs, repair guidance and stop semantics."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from django.urls import resolve
from pipeline.component_framework.models import ComponentModel
from pipeline.core.data.base import DataObject

from bkflow.harness.models import (
    HarnessIdempotencyRecord,
    HarnessRun,
    WorkflowPlanRevision,
)
from bkflow.pipeline_plugins.components.collections.http.v1_0 import (
    HttpComponent,
    HttpRequestService,
)
from bkflow.pipeline_plugins.components.collections.pause.legacy import PauseComponent
from bkflow.template.models import Template, TemplateSnapshot
from tests.interface.apigw.test_harness_p0 import (
    _assert_no_persisted_sentinel,
    _context,
    _domain_envelope,
    _request_for,
)
from tests.interface.apigw.test_harness_p0 import (
    authorized_harness_space as _authorized_harness_space,
)

authorized_harness_space = _authorized_harness_space


@pytest.fixture
def harness_call(authorized_harness_space):
    def call(tool, payload):
        path = "/apigw/space/{}/harness/{}/".format(authorized_harness_space.id, tool)
        return resolve(path).func(_request_for(path, payload), space_id=str(authorized_harness_space.id)).data

    return call


def request_for_component(monkeypatch, call, component, inputs):
    ComponentModel.objects.create(code=component.code, version=component.version, name="local-only", status=True)
    monkeypatch.setattr(
        "bkflow.plugin.services.plugin_schema_service.ComponentLibrary.get_component_class",
        lambda code, version: component,
    )
    found = call("search_workflow_capabilities", {"query": component.code})
    assert found["ok"], found
    card = found["artifact_refs"][0]["payload"][0]
    return {
        "intent_spec": {"goal": "local unpublished draft only"},
        "a2flow": {
            "version": "2.0",
            "name": "regression",
            "nodes": [{"id": "n1", "name": "local step", "inputs": inputs, "next": "end"}],
        },
        "bindings": [
            {
                "node_id": "n1",
                "capability_ref": card["capability_ref"],
                "schema_hash": card["schema_hash"],
                "credential_ref": None,
            }
        ],
        "idempotency_key": "validate-regression",
    }


def http_inputs(headers):
    return {
        "bk_http_request_method": "GET",
        "bk_http_request_url": "https://example.invalid/local-only",
        "bk_http_request_header": headers,
        "bk_http_request_body": "",
        "bk_http_timeout": 5,
        "bk_http_success_exp": "resp.status_code == 200",
    }


@pytest.mark.parametrize("timeout,expected_timeout", [(1, 1), (0, 60), (60, 60)])
def test_http_schema_to_draft_to_runtime_preserves_timeout(
    monkeypatch, harness_call, settings, timeout, expected_timeout
):
    """Schema 生成的草稿必须能直接交给真实插件，并保留超时与零值语义。"""
    settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = False
    inputs = http_inputs([{"name": "X-Test-Case", "value": "synthetic"}])
    inputs.update(bk_http_timeout=timeout, bk_http_success_exp="resp.result == True")
    request = request_for_component(monkeypatch, harness_call, HttpComponent, inputs)
    binding = request["bindings"][0]
    schema = harness_call(
        "get_plugin_schema",
        {"capability_ref": binding["capability_ref"], "expected_schema_hash": binding["schema_hash"]},
    )
    assert schema["ok"], schema
    accepted = harness_call("validate_workflow", request)
    assert accepted["ok"], accepted
    payload = {key: accepted[key] for key in ("run_id", "revision_id", "plan_hash")}
    drafted = harness_call("create_workflow_draft", dict(payload, idempotency_key="http-runtime-draft"))
    assert drafted["ok"], drafted
    tree = Template.objects.get().pipeline_tree
    values = next(iter(tree["activities"].values()))["component"]["data"]
    assert values["bk_http_timeout"]["value"] == timeout
    assert "bk_http_request_timeout" not in values
    data = DataObject(inputs={key: item["value"] for key, item in values.items()})
    response = MagicMock(status_code=200)
    response.json.return_value = {"result": True}
    send = MagicMock(return_value=response)
    monkeypatch.setattr("bkflow.pipeline_plugins.components.collections.http.v1_0.request", send)
    service = HttpComponent({}).service()
    service.logger = MagicMock()
    assert service.plugin_schedule(data, DataObject(inputs={})) is True
    assert data.outputs.status_code == 200
    assert data.outputs.data == {"result": True}
    send.assert_called_once_with(
        method="GET",
        url="https://example.invalid/local-only",
        verify=False,
        timeout=expected_timeout,
        headers={"X-Test-Case": "synthetic"},
    )


def test_http_legacy_schema_requires_revalidation_and_updates_same_draft(monkeypatch, harness_call):
    """旧错误字段的草稿不能绕过 Schema 漂移检查，可经新 Revision 原位修复。"""
    current_format = HttpRequestService.inputs_format

    def legacy_format(service):
        fields = current_format(service)
        for field in fields:
            if field.key == "bk_http_timeout":
                field.key = "bk_http_request_timeout"
        return fields

    monkeypatch.setattr(HttpRequestService, "inputs_format", legacy_format)
    inputs = http_inputs([])
    inputs["bk_http_request_timeout"] = inputs.pop("bk_http_timeout")
    request = request_for_component(monkeypatch, harness_call, HttpComponent, inputs)
    accepted = harness_call("validate_workflow", request)
    assert accepted["ok"], accepted
    payload = {key: accepted[key] for key in ("run_id", "revision_id", "plan_hash")}
    created = harness_call("create_workflow_draft", dict(payload, idempotency_key="legacy-http-draft"))
    assert created["ok"], created
    original_tree = deepcopy(Template.objects.get().pipeline_tree)

    monkeypatch.setattr(HttpRequestService, "inputs_format", current_format)
    stale = harness_call("create_workflow_draft", dict(payload, idempotency_key="legacy-http-new-write"))
    assert stale["ok"] is False
    assert stale["errors"][0]["code"] == "VALIDATION_STALE"
    assert Template.objects.get().pipeline_tree == original_tree
    old_binding = request["bindings"][0]
    drift = harness_call(
        "get_plugin_schema",
        {"capability_ref": old_binding["capability_ref"], "expected_schema_hash": old_binding["schema_hash"]},
    )
    assert drift["ok"] is False
    assert drift["errors"][0]["code"] == "SCHEMA_DRIFT"
    card = harness_call("search_workflow_capabilities", {"query": HttpComponent.code})["artifact_refs"][0]["payload"][0]
    assert card["schema_hash"] != old_binding["schema_hash"]
    old_binding["schema_hash"] = card["schema_hash"]
    request.update(run_id=accepted["run_id"], idempotency_key="reject-legacy-http-input")
    rejected = harness_call("validate_workflow", request)
    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert Template.objects.get().pipeline_tree == original_tree
    inputs["bk_http_timeout"] = inputs.pop("bk_http_request_timeout")
    request["idempotency_key"] = "repair-http-input"
    repaired = harness_call("validate_workflow", request)
    assert repaired["ok"], repaired
    payload = {key: repaired[key] for key in ("run_id", "revision_id", "plan_hash")}
    updated = harness_call("create_workflow_draft", dict(payload, idempotency_key="repair-http-draft"))
    assert updated["ok"], updated
    assert updated["artifact_refs"][0]["template_id"] == created["artifact_refs"][0]["template_id"]
    assert Template.objects.count() == 1
    assert TemplateSnapshot.objects.filter(draft=False).count() == 0
    values = next(iter(Template.objects.get().pipeline_tree["activities"].values()))["component"]["data"]
    assert values["bk_http_timeout"]["value"] == 5
    assert "bk_http_request_timeout" not in values


@pytest.mark.parametrize("wire_key", ["inputs", "data"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_public_http_headers_survive_validation_draft_and_replay(monkeypatch, harness_call, wire_key, wrapped):
    rows = [{"name": "Content-Type", "value": "application/json"}, {"name": "X-Test-Case", "value": "synthetic"}]
    headers = {"hook": False, "value": rows} if wrapped else rows
    request = request_for_component(monkeypatch, harness_call, HttpComponent, http_inputs(headers))
    node = request["a2flow"]["nodes"][0]
    node[wire_key] = node.pop("inputs")
    accepted = harness_call("validate_workflow", request)
    assert accepted["ok"], accepted
    assert harness_call("validate_workflow", request) == accepted
    payload = {key: accepted[key] for key in ("run_id", "revision_id", "plan_hash")}
    payload["idempotency_key"] = "draft-regression"
    drafted = harness_call("create_workflow_draft", payload)
    assert drafted["ok"], drafted
    assert drafted["next_actions"] == []
    assert harness_call("create_workflow_draft", payload) == drafted
    tree = Template.objects.get().pipeline_tree
    actual = next(iter(tree["activities"].values()))["component"]["data"]["bk_http_request_header"]
    assert actual["value"] == rows
    assert TemplateSnapshot.objects.get().draft is True


@pytest.mark.parametrize(
    "headers",
    [
        [{"name": name, "value": "OPAQUE_HEADER_SENTINEL"}]
        for name in (
            "Authorization",
            "Proxy-Authorization",
            "Cookie",
            "Set-Cookie",
            "X-Bkapi-Authorization",
            "X-API-Key",
            "X_Custom_Credential",
            "X-Unknown",
        )
    ]
    + [
        [{"name": "X-Test-Case", "value": "Bearer OPAQUE_HEADER_SENTINEL"}],
        [{"name": "X-Test-Case", "value": "ok\r\nAuthorization: OPAQUE_HEADER_SENTINEL"}],
        [{"name": "X-Test-Case", "value": "${OPAQUE_HEADER_SENTINEL}"}],
        [{"name": "X-Test-Case", "value": "public", "extra": "OPAQUE_HEADER_SENTINEL"}],
        {"hook": True, "value": "${OPAQUE_HEADER_SENTINEL}"},
        {"hook": False, "value": [{"name": "Cookie", "value": "OPAQUE_HEADER_SENTINEL"}]},
    ],
)
def test_unsafe_http_headers_never_persist_or_echo(monkeypatch, harness_call, headers):
    request = request_for_component(monkeypatch, harness_call, HttpComponent, http_inputs(headers))
    result = harness_call("validate_workflow", request)
    assert result["ok"] is False
    assert "OPAQUE_HEADER_SENTINEL" not in str(result)
    assert not WorkflowPlanRevision.objects.exists()
    assert not HarnessIdempotencyRecord.objects.exists()
    _assert_no_persisted_sentinel("OPAQUE_HEADER_SENTINEL")


@pytest.mark.parametrize("location", ["intent", "root", "other_plugin", "nested"])
def test_header_exception_cannot_escape_exact_http_input(monkeypatch, harness_call, location):
    rows = [{"name": "X-Test-Case", "value": "public"}]
    request = request_for_component(monkeypatch, harness_call, PauseComponent, {"description": "safe"})
    target = {
        "intent": request["intent_spec"],
        "root": request["a2flow"],
        "other_plugin": request["a2flow"]["nodes"][0]["inputs"],
    }.get(location)
    if location == "nested":
        target = request["a2flow"]["nodes"][0]["inputs"].setdefault("nested", {})
    target["bk_http_request_header"] = rows
    result = harness_call("validate_workflow", request)
    assert result["ok"] is False
    assert not WorkflowPlanRevision.objects.exists()


@pytest.mark.parametrize(
    "strategy,code",
    [
        ({"auto_retry": {"enable": True}, "timeout_config": {"enable": True}}, "FAILURE_STRATEGY_CONFLICT"),
        ({"auto_retry": {"enable": True}, "retryable": True}, "FAILURE_STRATEGY_INVALID_COMBO"),
    ],
)
def test_failure_strategy_has_actionable_allowlisted_guidance(monkeypatch, harness_call, strategy, code):
    request = request_for_component(monkeypatch, harness_call, PauseComponent, {"description": "safe"})
    request["a2flow"]["nodes"][0]["failure_strategy"] = strategy
    result = harness_call("validate_workflow", request)
    assert result["ok"] is False
    error = result["errors"][0]
    assert error["code"] == code
    assert "auto_retry" in error["message"]
    assert error["path"] == "nodes.n1.failure_strategy"
    assert error["suggested_action"] == "repair_a2flow"
    assert error["retryable"] is False


def test_draft_subprocess_explains_rule_without_publishing(monkeypatch, harness_call):
    request = request_for_component(monkeypatch, harness_call, PauseComponent, {"description": "safe"})
    accepted = harness_call("validate_workflow", request)
    assert accepted["ok"], accepted
    draft = {key: accepted[key] for key in ("run_id", "revision_id", "plan_hash")}
    draft["idempotency_key"] = "draft-child"
    result = harness_call("create_workflow_draft", draft)
    assert result["ok"], result
    parent = deepcopy(request)
    parent["idempotency_key"] = "validate-parent"
    parent["bindings"] = []
    parent["a2flow"]["nodes"] = [
        {"id": "child", "type": "SubProcess", "template_id": result["artifact_refs"][0]["template_id"], "next": "end"}
    ]
    rejected = harness_call("validate_workflow", parent)
    assert rejected["ok"] is False
    error = rejected["errors"][0]
    assert error["code"] == "SUBPROCESS_DRAFT_NOT_ALLOWED"
    assert "published" in error["message"]
    assert error["suggested_action"] == "repair_a2flow"
    assert error["path"] == "nodes.child.template_id"
    assert TemplateSnapshot.objects.get().draft is True


def test_draft_success_and_replay_stop_the_p0_agent_loop(monkeypatch, harness_call):
    request = request_for_component(monkeypatch, harness_call, PauseComponent, {"description": "safe"})
    accepted = harness_call("validate_workflow", request)
    assert accepted["ok"], accepted
    payload = {key: accepted[key] for key in ("run_id", "revision_id", "plan_hash")}
    payload["idempotency_key"] = "stop-draft"
    drafted = harness_call("create_workflow_draft", payload)
    assert drafted["ok"], drafted
    assert drafted["next_actions"] == []
    assert harness_call("create_workflow_draft", payload)["next_actions"] == []


def test_legacy_draft_replay_is_projected_as_stop_without_rewriting_snapshot():
    from bkflow.apigw.views.harness.common import _safe_domain_result

    persisted = _domain_envelope("trace", ok=True)
    persisted.update(status="DRAFT_READY", next_actions=["create_workflow_draft"])
    original = deepcopy(persisted)
    result = _safe_domain_result(_context(), persisted, "create_workflow_draft")
    assert result["next_actions"] == []
    assert persisted == original


@pytest.mark.parametrize("value", ["prefix=${missing}", "${missing}"])
def test_hook_reference_guidance_does_not_echo_expression(monkeypatch, harness_call, value):
    request = request_for_component(
        monkeypatch, harness_call, PauseComponent, {"description": {"hook": True, "value": value}}
    )
    result = harness_call("validate_workflow", request)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "HOOK_REFERENCE_INVALID"
    assert result["errors"][0]["path"] == "nodes.n1.inputs.description.value"
    assert "declared variable" in result["errors"][0]["message"]
    assert value not in str(result)


def test_revalidated_revision_updates_same_managed_draft_with_complete_layout(monkeypatch, harness_call):
    from bkflow.harness.services.canonical import sha256_json

    request = request_for_component(monkeypatch, harness_call, PauseComponent, {"description": "safe"})
    accepted = harness_call("validate_workflow", request)
    assert accepted["ok"], accepted
    draft = {key: accepted[key] for key in ("run_id", "revision_id", "plan_hash")}
    draft["idempotency_key"] = "create-first-draft"
    created = harness_call("create_workflow_draft", draft)
    assert created["ok"], created
    request.update(run_id=accepted["run_id"], idempotency_key="validate-revision-two")
    request["a2flow"]["nodes"][0]["next"] = "n2"
    request["a2flow"]["nodes"].append({"id": "n2", "name": "second", "inputs": {"description": "safe"}, "next": "end"})
    request["bindings"].append(dict(request["bindings"][0], node_id="n2"))
    accepted = harness_call("validate_workflow", request)
    assert accepted["ok"], accepted
    draft = {key: accepted[key] for key in ("run_id", "revision_id", "plan_hash")}
    draft["idempotency_key"] = "update-managed-draft"
    updated = harness_call("create_workflow_draft", draft)
    assert updated["ok"], updated
    assert updated["artifact_refs"][0]["template_id"] == created["artifact_refs"][0]["template_id"]
    template = Template.objects.get()
    tree = template.pipeline_tree
    assert len(tree["location"]) == 4
    assert len(tree["line"]) == 3
    assert sha256_json(tree) == accepted["artifact_refs"][0]["pipeline_tree_hash"]
    assert sha256_json(tree) == updated["artifact_refs"][0]["pipeline_tree_hash"]
    assert updated["next_actions"] == []


def test_invented_run_reference_stops_without_creating_artifacts(monkeypatch, harness_call):
    """模型虚构 Run 时安全拒绝，不应将其误导为换插件重试或隐式创建新 Run。"""
    request = request_for_component(monkeypatch, harness_call, PauseComponent, {"description": "safe"})
    request["run_id"] = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    response = harness_call("validate_workflow", request)
    assert response["ok"] is False
    error = response["errors"][0]
    assert (error["code"], error["category"], error["path"]) == ("CAPABILITY_FORBIDDEN", "PERMISSION", "run_id")
    assert error["repairable"] is error["retryable"] is False
    assert "run reference" in error["message"]
    assert "Stop tool calls" in error["message"]
    assert error["suggested_action"] == "contact_space_administrator"
    assert response["next_actions"] == []
    assert "denied" in response["summary"]
    assert response["run_id"] is response["revision_id"] is response["plan_hash"] is None
    assert response["artifact_refs"] == []
    assert request["run_id"] not in str(response)
    for model in (HarnessRun, WorkflowPlanRevision, HarnessIdempotencyRecord, Template):
        assert model.objects.count() == 0


@pytest.mark.parametrize("code", ["CAPABILITY_FORBIDDEN", "TRUSTED_CONTEXT_STALE", "HARNESS_ACCESS_DENIED"])
def test_permission_projection_cannot_restore_automatic_remediation_from_old_result(code):
    """最终响应须关闭旧持久化结果或下游返回附带的自动恢复建议。"""
    from bkflow.apigw.views.harness.common import _safe_domain_result

    persisted = _domain_envelope("trace", code=code, category="PERMISSION")
    persisted["errors"][0]["path"] = "run_id"
    persisted["next_actions"] = ["search_workflow_capabilities", "obtain_approval"]
    original = deepcopy(persisted)
    response = _safe_domain_result(_context(), persisted, "validate_workflow")
    assert response["next_actions"] == []
    assert "denied" in response["summary"]
    assert persisted == original


def test_public_header_allowance_does_not_relax_generic_json_safety():
    from bkflow.harness.safety import is_bounded_non_secret_json

    value = {"nodes": [{"inputs": {"bk_http_request_header": [{"name": "Accept", "value": "application/json"}]}}]}
    assert is_bounded_non_secret_json(value) is False
    assert is_bounded_non_secret_json(value, allow_public_http_headers=True) is True
    value["nodes"][0]["inputs"]["bk_http_request_header"].append({"name": "Cookie", "value": "opaque"})
    assert is_bounded_non_secret_json(value, allow_public_http_headers=True) is False


@pytest.mark.parametrize("rule", ["FAILURE_STRATEGY_CONFLICT", "FAILURE_STRATEGY_INVALID_COMBO", "UNKNOWN_RULE"])
def test_conversion_guidance_never_uses_raw_converter_message(rule):
    from bkflow.harness.services.validator import WorkflowValidator
    from bkflow.pipeline_converter.exceptions import A2FlowConvertError

    error = A2FlowConvertError(
        rule,
        "UNTRUSTED_DETAIL",
        node_id="n1",
        field="failure_strategy",
        hint="UNTRUSTED_DETAIL",
        value="UNTRUSTED_DETAIL",
    )
    result = WorkflowValidator._conversion_failure(error).as_error()
    assert "UNTRUSTED_DETAIL" not in str(result)
    assert result["code"] == (rule if rule != "UNKNOWN_RULE" else "A2FLOW_CONVERSION_ERROR")
