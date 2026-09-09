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
from bkflow.permission.models import ResourceType, TokenPermissionType
from bkflow.permission.services import get_valid_token
from bkflow.template.serializers.template import TemplateRelatedResourceSerializer

logger = logging.getLogger("root")


class DecisionTableUserPermission(permissions.BasePermission):
    NEED_TEMPLATE_EDIT_ACTIONS = ["list", "create", "update", "partial_update", "delete", "evaluate"]

    @staticmethod
    def _matches_template_id(resource_id, template_id):
        """保留决策表原有的数值模板 ID 比较。"""
        try:
            return int(resource_id) == template_id
        except (TypeError, ValueError):
            return False

    def has_permission(self, request, view):
        data = request.query_params or request.data
        ser = TemplateRelatedResourceSerializer(data=data)
        ser.is_valid(raise_exception=True)
        space_id, template_id = ser.validated_data["space_id"], ser.validated_data["template_id"]
        token = get_valid_token(request.token, request.user.username, space_id, request)
        if token is None:
            return False

        for grant in token.get_grants():
            if grant.resource_type == ResourceType.TEMPLATE.value and self._matches_template_id(
                grant.resource_id, template_id
            ):
                if view.action not in self.NEED_TEMPLATE_EDIT_ACTIONS or grant.permission_type in [
                    TokenPermissionType.EDIT.value,
                    TokenPermissionType.MOCK.value,
                ]:
                    return True
            if grant.resource_type == ResourceType.TASK.value and view.action not in self.NEED_TEMPLATE_EDIT_ACTIONS:
                try:
                    client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
                    result = client.get_task_detail(task_id=grant.resource_id)
                except Exception:
                    logger.warning(
                        "[DecisionTableUserPermission] get_task_detail failed, task_id=%s", grant.resource_id
                    )
                    continue
                if not result.get("result"):
                    continue
                if self._matches_template_id(result.get("data", {}).get("template_id"), template_id):
                    return True
        return False

    def has_object_permission(self, request, view, obj):
        data = request.query_params or request.data
        ser = TemplateRelatedResourceSerializer(data=data)
        ser.is_valid(raise_exception=True)
        space_id, template_id = ser.validated_data["space_id"], ser.validated_data["template_id"]
        token = get_valid_token(request.token, request.user.username, space_id, request)
        if token is None:
            return False
        return obj.template_id == template_id
