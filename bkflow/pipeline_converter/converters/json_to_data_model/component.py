# -*- coding: utf-8 -*-

from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter
from bkflow.pipeline_converter.data_models import Component, ComponentField


class ComponentFieldsConverter(JsonToDataModelConverter):
    def convert(self, *args, **kwargs):
        self.target_data = [
            ComponentField(
                key=c["key"],
                value=c["value"],
            )
            for c in self.source_data
        ]
        return self.target_data


class ComponentConverter(JsonToDataModelConverter):
    def convert(self, *args, **kwargs):
        self.target_data = Component(
            code=self.source_data["code"],
            version=self.source_data["version"],
            data=ComponentFieldsConverter(self.source_data["data"]).convert(),
        )
        return self.target_data
