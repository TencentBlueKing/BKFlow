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

from django.contrib import admin

from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateNodeStatistics,
    TemplateStatistics,
)


@admin.register(TemplateNodeStatistics)
class TemplateNodeStatisticsAdmin(admin.ModelAdmin):
    list_display = ["id", "template_id", "space_id", "component_code", "node_name", "is_remote", "created_at"]
    list_filter = ["space_id", "is_remote", "is_sub"]
    search_fields = ["component_code", "node_name", "template_id"]
    readonly_fields = ["created_at"]


@admin.register(TemplateStatistics)
class TemplateStatisticsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "template_id",
        "space_id",
        "template_name",
        "atom_total",
        "subprocess_total",
        "is_enabled",
        "updated_at",
    ]
    list_filter = ["space_id", "is_enabled"]
    search_fields = ["template_name", "template_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(TaskflowStatistics)
class TaskflowStatisticsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "task_id",
        "space_id",
        "template_id",
        "create_method",
        "is_success",
        "final_state",
        "elapsed_time",
        "create_time",
    ]
    list_filter = ["space_id", "create_method", "trigger_method", "is_success", "final_state"]
    search_fields = ["task_id", "instance_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(TaskflowExecutedNodeStatistics)
class TaskflowExecutedNodeStatisticsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "task_id",
        "node_id",
        "component_code",
        "status",
        "state",
        "elapsed_time",
        "started_time",
    ]
    list_filter = ["space_id", "status", "state", "is_skip", "is_retry"]
    search_fields = ["component_code", "node_name", "task_id"]
    readonly_fields = ["created_at"]


@admin.register(DailyStatisticsSummary)
class DailyStatisticsSummaryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "date",
        "space_id",
        "task_created_count",
        "task_success_count",
        "task_failed_count",
        "avg_task_elapsed_time",
    ]
    list_filter = ["space_id", "date"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(PluginExecutionSummary)
class PluginExecutionSummaryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "period_type",
        "period_start",
        "space_id",
        "component_code",
        "execution_count",
        "success_count",
        "avg_elapsed_time",
    ]
    list_filter = ["space_id", "period_type", "is_remote"]
    search_fields = ["component_code"]
    readonly_fields = ["created_at", "updated_at"]
