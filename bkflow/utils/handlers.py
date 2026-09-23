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
import logging

import ujson as json
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger("root")

# 凭证脱敏占位符
CREDENTIAL_MASK = "******"


def mask_credential_values(data, in_place=False):
    """
    对凭证数据进行脱敏处理，将 credentials 字典中每个凭证的 value 字段值替换为掩码。

    凭证数据结构示例：
    {
        "credentials": {
            "credential_key1": {
                "bk_app_code": "app_code",
                "bk_app_secret": "secret_value",  # 会被脱敏
                ...
            },
            "credential_key2": {...}
        }
    }

    @param data: 可能包含 credentials 的数据，可以是 dict、list 或其他类型
    @param in_place: 是否原地修改。False 时返回深拷贝后的脱敏数据（默认），True 时直接修改原数据。
                     注意：当 in_place=False 时，会使用 deepcopy 进行深拷贝，对于大型嵌套结构可能有性能开销。
                     如果确定不需要保留原始数据，可以设置 in_place=True 以提高性能。
    @return: 脱敏后的数据
    """
    if data is None:
        return data

    if not in_place:
        data = copy.deepcopy(data)

    if isinstance(data, dict):
        _mask_dict_credentials(data)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                _mask_dict_credentials(item)
            elif hasattr(item, "__dict__"):
                _mask_object_credentials(item)
    elif hasattr(data, "__dict__"):
        _mask_object_credentials(data)

    return data


def _mask_object_credentials(obj):
    """
    对对象中的 credentials 属性进行脱敏处理。
    用于处理如 TaskContext 这类对象，其 credentials 是作为属性存在的。

    @param obj: 需要处理的对象
    """
    if obj is None:
        return

    # 检查对象是否有 credentials 属性
    if hasattr(obj, "credentials"):
        credentials = getattr(obj, "credentials", None)
        if isinstance(credentials, dict):
            _mask_credentials_content(credentials)
        elif credentials is not None:
            # 如果 credentials 不是字典，直接替换为脱敏占位符
            setattr(obj, "credentials", CREDENTIAL_MASK)

    # 递归处理对象的其他属性
    if hasattr(obj, "__dict__"):
        for attr_name, attr_value in vars(obj).items():
            if attr_name == "credentials":
                continue
            if isinstance(attr_value, dict):
                _mask_dict_credentials(attr_value)
            elif isinstance(attr_value, list):
                for item in attr_value:
                    if isinstance(item, dict):
                        _mask_dict_credentials(item)
                    elif hasattr(item, "__dict__"):
                        _mask_object_credentials(item)
            elif hasattr(attr_value, "__dict__") and not callable(attr_value):
                _mask_object_credentials(attr_value)


