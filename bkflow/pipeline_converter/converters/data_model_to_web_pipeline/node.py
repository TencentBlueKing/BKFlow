# -*- coding: utf-8 -*-
from pipeline.core.constants import PE

from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.converters.base import DataModelToPipelineTreeConverter
from bkflow.pipeline_converter.converters.data_model_to_web_pipeline.component import (
    ComponentConverter,
)
from bkflow.pipeline_converter.data_models import ComponentNode
from bkflow.pipeline_converter.validators.node import NodeTypeValidator


class StartNodeConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(node_type=NodeTypes.START_EVENT.value)]

    def convert(self, *args, **kwargs):
        self.target_data = {
            "id": self.source_data.id,
            "name": "",
            "type": "EmptyStartEvent",
            "incoming": "",
            "outgoing": "",
        }
        return self.target_data


class EndNodeConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(node_type=NodeTypes.END_EVENT.value)]

    def convert(self, *args, **kwargs):
        self.target_data = {
            "id": self.source_data.id,
            "name": "",
            "type": "EmptyEndEvent",
            "incoming": [],
            "outgoing": "",
        }
        return self.target_data


class ComponentNodeConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(node_type=NodeTypes.COMPONENT.value)]

    def convert(self, *args, **kwargs):
        node: ComponentNode = self.source_data
        self.target_data = {
            "id": node.id,
            "name": node.name,
            "type": PE.ServiceActivity,
            "optional": True,
            "incoming": [],
            "outgoing": "",
            "component": ComponentConverter(node.component).convert(),
            "error_ignorable": node.error_ignorable,
            "skippable": node.skippable,
            "retryable": node.retryable,
            "auto_retry": node.auto_retry.dict(),
            "timeout_config": node.timeout_config.dict(),
        }

        return self.target_data
