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
import hashlib
import json
import re

from bkflow.harness.services.canonical import (
    canonical_json_bytes,
    plan_hash,
    schema_hash,
    sha256_json,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_canonical_json_bytes_sorts_object_keys_and_keeps_list_order():
    """对象键排序后字节相同，列表顺序仍然有意义。"""
    left = canonical_json_bytes({"b": 1, "a": [2, 1]})
    right = canonical_json_bytes({"a": [2, 1], "b": 1})
    assert left == right
    assert left == b'{"a":[2,1],"b":1}'
    assert canonical_json_bytes([1, 2]) != canonical_json_bytes([2, 1])


def test_canonical_json_bytes_keeps_unicode():
    """Unicode 不以 ASCII 转义，保证跨环境稳定。"""
    assert canonical_json_bytes({"name": "重启服务"}) == '{"name":"重启服务"}'.encode()


def test_sha256_and_schema_hash_are_lowercase_hex():
    """sha256_json 与 schema_hash 都是 64 位小写十六进制。"""
    value = {"type": "object", "properties": {"host": {"type": "string"}}}
    digest = sha256_json(value)
    assert HEX64.match(digest)
    assert (
        digest
        == hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    )
    assert schema_hash(value) == digest
    assert sha256_json({"x": 1}) != sha256_json({"x": 2})


def _base_plan():
    return {
        "a2flow": {"version": "2.0", "activities": {"node_1": {"type": "Service"}}},
        "bindings": [
            {
                "node_id": "node_2",
                "capability_ref": "cap_b",
                "resolved_version": "1.0.0",
                "schema_hash": "b" * 64,
                "credential_ref": None,
                "risk_level": "L1",
            },
            {
                "node_id": "node_1",
                "capability_ref": "cap_a",
                "resolved_version": "1.0.0",
                "schema_hash": "a" * 64,
                "credential_ref": "cred.restart",
                "risk_level": "L1",
            },
        ],
        "space_id": 12,
        "scope_type": None,
        "scope_value": None,
        "target_environment": "stage",
        "authorization_scope": "space:12",
        "policies": {
            "execution": {"mode": "draft_only"},
            "risk": {"max_level": "L1"},
            "retry": {"max": 0},
            "timeout": {"seconds": 30},
            "compensation": {"enabled": False},
            "postcondition": {"required": False},
        },
    }


def test_plan_hash_is_stable_for_reordered_bindings_and_keys():
    """plan_hash 对绑定顺序和对象键顺序稳定。"""
    left = _base_plan()
    right = _base_plan()
    right["bindings"] = list(reversed(right["bindings"]))
    right["policies"] = {
        "timeout": right["policies"]["timeout"],
        "risk": right["policies"]["risk"],
        "retry": right["policies"]["retry"],
        "postcondition": right["policies"]["postcondition"],
        "execution": right["policies"]["execution"],
        "compensation": right["policies"]["compensation"],
    }
    digest = plan_hash(left)
    assert HEX64.match(digest)
    assert digest == plan_hash(right)


def test_plan_hash_excludes_model_conversation_token_and_trace():
    """模型名、对话措辞、Token 明文和临时 Trace 不进入 plan_hash。"""
    base = _base_plan()
    polluted = dict(base)
    polluted.update(
        {
            "model_name": "deepseek-v3",
            "conversation_wording": "帮我重启一下",
            "display_copy": "草稿已就绪",
            "token_plaintext": "not-a-real-token",
            "trace_id": "transient-trace",
        }
    )
    assert plan_hash(base) == plan_hash(polluted)


def test_plan_hash_changes_when_version_scope_or_policy_changes():
    """精确版本、范围或策略变化必须改变 plan_hash。"""
    base = _base_plan()
    changed_version = _base_plan()
    changed_version["bindings"][1]["resolved_version"] = "1.0.1"
    changed_env = _base_plan()
    changed_env["target_environment"] = "prod"
    changed_policy = _base_plan()
    changed_policy["policies"]["retry"] = {"max": 1}

    assert plan_hash(base) != plan_hash(changed_version)
    assert plan_hash(base) != plan_hash(changed_env)
    assert plan_hash(base) != plan_hash(changed_policy)
