"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import logging

from celery import shared_task
from django.conf import settings

from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService

logger = logging.getLogger("celery")

SYNC_REQUEST_TIMEOUT = settings.OPEN_PLUGIN_CATALOG_SYNC_REQUEST_TIMEOUT


@shared_task(
    ignore_result=True,
    max_retries=0,
    rate_limit="10/m",
    soft_time_limit=SYNC_REQUEST_TIMEOUT + 60,
    time_limit=SYNC_REQUEST_TIMEOUT + 90,
)
def sync_open_plugin_catalog_source(space_id, source_key):
    """同步单个空间来源，失败由 Celery 独立记录且不自动重试。"""
    try:
        return OpenPluginCatalogService.sync_space_plugins(space_id=space_id, source_key=source_key)
    except Exception:
        logger.exception(
            "开放插件目录同步失败: space_id=%s, source_key=%s",
            space_id,
            source_key,
        )
        raise


@shared_task(ignore_result=True)
def dispatch_open_plugin_catalog_sync():
    """为已配置的开放插件来源分别投递同步任务。"""
    sync_sources = sorted(set(OpenPluginCatalogService.iter_configured_sources()))

    for space_id, source_key in sync_sources:
        sync_open_plugin_catalog_source.delay(space_id=space_id, source_key=source_key)

    logger.info("开放插件目录同步任务已投递: source_count=%s", len(sync_sources))
    return len(sync_sources)
