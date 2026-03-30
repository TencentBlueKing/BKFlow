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
from django.utils.html import format_html

from bkflow.admin.models import ModuleInfo


@admin.register(ModuleInfo)
class ModuleInfoAdmin(admin.ModelAdmin):
    list_display = ("code", "space_id", "type", "url", "isolation_level", "admin_link")
    search_fields = ("space_id", "url", "type", "isolation_level", "code")
    list_filter = ("space_id", "url", "type", "isolation_level", "code")
    ordering = ["space_id"]

    def admin_link(self, obj):
        if not obj.url:
            return "-"
        admin_url = f"{obj.url.rstrip('/')}/bkflow_admin/"
        return format_html('<a href="{}" target="_blank">打开 Django Admin</a>', admin_url)

    admin_link.short_description = "Engine Admin"
