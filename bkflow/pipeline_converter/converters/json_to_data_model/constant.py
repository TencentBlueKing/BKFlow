# -*- coding: utf-8 -*-
from bkflow.pipeline_converter.constants import ConstantTypes
from bkflow.pipeline_converter.converters.base import JsonToDataModelConverter
from bkflow.pipeline_converter.data_models import (
    ComponentInputConstant,
    ComponentOutConstant,
    CustomConstant,
    SourceInfo,
)
from bkflow.pipeline_converter.validators.constant import (
    JsonComponentInputValidator,
    JsonConstantValidator,
)
from bkflow.pipeline_converter.validators.node import JsonNodeTypeValidator


class SourceInfoConverter(JsonToDataModelConverter):
    def convert(self):
        self.target_data = []
        for info in self.source_data:
            info_data = SourceInfo(key=info["key"], value=info["value"])
            self.target_data.append(info_data)
        return self.target_data


class CustomConstantConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(ConstantTypes.CUSTOM_CONSTANT.value), JsonConstantValidator()]

    def convert(self):
        self.target_data = CustomConstant(
            name=self.source_data["name"],
            type=ConstantTypes.CUSTOM_CONSTANT.value,
            key=self.source_data["key"],
            value=self.source_data["value"],
            custom_type=self.source_data["custom_type"],
            source_tag=self.source_data["source_tag"],
            pre_render_make=False,
            source_info=SourceInfoConverter(self.source_data["source_info"]).convert(),
        )
        default_optional_field = ["desc", "source_info", "validation", "is_meta", "version", "show_type"]
        for field in default_optional_field:
            if field not in self.source_data:
                continue
            setattr(self.target_data, field, self.source_data[field])

        return self.target_data


class ComponentInputConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(ConstantTypes.COMPONENT_INPUTS_CONSTANT.value), JsonComponentInputValidator()]

    def convert(self):
        self.target_data = ComponentInputConstant(
            name=self.source_data["name"],
            key=self.source_data["key"],
            value=self.source_data["value"],
            custom_type=self.source_data["custom_type"],
            source_tag=self.source_data["source_tag"],
            type=ConstantTypes.COMPONENT_INPUTS_CONSTANT.value,
            source_info=SourceInfoConverter(self.source_data["source_info"]).convert(),
            version=self.source_data["version"],
            extra_info=self.source_data["extra_info"],
        )
        default_optional_field = ["desc", "validation", "version", "show_type", "plugin_code"]
        for field in default_optional_field:
            if field not in self.source_data:
                continue
            setattr(self.target_data, field, self.source_data[field])

        return self.target_data


class ComponentOutputConverter(JsonToDataModelConverter):
    validators = [JsonNodeTypeValidator(ConstantTypes.COMPONENT_OUTPUTS_CONSTANT.value)]

    def convert(self):
        self.target_data = ComponentOutConstant(
            name=self.source_data["name"],
            key=self.source_data["key"],
            value=self.source_data["value"],
            custom_type=self.source_data["custom_type"],
            source_tag=self.source_data["source_tag"],
            type=ConstantTypes.COMPONENT_OUTPUTS_CONSTANT.value,
            source_info=SourceInfoConverter(self.source_data["source_info"]).convert(),
            extra_info=self.source_data["extra_info"],
        )
        default_optional_field = ["desc", "validation", "show_type", "plugin_code"]
        for field in default_optional_field:
            if field not in self.source_data:
                continue
            setattr(self.target_data, field, self.source_data[field])

        return self.target_data
