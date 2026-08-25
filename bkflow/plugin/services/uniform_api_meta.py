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

from bkflow.exceptions import ValidationError
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient


class UniformAPIMetaError(ValueError):
    """统一 API meta 响应无效，不得写入缓存或快照。"""


def is_v4_wrapper_version(*wrapper_versions):
    """判断 wrapper_version 是否属于开放插件 V4。"""
    for wrapper_version in wrapper_versions:
        major = str(wrapper_version or "").lower().lstrip("v").split(".", 1)[0]
        if major == "4":
            return True
    return False


def extract_uniform_api_meta_data(result, requested_version=None, catalog_wrapper_version=None):
    """
    校验 UniformAPIClient.request 的 meta 响应并返回 data。

    :param result: HttpRequestResult
    :param requested_version: 请求的精确插件版本
    :param catalog_wrapper_version: 目录中记录的 wrapper_version
    :return: provider 返回的 data 字典
    :raises UniformAPIMetaError: 传输失败、业务失败、缺少 data、版本不一致或 schema 不合法
    """
    if not getattr(result, "result", False):
        raise UniformAPIMetaError("请求统一API元数据失败: {}".format(getattr(result, "message", "") or "provider 返回失败"))

    json_resp = getattr(result, "json_resp", None)
    if not isinstance(json_resp, dict) or json_resp.get("result") is not True:
        message = json_resp.get("message", "") if isinstance(json_resp, dict) else ""
        raise UniformAPIMetaError("请求统一API元数据失败: {}".format(message or "provider 返回失败"))

    data = json_resp.get("data")
    if not isinstance(data, dict):
        raise UniformAPIMetaError("请求统一API元数据失败: 响应体缺少 data 对象")

    provider_version = data.get("plugin_version")
    if is_v4_wrapper_version(catalog_wrapper_version, data.get("wrapper_version")) and not provider_version:
        raise UniformAPIMetaError("V4 统一API响应缺少 plugin_version，无法校验请求版本 [{}]".format(requested_version))
    if (
        provider_version is not None
        and requested_version is not None
        and str(provider_version) != str(requested_version)
    ):
        raise UniformAPIMetaError(
            "统一API响应插件版本与请求版本不一致: 请求版本 [{}], 响应版本 [{}]".format(
                requested_version,
                provider_version,
            )
        )

    try:
        UniformAPIClient.validate_response_data(data, UniformAPIClient.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)
    except ValidationError as exc:
        raise UniformAPIMetaError(str(exc)) from exc

    return data
