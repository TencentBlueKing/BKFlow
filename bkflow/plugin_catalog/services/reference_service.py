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

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from bkflow.exceptions import NotFoundError
from bkflow.plugin_catalog.models import (
    SpacePluginCatalogEntry,
    TemplatePluginReference,
    TemplatePluginReferenceRole,
)
from bkflow.plugin_catalog.services.guard_service import PluginCatalogGuardService
from bkflow.plugin_catalog.services.query_service import PluginCatalogQueryService
from bkflow.template.models import Template, TemplateSnapshot

logger = logging.getLogger(__name__)


class PluginReferenceService:
    """
    插件详情（基本信息 + 当前引用）：聚合某插件被哪些流程引用、引用了多少节点。

    `TemplatePluginReference` 不冗余存流程名/维护人，查询时 join 一次 `Template` 表，
    避免模板改名/改维护人后引用列表展示过期数据。
    """

    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 200

    @classmethod
    def rebuild_template_references(cls, space_id, template_id, role, pipeline_tree):
        """
        全量重算某个流程某个版本角色（published/draft）下的插件引用记录（先删后插）。

        在流程保存/发布/回滚的同一事务内调用，保证「流程保存成功但引用没更新」的不一致不会发生。

        :param space_id: 空间 ID
        :param template_id: 流程模板 ID
        :param role: TemplatePluginReferenceRole.PUBLISHED / DRAFT
        :param pipeline_tree: 该角色对应的流程树
        :return: 本次写入的引用记录条数
        """
        identities = PluginCatalogGuardService.extract_node_plugin_identities(pipeline_tree)
        rows = []
        for node_id, identity in identities.items():
            resolved = identity.get("resolved", True)
            rows.append(
                TemplatePluginReference(
                    space_id=space_id,
                    template_id=template_id,
                    role=role,
                    plugin_type=identity["plugin_type"],
                    source_key=identity["source_key"],
                    plugin_code=identity["plugin_code"],
                    plugin_version=identity.get("plugin_version", ""),
                    node_id=node_id,
                    node_name=identity["node_name"],
                    resolved=resolved,
                    unresolved_reason="" if resolved else "无法解析 API 插件身份",
                )
            )

        with transaction.atomic():
            TemplatePluginReference.objects.filter(
                space_id=space_id, template_id=template_id, role=role
            ).delete()
            if rows:
                TemplatePluginReference.objects.bulk_create(rows)
        return len(rows)

    @classmethod
    def clear_template_references(cls, space_id, template_ids):
        """流程被删除时清理其全部（published/draft）引用记录。"""
        template_ids = list(template_ids or [])
        if not template_ids:
            return 0
        deleted, _ = TemplatePluginReference.objects.filter(
            space_id=space_id, template_id__in=template_ids
        ).delete()
        return deleted

    @classmethod
    def get_plugin_detail(cls, space_id, entry_id):
        entry = cls._get_entry_or_404(space_id, entry_id)
        refs, items = cls._build_reference_items(space_id, entry)
        plugin = PluginCatalogQueryService.serialize_entries(space_id, [entry])[0]
        return {
            "plugin": plugin,
            "refs": refs,
            "references": items[: cls.DEFAULT_PAGE_SIZE],
        }

    @classmethod
    def list_references(cls, space_id, entry_id, scope="all", keyword=None, page=1, page_size=None):
        entry = cls._get_entry_or_404(space_id, entry_id)
        _, items = cls._build_reference_items(space_id, entry)

        if scope == "published":
            items = [item for item in items if item["published_node_count"]]
        elif scope == "draft":
            items = [item for item in items if item["draft_node_count"]]

        if keyword:
            kw = keyword.lower()
            items = [
                item
                for item in items
                if kw in (item["flow_name"] or "").lower() or kw in (item["maintainer"] or "").lower()
            ]

        total = len(items)
        page = page if page and page > 0 else 1
        page_size = min(page_size, cls.MAX_PAGE_SIZE) if page_size else cls.DEFAULT_PAGE_SIZE
        start = (page - 1) * page_size
        return {
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": items[start : start + page_size],
        }

    @staticmethod
    def _get_entry_or_404(space_id, entry_id):
        entry = SpacePluginCatalogEntry.objects.filter(space_id=space_id, pk=entry_id).first()
        if entry is None:
            raise NotFoundError(f"插件记录 {entry_id} 不存在")
        return entry

    @classmethod
    def _build_reference_items(cls, space_id, entry):
        base_qs = TemplatePluginReference.objects.filter(
            space_id=space_id,
            plugin_type=entry.plugin_type,
            source_key=entry.source_key,
            plugin_code=entry.plugin_code,
            resolved=True,
        )

        counts_by_template = {}
        for row in base_qs.values("template_id", "role").annotate(cnt=Count("id")):
            counts_by_template.setdefault(row["template_id"], {})[row["role"]] = row["cnt"]

        draft_names_by_template = {}
        for template_id, node_name in base_qs.filter(role=TemplatePluginReferenceRole.DRAFT).values_list(
            "template_id", "node_name"
        ):
            draft_names_by_template.setdefault(template_id, []).append(node_name)

        template_ids = list(counts_by_template.keys())
        draft_snapshot_ids = set(
            TemplateSnapshot.objects.filter(template_id__in=template_ids, draft=True).values_list(
                "template_id", flat=True
            )
        )
        templates = {
            t.id: t
            for t in Template.objects.filter(id__in=template_ids, space_id=space_id, is_deleted=False)
        }

        items = []
        published_flow_count = 0
        draft_only_flow_count = 0
        for template_id, counts in counts_by_template.items():
            template = templates.get(template_id)
            has_published = TemplatePluginReferenceRole.PUBLISHED in counts
            has_draft = TemplatePluginReferenceRole.DRAFT in counts
            if has_published:
                published_flow_count += 1
            if has_draft and not has_published:
                draft_only_flow_count += 1

            published_node_count = counts.get(TemplatePluginReferenceRole.PUBLISHED, 0)
            if template_id in draft_snapshot_ids:
                draft_node_count = counts.get(TemplatePluginReferenceRole.DRAFT, 0)
                draft_node_names = draft_names_by_template.get(template_id, [])
            else:
                draft_node_count = None
                draft_node_names = None

            published_version = None
            if template is not None and published_node_count:
                try:
                    published_version = template.version
                except Exception:
                    logger.exception("查询流程发布版本号失败: template_id=%s", template_id)

            items.append(
                {
                    "template_id": template_id,
                    "flow_name": template.name if template else f"#{template_id}",
                    "maintainer": (template.updated_by or template.creator) if template else "",
                    "published_node_count": published_node_count,
                    "published_version": published_version,
                    "draft_node_count": draft_node_count,
                    "draft_node_names": draft_node_names,
                    "_sort_key": template.update_at if template else timezone.now(),
                }
            )

        items.sort(key=lambda item: item["_sort_key"], reverse=True)
        for item in items:
            item.pop("_sort_key", None)

        refs = {
            "flow_count": len(counts_by_template),
            "published_flow_count": published_flow_count,
            "draft_only_flow_count": draft_only_flow_count,
        }
        return refs, items
