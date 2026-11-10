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
from pipeline.component_framework.models import ComponentModel

from bkflow.bk_plugin.models import BKPlugin
from bkflow.plugin.constants import WRAPPER_CODES
from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService
from bkflow.plugin_catalog.models import (
    PluginCatalogStatus,
    PluginType,
    SpacePluginCatalogEntry,
)
from bkflow.plugin_catalog.services.strategy_service import PluginAdmissionStrategyService
from bkflow.space.configs import PluginCatalogMigrationConfig
from bkflow.space.models import SpaceConfig

logger = logging.getLogger(__name__)


class PluginCatalogSyncService:
    """
    来源 -> SpacePluginCatalogEntry 的发现/同步/失效识别服务。

    只负责"发现新插件、标记来源消失的插件为失效、来源重新出现时唤醒"，
    不负责管理员的人工分类/状态流转（那部分见 `catalog_service`）。
    """

    @classmethod
    def sync_space_catalog(cls, space_id, username="admin"):
        """对一个空间做一次全量三类来源同步，返回各类型的同步统计。"""
        return {
            PluginType.BUILTIN: cls.sync_builtin(space_id),
            PluginType.BK_PLUGIN: cls.sync_bk_plugin(space_id),
            PluginType.API: cls.sync_api(space_id, username=username),
        }

    @classmethod
    def sync_builtin(cls, space_id):
        current_codes = set(
            ComponentModel.objects.filter(status=True).exclude(code__in=WRAPPER_CODES).values_list("code", flat=True)
        )
        return cls._sync_plugin_type(
            space_id=space_id, plugin_type=PluginType.BUILTIN, source_key="", current_codes=current_codes
        )

    @classmethod
    def sync_bk_plugin(cls, space_id):
        current_codes = set(BKPlugin.objects.for_space(space_id).values_list("code", flat=True))
        return cls._sync_plugin_type(
            space_id=space_id, plugin_type=PluginType.BK_PLUGIN, source_key="", current_codes=current_codes
        )

    @classmethod
    def sync_api(cls, space_id, username="admin"):
        """
        API 插件同步，覆盖 V2/V3/V4 全部协议版本，统一写入 SpacePluginCatalogEntry：

        1. 调用既有 `OpenPluginCatalogService.sync_space_plugins` 刷新 `OpenPluginCatalogIndex`——
           那张表只服务于画布"缓存优先"展示路径、只收录 V4 协议插件，跟下面的统一目录同步逻辑
           完全独立，互不影响；这一步失败只记日志，不阻断下面的同步。
        2. 调用 `OpenPluginCatalogService.fetch_all_source_plugins` 现场拉取每个已配置来源的
           **完整**插件清单（已修复为真正的全量分页，不再受限于首页 200 条），不按协议版本
           过滤，直接作为 `current_codes` 喂给 `_sync_plugin_type`，不需要再为 V2/V3 单独建
           缓存表——V2/V3 协议插件同样纳入目录管理，不再按协议版本过滤。
        3. 若某来源的配置已被整体删除（不再出现在 `fetch_all_source_plugins` 的返回结果里），
           但本空间此前已经为该来源生成过 `SpacePluginCatalogEntry` 记录，强制按
           `current_codes=空集合` 处理，级联将其下全部插件标记为失效——这里不能只依赖
           `OpenPluginCatalogIndex` 里的陈旧数据来判断"当前是否还存在"，那张表在来源配置被
           整体删除后不会自动清理（现有代码行为，不是本次引入的问题，但会误导失效判定，
           所以必须以"当前是否仍在 UniformApiConfig 里配置着"为准，而不是看缓存表里还剩什么）。

        第 2 步本身请求失败（网络/凭证问题）时，直接跳过本次目录条目生成/失效判定，保留现状，
        避免把"这一轮没拉到"误判为"插件已被下架"。
        """
        try:
            OpenPluginCatalogService.sync_space_plugins(space_id=space_id, username=username)
        except Exception:
            logger.exception("开放插件目录(V4展示缓存)刷新失败，不影响下面的统一插件目录同步: space_id=%s", space_id)

        try:
            codes_by_source = OpenPluginCatalogService.fetch_all_source_plugins(space_id=space_id, username=username)
        except Exception:
            logger.exception("API 插件来源拉取失败，跳过本次目录条目生成: space_id=%s", space_id)
            return {"created": 0, "invalidated": 0, "skipped": True}

        configured_sources = set(codes_by_source.keys())
        existing_sources = set(
            SpacePluginCatalogEntry.objects.filter(space_id=space_id, plugin_type=PluginType.API)
            .values_list("source_key", flat=True)
            .distinct()
        )

        total_created, total_invalidated = 0, 0
        # 并集：当前仍配置的来源（可能有新增来源/新增插件）
        #     + 本空间已有记录的来源（可能对应的配置已被整体删除，需要级联失效）
        for source_key in configured_sources | existing_sources:
            current_codes = set(codes_by_source.get(source_key, []))
            stat = cls._sync_plugin_type(
                space_id=space_id,
                plugin_type=PluginType.API,
                source_key=source_key,
                current_codes=current_codes,
            )
            total_created += stat["created"]
            total_invalidated += stat["invalidated"]
        return {"created": total_created, "invalidated": total_invalidated, "skipped": False}

    @classmethod
    def _sync_plugin_type(cls, space_id, plugin_type, source_key, current_codes):
        existing = {
            entry.plugin_code: entry
            for entry in SpacePluginCatalogEntry.objects.filter(
                space_id=space_id, plugin_type=plugin_type, source_key=source_key
            )
        }
        now = timezone.now()

        created = 0
        for code in current_codes - set(existing.keys()):
            cls._create_entry(space_id, plugin_type, source_key, code, now)
            created += 1

        # 之前失效、这一轮又重新出现的插件，唤醒回失效前的状态
        for code in current_codes & set(existing.keys()):
            entry = existing[code]
            if entry.status == PluginCatalogStatus.INVALID:
                cls._revive_entry(entry, now)

        # 之前存在、这一轮不存在、且当前不是失效态的插件，标记失效
        invalidated = 0
        for code in set(existing.keys()) - current_codes:
            entry = existing[code]
            if entry.status == PluginCatalogStatus.INVALID:
                continue
            cls._mark_invalid(entry, now)
            invalidated += 1

        # 仍然存在、本来就不是失效态的条目，刷新一下同步水位，不改其他字段
        still_present_ids = [
            existing[code].id
            for code in current_codes & set(existing.keys())
            if existing[code].status != PluginCatalogStatus.INVALID
        ]
        if still_present_ids:
            SpacePluginCatalogEntry.objects.filter(id__in=still_present_ids).update(
                source_valid=True, last_synced_at=now
            )

        return {"created": created, "invalidated": invalidated}

    @classmethod
    def _create_entry(cls, space_id, plugin_type, source_key, plugin_code, now):
        decision = PluginAdmissionStrategyService.decide(
            space_id=space_id, plugin_type=plugin_type, source_key=source_key
        )
        entry = SpacePluginCatalogEntry.objects.create(
            space_id=space_id,
            plugin_type=plugin_type,
            source_key=source_key,
            plugin_code=plugin_code,
            status=decision.status,
            directory_id=decision.directory_id,
            ever_enabled=decision.status == PluginCatalogStatus.VISIBLE,
            source_valid=True,
            last_synced_at=now,
            updated_by="system",
        )
        if decision.need_ai:
            cls._dispatch_auto_classify(entry, ai_scope=decision.ai_scope)
        return entry

    @classmethod
    def _dispatch_auto_classify(cls, entry, ai_scope):
        # 延迟 import：Celery 的任务模块由 worker 启动时的 autodiscovery 加载，
        # 这里保持"用时才导入"，避免应用加载阶段就把任务模块拉进来（与
        # bkflow/statistics/tasks/ 的写法保持一致）。这不是循环依赖导致的绕行。
        from bkflow.plugin_catalog.tasks import apply_automatic_classification_task

        plugin_key = f"{entry.plugin_type}:{entry.source_key}:{entry.plugin_code}"
        request_id = f"auto-sync-{entry.id}"
        transaction.on_commit(
            lambda: apply_automatic_classification_task.delay(
                space_id=entry.space_id,
                plugin_keys=[plugin_key],
                request_id=request_id,
                ai_scope=ai_scope,
            )
        )

    @classmethod
    def _mark_invalid(cls, entry, now):
        disable_config = cls._set_meta(entry.disable_config, pre_invalid_status=entry.status)
        entry.status = PluginCatalogStatus.INVALID
        entry.invalid_reason = "来源中已不存在该插件"
        entry.found_time = now
        entry.source_valid = False
        entry.last_synced_at = now
        entry.disable_config = disable_config
        entry.recommended = False
        entry.recommend_order = None
        entry.updated_by = "system"
        entry.save(
            update_fields=[
                "status",
                "invalid_reason",
                "found_time",
                "source_valid",
                "last_synced_at",
                "disable_config",
                "recommended",
                "recommend_order",
                "updated_by",
                "update_at",
            ]
        )

    @classmethod
    def _revive_entry(cls, entry, now):
        meta = dict((entry.disable_config or {}).get("_meta", {}))
        pre_status = meta.pop("pre_invalid_status", PluginCatalogStatus.REVIEW)
        disable_config = dict(entry.disable_config or {})
        disable_config["_meta"] = meta
        entry.status = pre_status
        entry.invalid_reason = ""
        entry.found_time = None
        entry.source_valid = True
        entry.last_synced_at = now
        entry.disable_config = disable_config
        entry.updated_by = "system"
        entry.save(
            update_fields=[
                "status",
                "invalid_reason",
                "found_time",
                "source_valid",
                "last_synced_at",
                "disable_config",
                "updated_by",
                "update_at",
            ]
        )

    @staticmethod
    def _set_meta(disable_config, **meta_updates):
        disable_config = dict(disable_config or {})
        meta = dict(disable_config.get("_meta", {}))
        meta.update(meta_updates)
        disable_config["_meta"] = meta
        return disable_config

    @classmethod
    def iter_ready_spaces(cls):
        """
        遍历已完成「插件目录」初始化迁移（PluginCatalogMigrationConfig.ready=True）的空间 id，
        供 Celery 调度按空间投递同步任务使用，见 bkflow/plugin/tasks.py::dispatch_open_plugin_catalog_sync。
        """
        queryset = SpaceConfig.objects.filter(name=PluginCatalogMigrationConfig.name).only("space_id", "json_value")
        for space_config in queryset.iterator():
            if isinstance(space_config.json_value, dict) and space_config.json_value.get("ready"):
                yield space_config.space_id
