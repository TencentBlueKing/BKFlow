# -*- coding: utf-8 -*-
from typing import Any, Dict

from bkflow.pipeline_converter.constants import ConstantTypes
from bkflow.pipeline_converter.data_models import ComponentInputConstant, CustomConstant
from bkflow.pipeline_converter.validators.base import BaseValidator


class ConstantValidator(BaseValidator):
    def validate(self, data: CustomConstant, *args, **kwargs):
        if data.custom_type not in ConstantTypes.CUSTOM_CONSTANT_CUSTOMS.value:
            raise ValueError("The parameter custom type does not meet the requirements")
        if data.source_tag not in ConstantTypes.CUSTOM_CONSTANT_TAGS.value:
            raise ValueError("The parameter source tag does not meet the requirements")


class ComponentInputValidator(BaseValidator):
    def validate(self, data: ComponentInputConstant, *args, **kwargs):
        constant_key = data.key
        try:
            code, tag_field = data.source_tag.split(".")
        except ValueError:
            raise ValueError("parameter source_tag does not conform to the required format")

        for info in data.source_info:
            info_field = info.value

            if not (constant_key == info_field == tag_field):
                raise ValueError("the information about the source node fields must be consistent in the parameters")


class JsonConstantValidator(BaseValidator):
    def validate(self, data: Dict[str, Any], *args, **kwargs):
        if data.get("custom_type") not in ConstantTypes.CUSTOM_CONSTANT_CUSTOMS.value:
            raise ValueError("The parameter custom type does not meet the requirements")
        if data.get("source_tag") not in ConstantTypes.CUSTOM_CONSTANT_TAGS.value:
            raise ValueError("The parameter source tag does not meet the requirements")


class JsonComponentInputValidator(BaseValidator):
    def validate(self, data: Dict[str, Any], *args, **kwargs):
        constant_key = data.get("key")
        try:
            code, tag_field = data.get("source_tag").split(".")
        except ValueError:
            raise ValueError("parameter source_tag does not conform to the required format")

        for info in data.get("source_info"):
            info_field = info.get("value")

            if not (constant_key == info_field == tag_field):
                raise ValueError("the information about the source node fields must be consistent in the parameters")
