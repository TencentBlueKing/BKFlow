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
import concurrent.futures

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pipeline.component_framework.models import ComponentModel
from rest_framework.exceptions import NotFound, PermissionDenied

from bkflow.bk_plugin.models import AuthStatus, BKPlugin, BKPluginAuthorization
from bkflow.exceptions import APIResponseError
from bkflow.pipeline_plugins.query.uniform_api.uniform_api import _get_api_credential
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.plugin.models import SpacePluginConfig as SpacePluginConfigModel
from bkflow.plugin.serializers.comonent import PluginType


class UniformApiPluginHandler:
    def __init__(self, data):
        self.data = data

    def get_plugin_detail(self):
        target_fields = self.data.get("target_fields", [])
        plugin_details = {}
        space_id = self.data.get("space_id")
        template_id = self.data.get("template_id")

        # 获取共享的 credential 信息
        credential = _get_api_credential(space_id=space_id, template_id=template_id)
        client = UniformAPIClient()
        header = client.gen_default_apigw_header(
            app_code=credential["bk_app_code"], app_secret=credential["bk_app_secret"]
        )

        # 使用并发请求插件信息
        # TODO: 优化并发请求可能导致的 CPU 飙升 (缓存部分插件信息)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_plugin_code = {
                executor.submit(
                    self.fetch_plugin_data, client, plugin["plugin_code"], plugin["meta_url"], header
                ): plugin["plugin_code"]
                for plugin in self.data.get(PluginType.UNIFORM_API.value, [])
            }

            for future in concurrent.futures.as_completed(future_to_plugin_code):
                plugin_code = future_to_plugin_code[future]
                plugin_data = future.result()
                plugin_details[plugin_code] = {field: plugin_data.get(field) for field in target_fields}

        return plugin_details

    def fetch_plugin_data(self, client, meta_url, header):
        # 发起请求并返回数据
        resp = client.request(
            url=meta_url,
            method="GET",
            headers=header,
        )
        if resp.result is False:
            raise APIResponseError(f"请求统一API元数据失败: {resp.message}")

        # 验证返回数据结构
        client.validate_response_data(resp.json_resp.get("data", {}), client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)
        return resp.json_resp["data"]


class ComponentPluginHandler:
    def __init__(self, data):
        self.data = data

    def get_plugin_detail(self):
        plugin_codes = [plugin["plugin_code"] for plugin in self.data.get(PluginType.COMPONENT.value, [])]
        target_fields = self.data.get("target_fields", [])

        plugins = ComponentModel.objects.filter(code__in=plugin_codes)

        if not plugins.exists():
            raise NotFound(_("Plugin {} not found.").format(plugin_codes))
        # 此处是批量接口 是否需要校验符合可见性
        restricted_plugins = set(settings.SPACE_PLUGIN_LIST)
        allow_list = SpacePluginConfigModel.objects.get_space_allow_list(self.data["space_id"])

        # 过滤需要检查权限的插件
        intersection_with_restricted = restricted_plugins.intersection(set(plugin_codes))

        # 检查交集是否都在 allow_list 中
        if intersection_with_restricted:
            unauthorized_plugins = intersection_with_restricted - set(allow_list)
            if unauthorized_plugins:
                raise PermissionDenied(
                    _("Plugins {} not allowed for space {}.").format(unauthorized_plugins, self.data["space_id"])
                )

        results = {}
        for plugin in plugins:
            plugin_data = {field: getattr(plugin, field, None) for field in target_fields}
            results[plugin.code] = plugin_data
        return results


class BluekingPluginHandler:
    def __init__(self, data):
        self.data = data

    def get_plugin_detail(self):
        plugin_codes = [plugin["plugin_code"] for plugin in self.data.get(PluginType.BLUEKING.value, [])]
        target_fields = self.data.get("target_fields", [])

        plugins = BKPlugin.objects.filter(code__in=plugin_codes)
        if not plugins.exists():
            raise NotFound(_("Plugin {} not found.").format(plugin_codes))
        authorized_plugins = BKPluginAuthorization.objects.filter(
            code__in=plugin_codes, status=AuthStatus.authorized.value
        )
        authorized_dict = {plugin.code: plugin.white_list for plugin in authorized_plugins}
        results = {}
        for plugin in plugins:
            # 检查插件是否被授权
            if plugin.code not in authorized_dict:
                raise PermissionDenied(
                    _("Plugin {} is not authorized for space {}").format(plugin.code, self.data["space_id"])
                )
            white_list = authorized_dict.get(plugin.code)
            # white_list 可能是 * 或对应的 space_id
            if "*" not in white_list and str(self.data["space_id"]) not in white_list:
                raise PermissionDenied(
                    _("Plugin {} is not authorized for space {}").format(plugin.code, self.data["space_id"])
                )

            plugin_data = {field: getattr(plugin, field, None) for field in target_fields}
            results[plugin.code] = plugin_data
        return results


class PluginQueryDispatcher:
    PLUGIN_MAP = {
        PluginType.UNIFORM_API.value: UniformApiPluginHandler,
        PluginType.COMPONENT.value: ComponentPluginHandler,
        PluginType.BLUEKING.value: BluekingPluginHandler,
    }

    def __init__(self, plugin_type, data):
        plugin_cls = self.PLUGIN_MAP.get(plugin_type)
        if plugin_cls is None:
            raise NotFound(_("Plugin type {} not supported.").format(plugin_type))
        self.instance = plugin_cls(data=data)
