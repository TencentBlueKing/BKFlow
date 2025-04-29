# -*- coding: utf-8 -*-
import importlib
from collections import defaultdict

from bkflow.utils.singleton import Singleton


class ConverterHub(metaclass=Singleton):
    __hub = defaultdict(dict)

    def __init__(self):
        importlib.import_module(".converters", package="bkflow.pipeline_converter")

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