def _mask_dict_credentials(data: dict):
    """
    递归处理字典中的 credentials 字段。

    @param data: 需要处理的字典
    """
    if not isinstance(data, dict):
        return

    # 如果当前字典包含 credentials 字段，对其进行脱敏
    if "credentials" in data and isinstance(data["credentials"], dict):
        _mask_credentials_content(data["credentials"])

    # 递归处理嵌套的字典、列表和对象
    for key, value in data.items():
        if key == "credentials":
            # credentials 已经处理过了，跳过
            continue
        if isinstance(value, dict):
            _mask_dict_credentials(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _mask_dict_credentials(item)
                elif hasattr(item, "__dict__"):
                    _mask_object_credentials(item)
        elif hasattr(value, "__dict__") and not callable(value):
            # 处理对象类型的值（如 TaskContext 实例）
            _mask_object_credentials(value)


def _mask_credentials_content(credentials: dict):
    """
    对 credentials 字典内容进行脱敏。
    credentials 结构为 {credential_key: credential_dict}，
    其中 credential_dict 包含敏感字段如 bk_app_secret、token 等。

    脱敏策略：
    1. 如果凭证值是字典且包含已知敏感字段，则只脱敏这些敏感字段
    2. 如果凭证值是字典但不包含任何已知敏感字段，则将整个字典脱敏为 "{***}"
    3. 如果凭证值是字符串，直接脱敏

    @param credentials: 凭证字典
    """
    # 需要脱敏的敏感字段名列表
    sensitive_fields = {
        "bk_app_secret",
        "app_secret",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "api_key",
        "private_key",
        "secret_key",
    }

    for cred_key, cred_value in list(credentials.items()):
        if isinstance(cred_value, dict):
            # 检查是否包含任何已知的敏感字段
            has_sensitive_field = any(field in cred_value for field in sensitive_fields)
            if has_sensitive_field:
                # 只脱敏已知的敏感字段
                for field in sensitive_fields:
                    if field in cred_value:
                        cred_value[field] = CREDENTIAL_MASK
            else:
                # 如果没有匹配到已知敏感字段，可能使用了自定义字段名
                # 为安全起见，将整个凭证字典脱敏
                credentials[cred_key] = "{***}"
        elif isinstance(cred_value, str):
            # 如果整个凭证值就是一个字符串（比如 token），直接脱敏
            credentials[cred_key] = CREDENTIAL_MASK


def mask_sensitive_data_for_display(data, in_place=False):
    """
    用于展示的数据脱敏函数，会处理以下敏感数据：
    1. credentials 凭证信息
    2. 其他可能的敏感字段

    @param data: 需要脱敏的数据
    @param in_place: 是否原地修改
    @return: 脱敏后的数据
    """
    return mask_credential_values(data, in_place=in_place)


def handle_api_error(system, api_name, params, result):
    request_id = result.get("request_id", "")

    message = _("调用{system}接口{api_name}返回失败, params={params}, error={error}").format(
        system=system, api_name=api_name, params=json.dumps(params), error=result.get("message", "")
    )
    if request_id:
        message = "{}, request_id={}".format(message, request_id)

    logger.error(message)

    # 对 message 进行脱敏处理后返回
    message = handle_plain_log(message)
    return message


def mask_credentials_in_string(text):
    """
    对字符串中可能包含的 credentials 敏感信息进行脱敏。
    使用正则表达式匹配常见的敏感字段模式并进行替换。

    @param text: 需要脱敏的字符串
    @return: 脱敏后的字符串
    """
    import re

    if not isinstance(text, str):
        return text

    # 需要脱敏的敏感字段名列表
    sensitive_fields = [
        "bk_app_secret",
        "app_secret",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "api_key",
        "private_key",
        "secret_key",
    ]

    result = text
    for field in sensitive_fields:
        # 匹配 "field": "xxx" 或 'field': 'xxx' 模式
        # JSON 双引号格式
        pattern1 = rf'"{field}"\s*:\s*"[^"]*"'
        result = re.sub(pattern1, f'"{field}": "{CREDENTIAL_MASK}"', result, flags=re.IGNORECASE)
        # Python 单引号格式
        pattern2 = rf"'{field}'\s*:\s*'[^']*'"
        result = re.sub(pattern2, f"'{field}': '{CREDENTIAL_MASK}'", result, flags=re.IGNORECASE)
        # 混合格式 "field": 'xxx'
        pattern3 = rf'"{field}"\s*:\s*\'[^\']*\''
        result = re.sub(pattern3, f"\"{field}\": '{CREDENTIAL_MASK}'", result, flags=re.IGNORECASE)
        # 混合格式 'field': "xxx"
        pattern4 = rf"'{field}'\s*:\s*\"[^\"]*\""
        result = re.sub(pattern4, f"'{field}': \"{CREDENTIAL_MASK}\"", result, flags=re.IGNORECASE)

    return result


def handle_plain_log(plain_log):
    """
    处理日志中的敏感信息，包括：
    1. LOG_SHIELDING_KEYWORDS 配置的关键字
    2. credentials 中的敏感字段

    @param plain_log: 需要处理的日志字符串
    @return: 脱敏后的日志字符串
    """
    if plain_log:
        # 处理配置的屏蔽关键字
        for key_word in settings.LOG_SHIELDING_KEYWORDS:
            plain_log = plain_log.replace(key_word, CREDENTIAL_MASK)
        # 处理 credentials 中的敏感字段
        plain_log = mask_credentials_in_string(plain_log)
    return plain_log
