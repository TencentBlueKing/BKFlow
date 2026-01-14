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
from unittest import mock
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from bkflow.interface.task.permissions import (
    ScopePermission,
    TaskMockTokenPermission,
    TaskTokenPermission,
)
from bkflow.permission.models import PermissionType, ResourceType, Token


@pytest.mark.django_db
class TestTaskTokenPermission:
    """Test TaskTokenPermission class"""

    def setup_method(self):
        self.permission = TaskTokenPermission()
        self.factory = APIRequestFactory()

    def test_get_resource_type(self):
        """Test get_resource_type returns TASK"""
        assert self.permission.get_resource_type() == "TASK"

    def test_has_operate_permission(self):
        """Test has_operate_permission method"""
        # Create a valid token
        token_obj = Token.objects.create(
            token="test_token_123",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.OPERATE.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        result = self.permission.has_operate_permission("testuser", 1, "123", "test_token_123")
        assert result is True

        # Test with wrong token
        result = self.permission.has_operate_permission("testuser", 1, "123", "wrong_token")
        assert result is False

        # Test with expired token
        token_obj.expired_time = timezone.now() - timezone.timedelta(hours=1)
        token_obj.save()
        result = self.permission.has_operate_permission("testuser", 1, "123", "test_token_123")
        assert result is False

    def test_has_permission_no_task_id(self):
        """Test has_permission when task_id is None"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token"

        view = MagicMock()
        view.kwargs = {}
        view.action = "get_task_detail"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is False

    def test_has_permission_mock_above_action(self):
        """Test has_permission when action is in MOCK_ABOVE_ACTIONS"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "get_task_mock_data"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is False

    def test_has_permission_operate_above_action_with_permission(self):
        """Test has_permission when action is in OPERATE_ABOVE_ACTIONS and has operate permission"""
        # Create a valid token with operate permission
        Token.objects.create(
            token="test_token_operate",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.OPERATE.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token_operate"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "operate_task"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is True

    def test_has_permission_operate_above_action_without_permission(self):
        """Test has_permission when action is in OPERATE_ABOVE_ACTIONS but no operate permission"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token_no_permission"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "operate_task"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is False

    def test_has_permission_view_action_with_view_permission(self):
        """Test has_permission when action is view and has view permission"""
        # Create a valid token with view permission
        Token.objects.create(
            token="test_token_view",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token_view"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "get_task_detail"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is True

    def test_has_permission_view_action_with_operate_permission(self):
        """Test has_permission when action is view and has operate permission"""
        # Create a valid token with operate permission
        Token.objects.create(
            token="test_token_operate_view",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.OPERATE.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token_operate_view"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "get_task_detail"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is True

    def test_has_permission_view_action_without_permission(self):
        """Test has_permission when action is view but no permission"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token_no_permission"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "get_task_detail"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is False


@pytest.mark.django_db
class TestScopePermission:
    """Test ScopePermission class"""

    def setup_method(self):
        self.permission = ScopePermission()
        self.factory = APIRequestFactory()

    def test_get_resource_type(self):
        """Test get_resource_type returns SCOPE"""
        assert self.permission.get_resource_type() == "SCOPE"

    def test_has_operate_permission(self):
        """Test has_operate_permission method"""
        # Create a valid token
        Token.objects.create(
            token="test_token_scope_123",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.SCOPE.value,
            resource_id="project_123",
            permission_type=PermissionType.OPERATE.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        result = self.permission.has_operate_permission("testuser", 1, "project_123", "test_token_scope_123")
        assert result is True

        # Test with wrong token
        result = self.permission.has_operate_permission("testuser", 1, "project_123", "wrong_token")
        assert result is False

    def test_has_permission_no_task_id(self):
        """Test has_permission when task_id is None"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token"

        view = MagicMock()
        view.kwargs = {}
        view.action = "get_task_detail"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is False

    def test_has_permission_mock_above_action(self):
        """Test has_permission when action is in MOCK_ABOVE_ACTIONS"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "get_task_mock_data"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is False

    def test_has_permission_operate_above_action_with_permission(self):
        """Test has_permission when action is in OPERATE_ABOVE_ACTIONS and has operate permission"""
        # Create a valid token with operate permission
        Token.objects.create(
            token="test_token_scope_operate",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.SCOPE.value,
            resource_id="123",
            permission_type=PermissionType.OPERATE.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token_scope_operate"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "operate_task"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is True

    def test_has_permission_view_action_with_view_permission(self):
        """Test has_permission when action is view and has view permission"""
        # Create a valid token with view permission
        Token.objects.create(
            token="test_token_scope_view",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.SCOPE.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token_scope_view"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "get_task_detail"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is True

    def test_has_permission_view_action_without_permission(self):
        """Test has_permission when action is view but no permission"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token_no_permission"

        view = MagicMock()
        view.kwargs = {"task_id": "123"}
        view.action = "get_task_detail"
        view.MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
        view.OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]

        result = self.permission.has_permission(request, view)
        assert result is False


@pytest.mark.django_db
class TestTaskMockTokenPermission:
    """Test TaskMockTokenPermission class"""

    def setup_method(self):
        self.permission = TaskMockTokenPermission()
        self.factory = APIRequestFactory()

    def test_has_permission_no_task_id(self):
        """Test has_permission when task_id is None"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.token = "test_token"

        view = MagicMock()
        view.kwargs = {}

        result = self.permission.has_permission(request, view)
        assert result is False

    @mock.patch("bkflow.interface.task.permissions.TaskComponentClient")
    def test_has_permission_no_space_id(self, mock_client_class):
        """Test has_permission when space_id is None"""
        request = self.factory.get("/task/")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.user.is_superuser = False
        request.token = "test_token"
        request.query_params = {}
        request.data = {}

        view = MagicMock()
        view.kwargs = {"task_id": "123"}

        result = self.permission.has_permission(request, view)
        assert result is False

    @mock.patch("bkflow.interface.task.permissions.TaskComponentClient")
    def test_has_permission_get_task_detail_failed(self, mock_client_class):
        """Test has_permission when get_task_detail returns result=False"""
        mock_client = mock.Mock()
        mock_client.get_task_detail.return_value = {"result": False, "message": "Task not found"}
        mock_client_class.return_value = mock_client

        request = self.factory.get("/task/?space_id=1")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.user.is_superuser = False
        request.token = "test_token"
        request.query_params = {"space_id": "1"}
        request.data = {}

        view = MagicMock()
        view.kwargs = {"task_id": "123"}

        result = self.permission.has_permission(request, view)
        assert result is False

    @mock.patch("bkflow.interface.task.permissions.TaskComponentClient")
    def test_has_permission_success(self, mock_client_class):
        """Test has_permission when everything is correct"""
        # Create a valid token with mock permission
        Token.objects.create(
            token="test_token_mock",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.TEMPLATE.value,
            resource_id="456",
            permission_type=PermissionType.MOCK.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": "123", "template_id": "456", "name": "Test Task", "create_method": "MOCK"},
        }
        mock_client_class.return_value = mock_client

        request = self.factory.get("/task/?space_id=1")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.user.is_superuser = False
        request.token = "test_token_mock"
        request.query_params = {"space_id": "1"}
        request.data = {}

        view = MagicMock()
        view.kwargs = {"task_id": "123"}

        result = self.permission.has_permission(request, view)
        assert result is True

    @mock.patch("bkflow.interface.task.permissions.TaskComponentClient")
    def test_has_permission_no_mock_permission(self, mock_client_class):
        """Test has_permission when no mock permission"""
        mock_client = mock.Mock()
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": "123", "template_id": "456", "name": "Test Task"},
        }
        mock_client_class.return_value = mock_client

        request = self.factory.get("/task/?space_id=1")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.user.is_superuser = False
        request.token = "test_token_no_permission"
        request.query_params = {"space_id": "1"}
        request.data = {}

        view = MagicMock()
        view.kwargs = {"task_id": "123"}

        result = self.permission.has_permission(request, view)
        assert result is False

    @mock.patch("bkflow.interface.task.permissions.TaskComponentClient")
    def test_has_permission_space_id_from_data(self, mock_client_class):
        """Test has_permission when space_id comes from request.data"""
        # Create a valid token with mock permission
        Token.objects.create(
            token="test_token_mock_data",
            space_id=1,
            user="testuser",
            resource_type=ResourceType.TEMPLATE.value,
            resource_id="456",
            permission_type=PermissionType.MOCK.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": "123", "template_id": "456", "name": "Test Task", "create_method": "MOCK"},
        }
        mock_client_class.return_value = mock_client

        request = self.factory.post("/task/", {"space_id": 1}, format="json")
        request.user = MagicMock()
        request.user.username = "testuser"
        request.user.is_superuser = False
        request.token = "test_token_mock_data"
        request.query_params = {}
        request.data = {"space_id": 1}

        view = MagicMock()
        view.kwargs = {"task_id": "123"}

        result = self.permission.has_permission(request, view)
        assert result is True
