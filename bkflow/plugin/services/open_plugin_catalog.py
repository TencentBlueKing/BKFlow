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

from django.conf import settings

from bkflow.exceptions import APIResponseError, ValidationError
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.plugin.models import (
    OPEN_PLUGIN_WRAPPER_VERSION,
    OpenPluginCatalogIndex,
    SpaceOpenPluginAvailability,
)
from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    UniformApiConfig,
    UniformAPIConfigHandler,
)
from bkflow.space.models import Credential, SpaceConfig

logger = logging.getLogger(__name__)


class OpenPluginCatalogService:
    # 单页请求条数；FETCH_MAX_PAGES 是安全上限（200*50=1万条），防止来源分页协议异常时死循环，
    # 不是业务容量承诺，纯粹是兜底保护。
    FETCH_PAGE_SIZE = 200
    FETCH_MAX_PAGES = 50

    @classmethod
    def is_catalog_initialized(cls, space_id, source_key, plugin_source=None):
        catalog_qs = OpenPluginCatalogIndex.objects.filter(space_id=space_id, source_key=source_key)
        if plugin_source:
            catalog_qs = catalog_qs.filter(plugin_source=plugin_source)
        return catalog_qs.exists()

    @classmethod
    def sync_space_plugins(cls, space_id, source_key=None, username="admin"):
        """
        同步开放插件目录（仅 V4 协议，`_refresh_catalog_index` 内部过滤），
        供画布"缓存优先"展示路径使用，详见 bkflow/pipeline_plugins/query/uniform_api/uniform_api.py。
        返回值契约（`list(来源 key)`）保持不变，被现有测试 `test_sync_space_plugins_aggregates_*`
        直接断言，不要改成返回原始数据，若需要原始数据请用 `fetch_all_source_plugins`。
        """
        source_plugins = cls._collect_source_plugins(space_id=space_id, source_key=source_key, username=username)

        for current_source_key, plugins_by_id in source_plugins.items():
            cls._refresh_catalog_index(
                space_id=space_id,
                source_key=current_source_key,
                api_list=list(plugins_by_id.values()),
            )
        return list(source_plugins.keys())

    @classmethod
    def fetch_all_source_plugins(cls, space_id, source_key=None, username="admin"):
        """
        返回每个已配置来源**当前完整**的插件 id 列表，不按 `wrapper_version` 过滤（V2/V3/V4 一视同仁）。

        供 `bkflow.plugin_catalog.services.sync_service.PluginCatalogSyncService.sync_api` 直接消费，
        把结果喂给统一插件目录（`SpacePluginCatalogEntry`），不经过只服务于 V4 展示缓存的
        `OpenPluginCatalogIndex` 中间表。

        :return: {source_key: [plugin_id, ...]}
        """
        source_plugins = cls._collect_source_plugins(space_id=space_id, source_key=source_key, username=username)
        return {src: list(plugins_by_id.keys()) for src, plugins_by_id in source_plugins.items()}

    @classmethod
    def _collect_source_plugins(cls, space_id, source_key=None, username="admin"):
        """实际发请求拉取每个已配置来源的完整插件清单，按"执行来源"聚合去重。

        `sync_space_plugins`（只服务 V4 缓存）与 `fetch_all_source_plugins`（服务统一插件目录，
        全版本不过滤）共用这一个方法，避免同一个来源在一次同步周期里被重复请求两次。
        """
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
        return source_plugins

    @classmethod
    def list_space_plugins(cls, space_id, source_key=None):
        catalog_qs = OpenPluginCatalogIndex.objects.filter(space_id=space_id).order_by("source_key", "plugin_name")
        availability_qs = SpaceOpenPluginAvailability.objects.filter(space_id=space_id)
        if source_key:
            catalog_qs = catalog_qs.filter(source_key=source_key)
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
                "group_display_name": item.group_display_name,
                "wrapper_version": item.wrapper_version,
                "default_version": item.default_version,
                "latest_version": item.latest_version,
                "versions": item.versions,
                "meta_url_template": item.meta_url_template,
                "description": item.description,
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

            try:
                config = UniformAPIConfigHandler(space_config.json_value).handle()
            except Exception:
                logger.exception("跳过无法解析的历史统一 API 配置: space_id=%s", space_config.space_id)
                continue
            source_keys = {
                cls._effective_source_key(api_key=api_key, api_entry=api_entry)
                for api_key, api_entry in config.api.items()
            }
            for source_key in sorted(source_keys):
                yield space_config.space_id, source_key

    @classmethod
    def _fetch_api_list(cls, space_id, api_entry, username):
        """
        请求某个来源的完整插件清单，内部做真正的分页循环（此前只请求第一页、最多 200 条，
        超过 200 条的来源会被误判为"后面的都已下架"，这里一并修复）。

        终止分页的依据是"本页返回条数 < 请求的 limit"（标准分页语义，不依赖来源是否准确填写
        `total` 字段）；额外加 FETCH_MAX_PAGES 安全上限兜底，防止来源分页协议异常时死循环。
        """
        credential = cls._get_apigw_credential(space_id=space_id)
        if not credential:
            raise ValidationError("空间 {} 未配置 API Gateway 凭证".format(space_id))

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(
            app_code=credential.content["bk_app_code"],
            app_secret=credential.content["bk_app_secret"],
            username=username,
            headers=api_entry.get("headers") or {},
        )
        url = api_entry.meta_apis if hasattr(api_entry, "meta_apis") else api_entry.get("meta_apis")

        page_size = cls.FETCH_PAGE_SIZE
        all_apis = []
        offset = 0
        for _ in range(cls.FETCH_MAX_PAGES):
            list_result = client.request(
                url=url,
                method="GET",
                data={"limit": page_size, "offset": offset},
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

            page_apis = response_data["apis"]
            all_apis.extend(page_apis)

            if len(page_apis) < page_size:
                # 返回条数不足一页，说明已经是最后一页
                break
            offset += len(page_apis)
        else:
            logger.warning(
                "开放插件目录分页达到安全上限(%s页)，可能未拉取完整结果: space_id=%s, url=%s, fetched=%s",
                cls.FETCH_MAX_PAGES,
                space_id,
                url,
                len(all_apis),
            )

        return all_apis

    @classmethod
    def _refresh_catalog_index(cls, space_id, source_key, api_list):
        current_ids = set()
        for api_item in api_list:
            if api_item.get("wrapper_version") != OPEN_PLUGIN_WRAPPER_VERSION:
                continue
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
                    "group_display_name": api_item.get("category_name") or api_item.get("category", ""),
                    "wrapper_version": api_item.get("wrapper_version", ""),
                    "default_version": api_item.get("default_version", ""),
                    "latest_version": api_item.get("latest_version", ""),
                    "versions": api_item.get("versions", []),
                    "meta_url_template": api_item.get("meta_url_template", api_item.get("meta_url", "")),
                    "description": api_item.get("description", ""),
                    "status": OpenPluginCatalogIndex.Status.AVAILABLE,
                },
            )
            # 只对首次入目录的插件生效，管理员手动关闭过的记录不会被同步覆盖。
            SpaceOpenPluginAvailability.objects.get_or_create(
                space_id=space_id,
                source_key=source_key,
                plugin_id=api_item["id"],
                defaults={"enabled": True},
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
