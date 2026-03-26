from django.contrib import admin

import env
from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateNodeStatistics,
    TemplateStatistics,
)


class TaskflowStatisticsAdmin(admin.ModelAdmin):
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


class TaskflowExecutedNodeStatisticsAdmin(admin.ModelAdmin):
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
    list_filter = ["status", "state", "is_retry", "is_remote"]
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
        "is_remote",
        "node_id",
        "node_name",
        "is_sub",
    ]
    list_filter = ["is_remote", "is_sub"]
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


module_type = getattr(env, "BKFLOW_MODULE_TYPE", "")

if module_type == "engine":
    admin.site.register(TaskflowStatistics, TaskflowStatisticsAdmin)
    admin.site.register(TaskflowExecutedNodeStatistics, TaskflowExecutedNodeStatisticsAdmin)
elif module_type == "interface":
    admin.site.register(TemplateStatistics, TemplateStatisticsAdmin)
    admin.site.register(TemplateNodeStatistics, TemplateNodeStatisticsAdmin)
else:
    admin.site.register(TaskflowStatistics, TaskflowStatisticsAdmin)
    admin.site.register(TaskflowExecutedNodeStatistics, TaskflowExecutedNodeStatisticsAdmin)
    admin.site.register(TemplateStatistics, TemplateStatisticsAdmin)
    admin.site.register(TemplateNodeStatistics, TemplateNodeStatisticsAdmin)

admin.site.register(DailyStatisticsSummary, DailyStatisticsSummaryAdmin)
admin.site.register(PluginExecutionSummary, PluginExecutionSummaryAdmin)
