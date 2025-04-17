# -*- coding: utf-8 -*-
from collections import defaultdict


class ConverterHub:
    __hub = defaultdict(list)

    @classmethod
    def register(cls, converter_cls):
        cls.__hub[(converter_cls.source, converter_cls.target)].append(converter_cls)

    @classmethod
    def get_converters(cls, source, target):
        return cls.__hub.get((source, target), [])
