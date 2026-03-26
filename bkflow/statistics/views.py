"""运营统计 API 视图

提供两组 ViewSet：
- SystemStatisticsViewSet: 全局维度的统计接口（概览、任务趋势、空间排名、插件排名、失败分析）
- SpaceStatisticsViewSet: 空间维度的统计接口（概览、任务趋势、插件排名、模板排名、失败分析、每日汇总）

所有接口支持 date_start/date_end 或 date_range（7d/14d/30d/90d）参数指定查询时间范围。
"""

import logging
from datetime import date, timedelta

from django.db.models import Avg, Count, Q, Sum
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkflow.statistics.conf import StatisticsSettings
from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateStatistics,
)
from bkflow.statistics.serializers import (
    DailyStatisticsSummarySerializer,
    DateRangeParamSerializer,
    FailureAnalysisSerializer,
    PluginRankingSerializer,
    SpaceRankingSerializer,
    StatisticsOverviewSerializer,
    TaskTrendSerializer,
    TemplateRankingSerializer,
)
from bkflow.utils.permissions import AdminPermission, AppInternalPermission

logger = logging.getLogger("root")

DATE_RANGE_MAP = {
    "7d": 7,
    "14d": 14,
    "30d": 30,
    "90d": 90,
}


def _get_date_range(request):
    """从请求参数中解析日期范围，支持 date_start/date_end 或 date_range 快捷方式"""
    param_ser = DateRangeParamSerializer(data=request.query_params)
    param_ser.is_valid(raise_exception=True)

    date_start = param_ser.validated_data.get("date_start")
    date_end = param_ser.validated_data.get("date_end")
    date_range = param_ser.validated_data.get("date_range")

    if date_range:
        days = DATE_RANGE_MAP.get(date_range, 7)
        date_end = date.today()
        date_start = date_end - timedelta(days=days)

    if not date_end:
        date_end = date.today()

    return date_start, date_end


def _validate_order_by(value, allowed):
    """校验排序字段是否在允许列表中，不合法时回退到默认字段"""
    if not value:
        return allowed[0] if allowed else "id"
    clean = value.lstrip("-")
    if clean not in allowed:
        return allowed[0] if allowed else "id"
    return value


def _get_limit(request, max_val=100):
    """从请求参数获取分页限制，约束在 [1, max_val] 范围内"""
    try:
        limit = int(request.query_params.get("limit", 10))
    except (ValueError, TypeError):
        limit = 10
    return min(max(limit, 1), max_val)


