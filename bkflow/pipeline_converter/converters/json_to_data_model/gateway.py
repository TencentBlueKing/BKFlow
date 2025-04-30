# -*- coding: utf-8 -*-

from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter
from bkflow.pipeline_converter.data_models import (
    Condition,
    ConditionalParallelGateway,
    ConvergeGateway,
    ExclusiveGateway,
    ParallelGateway,
)
from bkflow.pipeline_converter.validators.gateway import JsonGatewayValidator
from bkflow.pipeline_converter.validators.node import JsonNodeTypeValidator


class ConditionConverter(JsonToDataModelConverter):
    def convert(self):
        self.target_data = []
        for condition in self.source_data:
            condition_data = Condition(name=condition["name"], next_node=condition["next_node"])
            if condition.get("is_default") is True:
                setattr(condition_data, "is_default", condition["is_default"])
            else:
                setattr(condition_data, "expr", condition["expr"])
            self.target_data.append(condition_data)
        return self.target_data


class ParallelGatewayConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(node_type=NodeTypes.PARALLEL_GATEWAY.value)]

    def convert(self):
        self.target_data = ParallelGateway(
            id=self.source_data["id"],
            name=self.source_data["name"],
            next=self.source_data["next"],
            converge_gateway_id=self.source_data["converge_gateway_id"],
        )
        return self.target_data


class ExclusiveGatewayConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(node_type=NodeTypes.EXCLUSIVE_GATEWAY.value), JsonGatewayValidator()]

    def convert(self):
        self.target_data = ExclusiveGateway(
            id=self.source_data["id"],
            name=self.source_data["name"],
            next=self.source_data["next"],
            conditions=ConditionConverter(self.source_data["conditions"]).convert(),
        )
        if self.source_data.get("lang"):
            setattr(self.target_data, "lang", self.source_data["lang"])
        return self.target_data


class ConditionalParallelGatewayConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(node_type=NodeTypes.CONDITIONAL_PARALLEL_GATEWAY.value), JsonGatewayValidator()]

    def convert(self):
        self.target_data = ConditionalParallelGateway(
            id=self.source_data["id"],
            name=self.source_data["name"],
            next=self.source_data["next"],
            conditions=ConditionConverter(self.source_data["conditions"]).convert(),
            converge_gateway_id=self.source_data["converge_gateway_id"],
        )
        if self.source_data.get("lang"):
            setattr(self.target_data, "lang", self.source_data["lang"])
        return self.target_data


class ConvergeGatewayConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(node_type=NodeTypes.CONVERGE_GATEWAY.value)]

    def convert(self):
        self.target_data = ConvergeGateway(
            id=self.source_data["id"],
            name=self.source_data["name"],
            next=self.source_data["next"],
        )
        return self.target_data
