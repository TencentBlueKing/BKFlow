# -*- coding: utf-8 -*-
from bkflow.pipeline_converter.constants import ConstantTypes
from bkflow.pipeline_converter.converters.base import DataModelToPipelineTreeConverter
from bkflow.pipeline_converter.validators.constant import (
    ComponentInputValidator,
    ConstantValidator,
)
from bkflow.pipeline_converter.validators.node import NodeTypeValidator


class SourceInfoConverter(DataModelToPipelineTreeConverter):
    def convert(self):
        self.target_data = {}
        for info in self.source_data:
            self.target_data[info.key] = [info.value]
        return self.target_data


class CustomConstantConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(ConstantTypes.CUSTOM_CONSTANT.value), ConstantValidator()]

    def convert(self):
        converter_data = self.source_data
        self.target_data = {
            "name": converter_data.name,
            "key": f"${{{converter_data.key}}}",
            "desc": converter_data.desc,
            "value": converter_data.value,
            "custom_type": converter_data.custom_type,
            "show_type": converter_data.show_type,
            "source_tag": converter_data.source_tag,
            "source_type": ConstantTypes.CUSTOM_CONSTANT.value,
            "source_info": SourceInfoConverter(converter_data.source_info).convert(),
            "validation": converter_data.validation,
            "version": converter_data.version,
            "pre_render_make": False,
            "is_meta": converter_data.is_meta,
        }

        return self.target_data


class ComponentInputConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(ConstantTypes.COMPONENT_INPUTS_CONSTANT.value), ComponentInputValidator()]

    def convert(self):
        converter_data = self.source_data
        self.target_data = {
            "name": converter_data.name,
            "key": f"${{{converter_data.key}}}",
            "desc": converter_data.desc,
            "value": [converter_data.value],
            "custom_type": converter_data.custom_type,
            "show_type": converter_data.show_type,
            "source_tag": converter_data.source_tag,
            "source_type": ConstantTypes.COMPONENT_INPUTS_CONSTANT.value,
            "source_info": SourceInfoConverter(converter_data.source_info).convert(),
            "validation": converter_data.validation,
            "version": converter_data.version,
            "plugin_code": converter_data.plugin_code,
            "extra_info": converter_data.extra_info,
        }
        return self.target_data


class ComponentOutputConverter(DataModelToPipelineTreeConverter):
    validators = [NodeTypeValidator(ConstantTypes.COMPONENT_OUTPUTS_CONSTANT.value)]

    def convert(self):
        converter_data = self.source_data
        self.target_data = {
            "name": converter_data.name,
            "key": f"${{{converter_data.key}}}",
            "desc": converter_data.desc,
            "value": converter_data.value,
            "custom_type": converter_data.custom_type,
            "show_type": converter_data.show_type,
            "source_tag": converter_data.source_tag,
            "source_type": ConstantTypes.COMPONENT_OUTPUTS_CONSTANT.value,
            "source_info": SourceInfoConverter(converter_data.source_info).convert(),
            "validation": converter_data.validation,
            "plugin_code": converter_data.plugin_code,
            "extra_info": converter_data.extra_info,
        }
        return self.target_data