class SystemStatisticsViewSet(GenericViewSet):
    """全局维度的运营统计接口，需要管理员或内部应用权限"""

    permission_classes = [AdminPermission | AppInternalPermission]

    @action(methods=["get"], detail=False, url_path="overview")
    def overview(self, request):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()

        total_templates = TemplateStatistics.objects.using(db_alias).count()

        task_qs = TaskflowStatistics.objects.using(db_alias).filter(
            create_time__date__gte=date_start, create_time__date__lte=date_end
        )
        task_agg = task_qs.aggregate(
            total_tasks=Count("id"),
            total_finished=Count("id", filter=Q(is_finished=True)),
            total_failed=Count("id", filter=Q(is_finished=True) & ~Q(final_state="FINISHED")),
            avg_elapsed=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
        )

        node_agg = (
            TaskflowExecutedNodeStatistics.objects.using(db_alias)
            .filter(
                started_time__date__gte=date_start,
                started_time__date__lte=date_end,
                is_retry=False,
            )
            .aggregate(total_nodes=Count("id"))
        )

        total_tasks = task_agg["total_tasks"] or 0
        total_finished = task_agg["total_finished"] or 0
        total_failed = task_agg["total_failed"] or 0
        success_rate = ((total_finished - total_failed) / total_finished * 100) if total_finished > 0 else 0

        data = {
            "total_templates": total_templates,
            "total_tasks": total_tasks,
            "total_tasks_finished": total_finished,
            "total_tasks_failed": total_failed,
            "total_nodes_executed": node_agg["total_nodes"] or 0,
            "avg_task_elapsed_time": round(task_agg["avg_elapsed"] or 0, 2),
            "success_rate": round(success_rate, 2),
        }
        return Response(StatisticsOverviewSerializer(data).data)

    @action(methods=["get"], detail=False, url_path="task-trend")
    def task_trend(self, request):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()

        summaries = (
            DailyStatisticsSummary.objects.using(db_alias)
            .filter(date__gte=date_start, date__lte=date_end)
            .values("date")
            .annotate(
                task_created_count=Sum("task_created_count"),
                task_finished_count=Sum("task_finished_count"),
                task_success_count=Sum("task_success_count"),
                task_failed_count=Sum("task_failed_count"),
                task_revoked_count=Sum("task_revoked_count"),
                node_executed_count=Sum("node_executed_count"),
                avg_task_elapsed_time=Avg("avg_task_elapsed_time"),
            )
            .order_by("date")
        )
        return Response(TaskTrendSerializer(summaries, many=True).data)

    @action(methods=["get"], detail=False, url_path="space-ranking")
    def space_ranking(self, request):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        limit = _get_limit(request)
        order_by = _validate_order_by(
            request.query_params.get("order_by"), ["total_tasks", "total_templates", "total_nodes_executed"]
        )

        template_counts = dict(
            TemplateStatistics.objects.using(db_alias)
            .values("space_id")
            .annotate(cnt=Count("id"))
            .values_list("space_id", "cnt")
        )

        summaries = (
            DailyStatisticsSummary.objects.using(db_alias)
            .filter(date__gte=date_start, date__lte=date_end)
            .values("space_id", "scope_type", "scope_value")
            .annotate(
                total_tasks=Sum("task_created_count"),
                total_success=Sum("task_success_count"),
                total_finished=Sum("task_finished_count"),
                total_nodes_executed=Sum("node_executed_count"),
            )
            .order_by(f"-{order_by.lstrip('-')}")[:limit]
        )

        result = []
        for s in summaries:
            total_finished = s["total_finished"] or 0
            total_success = s["total_success"] or 0
            sr = (total_success / total_finished * 100) if total_finished > 0 else 0
            result.append(
                {
                    "space_id": s["space_id"],
                    "scope_type": s["scope_type"],
                    "scope_value": s["scope_value"],
                    "total_templates": template_counts.get(s["space_id"], 0),
                    "total_tasks": s["total_tasks"] or 0,
                    "total_nodes_executed": s["total_nodes_executed"] or 0,
                    "success_rate": round(sr, 2),
                }
            )

        return Response(SpaceRankingSerializer(result, many=True).data)

    @action(methods=["get"], detail=False, url_path="plugin-ranking")
    def plugin_ranking(self, request):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        limit = _get_limit(request)
        order_by = _validate_order_by(
            request.query_params.get("order_by"), ["execution_count", "failed_count", "avg_elapsed_time"]
        )

        stats = (
            PluginExecutionSummary.objects.using(db_alias)
            .filter(period_type="day", period_start__gte=date_start, period_start__lte=date_end)
            .values("component_code", "version", "plugin_type")
            .annotate(
                execution_count=Sum("execution_count"),
                success_count=Sum("success_count"),
                failed_count=Sum("failed_count"),
                avg_elapsed_time=Avg("avg_elapsed_time"),
            )
            .order_by(f"-{order_by.lstrip('-')}")[:limit]
        )

        result = []
        for s in stats:
            ec = s["execution_count"] or 0
            sc = s["success_count"] or 0
            sr = (sc / ec * 100) if ec > 0 else 0
            result.append(
                {
                    **s,
                    "success_rate": round(sr, 2),
                }
            )

        return Response(PluginRankingSerializer(result, many=True).data)

    @action(methods=["get"], detail=False, url_path="failure-analysis")
    def failure_analysis(self, request):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        limit = _get_limit(request)

        stats = (
            TaskflowExecutedNodeStatistics.objects.using(db_alias)
            .filter(started_time__date__gte=date_start, started_time__date__lte=date_end, is_retry=False)
            .values("component_code", "version", "plugin_type")
            .annotate(
                total_count=Count("id"),
                failed_count=Count("id", filter=Q(status=False)),
                avg_elapsed_time=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
            )
            .filter(failed_count__gt=0)
            .order_by("-failed_count")[:limit]
        )

        result = []
        for s in stats:
            tc = s["total_count"] or 0
            fc = s["failed_count"] or 0
            fr = (fc / tc * 100) if tc > 0 else 0
            result.append(
                {
                    **s,
                    "failure_rate": round(fr, 2),
                }
            )

        return Response(FailureAnalysisSerializer(result, many=True).data)


