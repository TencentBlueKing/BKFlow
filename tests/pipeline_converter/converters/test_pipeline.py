# -*- coding: utf-8 -*-
from bamboo_engine import validator as engine_validator
from pipeline.core.constants import PE

from bkflow.pipeline_converter.converters.pipeline import PipelineConverter
from bkflow.pipeline_converter.data_models import Pipeline, EmptyStartNode, ComponentNode, Component, EmptyEndNode
from bkflow.pipeline_web.parser.format import format_web_data_to_pipeline
from bkflow.pipeline_web.parser.validator import validate_web_pipeline_tree


class TestPipelineConverter:
    def test_data_model_2_pipeline_tree_pipeline_convert_success(self):
        node_list = [
            EmptyStartNode(id="start_node", next="component_node"),
            ComponentNode(
                id="component_node",
                name="component_node",
                component=Component(code="bk_display", version="v1.0", data=[]),
                next="end_node",
            ),
            EmptyEndNode(id="end_node"),
        ]
        pipeline_model = Pipeline(id="pipeline_id", name="pipeline_name", nodes=node_list, constants=[])
        web_pipeline_tree = PipelineConverter(pipeline_model).convert()
        assert len(web_pipeline_tree[PE.activities]) == 1
        assert len(web_pipeline_tree[PE.flows]) == 2

        # 确保 web_pipeline_tree 格式正确 且能够正常转换成 engine_pipeline_tree
        validate_web_pipeline_tree(web_pipeline_tree)
        engine_pipeline_tree = format_web_data_to_pipeline(web_pipeline_tree)
        engine_validator.validate_and_process_pipeline(engine_pipeline_tree, cycle_tolerate=False)
