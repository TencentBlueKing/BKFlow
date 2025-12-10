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

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.permission.models import PermissionType, Token
from bkflow.permission.permissions import BaseMockTokenPermission, BaseTokenPermission

logger = logging.getLogger("root")


class TaskTokenPermission(BaseTokenPermission):
    def get_resource_type(self):
        return "TASK"

    def has_operate_permission(self, username, space_id, resource_id, token):
        return Token.verify(
            space_id,
            username,
            resource_type=self.get_resource_type(),
            resource_id=resource_id,
            permission_type=PermissionType.OPERATE.value,
            token=token,
        )

    def has_permission(self, request, view):
        task_id = view.kwargs.get("task_id", None)
        if task_id is None:
            return False

        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

        has_operate_permission = self.has_operate_permission(request.user.username, None, task_id, request.token)

        if view.action in view.OPERATE_ABOVE_ACTIONS:
            return has_operate_permission

        has_view_permission = self.has_view_permission(request.user.username, None, task_id, request.token)
        return has_operate_permission or has_view_permission


class ScopePermission(BaseTokenPermission):
    def get_resource_type(self):
        return "SCOPE"

    def has_operate_permission(self, username, space_id, resource_id, token):
        return Token.verify(
            space_id,
            username,
            resource_type=self.get_resource_type(),
            resource_id=resource_id,
            permission_type=PermissionType.OPERATE.value,
            token=token,
        )

    def has_permission(self, request, view):
        task_id = view.kwargs.get("task_id", None)
        if task_id is None:
            return False

        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

        has_operate_permission = self.has_operate_permission(request.user.username, None, task_id, request.token)

        if view.action in view.OPERATE_ABOVE_ACTIONS:
            return has_operate_permission

        has_view_permission = self.has_view_permission(request.user.username, None, task_id, request.token)
        return has_operate_permission or has_view_permission


class TaskMockTokenPermission(BaseMockTokenPermission):
    def has_permission(self, request, view):
        task_id = view.kwargs.get("task_id", None)
        if task_id is None:
            return False
        space_id = self.get_space_id(request)
        if space_id is None:
            logger.error("[TaskMockTokenPermission] space_id is None")
            return False

        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        result = client.get_task_detail(task_id)
        if not result.get("result"):
            logger.error(f"[TaskMockTokenPermission] get_task_detail failed: {result}")
            return False
        template_id = result["data"].get("template_id")
        return self.has_mock_permission(request.user.username, space_id, template_id, request.token)
