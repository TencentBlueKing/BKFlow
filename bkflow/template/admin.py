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
from bkflow.template.models import (
    Template,
    TemplateMockData,
    TemplateMockScheme,
    TemplateOperationRecord,
    TemplateReference,
    TemplateSnapshot,
    Trigger,
)


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "space_id", "name", "source", "is_enabled", "snapshot_id")
    search_fields = ("space_id", "name", "source")
    list_filter = ("space_id", "source")
    ordering = ["-id"]


@admin.register(TemplateSnapshot)
class TemplateSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "template_id", "version", "draft", "creator", "update_time", "is_deleted")
    search_fields = ("template_id", "version", "creator")
    list_filter = ("draft", "is_deleted")
    ordering = ["-id"]


@admin.register(TemplateReference)
class TemplateReferenceAdmin(admin.ModelAdmin):
    list_display = ("id", "root_template_id", "subprocess_template_id", "subprocess_node_id", "always_use_latest")
    search_fields = ("root_template_id", "subprocess_template_id")
    ordering = ["-id"]


@admin.register(TemplateMockData)
class TemplateMockDataAdmin(admin.ModelAdmin):
    list_display = ("id", "space_id", "template_id", "node_id", "name", "is_default", "operator", "update_at")
    search_fields = ("template_id", "node_id", "name")
    list_filter = ("space_id", "is_default")
    ordering = ["-id"]


@admin.register(TemplateMockScheme)
class TemplateMockSchemeAdmin(admin.ModelAdmin):
    list_display = ("id", "space_id", "template_id", "operator", "update_at")
    search_fields = ("template_id",)
    list_filter = ("space_id",)
    ordering = ["-id"]


@admin.register(Trigger)
class TriggerAdmin(admin.ModelAdmin):
    list_display = ("id", "space_id", "template_id", "name", "is_enabled", "type")
    search_fields = ("space_id", "template_id", "name", "type")
    list_filter = ("space_id", "template_id", "name", "is_enabled", "type")
    ordering = ["-id"]


admin.site.register(TemplateOperationRecord, BaseOperateRecordAdmin)
