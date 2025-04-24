# -*- coding: utf-8 -*-
from pipeline.core.constants import PE

from bkflow.pipeline_converter.converters.pipeline import PipelineConverter
from bkflow.pipeline_converter.data_models import Pipeline, EmptyStartNode, ComponentNode, Component, EmptyEndNode


class TestPipelineConverter:
    def test_data_model_2_pipeline_tree_pipeline_convert_success(self):
        node_list = [
            EmptyStartNode(id="start_node", next="component_node"),
            ComponentNode(
                id="component_node",
                name="component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="end_node",
            ),
            EmptyEndNode(id="end_node"),
        ]
        pipeline_model = Pipeline(id="pipeline_id", name="pipeline_name", nodes=node_list, constants=[])
        pipeline_tree = PipelineConverter(pipeline_model).convert()
        assert len(pipeline_tree[PE.activities]) == 1
        assert len(pipeline_tree[PE.flows]) == 2
