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
import logging
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
logger = logging.getLogger("root")


class SpaceConfigValueType(Enum):
    # json 类型
    JSON = "JSON"
    # 文本类型
    TEXT = "TEXT"
    # 引用类型 存储在 engine
    REF = "REF"


class SpaceConfigVerifyNotSupported(Exception):
    """配置项不支持验证"""

    pass


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
    group = None  # 分组 key：access_security / flow_canvas / api_integration
    help = None  # {"summary": 用途, "effect": 影响, "media": [{type, src, caption}], "doc_link": url}
    ui = None  # 控件描述
    verifiable = False  # 是否支持"测试/验证"

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
            "group": cls.group,
            "help": cls.help,
            "ui": cls.ui,
            "verifiable": cls.verifiable,
        }

    @classmethod
    def validate(cls, value):
        return True

    @classmethod
    def verify(cls, space_id, value, **params):
        """验证配置（真实连通性/预览）。默认不支持。"""
        raise SpaceConfigVerifyNotSupported(f"config '{cls.name}' does not support verify")

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
    example = "[n]h or [n]d, h->hour d->day, at least 1h"
    LEAST_EXPIRATION_SECONDS = 60 * 60 * 1

    group = "access_security"
    help = {
        "summary": _("访问 Token 的有效期"),
        "effect": _("Token 到该时间节点之后自动过期"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "input",
        "label": _("设置过期时间"),
        "help": _("最短 1 小时，单位可选择小时/天"),
        "placeholder": "1h",
        "validation": {"type": "duration", "min": "1h"},
    }

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
    desc = _("Token自动续期")
    default_value = "true"
    choices = ["true", "false"]
    control = True

    group = "access_security"
    help = {
        "summary": _("Token 临近过期时是否自动续期"),
        "effect": _("Token 临近过期时自动延长有效期，减少调用中断"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "switch",
        "label": _("启用自动续期"),
        "true_value": "true",
        "false_value": "false",
        "help": _("关闭后到期即失效，需重新获取")
    }

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

    group = "flow_canvas"
    help = {
        "summary": _("单个流程是否允许配置多个触发器"),
        "effect": _("开启：一个流程可挂多个触发器（定时/事件）同时生效；关闭：仅允许一个"),
        "media": [],
        "doc_link": "",
    }
    ui = {"control": "switch", "label": _("允许多触发器"), "true_value": "true", "false_value": "false"}

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

    group = "api_integration"
    help = {
        "summary": _("下发给引擎的运行参数（高级）"),
        "effect": _("space 为空间级键值，scope 为按作用域覆盖的键值；影响引擎运行行为，请谨慎修改"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "engine_kv",
        "label": _("引擎模块配置"),
        "help": _("键值仅支持字符串/数字/布尔"),
    }

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
    is_public = False

    @classmethod
    def validate(cls, value: dict):
        try:
            jsonschema.validate(instance=value, schema=cls.SCHEMA)
        except jsonschema.ValidationError as e:
            raise ValidationError(f"Configuration validation error: {str(e)} excepted: {cls.example}")
        return True


class CallbackHooksConfig(BaseSpaceConfig):
    name = "callback_hooks"
    desc = _("回调配置")
    value_type = SpaceConfigValueType.JSON.value
    is_public = True
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
                "source_key": "{open plugin execution source key}",
                "catalog_mode": "remote/cache_first/cache_only",
                "headers": {"X-Custom-Header": "${_system.operator}"},
            }
        }
    }
    desc = _("API插件")
    """
    仍然支持读取 旧 SCHEMA 但不能支持继续配置
    旧 SCHEMA 格式 example = {"meta_apis": "{meta_apis url}", "api_categories": "{api_categories url}"}
    """

    group = "api_integration"
    verifiable = True
    help = {
        "summary": _("接入统一 API 平台，把外部 API 暴露为可编排的 API 插件"),
        "effect": _("管理API相关api_key的结构化接入与可视化解析；每个api_key一条接入信息"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "api_plugin_config",
        "label": _("API 插件"),
        "help": _("每个 api_key 配置 display_name / meta_apis(apigw URL) / api_categories(可选) / headers"),
        "validation": {"type": "apigw_url"},
    }

    class Keys(Enum):
        META_APIS = "meta_apis"
        API_CATEGORIES = "api_categories"
        DISPLAY_NAME = "display_name"
        CATALOG_MODE = "catalog_mode"
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

    @classmethod
    def verify(cls, space_id=None, value=None, api_key=None, credential_name=None, operator=None, **kwargs):
        """一键测试：依次调用 category_list / list / meta 三个接口，验证接入是否可用。

        :param space_id: 空间id
        :param value: 待测的 uniform_api 配置（表单当前值；为空则回退到已存配置）
        :param api_key: 待测 api_key，默认 default
        :param credential_name: 用于鉴权的凭证名，默认取空间默认网关凭证
        :param operator: 操作人用户名，用于 apigw 请求头
        """
        from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
        from bkflow.space.models import Credential, SpaceConfig

        # 获取待测试的api
        if not value:
            config_obj = SpaceConfig.objects.filter(space_id=space_id, name=cls.name).first()
            if config_obj:
                value = config_obj.json_value if config_obj.value_type == SpaceConfigValueType.JSON.value else {}
            else:
                value = {}

        try:
            model = UniformAPIConfigHandler(value).handle()
        except Exception as e:
            raise ValidationError(f"[uniform_api verify] 配置解析失败: {e}")

        api_key = api_key or cls.Keys.DEFAULT_API_KEY.value
        api_obj = model.api.get(api_key)
        if not api_obj:
            raise ValidationError(f"[uniform_api verify] 未找到 api_key={api_key} 的配置")
        meta_url = api_obj.get(cls.Keys.META_APIS.value)
        api_categories_url = api_obj.get(cls.Keys.API_CATEGORIES.value)
        if not meta_url:
            raise ValidationError(f"[uniform_api verify] api_key={api_key} 未配置 meta_apis")

        if not api_categories_url:
            raise ValidationError(f"[uniform_api verify] api_key={api_key} 未配置 api_categories_url")

        logger.info(f"[uniform_api verify] 待测试api.meta_url: {meta_url}，api_categories_url：{api_categories_url}")

        # 获取测试用的凭证
        if not credential_name:
            cred_config = SpaceConfig.objects.filter(
                space_id=space_id, name=ApiGatewayCredentialConfig.name).first()
            if cred_config:
                credential_name = ApiGatewayCredentialConfig.get_value(cred_config, scope='default')

        if not credential_name:
            raise ValidationError("[uniform_api verify] 空间未配置默认网关凭证，无法测试")

        credential = Credential.objects.filter(space_id=space_id, name=credential_name).first()
        if credential is None:
            raise ValidationError(f"[uniform_api verify] 凭证 {credential_name} 不存在")

        content = credential.content or {}
        if not content.get("bk_app_code") or not content.get("bk_app_secret"):
            raise ValidationError(f"[uniform_api verify] 凭证 {credential_name} 缺少 bk_app_code/bk_app_secret")

        client = UniformAPIClient(from_apigw_check=False)
        headers = client.gen_default_apigw_header(
            app_code=content["bk_app_code"],
            app_secret=content["bk_app_secret"],
            username=operator or "admin",
        )
        logger.info(
            f"[uniform_api verify] 测试用凭证.credential_name: {credential_name},app_code: {content['bk_app_code']}，app_secret: ******，username：{operator}")
        # 1. 调用 category_list 接口 → 获取分类列表
        cat_result = client.request(
            url=api_categories_url,
            method="GET",
            data={},
            headers=headers,
            username=operator
        )
        if not cat_result.result:
            raise ValidationError(f"[uniform_api verify] categories 接口请求失败: {cat_result.message}")
        categories = cat_result.json_resp.get('data') or []
        category_length = len(categories)

        # 2. 调用 list 接口 → 获取接口总数和列表（用第一个分类做 category 参数）
        list_request_data = {
            "limit": 50,
            "offset": 0,
        }

        api_list = []
        api_length = 0
        for category in categories:
            list_request_data["category"] = category.get("id", "all")
            list_result = client.request(
                url=meta_url,
                method="GET",
                data=list_request_data,
                headers=headers,
                username=operator
            )
            if not list_result.result:
                logger.error(
                    f"[uniform_api verify] list 接口请求失败: {list_result.message},data: {str(list_request_data)}")
                raise ValidationError(f"[uniform_api verify] list 接口请求失败: {list_result.message}")
            list_data = list_result.json_resp.get("data", {})
            api_length += list_data.get("total", 0)

            # 取某个分类的api
            if not api_list:
                for api in list_data.get('apis') or []:
                    api_list.append(api)

        # 3. 调用 meta 接口 → 取 list 返回的最多 5 个 api 的 meta_url
        samples = []
        for item in api_list:
            if len(samples) > 5:
                break
            meta_url_detail = item.get("meta_url")
            if not meta_url_detail:
                continue
            meta_result = client.request(
                url=meta_url_detail, method="GET", data={}, headers=headers, username=operator or "admin"
            )
            if not meta_result.result:
                logger.error(
                    f"[uniform_api verify] meta_url_detail 接口请求失败: {meta_result.message},meta_url_detail: {meta_url_detail}")
                raise ValidationError(f"[uniform_api verify] meta_url_detail 接口请求失败: {meta_result.message}")
            meta_data = meta_result.json_resp.get("data", {})
            samples.append({
                "id": meta_data.get("id", ""),
                "name": meta_data.get("name", ""),
                "method": meta_data.get("methods", [""])[0] if meta_data.get("methods") else ""
            })

        return {
            "api_key": api_key,
            "credential_name": credential_name,
            "category_length": category_length,
            "api_length": api_length,
            "samples": samples,
        }


class SuperusersConfig(BaseSpaceConfig):
    name = "superusers"
    desc = _("空间管理员")
    value_type = SpaceConfigValueType.JSON.value
    default_value = []
    example = ["super_user1", "super_user2", "super_user3"]

    group = "access_security"
    help = {
        "summary": _("空间的超级管理员"),
        "effect": _("拥有本空间全部管理权限，加入后可管理配置、凭证与全部流程/任务"),
        "media": [],
        "doc_link": "",
    }
    ui = {"control": "member_selector", "label": _("配置管理员"), "placeholder": _("请选择成员")}

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

    group = "flow_canvas"
    help = {
        "summary": _("流程画布的默认排布方向"),
        "effect": _("控制流程画布中节点的默认排布方向"),
        "media": [{"type": "gif", "src": "", "caption": _("横向 vs 纵向 排布示意")}],
        "doc_link": "",
    }
    ui = {
        "control": "radio",
        "label": _("画布模式"),
        "help": _("切换后新建流程画布按所选方向排布"),
        "options": [
            {"value": "horizontal", "label": _("横向"), "desc": _("节点从左到右排布，适合较线性的流程")},
            {"value": "vertical", "label": _("纵向"), "desc": _("节点从上到下排布，适合分支多、层级清晰的流程")},
        ],
    }

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

    group = "flow_canvas"
    help = {
        "summary": _("分支网关条件使用的表达式语言"),
        "effect": _("影响分支网关条件的书写与求值方式；修改仅影响此后新建/编辑的条件"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "radio",
        "label": _("表达式类型"),
        "options": [
            {"value": "boolrule", "label": _("Boolrule（默认）"), "desc": _("简单布尔规则，可视化友好，适合常规条件")},
            {"value": "FEEL", "label": "FEEL", "desc": _("DMN 标准表达式，功能强，适合复杂决策")},
            {"value": "MAKO", "label": "MAKO", "desc": _("Python 模板表达式，最灵活但需谨慎")},
        ],
    }

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
    desc = _("网关凭证")
    example = {"default": "{default_credential_name}", "{scope_type}_{scope_id}": "{credential_name}"}
    value_type = SpaceConfigValueType.TEXT.value
    is_mix_type = True

    group = "access_security"
    help = {
        "summary": _("网关调用使用哪个凭证（引用凭证管理里的 BK_APP 凭证）"),
        "effect": _("适用于 [凭证管理] 中的BK_APP 凭证访问统一API网关。本质是一张 [作用域] 到 [凭证] 的路由表。"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "credential_map",
        "label": _("网关凭证"),
        "help": _("默认凭证必选；可按作用域（scope_type_scope_value）追加覆盖"),
        "data_source": {"type": "credential", "credential_type": "BK_APP"},
    }

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

    group = "api_integration"
    help = {
        "summary": _("控制本空间可用的插件范围"),
        "effect": _("allow_list 仅允许所列插件，deny_list 屏蔽所列插件；影响流程编辑时可选插件"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "plugin_scope",
        "label": _("空间插件"),
        "help": _("选择模式并配置插件 code 列表"),
    }

    @classmethod
    def validate(cls, value: dict):
        return SpacePluginConfigParser(config=value).is_valid()


class FlowVersioning(BaseSpaceConfig):
    name = "flow_versioning"
    desc = _("流程版本控制")
    default_value = "false"
    choices = ["true", "false"]
    control = True

    group = "flow_canvas"
    help = {
        "summary": _("是否开启流程版本管理"),
        "effect": _("开启：流程保存产生版本、可回溯与回滚；关闭：仅保留最新版本"),
        "media": [],
        "doc_link": "",
    }
    ui = {"control": "switch", "label": _("版本控制"), "true_value": "true", "false_value": "false"}

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


class UniformAPICatalogMode(str, Enum):
    REMOTE = "remote"
    CACHE_FIRST = "cache_first"
    CACHE_ONLY = "cache_only"


# 定义 SCHEMA 对应的模型
class ApiModel(BaseModel):
    meta_apis: str
    api_categories: str
    display_name: str
    source_key: Optional[str] = None
    catalog_mode: UniformAPICatalogMode = UniformAPICatalogMode.REMOTE
    headers: Optional[dict] = None

    def get(self, field_name, default=None):
        # 由于获取插件种类/列表时候传入的 key 不确定 需要提供一个 get 方法
        return getattr(self, field_name, default)


class CommonModel(BaseModel):
    exclude_none_fields: Optional[str] = None
    enable_api_parameter_conversion: Optional[str] = None
    enable_standard_response: Optional[str] = None


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
