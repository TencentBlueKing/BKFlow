# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from typing import Any, List

from bkflow.pipeline_converter.constants import DataTypes
from bkflow.pipeline_converter.hub import CONVERTER_HUB
from bkflow.pipeline_converter.validators.base import BaseValidator


class BaseConverter(ABC):
    """
    转换器
    attrs:
        source: 源数据类型
        target: 目标数据类型
    """

    def __init__(self, source_data: Any, *args, **kwargs):
        self.source_data = source_data
        self.target_data = None
        self.validate()

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)

        if not hasattr(cls, "validators"):
            cls.validators: List[BaseValidator] = []

        exempt_cls_names = [
            "BaseConverter",
            "BaseBiConverter",
            "DataModelToPipelineTreeConverter",
            "JsonToDataModelConverter",
        ]
        if cls.__name__ in exempt_cls_names:
            return

        needed_attrs = ["source", "target"]
        if not all([hasattr(cls, field) for field in needed_attrs]):
            raise TypeError(f"sub class {cls.__name__} needs attrs {needed_attrs}")
        CONVERTER_HUB.register(cls)

    def validate(self, *args, **kwargs):
        for validator in self.validators:
            validator.validate(self.source_data, *args, **kwargs)

    @abstractmethod
    def convert(self, *args, **kwargs):
        pass


class BaseBiConverter(BaseConverter):
    """双向转换器"""

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        if not hasattr(cls, "reverse_validators"):
            cls.reverse_validators: List[BaseValidator] = []

    def reverse_validate(self, data: Any, *args, **kwargs):
        for validator in self.reverse_validators:
            validator.validate(data, *args, **kwargs)

    @abstractmethod
    def reconvert(self, *args, **kwargs):
        pass


class DataModelToPipelineTreeConverter(BaseConverter, ABC):
    """数据到流程转换器"""

    source = DataTypes.DATA_MODEL.value
    target = DataTypes.WEB_PIPELINE.value


class JsonToDataModelConverter(BaseConverter, ABC):
    """json到数据模型转换器"""

    source = DataTypes.JSON.value
    target = DataTypes.DATA_MODEL.value
