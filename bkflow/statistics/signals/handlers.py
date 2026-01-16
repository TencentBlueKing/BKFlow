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

from django.db.models.signals import post_save
from django.dispatch import receiver

from bkflow.statistics.conf import StatisticsConfig

logger = logging.getLogger("celery")

# 标记信号是否已注册
_signals_registered = False


def register_statistics_signals():
    """
    根据模块类型注册统计信号
    在 apps.py 的 ready() 方法中调用
    """
    global _signals_registered
    if _signals_registered:
        return

    if not StatisticsConfig.is_enabled():
        logger.info("[Statistics] Statistics is disabled, skip signal registration")
        return

    if StatisticsConfig.should_collect_template_stats():
        _register_template_signals()
        logger.info("[Statistics] Template statistics signals registered")

    if StatisticsConfig.should_collect_task_stats():
        _register_task_signals()
        logger.info("[Statistics] Task statistics signals registered")

    _signals_registered = True


def _register_template_signals():
    """注册模板统计信号（Interface 模块）"""
    try:
        from bkflow.template.models import Template

        @receiver(post_save, sender=Template, dispatch_uid="template_statistics_post_save")
        def template_post_save_handler(sender, instance, created, **kwargs):
            """模板保存后触发统计"""
            try:
                from bkflow.statistics.tasks import template_post_save_statistics_task

                template_post_save_statistics_task.delay(template_id=instance.id)
            except Exception as e:
                logger.exception(f"[template_post_save_handler] template_id={instance.id} error: {e}")

    except ImportError as e:
        logger.warning(f"[Statistics] Cannot register template signals: {e}")


def _register_task_signals():
    """注册任务统计信号（Engine 模块）"""
    try:
        from bkflow.task.models import TaskInstance

        @receiver(post_save, sender=TaskInstance, dispatch_uid="task_statistics_post_save")
        def task_post_save_handler(sender, instance, created, **kwargs):
            """任务创建后触发统计"""
            if created:
                try:
                    from bkflow.statistics.tasks import task_created_statistics_task

                    task_created_statistics_task.delay(task_id=instance.id)
                except Exception as e:
                    logger.exception(f"[task_post_save_handler] task_id={instance.id} error: {e}")

        # 注册 pipeline 状态变更信号
        try:
            from bamboo_engine import states as bamboo_engine_states
            from pipeline.eri.signals import post_set_state

            @receiver(post_set_state, dispatch_uid="task_statistics_state_change")
            def task_state_change_handler(sender, node_id, to_state, version, root_id, **kwargs):
                """任务状态变更时触发统计"""
                # 只在任务完成或撤销时采集执行统计
                if node_id == root_id and to_state in (
                    bamboo_engine_states.FINISHED,
                    bamboo_engine_states.REVOKED,
                ):
                    try:
                        from bkflow.statistics.tasks import task_archive_statistics_task

                        task_archive_statistics_task.delay(instance_id=root_id)
                    except Exception as e:
                        logger.exception(f"[task_state_change_handler] instance_id={root_id} error: {e}")

        except ImportError as e:
            logger.warning(f"[Statistics] Cannot register pipeline state signals: {e}")

    except ImportError as e:
        logger.warning(f"[Statistics] Cannot register task signals: {e}")
