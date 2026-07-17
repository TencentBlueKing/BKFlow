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

from django.conf import settings

from bkflow.exceptions import APIResponseError, ValidationError
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService
from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    UniformApiConfig,
    UniformAPIConfigHandler,
)
from bkflow.space.models import Credential, SpaceConfig


class OpenPluginCatalogService:
    @classmethod
    def sync_space_plugins(cls, space_id, source_key=None, username="admin"):
        source_plugins = {}
        for api_key, api_entry in cls._get_sources(space_id=space_id, source_key=source_key).items():
            current_source_key = cls._effective_source_key(api_key=api_key, api_entry=api_entry)
            api_list = cls._fetch_api_list(
                space_id=space_id,
                api_entry=api_entry,
                username=username,
            )
            plugins_by_id = source_plugins.setdefault(current_source_key, {})
            plugins_by_id.update({api_item["id"]: api_item for api_item in api_list})

        for current_source_key, plugins_by_id in source_plugins.items():
            cls._refresh_catalog_index(
                space_id=space_id,
                source_key=current_source_key,
                api_list=list(plugins_by_id.values()),
            )
        return list(source_plugins.keys())

    @classmethod
    def list_space_plugins(cls, space_id, source_key=None):
        catalog_qs = OpenPluginCatalogIndex.objects.filter(space_id=space_id).order_by("source_key", "plugin_name")
        granted_source_keys = set(OpenPluginGrantService.granted_source_keys(space_id))
        if source_key:
            if source_key not in granted_source_keys:
                return []
            catalog_qs = catalog_qs.filter(source_key=source_key)
        else:
            if not granted_source_keys:
                return []
            catalog_qs = catalog_qs.filter(source_key__in=granted_source_keys)

        availability_qs = SpaceOpenPluginAvailability.objects.filter(space_id=space_id)
        if source_key:
            availability_qs = availability_qs.filter(source_key=source_key)
        else:
            availability_qs = availability_qs.filter(source_key__in=granted_source_keys)

        enabled_map = {
            (item.source_key, item.plugin_id): item.enabled
            for item in availability_qs.only("source_key", "plugin_id", "enabled")
        }

        return [
            {
                "source_key": item.source_key,
                "plugin_id": item.plugin_id,
                "plugin_code": item.plugin_code,
                "plugin_name": item.plugin_name,
                "plugin_source": item.plugin_source,
                "group_name": item.group_name,
                "wrapper_version": item.wrapper_version,
                "default_version": item.default_version,
                "latest_version": item.latest_version,
                "versions": item.versions,
                "status": item.status,
                "enabled": enabled_map.get((item.source_key, item.plugin_id), False),
            }
            for item in catalog_qs
        ]

    @classmethod
    def toggle_plugin(cls, space_id, source_key, plugin_id, enabled):
        availability, _ = SpaceOpenPluginAvailability.objects.update_or_create(
            space_id=space_id,
            source_key=source_key,
            plugin_id=plugin_id,
            defaults={"enabled": enabled},
        )
        return availability

    @classmethod
    def enable_all_visible_plugins(cls, space_id, source_key=None):
        granted_source_keys = set(OpenPluginGrantService.granted_source_keys(space_id))
        if source_key and source_key not in granted_source_keys:
            raise ValueError("开放插件来源未准入: {}".format(source_key))

        catalog_qs = OpenPluginCatalogIndex.objects.filter(
            space_id=space_id,
            status=OpenPluginCatalogIndex.Status.AVAILABLE,
        )
        if source_key:
            catalog_qs = catalog_qs.filter(source_key=source_key)
        else:
            if not granted_source_keys:
                return []
            catalog_qs = catalog_qs.filter(source_key__in=granted_source_keys)

        updated = []
        for item in catalog_qs.only("source_key", "plugin_id"):
            availability = cls.toggle_plugin(
                space_id=space_id,
                source_key=item.source_key,
                plugin_id=item.plugin_id,
                enabled=True,
            )
            updated.append(availability)
        return updated

    @classmethod
    def disable_source_plugins(cls, space_id, source_key):
        SpaceOpenPluginAvailability.objects.filter(space_id=space_id, source_key=source_key).update(enabled=False)

    @classmethod
    def _get_sources(cls, space_id, source_key=None):
        uniform_api_config = SpaceConfig.get_config(space_id=space_id, config_name=UniformApiConfig.name)
        if not uniform_api_config:
            return {}

        config = UniformAPIConfigHandler(uniform_api_config).handle()
        sources = config.api
        if source_key:
            return {
                api_key: api_entry
                for api_key, api_entry in sources.items()
                if cls._effective_source_key(api_key=api_key, api_entry=api_entry) == source_key
            }
        return sources

    @staticmethod
    def _effective_source_key(api_key, api_entry):
        if isinstance(api_entry, dict):
            source_key = api_entry.get("source_key")
        else:
            source_key = getattr(api_entry, "source_key", None)
        return source_key if isinstance(source_key, str) and source_key else api_key

    @classmethod
    def iter_configured_sources(cls):
        queryset = SpaceConfig.objects.filter(name=UniformApiConfig.name).only("space_id", "json_value")
        for space_config in queryset.iterator():
            if not space_config.json_value:
                continue

            config = UniformAPIConfigHandler(space_config.json_value).handle()
            source_keys = {
                cls._effective_source_key(api_key=api_key, api_entry=api_entry)
                for api_key, api_entry in config.api.items()
            }
            for source_key in sorted(source_keys):
                yield space_config.space_id, source_key

    @classmethod
    def _fetch_api_list(cls, space_id, api_entry, username):
        credential = cls._get_apigw_credential(space_id=space_id)
        if not credential:
            raise ValidationError("空间 {} 未配置 API Gateway 凭证".format(space_id))

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(
            app_code=credential.content["bk_app_code"],
            app_secret=credential.content["bk_app_secret"],
            username=username,
        )
        list_result = client.request(
            url=api_entry.meta_apis if hasattr(api_entry, "meta_apis") else api_entry.get("meta_apis"),
            method="GET",
            data={"limit": 200, "offset": 0},
            headers=headers,
            username=username,
            timeout=settings.OPEN_PLUGIN_CATALOG_SYNC_REQUEST_TIMEOUT,
        )
        if not list_result.result:
            raise APIResponseError("请求开放插件目录失败: {}".format(list_result.message))
        if not isinstance(list_result.json_resp, dict):
            raise APIResponseError("请求开放插件目录失败: 响应体不是 JSON 对象")

        response_data = list_result.json_resp.get("data")
        if not isinstance(response_data, dict):
            raise APIResponseError("请求开放插件目录失败: 响应体缺少 data 对象")
        client.validate_response_data(response_data, client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)
        return response_data["apis"]

    @classmethod
    def _refresh_catalog_index(cls, space_id, source_key, api_list):
        current_ids = set()
        for api_item in api_list:
            current_ids.add(api_item["id"])
            OpenPluginCatalogIndex.objects.update_or_create(
                space_id=space_id,
                source_key=source_key,
                plugin_id=api_item["id"],
                defaults={
                    "plugin_code": api_item.get("plugin_code", ""),
                    "plugin_name": api_item.get("name", ""),
                    "plugin_source": api_item.get("plugin_source", ""),
                    "group_name": api_item.get("category", ""),
                    "wrapper_version": api_item.get("wrapper_version", ""),
                    "default_version": api_item.get("default_version", ""),
                    "latest_version": api_item.get("latest_version", ""),
                    "versions": api_item.get("versions", []),
                    "meta_url_template": api_item.get("meta_url_template", api_item.get("meta_url", "")),
                    "description": api_item.get("description", ""),
                    "status": OpenPluginCatalogIndex.Status.AVAILABLE,
                },
            )
            SpaceOpenPluginAvailability.objects.get_or_create(
                space_id=space_id,
                source_key=source_key,
                plugin_id=api_item["id"],
                defaults={"enabled": False},
            )

        OpenPluginCatalogIndex.objects.filter(space_id=space_id, source_key=source_key).exclude(
            plugin_id__in=current_ids
        ).update(status=OpenPluginCatalogIndex.Status.UNAVAILABLE)

    @classmethod
    def _get_apigw_credential(cls, space_id):
        credential_name = SpaceConfig.get_config(space_id=space_id, config_name=ApiGatewayCredentialConfig.name)
        if not credential_name:
            return None
        return Credential.objects.filter(space_id=space_id, name=credential_name).first()
