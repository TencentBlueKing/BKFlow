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
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.template.serializers.template import TemplateRelatedResourceSerializer


class TemplateResourceTargetMixin:
    """解析对象级模板资源鉴权所需的 (space_id, template_id)。"""

    @staticmethod
    def get_resource_target(obj):
        """快照不存储空间信息，鉴权坐标取自其所属模板；资源无效时返回 None。"""
        if isinstance(obj, TemplateSnapshot):
            template = Template.objects.filter(id=obj.template_id).first()
            if template is None:
                return None
            return template.space_id, template.id
        space_id = getattr(obj, "space_id", None)
        if space_id is None:
            return None
        return space_id, obj.id


class TemplatePermission(TemplateResourceTargetMixin, BaseTokenPermission):
    def get_resource_type(self):
        return "TEMPLATE"

    def has_permission(self, request, view):
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

    def has_object_permission(self, request, view, obj):
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False

        target = self.get_resource_target(obj)
        if target is None:
            return False
        space_id, template_id = target

        has_edit_permission = self.has_edit_permission(
            request.user.username,
            space_id,
            template_id,
            request.token,
            request=request,
            target_resource_type="TEMPLATE",
        )

        if view.action in view.EDIT_ABOVE_ACTIONS:
            return has_edit_permission

        has_view_permission = self.has_view_permission(
            request.user.username,
            space_id,
            template_id,
            request.token,
            request=request,
            target_resource_type="TEMPLATE",
        )
        return has_view_permission or has_edit_permission


class ScopePermission(TemplateResourceTargetMixin, BaseTokenPermission):
    def get_resource_type(self):
        return "SCOPE"

    def has_permission(self, request, view):
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        target = self.get_resource_target(obj)
        if target is None:
            return False
        space_id, template_id = target

        has_mock_permission = self.has_mock_permission(
            request.user.username,
            space_id,
            template_id,
            request.token,
            request=request,
            target_resource_type="TEMPLATE",
        )
        if view.action in view.MOCK_ABOVE_ACTIONS:
            return has_mock_permission

        has_edit_permission = self.has_edit_permission(
            request.user.username,
            space_id,
            template_id,
            request.token,
            request=request,
            target_resource_type="TEMPLATE",
        )
        if view.action in view.EDIT_ABOVE_ACTIONS:
            return has_edit_permission or has_mock_permission

        has_view_permission = self.has_view_permission(
            request.user.username,
            space_id,
            template_id,
            request.token,
            request=request,
            target_resource_type="TEMPLATE",
        )
        has_operate_permission = False
        if view.action in ["preview_task_tree"]:
            has_operate_permission = self.has_operate_permission(
                request.user.username,
                space_id,
                template_id,
                request.token,
                request=request,
                target_resource_type="TEMPLATE",
            )
        return has_view_permission or has_edit_permission or has_operate_permission or has_mock_permission


class TemplateMockPermission(TemplateResourceTargetMixin, BaseMockTokenPermission):
    def has_object_permission(self, request, view, obj):
        target = self.get_resource_target(obj)
        if target is None:
            return False
        space_id, template_id = target
        return self.has_mock_permission(
            request.user.username,
            space_id,
            template_id,
            request.token,
            request=request,
            target_resource_type="TEMPLATE",
        )


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
        action_perms = self.get_action_perm(view)
        if isinstance(action_perms, str):
            action_perms = (action_perms,)
        template_permission = any(
            getattr(self, f"has_{action_perm}_permission")(
                request.user.username,
                space_id,
                template_id,
                request.token,
                request=request,
                target_resource_type="TEMPLATE",
            )
            for action_perm in action_perms
        )
        if not template_permission:
            return self.has_scope_mock_permission(
                request.user.username,
                space_id,
                template_id,
                request.token,
                request=request,
                target_resource_type="TEMPLATE",
            )
        return template_permission
