"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
from typing import Any, Optional

from bkflow.harness.constants import UNVERSIONED
from bkflow.harness.contracts import ResolvedCapability, TrustedHarnessContext
from bkflow.harness.exceptions import (
    CapabilityForbidden,
    CapabilityNotFound,
    SchemaDrift,
)
from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import decode_capability_ref
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService


def _resolved_version(payload: dict, fallback: str) -> str:
    value = payload.get("resolved_version") or payload.get("version") or fallback
    return value or UNVERSIONED


def resolve_capability(
    context: TrustedHarnessContext,
    capability_ref: str,
    *,
    expected_schema_hash: Optional[str] = None,
    plugin_schema_service: Optional[Any] = None,
    risk_level: str = "L1",
) -> ResolvedCapability:
    """在可信空间内按 capability_ref 精确解析 Schema。"""
    identity = decode_capability_ref(capability_ref)
    service = plugin_schema_service or PluginSchemaService(
        space_id=context.space_id,
        username=context.actor,
        scope_type=context.scope_type,
        scope_id=context.scope_value,
    )
    version = None if identity["version"] == UNVERSIONED else identity["version"]
    try:
        payload = service.get_plugin_schema(
            code=identity["code"],
            version=version,
            plugin_type=identity["plugin_type"],
            source_key=identity["source_key"],
        )
    except PermissionError as exc:
        raise CapabilityForbidden("capability is forbidden in the trusted space") from exc
    except ValueError as exc:
        raise CapabilityNotFound("capability is not available in the trusted space") from exc

    resolved_version = _resolved_version(payload, identity["version"])
    if resolved_version != identity["version"]:
        raise SchemaDrift("capability version drifted")

    schema = {"inputs": payload.get("inputs") or [], "outputs": payload.get("outputs") or []}
    current_hash = schema_hash(schema)
    if expected_schema_hash and current_hash != expected_schema_hash:
        raise SchemaDrift("capability schema drifted")

    return ResolvedCapability(
        capability_ref=capability_ref,
        plugin_type=identity["plugin_type"],
        code=identity["code"],
        source_key=identity["source_key"],
        resolved_version=resolved_version,
        schema_hash=current_hash,
        schema=schema,
        risk_level=risk_level,
    )
