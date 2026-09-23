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

from bkflow.space import models


@admin.register(models.Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "app_code", "platform_url", "create_type", "creator", "create_at")
    search_fields = ("name", "app_code", "platform_url")
    list_filter = ("name", "app_code", "create_type", "platform_url")
    ordering = ["-create_at"]


@admin.register(models.SpaceConfig)
class SpaceConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "space_id", "name", "value_type", "text_value", "json_value")
    search_fields = ("space_id", "name", "value_type")
    list_filter = ("space_id", "name", "value_type")
    ordering = ["-space_id"]


@admin.register(models.Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "space_id", "name", "desc", "type", "content")
    search_fields = ("space_id", "name", "type")
    list_filter = ("space_id",)
    ordering = ["-id"]


@admin.register(models.CredentialScope)
class CredentialScopeAdmin(admin.ModelAdmin):
    list_display = ("id", "credential_id", "scope_type", "scope_value")
    search_fields = ("credential_id", "scope_type", "scope_value")
    list_filter = ("credential_id", "scope_type", "scope_value")
    ordering = ["-id"]
