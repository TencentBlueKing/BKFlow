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

from bkflow.statistics.conf import StatisticsConfig

logger = logging.getLogger("celery")


@shared_task(bind=True, ignore_result=True)
def template_post_save_statistics_task(self, template_id: int):
    """
    模板保存后的统计任务

    采集内容：
    - TemplateNodeStatistics: 模板节点引用统计
    - TemplateStatistics: 模板整体统计
    """
    if not StatisticsConfig.is_enabled():
        logger.debug("[template_statistics] Statistics is disabled")
        return

    try:
        from bkflow.statistics.collectors import TemplateStatisticsCollector

        collector = TemplateStatisticsCollector(template_id=template_id)
        result = collector.collect()
        if result:
            logger.info(f"[template_statistics] template_id={template_id} collected successfully")
        else:
            logger.warning(f"[template_statistics] template_id={template_id} collection failed")
    except Exception as e:
        logger.exception(f"[template_statistics] template_id={template_id} error: {e}")
