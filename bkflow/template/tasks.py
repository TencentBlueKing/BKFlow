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
    if not getattr(settings, "AUTO_SAVE_SNAPSHOT_CLEAN_ENABLED", True):
        logger.info("[clean_expired_auto_save_snapshots] skipped, AUTO_SAVE_SNAPSHOT_CLEAN_ENABLED is False")
        return

    retention_days = getattr(settings, "AUTO_SAVE_SNAPSHOT_RETENTION_DAYS")
    expired_time = timezone.now() - timezone.timedelta(days=retention_days)

    logger.info(
        "[clean_expired_auto_save_snapshots] start, retention_days=%s, expired_before=%s", retention_days, expired_time
    )

    deleted_count, _ = TemplateSnapshot.objects.filter(
        auto_save=True,
        is_deleted=False,
        create_time__lt=expired_time,
    ).delete()

    logger.info("[clean_expired_auto_save_snapshots] done, deleted_count=%s", deleted_count)
    return deleted_count
