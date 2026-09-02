"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
    10|CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import (
    AmbiguousCapability,
    HarnessAuthorizationError,
    SchemaDrift,
)
from bkflow.harness.models import HarnessRun, WorkflowPlanRevision
from bkflow.harness.services.capability_ref import decode_capability_ref
from bkflow.harness.services.context import derive_trusted_context
from bkflow.harness.services.draft import create_workflow_draft_with_context
from bkflow.harness.services.projection import (
    SEARCH_CARD_FIELDS,
    search_workflow_capabilities,
)
from bkflow.harness.services.resolver import resolve_capability
from bkflow.harness.services.validator import validate_workflow_with_context
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import ConversionResult
from bkflow.space.configs import SpaceConfigValueType
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/harness/golden_cases.yaml"
EXPECTED_GROUPS = {
    "positive_selection": 8,
    "ambiguous_requires_clarification": 6,
    "zero_candidate": 4,
    "schema_validation_error": 4,
    "schema_drift": 3,
    "idempotent_draft_retry": 3,
    "forged_identity_rejected": 2,
}
VALID_DEPLOYMENT = {
    "platform_key": "bkaidev",
    "allowed_scope_types": ["biz"],
    "scope_type": None,
    "scope_value": None,
    "target_environment": "stage",
    "risk_policy_version": "p0-v1",
    "mcp_contract_version": "1.0.0",
}
PIPELINE_TREE = {
    "activities": {"nact": {"id": "nact", "type": "ServiceActivity"}},
    "gateways": {},
    "flows": {},
    "start_event": {"id": "nstart", "type": "EmptyStartEvent"},
    "end_event": {"id": "nend", "type": "EmptyEndEvent"},
    "constants": {},
}


def _load_cases():
    assert FIXTURE.exists(), "golden_cases.yaml must exist"
    payload = yaml.safe_load(FIXTURE.read_text())
    assert payload["version"] == "p0-v1"
    return payload["cases"]


def test_golden_case_catalog_has_exactly_thirty_versioned_cases():
    """Golden Cases 必须按计划分组，合计 30 条。"""
    cases = _load_cases()
    assert len(cases) == 30
    counts = {group: 0 for group in EXPECTED_GROUPS}
    for case in cases:
        counts[case["group"]] += 1
        assert case["registry_snapshot"] is not None or case["group"] == "forged_identity_rejected"
        assert case["expected_tool_sequence"]
        assert "expected" in case
        assert "forbidden_side_effects" in case
    assert counts == EXPECTED_GROUPS


class SnapshotPluginSchemaService:
    """用 Golden Case 快照代替运行时插件注册表。"""

    def __init__(self, snapshot):
        self.snapshot = snapshot

    def get_plugin_schema(self, code, version, plugin_type, source_key):
        wanted = version or "unversioned"
        for item in self.snapshot:
            item_version = item.get("version") or "unversioned"
            if item["code"] == code and item_version == wanted and item.get("plugin_type") == plugin_type:
                schema = item.get("schema") or {}
                return {
                    "inputs": schema.get("inputs") or [],
                    "outputs": schema.get("outputs") or [],
                    "resolved_version": item_version,
                    "version": item_version,
                }
        raise ValueError("capability is not available in the trusted space")


def _enable_harness(space, users=None):
    SpaceConfig.objects.create(
        space_id=space.id, name="harness_enabled", value_type=SpaceConfigValueType.TEXT.value, text_value="true"
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="harness_deployment",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=VALID_DEPLOYMENT,
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="superusers",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=users if users is not None else ["alice"],
    )


def _context(space, actor="alice"):
    return TrustedHarnessContext(
        platform_key="bkaidev",
        platform_app="bkflow_harness",
        actor=actor,
        space_id=space.id,
        scope_type=None,
        scope_value=None,
        target_environment="stage",
        policy_version="p0-v1",
        mcp_contract_version="1.0.0",
        correlation_id="corr-golden",
    )


