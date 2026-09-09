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

from bkflow.permission.models import Token, TokenGrant


class TokenGrantInline(admin.TabularInline):
    """只读展示已签发授权，不允许通过管理页面追加、修改或删除明细。"""

    model = TokenGrant
    readonly_fields = ("resource_type", "resource_id", "permission_type", "grant_hash")
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    inlines = (TokenGrantInline,)
    readonly_fields = ("token", "grant_set_hash")
    list_display = ("token", "user", "grant_set_hash", "expired_time")
    search_fields = ("token", "user", "grants__resource_type", "grants__resource_id")
    list_filter = ("token", "user", "grants__resource_type", "expired_time")
    ordering = ["-expired_time"]

    def has_add_permission(self, request):
        """禁止从管理后台创建缺少授权明细的主票据。"""
        return False

    def get_queryset(self, request):
        """预取只读授权明细，避免管理列表关联查询重复访问数据库。"""
        return super().get_queryset(request).prefetch_related("grants")
