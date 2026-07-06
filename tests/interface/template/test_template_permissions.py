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
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from bkflow.permission.models import PermissionType, ResourceType, Token
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.template.permissions import TemplateRelatedResourcePermission
from bkflow.template.views.debug import DebugViewSet


@pytest.mark.django_db
class TestTemplateRelatedResourcePermission:
    """模板关联资源 token 权限测试"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.permission = TemplateRelatedResourcePermission()

    def _make_request(self, token):
        request = self.factory.get("/debug/input_schema/", {"space_id": 1, "template_id": 100})
        request.query_params = request.GET
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = token
        return request

    def _make_view(self, action, required_perm):
        view = MagicMock()
        view.action = action
        view.DEFAULT_PERMISSION = TemplateRelatedResourcePermission.VIEW_PERMISSION
        view.PERM_MAPPINGS = {action: required_perm}
        return view

    def _make_template(self):
        snapshot = TemplateSnapshot.create_snapshot({"activities": {}, "constants": {}}, "testuser", "1.0.0")
        template = Template.objects.create(
            id=100,
            space_id=1,
            name="debug template",
            snapshot_id=snapshot.id,
            scope_type="project",
            scope_value="abc",
        )
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])
        return template

    def _make_scope_token(self, token, permission_type):
        Token.objects.create(
            token=token,
            space_id=1,
            user="testuser",
            resource_type=ResourceType.SCOPE.value,
            resource_id="project_abc",
            permission_type=permission_type,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

    def test_scope_view_token_can_access_view_debug_resource(self):
        """SCOPE VIEW token 可访问调试只读资源"""
        self._make_template()
        self._make_scope_token("scope_view_token", PermissionType.VIEW.value)

        assert self.permission.has_permission(
            self._make_request("scope_view_token"),
            self._make_view("input_schema", TemplateRelatedResourcePermission.VIEW_PERMISSION),
        )

    def test_scope_edit_token_can_access_edit_debug_resource(self):
        """SCOPE EDIT token 可访问调试编辑级资源"""
        self._make_template()
        self._make_scope_token("scope_edit_token", PermissionType.EDIT.value)

        assert self.permission.has_permission(
            self._make_request("scope_edit_token"),
            self._make_view("edit_related", TemplateRelatedResourcePermission.EDIT_PERMISSION),
        )

    def test_scope_view_token_cannot_access_mock_debug_resource(self):
        """SCOPE VIEW token 不能访问调试执行资源"""
        self._make_template()
        self._make_scope_token("scope_view_no_mock_token", PermissionType.VIEW.value)

        assert not self.permission.has_permission(
            self._make_request("scope_view_no_mock_token"),
            self._make_view("global_run", TemplateRelatedResourcePermission.MOCK_PERMISSION),
        )


class TestDebugViewSetPermissionMappings:
    """调试接口权限映射测试"""

    def test_context_and_history_require_mock_permission(self):
        """调试上下文和历史包含调试态数据，需 MOCK 权限"""
        assert DebugViewSet.PERM_MAPPINGS["context"] == TemplateRelatedResourcePermission.MOCK_PERMISSION
        assert DebugViewSet.PERM_MAPPINGS["history"] == TemplateRelatedResourcePermission.MOCK_PERMISSION

    def test_schema_and_reset_impact_keep_view_permission(self):
        """输入 schema 和 reset 影响分析仍是只读结构信息"""
        assert DebugViewSet.PERM_MAPPINGS["input_schema"] == TemplateRelatedResourcePermission.VIEW_PERMISSION
        assert DebugViewSet.PERM_MAPPINGS["reset_impact"] == TemplateRelatedResourcePermission.VIEW_PERMISSION
