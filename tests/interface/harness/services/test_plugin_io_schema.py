"""真实 Bamboo IO 到 Harness Schema 的边界回归，不执行任何插件。"""

import json
from copy import deepcopy

import pytest
from django.conf import settings
from django.utils import translation
from django.utils.functional import lazy
from jsonschema import ValidationError, validate
from pipeline.core.flow.io import (
    ArrayItemSchema,
    BooleanItemSchema,
    FloatItemSchema,
    IntItemSchema,
    ObjectItemSchema,
    StringItemSchema,
)

from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.projection import _schema_payload as search_schema
from bkflow.harness.services.resolver import _schema_payload as exact_schema
from bkflow.harness.services.validator import WorkflowValidator
from bkflow.pipeline_plugins.components.collections.pause.legacy import PauseComponent


def test_real_pause_io_is_json_serializable_and_shared_by_search_and_resolver():
    """内置插件的延迟翻译值不能阻断检索、精确 Schema 或指纹。"""
    raw = {
        "plugin_type": "component",
        "inputs": PauseComponent.inputs_format(),
        "outputs": PauseComponent.outputs_format(),
    }
    projected = search_schema(raw)
    resolved = exact_schema(raw)
    assert json.loads(json.dumps(projected)) == resolved
    assert schema_hash(projected) == schema_hash(resolved)
    validate("验收描述", WorkflowValidator._field_json_schema(resolved["inputs"][0]))


@pytest.mark.parametrize(
    "item,value,invalid",
    [
        (StringItemSchema(description="text"), "hello", 1),
        (IntItemSchema(description="count"), 3, "3"),
        (FloatItemSchema(description="ratio"), 1.5, "1.5"),
        (BooleanItemSchema(description="enabled"), True, "true"),
        (
            ObjectItemSchema(
                description="nested",
                property_schemas={
                    "values": ArrayItemSchema(description="values", item_schema=IntItemSchema(description="count"))
                },
            ),
            {"values": [1, 2]},
            {"values": ["1"]},
        ),
        (StringItemSchema(description="choice", enum=["A", "B"]), "A", "C"),
    ],
)
def test_component_io_adapter_accepts_values_but_preserves_real_constraints(item, value, invalid):
    """转换 Bamboo 的别名及空枚举，不放宽实际类型、嵌套或非空枚举约束。"""
    raw = {"plugin_type": "component", "inputs": [{"key": "value", "schema": item.as_dict()}], "outputs": []}
    original = deepcopy(raw)
    schema = WorkflowValidator._field_json_schema(exact_schema(raw)["inputs"][0])
    validate(value, schema)
    with pytest.raises(ValidationError):
        validate(invalid, schema)
    assert raw == original


def test_component_schema_translation_does_not_drift_with_request_language():
    """同一部署内切换请求语言不能改变同一插件的精确 Schema 指纹。"""
    label = lazy(lambda: translation.get_language(), str)()
    raw = {"plugin_type": "component", "inputs": [{"key": "value", "name": label}], "outputs": []}
    with translation.override("en"):
        english = json.loads(json.dumps(search_schema(raw)))
    with translation.override("zh-hans"):
        chinese = json.loads(json.dumps(exact_schema(raw)))
    assert english == chinese
    assert chinese["inputs"][0]["name"] == settings.LANGUAGE_CODE


def test_external_json_schema_empty_enum_is_not_treated_as_bamboo_default():
    """外部 JSON Schema 显式空枚举不能因为内置适配而被删除。"""
    raw = {"plugin_type": "uniform_api", "inputs": [{"key": "value", "schema": {"enum": []}}]}
    assert exact_schema(raw)["inputs"][0]["schema"] == {"enum": []}


def test_schema_adapter_keeps_literal_defaults_and_rejects_unknown_python_objects():
    """只归一化 schema 关键字，不重写用户默认对象或把任意对象转成字符串。"""
    raw = {
        "plugin_type": "component",
        "inputs": [{"key": "value", "schema": {"type": "object", "enum": [], "default": {"type": "int", "enum": []}}}],
    }
    schema = exact_schema(raw)["inputs"][0]["schema"]
    assert schema["default"] == {"type": "int", "enum": []}
    raw["inputs"][0]["name"] = object()
    with pytest.raises(TypeError):
        json.dumps(exact_schema(raw))
