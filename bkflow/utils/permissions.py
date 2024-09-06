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
from django.conf import settings
from rest_framework import permissions


class AdminPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_superuser and not settings.BLOCK_ADMIN_PERMISSION

    def has_object_permission(self, request, view, obj):
        return request.user.is_superuser and not settings.BLOCK_ADMIN_PERMISSION


class AppInternalPermission(permissions.BasePermission):
    """用于内部模块间调用的权限校验"""

    @staticmethod
    def _app_internal_token_validation(request):
        if (
            request.app_internal_token and request.app_internal_token == settings.APP_INTERNAL_TOKEN
        ) or settings.APP_INTERNAL_VALIDATION_SKIP:
            return True
        return False

    def has_permission(self, request, view):
        return self._app_internal_token_validation(request)

    def has_object_permission(self, request, view, obj):
        return self._app_internal_token_validation(request)
