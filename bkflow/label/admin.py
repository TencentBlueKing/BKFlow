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

from .models import Label, TemplateLabelRelation


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    """Admin configuration for Label model."""

    list_display = (
        "id",
        "name",
        "space_id",
        "parent_label",
        "is_default",
        "color",
        "full_path",
        "created_at",
        "updated_at",
    )
    list_filter = ("space_id", "is_default")
    search_fields = ("name", "creator", "updated_by", "description")
    readonly_fields = ("created_at", "updated_at", "full_path")
    ordering = ("space_id", "parent_id", "name")
    list_per_page = 50

    def parent_label(self, obj):
        """Show parent label name in list_display."""
        parent = obj.get_parent_label()
        return parent.name if parent else "-"

    parent_label.short_description = "Parent label"


@admin.register(TemplateLabelRelation)
class TemplateLabelRelationAdmin(admin.ModelAdmin):
    """Admin for template-label relations."""

    list_display = ("id", "template_id", "label_id", "label_name")
    list_filter = ("template_id",)
    search_fields = ("template_id", "label_id")
    list_per_page = 50

    def label_name(self, obj):
        """Resolve label name from label_id."""
        try:
            label = Label.objects.get(id=obj.label_id)
            return label.name
        except Label.DoesNotExist:
            return "-"

    label_name.short_description = "Label"
