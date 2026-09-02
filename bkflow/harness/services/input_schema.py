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
import copy
import re
from typing import Any, Dict, List, Tuple

from jsonschema import Draft4Validator

TEMPLATE_RE = re.compile(r"^\$\{.+\}$")
TYPE_MAP = {
    "string": "string",
    "str": "string",
    "int": "integer",
    "integer": "integer",
    "bool": "boolean",
    "boolean": "boolean",
    "number": "number",
    "float": "number",
    "object": "object",
    "array": "array",
}
CONSTRAINT_KEYS = (
    "enum",
    "pattern",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "oneOf",
    "anyOf",
    "allOf",
    "items",
    "properties",
    "additionalProperties",
    "dependencies",
    "uniqueItems",
    "multipleOf",
    "format",
)


def _is_template(value: Any) -> bool:
    return isinstance(value, str) and bool(TEMPLATE_RE.match(value.strip()))


def _is_json_schema(value: Any) -> bool:
    return isinstance(value, dict) and (value.get("type") == "object" or "properties" in value)


def _field_to_schema(field: Dict[str, Any]) -> Dict[str, Any]:
    """把插件 IO 字段描述转成 Draft4 Schema。"""
    schema: Dict[str, Any] = {}
    mapped = TYPE_MAP.get(field.get("type"), field.get("type"))
    nested = field.get("schema")
    if isinstance(nested, dict):
        schema.update({key: value for key, value in nested.items() if value not in (None, {})})
    if mapped and "type" not in schema:
        schema["type"] = mapped
    for key in CONSTRAINT_KEYS:
        if key in field:
            schema[key] = field[key]
    return schema or {"type": mapped or "string"}


def plugin_inputs_to_jsonschema(inputs: Any) -> Dict[str, Any]:
    """将插件 inputs 列表或现成 JSON Schema 规范化为对象 Schema。"""
    if _is_json_schema(inputs):
        schema = copy.deepcopy(inputs)
        schema.setdefault("type", "object")
        schema.setdefault("additionalProperties", False)
        return schema

    properties = {}
    required = []
    dependencies = {}
    for field in inputs or []:
        if not isinstance(field, dict):
            continue
        key = field.get("key")
        if not key:
            continue
        properties[key] = _field_to_schema(field)
        if field.get("required"):
            required.append(key)
        depends_on = field.get("depends_on") or field.get("dependencies")
        if isinstance(depends_on, list) and depends_on:
            dependencies[key] = depends_on
        elif isinstance(depends_on, dict) and depends_on:
            dependencies[key] = depends_on

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    if dependencies:
        schema["dependencies"] = dependencies
    return schema


def _strip_templates(instance: Any, schema: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    """模板引用跳过类型检查，但仍视为已提供必填值。"""
    if not isinstance(instance, dict) or not isinstance(schema, dict):
        return instance, schema

    new_schema = copy.deepcopy(schema)
    properties = new_schema.get("properties") or {}
    cleaned = {}
    template_keys = []
    for key, value in instance.items():
        if _is_template(value):
            template_keys.append(key)
            continue
        child_schema = properties.get(key)
        if isinstance(value, dict) and isinstance(child_schema, dict):
            cleaned[key], properties[key] = _strip_templates(value, child_schema)
        else:
            cleaned[key] = value

    if template_keys and isinstance(new_schema.get("required"), list):
        new_schema["required"] = [key for key in new_schema["required"] if key not in template_keys]
    return cleaned, new_schema


def _error_path(node_id: str, error) -> str:
    parts = ["nodes", node_id, "inputs"]
    parts.extend(str(item) for item in list(error.path or []))
    if error.validator == "required":
        match = re.search(r"'([^']+)'", error.message or "")
        if match and match.group(1) not in parts:
            parts.append(match.group(1))
    elif error.validator == "additionalProperties":
        match = re.search(r"'([^']+)'", error.message or "")
        if match and match.group(1) not in parts:
            parts.append(match.group(1))
    return ".".join(parts)


def validate_node_data(node_id: str, data: Dict[str, Any], inputs: Any) -> List[Dict[str, Any]]:
    """按解析后的插件 Schema 校验节点输入，返回 SCHEMA_VALIDATION_ERROR 列表。"""
    schema = plugin_inputs_to_jsonschema(inputs)
    instance, schema = _strip_templates(data or {}, schema)
    errors = []
    for error in Draft4Validator(schema).iter_errors(instance):
        errors.append(
            {
                "code": "SCHEMA_VALIDATION_ERROR",
                "message": error.message,
                "path": _error_path(node_id, error),
                "repairable": True,
                "retryable": False,
            }
        )
    return errors
