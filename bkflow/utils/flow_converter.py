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

import logging
import re
import uuid

from pipeline.component_framework.models import ComponentModel

logger = logging.getLogger("root")


class SimpleFlowConverter:
    """
    将简化流程 JSON 格式转换为 BKFlow pipeline_tree

    输入格式示例 (JSONL，每行一个 JSON 对象):
    {"type": "name", "value": "流程名称"}
    {"type": "StartEvent", "id": "start", "name": "流程开始"}
    {"type": "Activity", "id": "n1", "name": "数据库备份", "code": "job_fast_execute_script"}
    {"type": "Link", "source": "start", "target": "n1"}
    {"type": "Variable", "key": "${db_server}", "name": "数据库IP"}
    ...
    """

    DEFAULT_ACTIVITY_CONFIG = {
        "auto_retry": {"enable": False, "interval": 0, "times": 1},
        "timeout_config": {"action": "forced_fail", "enable": False, "seconds": 10},
        "error_ignorable": False,
        "retryable": True,
        "skippable": True,
        "optional": True,
        "labels": [],
        "loop": None,
    }

    def __init__(self, simple_flow: list):
        self.simple_flow = simple_flow
        self.nodes = {}
        self.links = []
        self.variables = []
        self.template_name = ""
        self.id_mapping = {}
        self._parse_input()

    def _parse_input(self):
        for item in self.simple_flow:
            item_type = item.get("type")
            if item_type == "Link":
                self.links.append(item)
            elif item_type == "Variable":
                self.variables.append(item)
            elif item_type == "name":
                self.template_name = item.get("value", "")
            else:
                node_id = item.get("id")
                if node_id:
                    new_id = self._generate_node_id()
                    self.id_mapping[node_id] = new_id
                    item["_original_id"] = node_id
                    item["id"] = new_id
                    self.nodes[new_id] = item

        self._validate_links()

    def _generate_node_id(self):
        return "n{}".format(uuid.uuid4().hex[:31])

    def _validate_links(self):
        missing_nodes = set()
        for link in self.links:
            source = link.get("source")
            target = link.get("target")
            if source and source not in self.id_mapping:
                missing_nodes.add(source)
            if target and target not in self.id_mapping:
                missing_nodes.add(target)

        if missing_nodes:
            raise KeyError("Link 引用了未定义的节点: {}".format(", ".join(sorted(missing_nodes))))

    def _generate_flow_id(self):
        return "l{}".format(uuid.uuid4().hex[:30])

    def _map_id(self, old_id):
        return self.id_mapping.get(old_id, old_id)

    def _wrap_data_value(self, value):
        if isinstance(value, dict) and "hook" in value and "value" in value:
            return value
        return {"hook": False, "need_render": True, "value": value}

    def _normalize_component_data(self, data):
        if not isinstance(data, dict):
            return {}
        return {key: self._wrap_data_value(value) for key, value in data.items()}

    def _parse_version_number(self, version_str):
        if not version_str or version_str == "legacy":
            return (0, 0, 0)

        version_str = version_str.lstrip("vV")
        match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version_str)
        if match:
            major = int(match.group(1)) if match.group(1) else 0
            minor = int(match.group(2)) if match.group(2) else 0
            patch = int(match.group(3)) if match.group(3) else 0
            return (major, minor, patch)

        return (0, 0, 0)

    def _get_latest_component_version(self, code):
        if not code:
            return "legacy"

        try:
            versions = ComponentModel.objects.filter(code=code, status=1).values_list("version", flat=True)

            if not versions:
                logger.warning("_get_latest_component_version: No component found for code={}".format(code))
                return "legacy"

            latest_version = None
            latest_tuple = (0, 0, 0)

            for version in versions:
                version_tuple = self._parse_version_number(version)
                if version_tuple > latest_tuple:
                    latest_tuple = version_tuple
                    latest_version = version

            logger.info(
                "_get_latest_component_version: code={}, versions={}, latest={}".format(
                    code, list(versions), latest_version
                )
            )

            return latest_version or "legacy"

        except Exception as e:
            logger.exception("_get_latest_component_version: Error getting version for code={}: {}".format(code, e))
            return "legacy"

    def convert(self) -> dict:
        activities = {}
        gateways = {}
        flows = {}
        constants = {}

        start_event = None
        end_event = None

        node_incoming = {nid: [] for nid in self.nodes}
        node_outgoing = {nid: [] for nid in self.nodes}
        source_to_flows = {nid: [] for nid in self.nodes}

        for link in self.links:
            source = self._map_id(link["source"])
            target = self._map_id(link["target"])
            flow_id = self._generate_flow_id()

            flows[flow_id] = {"id": flow_id, "is_default": False, "source": source, "target": target}

            if source in node_outgoing:
                node_outgoing[source].append(flow_id)
            if target in node_incoming:
                node_incoming[target].append(flow_id)

            if source in source_to_flows:
                original_target = link["target"]
                source_to_flows[source].append((flow_id, target, original_target))

        for node_id, node in self.nodes.items():
            node_type = node["type"]

            if node_type == "StartEvent":
                start_event = self._build_start_event(node, node_outgoing.get(node_id, []))
            elif node_type == "EndEvent":
                end_event = self._build_end_event(node, node_incoming.get(node_id, []))
            elif node_type == "Activity":
                activities[node_id] = self._build_activity(
                    node, node_incoming.get(node_id, []), node_outgoing.get(node_id, [])
                )
            elif node_type in ("ParallelGateway", "ConditionalParallelGateway", "ExclusiveGateway", "ConvergeGateway"):
                gateways[node_id] = self._build_gateway(
                    node,
                    node_incoming.get(node_id, []),
                    node_outgoing.get(node_id, []),
                    source_to_flows.get(node_id, []),
                )

        for idx, var in enumerate(self.variables):
            key = var.get("key")
            if not key:
                raise KeyError('Variable 缺少必填字段 \'key\'，请确保格式为: {"type": "Variable", "key": "${变量名}", "name": "显示名"}')
            constants[key] = self._build_constant(var, idx)

        if not start_event or not end_event:
            raise ValueError("缺少开始/结束事件节点")

        return {
            "activities": activities,
            "gateways": gateways,
            "flows": flows,
            "start_event": start_event,
            "end_event": end_event,
            "constants": constants,
            "outputs": [],
        }

    def _build_activity(self, node, incoming, outgoing) -> dict:
        outgoing_value = outgoing[0] if len(outgoing) == 1 else outgoing

        raw_data = node.get("data", {})
        normalized_data = self._normalize_component_data(raw_data)

        code = node.get("code", "")
        version = self._get_latest_component_version(code)

        activity = {
            "id": node["id"],
            "name": node.get("name", ""),
            "type": "ServiceActivity",
            "incoming": incoming,
            "outgoing": outgoing_value,
            "stage_name": node.get("stage_name", node.get("name", "")),
            "component": {
                "code": code,
                "version": version,
                "data": normalized_data,
            },
        }
        activity.update(self.DEFAULT_ACTIVITY_CONFIG)
        return activity

    def _build_gateway(self, node, incoming, outgoing, outgoing_flows=None) -> dict:
        node_type = node["type"]
        outgoing_flows = outgoing_flows or []

        if node_type == "ConvergeGateway":
            outgoing_value = outgoing[0] if outgoing else ""
        else:
            outgoing_value = outgoing

        gateway = {
            "id": node["id"],
            "name": node.get("name", ""),
            "type": node_type,
            "incoming": incoming,
            "outgoing": outgoing_value,
        }

        if node_type == "ExclusiveGateway":
            gateway["conditions"] = self._build_gateway_conditions(node.get("conditions", {}), outgoing_flows)

        if node_type in ("ParallelGateway", "ConditionalParallelGateway"):
            converge_id = node.get("converge_gateway_id", "")
            if converge_id:
                converge_id = self._map_id(converge_id)
            gateway["converge_gateway_id"] = converge_id

        return gateway

    def _build_gateway_conditions(self, raw_conditions, outgoing_flows) -> dict:
        if not raw_conditions or not outgoing_flows:
            conditions = {}
            for idx, (flow_id, target_new_id, target_original_id) in enumerate(outgoing_flows):
                conditions[flow_id] = {
                    "evaluate": "True",
                    "name": "分支{}".format(idx + 1),
                    "tag": "branch_{}".format(flow_id),
                }
            return conditions

        target_to_flow = {}
        for flow_id, target_new_id, target_original_id in outgoing_flows:
            target_to_flow[target_original_id] = flow_id
            target_to_flow[target_new_id] = flow_id

        conditions = {}
        used_flows = set()

        if isinstance(raw_conditions, list):
            condition_items = []
            for cond in raw_conditions:
                if isinstance(cond, dict):
                    target_key = cond.get("target") or cond.get("target_id") or cond.get("id")
                    condition_items.append((target_key, cond))
        else:
            condition_items = list(raw_conditions.items())

        for cond_key, cond_value in condition_items:
            flow_id = target_to_flow.get(cond_key) if cond_key else None

            if not flow_id:
                for fid, _, _ in outgoing_flows:
                    if fid not in used_flows:
                        flow_id = fid
                        break

            if flow_id:
                used_flows.add(flow_id)
                expression = (
                    cond_value.get("evaluate") or cond_value.get("expression") or cond_value.get("expr") or "True"
                )
                conditions[flow_id] = {
                    "evaluate": expression,
                    "name": cond_value.get("name", ""),
                    "tag": "branch_{}".format(flow_id),
                }

        for flow_id, _, _ in outgoing_flows:
            if flow_id not in conditions:
                conditions[flow_id] = {"evaluate": "True", "name": "", "tag": "branch_{}".format(flow_id)}

        return conditions

    def _build_start_event(self, node, outgoing) -> dict:
        return {
            "id": node["id"],
            "name": node.get("name", ""),
            "type": "EmptyStartEvent",
            "incoming": "",
            "outgoing": outgoing[0] if outgoing else "",
            "labels": [],
        }

    def _build_end_event(self, node, incoming) -> dict:
        return {
            "id": node["id"],
            "name": node.get("name", ""),
            "type": "EmptyEndEvent",
            "incoming": incoming,
            "outgoing": "",
            "labels": [],
        }

    def _build_constant(self, var, index) -> dict:
        return {
            "key": var["key"],
            "name": var.get("name", ""),
            "value": var.get("value", ""),
            "desc": var.get("description", ""),
            "custom_type": var.get("custom_type", "input"),
            "source_type": var.get("source_type", "custom"),
            "source_tag": "",
            "source_info": {},
            "show_type": var.get("show_type", "show"),
            "validation": var.get("validation", ""),
            "index": index,
            "version": "legacy",
            "form_schema": {},
            "hook": False,
            "need_render": True,
        }
