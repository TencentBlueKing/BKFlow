# -*- coding: utf-8 -*-
import pytest
from bamboo_engine import validator as engine_validator
from pipeline.core.constants import PE

from bkflow.pipeline_converter.converters.data_model_to_web_pipeline.pipeline import (
    PipelineConverter,
)
from bkflow.pipeline_converter.data_models import (
    Component,
    ComponentNode,
    Condition,
    ConditionalParallelGateway,
    ConvergeGateway,
    EmptyEndNode,
    EmptyStartNode,
    ExclusiveGateway,
    ParallelGateway,
    Pipeline,
)
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

    def test_data_model_2_pipeline_tree_pipeline_convert_with_exclusive_gateway(self):
        node_list = [
            EmptyStartNode(id="start_node", next="component_node"),
            ComponentNode(
                id="component_node",
                name="component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="exclusive_gateway",
            ),
            ExclusiveGateway(
                id="exclusive_gateway",
                type="exclusive_gateway",
                next=["condition_node_1", "condition_node_2"],
                conditions=[
                    Condition(name="condition", expr="True"),
                    Condition(name="condition", expr="False"),
                ],
            ),
            ComponentNode(
                id="condition_node_1",
                name="condition_component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="end_node",
            ),
            ComponentNode(
                id="condition_node_2",
                name="condition_component_node",
                component=Component(code="bk_display", version="v1.0", data=[]),
                next="end_node",
            ),
            EmptyEndNode(id="end_node"),
        ]
        pipeline_model = Pipeline(id="pipeline_id", name="pipeline_name", nodes=node_list, constants=[])
        web_pipeline_tree = PipelineConverter(pipeline_model).convert()
        assert len(web_pipeline_tree[PE.activities]) == 3
        assert len(web_pipeline_tree[PE.flows]) == 6

        validate_web_pipeline_tree(web_pipeline_tree)
        engine_pipeline_tree = format_web_data_to_pipeline(web_pipeline_tree)
        engine_validator.validate_and_process_pipeline(engine_pipeline_tree, cycle_tolerate=False)

    def test_data_model_2_pipeline_tree_pipeline_convert_with_parallel_gateway(self):
        node_list = [
            EmptyStartNode(id="start_node", next="component_node"),
            ComponentNode(
                id="component_node",
                name="component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="parallel_gateway",
            ),
            ParallelGateway(
                id="parallel_gateway",
                type="parallel_gateway",
                next=["condition_node_1", "condition_node_2"],
                converge_gateway_id="converge_gateway",
            ),
            ComponentNode(
                id="condition_node_1",
                name="condition_component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="converge_gateway",
            ),
            ComponentNode(
                id="condition_node_2",
                name="condition_component_node",
                component=Component(code="bk_display", version="v1.0", data=[]),
                next="converge_gateway",
            ),
            ConvergeGateway(
                id="converge_gateway",
                type="converge_gateway",
                next="end_node",
            ),
            EmptyEndNode(id="end_node"),
        ]
        pipeline_model = Pipeline(id="pipeline_id", name="pipeline_name", nodes=node_list, constants=[])
        web_pipeline_tree = PipelineConverter(pipeline_model).convert()
        assert len(web_pipeline_tree[PE.activities]) == 3
        assert len(web_pipeline_tree[PE.flows]) == 7

        validate_web_pipeline_tree(web_pipeline_tree)
        engine_pipeline_tree = format_web_data_to_pipeline(web_pipeline_tree)
        engine_validator.validate_and_process_pipeline(engine_pipeline_tree, cycle_tolerate=False)

    def test_data_model_2_pipeline_tree_pipeline_convert_with_condition_gateway(self):
        node_list = [
            EmptyStartNode(id="start_node", next="component_node"),
            ComponentNode(
                id="component_node",
                name="component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="conditional_parallel_gateway",
            ),
            ConditionalParallelGateway(
                id="conditional_parallel_gateway",
                type="conditional_parallel_gateway",
                next=["condition_node_1", "condition_node_2"],
                conditions=[
                    Condition(name="condition", expr="True"),
                    Condition(name="condition", expr="False"),
                ],
                converge_gateway_id="converge_gateway",
            ),
            ComponentNode(
                id="condition_node_1",
                name="condition_component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="converge_gateway",
            ),
            ComponentNode(
                id="condition_node_2",
                name="condition_component_node",
                component=Component(code="bk_display", version="v1.0", data=[]),
                next="converge_gateway",
            ),
            ConvergeGateway(
                id="converge_gateway",
                type="converge_gateway",
                next="end_node",
            ),
            EmptyEndNode(id="end_node"),
        ]
        pipeline_model = Pipeline(id="pipeline_id", name="pipeline_name", nodes=node_list, constants=[])
        web_pipeline_tree = PipelineConverter(pipeline_model).convert()
        assert len(web_pipeline_tree[PE.activities]) == 3
        assert len(web_pipeline_tree[PE.flows]) == 7

        validate_web_pipeline_tree(web_pipeline_tree)
        engine_pipeline_tree = format_web_data_to_pipeline(web_pipeline_tree)
        engine_validator.validate_and_process_pipeline(engine_pipeline_tree, cycle_tolerate=False)

    def test_data_model_2_pipeline_tree_pipeline_convert_fail_for_conditions(self):
        node_list = [
            EmptyStartNode(id="start_node", next="component_node"),
            ComponentNode(
                id="component_node",
                name="component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="exclusive_gateway",
            ),
            ExclusiveGateway(
                id="exclusive_gateway",
                type="exclusive_gateway",
                next=["condition_node_1", "condition_node_2"],
                conditions=[
                    Condition(name="condition", expr="True"),
                ],
            ),
            ComponentNode(
                id="condition_node_1",
                name="condition_component_node",
                component=Component(code="example_code", version="legacy", data=[]),
                next="end_node",
            ),
            ComponentNode(
                id="condition_node_2",
                name="condition_component_node",
                component=Component(code="bk_display", version="v1.0", data=[]),
                next="end_node",
            ),
            EmptyEndNode(id="end_node"),
        ]
        with pytest.raises(ValueError):
            pipeline_model = Pipeline(id="pipeline_id", name="pipeline_name", nodes=node_list, constants=[])
            PipelineConverter(pipeline_model).convert()

    def test_data_model_2_pipeline_tree_pipeline_convert_fail_for_validate(self):
        node_list = [
            EmptyStartNode(id="start_node", next="component_node"),
            ComponentNode(
                id="component_node",
                name="component_node",
                type="component_node",
                component=Component(code="bk_display", version="v1.0", data=[]),
                next="end_node",
            ),
            EmptyEndNode(id="end_node"),
        ]
        pipeline_model = Pipeline(id="pipeline_id", name="pipeline_name", nodes=node_list, constants=[])
        with pytest.raises(ValueError):
            PipelineConverter(pipeline_model).convert()

    def test_data_model_2_pipeline_tree_pipeline_convert_fail_for_converted_node(self):
        node_list = [
            EmptyStartNode(id="start_node", next="component_node"),
            ComponentNode(
                id="component_node",
                name="component_node",
                component=Component(code="bk_display", version="v1.0", data=[]),
                next="gateway_node",
            ),
            EmptyEndNode(id="end_node"),
        ]
        pipeline_model = Pipeline(id="pipeline_id", name="pipeline_name", nodes=node_list, constants=[])
        with pytest.raises(ValueError):
            PipelineConverter(pipeline_model).convert()
