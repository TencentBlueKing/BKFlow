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
from bkflow.permission.permissions import BaseMockTokenPermission, BaseTokenPermission
from bkflow.permission.services import get_valid_token

logger = logging.getLogger("root")


class TaskTokenPermission(BaseTokenPermission):
    def get_resource_type(self):
        return "TASK"

    def has_permission(self, request, view):
        task_id = view.kwargs.get("task_id", None)
        if task_id is None:
            return False

        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

        has_operate_permission = self.has_operate_permission(
            request.user.username,
            BaseMockTokenPermission.get_space_id(request),
            task_id,
            request.token,
            request=request,
            target_resource_type="TASK",
        )

        if view.action in view.OPERATE_ABOVE_ACTIONS:
            return has_operate_permission

        has_view_permission = self.has_view_permission(
            request.user.username,
            BaseMockTokenPermission.get_space_id(request),
            task_id,
            request.token,
            request=request,
            target_resource_type="TASK",
        )
        return has_operate_permission or has_view_permission


class ScopePermission(BaseTokenPermission):
    def get_resource_type(self):
        return "SCOPE"

    def has_permission(self, request, view):
        task_id = view.kwargs.get("task_id", None)
        if task_id is None:
            return False

        has_mock_permission = self.has_mock_permission(
            request.user.username,
            BaseMockTokenPermission.get_space_id(request),
            task_id,
            request.token,
            request=request,
            target_resource_type="TASK",
        )
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return has_mock_permission

        has_operate_permission = self.has_operate_permission(
            request.user.username,
            BaseMockTokenPermission.get_space_id(request),
            task_id,
            request.token,
            request=request,
            target_resource_type="TASK",
        )

        if view.action in view.OPERATE_ABOVE_ACTIONS:
            return has_operate_permission or has_mock_permission

        has_view_permission = self.has_view_permission(
            request.user.username,
            BaseMockTokenPermission.get_space_id(request),
            task_id,
            request.token,
            request=request,
            target_resource_type="TASK",
        )
        return has_operate_permission or has_view_permission or has_mock_permission


class TaskMockTokenPermission(BaseMockTokenPermission):
    def has_permission(self, request, view):
        task_id = view.kwargs.get("task_id", None)
        if task_id is None:
            return False
        space_id = self.get_space_id(request)
        if space_id is None:
            logger.error("[TaskMockTokenPermission] space_id is None")
            return False

        if get_valid_token(request.token, request.user.username, space_id, request) is None:
            return False
        try:
            client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
            result = client.get_task_detail(task_id)
        except Exception:
            logger.warning("[TaskMockTokenPermission] get_task_detail failed, task_id=%s", task_id)
            return False
        if not result.get("result") or result.get("data", {}).get("create_method") != "MOCK":
            logger.error(f"[TaskMockTokenPermission] get_task_detail failed: {result}")
            return False
        template_id = result["data"].get("template_id")
        return self.has_mock_permission(
            request.user.username,
            space_id,
            template_id,
            request.token,
            request=request,
            target_resource_type="TEMPLATE",
        )
