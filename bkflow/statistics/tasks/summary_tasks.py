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
from datetime import date, timedelta

from celery import shared_task
from django.db.models import Avg, Count, Max, Q, Sum

from bkflow.statistics.conf import StatisticsConfig
from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
)

logger = logging.getLogger("celery")


@shared_task(bind=True, ignore_result=True)
def generate_daily_summary_task(self, target_date: str = None):
    """
    生成每日统计汇总

    Args:
        target_date: 目标日期（YYYY-MM-DD），默认为昨天
    """
    if not StatisticsConfig.is_enabled():
        logger.debug("[daily_summary] Statistics is disabled")
        return

    if target_date:
        summary_date = date.fromisoformat(target_date)
    else:
        summary_date = date.today() - timedelta(days=1)

    try:
        _generate_daily_summary(summary_date)
        logger.info(f"[daily_summary] date={summary_date} generated successfully")
    except Exception as e:
        logger.exception(f"[daily_summary] date={summary_date} error: {e}")


def _generate_daily_summary(summary_date: date):
    """生成指定日期的汇总数据"""
    db_alias = StatisticsConfig.get_db_alias()

    # 按 space_id + scope 分组统计
    task_stats = (
        TaskflowStatistics.objects.using(db_alias)
        .filter(create_time__date=summary_date)
        .values("space_id", "scope_type", "scope_value")
        .annotate(
            task_created=Count("id"),
            task_started=Count("id", filter=Q(is_started=True)),
            task_finished=Count("id", filter=Q(is_finished=True)),
            task_success=Count("id", filter=Q(is_success=True)),
            task_failed=Count("id", filter=Q(is_finished=True, is_success=False)),
            task_revoked=Count("id", filter=Q(final_state="REVOKED")),
            avg_elapsed=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
            max_elapsed=Max("elapsed_time"),
            total_elapsed=Sum("elapsed_time", filter=Q(elapsed_time__isnull=False)),
        )
    )

    for stat in task_stats:
        # 获取节点统计
        node_stats = (
            TaskflowExecutedNodeStatistics.objects.using(db_alias)
            .filter(
                space_id=stat["space_id"],
                scope_type=stat["scope_type"],
                scope_value=stat["scope_value"],
                started_time__date=summary_date,
            )
            .aggregate(
                node_executed=Count("id", filter=Q(is_retry=False)),
                node_success=Count("id", filter=Q(status=True, is_retry=False)),
                node_failed=Count("id", filter=Q(status=False, is_retry=False)),
                node_retry=Count("id", filter=Q(is_retry=True)),
            )
        )

        DailyStatisticsSummary.objects.using(db_alias).update_or_create(
            date=summary_date,
            space_id=stat["space_id"],
            scope_type=stat["scope_type"] or "",
            scope_value=stat["scope_value"] or "",
            defaults={
                "task_created_count": stat["task_created"],
                "task_started_count": stat["task_started"],
                "task_finished_count": stat["task_finished"],
                "task_success_count": stat["task_success"],
                "task_failed_count": stat["task_failed"],
                "task_revoked_count": stat["task_revoked"],
                "avg_task_elapsed_time": stat["avg_elapsed"] or 0,
                "max_task_elapsed_time": stat["max_elapsed"] or 0,
                "total_task_elapsed_time": stat["total_elapsed"] or 0,
                "node_executed_count": node_stats["node_executed"] or 0,
                "node_success_count": node_stats["node_success"] or 0,
                "node_failed_count": node_stats["node_failed"] or 0,
                "node_retry_count": node_stats["node_retry"] or 0,
            },
        )


@shared_task(bind=True, ignore_result=True)
def generate_plugin_summary_task(self, period_type: str = "day", target_date: str = None):
    """
    生成插件执行汇总

    Args:
        period_type: 周期类型（day/week/month）
        target_date: 周期开始日期
    """
    if not StatisticsConfig.is_enabled():
        logger.debug("[plugin_summary] Statistics is disabled")
        return

    if target_date:
        period_start = date.fromisoformat(target_date)
    else:
        period_start = date.today() - timedelta(days=1)

    try:
        _generate_plugin_summary(period_type, period_start)
        logger.info(f"[plugin_summary] {period_type}={period_start} generated successfully")
    except Exception as e:
        logger.exception(f"[plugin_summary] {period_type}={period_start} error: {e}")


def _generate_plugin_summary(period_type: str, period_start: date):
    """生成插件执行汇总"""
    db_alias = StatisticsConfig.get_db_alias()

    # 确定时间范围
    if period_type == "day":
        period_end = period_start + timedelta(days=1)
    elif period_type == "week":
        period_end = period_start + timedelta(weeks=1)
    else:  # month
        period_end = period_start + timedelta(days=30)

    # 按 space_id + component_code + version 分组统计
    node_stats = (
        TaskflowExecutedNodeStatistics.objects.using(db_alias)
        .filter(started_time__date__gte=period_start, started_time__date__lt=period_end)
        .values("space_id", "component_code", "version", "is_remote")
        .annotate(
            execution=Count("id"),
            success=Count("id", filter=Q(status=True)),
            failed=Count("id", filter=Q(status=False)),
            retry=Count("id", filter=Q(is_retry=True)),
            timeout=Count("id", filter=Q(is_timeout=True)),
            avg_elapsed=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
            max_elapsed=Max("elapsed_time"),
        )
    )

    for stat in node_stats:
        PluginExecutionSummary.objects.using(db_alias).update_or_create(
            period_type=period_type,
            period_start=period_start,
            space_id=stat["space_id"],
            component_code=stat["component_code"],
            version=stat["version"],
            defaults={
                "is_remote": stat["is_remote"],
                "execution_count": stat["execution"],
                "success_count": stat["success"],
                "failed_count": stat["failed"],
                "retry_count": stat["retry"],
                "timeout_count": stat["timeout"],
                "avg_elapsed_time": stat["avg_elapsed"] or 0,
                "max_elapsed_time": stat["max_elapsed"] or 0,
            },
        )


@shared_task(bind=True, ignore_result=True)
def clean_expired_statistics_task(self):
    """清理过期统计数据"""
    if not StatisticsConfig.is_enabled():
        return

    retention_days = StatisticsConfig.get_retention_days()
    if retention_days <= 0:
        logger.info("[clean_statistics] Retention days is 0, skip cleanup")
        return

    db_alias = StatisticsConfig.get_db_alias()
    cutoff_date = date.today() - timedelta(days=retention_days)

    try:
        # 清理节点执行统计
        deleted_nodes, _ = (
            TaskflowExecutedNodeStatistics.objects.using(db_alias).filter(started_time__date__lt=cutoff_date).delete()
        )

        # 清理每日汇总
        deleted_daily, _ = DailyStatisticsSummary.objects.using(db_alias).filter(date__lt=cutoff_date).delete()

        # 清理插件汇总
        deleted_plugin, _ = PluginExecutionSummary.objects.using(db_alias).filter(period_start__lt=cutoff_date).delete()

        logger.info(
            f"[clean_statistics] Cleaned: nodes={deleted_nodes}, daily={deleted_daily}, plugin={deleted_plugin}"
        )
    except Exception as e:
        logger.exception(f"[clean_statistics] error: {e}")
