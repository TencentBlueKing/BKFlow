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
from django.utils import timezone

from bkflow.exceptions import NotFoundError, ValidationError
from bkflow.plugin_catalog.models import (
    CatalogChangeSource,
    CatalogChangeType,
    PluginCatalogStatus,
    PluginDirectory,
    SpacePluginCatalogEntry,
)
from bkflow.plugin_catalog.services.change_record_service import CatalogChangeRecordService
from bkflow.plugin_catalog.services.query_service import MAX_RECOMMEND, PluginCatalogQueryService

logger = logging.getLogger(__name__)

# 未提供该参数（区别于显式传 None="未分类"）的哨兵值
UNSET = object()

# 状态机允许的流转方向（三态 + 一个失效终态）：
#   待审核 → 启用（审核通过）/ 未启用（审核不通过）
#   启用   → 未启用（管理员停用）
#   未启用 → 启用（重新启用）
#   已失效 → 终态，不开放人工流转；来源重新出现时由同步任务按 pre_invalid_status 唤醒
ALLOWED_TRANSITIONS = {
    PluginCatalogStatus.PENDING_REVIEW: {PluginCatalogStatus.ENABLE, PluginCatalogStatus.DISABLED},
    PluginCatalogStatus.ENABLE: {PluginCatalogStatus.DISABLED},
    PluginCatalogStatus.DISABLED: {PluginCatalogStatus.ENABLE},
    PluginCatalogStatus.EXPIRED: set(),
}

