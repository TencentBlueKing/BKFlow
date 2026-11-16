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
from django.utils.timezone import is_naive, localtime

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
from bkflow.utils.strings import pinyin_sort_key

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
        ref_stats = cls._reference_stats(space_id)
        # 设计稿列表页的「类型 / 来源 / 目录」三列直接展示名称，这里一并下发，
        # 免得前端再拿 id 反查一遍（反查同样要查库，且各页面口径容易不一致）
        type_names = dict(PluginType.CHOICES)
        source_names = SourceGroupService.source_display_names(space_id)
        directory_paths = cls.directory_paths(space_id)
        result = []
        for entry in entries:
            key = (entry.plugin_type, entry.source_key, entry.plugin_code)
            stat = ref_stats.get(key, {"ref_count": 0, "node_count": 0})
            source_id = cls._display_source_key(entry)
            result.append(
                {
                    "id": entry.id,
                    "plugin_type": entry.plugin_type,
                    "plugin_type_name": type_names.get(entry.plugin_type, entry.plugin_type),
                    "source_key": cls._display_source_key(entry),
                    "source_name": source_names.get(source_id, ""),
                    "plugin_code": entry.plugin_code,
                    # 插件名 / 描述取自目录条目表（来源同步写入的副本），不再实时查外部只读表
                    "plugin_name": entry.plugin_name or entry.plugin_code,
                    "plugin_desc": entry.plugin_desc or "",
                    "directory_id": entry.directory_id,
                    "directory_name": " / ".join(directory_paths.get(entry.directory_id, [])),
                    "status": entry.status,
                    "recommended": entry.recommended,
                    # 建议替换插件：只给 id，前端按需回查或直接跳转到该插件
                    "replace_plugin_id": entry.replace_plugin_id,
                    "ref_count": stat["ref_count"],
                    "node_count": stat["node_count"],
                    "found_time": cls._format_time(entry.found_time),
                    "disable_reason": entry.disable_reason,
                    "updated_by": entry.updated_by,
                    "update_at": cls._format_time(entry.update_at),
                }
            )
        return result

    @staticmethod
    def directory_paths(space_id):
        """目录 id -> 目录路径数组（最多两级，如 `["主机与作业", "作业执行"]`）。

        放在本类而不是 picker_service，是为了让画布选择器（接口 A5）复用同一份实现，
        避免两个接口对「目录路径」的口径不一致。
        """
        directories = list(PluginDirectory.objects.filter(space_id=space_id).only("id", "parent_id", "name"))
        name_map = {directory.id: directory.name for directory in directories}
        paths = {}
        for directory in directories:
            if directory.parent_id and directory.parent_id in name_map:
                paths[directory.id] = [name_map[directory.parent_id], directory.name]
            else:
                paths[directory.id] = [directory.name]
        return paths

    @staticmethod
    def _format_time(dt):
        """时间统一格式化为本地时区的 ``YYYY-MM-DD HH:MM:SS`` 字符串。

        与项目既有做法一致（见 `bkflow/bk_plugin/models.py` 的 `status_update_time`）：
        直接返回 datetime 对象会被 DRF 序列化成 ISO-8601 的 UTC 时间
        （如 ``2026-11-11T02:31:32.549919Z``），前端直接渲染既不是本地时间、
        也不是约定的字符串格式。空值统一给空串，避免前端判空出错。
        """
        if not dt:
            return ""
        if is_naive(dt):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return localtime(dt).strftime("%Y-%m-%d %H:%M:%S")

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

    @staticmethod
    def _display_source_key(entry):
        """对外的「来源」标识，口径见 `SourceGroupService.display_source_id`。"""
        return SourceGroupService.display_source_id(entry.plugin_type, entry.source_key)

    @staticmethod
    def _apply_keyword_filter(queryset, keyword):
        """按关键词过滤，**下推 SQL**（插件名 / 描述 / 最近修改人，多关键词 OR）。

        这三个字段都落在目录条目表里（插件名与描述由来源同步写入），所以可以直接
        `icontains`，不用把全量条目捞到内存再筛——列表接口与 Tab 计数接口共用本方法，
        两边口径完全一致。

        > 插件的「类型 / 来源 / 目录」按中文名搜索暂未纳入：类型/来源的展示名要额外映射，
        > 目录名要 join 目录表，与前三者的匹配成本差一个量级，需要时再单独补。
        """
        if not keyword:
            return queryset
        keywords = keyword if isinstance(keyword, (list, tuple)) else [keyword]
        condition = Q()
        for kw in keywords:
            if not kw:
                continue
            condition |= (
                Q(plugin_name__icontains=kw)
                | Q(plugin_desc__icontains=kw)
                | Q(updated_by__icontains=kw)
            )
        return queryset.filter(condition) if condition else queryset

    @classmethod
    def _apply_source_filter(cls, queryset, source_key):
        """按对外的「来源 id」筛选（与 `_display_source_key` 同一口径）。

        对外 id 是「来源匹配键」，而库里的 `source_key` 对 builtin / bk_plugin 恒为空串，
        所以要把 `builtin` / `bk_plugin` 翻译成「plugin_type 匹配 + source_key 为空」，
        其余（api 的具体来源）才按 `source_key` 精确匹配。
        """
        if not source_key:
            return queryset

        keys = list(source_key) if isinstance(source_key, (list, tuple)) else [source_key]
        type_keys = [key for key in keys if key in (PluginType.BUILTIN, PluginType.BK_PLUGIN)]
        exact_keys = [key for key in keys if key not in (PluginType.BUILTIN, PluginType.BK_PLUGIN)]

        condition = Q()
        if type_keys:
            condition |= Q(plugin_type__in=type_keys, source_key="")
        if exact_keys:
            condition |= Q(source_key__in=exact_keys)
        if not condition:
            return queryset
        return queryset.filter(condition)

    @classmethod
    def _base_queryset(cls, space_id, directory_id=None, status=None, plugin_type=None, source_key=None):
        queryset = SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False)
        queryset = cls._apply_directory_filter(queryset, space_id, directory_id)

        # status 由序列化器定死为 list：重复传参得到多值列表；不传（空列表）或传 all 表示全部
        status_list = list(status or [])
        if status_list and "all" not in status_list:
            queryset = queryset.filter(status__in=status_list)

        if plugin_type:
            queryset = queryset.filter(plugin_type__in=plugin_type)
        queryset = cls._apply_source_filter(queryset, source_key)
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
        # 关键词过滤下推 SQL：插件名 / 描述 / 最近修改人都落在目录条目表里，
        # 可以直接用 icontains 过滤，不用把全量条目捞到内存再筛。
        queryset = cls._apply_keyword_filter(queryset, keyword)

        serialized = cls.serialize_entries(space_id, list(queryset))

        reverse = ordering.startswith("-") if ordering else False
        order_field = (ordering or "-update_at").lstrip("-")
        if order_field == "name":
            # 中文按拼音排（设计稿「中文名称 A-Z」），不是 Unicode 码位序
            serialized.sort(key=lambda item: pinyin_sort_key(item["plugin_name"]), reverse=reverse)
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
        除 status 外其余条件过滤后，按四态分别计数（pending_review / enable / disabled / expired）。

        额外返回两个聚合值：
        - `all`：四态求和
        - `not_enable`：`disabled + expired`，对应前端的「不启用」Tab
        """
        queryset = SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False)
        queryset = cls._apply_directory_filter(queryset, space_id, directory_id)
        if plugin_type:
            queryset = queryset.filter(plugin_type__in=plugin_type)
        queryset = cls._apply_source_filter(queryset, source_key)
        # 与 list_entries 用同一个关键词过滤器 → Tab 计数与列表结果口径一致
        queryset = cls._apply_keyword_filter(queryset, keyword)

        counts = {status: 0 for status, _ in PluginCatalogStatus.CHOICES}
        for row in queryset.values("status").annotate(total=Count("id")):
            counts[row["status"]] = row["total"]
        counts["all"] = sum(counts[status] for status, _ in PluginCatalogStatus.CHOICES)
        # 「不启用」聚合分组：对外是一个 Tab（已停用 + 已失效）
        counts["not_enable"] = sum(counts[status] for status in PluginCatalogStatus.NOT_ENABLE_GROUP)
        return counts

    @classmethod
    def get_summary(cls, space_id):
        """
        插件目录侧边栏汇总：目录树（每个节点带插件数量）+ 三个虚拟节点的计数。

        计数口径与列表页默认过滤保持一致（排除"已失效"条目），保证侧边栏数字与
        点进去看到的条数对得上；一级目录的 count 含其二级子目录。
        """
        tree = cls.get_directory_tree(space_id)

        strategy = PluginAdmissionStrategyService.get_strategy(space_id) or {}

        return {
            "directory_tree": tree["tree"],
            # 虚拟节点计数：「全部插件」/「未分类插件」；「空间推荐」用 recommend_count
            "total_count": tree["total_count"],
            "uncategorized_count": tree["uncategorized_count"],
            "recommend_count": tree["recommend_count"],
            "recommend_max": MAX_RECOMMEND,
            "strategy_summary": {"mode": strategy.get("mode", "review")},
            "ready": PluginCatalogMigrationService.is_ready(space_id),
        }

    @classmethod
    def get_directory_tree(cls, space_id, status=None):
        """目录树 + 各目录插件数 + 三个虚拟节点计数。

        `status` 给定时**只统计该状态**的条目（画布「选择插件」面板传 `enable`，
        让左侧目录计数与右侧列表总数口径一致）；不给则统计全部条目。

        一级目录的 count = 自身 + 其二级子目录；二级目录 = 直接归属该目录的条目数。
        """
        base = SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False)
        if status:
            base = base.filter(status=status)

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

        directory_counts = cls._get_directory_plugin_counts(space_id, status=status)
        for directory_id, node in nodes.items():
            node["count"] = directory_counts.get(directory_id, 0)

        return {
            "tree": top_level,
            "total_count": base.count(),
            "uncategorized_count": base.filter(directory__isnull=True).count(),
            "recommend_count": base.filter(recommended=True).count(),
        }

    @classmethod
    def _get_directory_plugin_counts(cls, space_id, status=None):
        """各目录的插件数量。

        二级目录 = 直接归属该目录的条目数；一级目录 = 自身 + 其二级子目录的条目数。
        `status` 给定时只统计该状态的条目（画布选择面板用 enable 口径）。
        """
        queryset = SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False)
        if status:
            queryset = queryset.filter(status=status)
        rows = queryset.exclude(directory__isnull=True).values("directory_id").annotate(total=Count("id"))
        counts = {row["directory_id"]: row["total"] for row in rows}

        # 目录最多两级：一级目录的 count 需叠加其二级子目录
        child_ids = {}
        for parent_id, child_id in PluginDirectory.objects.filter(space_id=space_id).values_list("parent_id", "id"):
            if parent_id is not None:
                child_ids.setdefault(parent_id, []).append(child_id)
        for parent_id, children in child_ids.items():
            counts[parent_id] = counts.get(parent_id, 0) + sum(counts.get(cid, 0) for cid in children)
        return counts
