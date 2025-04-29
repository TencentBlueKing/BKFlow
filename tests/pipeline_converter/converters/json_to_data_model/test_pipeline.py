# -*- coding: utf-8 -*-
from bamboo_engine import validator as engine_validator
from pipeline.core.constants import PE

from bkflow.pipeline_converter.constants import DataTypes
from bkflow.pipeline_converter.data_models import Pipeline
from bkflow.pipeline_converter.hub import CONVERTER_HUB
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
        json_pipeline_cvt = CONVERTER_HUB.get_converter_cls(
            DataTypes.JSON.value, DataTypes.DATA_MODEL.value, "PipelineConverter"
        )
        dm_pipeline = json_pipeline_cvt(json_data).convert()
        assert isinstance(dm_pipeline, Pipeline)

        data_model_pipeline_cvt = CONVERTER_HUB.get_converter_cls(
            DataTypes.DATA_MODEL.value, DataTypes.WEB_PIPELINE.value, "PipelineConverter"
        )
        web_pipeline_tree = data_model_pipeline_cvt(dm_pipeline).convert()

        assert len(web_pipeline_tree[PE.activities]) == 1
        assert len(web_pipeline_tree[PE.flows]) == 2

        # 确保 web_pipeline_tree 格式正确 且能够正常转换成 engine_pipeline_tree
        validate_web_pipeline_tree(web_pipeline_tree)
        engine_pipeline_tree = format_web_data_to_pipeline(web_pipeline_tree)
        engine_validator.validate_and_process_pipeline(engine_pipeline_tree, cycle_tolerate=False)
