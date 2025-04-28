# -*- coding: utf-8 -*-
from bamboo_engine import validator as engine_validator
from pipeline.core.constants import PE

from bkflow.pipeline_converter.converters.data_model_to_web_pipeline.pipeline import (
    PipelineConverter as DataModelToWebPipelineConverter,
)
from bkflow.pipeline_converter.converters.json_to_data_model.pipeline import (
    PipelineConverter as JsonToDataModelPipelineConverter,
)
from bkflow.pipeline_converter.data_models import Pipeline
from bkflow.pipeline_web.parser.format import format_web_data_to_pipeline
from bkflow.pipeline_web.parser.validator import validate_web_pipeline_tree


class TestPipelineConverter:
    def test_json_2_data_model_pipeline_convert_success(self):
        json_data = {
            "id": "pipeline_id",
            "name": "pipeline_name",
            "nodes": [
                {
                    "id": "start_node",
                    "type": "start_event",
                    "next": "custom_node",
                },
                {
                    "id": "custom_node",
                    "type": "component",
                    "name": "component_node",
                    "component": {
                        "code": "bk_display",
                        "version": "v1.0",
                        "data": [{"key": "bk_display_message", "value": 123}],
                    },
                    "next": "end_node",
                },
                {
                    "id": "end_node",
                    "type": "end_event",
                },
            ],
        }

        dm_pipeline = JsonToDataModelPipelineConverter(json_data).convert()
        assert isinstance(dm_pipeline, Pipeline)

        web_pipeline_tree = DataModelToWebPipelineConverter(dm_pipeline).convert()
        assert len(web_pipeline_tree[PE.activities]) == 1
        assert len(web_pipeline_tree[PE.flows]) == 2

        # 确保 web_pipeline_tree 格式正确 且能够正常转换成 engine_pipeline_tree
        validate_web_pipeline_tree(web_pipeline_tree)
        engine_pipeline_tree = format_web_data_to_pipeline(web_pipeline_tree)
        engine_validator.validate_and_process_pipeline(engine_pipeline_tree, cycle_tolerate=False)
