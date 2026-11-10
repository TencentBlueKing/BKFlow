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
from django.db.models import Max
from django.utils import timezone

from bkflow.exceptions import NotFoundError, ValidationError
from bkflow.plugin_catalog.models import PluginCatalogStatus, PluginDirectory, SpacePluginCatalogEntry
from bkflow.plugin_catalog.services.query_service import MAX_RECOMMEND, PluginCatalogQueryService

logger = logging.getLogger(__name__)

# 未提供该参数（区别于显式传 None="未分类"）的哨兵值
UNSET = object()

# 状态机允许的流转方向。invalid 为终态，只能由同步任务唤醒，不开放任何人工流转入口；
# offline 不开放回退到「已停用」（下架后只能重新启用或保持下架，减少状态跳转复杂度）。
ALLOWED_TRANSITIONS = {
    PluginCatalogStatus.REVIEW: {PluginCatalogStatus.VISIBLE, PluginCatalogStatus.NOT_ENABLED},
    PluginCatalogStatus.VISIBLE: {PluginCatalogStatus.DISABLED},
    PluginCatalogStatus.DISABLED: {PluginCatalogStatus.VISIBLE, PluginCatalogStatus.OFFLINE},
    PluginCatalogStatus.OFFLINE: {PluginCatalogStatus.VISIBLE},
    PluginCatalogStatus.NOT_ENABLED: {PluginCatalogStatus.VISIBLE},
    PluginCatalogStatus.INVALID: set(),
}


