"""统计模块的 Django 信号处理器

根据模块类型注册不同的信号：
- interface 模块：监听 Template 的 pre_save/post_save，在模板保存时异步采集模板统计
- engine 模块：监听 TaskInstance 的 post_save（任务创建时采集）和 post_set_state（任务归档时采集）

信号注册是幂等的，通过 _signals_registered 标志确保只注册一次。
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from bkflow.statistics.conf import StatisticsSettings

logger = logging.getLogger("celery")

_signals_registered = False


def register_statistics_signals():
    """根据当前模块类型注册对应的统计信号，幂等调用"""
    global _signals_registered
    if _signals_registered:
        return

    if not StatisticsSettings.is_enabled():
        logger.info("[Statistics] Statistics is disabled, skip signal registration")
        return

    if StatisticsSettings.should_collect_template_stats():
        _register_template_signals()
        logger.info("[Statistics] Template statistics signals registered")

    if StatisticsSettings.should_collect_task_stats():
        _register_task_signals()
        logger.info("[Statistics] Task statistics signals registered")

    _signals_registered = True


def _register_template_signals():
    """注册模板相关的统计信号

    pre_save: 记录保存前的 snapshot_id，用于 post_save 时判断 pipeline 结构是否变化
    post_save: 异步触发模板统计采集任务
    """
    try:
        from bkflow.template.models import Template

        @receiver(pre_save, sender=Template, dispatch_uid="template_statistics_pre_save", weak=False)
        def template_pre_save_handler(sender, instance, **kwargs):
            if instance.pk:
                try:
                    old = Template.objects.filter(pk=instance.pk).values_list("snapshot_id", flat=True).first()
                    instance._pre_save_snapshot_id = old
                except Exception:
                    instance._pre_save_snapshot_id = None
            else:
                instance._pre_save_snapshot_id = None

        @receiver(post_save, sender=Template, dispatch_uid="template_statistics_post_save", weak=False)
        def template_post_save_handler(sender, instance, created, **kwargs):
            try:
                from bkflow.statistics.tasks import template_post_save_statistics_task

                old_snapshot_id = getattr(instance, "_pre_save_snapshot_id", None)
                template_post_save_statistics_task.delay(
                    template_id=instance.id,
                    old_snapshot_id=old_snapshot_id,
                    new_snapshot_id=instance.snapshot_id,
                )
            except Exception as e:
                logger.exception(f"[template_post_save_handler] template_id={instance.id} error: {e}")

    except ImportError as e:
        logger.warning(f"[Statistics] Cannot register template signals: {e}")


def _register_task_signals():
    """注册任务相关的统计信号

    post_save: 任务创建时触发统计采集
    post_set_state: 任务进入终态（FINISHED/REVOKED）时触发归档统计采集
    """
    try:
        from bkflow.task.models import TaskInstance

        @receiver(post_save, sender=TaskInstance, dispatch_uid="task_statistics_post_save", weak=False)
        def task_post_save_handler(sender, instance, created, **kwargs):
            if created:
                try:
                    from bkflow.statistics.tasks import task_created_statistics_task

                    task_created_statistics_task.delay(task_id=instance.id)
                except Exception as e:
                    logger.exception(f"[task_post_save_handler] task_id={instance.id} error: {e}")

        try:
            from pipeline.eri.signals import post_set_state

            @receiver(post_set_state, dispatch_uid="task_statistics_state_change", weak=False)
            def task_state_change_handler(sender, node_id, to_state, version, root_id, **kwargs):
                if node_id == root_id and to_state in ("FINISHED", "REVOKED"):
                    try:
                        from bkflow.statistics.tasks import task_archive_statistics_task

                        task_archive_statistics_task.delay(instance_id=root_id)
                    except Exception as e:
                        logger.exception(f"[task_state_change_handler] instance_id={root_id} error: {e}")

        except ImportError as e:
            logger.warning(f"[Statistics] Cannot register pipeline state signals: {e}")

    except ImportError as e:
        logger.warning(f"[Statistics] Cannot register task signals: {e}")
