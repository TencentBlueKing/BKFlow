# -*- coding: utf-8 -*-

from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter


class ComponentFieldsConverter(JsonToDataModelConverter):
    def convert(self, *args, **kwargs):
        self.target_data = {}
        return self.target_data


class ComponentConverter(JsonToDataModelConverter):
    def convert(self, *args, **kwargs):
        self.target_data = {}
        return self.target_data
