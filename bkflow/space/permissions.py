# -*- coding: utf-8 -*
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
import itertools

from django.conf import settings
from rest_framework import permissions

from bkflow.space.configs import SuperusersConfig
from bkflow.space.models import Space, SpaceConfig


class SpaceExemptionPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if view.action in ["create", "list"]:
            return True


class SpaceSuperuserPermission(permissions.BasePermission):
    obj_actions = ["retrieve", "update", "partial_update", "destroy"]

    def has_permission(self, request, view):
        if settings.BLOCK_ADMIN_PERMISSION:
            return False
        if view.basename == "space":
            superusers = SpaceConfig.objects.filter(name=SuperusersConfig.name).values_list("json_value", flat=True)
            superusers = list(itertools.chain(*superusers))
            return request.user.username in superusers

        if view.action in self.obj_actions:
            # 在 has_object_permission 中校验
            return True

        space_id = request.query_params.get("space_id") or request.data.get("space_id") or view.kwargs.get("space_id")
        if not space_id:
            return False
        space_superusers = SpaceConfig.get_config(space_id, SuperusersConfig.name)
        is_space_superuser = request.user.username in space_superusers
        setattr(request, "is_space_superuser", is_space_superuser)
        return is_space_superuser

    def has_object_permission(self, request, view, obj):
        if settings.BLOCK_ADMIN_PERMISSION:
            return False
        space_id = obj.id if isinstance(obj, Space) else obj.space_id
        space_superusers = SpaceConfig.get_config(space_id, SuperusersConfig.name)
        is_space_superuser = request.user.username in space_superusers
        setattr(request, "is_space_superuser", is_space_superuser)
        return is_space_superuser
