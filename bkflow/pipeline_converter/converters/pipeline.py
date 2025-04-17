# -*- coding: utf-8 -*-
from bkflow.pipeline_converter.constants import DataTypes
from bkflow.pipeline_converter.converters.base import BaseConverter


class PipelineConverter(BaseConverter):
    source = DataTypes.DATA_MODEL.value
    target = DataTypes.PIPELINE_TREE.value

    def convert(self) -> dict:
        """
        将数据模型转换为流程树
        """
        self.target_data = {}
