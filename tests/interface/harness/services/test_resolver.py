"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from unittest.mock import Mock

import pytest

from bkflow.harness.constants import UNVERSIONED
from bkflow.harness.contracts import ResolvedCapability, TrustedHarnessContext
from bkflow.harness.exceptions import (
    CapabilityForbidden,
    CapabilityNotFound,
    CapabilityRefError,
    SchemaDrift,
)
from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.resolver import resolve_capability

CONTEXT = TrustedHarnessContext(
    platform_key="bkaidev",
    platform_app="bkflow_harness",
    actor="alice",
    space_id=12,
    scope_type=None,
    scope_value=None,
    target_environment="stage",
    policy_version="p0-v1",
    mcp_contract_version="1.0.0",
    correlation_id="corr-1",
)

SCHEMA = {"inputs": [{"key": "host", "type": "string"}], "outputs": []}


def _schema_service(payload, error=None):
    service = Mock()
    if error:
        service.get_plugin_schema.side_effect = error
    else:
        service.get_plugin_schema.return_value = payload
    service.space_id = CONTEXT.space_id
    return service


def test_resolve_exact_version_and_schema_hash():
    """Resolve 必须核对精确版本和 Schema 哈希。"""
    payload = {
        "code": "demo_restart_service",
        "plugin_type": "component",
        "version": "1.0.0",
        "resolved_version": "1.0.0",
        "inputs": SCHEMA["inputs"],
        "outputs": SCHEMA["outputs"],
    }
    ref = encode_capability_ref(
        plugin_type="component",
        source_key=None,
        code="demo_restart_service",
        version="1.0.0",
    )
    resolved = resolve_capability(
        CONTEXT,
        ref,
        expected_schema_hash=schema_hash(SCHEMA),
        plugin_schema_service=_schema_service(payload),
    )
    assert isinstance(resolved, ResolvedCapability)
    assert resolved.resolved_version == "1.0.0"
    assert resolved.schema_hash == schema_hash(SCHEMA)
    assert resolved.schema == SCHEMA


def test_missing_version_uses_unversioned_sentinel():
    """引用缺少版本时使用 unversioned，而不是 latest。"""
    payload = {
        "code": "legacy_plugin",
        "plugin_type": "remote_plugin",
        "version": "",
        "resolved_version": UNVERSIONED,
        "inputs": [],
        "outputs": [],
    }
    ref = encode_capability_ref(plugin_type="remote_plugin", source_key=None, code="legacy_plugin", version=UNVERSIONED)
    resolved = resolve_capability(CONTEXT, ref, plugin_schema_service=_schema_service(payload))
    assert resolved.resolved_version == UNVERSIONED


def test_schema_or_version_drift_is_typed_error():
    """版本或哈希漂移必须返回 SCHEMA_DRIFT。"""
    payload = {
        "code": "demo_restart_service",
        "plugin_type": "component",
        "version": "1.0.1",
        "resolved_version": "1.0.1",
        "inputs": SCHEMA["inputs"],
        "outputs": SCHEMA["outputs"],
    }
    ref = encode_capability_ref(plugin_type="component", source_key=None, code="demo_restart_service", version="1.0.0")
    with pytest.raises(SchemaDrift) as exc:
        resolve_capability(CONTEXT, ref, plugin_schema_service=_schema_service(payload))
    assert exc.value.code == "SCHEMA_DRIFT"


def test_raw_plugin_code_cannot_replace_capability_ref():
    """禁止用裸 plugin code 代替 capability_ref。"""
    with pytest.raises(CapabilityRefError):
        resolve_capability(CONTEXT, "demo_restart_service", plugin_schema_service=_schema_service({}))


def test_missing_and_forbidden_capabilities():
    """空间内不存在或无权限时返回类型化错误。"""
    ref = encode_capability_ref(plugin_type="component", source_key=None, code="missing", version="1.0.0")
    with pytest.raises(CapabilityNotFound):
        resolve_capability(CONTEXT, ref, plugin_schema_service=_schema_service({}, error=ValueError("未找到插件")))
    with pytest.raises(CapabilityForbidden):
        resolve_capability(
            CONTEXT,
            ref,
            plugin_schema_service=_schema_service({}, error=PermissionError("forbidden")),
        )
