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

from bkflow.contrib.operation_record.admin import BaseOperateRecordAdmin

from . import models
from .models import TaskOperationRecord


@admin.register(models.TaskInstance)
class TaskInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "instance_id",
        "name",
        "creator",
        "create_time",
        "finish_time",
        "scope_type",
        "scope_value",
        "executor",
    )
    search_fields = ("instance_id", "name", "creator")
    list_filter = ("create_time", "finish_time")
    ordering = ("-create_time",)


@admin.register(models.TaskTreeInfo)
class TaskTreeInfoAdmin(admin.ModelAdmin):
    list_display = ("id",)
    ordering = ["-id"]


@admin.register(models.TaskSnapshot)
class TaskSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id",)
    ordering = ["-id"]


@admin.register(models.TaskExecutionSnapshot)
class TaskExecutionSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id",)
    ordering = ["-id"]


@admin.register(models.PeriodicTask)
class PeriodicTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "template_id",
        "trigger_id",
        "cron",
        "name",
        "creator",
        "total_run_count",
        "last_run_at",
        "creator",
        "extra_info",
    )
    search_fields = ("template_id", "trigger_id", "name", "creator")


@admin.register(models.AutoRetryNodeStrategy)
class AutoRetryNodeStrategyAdmin(admin.ModelAdmin):
    list_display = ["taskflow_id", "root_pipeline_id", "node_id", "retry_times", "max_retry_times", "interval"]
    search_fields = ["root_pipeline_id__exact", "node_id__exact"]


@admin.register(models.TaskMockData)
class TaskMockDataAdmin(admin.ModelAdmin):
    list_display = ["id", "taskflow_id", "mock_data_ids", "data"]
    search_fields = ["taskflow_id", "mock_data_ids"]


@admin.register(models.TimeoutNodeConfig)
class TimeoutNodeConfigAdmin(admin.ModelAdmin):
    list_display = ("node_id", "task_id", "root_pipeline_id", "action", "timeout")
    search_fields = ("node_id", "root_pipeline_id", "task_id")


@admin.register(models.TimeoutNodesRecord)
class TimeoutNodesRecordAdmin(admin.ModelAdmin):
    list_display = ("id",)
    ordering = ["-id"]


@admin.register(models.EngineSpaceConfig)
class EngineSpaceConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "space_id", "name", "is_public", "value_type", "text_value", "interface_config_id")
    search_fields = ("space_id", "name")
    list_filter = ("space_id", "is_public", "value_type")
    ordering = ["-id"]


@admin.register(models.TaskFlowRelation)
class TaskFlowRelationAdmin(admin.ModelAdmin):
    list_display = ("id", "task_id", "parent_task_id", "root_task_id", "create_time")
    search_fields = ("task_id", "parent_task_id", "root_task_id")
    ordering = ["-id"]


admin.site.register(TaskOperationRecord, BaseOperateRecordAdmin)
