"""Harness 专用的插件 IO 适配，不修改画布使用的原始插件协议。"""

from django.conf import settings
from django.utils.functional import Promise
from django.utils.translation import override

_TYPE_ALIASES = {"int": "integer", "float": "number", "str": "string", "bool": "boolean", "list": "array"}


def _json_values(value):
    """递归解析延迟翻译；未知 Python 对象仍由 canonical JSON 拒绝。"""
    if isinstance(value, Promise):
        return str(value)
    if isinstance(value, dict):
        return {_json_values(key): _json_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_values(item) for item in value]
    return value


def _bamboo_schema(schema):
    """将内置 Bamboo ItemSchema 转为 JSON Schema，保留字面默认值和枚举内容。"""
    if not isinstance(schema, dict):
        return schema
    if isinstance(schema.get("type"), str):
        schema["type"] = _TYPE_ALIASES.get(schema["type"], schema["type"])
    # Bamboo 的默认空枚举代表未限制取值，不是 JSON Schema 的不可满足枚举。
    if schema.get("enum") == []:
        schema.pop("enum")
    if isinstance(schema.get("properties"), dict):
        for child in schema["properties"].values():
            _bamboo_schema(child)
    if isinstance(schema.get("items"), list):
        for child in schema["items"]:
            _bamboo_schema(child)
    else:
        _bamboo_schema(schema.get("items"))
    return schema


def generator_schema(plugin_schema, plugin_type=None):
    """搜索与精确解析共用稳定的、可 JSON 序列化的生成器 IO 视图。"""
    with override(settings.LANGUAGE_CODE):
        payload = _json_values({"inputs": plugin_schema.get("inputs", []), "outputs": plugin_schema.get("outputs", [])})
    if (plugin_type or plugin_schema.get("plugin_type")) == "component":
        for fields in payload.values():
            for field in fields:
                if isinstance(field.get("type"), str):
                    field["type"] = _TYPE_ALIASES.get(field["type"], field["type"])
                _bamboo_schema(field.get("schema"))
    return payload