# 审核不通过时写入「未启用原因」的固定文案（人工决定，与来源无关）
REJECTED_REASON = "审核不通过"


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
    def _resolve_replace_plugin(space_id, entry_id, replace_plugin_id):
        """解析建议替换插件：必须是本空间内、可见、且不是自身的另一个插件。

        设计稿 8「停用插件」弹窗的替换插件下拉只能选当前可见的其他插件，
        因此这里按同口径校验，避免写入一个前端根本选不到的引用。
        """
        replace_entry = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id, pk=replace_plugin_id
        ).first()
        if replace_entry is None:
            raise ValidationError(f"建议替换插件 {replace_plugin_id} 不存在")
        if replace_entry.id == entry_id:
            raise ValidationError("建议替换插件不能是插件自身")
        if replace_entry.status != PluginCatalogStatus.ENABLE:
            raise ValidationError(
                f"建议替换插件 {replace_plugin_id} 当前不是可用状态，不能作为替换建议"
            )
        return replace_entry

    # ----------------------------------------------------------- 编辑单条(01) ----

    @classmethod
    def update_entry(
        cls,
        space_id,
        entry_id,
        directory_id=UNSET,
        recommended=UNSET,
        operator="admin",
        operate_source=CatalogChangeSource.WEB,
        request_id="",
    ):
        if directory_id is not UNSET:
            entry = cls._get_entry_or_404(space_id, entry_id)
            before_value = CatalogChangeRecordService.entry_snapshot(entry)
            entry.directory = cls._resolve_directory(space_id, directory_id)
            entry.updated_by = operator
            entry.save(update_fields=["directory", "updated_by", "update_at"])
            CatalogChangeRecordService.record_entry_change(
                space_id=space_id,
                entry=entry,
                before_value=before_value,
                operate_type=CatalogChangeType.UPDATE_ENTRY,
                operator=operator,
                method="plugins/update_entry",
                operate_source=operate_source,
                request_id=request_id,
            )
        if recommended is not UNSET:
            cls.set_recommended(
                space_id,
                entry_id,
                recommended,
                operator,
                operate_source=operate_source,
                request_id=request_id,
            )
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
        disable_reason="",
        replace_plugin_id=None,
        operate_source=CatalogChangeSource.WEB,
        request_id="",
        change_type=CatalogChangeType.TRANSITION_STATUS,
        method="plugins/status",
    ):
        with transaction.atomic():
            entry = cls._get_entry_or_404(space_id, entry_id, for_update=True)
            allowed = ALLOWED_TRANSITIONS.get(entry.status, set())
            if target_status not in allowed:
                raise ValidationError(f"插件当前状态「{entry.status}」不允许流转到「{target_status}」")

            before_value = CatalogChangeRecordService.entry_snapshot(entry)
            now = timezone.now()
            update_fields = ["status", "updated_by", "update_at"]

            if target_status == PluginCatalogStatus.ENABLE:
                if target_directory_id is UNSET:
                    raise ValidationError("启用插件需要指定 target_directory_id（可为空表示未分类）")
                entry.directory = cls._resolve_directory(space_id, target_directory_id)
                entry.ever_enabled = True
                update_fields += ["directory", "ever_enabled"]
            elif target_status == PluginCatalogStatus.DISABLED:
                # 未启用原因是选填：
                #   - 管理员停用：用户填写的原因
                #   - 审核不通过：写固定文案「审核不通过」
                # 不填时前端统一显示「该插件已被空间管理停用」
                if entry.status == PluginCatalogStatus.PENDING_REVIEW:
                    entry.disable_reason = disable_reason or REJECTED_REASON
                else:
                    entry.disable_reason = disable_reason or ""
                update_fields.append("disable_reason")

            # 建议替换插件在「未启用」场景可填（设计稿的停用配置弹窗有该下拉）
            if replace_plugin_id:
                entry.replace_plugin = cls._resolve_replace_plugin(space_id, entry.id, replace_plugin_id)
                update_fields.append("replace_plugin")

            entry.status = target_status
            entry.updated_by = operator
            entry.update_at = now
            entry.save(update_fields=update_fields)

            CatalogChangeRecordService.record_entry_change(
                space_id=space_id,
                entry=entry,
                before_value=before_value,
                operate_type=change_type,
                operator=operator,
                method=method,
                reason=entry.disable_reason,
                operate_source=operate_source,
                request_id=request_id,
            )
        return entry

    @classmethod
    def suggest_restore_directory(cls, space_id, entry_id):
        """03 · 启用二次确认弹窗的默认目录建议：原目录仍存在则沿用，否则回「未分类」。"""
        entry = cls._get_entry_or_404(space_id, entry_id)
        if entry.directory_id and PluginDirectory.objects.filter(space_id=space_id, pk=entry.directory_id).exists():
            return {"directory_id": entry.directory_id}
        return {"directory_id": None}

    @classmethod
    def update_reason(
        cls,
        space_id,
        entry_id,
        reason="",
        replace_plugin_id=None,
        operator="admin",
        operate_source=CatalogChangeSource.WEB,
        request_id="",
    ):
        """03 · 独立编辑「未启用配置」（未启用原因 + 建议替换插件），仅「未启用」态下允许。

        未启用原因与建议替换插件是一组配置（设计稿的「停用配置」弹窗就是这两个字段），
        与状态流转解耦：停用后仍可单独调整文案与替代推荐。
        「已失效」是来源事实（源头已不存在该插件），不在此入口维护。
        """
        entry = cls._get_entry_or_404(space_id, entry_id)
        if entry.status != PluginCatalogStatus.DISABLED:
            raise ValidationError(f"当前状态「{entry.status}」不支持编辑未启用配置")

        reason = reason or ""
        if len(reason) > 200:
            raise ValidationError("原因不能超过 200 字")

        before_value = CatalogChangeRecordService.entry_snapshot(entry)
        entry.disable_reason = reason
        update_fields = ["disable_reason"]
        if replace_plugin_id:
            entry.replace_plugin = cls._resolve_replace_plugin(space_id, entry.id, replace_plugin_id)
            update_fields.append("replace_plugin")
        entry.updated_by = operator
        entry.save(update_fields=update_fields + ["updated_by", "update_at"])
        CatalogChangeRecordService.record_entry_change(
            space_id=space_id,
            entry=entry,
            before_value=before_value,
            operate_type=CatalogChangeType.UPDATE_REASON,
            operator=operator,
            method="plugins/reason",
            reason=reason,
            operate_source=operate_source,
            request_id=request_id,
        )
        return entry

    # ------------------------------------------------------------- 批量操作 ----

    @classmethod
    def batch_category(
        cls,
        space_id,
        ids,
        directory_id,
        operator="admin",
        operate_source=CatalogChangeSource.WEB,
        request_id="",
    ):
        directory = cls._resolve_directory(space_id, directory_id)
        entries = list(SpacePluginCatalogEntry.objects.filter(space_id=space_id, id__in=ids, is_deleted=False))
        before_map = {entry.id: CatalogChangeRecordService.entry_snapshot(entry) for entry in entries}
        with transaction.atomic():
            updated = SpacePluginCatalogEntry.objects.filter(space_id=space_id, id__in=ids, is_deleted=False).update(
                directory=directory, updated_by=operator, update_at=timezone.now()
            )
            # 批量归类按条目逐条留痕：查单个插件的历史时才能查到这次批量操作
            for entry in entries:
                entry.directory = directory
                CatalogChangeRecordService.record_entry_change(
                    space_id=space_id,
                    entry=entry,
                    before_value=before_map[entry.id],
                    operate_type=CatalogChangeType.BATCH_CATEGORY,
                    operator=operator,
                    method="plugins/batch_category",
                    operate_source=operate_source,
                    request_id=request_id,
                )
        return {"ids": ids, "updated": updated}

    @classmethod
    def batch_status(
        cls,
        space_id,
        ids,
        status,
        target_directory_id=None,
        items=None,
        operator="admin",
        operate_source=CatalogChangeSource.WEB,
        request_id="",
    ):
        """
        批量启用/未启用复用同一个入口。`items` 支持"逐条保留各自原目录"
        场景（`[{"id":.., "target_directory_id":..}]`），未提供时按 `target_directory_id` 统一赋值；
        两者都没有且 status=enable 时，各条目沿用自身现有 directory_id（等价于"保持原目录不变"）。
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
                if status == PluginCatalogStatus.ENABLE:
                    if eid in directory_overrides:
                        extra["target_directory_id"] = directory_overrides[eid]
                    elif target_directory_id is not None:
                        extra["target_directory_id"] = target_directory_id
                    else:
                        # 未显式指定目录时，沿用条目当前 directory_id（03 的"各自保留原目录"默认行为）
                        extra["target_directory_id"] = entry.directory_id
                cls.transition_status(
                    space_id=space_id,
                    entry_id=eid,
                    target_status=status,
                    operator=operator,
                    operate_source=operate_source,
                    request_id=request_id,
                    change_type=CatalogChangeType.BATCH_STATUS,
                    method="plugins/batch_status",
                    **extra,
                )

        return {"ids": list(entries.keys())}

    # ----------------------------------------------------------------- 推荐(05) ----

    @classmethod
    def set_recommended(
        cls,
        space_id,
        entry_id,
        recommended,
        operator="admin",
        operate_source=CatalogChangeSource.WEB,
        request_id="",
    ):
        with transaction.atomic():
            entry = cls._get_entry_or_404(space_id, entry_id, for_update=True)
            before_value = CatalogChangeRecordService.entry_snapshot(entry)
            if recommended and not entry.recommended:
                current_count = (
                    SpacePluginCatalogEntry.objects.select_for_update()
                    .filter(space_id=space_id, recommended=True, is_deleted=False)
                    .count()
                )
                if current_count >= MAX_RECOMMEND:
                    raise ValidationError(f"空间推荐已达上限 {MAX_RECOMMEND}，请先移除不需要的推荐")
                entry.recommended = True
            elif not recommended and entry.recommended:
                entry.recommended = False
            entry.updated_by = operator
            entry.save(update_fields=["recommended", "updated_by", "update_at"])

            CatalogChangeRecordService.record_entry_change(
                space_id=space_id,
                entry=entry,
                before_value=before_value,
                operate_type=(
                    CatalogChangeType.RECOMMEND if recommended else CatalogChangeType.CANCEL_RECOMMEND
                ),
                operator=operator,
                method="plugins/recommend" if recommended else "plugins/recommend_cancel",
                operate_source=operate_source,
                request_id=request_id,
            )
        return entry

    @classmethod
    def cancel_recommend(cls, space_id, entry_id, operator="admin", operate_source=CatalogChangeSource.WEB, request_id=""):
        return cls.set_recommended(
            space_id,
            entry_id,
            recommended=False,
            operator=operator,
            operate_source=operate_source,
            request_id=request_id,
        )

    @classmethod
    def list_recommend(cls, space_id):
        entries = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id, recommended=True, is_deleted=False
        ).order_by("id")
        return PluginCatalogQueryService.serialize_entries(space_id, list(entries))

