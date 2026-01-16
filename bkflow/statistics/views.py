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

from datetime import date, timedelta

from django.db.models import Avg, Count, Q, Sum
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from bkflow.statistics.conf import StatisticsConfig
from bkflow.statistics.models import (
    DailyStatisticsSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateStatistics,
)
from bkflow.statistics.serializers import (
    DailyStatisticsSummarySerializer,
    PluginRankingSerializer,
    StatisticsOverviewSerializer,
    TaskTrendSerializer,
    TemplateRankingSerializer,
)


class SpaceStatisticsViewSet(ViewSet):
    """空间运营数据 API"""

    def get_db_alias(self):
        return StatisticsConfig.get_db_alias()

    def _get_date_range(self, request):
        """获取查询的日期范围"""
        date_range = request.query_params.get("date_range", "30d")
        end_date = date.today()

        if date_range == "7d":
            start_date = end_date - timedelta(days=7)
        elif date_range == "30d":
            start_date = end_date - timedelta(days=30)
        elif date_range == "90d":
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=30)

        return start_date, end_date

    @action(methods=["GET"], detail=False, url_path="overview")
    def overview(self, request):
        """
        空间运营概览

        Query params:
            space_id: 空间ID（必填）
            scope_type: 范围类型（可选）
            scope_value: 范围值（可选）
            date_range: 日期范围（7d/30d/90d，默认30d）
        """
        space_id = request.query_params.get("space_id")
        if not space_id:
            return Response({"error": "space_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        scope_type = request.query_params.get("scope_type")
        scope_value = request.query_params.get("scope_value")
        start_date, end_date = self._get_date_range(request)

        db_alias = self.get_db_alias()

        # 构建查询条件
        task_filters = Q(space_id=space_id, create_time__date__gte=start_date, create_time__date__lte=end_date)
        if scope_type:
            task_filters &= Q(scope_type=scope_type)
        if scope_value:
            task_filters &= Q(scope_value=scope_value)

        # 任务统计
        task_stats = (
            TaskflowStatistics.objects.using(db_alias)
            .filter(task_filters)
            .aggregate(
                total_tasks=Count("id"),
                success_tasks=Count("id", filter=Q(is_success=True)),
                failed_tasks=Count("id", filter=Q(is_finished=True, is_success=False)),
                avg_elapsed=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
            )
        )

        # 模板统计
        template_filters = Q(space_id=space_id)
        if scope_type:
            template_filters &= Q(scope_type=scope_type)
        if scope_value:
            template_filters &= Q(scope_value=scope_value)

        template_stats = (
            TemplateStatistics.objects.using(db_alias)
            .filter(template_filters)
            .aggregate(
                total_templates=Count("id"),
                active_templates=Count("id", filter=Q(is_enabled=True)),
            )
        )

        # 节点统计
        node_filters = Q(space_id=space_id, started_time__date__gte=start_date, started_time__date__lte=end_date)
        if scope_type:
            node_filters &= Q(scope_type=scope_type)
        if scope_value:
            node_filters &= Q(scope_value=scope_value)

        node_stats = (
            TaskflowExecutedNodeStatistics.objects.using(db_alias)
            .filter(node_filters, is_retry=False)
            .aggregate(
                total_nodes=Count("id"),
                success_nodes=Count("id", filter=Q(status=True)),
            )
        )

        total_tasks = task_stats["total_tasks"] or 0
        success_tasks = task_stats["success_tasks"] or 0
        total_nodes = node_stats["total_nodes"] or 0
        success_nodes = node_stats["success_nodes"] or 0

        result = {
            "space_id": int(space_id),
            "scope_type": scope_type,
            "scope_value": scope_value,
            "total_tasks": total_tasks,
            "success_tasks": success_tasks,
            "failed_tasks": task_stats["failed_tasks"] or 0,
            "success_rate": round(success_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0,
            "total_templates": template_stats["total_templates"] or 0,
            "active_templates": template_stats["active_templates"] or 0,
            "total_nodes_executed": total_nodes,
            "node_success_rate": round(success_nodes / total_nodes * 100, 2) if total_nodes > 0 else 0,
            "avg_task_elapsed_time": round(task_stats["avg_elapsed"] or 0, 2),
        }

        serializer = StatisticsOverviewSerializer(result)
        return Response(serializer.data)

    @action(methods=["GET"], detail=False, url_path="task-trend")
    def task_trend(self, request):
        """
        任务执行趋势

        Query params:
            space_id: 空间ID（必填）
            scope_type: 范围类型（可选）
            scope_value: 范围值（可选）
            date_range: 日期范围（7d/30d/90d，默认30d）
        """
        space_id = request.query_params.get("space_id")
        if not space_id:
            return Response({"error": "space_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        scope_type = request.query_params.get("scope_type")
        scope_value = request.query_params.get("scope_value")
        start_date, end_date = self._get_date_range(request)

        db_alias = self.get_db_alias()

        # 优先从每日汇总表查询
        filters = Q(space_id=space_id, date__gte=start_date, date__lte=end_date)
        if scope_type:
            filters &= Q(scope_type=scope_type)
        if scope_value:
            filters &= Q(scope_value=scope_value)

        daily_stats = (
            DailyStatisticsSummary.objects.using(db_alias)
            .filter(filters)
            .values("date")
            .annotate(
                task_created_count=Sum("task_created_count"),
                task_finished_count=Sum("task_finished_count"),
                task_success_count=Sum("task_success_count"),
            )
            .order_by("date")
        )

        result = []
        for stat in daily_stats:
            finished = stat["task_finished_count"] or 0
            success = stat["task_success_count"] or 0
            result.append(
                {
                    "date": stat["date"],
                    "task_created_count": stat["task_created_count"] or 0,
                    "task_finished_count": finished,
                    "task_success_count": success,
                    "success_rate": round(success / finished * 100, 2) if finished > 0 else 0,
                }
            )

        serializer = TaskTrendSerializer(result, many=True)
        return Response(serializer.data)

    @action(methods=["GET"], detail=False, url_path="plugin-ranking")
    def plugin_ranking(self, request):
        """
        插件排行

        Query params:
            space_id: 空间ID（必填）
            date_range: 日期范围（7d/30d/90d，默认30d）
            order_by: 排序字段（execution_count/success_rate/avg_elapsed_time，默认execution_count）
            limit: 返回数量（默认10）
        """
        space_id = request.query_params.get("space_id")
        if not space_id:
            return Response({"error": "space_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        start_date, end_date = self._get_date_range(request)
        order_by = request.query_params.get("order_by", "execution_count")
        limit = int(request.query_params.get("limit", 10))

        db_alias = self.get_db_alias()

        filters = Q(space_id=space_id, started_time__date__gte=start_date, started_time__date__lte=end_date)

        plugin_stats = (
            TaskflowExecutedNodeStatistics.objects.using(db_alias)
            .filter(filters, is_retry=False)
            .values("component_code", "version")
            .annotate(
                execution_count=Count("id"),
                success_count=Count("id", filter=Q(status=True)),
                failed_count=Count("id", filter=Q(status=False)),
                avg_elapsed_time=Avg("elapsed_time", filter=Q(elapsed_time__isnull=False)),
            )
            .order_by(f"-{order_by}" if order_by != "success_rate" else "-execution_count")[:limit]
        )

        result = []
        for stat in plugin_stats:
            execution = stat["execution_count"] or 0
            success = stat["success_count"] or 0
            result.append(
                {
                    "component_code": stat["component_code"],
                    "version": stat["version"],
                    "execution_count": execution,
                    "success_count": success,
                    "failed_count": stat["failed_count"] or 0,
                    "success_rate": round(success / execution * 100, 2) if execution > 0 else 0,
                    "avg_elapsed_time": round(stat["avg_elapsed_time"] or 0, 2),
                }
            )

        # 如果按成功率排序，需要在内存中重新排序
        if order_by == "success_rate":
            result.sort(key=lambda x: x["success_rate"], reverse=True)

        serializer = PluginRankingSerializer(result, many=True)
        return Response(serializer.data)

    @action(methods=["GET"], detail=False, url_path="template-ranking")
    def template_ranking(self, request):
        """
        模板排行

        Query params:
            space_id: 空间ID（必填）
            date_range: 日期范围（7d/30d/90d，默认30d）
            order_by: 排序字段（task_count/success_rate，默认task_count）
            limit: 返回数量（默认10）
        """
        space_id = request.query_params.get("space_id")
        if not space_id:
            return Response({"error": "space_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        start_date, end_date = self._get_date_range(request)
        order_by = request.query_params.get("order_by", "task_count")
        limit = int(request.query_params.get("limit", 10))

        db_alias = self.get_db_alias()

        filters = Q(
            space_id=space_id,
            template_id__isnull=False,
            create_time__date__gte=start_date,
            create_time__date__lte=end_date,
        )

        template_stats = (
            TaskflowStatistics.objects.using(db_alias)
            .filter(filters)
            .values("template_id")
            .annotate(
                task_count=Count("id"),
                success_count=Count("id", filter=Q(is_success=True)),
            )
            .order_by("-task_count")[:limit]
        )

        # 获取模板名称
        template_ids = [stat["template_id"] for stat in template_stats]
        template_names = dict(
            TemplateStatistics.objects.using(db_alias)
            .filter(template_id__in=template_ids)
            .values_list("template_id", "template_name")
        )

        result = []
        for stat in template_stats:
            task_count = stat["task_count"] or 0
            success_count = stat["success_count"] or 0
            result.append(
                {
                    "template_id": stat["template_id"],
                    "template_name": template_names.get(stat["template_id"], ""),
                    "task_count": task_count,
                    "success_count": success_count,
                    "success_rate": round(success_count / task_count * 100, 2) if task_count > 0 else 0,
                }
            )

        # 如果按成功率排序，需要在内存中重新排序
        if order_by == "success_rate":
            result.sort(key=lambda x: x["success_rate"], reverse=True)

        serializer = TemplateRankingSerializer(result, many=True)
        return Response(serializer.data)

    @action(methods=["GET"], detail=False, url_path="daily-summary")
    def daily_summary(self, request):
        """
        每日统计汇总

        Query params:
            space_id: 空间ID（必填）
            scope_type: 范围类型（可选）
            scope_value: 范围值（可选）
            date_range: 日期范围（7d/30d/90d，默认30d）
        """
        space_id = request.query_params.get("space_id")
        if not space_id:
            return Response({"error": "space_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        scope_type = request.query_params.get("scope_type")
        scope_value = request.query_params.get("scope_value")
        start_date, end_date = self._get_date_range(request)

        db_alias = self.get_db_alias()

        filters = Q(space_id=space_id, date__gte=start_date, date__lte=end_date)
        if scope_type:
            filters &= Q(scope_type=scope_type)
        if scope_value:
            filters &= Q(scope_value=scope_value)

        daily_stats = DailyStatisticsSummary.objects.using(db_alias).filter(filters).order_by("date")

        serializer = DailyStatisticsSummarySerializer(daily_stats, many=True)
        return Response(serializer.data)
