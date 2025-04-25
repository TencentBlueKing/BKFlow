# -*- coding: utf-8 -*-
from typing import Dict, Any

from bkflow.pipeline_converter.data_models import Node
from bkflow.pipeline_converter.validators.base import BaseValidator


class NodeTypeValidator(BaseValidator):
    def __init__(self, node_type: str):
        self.node_type = node_type

    def validate(self, data: Node, *args, **kwargs):
        if data.type != self.node_type:
            raise ValueError(f"Type of node {data.id} must be {self.node_type}")


class JsonNodeTypeValidator(NodeTypeValidator):
    def validate(self, data: Dict[str, Any], *args, **kwargs):
        if data.get("type") != self.node_type:
            raise ValueError(f"Type of node {data.get('id')} must be {self.node_type}")
