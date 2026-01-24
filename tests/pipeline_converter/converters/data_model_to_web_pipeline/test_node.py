# -*- coding: utf-8 -*-

import pytest

from bkflow.pipeline_converter.constants import DataTypes
from bkflow.pipeline_converter.converters.data_model_to_web_pipeline.node import (
    ComponentNodeConverter,
    EndNodeConverter,
    StartNodeConverter,
)
from bkflow.pipeline_converter.data_models import (
    AutoRetryConfig,
    Component,
    ComponentNode,
    Node,
    TimeoutConfig,
)


class TestNodeConverter:
    source_type = DataTypes.DATA_MODEL.value
    target_type = DataTypes.WEB_PIPELINE.value
    source_node_id = "node_123"

    def test_start_node_converter_success(self):
        json_data = {
            "id": self.source_node_id,
            "type": "start_event",
        }
        source_data = Node(**json_data)
        converter = StartNodeConverter(source_data=source_data)
        result = converter.convert()

        assert converter.source == self.source_type
        assert converter.target == self.target_type
        assert result == {
            "id": self.source_node_id,
            "name": "",
            "type": "EmptyStartEvent",
            "incoming": "",
            "outgoing": "",
        }

    def test_start_mode_converter_fail(self):
        json_data = {
            "id": self.source_node_id,
            "type": "start",
        }
        source_data = Node(**json_data)
        with pytest.raises(ValueError):
            StartNodeConverter(source_data=source_data)

    def test_end_node_converter_success(self):
        json_data = {
            "id": self.source_node_id,
            "type": "end_event",
        }
        source_data = Node(**json_data)
        converter = EndNodeConverter(source_data=source_data)
        result = converter.convert()

        assert converter.source == self.source_type
        assert converter.target == self.target_type
        assert result == {
            "id": self.source_node_id,
            "name": "",
            "type": "EmptyEndEvent",
            "incoming": [],
            "outgoing": "",
        }

    def test_component_node_converter_success(self):
        json_data = ComponentNode(
            id=self.source_node_id,
            component=Component(code="test_component", version="1.0", data=[]),
            auto_retry=AutoRetryConfig(),
            timeout_config=TimeoutConfig(),
        )
        converter = ComponentNodeConverter(source_data=json_data)
        result = converter.convert()

        assert converter.source == self.source_type
        assert converter.target == self.target_type
        assert result == {
            "id": self.source_node_id,
            "name": "",
            "type": "ServiceActivity",
            "optional": True,
            "incoming": [],
            "outgoing": "",
            "component": {"code": "test_component", "data": {}, "version": "1.0"},
            "error_ignorable": False,
            "skippable": True,
            "retryable": True,
            "auto_retry": {"enable": False, "interval": 0, "times": 1},
            "timeout_config": {"action": "forced_fail", "enable": False, "seconds": 10},
        }