class SpaceStatisticsViewSet(GenericViewSet):
    """空间维度的运营统计接口，按 space_id 过滤数据"""

    permission_classes = [AdminPermission | AppInternalPermission]

    def _get_space_id(self):
        return int(self.kwargs.get("space_id", 0))

    def _get_scope_filters(self, request):
        filters = {"space_id": self._get_space_id()}
        scope_type = request.query_params.get("scope_type", "")
        scope_value = request.query_params.get("scope_value", "")
        if scope_type:
            filters["scope_type"] = scope_type
        if scope_value:
            filters["scope_value"] = scope_value
        return filters

    @action(methods=["get"], detail=False, url_path="overview")
    def overview(self, request, **kwargs):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        scope_filters = self._get_scope_filters(request)

        total_templates = TemplateStatistics.objects.using(db_alias).filter(**scope_filters).count()

        task_qs = TaskflowStatistics.objects.using(db_alias).filter(
            create_time__date__gte=date_start,
            create_time__date__lte=date_end,
            **scope_filters,
        )
        task_agg = task_qs.aggregate(
            total_tasks=Count("id"),
            total_finished=Count("id", filter=Q(is_finished=True)),
            total_failed=Count("id", filter=Q(is_finished=True) & ~Q(final_state="FINISHED")),
            avg_elapsed=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
        )

        node_agg = (
            TaskflowExecutedNodeStatistics.objects.using(db_alias)
            .filter(
                started_time__date__gte=date_start,
                started_time__date__lte=date_end,
                space_id=self._get_space_id(),
                is_retry=False,
            )
            .aggregate(total_nodes=Count("id"))
        )

        total_tasks = task_agg["total_tasks"] or 0
        total_finished = task_agg["total_finished"] or 0
        total_failed = task_agg["total_failed"] or 0
        success_rate = ((total_finished - total_failed) / total_finished * 100) if total_finished > 0 else 0

        data = {
            "total_templates": total_templates,
            "total_tasks": total_tasks,
            "total_tasks_finished": total_finished,
            "total_tasks_failed": total_failed,
            "total_nodes_executed": node_agg["total_nodes"] or 0,
            "avg_task_elapsed_time": round(task_agg["avg_elapsed"] or 0, 2),
            "success_rate": round(success_rate, 2),
        }
        return Response(StatisticsOverviewSerializer(data).data)

    @action(methods=["get"], detail=False, url_path="task-trend")
    def task_trend(self, request, **kwargs):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        scope_filters = self._get_scope_filters(request)

        summaries = (
            DailyStatisticsSummary.objects.using(db_alias)
            .filter(date__gte=date_start, date__lte=date_end, **scope_filters)
            .values("date")
            .annotate(
                task_created_count=Sum("task_created_count"),
                task_finished_count=Sum("task_finished_count"),
                task_success_count=Sum("task_success_count"),
                task_failed_count=Sum("task_failed_count"),
                task_revoked_count=Sum("task_revoked_count"),
                node_executed_count=Sum("node_executed_count"),
                avg_task_elapsed_time=Avg("avg_task_elapsed_time"),
            )
            .order_by("date")
        )
        return Response(TaskTrendSerializer(summaries, many=True).data)

    @action(methods=["get"], detail=False, url_path="plugin-ranking")
    def plugin_ranking(self, request, **kwargs):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        space_id = self._get_space_id()
        limit = _get_limit(request)
        order_by = _validate_order_by(
            request.query_params.get("order_by"), ["execution_count", "failed_count", "avg_elapsed_time"]
        )

        stats = (
            PluginExecutionSummary.objects.using(db_alias)
            .filter(
                period_type="day",
                period_start__gte=date_start,
                period_start__lte=date_end,
                space_id=space_id,
            )
            .values("component_code", "version", "plugin_type")
            .annotate(
                execution_count=Sum("execution_count"),
                success_count=Sum("success_count"),
                failed_count=Sum("failed_count"),
                avg_elapsed_time=Avg("avg_elapsed_time"),
            )
            .order_by(f"-{order_by.lstrip('-')}")[:limit]
        )

        result = []
        for s in stats:
            ec = s["execution_count"] or 0
            sc = s["success_count"] or 0
            sr = (sc / ec * 100) if ec > 0 else 0
            result.append(
                {
                    **s,
                    "success_rate": round(sr, 2),
                }
            )

        return Response(PluginRankingSerializer(result, many=True).data)

    @action(methods=["get"], detail=False, url_path="template-ranking")
    def template_ranking(self, request, **kwargs):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        space_id = self._get_space_id()
        limit = _get_limit(request)
        order_by = _validate_order_by(request.query_params.get("order_by"), ["task_count", "task_failed_count"])

        stats = (
            TaskflowStatistics.objects.using(db_alias)
            .filter(
                create_time__date__gte=date_start,
                create_time__date__lte=date_end,
                space_id=space_id,
                template_id__isnull=False,
            )
            .values("template_id")
            .annotate(
                task_count=Count("id"),
                task_success_count=Count("id", filter=Q(final_state="FINISHED")),
                task_failed_count=Count("id", filter=Q(is_finished=True) & ~Q(final_state="FINISHED")),
            )
            .order_by(f"-{order_by.lstrip('-')}")[:limit]
        )

        template_names = dict(
            TemplateStatistics.objects.using(db_alias)
            .filter(space_id=space_id)
            .values_list("template_id", "template_name")
        )

        result = []
        for s in stats:
            result.append(
                {
                    "template_id": s["template_id"],
                    "template_name": template_names.get(s["template_id"], ""),
                    "space_id": space_id,
                    "task_count": s["task_count"],
                    "task_success_count": s["task_success_count"],
                    "task_failed_count": s["task_failed_count"],
                }
            )

        return Response(TemplateRankingSerializer(result, many=True).data)

    @action(methods=["get"], detail=False, url_path="failure-analysis")
    def failure_analysis(self, request, **kwargs):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        space_id = self._get_space_id()
        limit = _get_limit(request)

        stats = (
            TaskflowExecutedNodeStatistics.objects.using(db_alias)
            .filter(
                started_time__date__gte=date_start,
                started_time__date__lte=date_end,
                space_id=space_id,
                is_retry=False,
            )
            .values("component_code", "version", "plugin_type")
            .annotate(
                total_count=Count("id"),
                failed_count=Count("id", filter=Q(status=False)),
                avg_elapsed_time=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
            )
            .filter(failed_count__gt=0)
            .order_by("-failed_count")[:limit]
        )

        result = []
        for s in stats:
            tc = s["total_count"] or 0
            fc = s["failed_count"] or 0
            fr = (fc / tc * 100) if tc > 0 else 0
            result.append(
                {
                    **s,
                    "failure_rate": round(fr, 2),
                }
            )

        return Response(FailureAnalysisSerializer(result, many=True).data)

    @action(methods=["get"], detail=False, url_path="daily-summary")
    def daily_summary(self, request, **kwargs):
        date_start, date_end = _get_date_range(request)
        db_alias = StatisticsSettings.get_db_alias()
        scope_filters = self._get_scope_filters(request)

        summaries = (
            DailyStatisticsSummary.objects.using(db_alias)
            .filter(date__gte=date_start, date__lte=date_end, **scope_filters)
            .order_by("-date")
        )
        return Response(DailyStatisticsSummarySerializer(summaries, many=True).data)
