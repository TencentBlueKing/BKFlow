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
import pytest

from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import AmbiguousCapability, HarnessUserInputError
from bkflow.harness.services.canonical import canonical_json_bytes
from bkflow.harness.services.capability_ref import decode_capability_ref
from bkflow.harness.services.projection import (
    SEARCH_CARD_FIELDS,
    search_workflow_capabilities,
)

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


def _item(**overrides):
    item = {
        "plugin_type": "component",
        "source_key": None,
        "code": "demo_restart_service",
        "version": "1.0.0",
        "name": "重启服务",
        "aliases": ["restart"],
        "tags": ["ops"],
        "use_cases": ["重启主机服务"],
        "space_ids": [12],
        "schema": {"inputs": [{"key": "host"}], "outputs": []},
        "required_credentials": [],
        "side_effects": "write",
    }
    item.update(overrides)
    return item


def test_search_returns_lightweight_cards_without_schema():
    """搜索只返回轻量投影，不泄漏完整 Schema 或密钥。"""
    result = search_workflow_capabilities(
        context=CONTEXT,
        query="重启服务",
        registry_snapshot=[_item()],
    )
    assert result.ok is True
    assert len(result.candidates) == 1
    card = result.candidates[0]
    assert set(card) == set(SEARCH_CARD_FIELDS)
    assert "schema" not in card
    assert "inputs" not in card
    assert "token" not in str(card).lower()


def test_exact_name_and_alias_and_chinese_token():
    """精确名称、别名和中文 token 都能命中。"""
    snapshot = [_item()]
    by_name = search_workflow_capabilities(context=CONTEXT, query="重启服务", registry_snapshot=snapshot)
    by_alias = search_workflow_capabilities(context=CONTEXT, query="restart", registry_snapshot=snapshot)
    by_zh = search_workflow_capabilities(context=CONTEXT, query="重启", registry_snapshot=snapshot)
    assert decode_capability_ref(by_name.candidates[0]["capability_ref"])["code"] == "demo_restart_service"
    assert decode_capability_ref(by_alias.candidates[0]["capability_ref"])["code"] == "demo_restart_service"
    assert decode_capability_ref(by_zh.candidates[0]["capability_ref"])["code"] == "demo_restart_service"


def test_ambiguous_query_requires_clarification():
    """同分候选必须澄清，不能任意决胜。"""
    snapshot = [
        _item(code="restart_a", name="重启A", aliases=["restart"]),
        _item(code="restart_b", name="重启B", aliases=["restart"]),
    ]
    with pytest.raises(AmbiguousCapability) as exc:
        search_workflow_capabilities(context=CONTEXT, query="restart", registry_snapshot=snapshot)
    assert exc.value.code == "AMBIGUOUS_CAPABILITY"
    assert len(exc.value.candidates) == 2


def test_zero_candidate_and_cross_space_filter():
    """无结果为空列表；跨空间能力在过滤阶段被去掉。"""
    empty = search_workflow_capabilities(context=CONTEXT, query="不存在的能力", registry_snapshot=[_item()])
    assert empty.ok is True
    assert empty.candidates == []
    leaked = search_workflow_capabilities(
        context=CONTEXT,
        query="重启服务",
        registry_snapshot=[_item(space_ids=[99], code="other_space_plugin")],
    )
    assert leaked.candidates == []


def test_stable_tie_break_and_byte_equivalent_output():
    """弱匹配同分后按稳定身份排序，相同输入输出字节级一致。"""
    snapshot = [
        _item(code="beta_tool", name="Beta Helper", aliases=[], tags=["tool"], use_cases=[]),
        _item(code="alpha_tool", name="Alpha Helper", aliases=[], tags=["tool"], use_cases=[]),
    ]
    first = search_workflow_capabilities(context=CONTEXT, query="tool", registry_snapshot=snapshot)
    second = search_workflow_capabilities(context=CONTEXT, query="tool", registry_snapshot=list(reversed(snapshot)))
    assert [decode_capability_ref(item["capability_ref"])["code"] for item in first.candidates] == [
        "alpha_tool",
        "beta_tool",
    ]
    assert canonical_json_bytes(first.candidates) == canonical_json_bytes(second.candidates)


def test_top_k_default_and_cap_and_reject_21():
    """top_k 默认 10，最大 20，21 被拒绝。"""
    snapshot = [_item(code=f"plugin_{i}", name=f"插件{i}", aliases=[], tags=["plugin"], use_cases=[]) for i in range(25)]
    defaulted = search_workflow_capabilities(context=CONTEXT, query="plugin", registry_snapshot=snapshot)
    assert len(defaulted.candidates) == 10
    capped = search_workflow_capabilities(context=CONTEXT, query="plugin", registry_snapshot=snapshot, top_k=20)
    assert len(capped.candidates) == 20
    with pytest.raises(HarnessUserInputError) as exc:
        search_workflow_capabilities(context=CONTEXT, query="plugin", registry_snapshot=snapshot, top_k=21)
    assert exc.value.code == "USER_INPUT"
