# -*- coding: utf-8 -*-
from bkflow.pipeline_converter.data_models import Node
from bkflow.pipeline_converter.validators.base import BaseValidator


class NodeTypeValidator(BaseValidator):
    def __init__(self, node_type: str):
        self.node_type = node_type

    def validate(self, data: Node, *args, **kwargs):
        if data.type != self.node_type:
            raise ValueError(f"Type of node {data.id} must be {self.node_type}")
