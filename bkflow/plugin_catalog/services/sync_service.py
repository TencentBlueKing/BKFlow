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
from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService
from bkflow.plugin_catalog.models import (
    PluginCatalogStatus,
    PluginType,
    SpacePluginCatalogEntry,
)
from bkflow.plugin_catalog.services.source_group_service import SourceGroupService
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
        # 元信息跟数据一次取回：code / name / version 一次查询，避免同一个来源查两遍表。
        # 功能性内置插件（子画布等）不参与目录管理，在采集阶段就排除，不会写进目录条目表。
        plugins = SourceGroupService.collect_builtin_metadata()
        return cls._sync_plugin_type(
            space_id=space_id, plugin_type=PluginType.BUILTIN, source_key="", plugins=plugins
        )

    @classmethod
    def sync_bk_plugin(cls, space_id):
        # 元信息跟数据一次取回：code / name / introduction 一次查询
        plugins = SourceGroupService.collect_bk_plugin_metadata(space_id)
        return cls._sync_plugin_type(
            space_id=space_id, plugin_type=PluginType.BK_PLUGIN, source_key="", plugins=plugins
        )

    @classmethod
    def sync_api(cls, space_id, username="admin"):
        """
        API 插件同步，覆盖 V2/V3/V4 全部协议版本，统一写入 SpacePluginCatalogEntry：

        1. 调用 `OpenPluginCatalogService.sync_space_plugins_with_meta` **一次**请求完成两件事：
           刷新 `OpenPluginCatalogIndex`（只服务画布"缓存优先"展示路径、只收录 V4 协议插件，
           与下面的统一目录同步逻辑完全独立，互不影响），同时返回每个已配置来源的**完整**
           插件元信息（name + description，V2/V3/V4 都有）——现场拉取已修复为真正的全量分页，
           不再受限于首页 200 条；不按协议版本过滤，直接作为统一目录的写入依据，不需要再为
           V2/V3 单独建缓存表——V2/V3 协议插件同样纳入目录管理，不再按协议版本过滤。
        2. 若某来源的配置已被整体删除（不再出现在返回结果里），但本空间此前已经为该来源
           生成过 `SpacePluginCatalogEntry` 记录，强制按"空集合"处理，级联将其下全部插件
           标记为失效——这里不能只依赖 `OpenPluginCatalogIndex` 里的陈旧数据来判断"当前是否
           还存在"，那张表在来源配置被整体删除后不会自动清理（现有代码行为，不是本次引入的
           问题，但会误导失效判定，所以必须以"当前是否仍在 UniformApiConfig 里配置着"为准，
           而不是看缓存表里还剩什么）。

        第 1 步本身请求失败（网络/凭证问题）时，直接跳过本次目录条目生成/失效判定，保留现状，
        避免把"这一轮没拉到"误判为"插件已被下架"。
        """
        try:
            plugins_by_source = OpenPluginCatalogService.sync_space_plugins_with_meta(
                space_id=space_id, username=username
            )
        except Exception:
            logger.exception("API 插件来源拉取失败，跳过本次目录条目生成: space_id=%s", space_id)
            return {"created": 0, "invalidated": 0, "skipped": True}

        configured_sources = set(plugins_by_source.keys())
        existing_sources = set(
            SpacePluginCatalogEntry.objects.filter(space_id=space_id, plugin_type=PluginType.API)
            .values_list("source_key", flat=True)
            .distinct()
        )

        total_created, total_invalidated = 0, 0
        # 并集：当前仍配置的来源（可能有新增来源/新增插件）
        #     + 本空间已有记录的来源（可能对应的配置已被整体删除，需要级联失效）
        for source_key in configured_sources | existing_sources:
            plugins = plugins_by_source.get(source_key, {})
            stat = cls._sync_plugin_type(
                space_id=space_id,
                plugin_type=PluginType.API,
                source_key=source_key,
                plugins=plugins,
            )
            total_created += stat["created"]
            total_invalidated += stat["invalidated"]
        return {"created": total_created, "invalidated": total_invalidated, "skipped": False}

    @classmethod
    def _sync_plugin_type(cls, space_id, plugin_type, source_key, plugins):
        """
        同步单一来源类型的插件目录条目。

        :param plugins: `{plugin_code: (name, desc)}`——由调用方（各来源的采集逻辑）准备好。
            元信息跟着数据一次取回，本方法不再自己去外部只读表补查，避免同一份数据查两遍；
            API 插件的元信息直接来自现场响应（V2/V3/V4 都有），不依赖只收录 V4 的缓存表。
        """
        existing = {
            entry.plugin_code: entry
            for entry in SpacePluginCatalogEntry.objects.filter(
                space_id=space_id, plugin_type=plugin_type, source_key=source_key
            )
        }
        now = timezone.now()
        current_codes = set(plugins.keys())

        # 来源元信息（插件名 + 描述）：创建时写入，已存在的条目每次同步都刷新，
        # 这样插件在来源侧改名/改描述后，下一次同步就能带过来。
        metadata = plugins

        created = 0
        for code in current_codes - set(existing.keys()):
            cls._create_entry(space_id, plugin_type, source_key, code, now, metadata.get(code, ("", "")))
            created += 1

        # 之前失效、这一轮又重新出现的插件，唤醒回失效前的状态
        for code in current_codes & set(existing.keys()):
            entry = existing[code]
            if entry.status == PluginCatalogStatus.EXPIRED:
                cls._revive_entry(entry, now)

        # 之前存在、这一轮不存在、且当前不是失效态的插件，标记失效
        invalidated = 0
        for code in set(existing.keys()) - current_codes:
            entry = existing[code]
            if entry.status == PluginCatalogStatus.EXPIRED:
                continue
            cls._mark_invalid(entry, now)
            invalidated += 1

        # 仍然存在、本来就不是失效态的条目，刷新同步水位 + 刷新来源元信息
        still_present = [
            existing[code] for code in current_codes & set(existing.keys())
            if existing[code].status != PluginCatalogStatus.EXPIRED
        ]
        if still_present:
            SpacePluginCatalogEntry.objects.filter(id__in=[entry.id for entry in still_present]).update(
                last_synced_at=now
            )
            cls._refresh_metadata(still_present, metadata)

        return {"created": created, "invalidated": invalidated}

    @classmethod
    def _refresh_metadata(cls, entries, metadata):
        """刷新已存在条目的来源元信息（插件名 + 描述）。

        只更新变化的行，避免每次同步都把所有条目重写一遍。
        """
        to_update = []
        for entry in entries:
            name, desc = metadata.get(entry.plugin_code, (None, None))
            if name is None and desc is None:
                continue
            changed = []
            if name is not None and entry.plugin_name != name:
                entry.plugin_name = name
                changed.append("plugin_name")
            if desc is not None and entry.plugin_desc != desc:
                entry.plugin_desc = desc
                changed.append("plugin_desc")
            if changed:
                to_update.append(entry)
        if to_update:
            SpacePluginCatalogEntry.objects.bulk_update(to_update, ["plugin_name", "plugin_desc"])

    @classmethod
    def _create_entry(cls, space_id, plugin_type, source_key, plugin_code, now, metadata=("", "")):
        decision = PluginAdmissionStrategyService.decide(
            space_id=space_id, plugin_type=plugin_type, source_key=source_key
        )
        plugin_name, plugin_desc = metadata
        entry = SpacePluginCatalogEntry.objects.create(
            space_id=space_id,
            plugin_type=plugin_type,
            source_key=source_key,
            plugin_code=plugin_code,
            plugin_name=plugin_name or "",
            plugin_desc=plugin_desc or "",
            status=decision.status,
            directory_id=decision.directory_id,
            ever_enabled=decision.status == PluginCatalogStatus.ENABLE,
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
        """标记失效：记下失效前的状态，供来源重新出现后唤醒回原状态。

        失效只改「来源事实」（状态置已失效 + 发现时间），
        **不动管理员的管理决定**（目录、推荐、未启用原因）——设计文档要求
        「失效不改管理决定」「来源同步不能覆盖人工决定」，所以失效原因不写入
        `disable_reason`，人工填写的停用原因必须原样保留。
        """
        entry.pre_invalid_status = entry.status
        entry.status = PluginCatalogStatus.EXPIRED
        entry.found_time = now
        entry.last_synced_at = now
        entry.recommended = False
        entry.updated_by = "system"
        entry.save(
            update_fields=[
                "status",
                "found_time",
                "last_synced_at",
                "pre_invalid_status",
                "recommended",
                "updated_by",
                "update_at",
            ]
        )

    @classmethod
    def _revive_entry(cls, entry, now):
        """唤醒回失效前的状态。

        `pre_invalid_status` 是**一次性**记忆：用完即清空，避免下一轮失效时读到上一次的旧值。
        没有记忆（空串）时保守回落到待审核，交给管理员处理。
        `disable_reason` 不动：人工填的停用原因在失效期间保留，唤醒后仍有效。
        """
        pre_status = entry.pre_invalid_status or PluginCatalogStatus.PENDING_REVIEW
        entry.pre_invalid_status = ""
        entry.status = pre_status
        entry.found_time = None
        entry.last_synced_at = now
        entry.updated_by = "system"
        entry.save(
            update_fields=[
                "status",
                "found_time",
                "last_synced_at",
                "pre_invalid_status",
                "updated_by",
                "update_at",
            ]
        )

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