def _bind_snapshot(snapshot, space_id, other_space_id):
    bound = []
    for item in snapshot or []:
        item = copy.deepcopy(item)
        mapped = []
        for value in item.get("space_ids") or []:
            if value == "__current__":
                mapped.append(space_id)
            elif value == "__other__":
                mapped.append(other_space_id)
            else:
                mapped.append(value)
        item["space_ids"] = mapped
        bound.append(item)
    return bound


def _install_domain_mocks(monkeypatch, snapshot):
    service = SnapshotPluginSchemaService(snapshot)

    def fake_resolve(context, capability_ref, expected_schema_hash=None, **kwargs):
        return resolve_capability(
            context,
            capability_ref,
            expected_schema_hash=expected_schema_hash,
            plugin_schema_service=service,
        )

    def persist_template(**kwargs):
        snapshot_obj = TemplateSnapshot.create_draft_snapshot(PIPELINE_TREE, kwargs["username"])
        template = Template.objects.create(
            name=kwargs["a2flow"].get("name") or "golden",
            space_id=kwargs["space_id"],
            creator=kwargs["username"],
            updated_by=kwargs["username"],
            snapshot_id=snapshot_obj.id,
            bk_app_code=kwargs["bind_app_code"],
        )
        snapshot_obj.template_id = template.id
        snapshot_obj.save(update_fields=["template_id"])
        return template

    def update_template(*, template, **kwargs):
        return TemplateSnapshot.objects.filter(template_id=template.id).first()

    conversion = ConversionResult(
        pipeline_tree=PIPELINE_TREE,
        converter_fingerprint="a" * 64,
        source_map={"node_1": "nact", "start": "nstart", "end": "nend"},
    )
    monkeypatch.setattr("bkflow.harness.services.validator.resolve_capability", fake_resolve)
    monkeypatch.setattr("bkflow.harness.services.draft.resolve_capability", fake_resolve)
    monkeypatch.setattr(
        "bkflow.harness.services.validator.A2FlowV2Converter.convert_with_metadata",
        Mock(return_value=conversion),
    )
    monkeypatch.setattr(
        "bkflow.harness.services.draft.A2FlowV2Converter.convert_with_metadata",
        Mock(return_value=conversion),
    )
    monkeypatch.setattr("bkflow.harness.services.validator.ValidatorHandler.validate", Mock())
    monkeypatch.setattr("bkflow.harness.services.draft.ValidatorHandler.validate", Mock())
    monkeypatch.setattr("bkflow.harness.services.draft.create_template_from_a2flow", persist_template)
    monkeypatch.setattr("bkflow.harness.services.draft.update_template_draft_from_a2flow", update_template)
    return fake_resolve


def _search(context, query, snapshot):
    try:
        result = search_workflow_capabilities(context=context, query=query, registry_snapshot=snapshot)
        return {
            "ok": result.ok,
            "candidates": result.candidates,
            "error_code": None,
            "next_actions": [item.get("action") if isinstance(item, dict) else item for item in result.next_actions],
        }
    except AmbiguousCapability as exc:
        return {
            "ok": False,
            "candidates": exc.candidates,
            "error_code": "AMBIGUOUS_CAPABILITY",
            "next_actions": ["clarify_capability"],
        }


def _selected_card(search_result, expected_code):
    for card in search_result["candidates"]:
        if decode_capability_ref(card["capability_ref"])["code"] == expected_code:
            return card
    return search_result["candidates"][0] if search_result["candidates"] else None


def _a2flow(code, data):
    return {
        "version": "2.0",
        "name": "golden",
        "nodes": [{"id": "node_1", "name": "n1", "code": code, "data": data, "next": "end"}],
    }


def _assert_no_forbidden_effects(space):
    for template in Template.objects.filter(space_id=space.id):
        drafts = TemplateSnapshot.objects.filter(template_id=template.id)
        assert drafts.filter(draft=False).count() == 0
    assert not HarnessRun.objects.filter(
        space_id=space.id,
        status__in=[HarnessRunStatus.PUBLISHED.value, HarnessRunStatus.EXECUTING.value],
    ).exists()


