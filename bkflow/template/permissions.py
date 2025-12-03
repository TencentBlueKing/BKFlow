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
from bkflow.permission.permissions import BaseMockTokenPermission, BaseTokenPermission
from bkflow.template.serializers.template import TemplateRelatedResourceSerializer


class TemplatePermission(BaseTokenPermission):
    def get_resource_type(self):
        return "TEMPLATE"

    def has_permission(self, request, view):
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

    def has_object_permission(self, request, view, obj):
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

        has_edit_permission = self.has_edit_permission(request.user.username, obj.space_id, obj.id, request.token)

        if view.action in view.EDIT_ABOVE_ACTIONS:
            return has_edit_permission

        has_view_permission = self.has_view_permission(request.user.username, obj.space_id, obj.id, request.token)
        return has_view_permission or has_edit_permission


class ScopePermission(BaseTokenPermission):
    def get_resource_type(self):
        return "SCOPE"

    def has_permission(self, request, view):
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

    def has_object_permission(self, request, view, obj):
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

        has_view_permission = self.has_view_permission(request.user.username, obj.space_id, obj.id, request.token)
        return has_view_permission


class TemplateMockPermission(BaseMockTokenPermission):
    def has_object_permission(self, request, view, obj):
        return self.has_mock_permission(request.user.username, obj.space_id, obj.id, request.token)


class TemplateRelatedResourcePermission(BaseMockTokenPermission):
    EDIT_PERMISSION = "edit"
    VIEW_PERMISSION = "view"
    MOCK_PERMISSION = "mock"
    DEFAULT_PERMISSION = VIEW_PERMISSION

    def get_resource_type(self):
        return "TEMPLATE"

    def get_action_perm(self, view):
        return getattr(view, "PERM_MAPPINGS", {}).get(
            view.action, getattr(view, "DEFAULT_PERMISSION", self.DEFAULT_PERMISSION)
        )

    def has_permission(self, request, view):
        data = request.query_params or request.data
        ser = TemplateRelatedResourceSerializer(data=data)
        ser.is_valid(raise_exception=True)
        space_id, template_id = ser.validated_data["space_id"], ser.validated_data["template_id"]
        action_perm = self.get_action_perm(view)
        return getattr(self, f"has_{action_perm}_permission")(
            request.user.username, space_id, template_id, request.token
        )
