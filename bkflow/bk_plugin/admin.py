# -*- coding: utf-8 -*-
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

from bkflow.bk_plugin.models import BKPlugin, BKPluginAuthorization


# Register your models here.
@admin.register(BKPlugin)
class BKPluginAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "tag",
        "logo_url",
        "introduction",
        "created_time",
        "updated_time",
        "manager",
        "extra_info",
    )
    search_fields = ("code", "name", "tag")
    list_filter = ("code",)
    ordering = ("code",)


@admin.register(BKPluginAuthorization)
class BKPluginAuthenticationAdmin(admin.ModelAdmin):
    list_display = ("code", "status", "config", "authorized_time", "operator")
    search_fields = ("code", "operator")
    list_filter = ("code", "operator", "status")
    ordering = ("code",)
