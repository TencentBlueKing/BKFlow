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
from bkflow.template.permissions import TemplateRelatedResourcePermission
from bkflow.template.views.debug import DebugViewSet


@pytest.mark.django_db
class TestDebugTokenPermission:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.permission = TemplateRelatedResourcePermission()

    def _request(self, token):
        request = self.factory.get("/debug/context/")
        request.user = MagicMock(username="testuser")
        request.token = token
        request.query_params = {"space_id": "1", "template_id": "407"}
        request.data = {}
        return request

    def _create_token(self, token, permission_type, resource_id="407"):
        Token.objects.create(
            token=token,
            space_id=1,
            user="testuser",
            resource_type=ResourceType.TEMPLATE.value,
            resource_id=resource_id,
            permission_type=permission_type,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

    @pytest.mark.parametrize("action", ["context", "input_schema", "history", "reset_impact"])
    def test_mock_token_can_access_debug_read_action(self, action):
        self._create_token("mock_token", PermissionType.MOCK.value)
        view = DebugViewSet()
        view.action = action

        assert self.permission.has_permission(self._request("mock_token"), view) is True

    @pytest.mark.parametrize("action", ["global_run", "reset", "terminate", "step_run", "node_mock", "context_var"])
    def test_view_token_cannot_access_debug_write_action(self, action):
        self._create_token("view_token", PermissionType.VIEW.value)
        view = DebugViewSet()
        view.action = action

        assert self.permission.has_permission(self._request("view_token"), view) is False

    def test_mock_token_cannot_access_another_template(self):
        self._create_token("other_template_token", PermissionType.MOCK.value, resource_id="408")
        view = DebugViewSet()
        view.action = "context"

        assert self.permission.has_permission(self._request("other_template_token"), view) is False
