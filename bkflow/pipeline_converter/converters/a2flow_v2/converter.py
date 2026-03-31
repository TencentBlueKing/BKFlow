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
import uuid
from collections import defaultdict, deque

from bkflow.pipeline_converter.constants import (
    BRANCH_GATEWAY_TYPES,
    GATEWAY_TYPES,
    RESERVED_IDS,
    NodeType,
)
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import (
    A2FlowNode,
    A2FlowPipeline,
)
from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import build_gateway
from bkflow.pipeline_converter.converters.a2flow_v2.node_builder import (
    build_activity,
    build_end_event,
    build_start_event,
)
from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import (
    PluginResolver,
)
from bkflow.pipeline_converter.converters.a2flow_v2.variable_builder import (
    build_constant,
)
from bkflow.pipeline_converter.exceptions import (
    A2FlowConvertError,
    A2FlowValidationError,
    ErrorTypes,
)

logger = logging.getLogger("root")


class A2FlowV2Converter:
    """
    a2flow v2.0 JSON → pipeline_tree dict 转换器

    处理流程:
    1. Pydantic DataModel 解析输入
    2. 隐式注入 StartEvent / EndEvent
    3. 校验节点引用、条件数量等
    4. 批量识别插件类型
    5. 生成 flow 连接 (从 next 字段)
    6. 推断 converge_gateway_id
    7. 组装 pipeline_tree
    """

    def __init__(
        self, a2flow_data: dict, space_id: int, username: str = "", scope_type: str = None, scope_value: str = None
    ):
        self.a2flow_data = a2flow_data
        self.space_id = space_id
        self.username = username
        self.scope_type = scope_type
        self.scope_value = scope_value

    def convert(self) -> dict:
        pipeline = A2FlowPipeline(**self.a2flow_data)
        normalized_version = str(pipeline.version)
        if normalized_version in ("2", "2.0"):
            pipeline.version = "2.0"
        if pipeline.version != "2.0":
            raise A2FlowValidationError(
                A2FlowConvertError(
                    error_type=ErrorTypes.UNSUPPORTED_VERSION,
                    message="不支持的 a2flow 版本: '{}'".format(pipeline.version),
                    field="version",
                    value=pipeline.version,
                    hint="当前仅支持版本: 2.0",
                )
            )

        nodes = list(pipeline.nodes)
        nodes = self._inject_start_end(nodes)

        node_map = {}
        for node in nodes:
            node_map[node.id] = node

        self._validate(nodes, node_map)

        id_mapping = self._generate_id_mapping(nodes)

        plugin_resolver = PluginResolver(
            self.space_id, username=self.username, scope_type=self.scope_type, scope_value=self.scope_value
        )
        activity_infos = [
            {"code": n.code, "plugin_type": n.plugin_type} for n in nodes if n.type == NodeType.ACTIVITY and n.code
        ]
        plugin_map = plugin_resolver.resolve_batch(activity_infos)

        flows, node_incoming, node_outgoing, next_to_flow = self._build_flows(nodes, id_mapping)

        self._infer_converge_gateway_ids(nodes, node_map, id_mapping)

        activities = {}
        gateways = {}
        start_event = None
        end_event = None

        for node in nodes:
            new_id = id_mapping[node.id]
            incoming = node_incoming.get(new_id, [])
            outgoing = node_outgoing.get(new_id, [])

            if node.type == NodeType.START_EVENT:
                start_event = build_start_event(
                    node_id=new_id,
                    name=node.name,
                    outgoing=outgoing[0] if outgoing else "",
                )
            elif node.type == NodeType.END_EVENT:
                end_event = build_end_event(
                    node_id=new_id,
                    name=node.name,
                    incoming=incoming,
                )
            elif node.type == NodeType.ACTIVITY:
                plugin = plugin_map.get((node.code, node.plugin_type))
                outgoing_val = outgoing[0] if len(outgoing) == 1 else outgoing
                activities[new_id] = build_activity(
                    node_id=new_id,
                    name=node.name,
                    data=node.data,
                    plugin=plugin,
                    incoming=incoming,
                    outgoing=outgoing_val,
                    stage_name=node.stage_name,
                )
            elif node.type in GATEWAY_TYPES:
                default_next_flow_id = None
                if node.type == NodeType.EXCLUSIVE_GATEWAY and node.default_next:
                    default_next_flow_id = next_to_flow.get((node.id, node.default_next))

                converge_gw_id = None
                if node.converge_gateway_id:
                    converge_gw_id = id_mapping.get(node.converge_gateway_id, node.converge_gateway_id)

                conditions_data = None
                if node.conditions:
                    conditions_data = [{"evaluate": c.evaluate, "name": c.name} for c in node.conditions]

                gateways[new_id] = build_gateway(
                    node_id=new_id,
                    name=node.name,
                    node_type=node.type,
                    incoming=incoming,
                    outgoing=outgoing,
                    conditions=conditions_data,
                    default_next_flow_id=default_next_flow_id,
                    converge_gateway_id=converge_gw_id,
                )

        constants = {}
        for idx, var in enumerate(pipeline.variables):
            constants[var.key] = build_constant(var, idx)

        return {
            "activities": activities,
            "gateways": gateways,
            "flows": flows,
            "start_event": start_event,
            "end_event": end_event,
            "constants": constants,
            "outputs": [],
            "canvas_mode": "horizontal",
        }

    def _inject_start_end(self, nodes):
        has_start = any(n.type == NodeType.START_EVENT for n in nodes)
        has_end = any(n.type == NodeType.END_EVENT for n in nodes)

        if not has_start:
            first_node_id = nodes[0].id if nodes else "end"
            start_node = A2FlowNode(id="start", name="开始", type=NodeType.START_EVENT, next=first_node_id)
            nodes.insert(0, start_node)

        if not has_end:
            end_node = A2FlowNode(id="end", name="结束", type=NodeType.END_EVENT)
            nodes.append(end_node)

        return nodes

    def _validate(self, nodes, node_map):
        errors = []
        seen_ids = set()
        valid_ids = set(node_map.keys())

        for node in nodes:
            if node.id in RESERVED_IDS and (
                (node.id == "start" and node.type != NodeType.START_EVENT)
                or (node.id == "end" and node.type != NodeType.END_EVENT)
            ):
                errors.append(
                    A2FlowConvertError(
                        error_type=ErrorTypes.RESERVED_ID_CONFLICT,
                        message="保留 ID '{}' 只能用于对应的开始/结束事件节点".format(node.id),
                        node_id=node.id,
                        field="id",
                        value=node.id,
                        hint="start 仅允许 StartEvent，end 仅允许 EndEvent",
                    )
                )

            if node.type != NodeType.END_EVENT and node.next is None:
                errors.append(
                    A2FlowConvertError(
                        error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                        message="节点 '{}' 缺少 next 字段".format(node.id),
                        node_id=node.id,
                        field="next",
                    )
                )

            if node.type in (
                NodeType.PARALLEL_GATEWAY,
                NodeType.EXCLUSIVE_GATEWAY,
                NodeType.CONDITIONAL_PARALLEL_GATEWAY,
            ):
                if node.next is not None and not isinstance(node.next, list):
                    errors.append(
                        A2FlowConvertError(
                            error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                            message="节点 '{}' 的 next 必须是数组".format(node.id),
                            node_id=node.id,
                            field="next",
                            value=node.next,
                            hint="分支网关的 next 需为分支目标 ID 数组",
                        )
                    )

            if node.type in (NodeType.ACTIVITY, NodeType.START_EVENT, NodeType.CONVERGE_GATEWAY):
                if isinstance(node.next, list):
                    errors.append(
                        A2FlowConvertError(
                            error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                            message="节点 '{}' 的 next 必须是单个字符串 ID".format(node.id),
                            node_id=node.id,
                            field="next",
                            value=node.next,
                            hint="该类型节点只允许一个下游节点",
                        )
                    )

            if node.id in seen_ids:
                errors.append(
                    A2FlowConvertError(
                        error_type=ErrorTypes.DUPLICATE_NODE_ID,
                        message="重复的节点 ID: '{}'".format(node.id),
                        node_id=node.id,
                    )
                )
            seen_ids.add(node.id)

            if node.next is not None:
                next_ids = [node.next] if isinstance(node.next, str) else node.next
                for nid in next_ids:
                    if nid not in valid_ids:
                        errors.append(
                            A2FlowConvertError(
                                error_type=ErrorTypes.INVALID_REFERENCE,
                                message="节点 '{}' 的 next 引用了未定义的节点 '{}'".format(node.id, nid),
                                node_id=node.id,
                                field="next",
                                value=nid,
                                hint="可用的节点 ID: {}".format(sorted(valid_ids)),
                            )
                        )

            if node.type in (NodeType.EXCLUSIVE_GATEWAY, NodeType.CONDITIONAL_PARALLEL_GATEWAY):
                if not node.conditions:
                    errors.append(
                        A2FlowConvertError(
                            error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                            message="节点 '{}' 缺少 conditions 字段".format(node.id),
                            node_id=node.id,
                            field="conditions",
                        )
                    )
                if node.conditions and node.next:
                    next_count = len(node.next) if isinstance(node.next, list) else 1
                    if len(node.conditions) != next_count:
                        errors.append(
                            A2FlowConvertError(
                                error_type=ErrorTypes.CONDITIONS_MISMATCH,
                                message="节点 '{}' 的 conditions 数量 ({}) 与 next 分支数 ({}) 不一致".format(
                                    node.id, len(node.conditions), next_count
                                ),
                                node_id=node.id,
                                field="conditions",
                            )
                        )

            if node.type == NodeType.EXCLUSIVE_GATEWAY and node.default_next:
                next_ids = node.next if isinstance(node.next, list) else [node.next] if node.next else []
                if node.default_next not in next_ids:
                    errors.append(
                        A2FlowConvertError(
                            error_type=ErrorTypes.INVALID_DEFAULT_NEXT,
                            message="节点 '{}' 的 default_next '{}' 不在 next 列表中".format(node.id, node.default_next),
                            node_id=node.id,
                            field="default_next",
                            value=node.default_next,
                            hint="default_next 必须是 next 中的某一个: {}".format(next_ids),
                        )
                    )

            if node.type == NodeType.ACTIVITY and not node.code:
                errors.append(
                    A2FlowConvertError(
                        error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                        message="Activity 节点 '{}' 缺少 code 字段".format(node.id),
                        node_id=node.id,
                        field="code",
                    )
                )

        if errors:
            raise A2FlowValidationError(errors)

    def _generate_id_mapping(self, nodes):
        mapping = {}
        for node in nodes:
            mapping[node.id] = "n{}".format(uuid.uuid4().hex[:31])
        return mapping

    def _build_flows(self, nodes, id_mapping):
        flows = {}
        node_incoming = defaultdict(list)
        node_outgoing = defaultdict(list)
        next_to_flow = {}

        for node in nodes:
            if node.next is None:
                continue
            next_ids = [node.next] if isinstance(node.next, str) else node.next
            source = id_mapping[node.id]

            for target_original_id in next_ids:
                target = id_mapping.get(target_original_id, target_original_id)
                flow_id = "l{}".format(uuid.uuid4().hex[:30])
                is_default = bool(
                    node.type == NodeType.EXCLUSIVE_GATEWAY
                    and getattr(node, "default_next", None)
                    and target_original_id == node.default_next
                )
                flows[flow_id] = {
                    "id": flow_id,
                    "is_default": is_default,
                    "source": source,
                    "target": target,
                }
                node_outgoing[source].append(flow_id)
                node_incoming[target].append(flow_id)
                next_to_flow[(node.id, target_original_id)] = flow_id

        return flows, dict(node_incoming), dict(node_outgoing), next_to_flow

    def _infer_converge_gateway_ids(self, nodes, node_map, id_mapping):
        needs_infer = {}
        for node in nodes:
            if node.type in (NodeType.PARALLEL_GATEWAY, NodeType.CONDITIONAL_PARALLEL_GATEWAY):
                if not node.converge_gateway_id:
                    needs_infer[node.id] = node

        if not needs_infer:
            return

        adj = defaultdict(list)
        in_degree = defaultdict(int)
        for node in nodes:
            in_degree.setdefault(node.id, 0)
            if node.next is not None:
                next_ids = [node.next] if isinstance(node.next, str) else node.next
                for nid in next_ids:
                    adj[node.id].append(nid)
                    in_degree[nid] = in_degree.get(nid, 0) + 1

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        topo_order = []
        while queue:
            curr = queue.popleft()
            topo_order.append(curr)
            for nxt in adj[curr]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        stack = []
        for nid in topo_order:
            node = node_map.get(nid)
            if not node:
                continue
            if node.type in BRANCH_GATEWAY_TYPES:
                stack.append(nid)
            elif node.type == NodeType.CONVERGE_GATEWAY and stack:
                branch_id = stack.pop()
                if branch_id in needs_infer:
                    needs_infer[branch_id].converge_gateway_id = nid

        unresolved = [node_id for node_id, node in needs_infer.items() if not node.converge_gateway_id]
        if unresolved:
            raise A2FlowValidationError(
                [
                    A2FlowConvertError(
                        error_type=ErrorTypes.CONVERGE_INFER_FAILED,
                        message="节点 '{}' 无法自动推断 converge_gateway_id".format(node_id),
                        node_id=node_id,
                        field="converge_gateway_id",
                        hint="请补充显式 converge_gateway_id，或检查网关拓扑是否缺少汇聚节点",
                    )
                    for node_id in unresolved
                ]
            )
