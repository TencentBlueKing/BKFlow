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

import pytest

from bkflow.template.debug.pipeline_builder import build_single_node_pipeline_tree

FULL_TREE = {
    "activities": {
        "A": {
            "id": "A",
            "type": "ServiceActivity",
            "name": "A",
            "optional": True,
            "component": {"code": "t", "data": {"x": {"hook": False, "value": "1"}}},
        },
        "B": {
            "id": "B",
            "type": "ServiceActivity",
            "name": "B",
            "optional": True,
            "component": {"code": "t", "data": {"y": {"hook": True, "value": "${g1}"}}},
        },
    },
    "flows": {},
    "gateways": {},
    "constants": {
        "${g1}": {
            "key": "${g1}",
            "name": "g1",
            "show_type": "hide",
            "value": "",
            "source_type": "component_outputs",
            "custom_type": "",
            "source_tag": "",
            "source_info": {"A": ["k1"]},
        }
    },
}


class TestBuildSingleNode:
    def test_minimal_topology_and_constants(self):
        tree = build_single_node_pipeline_tree(FULL_TREE, "B", var_values={"${g1}": "hydrated"})
        # 仅一个活动节点 B，且 start->B->end 连通
        assert list(tree["activities"].keys()) == ["B"]
        b = tree["activities"]["B"]
        assert tree["start_event"]["outgoing"] == b["incoming"]
        assert tree["end_event"]["incoming"] == b["outgoing"]
        assert len(tree["flows"]) == 2
        # ${g1} 被注入值并降级为 custom
        c = tree["constants"]["${g1}"]
        assert c["value"] == "hydrated"
        assert c["source_type"] == "custom" and c["source_info"] == {}

    def test_node_not_found_raises(self):
        with pytest.raises(KeyError):
            build_single_node_pipeline_tree(FULL_TREE, "ZZZ", var_values={})