class PluginCatalogService:
    """
    插件列表页的编辑、状态流转、批量操作与空间推荐位管理。
    """

    # --------------------------------------------------------------- 基础工具 ----

    @staticmethod
    def _get_entry_or_404(space_id, entry_id, for_update=False):
        queryset = SpacePluginCatalogEntry.objects.filter(space_id=space_id, pk=entry_id)
        if for_update:
            queryset = queryset.select_for_update()
        entry = queryset.first()
        if entry is None:
            raise NotFoundError(f"插件记录 {entry_id} 不存在")
        return entry

    @staticmethod
    def _resolve_directory(space_id, directory_id):
        if directory_id in (None, "", "null", "uncategorized"):
            return None
        directory = PluginDirectory.objects.filter(space_id=space_id, pk=directory_id).first()
        if directory is None:
            raise ValidationError(f"目录 {directory_id} 不存在")
        return directory

    @staticmethod
    def _merge_disable_config(existing, incoming):
        """保留 `_meta` 命名空间下的内部字段（如 pre_invalid_status/applied_ai_request_id），
        只用用户输入覆盖业务可见的其余字段，避免人工编辑时误把内部状态冲掉。"""
        meta = dict((existing or {}).get("_meta", {}))
        merged = {key: value for key, value in (incoming or {}).items() if key != "_meta"}
        merged["_meta"] = meta
        return merged

    # ----------------------------------------------------------- 编辑单条(01) ----

    @classmethod
    def update_entry(cls, space_id, entry_id, directory_id=UNSET, recommended=UNSET, operator="admin"):
        if directory_id is not UNSET:
            entry = cls._get_entry_or_404(space_id, entry_id)
            entry.directory = cls._resolve_directory(space_id, directory_id)
            entry.updated_by = operator
            entry.save(update_fields=["directory", "updated_by", "update_at"])
        if recommended is not UNSET:
            cls.set_recommended(space_id, entry_id, recommended, operator)
        return cls._get_entry_or_404(space_id, entry_id)

    # --------------------------------------------------------- 状态流转(01/02/03) ----

    @classmethod
    def transition_status(
        cls,
        space_id,
        entry_id,
        target_status,
        operator="admin",
        target_directory_id=UNSET,
        disable_config=None,
        offline_reason="",
        replace_plugin_id=None,
    ):
        with transaction.atomic():
            entry = cls._get_entry_or_404(space_id, entry_id, for_update=True)
            allowed = ALLOWED_TRANSITIONS.get(entry.status, set())
            if target_status not in allowed:
                raise ValidationError(f"插件当前状态「{entry.status}」不允许流转到「{target_status}」")

            now = timezone.now()
            update_fields = ["status", "updated_by", "update_at"]

            if target_status == PluginCatalogStatus.VISIBLE:
                if target_directory_id is UNSET:
                    raise ValidationError("启用插件需要指定 target_directory_id（可为空表示未分类）")
                entry.directory = cls._resolve_directory(space_id, target_directory_id)
                entry.ever_enabled = True
                update_fields += ["directory", "ever_enabled"]
            elif target_status == PluginCatalogStatus.DISABLED:
                if not disable_config:
                    raise ValidationError("停用插件需要填写停用提示配置 disable_config")
                entry.disable_config = cls._merge_disable_config(entry.disable_config, disable_config)
                update_fields.append("disable_config")
            elif target_status == PluginCatalogStatus.OFFLINE:
                if not offline_reason:
                    raise ValidationError("下架插件需要填写下架原因 offline_reason")
                entry.offline_reason = offline_reason
                entry.offline_by = operator
                entry.offline_time = now
                update_fields += ["offline_reason", "offline_by", "offline_time"]
                if replace_plugin_id:
                    replace_entry = SpacePluginCatalogEntry.objects.filter(
                        space_id=space_id, pk=replace_plugin_id
                    ).first()
                    if replace_entry is None:
                        raise ValidationError(f"建议替换插件 {replace_plugin_id} 不存在")
                    entry.replace_plugin = replace_entry
                    update_fields.append("replace_plugin")
            # target_status == NOT_ENABLED（不启用）：仅改 status，不需要额外字段

            entry.status = target_status
            entry.updated_by = operator
            entry.update_at = now
            entry.save(update_fields=update_fields)
        return entry

    @classmethod
    def suggest_restore_directory(cls, space_id, entry_id):
        """03 · 启用二次确认弹窗的默认目录建议：原目录仍存在则沿用，否则回「未分类」。"""
        entry = cls._get_entry_or_404(space_id, entry_id)
        if entry.directory_id and PluginDirectory.objects.filter(space_id=space_id, pk=entry.directory_id).exists():
            return {"directory_id": entry.directory_id}
        return {"directory_id": None}

    @classmethod
    def update_disable_config(cls, space_id, entry_id, disable_config, operator="admin"):
        """03 · 独立编辑停用提示配置，仅「已停用」/「已下架」两态下允许（与状态流转解耦）。"""
        entry = cls._get_entry_or_404(space_id, entry_id)
        if entry.status not in (PluginCatalogStatus.DISABLED, PluginCatalogStatus.OFFLINE):
            raise ValidationError(f"当前状态「{entry.status}」不支持编辑停用配置")
        entry.disable_config = cls._merge_disable_config(entry.disable_config, disable_config)
        entry.updated_by = operator
        entry.save(update_fields=["disable_config", "updated_by", "update_at"])
        return entry

    # ------------------------------------------------------------- 批量操作 ----

    @classmethod
    def batch_category(cls, space_id, ids, directory_id, operator="admin"):
        directory = cls._resolve_directory(space_id, directory_id)
        updated = SpacePluginCatalogEntry.objects.filter(space_id=space_id, id__in=ids, is_deleted=False).update(
            directory=directory, updated_by=operator, update_at=timezone.now()
        )
        return {"ids": ids, "updated": updated}

    @classmethod
    def batch_status(cls, space_id, ids, status, target_directory_id=None, items=None, operator="admin"):
        """
        批量启用/不启用复用同一个入口。`items` 支持"逐条保留各自原目录"
        场景（`[{"id":.., "target_directory_id":..}]`），未提供时按 `target_directory_id` 统一赋值；
        两者都没有且 status=visible 时，各条目沿用自身现有 directory_id（等价于"保持原目录不变"）。
        """
        entries = {
            entry.id: entry
            for entry in SpacePluginCatalogEntry.objects.filter(space_id=space_id, id__in=ids, is_deleted=False)
        }
        missing = set(ids) - set(entries.keys())
        if missing:
            raise ValidationError(f"插件记录 {sorted(missing)} 不存在")

        illegal = [eid for eid, entry in entries.items() if status not in ALLOWED_TRANSITIONS.get(entry.status, set())]
        if illegal:
            raise ValidationError(f"插件 {sorted(illegal)} 当前状态不允许流转到「{status}」，批量操作整体拒绝")

        directory_overrides = {int(item["id"]): item.get("target_directory_id") for item in (items or [])}

        with transaction.atomic():
            for eid, entry in entries.items():
                extra = {}
                if status == PluginCatalogStatus.VISIBLE:
                    if eid in directory_overrides:
                        extra["target_directory_id"] = directory_overrides[eid]
                    elif target_directory_id is not None:
                        extra["target_directory_id"] = target_directory_id
                    else:
                        # 未显式指定目录时，沿用条目当前 directory_id（03 的"各自保留原目录"默认行为）
                        extra["target_directory_id"] = entry.directory_id
                cls.transition_status(space_id=space_id, entry_id=eid, target_status=status, operator=operator, **extra)

        return {"ids": list(entries.keys())}

    @classmethod
    def batch_clean(cls, space_id, ids):
        """04 · 批量清理已失效记录：硬删除（不是软删除），因为失效记录本身已是"事实不存在"，
        区别于目录整理场景的软删除。"""
        entries = SpacePluginCatalogEntry.objects.filter(space_id=space_id, id__in=ids)
        found_count = entries.count()
        if found_count != len(set(ids)):
            raise ValidationError("存在不属于该空间或不存在的插件记录")
        statuses = set(entries.values_list("status", flat=True))
        if statuses - {PluginCatalogStatus.INVALID}:
            raise ValidationError("只能清理状态为「已失效」的记录，批量操作整体拒绝")
        entries.delete()
        return {"deleted": found_count}

    # ----------------------------------------------------------------- 推荐(05) ----

    @classmethod
    def set_recommended(cls, space_id, entry_id, recommended, operator="admin"):
        with transaction.atomic():
            entry = cls._get_entry_or_404(space_id, entry_id, for_update=True)
            if recommended and not entry.recommended:
                current_count = (
                    SpacePluginCatalogEntry.objects.select_for_update()
                    .filter(space_id=space_id, recommended=True, is_deleted=False)
                    .count()
                )
                if current_count >= MAX_RECOMMEND:
                    raise ValidationError(f"空间推荐已达上限 {MAX_RECOMMEND}，请先移除不需要的推荐")
                max_order = (
                    SpacePluginCatalogEntry.objects.filter(space_id=space_id, recommended=True).aggregate(
                        Max("recommend_order")
                    )["recommend_order__max"]
                    or 0
                )
                entry.recommended = True
                entry.recommend_order = max_order + 1
            elif not recommended and entry.recommended:
                entry.recommended = False
                entry.recommend_order = None
            entry.updated_by = operator
            entry.save(update_fields=["recommended", "recommend_order", "updated_by", "update_at"])
        return entry

    @classmethod
    def cancel_recommend(cls, space_id, entry_id, operator="admin"):
        return cls.set_recommended(space_id, entry_id, recommended=False, operator=operator)

    @classmethod
    def list_recommend(cls, space_id):
        entries = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id, recommended=True, is_deleted=False
        ).order_by("recommend_order", "id")
        return PluginCatalogQueryService.serialize_entries(space_id, list(entries))

