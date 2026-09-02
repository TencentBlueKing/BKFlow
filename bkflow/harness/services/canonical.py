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
import hashlib
import json
from typing import Any, Dict, Iterable, List

BINDING_KEYS = (
    "node_id",
    "capability_ref",
    "resolved_version",
    "schema_hash",
    "credential_ref",
    "risk_level",
)
POLICY_KEYS = ("execution", "risk", "retry", "timeout", "compensation", "postcondition")


def canonical_json_bytes(value: Any) -> bytes:
    """将值规范化为稳定的 UTF-8 JSON 字节。"""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    """计算规范化 JSON 的小写 SHA-256。"""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def schema_hash(schema: Any) -> str:
    """计算插件 Schema 哈希。"""
    return sha256_json(schema)


def _sorted_bindings(bindings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = [{key: item.get(key) for key in BINDING_KEYS} for item in bindings]
    return sorted(normalized, key=lambda item: item["node_id"] or "")


def plan_hash(plan: Dict[str, Any]) -> str:
    """
    计算计划哈希。

    只纳入 canonical a2flow、排序后的精确绑定、可信空间/范围/环境、
    凭证引用、授权范围以及执行/风险/重试/超时/补偿/后置条件策略。
    """
    policies = plan.get("policies") or {}
    payload = {
        "a2flow": plan["a2flow"],
        "authorization_scope": plan.get("authorization_scope"),
        "bindings": _sorted_bindings(plan.get("bindings") or []),
        "policies": {key: policies.get(key) for key in POLICY_KEYS},
        "scope_type": plan.get("scope_type"),
        "scope_value": plan.get("scope_value"),
        "space_id": plan["space_id"],
        "target_environment": plan["target_environment"],
    }
    return sha256_json(payload)
