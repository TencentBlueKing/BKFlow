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

from pipeline.component_framework.models import ComponentModel

from bkflow.bk_plugin.models import BKPlugin
from bkflow.plugin.constants import WRAPPER_CODES
from bkflow.plugin.models import OpenPluginCatalogIndex
from bkflow.plugin_catalog.models import PluginDirectory, PluginType
from bkflow.space.configs import UniformApiConfig, UniformAPIConfigHandler
from bkflow.space.models import SpaceConfig

logger = logging.getLogger(__name__)


class SourceGroupService:
    """
    来源分组只读聚合，不落库，供 06 新插件策略"直通来源"、08 目录批量管理"来源绑定目录"的
    来源选择器使用。

    分组层级固定两级：第一级 = plugin_type（builtin/bk_plugin/api），第二级（仅 api 分组有）
    = 具体来源 source_key。builtin/bk_plugin 分组本身就是最小可选单元（它们没有"来源"细分概念，
    source_key 恒为空），其 id 本身即是 06 策略条件组 `sources` 字段里用的匹配键，
    与 PluginAdmissionStrategyService._match_key 的口径保持一致。
    """

    @classmethod
    def list_groups(cls, space_id):
        groups = [
            cls._builtin_group(),
            cls._bk_plugin_group(),
            cls._api_group(space_id),
        ]
        return groups

    @classmethod
    def _builtin_group(cls):
        return {
            "id": PluginType.BUILTIN,
            "name": "内置插件",
            "plugin_type": PluginType.BUILTIN,
            "whole": True,
            "children": [],
        }

    @classmethod
    def _bk_plugin_group(cls):
        return {
            "id": PluginType.BK_PLUGIN,
            "name": "蓝鲸插件",
            "plugin_type": PluginType.BK_PLUGIN,
            "whole": True,
            "children": [],
        }

    @classmethod
    def _api_group(cls, space_id):
        uniform_api_config = SpaceConfig.get_config(space_id=space_id, config_name=UniformApiConfig.name)
        children = []
        if uniform_api_config:
            try:
                config = UniformAPIConfigHandler(uniform_api_config).handle()
            except Exception:
                logger.exception("跳过无法解析的统一 API 配置: space_id=%s", space_id)
                config = None

            if config is not None:
                used_source_keys = set()
                for api_key, api_entry in config.api.items():
                    source_key = cls._effective_source_key(api_key, api_entry)
                    display_name = getattr(api_entry, "display_name", None) or api_key
                    # 兜底：source_key 在同一空间内本应唯一（UniformApiConfig.validate 已拦截），
                    # 但历史脏数据可能绕过校验。重复时只保留第一个并记日志——两个 id 相同的选项
                    # 会让前端"选了哪个"无法区分，且同步时这两个来源的插件会被合并成一份。
                    if source_key in used_source_keys:
                        logger.warning(
                            "跳过重复 source_key 的 API 来源: space_id=%s, api_key=%s, source_key=%s",
                            space_id,
                            api_key,
                            source_key,
                        )
                        continue
                    used_source_keys.add(source_key)
                    # 自 PluginCatalogSyncService.sync_api 支持全量分页直取（不再按 wrapper_version
                    # 过滤）后，所有 API 来源均可被 SpacePluginCatalogEntry 精细化管理到单个插件，
                    # 所有 API 来源都支持精细化管理到单个插件，因此这里恒为 whole=False。
                    children.append(
                        {
                            "id": source_key,
                            "name": display_name,
                            "whole": False,
                        }
                    )
        return {
            "id": PluginType.API,
            "name": "API 插件",
            "plugin_type": PluginType.API,
            "whole": False,
            "children": children,
        }

    @staticmethod
    def _effective_source_key(api_key, api_entry):
        source_key = getattr(api_entry, "source_key", None)
        return source_key if isinstance(source_key, str) and source_key else api_key

    @staticmethod
    def display_source_id(plugin_type, source_key):
        """对外的「来源」标识：与本服务返回的来源分组 id 同口径。

        库里 `builtin` / `bk_plugin` 的 `source_key` 恒为空串（这两类本身没有来源细分），
        直接对外给空串，前端无法渲染设计稿里的「来源」列、也无法做来源筛选。这里统一成
        「来源匹配键」口径：

        - `builtin`   -> `"builtin"`
        - `bk_plugin` -> `"bk_plugin"`
        - `api`       -> 该来源的 `source_key`（如 `"api_job"`）

        与 `PluginAdmissionStrategyService._match_key` 同口径，也与 `GET
        /api/plugin_catalog/strategy/sources/` 返回的 id 一致——前端拿同一份 id 就能同时用于
        「来源」列展示、来源筛选、以及新插件策略条件组的 `sources` 选择。

        注意：库里存的 `source_key` 不变（保持空串），只改对外表达，否则会破坏
        `unique_together(space_id, plugin_type, source_key, plugin_code)` 与存量数据的一致性。
        """
        if plugin_type == PluginType.API and source_key:
            return source_key
        return plugin_type

    @staticmethod
    def normalize_source_key(plugin_type, source_key):
        """把对外口径的「来源 id」翻译回库里的 `source_key`。

        对外 id 是「来源匹配键」，库里 `builtin` / `bk_plugin` 的 `source_key` 恒为空串，
        所以这两类统一归一成空串；api 的来源 id 就是库里的 `source_key`，原样返回。
        用于入参归一化：前端传 `"builtin"` 或 `""` 都能查到同一条记录。
        """
        if plugin_type in (PluginType.BUILTIN, PluginType.BK_PLUGIN):
            return ""
        return source_key or ""

    @classmethod
    def builtin_display_names(cls):
        """内置插件 code -> 展示名称，供目录管理/插件列表等后续步骤复用，避免重复查询逻辑。"""
        names = {}
        for code, name in (
            ComponentModel.objects.filter(status=True).exclude(code__in=WRAPPER_CODES).values_list("code", "name")
        ):
            names.setdefault(code, name)
        return names

    @classmethod
    def bk_plugin_display_names(cls, space_id):
        return dict(BKPlugin.objects.for_space(space_id).values_list("code", "name"))

    @classmethod
    def source_display_names(cls, space_id):
        """对外「来源 id」-> 来源展示名，供列表页渲染设计稿的「来源」列。

        - builtin   → `builtin`   -> "BKFlow"
        - bk_plugin → `bk_plugin` -> "PaaS"
        - api       → 该来源的 source_key -> 用户在统一 API 配置里起的来源名（display_name）
        """
        names = {
            PluginType.BUILTIN: "BKFlow",
            PluginType.BK_PLUGIN: "PaaS",
        }
        for child in cls._api_group(space_id)["children"]:
            names[child["id"]] = child["name"]
        return names

    @classmethod
    def api_display_names(cls, space_id):
        """
        API 插件 (source_key, plugin_code) -> 展示名称，供 08 目录批量管理等列表场景展示插件名。

        仅覆盖已被 V4 展示缓存（OpenPluginCatalogIndex）收录的插件；V2/V3 协议插件未被该表缓存，
        查不到时由调用方回退展示 plugin_code 本身。
        用 (source_key, plugin_code) 二元组做 key，避免不同来源下插件 id 碰巧同名时互相覆盖。
        """
        return {
            (item.source_key, item.plugin_id): item.plugin_name
            for item in OpenPluginCatalogIndex.objects.filter(space_id=space_id).only(
                "source_key", "plugin_id", "plugin_name"
            )
        }
