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
from enum import Enum
from typing import Dict, Optional, Type

import jsonschema
from django.utils.translation import ugettext_lazy as _
from pydantic import BaseModel, constr
from pytimeparse import parse

from bkflow.exceptions import ValidationError
from bkflow.plugin.space_plugin_config_parser import SpacePluginConfigParser
from bkflow.utils.apigw import check_url_from_apigw

valid_api_key = constr(regex=r"^[A-Za-z0-9_]+$")


class SpaceConfigValueType(Enum):
    # json 类型
    JSON = "JSON"
    # 文本类型
    TEXT = "TEXT"
    # 引用类型 存储在 engine
    REF = "REF"


class SpaceConfigMeta(type):
    def __new__(cls, name, bases, attrs):
        new_cls = super().__new__(cls, name, bases, attrs)
        if name == "BaseSpaceConfig":
            return new_cls
        necessary_attrs = ["name", "desc"]
        for attr in necessary_attrs:
            if getattr(new_cls, attr) is None:
                raise ValueError(f"[SpaceConfigMeta] Missing attribute {attr}")

        SpaceConfigHandler.register_space_config(new_cls)
        return new_cls

    def __call__(cls, *args, **kwargs):
        raise TypeError(f"{cls.__name__} can not be instantiated")


class BaseSpaceConfig(metaclass=SpaceConfigMeta):
    """
    SpaceConfig 基类，该类及其子类无需被实例化即可使用
    """

    name = None  # 配置名称（唯一），需要定义
    desc = None  # 描述，需要定义
    is_public = True  # 是否公开
    value_type = SpaceConfigValueType.TEXT.value  # 配置值类型
    default_value = None  # 默认值
    choices = None  # 配置值可选项列表，适用于 TEXT 类型
    example = None  # 配置值示例
    is_mix_type = False

    @classmethod
    def to_dict(cls):
        return {
            "name": cls.name,
            "desc": cls.desc,
            "is_public": cls.is_public,
            "value_type": cls.value_type,
            "default_value": cls.default_value,
            "choices": cls.choices,
            "example": cls.example,
            "is_mix_type": cls.is_mix_type,
        }

    @classmethod
    def validate(cls, value):
        return True

    @classmethod
    def get_value(cls, config, *args, **kwrags):
        # 默认的父类方法
        return config.text_value if config.value_type == SpaceConfigValueType.TEXT.value else config.json_value


class SpaceConfigHandler:
    __hub = {}

    @classmethod
    def register_space_config(cls, config_cls: Type[BaseSpaceConfig]):
        cls.__hub[config_cls.name] = config_cls

    @classmethod
    def get_config(cls, name):
        if name not in cls.__hub:
            raise ValidationError(f"[SpaceConfigHandler] Config '{name}' not in hub")
        return cls.__hub[name]

    @classmethod
    def get_all_configs(cls, only_public=False):

        # copy, 降低被修改风险
        if only_public:
            return {name: config_cls for name, config_cls in cls.__hub.items() if config_cls.is_public}
        return {name: config_cls for name, config_cls in cls.__hub.items()}

    @classmethod
    def get_control_configs(cls, only_public=False):
        if only_public:
            return {
                name: config_cls
                for name, config_cls in cls.__hub.items()
                if config_cls.is_public and getattr(config_cls, "control", False)
            }
        return {name: config_cls for name, config_cls in cls.__hub.items() if getattr(config_cls, "control", False)}

    @classmethod
    def validate_configs(cls, configs: dict):
        return all([cls.validate(name, value) for name, value in configs.items()])

    @classmethod
    def validate(cls, name, value):
        if name not in cls.__hub:
            raise ValidationError(f"[SpaceConfigHandler] Config '{name}' not in hub")
        return cls.__hub[name].validate(value)


class TokenExpirationConfig(BaseSpaceConfig):
    name = "token_expiration"
    desc = _("Token过期时间")
    default_value = "1h"
    example = "[n]m or [n]h or [n]d, m->minute h->hour d->day, at least 1h"
    LEAST_EXPIRATION_SECONDS = 60 * 60 * 1

    @classmethod
    def validate(cls, value: str):
        try:
            seconds = parse(value)
        except Exception as e:
            raise ValidationError(
                "[validate token expiration config error]: time expiration parse error, value: {}, error: {}".format(
                    value, e
                )
            )

        if seconds is None:
            raise ValidationError(
                "[validate token expiration config error]: time expiration parse error, seconds is None, "
                "value:{}".format(value)
            )
        if seconds < cls.LEAST_EXPIRATION_SECONDS:
            raise ValidationError(
                "[validate token expiration config error]: time expiration must be greater than 1h, value: {}".format(
                    value
                )
            )

        return True


class TokenAutoRenewalConfig(BaseSpaceConfig):
    name = "token_auto_renewal"
    desc = _("是否开启Token自动续期")
    default_value = "true"
    choices = ["true", "false"]
    control = True

    @classmethod
    def validate(cls, value: str):
        if value not in cls.choices:
            raise ValidationError(
                f"[validate token_auto_renewal error]: "
                f"token_auto_renewal only support 'true' or 'false', value: {value}"
            )
        return True


