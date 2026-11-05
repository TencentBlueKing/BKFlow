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
    def list_groups(cls, space_id, exclude_directory_id=None):
        groups = [
            cls._builtin_group(),
            cls._bk_plugin_group(),
            cls._api_group(space_id),
        ]
        bound_map = cls._bound_directory_map(space_id, exclude_directory_id=exclude_directory_id)

        for group in groups:
            bound = bound_map.get(group["id"])
            if bound:
                group["bound_directory_id"], group["bound_directory_name"] = bound
            for child in group["children"]:
                bound = bound_map.get(child["id"])
                if bound:
                    child["bound_directory_id"], child["bound_directory_name"] = bound
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
                for api_key, api_entry in config.api.items():
                    source_key = cls._effective_source_key(api_key, api_entry)
                    display_name = getattr(api_entry, "display_name", None) or api_key
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

    @classmethod
    def _bound_directory_map(cls, space_id, exclude_directory_id=None):
        """
        反查一级目录的来源绑定，key 为"来源匹配键"（与 _match_key 口径一致），
        value 为 (directory_id, directory_name)。exclude_directory_id 用于编辑自身一级目录时，
        不把自己已绑定的来源算作"已被其他分类绑定"。
        """
        qs = PluginDirectory.objects.filter(space_id=space_id, parent__isnull=True).exclude(bindings=[])
        if exclude_directory_id:
            qs = qs.exclude(id=exclude_directory_id)
        result = {}
        for directory in qs.only("id", "name", "bindings"):
            for match_key in directory.bindings:
                result[match_key] = (directory.id, directory.name)
        return result

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
