# -*- coding: utf-8 -*-
from typing import Any, Dict

from bkflow.pipeline_converter.data_models import ExclusiveGateway
from bkflow.pipeline_converter.validators.base import BaseValidator


class GatewayConditionValidator(BaseValidator):
    def validate(self, data: ExclusiveGateway, *args, **kwargs):
        default_condition_count = 0
        for condition in data.conditions:
            if condition.next_node not in data.next:
                raise ValueError(f"condition {condition.name} must point to an existing node")
            if condition.is_default is True:
                default_condition_count += 1
            if not condition.is_default and not condition.expr:
                raise ValueError(f"The condition {condition.name} must provide an expr")
        if default_condition_count > 1:
            raise ValueError("Only one default condition is allowed")


class JsonGatewayValidator(BaseValidator):
    def validate(self, data: Dict[str, Any], *args, **kwargs):
        default_condition_count = 0
        for condition in data["conditions"]:
            if condition["next_node"] not in data["next"]:
                raise ValueError(f"condition {condition['name']} must point to an existing node")
            is_default_condition = condition.get("is_default") is True
            if is_default_condition:
                default_condition_count += 1
            if not is_default_condition and "expr" not in condition:
                raise ValueError(f"The condition {condition['name']} must provide an expr")
        if default_condition_count > 1:
            raise ValueError("Only one default condition is allowed")
