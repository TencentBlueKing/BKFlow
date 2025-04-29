# -*- coding: utf-8 -*-
import importlib
from collections import defaultdict

from bkflow.utils.singleton import Singleton


class ConverterHub(metaclass=Singleton):
    __hub = defaultdict(dict)
    _initialized = False

    @classmethod
    def _ensure_initialized(cls):
        if not cls._initialized:
            importlib.import_module(".converters", package="bkflow.pipeline_converter")
            cls._initialized = True

    @classmethod
    def register(cls, converter_cls):
        cls.__hub[(converter_cls.source, converter_cls.target)][converter_cls.__name__] = converter_cls

    @classmethod
    def get_converters(cls, source, target):
        return cls.__hub.get((source, target), {})

    @classmethod
    def get_converter_cls(cls, source, target, converter_name):
        return cls.get_converters(source, target).get(converter_name)


CONVERTER_HUB = ConverterHub()
CONVERTER_HUB._ensure_initialized()
