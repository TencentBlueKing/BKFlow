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
import logging

from rest_framework import permissions

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.permission.models import PermissionType, ResourceType, Token
from bkflow.template.serializers.template import TemplateRelatedResourceSerializer

logger = logging.getLogger("root")


class DecisionTableUserPermission(permissions.BasePermission):
    NEED_TEMPLATE_EDIT_ACTIONS = ["list", "create", "update", "partial_update", "delete", "evaluate"]

    def has_permission(self, request, view):
        data = request.query_params or request.data
        ser = TemplateRelatedResourceSerializer(data=data)
        ser.is_valid(raise_exception=True)
        space_id, template_id = ser.validated_data["space_id"], ser.validated_data["template_id"]
        token = Token.objects.filter(space_id=space_id, token=request.token).first()
        if not token or token.has_expired():
            return False

        if token.resource_type == ResourceType.TEMPLATE.value and int(token.resource_id) == template_id:
            return view.action not in self.NEED_TEMPLATE_EDIT_ACTIONS or token.permission_type in [
                PermissionType.EDIT.value,
                PermissionType.MOCK.value,
            ]

        if token.resource_type == ResourceType.TASK.value:
            client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
            result = client.get_task_detail(task_id=token.resource_id)
            if not result.get("result"):
                logger.error(f"[TaskMockTokenPermission] get_task_detail failed: {result}")
                return False
            task_template_id = result["data"].get("template_id")
            return view.action not in self.NEED_TEMPLATE_EDIT_ACTIONS and int(task_template_id) == template_id

    def has_object_permission(self, request, view, obj):
        data = request.query_params or request.data
        ser = TemplateRelatedResourceSerializer(data=data)
        ser.is_valid(raise_exception=True)
        space_id, template_id = ser.validated_data["space_id"], ser.validated_data["template_id"]
        token = Token.objects.filter(space_id=space_id, token=request.token).first()
        if not token or token.has_expired():
            return False
        return obj.template_id == template_id
