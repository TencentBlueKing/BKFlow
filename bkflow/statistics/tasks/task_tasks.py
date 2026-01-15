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
def task_created_statistics_task(self, task_id: int):
    """
    任务创建后的统计任务

    采集内容：
    - TaskflowStatistics: 任务基本信息
    """
    if not StatisticsConfig.is_enabled():
        logger.debug("[task_statistics] Statistics is disabled")
        return

    try:
        from bkflow.statistics.collectors import TaskStatisticsCollector

        collector = TaskStatisticsCollector(task_id=task_id)
        result = collector.collect_on_create()
        if result:
            logger.info(f"[task_statistics] task_id={task_id} created stats collected")
        else:
            logger.debug(f"[task_statistics] task_id={task_id} skipped or failed")
    except Exception as e:
        logger.exception(f"[task_statistics] task_id={task_id} error: {e}")


@shared_task(bind=True, ignore_result=True)
def task_archive_statistics_task(self, instance_id: str):
    """
    任务归档统计任务（完成/撤销后触发）

    采集内容：
    - TaskflowStatistics: 更新执行信息
    - TaskflowExecutedNodeStatistics: 节点执行详情
    """
    if not StatisticsConfig.is_enabled():
        logger.debug("[task_statistics] Statistics is disabled")
        return

    try:
        from bkflow.statistics.collectors import TaskStatisticsCollector

        collector = TaskStatisticsCollector(instance_id=instance_id)
        result = collector.collect_on_archive()
        if result:
            logger.info(f"[task_statistics] instance_id={instance_id} archive stats collected")
        else:
            logger.warning(f"[task_statistics] instance_id={instance_id} archive collection failed")
    except Exception as e:
        logger.exception(f"[task_statistics] instance_id={instance_id} error: {e}")
