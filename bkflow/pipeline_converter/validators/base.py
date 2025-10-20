# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from typing import Any


class BaseValidator(ABC):
    @abstractmethod
    def validate(self, data: Any, *args, **kwargs):
        pass
