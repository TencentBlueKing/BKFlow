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
from typing import List, Optional


def _build_conditions(outgoing_flow_ids, conditions_data):
    result = {}
    for idx, flow_id in enumerate(outgoing_flow_ids):
        if idx < len(conditions_data):
            cond = conditions_data[idx]
            evaluate = cond.get("evaluate", "True") if isinstance(cond, dict) else "True"
            name = cond.get("name", "") if isinstance(cond, dict) else ""
        else:
            evaluate = "True"
            name = ""
        result[flow_id] = {"evaluate": evaluate, "name": name, "tag": "branch_{}".format(flow_id)}
    return result


def build_gateway(
    node_id: str,
    name: str,
    node_type: str,
    incoming: List[str],
    outgoing: List[str],
    conditions: Optional[List[dict]] = None,
    default_next_flow_id: Optional[str] = None,
    converge_gateway_id: Optional[str] = None,
) -> dict:
    if node_type == "ConvergeGateway":
        outgoing_value = outgoing[0] if outgoing else ""
    else:
        outgoing_value = outgoing
    gateway = {"id": node_id, "name": name, "type": node_type, "incoming": incoming, "outgoing": outgoing_value}
    if node_type in ("ExclusiveGateway", "ConditionalParallelGateway"):
        gateway["conditions"] = _build_conditions(outgoing, conditions or [])
    if node_type == "ExclusiveGateway":
        if default_next_flow_id:
            gateway["default_condition"] = {"flow_id": default_next_flow_id, "name": "默认分支"}
        else:
            gateway["default_condition"] = {}
    if node_type in ("ParallelGateway", "ConditionalParallelGateway"):
        gateway["converge_gateway_id"] = converge_gateway_id or ""
    return gateway
