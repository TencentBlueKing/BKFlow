"""保留 jsonschema 2.x 的默认 Draft 4 语义，同时尊重显式指定的校验版本。"""

import jsonschema


def validate(instance, schema, cls=None, *args, **kwargs):
    """未声明版本的存量 schema 继续使用 Draft 4，避免升级依赖改变流程行为。"""
    if cls is None:
        cls = jsonschema.validators.validator_for(schema, default=jsonschema.Draft4Validator)
    return jsonschema.validate(instance, schema, cls, *args, **kwargs)


def __getattr__(name):
    """保留 ValidationError、Draft4Validator 等原有公开接口。"""
    return getattr(jsonschema, name)
