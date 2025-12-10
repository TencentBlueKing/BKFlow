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
import abc

from rest_framework import permissions
from rest_framework.request import Request

from bkflow.permission.models import PermissionType, Token


class BaseTokenPermission(permissions.BasePermission):
    @abc.abstractmethod
    def get_resource_type(self):
        pass

    def has_operate_permission(self, username, space_id, resource_id, token):
        return Token.verify(
            space_id,
            username,
            resource_type=self.get_resource_type(),
            resource_id=resource_id,
            permission_type=PermissionType.OPERATE.value,
            token=token,
        )

    def has_edit_permission(self, username, space_id, resource_id, token):
        return Token.verify(
            space_id,
            username,
            resource_type=self.get_resource_type(),
            resource_id=resource_id,
            permission_type=PermissionType.EDIT.value,
            token=token,
        )

    def has_view_permission(self, username, space_id, resource_id, token):
        return Token.verify(
            space_id,
            username,
            resource_type=self.get_resource_type(),
            resource_id=resource_id,
            permission_type=PermissionType.VIEW.value,
            token=token,
        )


class BaseMockTokenPermission(BaseTokenPermission):
    def get_resource_type(self):
        return "TEMPLATE"

    @staticmethod
    def get_space_id(request: Request):
        return request.query_params.get("space_id", None) or request.data.get("space_id", None)

    def has_mock_permission(self, username, space_id, resource_id, token):
        return Token.verify(
            space_id,
            username,
            resource_type=self.get_resource_type(),
            resource_id=resource_id,
            permission_type=PermissionType.MOCK.value,
            token=token,
        )
