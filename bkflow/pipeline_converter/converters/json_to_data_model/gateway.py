# -*- coding: utf-8 -*-

from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter
from bkflow.pipeline_converter.data_models import (
    ConditionalParallelGateway,
    ConvergeGateway,
    DefaultCondition,
    ExclusiveGateway,
    ExprCondition,
    ParallelGateway,
)
from bkflow.pipeline_converter.validators.gateway import JsonGatewayValidator
from bkflow.pipeline_converter.validators.node import JsonNodeTypeValidator


class ConditionConverter(JsonToDataModelConverter):
    def convert(self):
        self.target_data = []
        for condition in self.source_data:
            condition_data = ExprCondition(name=condition["name"], expr=condition["expr"], next=condition["next"])
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
        optional_field_data_model_map = {"lang": None, "default_condition": DefaultCondition}
        for field, data_model in optional_field_data_model_map.items():
            if field not in self.source_data:
                continue
            setattr(
                self.target_data,
                field,
                data_model(**self.source_data[field]) if data_model else self.source_data[field],
            )
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
        optional_field_data_model_map = {"lang": None, "default_condition": DefaultCondition}
        for field, data_model in optional_field_data_model_map.items():
            if field not in self.source_data:
                continue
            setattr(
                self.target_data,
                field,
                data_model(**self.source_data[field]) if data_model else self.source_data[field],
            )
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
