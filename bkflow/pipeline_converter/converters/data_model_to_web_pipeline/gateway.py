# -*- coding: utf-8 -*-
from typing import List

from pipeline.core.constants import PE

from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.converters.base import DataModelToPipelineTreeConverter
from bkflow.pipeline_converter.data_models import (
    ConditionalParallelGateway,
    ConvergeGateway,
    ExclusiveGateway,
    ExprCondition,
    ParallelGateway,
)
from bkflow.pipeline_converter.validators.gateway import GatewayConditionValidator
from bkflow.pipeline_converter.validators.node import NodeTypeValidator


class ConditionConverter(DataModelToPipelineTreeConverter):
    def convert(self, *args, **kwargs):
        condition_data: List[ExprCondition] = self.source_data
        self.target_data = []
        for condition in condition_data:
            self.target_data.append({"name": condition.name, "evaluate": condition.expr, "next": condition.next})
        return self.target_data


class ParallelGatewayConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(node_type=NodeTypes.PARALLEL_GATEWAY.value)]

    def convert(self, *args, **kwargs):
        node: ParallelGateway = self.source_data
        self.target_data = {
            "id": node.id,
            "type": PE.ParallelGateway,
            "name": node.name,
            "incoming": [],
            "outgoing": [],
            "converge_gateway_id": node.converge_gateway_id,
        }
        return self.target_data


class ExclusiveGatewayConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(node_type=NodeTypes.EXCLUSIVE_GATEWAY.value), GatewayConditionValidator()]

    def convert(self, *args, **kwargs):
        node: ExclusiveGateway = self.source_data
        self.target_data = {
            "id": node.id,
            "type": PE.ExclusiveGateway,
            "name": node.name,
            "incoming": [],
            "outgoing": [],
            "conditions": ConditionConverter(node.conditions).convert(),
            "extra_info": {"parse_lang": node.lang},
        }
        if node.default_condition:
            self.target_data["default_condition"] = node.default_condition
        return self.target_data


class ConditionalParallelGatewayConverter(DataModelToPipelineTreeConverter):
    validators = [
        NodeTypeValidator(node_type=NodeTypes.CONDITIONAL_PARALLEL_GATEWAY.value),
        GatewayConditionValidator(),
    ]

    def convert(self, *args, **kwargs):
        node: ConditionalParallelGateway = self.source_data
        self.target_data = {
            "id": node.id,
            "type": PE.ConditionalParallelGateway,
            "name": node.name,
            "incoming": [],
            "outgoing": [],
            "conditions": ConditionConverter(node.conditions).convert(),
            "extra_info": {"parse_lang": node.lang},
            "converge_gateway_id": node.converge_gateway_id,
        }
        if node.default_condition:
            self.target_data["default_condition"] = node.default_condition
        return self.target_data


class ConvergeGatewayConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(node_type=NodeTypes.CONVERGE_GATEWAY.value)]

    def convert(self, *args, **kwargs):
        node: ConvergeGateway = self.source_data
        self.target_data = {
            "id": node.id,
            "type": PE.ConvergeGateway,
            "name": node.name,
            "incoming": [],
            "outgoing": "",
        }
        return self.target_data