class TemplateTriggerConfig(BaseSpaceConfig):
    name = "allow_multiple_triggers"
    desc = _("是否允许配置多个触发器")
    default_value = "false"
    choices = ["true", "false"]
    control = True

    @classmethod
    def validate(cls, value: str):
        if value not in cls.choices:
            raise ValidationError(
                f"[validate allow_multiple_triggers error]: only support 'true' or 'false', value: {value}"
            )
        return True


class SpaceEngineConfig(BaseSpaceConfig):
    """
    引擎模块配置
    """

    name = "engine_space_config"
    desc = _("引擎模块配置")
    value_type = SpaceConfigValueType.REF.value
    example = {"space": {"{key1}", "{value1}"}, "scope": {"{scope_type}_{scope_value}": {"{key1}": "{value1}"}}}
    SCHEMA = {
        "type": "object",
        "properties": {
            "space": {"type": "object", "additionalProperties": {"type": ["string", "number", "boolean"]}},
            "scope": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "additionalProperties": {"type": ["string", "number", "boolean"]},
                },
            },
        },
        "additionalProperties": False,
    }

    @classmethod
    def validate(cls, value: dict):
        try:
            jsonschema.validate(instance=value, schema=cls.SCHEMA)
        except jsonschema.ValidationError as e:
            raise ValidationError(f"Configuration validation error: {str(e)} excepted: {cls.example}")


class CallbackHooksConfig(BaseSpaceConfig):
    name = "callback_hooks"
    desc = _("回调配置")
    value_type = SpaceConfigValueType.JSON.value
    is_public = False
    example = {"url": "{callback_url}", "callback_types": ["template"]}

    SCHEMA = {
        "type": "object",
        "required": ["url", "callback_types"],
        "properties": {"url": {"type": "string"}, "callback_types": {"type": "array"}},
    }

    @classmethod
    def validate(cls, value: dict):
        try:
            jsonschema.validate(value, cls.SCHEMA)
        except jsonschema.ValidationError as e:
            raise ValidationError(f"[validate callback hooks error]: {str(e)}")

        callback_url_from_apigw = check_url_from_apigw(value.get("url"))
        if not callback_url_from_apigw:
            raise ValidationError(
                "[validate callback hooks url, url show be from apigw, value: {}]".format(value.get("url"))
            )

        support_callback_types = ["template"]

        callback_types = value.get("callback_types", [])

        if not all([callback_type in support_callback_types for callback_type in callback_types]):
            raise ValidationError(
                f"[validate callback hooks callback_types, callback_type only support: {support_callback_types}]"
            )

        return True


class UniformApiConfig(BaseSpaceConfig):
    name = "uniform_api"
    value_type = SpaceConfigValueType.JSON.value
    default_value = {}
    example = {
        "api": {
            "{api_key}": {
                "meta_apis": "{meta_apis url}",
                "api_categories": "{api_categories url}",
                "display_name": "{display_name}",
            }
        }
    }
    desc = _("API 插件配置 （如更改配置，可能对已存在数据产生不兼容影响，请谨慎操作）")
    """
    仍然支持读取 旧 SCHEMA 但不能支持继续配置
    旧 SCHEMA 格式 example = {"meta_apis": "{meta_apis url}", "api_categories": "{api_categories url}"}
    """

    class Keys(Enum):
        META_APIS = "meta_apis"
        API_CATEGORIES = "api_categories"
        DISPLAY_NAME = "display_name"
        DEFAULT_DISPLAY_NAME = "API插件"
        DEFAULT_API_KEY = "default"

    @classmethod
    def check_url(cls, value):
        meta_apis_from_apigw = check_url_from_apigw(value.get(cls.Keys.META_APIS.value))
        category_config = value.get(cls.Keys.API_CATEGORIES.value)
        api_categories_from_apigw = check_url_from_apigw(category_config) if category_config else True
        if not (api_categories_from_apigw and meta_apis_from_apigw):
            raise ValidationError(
                "[validate uniform api config error]: both meta_apis and api_categories need apigw urls"
            )
        return True

    @classmethod
    def validate(cls, value: dict):
        try:
            model = SchemaV2Model(**value)
        except ValueError as e:
            raise ValidationError(f"[validate uniform api config error]: {str(e)} should have {str(cls.example)}")
        for obj in model.api.values():
            cls.check_url(obj)
        return True


class SuperusersConfig(BaseSpaceConfig):
    name = "superusers"
    desc = _("空间管理员")
    value_type = SpaceConfigValueType.JSON.value
    default_value = []
    example = ["super_user1", "super_user2", "super_user3"]

    @classmethod
    def validate(cls, value: list):
        if not isinstance(value, list):
            raise ValidationError("[validate superusers error]: superusers must be a list, value: {}".format(value))
        return True


