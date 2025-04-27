# -*- coding: utf-8 -*-
from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter
from bkflow.pipeline_converter.converters.json_to_data_model.node import (
    ComponentNodeConverter,
    EndNodeConverter,
    StartNodeConverter,
)
from bkflow.pipeline_converter.data_models import Pipeline
from bkflow.pipeline_converter.hub import CONVERTER_HUB


class PipelineConverter(JsonToDataModelConverter):

    def convert(self) -> dict:
        """
        将 json 转换成 DataModel
        """
        self.target_data = Pipeline(id=self.source_data["id"], name=self.source_data["name"], nodes=[], constants=[])

        target_nodes = []
        # TODO: 这块考虑抽象公共逻辑
        node_type_converter_cls_name_map = {
            NodeTypes.COMPONENT.value: ComponentNodeConverter.__name__,
            NodeTypes.END_EVENT.value: EndNodeConverter.__name__,
            NodeTypes.START_EVENT.value: StartNodeConverter.__name__,
        }
        for node in self.source_data.get("nodes", []):
            converter_cls = CONVERTER_HUB.get_converter_cls(
                source=self.source, target=self.target, converter_name=node_type_converter_cls_name_map[node["type"]]
            )
            target_nodes.append(converter_cls(node).convert())
        self.target_data.nodes = target_nodes

        return self.target_data
