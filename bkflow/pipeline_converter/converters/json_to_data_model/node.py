# -*- coding: utf-8 -*-

from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter
from bkflow.pipeline_converter.converters.json_to_data_model.component import ComponentConverter
from bkflow.pipeline_converter.data_models import (
    EmptyStartNode,
    EmptyEndNode,
    ComponentNode,
    AutoRetryConfig,
    TimeoutConfig,
)
from bkflow.pipeline_converter.validators.node import JsonNodeTypeValidator


class StartNodeConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(node_type=NodeTypes.START_EVENT.value)]

    def convert(self, *args, **kwargs):
        self.target_data = EmptyStartNode(
            id=self.source_data["id"], name=self.source_data.get("name", ""), next=self.source_data["next"]
        )
        return self.target_data


class EndNodeConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(node_type=NodeTypes.END_EVENT.value)]

    def convert(self, *args, **kwargs):
        self.target_data = EmptyEndNode(id=self.source_data["id"], name=self.source_data.get("name", ""))
        return self.target_data


class ComponentNodeConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(node_type=NodeTypes.COMPONENT.value)]

    def convert(self, *args, **kwargs):
        self.target_data = ComponentNode(
            id=self.source_data["id"],
            name=self.source_data["name"],
            next=self.source_data["next"],
            component=ComponentConverter(self.source_data["component"]).convert(),
        )

        optional_field_data_model_map = {
            "skippable": None,
            "retryable": None,
            "error_ignorable": None,
            "auto_retry": AutoRetryConfig,
            "timeout_config": TimeoutConfig,
        }
        for field, data_model in optional_field_data_model_map.items():
            if field not in self.source_data:
                continue
            setattr(
                self.target_data,
                field,
                data_model(**self.source_data[field]) if data_model else self.source_data[field],
            )
        return self.target_data