class CanvasModeConfig(BaseSpaceConfig):
    name = "canvas_mode"
    desc = _("画布模式")
    default_value = "horizontal"
    choices = ["horizontal", "vertical"]

    @classmethod
    def validate(cls, value: str):
        if value not in cls.choices:
            raise ValidationError(
                f"[validate canvas mode error]: canvas mode only support 'horizontal' or 'vertical', value: {value}"
            )
        return True


class GatewayExpressionConfig(BaseSpaceConfig):
    name = "gateway_expression"
    desc = _("网关表达式")
    default_value = "boolrule"
    choices = ["boolrule", "FEEL", "MAKO"]

    @classmethod
    def validate(cls, value: str):
        if value not in cls.choices:
            raise ValidationError(
                f"[validate gateway expression error]: gateway expression only support "
                f"'boolrule' or 'FEEL' or 'MAKO', value: {value}"
            )
        return True


class ApiGatewayCredentialConfig(BaseSpaceConfig):
    name = "api_gateway_credential_name"
    desc = _("API_GATEWAY使用的凭证配置")
    example = {"default": "{default_credential_name}", "{scope_type}_{scope_id}": "{credential_name}"}
    value_type = SpaceConfigValueType.TEXT.value
    is_mix_type = True

    SCHEMA = {
        "type": "object",
        "patternProperties": {
            "^[^{]+_[^{]+$": {"type": "string"},
        },
        "additionalProperties": False,
        "required": ["default"],  # 必须存在 default 配置
        "properties": {"default": {"type": "string"}},
    }

    @classmethod
    def validate(cls, value):
        if isinstance(value, str):
            return True
        if isinstance(value, dict):
            try:
                jsonschema.validate(value, cls.SCHEMA)
                return True
            except jsonschema.ValidationError as e:
                raise ValidationError(f"[validate api_gateway_credential error]: {str(e)}")
        else:
            raise ValidationError(
                "[validate api_gateway_credential error]: "
                "api_gateway_credential only support string or list of json: "
                f"{cls.example}"
            )

    @classmethod
    def get_value(cls, config, *args, **kwrags):
        scope = kwrags.get("scope", None)
        config = config.json_value if config.value_type == SpaceConfigValueType.JSON.value else config.text_value
        if isinstance(config, str):
            # 如果是字符串 则只有一个默认配置
            return config
        if scope:
            # 获取特定 scope 的配置
            return config.get(scope) or config.get("default")


class SpacePluginConfig(BaseSpaceConfig):
    name = "space_plugin_config"
    desc = _("空间插件配置")
    value_type = SpaceConfigValueType.JSON.value
    example = {"default": {"mode": "{allow_list/deny_list}", "plugin_codes": ["plugin_1", "plugin_2"]}}

    @classmethod
    def validate(cls, value: dict):
        return SpacePluginConfigParser(config=value).is_valid()


class FlowVersioning(BaseSpaceConfig):
    name = "flow_versioning"
    desc = _("流程版本控制")
    default_value = "false"
    choices = ["true", "false"]
    control = True

    @classmethod
    def validate(cls, value: str):
        if value not in cls.choices:
            raise ValidationError(
                f"[validate flow version error]: flow version only support 'true' or 'false', value: {value}"
            )
        return True


# 定义 SCHEMA_V1 对应的模型
class SchemaV1Model(BaseModel):
    meta_apis: str
    api_categories: Optional[str] = None


# 定义 SCHEMA 对应的模型
class ApiModel(BaseModel):
    meta_apis: str
    api_categories: str
    display_name: str

    def get(self, field_name, default=None):
        # 由于获取插件种类/列表时候传入的 key 不确定 需要提供一个 get 方法
        return getattr(self, field_name, default)


class CommonModel(BaseModel):
    exclude_none_fields: Optional[str] = None
    enable_api_parameter_conversion: Optional[str] = None


class SchemaV2Model(BaseModel):
    api: Dict[valid_api_key, ApiModel]
    common: Optional[CommonModel] = None

    def __getattr__(self, key):
        try:
            super().__getattribute__(key)
        except AttributeError:
            # 当前没有则从 common 中获取 如果出现不存在的字段则报错
            if key not in CommonModel.__fields__:
                raise
            if self.common and hasattr(self.common, key):
                return getattr(self.common, key)
            return None


class UniformAPIConfigHandler:
    def __init__(self, config: dict):
        self.config = config

    def handle(self):
        model = None
        try:
            # 尝试按新协议解析
            model = SchemaV2Model(**self.config)
            return model
        except ValueError:
            pass
        try:
            # 兼容旧协议解析
            v1_model = SchemaV1Model(**self.config)
        except ValueError as e:
            raise ValidationError(
                f"[validate uniform api config error]: {str(e)} should have {UniformApiConfig.example}"
            )
        api_model = ApiModel(
            meta_apis=v1_model.meta_apis,
            api_categories=v1_model.api_categories,
            display_name=UniformApiConfig.Keys.DEFAULT_DISPLAY_NAME.value,
        )
        model = SchemaV2Model(api={UniformApiConfig.Keys.DEFAULT_API_KEY.value: api_model})
        return model
