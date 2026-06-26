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
from bkflow.template.debug.dependency import (
    build_dependency_graph,
    closure,
    compute_node_config_hash,
    compute_tree_fingerprint,
)

# 最小 web 树：start -> A -> B -> end；B 引用 A 产出的 ${g1}
PIPELINE = {
    "start_event": {"id": "s", "type": "EmptyStartEvent", "incoming": None, "outgoing": "f0"},
    "end_event": {"id": "e", "type": "EmptyEndEvent", "incoming": "f2", "outgoing": None},
    "activities": {
        "A": {
            "id": "A",
            "type": "ServiceActivity",
            "incoming": "f0",
            "outgoing": "f1",
            "component": {"code": "test", "data": {"x": {"hook": False, "value": "1"}}},
        },
        "B": {
            "id": "B",
            "type": "ServiceActivity",
            "incoming": "f1",
            "outgoing": "f2",
            "component": {"code": "test", "data": {"y": {"hook": True, "value": "${g1}"}}},
        },
    },
    "flows": {
        "f0": {"id": "f0", "source": "s", "target": "A"},
        "f1": {"id": "f1", "source": "A", "target": "B"},
        "f2": {"id": "f2", "source": "B", "target": "e"},
    },
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
        },
    },
}


class TestDependency:
    def test_control_and_data_edges(self):
        graph = build_dependency_graph(PIPELINE)
        # 控制流：A -> B
        assert "B" in graph["control"]["A"]
        # 数据流：A 产出 ${g1}，B 消费 -> A -> B
        assert "B" in graph["data"]["A"]

    def test_closure_includes_downstream(self):
        graph = build_dependency_graph(PIPELINE)
        assert closure({"A"}, graph) == {"A", "B"}
        assert closure({"B"}, graph) == {"B"}

    def test_config_hash_stable_and_sensitive(self):
        h1 = compute_node_config_hash(PIPELINE["activities"]["A"])
        h2 = compute_node_config_hash(PIPELINE["activities"]["A"])
        assert h1 == h2
        changed = {
            **PIPELINE["activities"]["A"],
            "component": {"code": "test", "data": {"x": {"hook": False, "value": "2"}}},
        }
        assert compute_node_config_hash(changed) != h1

    def test_tree_fingerprint_has_nodes_and_topology(self):
        fp = compute_tree_fingerprint(PIPELINE)
        assert set(fp["nodes"].keys()) == {"A", "B"}
        assert "flows" in fp and "constants" in fp and "gateways" in fp
