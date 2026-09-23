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
import re
from dataclasses import dataclass
from typing import Optional

from pipeline.component_framework.models import ComponentModel

from bkflow.bk_plugin.models import BKPlugin
from bkflow.pipeline_converter.constants import A2FlowPluginType
from bkflow.pipeline_converter.exceptions import A2FlowConvertError, ErrorTypes

logger = logging.getLogger("root")


@dataclass
class ResolvedPlugin:
    """插件类型识别后的中间表示"""

    plugin_type: str
    original_code: str
    wrapper_code: str
    wrapper_version: str
    api_meta: Optional[dict] = None
    remote_plugin_version: Optional[str] = None


class PluginResolver:
    """
    根据 code 和可选的 plugin_type 提示，识别插件类型并生成 pipeline_tree 所需的包装信息。

    识别策略：
    1. 如果 plugin_type 已指定 → 直接按指定类型处理
    2. 如果未指定 → 依次查 ComponentModel、BKPlugin，都不匹配则报错
    3. 如果同时匹配多个注册表 → 报 AMBIGUOUS_PLUGIN_CODE
    """

    REMOTE_PLUGIN_VERSION = "1.0.0"

    def __init__(self, space_id, username=None, scope_type=None, scope_value=None):
        self.space_id = space_id
        self.username = username
        self.scope_type = scope_type
        self.scope_value = scope_value

    def resolve(self, code, plugin_type_hint=None):
        if plugin_type_hint:
            return self._resolve_by_type(code, plugin_type_hint)
        return self._auto_resolve(code)

    def resolve_batch(self, nodes_info):
        results = {}
        for info in nodes_info:
            code = info["code"]
            cache_key = (code, info.get("plugin_type"))
            if cache_key not in results:
                results[cache_key] = self.resolve(code, info.get("plugin_type"))
        return results

    def _resolve_by_type(self, code, plugin_type):
        if plugin_type == A2FlowPluginType.COMPONENT.value:
            return self._resolve_as_component(code)
        elif plugin_type == A2FlowPluginType.REMOTE_PLUGIN.value:
            return self._resolve_as_remote_plugin(code)
        elif plugin_type == A2FlowPluginType.UNIFORM_API.value:
            return self._resolve_as_uniform_api(code)
        else:
            raise A2FlowConvertError(
                error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                message="不支持的 plugin_type: {}".format(plugin_type),
                field="plugin_type",
                value=plugin_type,
                hint="可选值: {}".format([e.value for e in A2FlowPluginType]),
            )

    def _auto_resolve(self, code):
        is_component = bool(ComponentModel.objects.filter(code=code, status=1).values_list("version", flat=True))
        is_bk_plugin = BKPlugin.objects.filter(code=code).exists()
        uniform_api_meta = self._safe_fetch_uniform_api_meta(code)

        hit_types = [
            flag
            for flag, ok in [
                ("component", is_component),
                ("remote_plugin", is_bk_plugin),
                ("uniform_api", bool(uniform_api_meta)),
            ]
            if ok
        ]
        if len(hit_types) > 1:
            raise A2FlowConvertError(
                error_type=ErrorTypes.AMBIGUOUS_PLUGIN_CODE,
                message="插件 code '{}' 在多个插件注册表中同时存在，请指定 plugin_type 消歧".format(code),
                field="plugin_type",
                value=code,
                hint="在节点中添加 plugin_type 字段，可选值: component, remote_plugin, uniform_api",
            )

        if is_component:
            return self._resolve_as_component(code)
        if is_bk_plugin:
            return self._resolve_as_remote_plugin(code)
        if uniform_api_meta:
            return self._resolve_as_uniform_api(code)

        raise A2FlowConvertError(
            error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
            message="未找到插件 code '{}'，请检查插件是否存在或是否需要指定 plugin_type".format(code),
            field="code",
            value=code,
            hint="请检查 code 是否存在；若发生同名冲突，可显式指定 plugin_type",
        )

    def _safe_fetch_uniform_api_meta(self, code):
        try:
            return self._fetch_uniform_api_meta(code)
        except A2FlowConvertError:
            return None

    def _resolve_as_component(self, code):
        versions = list(ComponentModel.objects.filter(code=code, status=1).values_list("version", flat=True))
        version = self._pick_latest_version(versions) if versions else "legacy"
        return ResolvedPlugin(
            plugin_type=A2FlowPluginType.COMPONENT.value,
            original_code=code,
            wrapper_code=code,
            wrapper_version=version,
        )

    def _resolve_as_remote_plugin(self, code):
        return ResolvedPlugin(
            plugin_type=A2FlowPluginType.REMOTE_PLUGIN.value,
            original_code=code,
            wrapper_code="remote_plugin",
            wrapper_version=self.REMOTE_PLUGIN_VERSION,
            remote_plugin_version=self._fetch_remote_plugin_version(code),
        )

    def _fetch_remote_plugin_version(self, code):
        from plugin_service.plugin_client import PluginServiceApiClient

        client = PluginServiceApiClient(code)
        result = client.get_meta()
        if not result["result"]:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="查询蓝鲸标准插件版本失败: {}".format(result.get("message")),
                value=code,
            )

        versions = result["data"].get("versions") or []
        if not versions:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="蓝鲸标准插件 '{}' 没有可用版本".format(code),
                value=code,
            )
        return self._pick_latest_version(versions)

    def _resolve_as_uniform_api(self, code):
        versions = list(ComponentModel.objects.filter(code="uniform_api", status=1).values_list("version", flat=True))
        version = self._pick_latest_version(versions) if versions else "v2.0.0"
        api_meta = self._fetch_uniform_api_meta(code)
        return ResolvedPlugin(
            plugin_type=A2FlowPluginType.UNIFORM_API.value,
            original_code=code,
            wrapper_code="uniform_api",
            wrapper_version=version,
            api_meta=api_meta,
        )

    def _fetch_uniform_api_meta(self, code):
        from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
        from bkflow.space.configs import (
            ApiGatewayCredentialConfig,
            UniformApiConfig,
            UniformAPIConfigHandler,
        )
        from bkflow.space.models import Credential, SpaceConfig

        uniform_api_config = SpaceConfig.get_config(space_id=self.space_id, config_name=UniformApiConfig.name)
        if not uniform_api_config:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="空间未配置 uniform_api，无法解析 API 插件 '{}'".format(code),
                value=code,
            )

        config = UniformAPIConfigHandler(uniform_api_config).handle()
        api_key = UniformApiConfig.Keys.DEFAULT_API_KEY.value
        meta_apis_url = config.api.get(api_key, {}).get(UniformApiConfig.Keys.META_APIS.value)
        if not meta_apis_url:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="空间 uniform_api 配置缺少 meta_apis 地址，无法解析 '{}'".format(code),
                value=code,
            )

        scope = "{}_{}".format(self.scope_type, self.scope_value) if self.scope_type and self.scope_value else None
        credential_name = SpaceConfig.get_config(
            space_id=self.space_id, config_name=ApiGatewayCredentialConfig.name, scope=scope
        )
        credential = Credential.objects.filter(space_id=self.space_id, name=credential_name).first()
        if not credential:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="空间缺少 API Gateway 凭证，无法解析 API 插件 '{}'".format(code),
                value=code,
            )

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(
            app_code=credential.content["bk_app_code"],
            app_secret=credential.content["bk_app_secret"],
            username=self.username or "admin",
        )
        list_result = client.request(
            url=meta_apis_url,
            method="GET",
            data={"limit": 200, "offset": 0},
            headers=headers,
            username=self.username or "admin",
        )
        client.validate_response_data(
            list_result.json_resp.get("data", {}), client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA
        )
        api_item = next((item for item in list_result.json_resp["data"]["apis"] if item["id"] == code), None)
        if not api_item:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="未在空间 uniform_api 列表中找到 API 插件 '{}'".format(code),
                value=code,
            )

        meta_result = client.request(
            url=api_item["meta_url"],
            method="GET",
            data={},
            headers=headers,
            username=self.username or "admin",
        )
        client.validate_response_data(
            meta_result.json_resp.get("data", {}), client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA
        )
        meta = meta_result.json_resp["data"]
        meta.update({"meta_url": api_item["meta_url"], "api_key": api_key})
        return meta

    @staticmethod
    def _parse_version(version_str):
        if not version_str or version_str == "legacy":
            return (0, 0, 0)
        version_str = version_str.lstrip("vV")
        match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version_str)
        if match:
            return (
                int(match.group(1) or 0),
                int(match.group(2) or 0),
                int(match.group(3) or 0),
            )
        return (0, 0, 0)

    @classmethod
    def _pick_latest_version(cls, versions):
        if not versions:
            return "legacy"
        latest = None
        latest_tuple = (0, 0, 0)
        for v in versions:
            vt = cls._parse_version(v)
            if vt > latest_tuple:
                latest_tuple = vt
                latest = v
        return latest or "legacy"