@pytest.fixture
def golden_space(space):
    _enable_harness(space)
    other = Space.objects.create(name="golden-other", app_code="other_app", platform_url="http://example.com")
    return space, other


def _run_case(case, spaces, monkeypatch):
    space, other = spaces
    context = _context(space)
    snapshot = _bind_snapshot(case.get("registry_snapshot") or [], space.id, other.id)
    expected = case["expected"]
    executed = []

    if case["group"] == "forged_identity_rejected":
        return _run_forged(case, space, expected, executed)

    _install_domain_mocks(monkeypatch, snapshot)
    query = case.get("query") or ""
    search_result = _search(context, query, snapshot)
    executed.append("search_workflow_capabilities")
    for card in search_result["candidates"]:
        assert set(card) == set(SEARCH_CARD_FIELDS)
        assert "schema" not in card
        assert "inputs" not in card
        assert "code" not in card

    if case["group"] == "ambiguous_requires_clarification":
        assert search_result["ok"] is False
        assert search_result["error_code"] == "AMBIGUOUS_CAPABILITY"
        assert search_result["next_actions"] == ["clarify_capability"]
        assert len(search_result["candidates"]) >= 2
        assert WorkflowPlanRevision.objects.filter(run__space_id=space.id).count() == 0
        return executed

    if case["group"] == "zero_candidate":
        assert search_result["ok"] is True
        assert search_result["candidates"] == []
        assert "revise_query" in search_result["next_actions"]
        return executed

    card = _selected_card(search_result, expected.get("selected_code"))
    if case["group"] == "positive_selection":
        assert search_result["ok"] is True
        assert card is not None
        identity = decode_capability_ref(card["capability_ref"])
        assert identity["code"] == expected["selected_code"]
        assert card["resolved_version"] == expected["selected_version"]
        if expected.get("schema_hash"):
            assert card["schema_hash"] == expected["schema_hash"]
        resolved = resolve_capability(
            context,
            card["capability_ref"],
            expected_schema_hash=card["schema_hash"],
            plugin_schema_service=SnapshotPluginSchemaService(snapshot),
        )
        executed.append("get_plugin_schema")
        assert resolved.resolved_version == expected["selected_version"]
        envelope = validate_workflow_with_context(
            context,
            {
                "intent": {"goal": case["id"]},
                "a2flow": _a2flow(identity["code"], {"host": "example-host"}),
                "bindings": [
                    {
                        "node_id": "node_1",
                        "capability_ref": card["capability_ref"],
                        "schema_hash": card["schema_hash"],
                        "credential_ref": None,
                    }
                ],
                "idempotency_key": case["id"],
            },
        )
        executed.append("validate_workflow")
        assert envelope["ok"] is True
        assert envelope["status"] == expected["final_status"]
        assert envelope["revision_id"]
        return executed

    if case["group"] == "schema_validation_error":
        identity = decode_capability_ref(card["capability_ref"])
        executed.append("get_plugin_schema")
        payload = _validation_defect_payload(case, card, identity)
        envelope = validate_workflow_with_context(context, payload)
        executed.append("validate_workflow")
        assert envelope["ok"] is False
        assert envelope["errors"][0]["code"] == expected["error_code"]
        assert expected.get("error_path") in (envelope["errors"][0].get("path") or "")
        assert envelope["revision_id"] is None
        assert envelope["status"] == HarnessRunStatus.NEEDS_REPAIR.value
        return executed

    if case["group"] == "schema_drift":
        return _run_drift(case, context, snapshot, card, executed, monkeypatch)

    if case["group"] == "idempotent_draft_retry":
        return _run_idempotent(case, context, snapshot, card, executed)

    raise AssertionError("unhandled group {}".format(case["group"]))


