"""升级 jsonschema 时保留存量配置的校验语义。"""

import jsonschema
import pytest

from bkflow.utils import jsonschema_compat


@pytest.mark.parametrize(
    "schema,valid,invalid",
    [
        ({"type": "number", "minimum": 0, "exclusiveMinimum": True}, 1, 0),
        ({"type": "array", "items": [{"type": "string"}, {"type": "integer"}]}, ["x", 1], ["x", "1"]),
    ],
)
def test_undeclared_schema_keeps_draft4_semantics(schema, valid, invalid):
    """旧版数值边界与数组逐项 schema 仍按 Draft 4 接受和拒绝数据。"""
    jsonschema_compat.validate(valid, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema_compat.validate(invalid, schema)


def test_explicit_schema_version_is_respected():
    """显式声明新版 schema 时保留其规则，不强制降为 Draft 4。"""
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "number", "exclusiveMinimum": 0}
    jsonschema_compat.validate(1, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema_compat.validate(0, schema)


def test_explicit_validator_and_library_are_unchanged():
    """调用方可选校验器；兼容层不修改第三方库的全局默认规则。"""
    schema = {"type": "number", "exclusiveMinimum": 0}
    jsonschema_compat.validate(1, schema, cls=jsonschema.Draft202012Validator)
    with pytest.raises(jsonschema.SchemaError):
        jsonschema.validate(1, {"type": "number", "minimum": 0, "exclusiveMinimum": True})
    assert jsonschema_compat.ValidationError is jsonschema.ValidationError
