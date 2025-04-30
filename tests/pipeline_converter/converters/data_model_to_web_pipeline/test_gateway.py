# -*- coding: utf-8 -*-

import pytest

from bkflow.pipeline_converter.constants import DataTypes
from bkflow.pipeline_converter.converters.data_model_to_web_pipeline.gateway import (
    ConditionalParallelGatewayConverter,
    ConvergeGatewayConverter,
    ExclusiveGatewayConverter,
    ParallelGatewayConverter,
)
from bkflow.pipeline_converter.data_models import (
    Condition,
    ConditionalParallelGateway,
    ConvergeGateway,
    ExclusiveGateway,
    ParallelGateway,
)


class TestGateway(object):
    source_type = DataTypes.DATA_MODEL.value
    target_type = DataTypes.WEB_PIPELINE.value
    gateway_node = "node_1"
    converge_gateway_id = "node_2"
    next = ["node_3", "node_4"]

    def test_parallel_gateway_converter(self):
        json_data = {
            "id": self.gateway_node,
            "type": "parallel_gateway",
            "converge_gateway_id": self.converge_gateway_id,
        }
        source_data = ParallelGateway(**json_data)
        child_converter = ParallelGatewayConverter(source_data)
        result = child_converter.convert()

        assert child_converter.source == self.source_type
        assert child_converter.target == self.target_type
        assert result == {
            "id": self.gateway_node,
            "name": "",
            "type": "ParallelGateway",
            "incoming": [],
            "outgoing": [],
            "converge_gateway_id": self.converge_gateway_id,
        }

    def test_parallel_gateway_converter_failed(self):
        with pytest.raises(ValueError):
            json_data = {
                "id": self.gateway_node,
                "type": "component",
                "converge_gateway_id": "",
            }
            source_data = ParallelGateway(**json_data)
            ParallelGatewayConverter(source_data)

    def test_exclusive_gateway_converter(self):
        conditions = Condition(name="", expr="1 == 1", next_node="node_3")
        json_data = {
            "id": self.gateway_node,
            "type": "exclusive_gateway",
            "conditions": [conditions],
            "lang": "boolrule",
            "next": self.next,
        }
        source_data = ExclusiveGateway(**json_data)
        child_converter = ExclusiveGatewayConverter(source_data)
        result = child_converter.convert()

        assert child_converter.source == self.source_type
        assert child_converter.target == self.target_type
        assert result == {
            "id": self.gateway_node,
            "name": "",
            "type": "ExclusiveGateway",
            "incoming": [],
            "outgoing": [],
            "conditions": [{"name": "", "evaluate": "1 == 1", "next_node": "node_3", "is_default": False}],
            "extra_info": {"parse_lang": "boolrule"},
        }

    def test_conditional_parallel_gateway_converter(self):
        conditions = Condition(name="", expr="1 == 1", next_node="node_3")
        json_data = {
            "id": self.gateway_node,
            "type": "conditional_parallel_gateway",
            "converge_gateway_id": self.converge_gateway_id,
            "conditions": [conditions],
            "lang": "boolrule",
            "next": self.next,
        }
        source_data = ConditionalParallelGateway(**json_data)
        child_converter = ConditionalParallelGatewayConverter(source_data)
        result = child_converter.convert()

        assert child_converter.source == self.source_type
        assert child_converter.target == self.target_type
        assert result == {
            "id": self.gateway_node,
            "name": "",
            "type": "ConditionalParallelGateway",
            "incoming": [],
            "outgoing": [],
            "converge_gateway_id": self.converge_gateway_id,
            "conditions": [{"name": "", "evaluate": "1 == 1", "next_node": "node_3", "is_default": False}],
            "extra_info": {"parse_lang": "boolrule"},
        }

    def test_converge_gateway_converter(self):
        json_data = {
            "id": self.converge_gateway_id,
            "type": "converge_gateway",
            "next": self.next,
        }
        source_data = ConvergeGateway(**json_data)
        child_converter = ConvergeGatewayConverter(source_data)
        result = child_converter.convert()
        assert child_converter.source == self.source_type
        assert child_converter.target == self.target_type
        assert result == {
            "id": self.converge_gateway_id,
            "name": "",
            "type": "ConvergeGateway",
            "incoming": [],
            "outgoing": "",
        }
