# -*- coding: utf-8 -*-
from typing import Any, Dict

from bkflow.pipeline_converter.data_models import ExclusiveGateway
from bkflow.pipeline_converter.validators.base import BaseValidator


class GatewayConditionValidator(BaseValidator):
    def validate(self, data: ExclusiveGateway, *args, **kwargs):
        for condition in data.conditions:
            if condition.next not in data.next:
                raise ValueError(f"condition {condition.name} must point to an existing node")
        default_condition = data.default_condition
        if default_condition and default_condition.next not in data.next:
            raise ValueError(f"default condition {default_condition.name} must point to an existing node")


class JsonGatewayValidator(BaseValidator):
    def validate(self, data: Dict[str, Any], *args, **kwargs):
        for condition in data["conditions"]:
            if condition["next"] not in data["next"]:
                raise ValueError(f"condition {condition['name']} must point to an existing node")
        default_condition = data.get("default_condition")
        if default_condition and default_condition["next"] not in data["next"]:
            raise ValueError(f"default condition {default_condition['name']} must point to an existing node")
