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

from bkflow.bk_plugin.models import BKPluginAuthorization
from bkflow.plugin_catalog.models import PluginCatalogStatus, PluginDirectory, PluginType, SpacePluginCatalogEntry
from bkflow.plugin_catalog.services.query_service import PluginCatalogQueryService
from bkflow.utils.strings import pinyin_sort_key

logger = logging.getLogger(__name__)


class PluginPickerService:
    """
    画布统一选择列表：供流程画布「选择插件」面板使用，只返回可用(visible)的插件。

    核心约束：可见性判定与管理侧列表**完全一致**（只取 status=visible），
    避免"管理页隐藏了但画布还能选到"的不一致 bug。

    两处刻意不写成两套平行实现：管理侧与画布侧都基于同一张 `SpacePluginCatalogEntry` 表，
    状态枚举只有 `PluginCatalogStatus` 一处定义，区别仅在状态过滤条件——
    `PluginCatalogQueryService.list_entries`（管理侧，看全部状态）与本类（画布侧，只看 visible）。
    """

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 200

    ORDERING_CHOICES = ("recommend", "-publish_time", "publish_time", "name", "-usage_count", "usage_count")

    @classmethod
    def list_pickable_plugins(
        cls,
        space_id,
        directory_id="all",
        plugin_type="all",
        keyword=None,
        ordering="recommend",
        page=1,
        page_size=None,
    ):
        entries = cls._list_visible_entries(space_id, directory_id=directory_id, plugin_type=plugin_type)

        directory_paths = cls._load_directory_paths(space_id)
        ref_stats = PluginCatalogQueryService.bulk_get_ref_counts(space_id)

        results = []
        for entry in entries:
            # 插件名 / 描述取自目录条目表（来源同步写入的副本），不再实时查外部只读表
            name = entry.plugin_name or entry.plugin_code
            desc = entry.plugin_desc or ""
            if keyword:
                kw = keyword.lower()
                if kw not in (name or "").lower() and kw not in (desc or "").lower():
                    continue
            stat = ref_stats.get((entry.plugin_type, entry.source_key, entry.plugin_code), {})
            results.append(
                {
                    "plugin_type": entry.plugin_type,
                    "source_key": entry.source_key,
                    "plugin_code": entry.plugin_code,
                    "plugin_name": name,
                    "plugin_desc": desc,
                    "recommended": entry.recommended,
                    "directory_path": directory_paths.get(entry.directory_id, []),
                    "usage_count": stat.get("ref_count", 0),
                    # 目录条目没有独立的"发布时间"字段，这里用最近一次来源同步时间近似，
                    # 仅用于排序，不对外返回。
                    "publish_time": entry.last_synced_at,
                    # 推荐项内部按 id 升序（即"设为推荐的先后顺序"，与接口 3 空间推荐列表一致），
                    # 仅用于排序，不对外返回。
                    "_entry_id": entry.id,
                }
            )

        cls._sort_results(results, ordering)

        total = len(results)
        page = page if page and page > 0 else 1
        page_size = min(page_size, cls.MAX_PAGE_SIZE) if page_size else cls.DEFAULT_PAGE_SIZE
        start = (page - 1) * page_size
        return {
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": results[start : start + page_size],
            # 左侧目录树 + 计数：口径与右侧列表一致（只算 enable），
            # 避免前端再调接口 1.1 拿到「含已失效」的全量计数，导致两处数字对不上。
            "directories": PluginCatalogQueryService.get_directory_tree(
                space_id, status=PluginCatalogStatus.ENABLE
            ),
        }

    # ------------------------------------------------------------------ 数据装配 ----

    @classmethod
    def _list_visible_entries(cls, space_id, directory_id="all", plugin_type="all"):
        queryset = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id, status=PluginCatalogStatus.ENABLE, is_deleted=False
        )
        queryset = cls._apply_directory_filter(queryset, space_id, directory_id)
        if plugin_type and plugin_type != "all":
            queryset = queryset.filter(plugin_type=plugin_type)
        entries = list(queryset)

        # 蓝鲸插件除目录 visible 外，还需与平台侧授权白名单取交集
        # （Authorization 是平台侧控制，目录 status 是空间管理员的决定，两者语义不同都要满足）
        if any(entry.plugin_type == PluginType.BK_PLUGIN for entry in entries):
            authorized_codes = set(BKPluginAuthorization.objects.get_codes_by_space_id(space_id))
            entries = [
                entry
                for entry in entries
                if entry.plugin_type != PluginType.BK_PLUGIN or entry.plugin_code in authorized_codes
            ]
        return entries

    @staticmethod
    def _apply_directory_filter(queryset, space_id, directory_id):
        if not directory_id or directory_id == "all":
            return queryset
        if directory_id == "recommend":
            return queryset.filter(recommended=True)
        if directory_id == "uncategorized":
            return queryset.filter(directory__isnull=True)
        try:
            pk = int(directory_id)
        except (TypeError, ValueError):
            return queryset
        child_ids = list(
            PluginDirectory.objects.filter(space_id=space_id, parent_id=pk).values_list("id", flat=True)
        )
        return queryset.filter(directory_id__in=[pk] + child_ids)

    @staticmethod
    def _load_directory_paths(space_id):
        """目录最多两级，直接拼父子 name；未分类返回空数组。

        与列表页（接口 2）共用同一份实现，保证两个接口的目录路径口径一致。
        """
        return PluginCatalogQueryService.directory_paths(space_id)

    @staticmethod
    def _sort_results(results, ordering):
        ordering = ordering or "recommend"
        if ordering == "name":
            # 中文按拼音排（设计稿「中文名称 ↑ A-Z」），不是 Unicode 码位序
            results.sort(key=lambda item: pinyin_sort_key(item["name"]))
        elif ordering in ("-usage_count", "usage_count"):
            results.sort(key=lambda item: item["usage_count"], reverse=ordering.startswith("-"))
        elif ordering in ("-publish_time", "publish_time"):
            # 目录条目没有独立的"发布时间"字段，用最近一次来源同步时间近似
            results.sort(key=lambda item: item.get("publish_time") or "", reverse=ordering.startswith("-"))
        else:
            # 默认：推荐项整体在前；推荐项内部按 id 升序（设为推荐的先后顺序，与接口 3 一致），
            # 非推荐项内部按最近同步时间倒序。
            # 两次 sort 是稳定排序——后一次是主键（是否推荐 + id），前一次的时间序在非推荐分组内保留。
            results.sort(key=lambda item: item.get("publish_time") or "", reverse=True)
            results.sort(key=lambda item: (0 if item["recommended"] else 1, item["_entry_id"] if item["recommended"] else 0))
        # publish_time / _entry_id 只用于排序，不出现在接口响应里
        for item in results:
            item.pop("publish_time", None)
            item.pop("_entry_id", None)
