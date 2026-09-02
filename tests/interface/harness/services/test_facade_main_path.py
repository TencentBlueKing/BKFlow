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
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import CapabilityForbidden
from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import (
    decode_capability_ref,
    encode_capability_ref,
)
from bkflow.harness.services.facade import HarnessFacade
from bkflow.harness.services.resolver import resolve_capability

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
    correlation_id="corr-main-path",
)

SCHEMA = {"inputs": [{"key": "host", "type": "string", "required": True}], "outputs": []}
SCHEMA_HASH = schema_hash(SCHEMA)
PLUGIN = {
    "plugin_type": "component",
    "source_key": None,
    "code": "demo_restart_service",
    "version": "1.0.0",
    "name": "重启服务",
    "description": "重启指定主机上的服务",
    "inputs": SCHEMA["inputs"],
    "outputs": SCHEMA["outputs"],
}
CAP_REF = encode_capability_ref(plugin_type="component", source_key=None, code="demo_restart_service", version="1.0.0")


class RecordingRegistry:
    """只替代插件目录，不替代 Facade / Projection / Resolver。"""

    def __init__(self, plugins, get_error=None):
        self.plugins = plugins
        self.get_error = get_error
        self.list_calls = []

    def list_plugins(self, **kwargs):
        self.list_calls.append(kwargs)
        keyword = kwargs.get("keyword")
        items = list(self.plugins)
        if keyword:
            lowered = keyword.lower()
            items = [
                item
                for item in items
                if lowered in (item.get("code") or "").lower() or lowered in (item.get("name") or "").lower()
            ]
        return items, len(items)

    def get_plugin_schema(self, code, version=None, plugin_type=None, source_key=None):
        if self.get_error:
            raise self.get_error
        for item in self.plugins:
            if item["code"] != code:
                continue
            if version and version != (item.get("version") or item.get("resolved_version")):
                raise ValueError("version {} is not available".format(version))
            return {
                "code": item["code"],
                "plugin_type": item["plugin_type"],
                "version": item["version"],
                "resolved_version": item["version"],
                "inputs": item.get("inputs") or [],
                "outputs": item.get("outputs") or [],
                "source_key": item.get("source_key"),
            }
        raise ValueError("capability is not available")


def _install(monkeypatch, registry):
    monkeypatch.setattr("bkflow.harness.services.facade.PluginSchemaService", lambda **kwargs: registry)
    monkeypatch.setattr("bkflow.harness.services.resolver.PluginSchemaService", lambda **kwargs: registry)
    return HarnessFacade()


def test_natural_language_query_reaches_projection_and_returns_real_schema_hash(monkeypatch):
    """自然语言查询不能在目录层被整句过滤，卡片 hash 必须等于真实 Schema。"""
    registry = RecordingRegistry([PLUGIN])
    envelope = _install(monkeypatch, registry).search_workflow_capabilities(CONTEXT, {"query": "请帮我重启服务并通知负责人"})

    assert envelope["ok"] is True
    assert registry.list_calls
    assert registry.list_calls[0].get("keyword") in {None, ""}
    card = envelope["artifact_refs"][0]["value"]
    assert decode_capability_ref(card["capability_ref"])["code"] == "demo_restart_service"
    assert card["schema_hash"] == SCHEMA_HASH
    assert card["schema_hash"] != schema_hash({})
    assert "inputs" not in card

    resolved = resolve_capability(
        CONTEXT,
        card["capability_ref"],
        expected_schema_hash=card["schema_hash"],
        plugin_schema_service=registry,
    )
    assert resolved.schema_hash == card["schema_hash"]


def test_get_plugin_schema_maps_forbidden_and_infra_errors(monkeypatch):
    """权限错误保持 PERMISSION；基础设施异常不得伪装成能力不存在。"""
    forbidden_registry = RecordingRegistry([PLUGIN], get_error=CapabilityForbidden("no"))
    forbidden = _install(monkeypatch, forbidden_registry).get_plugin_schema(CONTEXT, {"capability_ref": CAP_REF})
    assert forbidden["ok"] is False
    assert forbidden["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert forbidden["errors"][0]["category"] == "PERMISSION"

    timeout_registry = RecordingRegistry([PLUGIN], get_error=TimeoutError("meta timeout"))
    timeout = _install(monkeypatch, timeout_registry).get_plugin_schema(CONTEXT, {"capability_ref": CAP_REF})
    assert timeout["ok"] is False
    assert timeout["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert timeout["errors"][0]["category"] == "RETRYABLE_INFRA"
    assert timeout["errors"][0]["retryable"] is True
    assert timeout["errors"][0]["code"] != "CAPABILITY_NOT_FOUND"


def test_expected_schema_hash_from_card_does_not_drift_on_fetch(monkeypatch):
    """Agent 把卡片 hash 传给 get_plugin_schema 时不能误报 SCHEMA_DRIFT。"""
    registry = RecordingRegistry([PLUGIN])
    facade = _install(monkeypatch, registry)
    search = facade.search_workflow_capabilities(CONTEXT, {"query": "重启服务"})
    card = search["artifact_refs"][0]["value"]
    fetched = facade.get_plugin_schema(
        CONTEXT, {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]}
    )
    assert fetched["ok"] is True
    assert fetched["artifact_refs"][0]["value"]["schema_hash"] == card["schema_hash"]
