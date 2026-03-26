from django.contrib import admin

import env
from bkflow.statistics.conf import StatisticsSettings
from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateNodeStatistics,
    TemplateStatistics,
)


def _is_engine_module():
    return getattr(env, "BKFLOW_MODULE_TYPE", "") == "engine"


class EngineFilterMixin:
    """engine 模块下自动按 engine_id 过滤，仅展示本实例管理的数据"""

    engine_id_field = "engine_id"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_engine_module():
            qs = qs.filter(**{self.engine_id_field: StatisticsSettings.get_engine_id()})
        return qs


class TaskflowStatisticsAdmin(EngineFilterMixin, admin.ModelAdmin):
    list_display = [
        "task_id",
        "space_id",
        "template_id",
        "engine_id",
        "final_state",
        "is_started",
        "is_finished",
        "create_time",
        "elapsed_time",
    ]
    list_filter = ["final_state", "engine_id", "is_started", "is_finished"]
    search_fields = ["task_id", "space_id", "template_id"]
    readonly_fields = [f.name for f in TaskflowStatistics._meta.get_fields()]


class TaskflowExecutedNodeStatisticsAdmin(EngineFilterMixin, admin.ModelAdmin):
    list_display = [
        "task_id",
        "component_code",
        "component_name",
        "node_id",
        "status",
        "state",
        "is_retry",
        "elapsed_time",
        "started_time",
    ]
    list_filter = ["status", "state", "is_retry", "plugin_type"]
    search_fields = ["task_id", "component_code", "node_id"]
    readonly_fields = [f.name for f in TaskflowExecutedNodeStatistics._meta.get_fields()]


class TemplateStatisticsAdmin(admin.ModelAdmin):
    list_display = [
        "template_id",
        "space_id",
        "template_name",
        "is_enabled",
        "atom_total",
        "subprocess_total",
        "gateways_total",
    ]
    list_filter = ["is_enabled"]
    search_fields = ["template_id", "template_name", "space_id"]
    readonly_fields = [f.name for f in TemplateStatistics._meta.get_fields()]


class TemplateNodeStatisticsAdmin(admin.ModelAdmin):
    list_display = [
        "template_id",
        "component_code",
        "component_name",
        "version",
        "plugin_type",
        "node_id",
        "node_name",
        "is_sub",
    ]
    list_filter = ["plugin_type", "is_sub"]
    search_fields = ["template_id", "component_code", "node_id"]
    readonly_fields = [f.name for f in TemplateNodeStatistics._meta.get_fields()]


class DailyStatisticsSummaryAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "space_id",
        "scope_type",
        "task_created_count",
        "task_finished_count",
        "task_success_count",
        "task_failed_count",
        "node_executed_count",
    ]
    list_filter = ["date"]
    search_fields = ["space_id"]
    readonly_fields = [f.name for f in DailyStatisticsSummary._meta.get_fields()]


class PluginExecutionSummaryAdmin(admin.ModelAdmin):
    list_display = [
        "period_type",
        "period_start",
        "space_id",
        "component_code",
        "component_name",
        "execution_count",
        "success_count",
        "failed_count",
    ]
    list_filter = ["period_type", "period_start"]
    search_fields = ["component_code", "space_id"]
    readonly_fields = [f.name for f in PluginExecutionSummary._meta.get_fields()]


admin.site.register(TaskflowStatistics, TaskflowStatisticsAdmin)
admin.site.register(TaskflowExecutedNodeStatistics, TaskflowExecutedNodeStatisticsAdmin)
admin.site.register(TemplateStatistics, TemplateStatisticsAdmin)
admin.site.register(TemplateNodeStatistics, TemplateNodeStatisticsAdmin)

admin.site.register(DailyStatisticsSummary, DailyStatisticsSummaryAdmin)
admin.site.register(PluginExecutionSummary, PluginExecutionSummaryAdmin)
