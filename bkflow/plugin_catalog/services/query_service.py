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

from django.db.models import Count, Q

from bkflow.plugin_catalog.models import (
    PluginCatalogStatus,
    PluginDirectory,
    PluginType,
    SpacePluginCatalogEntry,
    TemplatePluginReference,
)
from bkflow.plugin_catalog.services.migration_service import PluginCatalogMigrationService
from bkflow.plugin_catalog.services.source_group_service import SourceGroupService
from bkflow.plugin_catalog.services.strategy_service import PluginAdmissionStrategyService

logger = logging.getLogger(__name__)

MAX_RECOMMEND = 10


class PluginCatalogQueryService:
    """
    插件列表页的公共查询/聚合逻辑：筛选、排序、分页、状态计数与引用统计。

    插件展示名来自外部只读来源（ComponentModel/BKPlugin/OpenPluginCatalogIndex），不落在
    SpacePluginCatalogEntry 表内，因此"按名称搜索/排序"无法直接转成 SQL WHERE/ORDER BY。
    采用"结构化条件先过滤出候选集 → 批量解析展示名/引用计数 → 内存过滤/排序/分页"的方式，
    不引入额外的名称缓存表；空间插件规模可控（通常几十到几百条），内存处理足够。
    """

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 200

    # ------------------------------------------------------- 展示名 / 引用计数 ----

    @classmethod
    def _name_resolvers(cls, space_id):
        return {
            PluginType.BUILTIN: SourceGroupService.builtin_display_names(),
            PluginType.BK_PLUGIN: SourceGroupService.bk_plugin_display_names(space_id),
            PluginType.API: SourceGroupService.api_display_names(space_id),
        }

    @classmethod
    def _resolve_name(cls, entry, name_maps):
        if entry.plugin_type == PluginType.API:
            return name_maps[PluginType.API].get((entry.source_key, entry.plugin_code), entry.plugin_code)
        return name_maps[entry.plugin_type].get(entry.plugin_code, entry.plugin_code)

    @classmethod
    def bulk_get_ref_counts(cls, space_id, identities=None):
        """
        批量统计插件身份被流程引用的次数，供 07 详情页与 10 画布选择器共用同一口径，
        避免两处各算一套。

        放在本类而不是 reference_service，是为了避免
        reference_service -> query_service（复用 serialize_entries）与
        query_service -> reference_service（复用本方法）的模块级循环依赖。

        :param identities: 可选，指定要统计的 {(plugin_type, source_key, plugin_code)} 集合；
                           为 None 时统计该空间下全部插件身份。
        :return: {(plugin_type, source_key, plugin_code): {"ref_count": N, "node_count": N}}
                 ref_count 按 template_id 去重（引用流程数），node_count 按行数（引用节点数）。
                 resolved=False 的"无法识别 API 节点"不计入引用计数。
        """
        queryset = TemplatePluginReference.objects.filter(space_id=space_id, resolved=True)
        if identities is not None:
            identities = set(identities)
            if not identities:
                return {}
            # 先用三个 IN 条件粗筛（走索引），再用完整三元组在 Python 侧精确匹配，
            # 避免用 Q 拼三维 OR 导致无法走索引。
            queryset = queryset.filter(
                plugin_type__in={item[0] for item in identities},
                source_key__in={item[1] for item in identities},
                plugin_code__in={item[2] for item in identities},
            )

        stats = {}
        template_sets = {}
        rows = queryset.values("plugin_type", "source_key", "plugin_code", "template_id")
        for row in rows:
            key = (row["plugin_type"], row["source_key"], row["plugin_code"])
            if identities is not None and key not in identities:
                continue
            stats.setdefault(key, {"ref_count": 0, "node_count": 0})
            stats[key]["node_count"] += 1
            template_sets.setdefault(key, set()).add(row["template_id"])
        for key, templates in template_sets.items():
            stats[key]["ref_count"] = len(templates)
        return stats

    @classmethod
    def _reference_stats(cls, space_id):
        return cls.bulk_get_ref_counts(space_id)

    @classmethod
    def serialize_entries(cls, space_id, entries):
        name_maps = cls._name_resolvers(space_id)
        ref_stats = cls._reference_stats(space_id)
        result = []
        for entry in entries:
            key = (entry.plugin_type, entry.source_key, entry.plugin_code)
            stat = ref_stats.get(key, {"ref_count": 0, "node_count": 0})
            result.append(
                {
                    "id": entry.id,
                    "plugin_type": entry.plugin_type,
                    "source_key": entry.source_key,
                    "plugin_code": entry.plugin_code,
                    "plugin_name": cls._resolve_name(entry, name_maps),
                    "directory_id": entry.directory_id,
                    "status": entry.status,
                    "recommended": entry.recommended,
                    "recommend_order": entry.recommend_order,
                    "ref_count": stat["ref_count"],
                    "node_count": stat["node_count"],
                    "offline_reason": entry.offline_reason,
                    "invalid_reason": entry.invalid_reason,
                    "found_time": entry.found_time,
                    "disable_config": {k: v for k, v in (entry.disable_config or {}).items() if k != "_meta"},
                    "updated_by": entry.updated_by,
                    "update_at": entry.update_at,
                }
            )
        return result

    # ------------------------------------------------------------------- 筛选 ----

    @classmethod
    def _directory_scope_ids(cls, space_id, directory_id):
        """具体目录 id -> [自身 id] + 其二级子目录 id 列表；传入二级目录则只返回自身。"""
        try:
            pk = int(directory_id)
        except (TypeError, ValueError):
            return None
        child_ids = list(
            PluginDirectory.objects.filter(space_id=space_id, parent_id=pk).values_list("id", flat=True)
        )
        return [pk] + child_ids

    @classmethod
    def _apply_directory_filter(cls, queryset, space_id, directory_id):
        if not directory_id or directory_id == "all":
            return queryset
        if directory_id == "recommend":
            return queryset.filter(recommended=True)
        if directory_id == "uncategorized":
            return queryset.filter(directory__isnull=True)
        scope_ids = cls._directory_scope_ids(space_id, directory_id)
        return queryset.filter(directory_id__in=scope_ids) if scope_ids else queryset.none()

    @classmethod
    def _base_queryset(cls, space_id, directory_id=None, status=None, plugin_type=None, source_key=None):
        queryset = SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False)
        queryset = cls._apply_directory_filter(queryset, space_id, directory_id)

        status_list = status if isinstance(status, (list, tuple)) else ([status] if status else None)
        if not status_list or status_list == ["all"]:
            queryset = queryset.exclude(status=PluginCatalogStatus.INVALID)
        else:
            queryset = queryset.filter(status__in=status_list)

        if plugin_type:
            queryset = queryset.filter(plugin_type__in=plugin_type)
        if source_key:
            queryset = queryset.filter(source_key__in=source_key)
        return queryset

    @classmethod
    def list_entries(
        cls,
        space_id,
        directory_id=None,
        status=None,
        plugin_type=None,
        source_key=None,
        keyword=None,
        ordering="-update_at",
        page=1,
        page_size=None,
    ):
        queryset = cls._base_queryset(
            space_id, directory_id=directory_id, status=status, plugin_type=plugin_type, source_key=source_key
        )
        serialized = cls.serialize_entries(space_id, list(queryset))

        if keyword:
            keywords = keyword if isinstance(keyword, (list, tuple)) else [keyword]
            lowered = [kw.lower() for kw in keywords if kw]
            if lowered:
                serialized = [
                    item
                    for item in serialized
                    if any(kw in (item["plugin_name"] or "").lower() for kw in lowered)
                    or any(kw in (item["updated_by"] or "").lower() for kw in lowered)
                ]

        reverse = ordering.startswith("-") if ordering else False
        order_field = (ordering or "-update_at").lstrip("-")
        if order_field == "name":
            serialized.sort(key=lambda item: item["plugin_name"] or "", reverse=reverse)
        elif order_field == "ref_count":
            serialized.sort(key=lambda item: item["ref_count"], reverse=reverse)
        else:
            serialized.sort(key=lambda item: item["update_at"], reverse=reverse)

        total = len(serialized)
        page = page if page and page > 0 else 1
        page_size = min(page_size, cls.MAX_PAGE_SIZE) if page_size else cls.DEFAULT_PAGE_SIZE
        start = (page - 1) * page_size
        return {
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": serialized[start : start + page_size],
        }

    @classmethod
    def get_status_counts(cls, space_id, directory_id=None, plugin_type=None, source_key=None, keyword=None):
        """
        除 status 外其余条件过滤后，按六态分别计数（这里统计全部六态，含 invalid，供前端把
        invalid 单独映射到"已失效" Tab；"全部"Tab 的 all 计数口径=六态求和-invalid，由本方法
        的调用方/前端自行汇总，不在这里预先剔除）。
        """
        queryset = SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False)
        queryset = cls._apply_directory_filter(queryset, space_id, directory_id)
        if plugin_type:
            queryset = queryset.filter(plugin_type__in=plugin_type)
        if source_key:
            queryset = queryset.filter(source_key__in=source_key)
        if keyword:
            # 关键字命中插件名称无法下推 SQL（名称来自外部只读来源），Tab 计数场景退化为只按
            # updated_by 过滤；计数本身是粗粒度展示，精确结果以 list_entries 的内存过滤为准。
            keywords = keyword if isinstance(keyword, (list, tuple)) else [keyword]
            condition = Q()
            for kw in keywords:
                condition |= Q(updated_by__icontains=kw)
            queryset = queryset.filter(condition)

        counts = {status: 0 for status, _ in PluginCatalogStatus.CHOICES}
        for row in queryset.values("status").annotate(total=Count("id")):
            counts[row["status"]] = row["total"]
        counts["all"] = sum(v for status, v in counts.items() if status != PluginCatalogStatus.INVALID)
        counts["unused"] = sum(counts[status] for status in PluginCatalogStatus.UNUSED_GROUP)
        return counts

    @classmethod
    def get_summary(cls, space_id):
        directories = PluginDirectory.objects.filter(space_id=space_id).order_by("parent_id", "order", "id")
        nodes, top_level = {}, []
        for directory in directories:
            node = {"id": directory.id, "name": directory.name, "order": directory.order, "children": []}
            nodes[directory.id] = node
            if directory.parent_id is None:
                top_level.append(node)
        for directory in directories:
            if directory.parent_id is not None and directory.parent_id in nodes:
                nodes[directory.parent_id]["children"].append(nodes[directory.id])

        status_counts = cls.get_status_counts(space_id)
        strategy = PluginAdmissionStrategyService.get_strategy(space_id) or {}
        recommend_count = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id, recommended=True, is_deleted=False
        ).count()
        unresolved_node_count = TemplatePluginReference.objects.filter(space_id=space_id, resolved=False).count()

        return {
            "directory_tree": top_level,
            "status_counts": status_counts,
            "strategy_summary": {"mode": strategy.get("mode", "review")},
            "pending_strategy_changes": status_counts.get(PluginCatalogStatus.REVIEW, 0),
            "recommend_count": recommend_count,
            "recommend_max": MAX_RECOMMEND,
            "unresolved_node_count": unresolved_node_count,
            # 本空间是否已完成插件目录初始化迁移。未就绪时上面各计数恒为 0，
            # 前端据此提示"尚未启用插件目录"，而不是把 0 当成"没有插件"。
            "ready": PluginCatalogMigrationService.is_ready(space_id),
        }
