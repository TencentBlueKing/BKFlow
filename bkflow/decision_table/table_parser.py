# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import abc
import logging
from typing import List, Optional

import jsonschema
from pydantic import BaseModel

from bkflow.decision_table.constants import ObjValueTypes
from bkflow.exceptions import ValidationError

logger = logging.getLogger(__name__)


class BaseField(BaseModel):
    id: str
    name: str
    type: str
    tips: str = ""
    desc: str = ""
    options: Optional[dict]


class InputField(BaseField):
    pass


class OutputField(BaseField):
    pass


class DecisionTableParser:
    BKFLOW_DECISION_TABLE_SCHEMA = {
        "type": "object",
        "required": ["inputs", "outputs", "records"],
        "properties": {
            "inputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "desc": {"type": "string"},
                        "from": {"type": "string"},
                        "name": {"type": "string"},
                        "tips": {"type": "string"},
                        "type": {"type": "string"},
                        "options": {"type": "object"},
                    },
                },
            },
            "outputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "desc": {"type": "string"},
                        "from": {"type": "string"},
                        "name": {"type": "string"},
                        "tips": {"type": "string"},
                        "type": {"type": "string"},
                        "options": {"type": "object"},
                    },
                },
            },
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"inputs": {"type": "object"}, "outputs": {"type": "object"}},
                },
            },
        },
    }

    def __init__(self, title, decision_table, hit_policy="Unique", validate=True):
        self.title = title
        self.original_table = decision_table
        self.hit_policy = hit_policy
        if validate:
            self.validate()

    def validate(self):
        try:
            jsonschema.validate(self.original_table, self.BKFLOW_DECISION_TABLE_SCHEMA)
        except jsonschema.ValidationError as e:
            logger.exception(f"[validate decision table schema error]: {e}")
            raise ValidationError(f"[validate decision table schema error]: {str(e)}")

    def parse(self):
        result = {"title": self.title, "hit_policy": self.hit_policy}

        # prepare for inputs data
        input_fields = [InputField(**input_meta) for input_meta in self.original_table["inputs"]]
        inputs = {
            "cols": [{"id": input_field.id, "name": input_field.name} for input_field in input_fields],
            "rows": [],
        }
        for record in self.original_table["records"]:
            record_inputs = record["inputs"]
            parser_mappings = {
                "common": CommonConditionParser,
                "or_and": OrAndConditionParser,
                "expression": ExpressionParser,
            }
            parser = parser_mappings.get(record_inputs["type"])

            if parser is None:
                msg = f"[parse decision table error]: can not get record type of {record_inputs['type']}"
                logger.error(msg)
                raise ValidationError(msg)

            inputs["rows"].append(parser(conditions=record_inputs["conditions"], input_fields=input_fields).parse())
        result["inputs"] = inputs

        # prepare for outputs data
        output_fields = [OutputField(**output_meta) for output_meta in self.original_table["outputs"]]
        outputs = {"cols": [{"id": field.id, "name": field.name} for field in output_fields], "rows": []}
        for record in self.original_table["records"]:
            record_outputs = record["outputs"]
            outputs["rows"].append(
                [
                    OutputParser(output_field=field).parse(output_value=record_outputs[field.id])
                    for i, field in enumerate(output_fields)
                ]
            )
        result["outputs"] = outputs

        return result


class ConditionBaseParser(metaclass=abc.ABCMeta):
    def __init__(self, conditions, input_fields: List[InputField]):
        self.conditions = conditions
        self.input_fields = input_fields

    @abc.abstractmethod
    def parse(self):
        pass


class CommonConditionParser(ConditionBaseParser):
    def parse(self):
        row_inputs = []
        for i, condition in enumerate(self.conditions):
            operation_parser = RightOperationParser(input_field=self.input_fields[i])
            parse_result = operation_parser.parse(compare=condition["compare"], value_obj=condition["right"]["obj"])
            row_inputs.append(parse_result)
        return row_inputs


class OrAndConditionParser(ConditionBaseParser):
    def __init__(self, conditions, input_fields: List[InputField]):
        super().__init__(conditions, input_fields)
        self.input_fields_mapping = {field.id: field for field in self.input_fields}

    def _parse_left_right_conditions(self, conditions):
        operator = conditions["operator"]
        results = []
        for condition in conditions["conditions"]:
            left_obj_key, compare, right_value_obj = (
                condition["left"]["obj"]["key"],
                condition["compare"],
                condition["right"]["obj"],
            )
            rop = RightOperationParser(input_field=self.input_fields_mapping[left_obj_key], is_full=True)
            results.append(rop.parse(compare=compare, value_obj=right_value_obj))
        return f'({f" {operator} ".join(results)})'

    def parse(self):
        operator = self.conditions["operator"]
        condition_results = [
            self._parse_left_right_conditions(conditions) for conditions in self.conditions["conditions"]
        ]
        return f" {operator} ".join(condition_results)


class ExpressionParser(ConditionBaseParser):
    def parse(self):
        return self.conditions


class RightOperationParser:
    def __init__(self, input_field: InputField, is_full: bool = False):
        self.input_field = input_field
        self.is_full = is_full

    def parse(self, compare, value_obj):
        value = self._parse_value_obj(value_obj)
        return getattr(self, f"_parse_{compare.replace('-', '_')}")(value)

    @staticmethod
    def _parse_value_obj(obj):
        """obj 可能为 {} 或 {"type": xxx, "value"}"""
        if obj.get("type") == ObjValueTypes.INT.value:
            return int(obj["value"])
        if obj.get("type") == ObjValueTypes.INT_RANGE.value:
            return f'[{obj["value"]["start"]}..{obj["value"]["end"]}]'
        return obj.get("value")

    def _parse_equals(self, value):
        result = f"{value}" if isinstance(value, int) else f'"{value}"'
        return f"{self.input_field.id}={result}" if self.is_full else result

    def _parse_not_equals(self, value):
        result = f"{value}" if isinstance(value, int) else f'"{value}"'
        return f"{self.input_field.id}!={result}"

    def _parse_is_null(self, value):
        return f"{self.input_field.id}=null" if self.is_full else "null"

    def _parse_not_null(self, value):
        return f"{self.input_field.id}!=null"

    def _parse_contains(self, value):
        return f'contains({self.input_field.id},"{value}")'

    def _parse_not_contains(self, value):
        return f"not({self._parse_contains(value)})"

    def _parse_greater_than(self, value):
        return f"{self.input_field.id}>{value}" if self.is_full else f">{value}"

    def _parse_less_than(self, value):
        return f"{self.input_field.id}<{value}" if self.is_full else f"<{value}"

    def _parse_greater_than_or_equal(self, value):
        return f"{self.input_field.id}>={value}" if self.is_full else f">={value}"

    def _parse_less_than_or_equal(self, value):
        return f"{self.input_field.id}<={value}" if self.is_full else f"<={value}"

    def _parse_in_range(self, value):
        # select range
        if isinstance(value, list):
            return f'list contains("{value}", {self.input_field.id})'
        # int range
        return f"{self.input_field.id} in {value}" if self.is_full else value

    def _parse_not_in_range(self, value):
        # select range
        if isinstance(value, list):
            return f'not(list contains("{value}", {self.input_field.id}))'
        # int range
        return f"not({self.input_field.id} in {value})"


class OutputParser:
    def __init__(self, output_field: OutputField):
        self.output_field = output_field

    def parse(self, output_value):
        if self.output_field.type == ObjValueTypes.INT.value:
            return output_value
        return f'"{output_value}"'
