import logging

from celery import shared_task

from bkflow.statistics.conf import StatisticsSettings

logger = logging.getLogger("celery")


@shared_task(bind=True, ignore_result=True)
def template_post_save_statistics_task(
    self, template_id: int, old_snapshot_id: int = None, new_snapshot_id: int = None
):
    if not StatisticsSettings.is_enabled():
        return

    try:
        from bkflow.statistics.collectors import TemplateStatisticsCollector

        collector = TemplateStatisticsCollector(template_id=template_id, snapshot_id=new_snapshot_id)

        if old_snapshot_id is not None and old_snapshot_id == new_snapshot_id:
            collector.collect_meta_only()
            logger.info(f"[template_statistics] template_id={template_id} meta updated (snapshot unchanged)")
        else:
            result = collector.collect()
            if result:
                logger.info(f"[template_statistics] template_id={template_id} collected successfully")
            else:
                logger.warning(f"[template_statistics] template_id={template_id} collection failed")
    except Exception as e:
        logger.exception(f"[template_statistics] template_id={template_id} error: {e}")
