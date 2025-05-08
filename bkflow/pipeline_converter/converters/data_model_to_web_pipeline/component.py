# -*- coding: utf-8 -*-
from typing import List

from bkflow.pipeline_converter.converters.base import DataModelToPipelineTreeConverter
from bkflow.pipeline_converter.data_models import Component, ComponentField


class ComponentFieldsConverter(DataModelToPipelineTreeConverter):
    def convert(self, *args, **kwargs):
        fields: List[ComponentField] = self.source_data
        self.target_data = {}
        for field in fields:
            self.target_data[field.key] = {
                "need_render": field.need_render,
                "value": field.value,
                "hook": False,  # TODO: 可配置
            }
        return self.target_data


class ComponentConverter(DataModelToPipelineTreeConverter):
    def convert(self, *args, **kwargs):
        component: Component = self.source_data
        self.target_data = {
            "code": component.code,
            "version": component.version,
            "data": ComponentFieldsConverter(component.data).convert(),
        }
        return self.target_data
