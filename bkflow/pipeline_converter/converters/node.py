# -*- coding: utf-8 -*-
from pipeline.utils.uniqid import node_uniqid

from bkflow.pipeline_converter.constants import DataTypes, NodeTypes
from bkflow.pipeline_converter.converters.base import BaseConverter
from bkflow.pipeline_converter.validators.node import NodeTypeValidator


class StartNodeConverter(BaseConverter):
    source = DataTypes.DATA_MODEL.value
    target = DataTypes.PIPELINE_TREE.value
    validators = [NodeTypeValidator(node_type=NodeTypes.START_EVENT.value)]

    def convert(self, *args, **kwargs):
        self.target_data = {
            "start_event": {"id": node_uniqid(), "name": "", "type": "EmptyStartEvent", "incoming": "", "outgoing": ""}
        }
        return self.target_data


class EndNodeConverter(BaseConverter):
    source = DataTypes.DATA_MODEL.value
    target = DataTypes.PIPELINE_TREE.value
    validators = [NodeTypeValidator(node_type=NodeTypes.END_EVENT.value)]

    def convert(self, *args, **kwargs):
        self.target_data = {
            "end_event": {"id": node_uniqid(), "name": "", "type": "EmptyEndEvent", "incoming": [], "outgoing": ""}
        }
        return self.target_data
