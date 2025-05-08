# -*- coding: utf-8 -*-
from typing import List

from pipeline.core.constants import PE
from pipeline.parser.utils import replace_all_id
from pipeline.utils.uniqid import line_uniqid

from bkflow.pipeline_converter.constants import ConstantTypes, NodeTypes
from bkflow.pipeline_converter.converters.base import DataModelToPipelineTreeConverter
from bkflow.pipeline_converter.converters.data_model_to_web_pipeline.constant import (
    ComponentInputConverter,
    ComponentOutputConverter,
    CustomConstantConverter,
)
from bkflow.pipeline_converter.converters.data_model_to_web_pipeline.gateway import (
    ConditionalParallelGatewayConverter,
    ConvergeGatewayConverter,
    ExclusiveGatewayConverter,
    ParallelGatewayConverter,
)
from bkflow.pipeline_converter.converters.data_model_to_web_pipeline.node import (
    ComponentNodeConverter,
    EndNodeConverter,
    StartNodeConverter,
)
from bkflow.pipeline_converter.data_models import Flow, Node, Pipeline
from bkflow.pipeline_converter.hub import ConverterHub


class PipelineConverter(DataModelToPipelineTreeConverter):
    def convert(self) -> dict:
        """
        将数据模型转换为 web 流程树
        """
        pipeline: Pipeline = self.source_data
        nodes: List[Node] = pipeline.nodes
        constants = pipeline.constants
        self.target_data = {
            PE.id: pipeline.id,
            PE.name: pipeline.name,
            PE.end_event: {},
            PE.start_event: {},
            PE.activities: {},
            PE.gateways: {},
            PE.flows: {},
            PE.constants: {},
            PE.outputs: [],
        }
        gateway_mapping = {
            "parallel_gateway": ParallelGatewayConverter,
            "exclusive_gateway": ExclusiveGatewayConverter,
            "conditional_parallel_gateway": ConditionalParallelGatewayConverter,
            "converge_gateway": ConvergeGatewayConverter,
        }

        # 单节点相关转换
        for node in nodes:
            if node.type == NodeTypes.COMPONENT.value:
                self.target_data[PE.activities][node.id] = ComponentNodeConverter(node).convert()
            elif node.type == NodeTypes.END_EVENT.value:
                self.target_data[PE.end_event] = EndNodeConverter(node).convert()
            elif node.type == NodeTypes.START_EVENT.value:
                self.target_data[PE.start_event] = StartNodeConverter(node).convert()
            elif node.type in NodeTypes.GATEWAYS:
                gateway_data = gateway_mapping[node.type](node).convert()
                self.target_data[PE.gateways][node.id] = gateway_data

        # 常量数据转换
        self.target_data[PE.constants] = self.constant_converter(constants)
        # 连线数据转换
        flows = self._generate_flows_by_nodes(nodes)
        self.target_data[PE.flows] = {flow.id: flow.dict() for flow in flows}

        # 补充节点数据的 incoming 和 outgoing
        for flow in flows:
            source_node = self._get_converted_node(self.target_data, flow.source)
            self.add_node_incoming_or_outgoing(source_node, "outgoing", flow.id)
            target_node = self._get_converted_node(self.target_data, flow.target)
            self.add_node_incoming_or_outgoing(target_node, "incoming", flow.id)

        self.remap_condition_keys_to_outgoing(self.target_data[PE.gateways], flows)
        # 这里确保每次转换后 id 都是唯一的，避免重复
        replace_all_id(self.target_data)
        return self.target_data

    def constant_converter(self, constants):
        constant_type_converter_cls_name_map = {
            ConstantTypes.CUSTOM_CONSTANT.value: CustomConstantConverter.__name__,
            ConstantTypes.COMPONENT_INPUTS_CONSTANT.value: ComponentInputConverter.__name__,
            ConstantTypes.COMPONENT_OUTPUTS_CONSTANT.value: ComponentOutputConverter.__name__,
        }
        result = {}
        for index, constant in enumerate(constants):
            converter_cls = ConverterHub.get_converter_cls(
                source=self.source,
                target=self.target,
                converter_name=constant_type_converter_cls_name_map[constant.type],
            )
            constant_data = converter_cls(constant).convert()
            constant_data["index"] = index
            result[constant.key] = constant_data
        return result

    @staticmethod
    def _generate_flows_by_nodes(nodes: List[Node]) -> List[Flow]:
        """生成流程中的连线信息"""
        flows = []
        for node in nodes:
            if not node.next:
                continue
            if isinstance(node.next, str):
                flows.append(Flow(id=line_uniqid(), source=node.id, target=node.next))
            if isinstance(node.next, list):
                flows.extend(
                    [Flow(id=line_uniqid(), source=node.id, target=next_node_id) for next_node_id in node.next]
                )

        return flows

    @staticmethod
    def _get_converted_node(pipeline_tree, node_id: str):
        node = pipeline_tree[PE.activities].get(node_id) or pipeline_tree[PE.gateways].get(node_id)
        if node:
            return node
        if node_id == pipeline_tree[PE.start_event]["id"]:
            return pipeline_tree[PE.start_event]
        if node_id == pipeline_tree[PE.end_event]["id"]:
            return pipeline_tree[PE.end_event]
        raise ValueError(f"未找到节点：{node_id}")

    @staticmethod
    def add_node_incoming_or_outgoing(node, field, flow_id):
        if isinstance(node[field], list):
            node[field].append(flow_id)
            return
        elif isinstance(node[field], str):
            node[field] = flow_id
            return
        raise ValueError(f"{field}字段类型错误，期望list或str，实际为{type(node[field])}")

    @staticmethod
    def remap_condition_keys_to_outgoing(gateways_data, flows):
        flow_id_map = {(flow.source, flow.target): flow.id for flow in flows}

        for gateway_id, gateway in gateways_data.items():
            if gateway.get("type") not in [PE.ExclusiveGateway, PE.ConditionalParallelGateway]:
                continue

            default_condition = gateway.get("default_condition")
            if default_condition:
                default_condition_node = default_condition["next"]
                flow_id = flow_id_map.get((gateway_id, default_condition_node))
                gateway["default_condition"] = {"name": default_condition["name"], "flow_id": flow_id}

            new_conditions = {}
            for condition in gateway["conditions"]:
                condition_node = condition["next"]
                flow_id = flow_id_map.get((gateway_id, condition_node))
                new_conditions[flow_id] = {"name": condition["name"], "evaluate": condition["evaluate"]}
            gateway["conditions"] = new_conditions
