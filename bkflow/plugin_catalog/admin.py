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

from bkflow.plugin_catalog.models import (
    PluginDirectory,
    SpacePluginCatalogEntry,
    TemplatePluginReference,
)


class PluginDirectoryAdmin(admin.ModelAdmin):
    list_display = ("space_id", "name", "parent", "order", "update_time")
    list_filter = ("space_id",)
    search_fields = ("space_id", "name")
    ordering = ("-update_time",)


class SpacePluginCatalogEntryAdmin(admin.ModelAdmin):
    list_display = (
        "space_id",
        "plugin_type",
        "source_key",
        "plugin_code",
        "status",
        "directory",
        "recommended",
        "recommend_order",
        "is_deleted",
        "update_at",
    )
    list_filter = ("status", "plugin_type", "recommended", "is_deleted")
    search_fields = ("space_id", "plugin_code", "source_key")
    ordering = ("-update_at",)


class TemplatePluginReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "space_id",
        "template_id",
        "role",
        "plugin_type",
        "source_key",
        "plugin_code",
        "node_id",
        "node_name",
        "resolved",
    )
    list_filter = ("role", "plugin_type", "resolved")
    search_fields = ("space_id", "template_id", "plugin_code", "node_id")
    ordering = ("-update_time",)


admin.site.register(PluginDirectory, PluginDirectoryAdmin)
admin.site.register(SpacePluginCatalogEntry, SpacePluginCatalogEntryAdmin)
admin.site.register(TemplatePluginReference, TemplatePluginReferenceAdmin)
