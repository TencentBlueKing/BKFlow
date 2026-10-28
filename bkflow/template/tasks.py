"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

import logging

from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone

from bkflow.template.models import TemplateSnapshot

logger = logging.getLogger("celery")


@periodic_task(run_every=crontab(*settings.AUTO_SAVE_SNAPSHOT_CLEAN_INTERVAL))
def clean_expired_auto_save_snapshots():
    """清理超过保留天数的自动保存快照"""
    if not getattr(settings, "AUTO_SAVE_SNAPSHOT_CLEAN_ENABLED", False):
        logger.info("[clean_expired_auto_save_snapshots] skipped, AUTO_SAVE_SNAPSHOT_CLEAN_ENABLED is False")
        return

    retention_days = getattr(settings, "AUTO_SAVE_SNAPSHOT_RETENTION_DAYS")
    expired_time = timezone.now() - timezone.timedelta(days=retention_days)

    logger.info(
        "[clean_expired_auto_save_snapshots] start, retention_days=%s, expired_before=%s", retention_days, expired_time
    )

    # 以模板为单位遍历处理：每个模板保留最新一条（id 最大）自动保存快照，删其余过期的。
    # 先一次性取出所有未软删的 auto_save 快照（仅取必要字段），在内存中按 template_id 分组，
    # 既保证了「逐模板操作」的清晰语义与可调试性，又将查询次数控制在 2 条 SQL
    # 语义示例：模板1共3条 -> 保留最新1条、删2条；模板2共4条 -> 保留最新1条、删3条。
    snapshots = TemplateSnapshot.objects.filter(
        auto_save=True, is_deleted=False, template_id__isnull=False
    ).values_list("template_id", "id", "create_time")

    # 按模板分组：(template_id -> [(snap_id, create_time), ...])
    grouped = {}
    for template_id, snap_id, create_time in snapshots:
        grouped.setdefault(template_id, []).append((snap_id, create_time))

    expired_ids = []
    for template_id, items in grouped.items():
        # 按 id 升序排序，最新一条（id 最大）保留
        items.sort(key=lambda x: x[0])
        latest_id = items[-1][0]
        # 其余已过期的收集待删
        template_expired_ids = [sid for sid, ctime in items if sid != latest_id and ctime < expired_time]
        if template_expired_ids:
            expired_ids.extend(template_expired_ids)
            logger.info(
                "[clean_expired_auto_save_snapshots] template_id=%s, expired_to_delete=%s",
                template_id,
                len(template_expired_ids),
            )

    deleted_count = 0
    if expired_ids:
        deleted_count, _ = TemplateSnapshot.objects.filter(id__in=expired_ids).delete()

    logger.info("[clean_expired_auto_save_snapshots] done, deleted_count=%s", deleted_count)
    return deleted_count