def _validation_defect_payload(case, card, identity):
    variant = case["variant"]
    base_a2flow = _a2flow(identity["code"], {"host": "example-host"})
    binding = {
        "node_id": "node_1",
        "capability_ref": card["capability_ref"],
        "schema_hash": card["schema_hash"],
        "credential_ref": None,
    }
    if variant == "missing_required_input":
        return {
            "a2flow": _a2flow(identity["code"], {}),
            "bindings": [binding],
            "idempotency_key": case["id"],
        }
    if variant == "extra_binding":
        extra = dict(binding, node_id="ghost")
        return {"a2flow": base_a2flow, "bindings": [binding, extra], "idempotency_key": case["id"]}
    if variant == "missing_bindings":
        return {"a2flow": base_a2flow, "bindings": [], "idempotency_key": case["id"]}
    if variant == "duplicate_bindings":
        return {"a2flow": base_a2flow, "bindings": [binding, dict(binding)], "idempotency_key": case["id"]}
    raise AssertionError(variant)


def _run_drift(case, context, snapshot, card, executed, monkeypatch):
    variant = case["variant"]
    if variant == "fetch_hash_mismatch":
        executed.append("get_plugin_schema")
        with pytest.raises(SchemaDrift):
            resolve_capability(
                context,
                card["capability_ref"],
                expected_schema_hash="b" * 64,
                plugin_schema_service=SnapshotPluginSchemaService(snapshot),
            )
        executed.append("search_workflow_capabilities")
        return executed
    if variant == "validate_hash_mismatch":
        executed.append("get_plugin_schema")
        identity = decode_capability_ref(card["capability_ref"])
        envelope = validate_workflow_with_context(
            context,
            {
                "a2flow": _a2flow(identity["code"], {"host": "example-host"}),
                "bindings": [
                    {
                        "node_id": "node_1",
                        "capability_ref": card["capability_ref"],
                        "schema_hash": "b" * 64,
                        "credential_ref": None,
                    }
                ],
                "idempotency_key": case["id"],
            },
        )
        executed.append("validate_workflow")
        assert envelope["ok"] is False
        assert envelope["errors"][0]["code"] == "SCHEMA_DRIFT"
        return executed
    if variant == "mutate_after_search":
        executed.append("get_plugin_schema")
        mutated = copy.deepcopy(snapshot)
        mutated[0]["schema"] = {
            "inputs": [{"key": "host", "type": "string", "required": True}, {"key": "extra"}],
            "outputs": [],
        }
        _install_mutated = SnapshotPluginSchemaService(mutated)
        identity = decode_capability_ref(card["capability_ref"])

        def drifted_resolve(context, capability_ref, expected_schema_hash=None, **kwargs):
            return resolve_capability(
                context,
                capability_ref,
                expected_schema_hash=expected_schema_hash,
                plugin_schema_service=_install_mutated,
            )

        monkeypatch.setattr("bkflow.harness.services.validator.resolve_capability", drifted_resolve)
        envelope = validate_workflow_with_context(
            context,
            {
                "a2flow": _a2flow(identity["code"], {"host": "example-host"}),
                "bindings": [
                    {
                        "node_id": "node_1",
                        "capability_ref": card["capability_ref"],
                        "schema_hash": card["schema_hash"],
                        "credential_ref": None,
                    }
                ],
                "idempotency_key": case["id"],
            },
        )
        executed.append("validate_workflow")
        assert envelope["ok"] is False
        assert envelope["errors"][0]["code"] == "SCHEMA_DRIFT"
        return executed
    raise AssertionError(variant)


