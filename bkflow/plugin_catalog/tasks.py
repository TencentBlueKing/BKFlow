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

from celery import shared_task
from django.db import transaction

from bkflow.plugin_catalog.models import PluginCatalogStatus, SpacePluginCatalogEntry
from bkflow.plugin_catalog.services.ai_classify_service import AiClassifyService

logger = logging.getLogger("celery")


@shared_task(ignore_result=True, max_retries=0)
def sync_space_plugin_catalog_task(space_id, trigger="schedule", source_keys=None):
    """
    按空间同步 builtin/bk_plugin/api 三类插件进统一插件目录。
    由 bkflow.plugin.tasks.dispatch_open_plugin_catalog_sync 对"已完成插件目录迁移"的空间
    批量投递。失败只记录日志，不自动重试，
    等下一轮周期调度自然重试（与现有 sync_open_plugin_catalog_source 的失败处理口径一致）。

    `trigger` 区分触发原因（设计文档：快速重试与低频恢复走**同一个同步执行函数**、
    不同触发原因，**不另建 retry task**、不新增 Beat 入口）：

    - `schedule`：周期调度（Beat 30 分钟一轮）
    - `retry`：失败后的快速重试（按 `SourceSyncState` 里的 `next_retry_at` 决定间隔，
      10/20/40 秒退避、最多 3 次、抖动不超过 20%）

    快速重试的判定状态**持久化在 `SourceSyncState` 表里**（不是队列消息），
    进程重启不丢；耗尽后同一故障不重新开启快速重试，等下一轮周期调度自然重试。
    """
    # 延迟 import，避免在 Celery worker 启动阶段过早触发 bkflow.plugin_catalog.services 的
    # 模块级依赖加载顺序问题。
    from bkflow.plugin_catalog.services.sync_service import PluginCatalogSyncService

    try:
        result = PluginCatalogSyncService.sync_space_catalog(
            space_id=space_id, source_keys=source_keys
        )
        logger.info("空间插件目录同步完成: space_id=%s, trigger=%s, result=%s", space_id, trigger, result)
    except Exception:
        logger.exception("空间插件目录同步失败: space_id=%s, trigger=%s", space_id, trigger)
        raise

    # 采集失败的来源：未耗尽且有下次重试时间 -> 延迟投递自己（同一个 task，trigger=retry）
    if trigger != "retry":
        _dispatch_fast_retry(space_id)
    return result


def _dispatch_fast_retry(space_id):
    """为采集失败的来源投递一次**快速重试**（同一个 task，`trigger=retry`）。

    设计文档要求：快速重试与低频恢复走**同一个同步执行函数、不同触发原因**，
    **不另建 retry task**、不新增 Beat 入口；重试次数与时限写在 `SourceSyncState`
    （不是队列消息），进程重启不丢。

    只重试「失败且未耗尽」的来源；耗尽的（同一故障已重试满 3 次）等下一轮周期调度。
    """
    from django.utils import timezone

    from bkflow.plugin_catalog.services.source_sync_state_service import SourceSyncStateService

    pending = SourceSyncStateService.pending_retry_sources(space_id)
    if not pending:
        return 0

    # 每次失败后都要投递，用 countdown 把唤醒时间对齐到 `next_retry_at`
    # （10/20/40 秒退避）；已经到点的 countdown 为 0（立即重试）。
    now = timezone.now()
    source_keys = [source_key for source_key, _ in pending]
    next_at = min(next_retry_at for _, next_retry_at in pending)
    countdown = max(0, int((next_at - now).total_seconds()))
    try:
        sync_space_plugin_catalog_task.apply_async(
            args=[space_id],
            kwargs={"trigger": "retry", "source_keys": source_keys},
            countdown=countdown,
        )
    except Exception:
        logger.exception("[来源同步] 快速重试投递失败，等下一轮周期调度: space_id=%s", space_id)
        return 0
    logger.info(
        "[来源同步] 已投递快速重试: space_id=%s, source_keys=%s, countdown=%ss",
        space_id,
        source_keys,
        countdown,
    )
    return len(source_keys)


@shared_task(ignore_result=True, max_retries=0)
def apply_automatic_classification_task(space_id, plugin_keys, request_id, ai_scope):
    """
    新插件策略"全部直接通过 / AI 自动决定分类"及"设条件自动通过"条件组里 after_pass=ai 的
    异步落位任务。

    只处理仍为 review 态、且未被同一 request_id 处理过的条目，晚到/重复结果不覆盖人工
    已经处理过的记录；AI 服务返回空建议/失败时保持 review，交由人工在待审核列表处理。
    """
    result = AiClassifyService.classify(
        space_id=space_id, plugin_keys=plugin_keys, ai_scope=ai_scope, request_id=request_id
    )

    if result["result"] != AiClassifyService.RESULT_PATCH:
        logger.info(
            "AI 自动分类无建议或失败，保持待审核: space_id=%s, request_id=%s, result=%s",
            space_id,
            request_id,
            result["result"],
        )
        return result

    applied, skipped = [], []
    for plugin_key, directory_id in result["patch"].items():
        plugin_type, source_key, plugin_code = plugin_key.split(":", 2)
        with transaction.atomic():
            entry = (
                SpacePluginCatalogEntry.objects.select_for_update()
                .filter(
                    space_id=space_id,
                    plugin_type=plugin_type,
                    source_key=source_key,
                    plugin_code=plugin_code,
                )
                .first()
            )
            if not entry or entry.status != PluginCatalogStatus.PENDING_REVIEW:
                # 记录不存在，或已被人工处理过（不再是待审核），晚到结果不覆盖
                skipped.append(plugin_key)
                continue
            if entry.applied_ai_request_id == request_id:
                # 同一 request_id 已应用过一次，重复投递直接跳过
                skipped.append(plugin_key)
                continue

            entry.applied_ai_request_id = request_id
            entry.status = PluginCatalogStatus.ENABLE
            entry.directory_id = directory_id
            entry.ever_enabled = True
            entry.updated_by = "system"
            entry.save(
                update_fields=[
                    "status",
                    "directory_id",
                    "ever_enabled",
                    "applied_ai_request_id",
                    "updated_by",
                    "update_at",
                ]
            )
            applied.append(plugin_key)

    logger.info(
        "AI 自动分类落位完成: space_id=%s, request_id=%s, applied=%s, skipped=%s",
        space_id,
        request_id,
        len(applied),
        len(skipped),
    )
    return {"applied": applied, "skipped": skipped}
