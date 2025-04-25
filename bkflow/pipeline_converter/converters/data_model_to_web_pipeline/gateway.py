# -*- coding: utf-8 -*-
from typing import List

from pipeline.core.constants import PE

from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.converters.base import DataModelToPipelineTreeConverter
from bkflow.pipeline_converter.data_models import (
    Condition,
    ConditionalParallelGateway,
    ConvergeGateway,
    ExclusiveGateway,
    ParallelGateway,
)
from bkflow.pipeline_converter.validators.gateway import GatewayTypeValidator


class ConditionConverter(DataModelToPipelineTreeConverter):
    def convert(self, *args, **kwargs):
        node_data: List[Condition] = self.source_data
        self.target_data = {}
        for node in node_data:
            self.target_data[node.id] = {"name": node.name, "lang": node.lang, "expr": node.expr}
        return self.target_data


class ParallelGatewayConverter(DataModelToPipelineTreeConverter):
    validators = [GatewayTypeValidator(node_type=NodeTypes.PARALLEL_GATEWAY.value)]

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
    validators = [GatewayTypeValidator(node_type=NodeTypes.EXCLUSIVE_GATEWAY.value)]

    def convert(self, *args, **kwargs):
        node: ExclusiveGateway = self.source_data
        self.target_data = {
            "id": node.id,
            "type": PE.ExclusiveGateway,
            "name": node.name,
            "incoming": [],
            "outgoing": [],
            "conditions": ConditionConverter(node.conditions).convert(),
        }
        return self.target_data


class ConditionalParallelGatewayConverter(DataModelToPipelineTreeConverter):
    validators = [GatewayTypeValidator(node_type=NodeTypes.CONDITIONAL_PARALLEL_GATEWAY.value)]

    def convert(self, *args, **kwargs):
        node: ConditionalParallelGateway = self.source_data
        self.target_data = {
            "id": node.id,
            "type": PE.ConditionalParallelGateway,
            "name": node.name,
            "incoming": [],
            "outgoing": [],
            "conditions": ConditionConverter(node.conditions).convert(),
            "converge_gateway_id": node.converge_gateway_id,
        }
        return self.target_data


class ConvergeGatewayConverter(DataModelToPipelineTreeConverter):
    validators = [GatewayTypeValidator(node_type=NodeTypes.CONVERGE_GATEWAY.value)]

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
