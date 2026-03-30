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

from bamboo_engine import states as bamboo_states
from celery import shared_task
from django.db.models import Avg, Count, Max, Q

from bkflow.statistics.conf import StatisticsSettings, date_to_datetime_range
from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateStatistics,
)

logger = logging.getLogger("celery")


@shared_task(bind=True, ignore_result=True)
def generate_daily_summary_task(self, target_date: str = None):
    """按天汇总各空间的任务和节点执行统计，默认汇总前一天的数据"""
    if not StatisticsSettings.is_enabled():
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
    db_alias = StatisticsSettings.get_db_alias()
    day_start, day_end = date_to_datetime_range(summary_date)

    task_stats = (
        TaskflowStatistics.objects.using(db_alias)
        .filter(create_time__gte=day_start, create_time__lt=day_end)
        .values("space_id", "scope_type", "scope_value")
        .annotate(
            task_created=Count("id"),
            task_finished=Count("id", filter=Q(is_finished=True)),
            task_success=Count("id", filter=Q(final_state=bamboo_states.FINISHED)),
            task_failed=Count("id", filter=Q(is_finished=True) & ~Q(final_state=bamboo_states.FINISHED)),
            task_revoked=Count("id", filter=Q(final_state=bamboo_states.REVOKED)),
            avg_elapsed=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
            max_elapsed=Max("elapsed_time"),
        )
    )

    node_stats_by_space = {}
    for ns in (
        TaskflowExecutedNodeStatistics.objects.using(db_alias)
        .filter(started_time__gte=day_start, started_time__lt=day_end, is_retry=False)
        .values("space_id")
        .annotate(
            node_executed=Count("id"),
            node_success=Count("id", filter=Q(status=True)),
            node_failed=Count("id", filter=Q(status=False)),
        )
    ):
        node_stats_by_space[ns["space_id"]] = ns

    processed_spaces = set()

    for stat in task_stats:
        space_id = stat["space_id"]
        node_stats = node_stats_by_space.get(space_id, {})
        space_key = (space_id, stat["scope_type"] or "", stat["scope_value"] or "")

        is_first_scope_for_space = space_id not in {k[0] for k in processed_spaces}
        processed_spaces.add(space_key)

        DailyStatisticsSummary.objects.using(db_alias).update_or_create(
            date=summary_date,
            space_id=space_id,
            scope_type=stat["scope_type"] or "",
            scope_value=stat["scope_value"] or "",
            defaults={
                "task_created_count": stat["task_created"],
                "task_finished_count": stat["task_finished"],
                "task_success_count": stat["task_success"],
                "task_failed_count": stat["task_failed"],
                "task_revoked_count": stat["task_revoked"],
                "avg_task_elapsed_time": stat["avg_elapsed"] or 0,
                "max_task_elapsed_time": stat["max_elapsed"] or 0,
                "node_executed_count": (node_stats.get("node_executed") or 0) if is_first_scope_for_space else 0,
                "node_success_count": (node_stats.get("node_success") or 0) if is_first_scope_for_space else 0,
                "node_failed_count": (node_stats.get("node_failed") or 0) if is_first_scope_for_space else 0,
            },
        )

    # 为当天没有任务的活跃空间填充零值记录，确保趋势图数据连续
    active_spaces = (
        TemplateStatistics.objects.using(db_alias).values_list("space_id", "scope_type", "scope_value").distinct()
    )

    for space_id, scope_type, scope_value in active_spaces:
        space_key = (space_id, scope_type or "", scope_value or "")
        if space_key not in processed_spaces:
            DailyStatisticsSummary.objects.using(db_alias).get_or_create(
                date=summary_date,
                space_id=space_id,
                scope_type=scope_type or "",
                scope_value=scope_value or "",
            )


@shared_task(bind=True, ignore_result=True)
def generate_plugin_summary_task(self, period_type: str = "day", target_date: str = None):
    """按指定周期（day/week/month）汇总各插件的执行次数、成功率和耗时"""
    if not StatisticsSettings.is_enabled():
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
    db_alias = StatisticsSettings.get_db_alias()

    if period_type == "day":
        period_end_date = period_start + timedelta(days=1)
    elif period_type == "week":
        period_end_date = period_start + timedelta(weeks=1)
    else:
        period_end_date = period_start + timedelta(days=30)

    range_start, _ = date_to_datetime_range(period_start)
    _, range_end = date_to_datetime_range(period_end_date - timedelta(days=1))

    node_stats = (
        TaskflowExecutedNodeStatistics.objects.using(db_alias)
        .filter(started_time__gte=range_start, started_time__lt=range_end, is_retry=False)
        .values("space_id", "component_code", "version", "plugin_type")
        .annotate(
            execution=Count("id"),
            success=Count("id", filter=Q(status=True)),
            failed=Count("id", filter=Q(status=False)),
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
                "plugin_type": stat["plugin_type"],
                "execution_count": stat["execution"],
                "success_count": stat["success"],
                "failed_count": stat["failed"],
                "avg_elapsed_time": stat["avg_elapsed"] or 0,
                "max_elapsed_time": stat["max_elapsed"] or 0,
            },
        )


@shared_task(bind=True, ignore_result=True)
def clean_expired_statistics_task(self):
    """清理过期统计数据，明细和汇总分别按各自的保留天数清理"""
    if not StatisticsSettings.is_enabled():
        return

    detail_days = StatisticsSettings.get_detail_retention_days()
    summary_days = StatisticsSettings.get_summary_retention_days()
    db_alias = StatisticsSettings.get_db_alias()

    try:
        if detail_days > 0:
            detail_cutoff = date.today() - timedelta(days=detail_days)
            cutoff_start, _ = date_to_datetime_range(detail_cutoff)
            d1, _ = (
                TaskflowExecutedNodeStatistics.objects.using(db_alias).filter(started_time__lt=cutoff_start).delete()
            )
            d2, _ = TaskflowStatistics.objects.using(db_alias).filter(create_time__lt=cutoff_start).delete()
            logger.info(f"[clean_statistics] Detail cleaned: nodes={d1}, tasks={d2}")

        if summary_days > 0:
            summary_cutoff = date.today() - timedelta(days=summary_days)
            d3, _ = DailyStatisticsSummary.objects.using(db_alias).filter(date__lt=summary_cutoff).delete()
            d4, _ = PluginExecutionSummary.objects.using(db_alias).filter(period_start__lt=summary_cutoff).delete()
            logger.info(f"[clean_statistics] Summary cleaned: daily={d3}, plugin={d4}")
    except Exception as e:
        logger.exception(f"[clean_statistics] error: {e}")
