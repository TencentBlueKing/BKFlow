import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from bkflow.statistics.conf import StatisticsSettings

logger = logging.getLogger("celery")

_signals_registered = False


def register_statistics_signals():
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
    try:
        from bkflow.template.models import Template

        @receiver(pre_save, sender=Template, dispatch_uid="template_statistics_pre_save")
        def template_pre_save_handler(sender, instance, **kwargs):
            if instance.pk:
                try:
                    old = Template.objects.filter(pk=instance.pk).values_list("snapshot_id", flat=True).first()
                    instance._pre_save_snapshot_id = old
                except Exception:
                    instance._pre_save_snapshot_id = None
            else:
                instance._pre_save_snapshot_id = None

        @receiver(post_save, sender=Template, dispatch_uid="template_statistics_post_save")
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
    try:
        from bkflow.task.models import TaskInstance

        @receiver(post_save, sender=TaskInstance, dispatch_uid="task_statistics_post_save")
        def task_post_save_handler(sender, instance, created, **kwargs):
            if created:
                try:
                    from bkflow.statistics.tasks import task_created_statistics_task

                    task_created_statistics_task.delay(task_id=instance.id)
                except Exception as e:
                    logger.exception(f"[task_post_save_handler] task_id={instance.id} error: {e}")

        try:
            from pipeline.eri.signals import post_set_state

            @receiver(post_set_state, dispatch_uid="task_statistics_state_change")
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
