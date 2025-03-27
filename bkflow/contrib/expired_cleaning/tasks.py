import logging
from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .utils import delete_expired_data

logger = logging.getLogger("celery")


@shared_task
def clean_task():
    if not settings.ENABLE_CLEAN_TASK:
        logger.info("未开启清理任务 退出....")
        return
    logger.info("清理任务开始...")
    previous_execute_time, current_execute_time = None, None
    current_execute_time = datetime.utcnow()
    previous_execute_time = current_execute_time - timezone.timedelta(days=settings.CLEAN_TASK_EXPIRED_DAYS)
    logger.info(f"删除周期 {previous_execute_time} - {current_execute_time}")
    delete_expired_data(previous_execute_time, current_execute_time)
