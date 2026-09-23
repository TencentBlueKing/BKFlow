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
import copy

from pipeline.utils.uniqid import node_uniqid


def build_single_node_pipeline_tree(full_tree: dict, node_id: str, var_values: dict) -> dict:
    """构造仅含 node_id 的最小 web pipeline_tree：start -> node -> end。

    :param full_tree: 完整 draft pipeline_tree
    :param node_id: 目标节点（必须是 ServiceActivity）
    :param var_values: 注入到常量的取值 {${key}: value}
    """
    if node_id not in full_tree.get("activities", {}):
        raise KeyError("node {} not in pipeline activities".format(node_id))

    node = copy.deepcopy(full_tree["activities"][node_id])
    start_id, end_id = node_uniqid(), node_uniqid()
    flow_in, flow_out = node_uniqid(), node_uniqid()

    node["incoming"] = flow_in
    node["outgoing"] = flow_out
    node.setdefault("optional", True)

    constants = {}
    for key, c in full_tree.get("constants", {}).items():
        nc = copy.deepcopy(c)
        if key in var_values:
            nc["value"] = var_values[key]
        # mini 树中没有产出节点，所有产出型常量降级为 custom 直接给值
        if nc.get("source_type") == "component_outputs":
            nc["source_type"] = "custom"
            nc["source_info"] = {}
            nc["source_tag"] = ""
            if key in var_values:
                nc["value"] = var_values[key]
        constants[key] = nc

    return {
        "id": node_uniqid(),
        "name": "debug_single_node",
        "start_event": {
            "id": start_id,
            "name": "start",
            "type": "EmptyStartEvent",
            "incoming": None,
            "outgoing": flow_in,
        },
        "end_event": {
            "id": end_id,
            "name": "end",
            "type": "EmptyEndEvent",
            "incoming": flow_out,
            "outgoing": None,
        },
        "activities": {node_id: node},
        "flows": {
            flow_in: {"id": flow_in, "source": start_id, "target": node_id},
            flow_out: {"id": flow_out, "source": node_id, "target": end_id},
        },
        "gateways": {},
        "constants": constants,
        "outputs": [],
    }
