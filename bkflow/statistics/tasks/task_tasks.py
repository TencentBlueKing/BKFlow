import logging

from celery import shared_task

from bkflow.statistics.conf import StatisticsSettings

logger = logging.getLogger("celery")


@shared_task(bind=True, ignore_result=True)
def task_created_statistics_task(self, task_id: int):
    if not StatisticsSettings.is_enabled():
        return

    try:
        from bkflow.statistics.collectors import TaskStatisticsCollector

        collector = TaskStatisticsCollector(task_id=task_id)
        result = collector.collect_on_create()
        if result:
            logger.info(f"[task_statistics] task_id={task_id} created stats collected")
    except Exception as e:
        logger.exception(f"[task_statistics] task_id={task_id} error: {e}")


@shared_task(bind=True, ignore_result=True)
def task_archive_statistics_task(self, instance_id: str):
    if not StatisticsSettings.is_enabled():
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
