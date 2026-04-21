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

from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.space.configs import ApiGatewayCredentialConfig, UniformApiConfig, UniformAPIConfigHandler
from bkflow.space.models import Credential, SpaceConfig


class OpenPluginCatalogService:
    @classmethod
    def sync_space_plugins(cls, space_id, source_key=None, username="admin"):
        synced_sources = []
        for current_source_key, api_entry in cls._get_sources(space_id=space_id, source_key=source_key).items():
            api_list = cls._fetch_api_list(
                space_id=space_id,
                api_entry=api_entry,
                username=username,
            )
            cls._refresh_catalog_index(space_id=space_id, source_key=current_source_key, api_list=api_list)
            synced_sources.append(current_source_key)
        return synced_sources

    @classmethod
    def list_space_plugins(cls, space_id, source_key=None):
        catalog_qs = OpenPluginCatalogIndex.objects.filter(space_id=space_id).order_by("source_key", "plugin_name")
        if source_key:
            catalog_qs = catalog_qs.filter(source_key=source_key)

        availability_qs = SpaceOpenPluginAvailability.objects.filter(space_id=space_id)
        if source_key:
            availability_qs = availability_qs.filter(source_key=source_key)

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
        catalog_qs = OpenPluginCatalogIndex.objects.filter(
            space_id=space_id,
            status=OpenPluginCatalogIndex.Status.AVAILABLE,
        )
        if source_key:
            catalog_qs = catalog_qs.filter(source_key=source_key)

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
            entry = sources.get(source_key)
            return {source_key: entry} if entry else {}
        return sources

    @classmethod
    def _fetch_api_list(cls, space_id, api_entry, username):
        credential = cls._get_apigw_credential(space_id=space_id)
        if not credential:
            return []

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
        )
        return list_result.json_resp.get("data", {}).get("apis", [])

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
