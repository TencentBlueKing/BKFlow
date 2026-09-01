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
from bkflow.harness.contracts import ResolvedCapability, TrustedHarnessContext
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.facade import (
    ERROR_CATEGORIES,
    HARNESS_CONTRACT_VERSION,
    P0_ACTION_RISK,
    P0_TOOL_OPERATION_MAP,
    HarnessFacade,
    normalize_errors,
)
from bkflow.harness.services.projection import CapabilitySearchResult
from bkflow.harness.services.validator import ENVELOPE_KEYS

CONTEXT = TrustedHarnessContext(
    platform_key="bkaidev",
    platform_app="test",
    actor="username",
    space_id=12,
    scope_type=None,
    scope_value=None,
    target_environment="stage",
    policy_version="p0-v1",
    mcp_contract_version="1.0.0",
    correlation_id="corr-facade",
)


def test_tool_operation_map_and_risk():
    """P0 Tool 与 APIGW operation、风险映射保持稳定。"""
    assert HARNESS_CONTRACT_VERSION == "1.0.0"
    assert P0_TOOL_OPERATION_MAP == {
        "search_workflow_capabilities": "harness_search_workflow_capabilities",
        "get_plugin_schema": "harness_get_plugin_schema",
        "validate_workflow": "harness_validate_workflow",
        "create_workflow_draft": "harness_create_workflow_draft",
    }
    assert P0_ACTION_RISK["create_workflow_draft"] == "L1"
    assert set(ERROR_CATEGORIES) >= {"USER_INPUT", "SCHEMA_DRIFT", "PERMISSION", "VALIDATION"}


def test_normalize_errors_adds_category_and_redacts_nothing_extra():
    """错误条目补齐 category，且不含 token/secret 字段。"""
    items = normalize_errors([{"code": "SCHEMA_DRIFT", "message": "drift", "path": "bindings.node_1"}])
    assert items[0]["category"] == "SCHEMA_DRIFT"
    assert items[0]["suggested_action"] == "search_and_rebind"
    assert "token" not in str(items).lower()


def test_search_wraps_projection_into_envelope(monkeypatch):
    """检索结果进入标准 Envelope。"""
    monkeypatch.setattr(
        "bkflow.harness.services.facade.PluginSchemaService.list_plugins",
        lambda self, **kwargs: ([{"code": "demo", "name": "重启", "plugin_type": "component", "version": "1.0.0"}], 1),
    )
    monkeypatch.setattr(
        "bkflow.harness.services.facade.search_capabilities",
        lambda **kwargs: CapabilitySearchResult(
            ok=True,
            candidates=[{"capability_ref": "cap_v1_x", "display_name": "重启", "score": 90}],
        ),
    )
    envelope = HarnessFacade().search_workflow_capabilities(CONTEXT, {"query": "重启"})
    assert set(envelope) == set(ENVELOPE_KEYS)
    assert envelope["ok"] is True
    assert envelope["artifact_refs"][0]["type"] == "capability_card"


def test_get_plugin_schema_uses_resolver(monkeypatch):
    """精确 Schema 通过 resolver 加载。"""
    ref = encode_capability_ref(plugin_type="component", source_key=None, code="demo", version="1.0.0")
    monkeypatch.setattr(
        "bkflow.harness.services.facade.resolve_capability",
        lambda *args, **kwargs: ResolvedCapability(
            capability_ref=ref,
            plugin_type="component",
            code="demo",
            source_key=None,
            resolved_version="1.0.0",
            schema_hash="a" * 64,
            schema={"inputs": [], "outputs": []},
            risk_level="L1",
        ),
    )
    envelope = HarnessFacade().get_plugin_schema(CONTEXT, {"capability_ref": ref})
    assert envelope["ok"] is True
    assert envelope["artifact_refs"][0]["value"]["schema"] == {"inputs": [], "outputs": []}


def test_validate_and_draft_delegate(monkeypatch):
    """写操作委托给已有服务并保持 Envelope。"""
    monkeypatch.setattr(
        "bkflow.harness.services.facade.validate_workflow_with_context",
        lambda context, payload: {
            "ok": True,
            "run_id": "r1",
            "revision_id": "rev1",
            "plan_hash": "a" * 64,
            "status": "VALIDATING",
            "summary": "ok",
            "artifact_refs": [],
            "errors": [],
            "next_actions": [],
            "correlation_id": context.correlation_id,
        },
    )
    monkeypatch.setattr(
        "bkflow.harness.services.facade.create_workflow_draft_with_context",
        lambda context, payload: {
            "ok": True,
            "run_id": "r1",
            "revision_id": "rev1",
            "plan_hash": "a" * 64,
            "status": "DRAFT_READY",
            "summary": "draft",
            "artifact_refs": [],
            "errors": [],
            "next_actions": [],
            "correlation_id": context.correlation_id,
        },
    )
    facade = HarnessFacade()
    validated = facade.validate_workflow(CONTEXT, {"a2flow": {}, "bindings": [], "idempotency_key": "k"})
    drafted = facade.create_workflow_draft(
        CONTEXT, {"run_id": "r1", "revision_id": "rev1", "expected_plan_hash": "a" * 64, "auto_release": True}
    )
    assert validated["ok"] is True
    assert drafted["status"] == "DRAFT_READY"
    assert drafted["ok"] is True
