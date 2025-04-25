# -*- coding: utf-8 -*-

from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter
from bkflow.pipeline_converter.data_models import EmptyStartNode, EmptyEndNode, ComponentNode
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
        self.target_data = {}
        return self.target_data