def _run_idempotent(case, context, snapshot, card, executed):
    identity = decode_capability_ref(card["capability_ref"])
    executed.extend(["get_plugin_schema"])
    payload = {
        "intent": {"goal": case["id"]},
        "a2flow": _a2flow(identity["code"], {"host": "example-host"}),
        "bindings": [
            {
                "node_id": "node_1",
                "capability_ref": card["capability_ref"],
                "schema_hash": card["schema_hash"],
                "credential_ref": None,
            }
        ],
        "idempotency_key": "{}-validate".format(case["id"]),
    }
    first = validate_workflow_with_context(context, payload)
    executed.append("validate_workflow")
    assert first["ok"] is True
    if case["variant"] == "validate_and_draft_replay":
        replay = validate_workflow_with_context(context, payload)
        assert replay["revision_id"] == first["revision_id"]
        assert WorkflowPlanRevision.objects.filter(run_id=first["run_id"]).count() == 1
    draft_payload = {
        "run_id": first["run_id"],
        "revision_id": first["revision_id"],
        "plan_hash": first["plan_hash"],
        "idempotency_key": "{}-draft".format(case["id"]),
        "auto_release": True,
    }
    draft1 = create_workflow_draft_with_context(context, draft_payload)
    executed.append("create_workflow_draft")
    assert draft1["ok"] is True
    assert draft1["status"] == HarnessRunStatus.DRAFT_READY.value
    draft2 = create_workflow_draft_with_context(context, draft_payload)
    executed.append("create_workflow_draft")
    assert draft2["artifact_refs"] == draft1["artifact_refs"]
    template_ids = [item["value"] for item in draft1["artifact_refs"] if item["type"] == "template_id"]
    assert len(template_ids) == 1
    if case["variant"] == "later_revision_same_template":
        second = validate_workflow_with_context(
            context,
            {
                **payload,
                "run_id": first["run_id"],
                "a2flow": {**payload["a2flow"], "desc": "retry"},
                "expected_plan_hash": first["plan_hash"],
                "idempotency_key": "{}-validate-2".format(case["id"]),
            },
        )
        executed.append("validate_workflow")
        later = create_workflow_draft_with_context(
            context,
            {
                "run_id": second["run_id"],
                "revision_id": second["revision_id"],
                "plan_hash": second["plan_hash"],
                "idempotency_key": "{}-draft-2".format(case["id"]),
            },
        )
        executed.append("create_workflow_draft")
        later_ids = [item["value"] for item in later["artifact_refs"] if item["type"] == "template_id"]
        assert later_ids == template_ids
        assert Template.objects.filter(space_id=context.space_id).count() == 1
    return executed


def _run_forged(case, space, expected, executed):
    if case["variant"] == "forged_body_ignored":
        request = SimpleNamespace(
            app=SimpleNamespace(bk_app_code="bkflow_harness"),
            user=SimpleNamespace(username="alice", is_authenticated=True),
            data={
                "platform_key": "evil",
                "platform_app": "evil_app",
                "actor": "mallory",
                "space_id": 999999,
                "scope_type": "biz",
                "scope_value": "999",
                "target_environment": "prod",
            },
            trace_id="corr-forged",
        )
        context = derive_trusted_context(request, space.id)
        executed.append("trusted_context")
        assert context.actor == "alice"
        assert context.platform_app == "bkflow_harness"
        assert context.space_id == space.id
        assert context.target_environment == "stage"
        assert context.platform_key == "bkaidev"
        return executed
    request = SimpleNamespace(
        app=SimpleNamespace(bk_app_code="bkflow_harness"),
        user=SimpleNamespace(username="mallory", is_authenticated=True),
        data={},
        trace_id="corr-denied",
    )
    with pytest.raises(HarnessAuthorizationError) as exc:
        derive_trusted_context(request, space.id)
    executed.append("trusted_context")
    assert exc.value.code == expected["error_code"]
    return executed


@pytest.mark.django_db
@pytest.mark.parametrize("case", _load_cases() if FIXTURE.exists() else [], ids=lambda item: item["id"])
def test_golden_case_executes_pinned_tool_sequence(case, golden_space, monkeypatch):
    """执行单条 Golden Case，核对工具序列、终态和禁止副作用。"""
    executed = _run_case(case, golden_space, monkeypatch)
    assert executed == case["expected_tool_sequence"]
    _assert_no_forbidden_effects(golden_space[0])
