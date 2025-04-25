# -*- coding: utf-8 -*-
from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter


class PipelineConverter(JsonToDataModelConverter):

    def convert(self) -> dict:
        """
        将 json 转换成 DataModel
        """
        return self.target_data
