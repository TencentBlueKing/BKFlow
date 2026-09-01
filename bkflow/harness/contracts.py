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
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TrustedHarnessContext:
    """由网关身份和空间部署绑定推导的可信上下文。"""

    platform_key: str
    platform_app: str
    actor: str
    space_id: int
    scope_type: Optional[str]
    scope_value: Optional[str]
    target_environment: str
    policy_version: str
    mcp_contract_version: str
    correlation_id: str

    @classmethod
    def from_request(cls, request: Any, space_id: int) -> "TrustedHarnessContext":
        from bkflow.harness.services.context import derive_trusted_context

        return derive_trusted_context(request, space_id)


@dataclass(frozen=True)
class ResolvedCapability:
    """可信空间内解析出的精确能力。"""

    capability_ref: str
    plugin_type: str
    code: str
    source_key: Optional[str]
    resolved_version: str
    schema_hash: str
    schema: Dict[str, Any]
    risk_level: str
