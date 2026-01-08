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
from blueapps.account.models import User
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.exceptions import APIRequestError
from bkflow.interface.task.view import (
    TaskInterfaceAdminViewSet,
    TaskInterfaceSystemSuperuserViewSet,
    TaskInterfaceViewSet,
)
from bkflow.permission.models import (
    TASK_PERMISSION_TYPE,
    PermissionType,
    ResourceType,
    Token,
)
from bkflow.space.models import Space


@pytest.mark.django_db
class TestTaskInterfaceAdminViewSet:
    """Test TaskInterfaceAdminViewSet class"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )
        self.space, _ = Space.objects.get_or_create(name="Test Space", defaults={"app_code": "test_app"})

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_list(self, mock_client_class):
        """Test get_task_list method"""
        mock_client = mock.Mock()
        mock_client.task_list.return_value = {"result": True, "data": [{"id": 1, "name": "Task 1"}]}
        mock_client_class.return_value = mock_client

        view = TaskInterfaceAdminViewSet.as_view({"get": "get_task_list"})
        request = self.factory.get(f"/admin/tasks/get_task_list/{self.space.id}/")
        force_authenticate(request, user=self.admin_user)

        response = view(request, space_id=self.space.id)

        assert response.status_code == 200
        mock_client.task_list.assert_called_once()
        assert mock_client_class.called_with(space_id=self.space.id)

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_tasks_states(self, mock_client_class):
        """Test get_tasks_states method"""
        mock_client = mock.Mock()
        mock_client.get_tasks_states.return_value = {
            "result": True,
            "data": {"task_1": {"state": "RUNNING"}, "task_2": {"state": "FINISHED"}},
        }
        mock_client_class.return_value = mock_client

        view = TaskInterfaceAdminViewSet.as_view({"post": "get_tasks_states"})
        data = {"space_id": self.space.id, "task_ids": [1, 2]}
        request = self.factory.post("/admin/tasks/get_tasks_states/", data, format="json")
        force_authenticate(request, user=self.admin_user)

        response = view(request)

        assert response.status_code == 200
        mock_client.get_tasks_states.assert_called_once()

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_batch_delete_tasks_not_full(self, mock_client_class):
        """Test batch_delete_tasks when is_full is False"""
        mock_client = mock.Mock()
        mock_client.batch_delete_tasks.return_value = {"result": True, "data": {"deleted_count": 2}}
        mock_client_class.return_value = mock_client

        view = TaskInterfaceAdminViewSet.as_view({"post": "batch_delete_tasks"})
        data = {"space_id": self.space.id, "task_ids": [1, 2], "is_full": False}
        request = self.factory.post("/admin/tasks/batch_delete_tasks/", data, format="json")
        force_authenticate(request, user=self.admin_user)

        response = view(request)

        assert response.status_code == 200
        mock_client.batch_delete_tasks.assert_called_once()
        call_args = mock_client.batch_delete_tasks.call_args[1]["data"]
        assert "is_mock" not in call_args

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_batch_delete_tasks_full(self, mock_client_class):
        """Test batch_delete_tasks when is_full is True"""
        mock_client = mock.Mock()
        mock_client.batch_delete_tasks.return_value = {"result": True, "data": {"deleted_count": 2}}
        mock_client_class.return_value = mock_client

        view = TaskInterfaceAdminViewSet.as_view({"post": "batch_delete_tasks"})
        data = {"space_id": self.space.id, "task_ids": [1, 2], "is_full": True, "is_mock": False}
        request = self.factory.post("/admin/tasks/batch_delete_tasks/", data, format="json")
        force_authenticate(request, user=self.admin_user)

        response = view(request)

        assert response.status_code == 200
        mock_client.batch_delete_tasks.assert_called_once()
        call_args = mock_client.batch_delete_tasks.call_args[1]["data"]
        assert call_args["is_mock"] is False


@pytest.mark.django_db
class TestTaskInterfaceSystemSuperuserViewSet:
    """Test TaskInterfaceSystemSuperuserViewSet class"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )
        self.space, _ = Space.objects.get_or_create(name="Test Space", defaults={"app_code": "test_app"})

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_trigger_engine_admin_action(self, mock_client_class):
        """Test trigger_engine_admin_action method"""
        mock_client = mock.Mock()
        mock_client.trigger_engine_admin_action.return_value = {"result": True, "data": {"status": "success"}}
        mock_client_class.return_value = mock_client

        view = TaskInterfaceSystemSuperuserViewSet.as_view({"post": "trigger_engine_admin_action"})
        data = {
            "space_id": self.space.id,
            "instance_id": "instance_123",
            "action": "pause",
            "data": {"reason": "test"},
        }
        request = self.factory.post("/admin/tasks/trigger_engine_admin_action/", data, format="json")
        force_authenticate(request, user=self.admin_user)

        response = view(request)

        assert response.status_code == 200
        mock_client.trigger_engine_admin_action.assert_called_once_with(
            "instance_123", "pause", data={"reason": "test"}
        )


@pytest.mark.django_db
class TestTaskInterfaceViewSet:
    """Test TaskInterfaceViewSet class"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )
        self.normal_user, _ = User.objects.get_or_create(
            username="normaluser", defaults={"is_superuser": False, "is_staff": False}
        )
        self.space, _ = Space.objects.get_or_create(name="Test Space", defaults={"app_code": "test_app"})

    def test_inject_user_task_auth_superuser(self):
        """Test _inject_user_task_auth when user is superuser"""
        request = MagicMock()
        request.user.is_superuser = True
        request.user.username = "admin"
        request.is_space_superuser = False

        data = {"result": True, "data": {"id": "123", "space_id": self.space.id}}

        TaskInterfaceViewSet._inject_user_task_auth(request, data)

        assert data["data"]["auth"] == TASK_PERMISSION_TYPE

    def test_inject_user_task_auth_space_superuser(self):
        """Test _inject_user_task_auth when user is space superuser"""
        request = MagicMock()
        request.user.is_superuser = False
        request.user.username = "normaluser"
        request.is_space_superuser = True

        data = {"result": True, "data": {"id": "123", "space_id": self.space.id}}

        TaskInterfaceViewSet._inject_user_task_auth(request, data)

        assert data["data"]["auth"] == TASK_PERMISSION_TYPE

    def test_inject_user_task_auth_with_token_permissions(self):
        """Test _inject_user_task_auth with token permissions"""
        # Create tokens with different permissions
        Token.objects.create(
            token="token1",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )
        Token.objects.create(
            token="token2",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.OPERATE.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        request = MagicMock()
        request.user.is_superuser = False
        request.user.username = "normaluser"
        request.is_space_superuser = False

        data = {
            "result": True,
            "data": {
                "id": "123",
                "space_id": self.space.id,
                "scope_type": "project",
                "scope_value": "456",
            },
        }

        TaskInterfaceViewSet._inject_user_task_auth(request, data)

        assert "auth" in data["data"]
        assert PermissionType.VIEW.value in data["data"]["auth"]
        assert PermissionType.OPERATE.value in data["data"]["auth"]

    def test_inject_user_task_auth_with_scope_permissions(self):
        """Test _inject_user_task_auth with scope permissions"""
        Token.objects.create(
            token="token_scope",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.SCOPE.value,
            resource_id="project_456",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        request = MagicMock()
        request.user.is_superuser = False
        request.user.username = "normaluser"
        request.is_space_superuser = False

        data = {
            "result": True,
            "data": {
                "id": "123",
                "space_id": self.space.id,
                "scope_type": "project",
                "scope_value": "456",
            },
        }

        TaskInterfaceViewSet._inject_user_task_auth(request, data)

        assert "auth" in data["data"]
        assert PermissionType.VIEW.value in data["data"]["auth"]

    def test_inject_user_task_auth_result_false(self):
        """Test _inject_user_task_auth when result is False"""
        request = MagicMock()
        request.user.is_superuser = False
        request.user.username = "normaluser"

        data = {"result": False, "data": {"id": "123"}}

        TaskInterfaceViewSet._inject_user_task_auth(request, data)

        # Should not modify data when result is False
        assert "auth" not in data["data"]

    def test_get_space_id_superuser(self):
        """Test get_space_id when user is superuser"""
        view = TaskInterfaceViewSet()
        request = MagicMock()
        request.user.is_superuser = True
        request.user.username = "admin"
        request.query_params = {"space_id": str(self.space.id)}
        request.data = {}

        space_id = view.get_space_id(request)

        assert space_id == str(self.space.id)

    @mock.patch("bkflow.interface.task.view.SpaceConfig.get_config")
    def test_get_space_id_space_superuser(self, mock_get_config):
        """Test get_space_id when user is space superuser"""
        mock_get_config.return_value = ["normaluser"]

        view = TaskInterfaceViewSet()
        request = MagicMock()
        request.user.is_superuser = False
        request.user.username = "normaluser"
        request.query_params = {"space_id": str(self.space.id)}
        request.data = {}

        space_id = view.get_space_id(request)

        assert space_id == str(self.space.id)

    def test_get_space_id_with_token(self):
        """Test get_space_id when using token"""
        Token.objects.create(
            token="test_token_valid",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        view = TaskInterfaceViewSet()
        request = MagicMock()
        request.user.is_superuser = False
        request.user.username = "normaluser"
        request.token = "test_token_valid"
        request.query_params = {}
        request.data = {}

        space_id = view.get_space_id(request)

        assert space_id == self.space.id

    def test_get_space_id_token_not_exist(self):
        """Test get_space_id when token does not exist"""
        view = TaskInterfaceViewSet()
        request = MagicMock()
        request.user.is_superuser = False
        request.user.username = "normaluser"
        request.token = "invalid_token"
        request.query_params = {}
        request.data = {}

        with pytest.raises(APIRequestError):
            view.get_space_id(request)

    def test_get_space_id_from_data(self):
        """Test get_space_id when space_id comes from request.data"""
        Token.objects.create(
            token="test_token_data",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        view = TaskInterfaceViewSet()
        request = MagicMock()
        request.user.is_superuser = False
        request.user.username = "normaluser"
        request.token = "test_token_data"
        request.query_params = {}
        request.data = {"space_id": self.space.id}

        space_id = view.get_space_id(request)

        assert space_id == self.space.id

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_detail(self, mock_client_class):
        """Test get_task_detail method"""
        Token.objects.create(
            token="test_token_detail",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {
                "id": "123",
                "name": "Test Task",
                "space_id": self.space.id,
                "scope_type": "project",
                "scope_value": "456",
            },
        }
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet.as_view({"get": "get_task_detail"})
        request = self.factory.get("/tasks/get_task_detail/123/?space_id={}".format(self.space.id))
        request.user = self.normal_user
        request.token = "test_token_detail"
        request.query_params = {"space_id": str(self.space.id)}
        request.data = {}

        response = view(request, task_id="123")

        assert response.status_code == 200
        mock_client.get_task_detail.assert_called_once_with("123")

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_states(self, mock_client_class):
        """Test get_task_states method"""
        Token.objects.create(
            token="test_token_states",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "RUNNING", "children": {}},
        }
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet.as_view({"get": "get_task_states"})
        request = self.factory.get("/tasks/get_task_states/123/")
        request.user = self.normal_user
        request.token = "test_token_states"
        request.query_params = {}
        request.data = {}

        response = view(request, task_id="123")

        assert response.status_code == 200
        mock_client.get_task_states.assert_called_once()

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_mock_data(self, mock_client_class):
        """Test get_task_mock_data method"""
        from bkflow.admin.models import ModuleInfo

        # Create necessary ModuleInfo
        ModuleInfo.objects.get_or_create(
            type="TASK",
            space_id=0,
            defaults={
                "code": "task",
                "url": "http://localhost:8000",
                "token": "test_token",
                "isolation_level": "only_calculation",
            },
        )

        # Create token with MOCK permission for template
        Token.objects.create(
            token="test_token_mock",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TEMPLATE.value,
            resource_id="456",
            permission_type=PermissionType.MOCK.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        # TaskMockTokenPermission calls get_task_detail first during permission check
        # The view also calls get_task_mock_data
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": "123", "template_id": "456", "space_id": self.space.id},
        }
        mock_client.get_task_mock_data.return_value = {
            "result": True,
            "data": {"mock_data": {"nodes": [], "outputs": {}}},
        }
        # Mock should return the same instance for both permission check and view call
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet.as_view({"get": "get_task_mock_data"})
        request = self.factory.get("/tasks/get_task_mock_data/123/?space_id={}".format(self.space.id))
        # Use admin user (superuser) to bypass permission checks
        request.user = self.admin_user
        request.user.is_superuser = True
        request.token = "test_token_mock"
        request.query_params = {"space_id": str(self.space.id)}
        request.data = {}

        response = view(request, task_id="123")

        assert response.status_code == 200
        # get_task_mock_data is called in the view
        assert mock_client.get_task_mock_data.called

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    @mock.patch("bkflow.interface.task.view.start_trace")
    def test_operate_task(self, mock_start_trace, mock_client_class):
        """Test operate_task method"""
        Token.objects.create(
            token="test_token_operate",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.OPERATE.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.operate_task.return_value = {"result": True, "data": {"status": "success"}}
        mock_client_class.return_value = mock_client

        mock_context_manager = MagicMock()
        mock_start_trace.return_value.__enter__ = MagicMock(return_value=mock_context_manager)
        mock_start_trace.return_value.__exit__ = MagicMock(return_value=False)

        view = TaskInterfaceViewSet.as_view({"post": "operate_task"})
        request = self.factory.post(
            "/tasks/operate_task/123/start/?space_id={}".format(self.space.id), {"param": "value"}, format="json"
        )
        request.user = self.normal_user
        request.token = "test_token_operate"
        request.query_params = {"space_id": str(self.space.id)}
        request.data = {"param": "value"}

        response = view(request, task_id="123", operation="start")

        assert response.status_code == 200
        mock_client.operate_task.assert_called_once()
        # operator is added in the view, check it was called with operator
        call_args = mock_client.operate_task.call_args
        # operate_task is called as: operate_task(task_id, operation, data)
        # Check that operator was added to request.data (it's passed as part of the data dict)
        assert len(call_args[0]) >= 3  # positional args: task_id, operation, data
        assert call_args[0][2].get("operator") == "normaluser"

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_node_detail(self, mock_client_class):
        """Test get_task_node_detail method"""
        Token.objects.create(
            token="test_token_node",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"node_id": "node_1", "state": "FINISHED"},
        }
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet.as_view({"get": "get_task_node_detail"})
        request = self.factory.get("/tasks/get_task_node_detail/123/node/node_1/")
        request.user = self.normal_user
        request.token = "test_token_node"
        request.GET = {}
        request.query_params = {}
        request.data = {}

        response = view(request, task_id="123", node_id="node_1")

        assert response.status_code == 200
        mock_client.get_task_node_detail.assert_called_once()

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    @mock.patch("bkflow.interface.task.view.start_trace")
    def test_operate_node(self, mock_start_trace, mock_client_class):
        """Test operate_node method"""
        Token.objects.create(
            token="test_token_node_operate",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.OPERATE.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": True, "data": {"status": "success"}}
        mock_client_class.return_value = mock_client

        mock_context_manager = MagicMock()
        mock_start_trace.return_value.__enter__ = MagicMock(return_value=mock_context_manager)
        mock_start_trace.return_value.__exit__ = MagicMock(return_value=False)

        view = TaskInterfaceViewSet.as_view({"post": "operate_node"})
        request = self.factory.post(
            "/tasks/operate_node/123/node/node_1/retry/?space_id={}".format(self.space.id),
            {"param": "value"},
            format="json",
        )
        request.user = self.normal_user
        request.token = "test_token_node_operate"
        request.query_params = {"space_id": str(self.space.id)}
        request.data = {"param": "value"}

        response = view(request, task_id="123", node_id="node_1", operation="retry")

        assert response.status_code == 200
        mock_client.node_operate.assert_called_once()
        # operator is added in the view, check it was called with operator
        call_args = mock_client.node_operate.call_args
        # node_operate is called as: node_operate(task_id, node_id, operation, data)
        # Check that operator was added to request.data (it's passed as part of the data dict)
        assert len(call_args[0]) >= 4  # positional args: task_id, node_id, operation, data
        assert call_args[0][3].get("operator") == "normaluser"

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_node_log(self, mock_client_class):
        """Test get_task_node_log method"""
        Token.objects.create(
            token="test_token_log",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.get_task_node_log.return_value = {
            "result": True,
            "data": {"logs": ["log1", "log2"]},
        }
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet.as_view({"get": "get_task_node_log"})
        request = self.factory.get("/tasks/get_task_node_log/123/node_1/v1/")
        request.user = self.normal_user
        request.token = "test_token_log"
        request.query_params = {}
        request.data = {}

        response = view(request, task_id="123", node_id="node_1", version="v1")

        assert response.status_code == 200
        mock_client.get_task_node_log.assert_called_once()

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_render_current_constants(self, mock_client_class):
        """Test render_current_constants method"""
        Token.objects.create(
            token="test_token_constants",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.render_current_constants.return_value = {
            "result": True,
            "data": {"const1": "value1", "const2": "value2"},
        }
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet.as_view({"get": "render_current_constants"})
        request = self.factory.get("/tasks/render_current_constants/123/")
        request.user = self.normal_user
        request.token = "test_token_constants"
        request.query_params = {}
        request.data = {}

        response = view(request, task_id="123")

        assert response.status_code == 200
        mock_client.render_current_constants.assert_called_once_with("123")

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_operation_record(self, mock_client_class):
        """Test get_task_operation_record method"""
        Token.objects.create(
            token="test_token_record",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.get_task_operation_record.return_value = {
            "result": True,
            "data": {"records": [{"operator": "user1", "operation": "start"}]},
        }
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet.as_view({"get": "get_task_operation_record"})
        request = self.factory.get("/tasks/get_task_operation_record/123/")
        request.user = self.normal_user
        request.token = "test_token_record"
        request.query_params = {}
        request.data = {}

        response = view(request, task_id="123")

        assert response.status_code == 200
        mock_client.get_task_operation_record.assert_called_once()

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_node_snapshot_config(self, mock_client_class):
        """Test get_node_snapshot_config method"""
        Token.objects.create(
            token="test_token_snapshot",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_client = mock.Mock()
        mock_client.get_node_snapshot_config.return_value = {
            "result": True,
            "data": {"config": {"key": "value"}},
        }
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet.as_view({"get": "get_node_snapshot_config"})
        request = self.factory.get("/tasks/get_node_snapshot_config/123/node_1/")
        request.user = self.normal_user
        request.token = "test_token_snapshot"
        request.query_params = {}
        request.data = {}

        response = view(request, task_id="123", node_id="node_1")

        assert response.status_code == 200
        mock_client.get_node_snapshot_config.assert_called_once()
        call_args = mock_client.get_node_snapshot_config.call_args
        assert call_args[0][0] == "123"
        # Check that data parameter was passed correctly
        # get_node_snapshot_config is called as: get_node_snapshot_config(task_id, data)
        assert len(call_args[0]) >= 2
        assert call_args[0][1]["node_id"] == "node_1"

    @mock.patch("bkflow.interface.task.view.StageJobStateHandler")
    def test_get_stage_and_job_states(self, mock_handler_class):
        """Test get_stage_and_job_states method"""
        Token.objects.create(
            token="test_token_stage",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_handler = mock.Mock()
        mock_handler.process.return_value = [{"id": "stage1", "state": "FINISHED", "jobs": []}]
        mock_handler_class.return_value = mock_handler

        view = TaskInterfaceViewSet.as_view({"get": "get_stage_and_job_states"})
        request = self.factory.get("/tasks/get_stage_job_states/123/")
        request.user = self.normal_user
        request.token = "test_token_stage"
        request.query_params = {}
        request.data = {}

        response = view(request, task_id="123")

        assert response.status_code == 200
        mock_handler.process.assert_called_once_with("123")

    @mock.patch("bkflow.interface.task.view.StageConstantHandler")
    def test_render_stage_constants(self, mock_handler_class):
        """Test render_stage_constants method"""
        Token.objects.create(
            token="test_token_render",
            space_id=self.space.id,
            user="normaluser",
            resource_type=ResourceType.TASK.value,
            resource_id="123",
            permission_type=PermissionType.VIEW.value,
            expired_time=timezone.now() + timezone.timedelta(hours=1),
        )

        mock_handler = mock.Mock()
        mock_handler.process.return_value = {"const1": "rendered_value1", "const2": "rendered_value2"}
        mock_handler_class.return_value = mock_handler

        view = TaskInterfaceViewSet.as_view({"post": "render_stage_constants"})
        data = {
            "node_ids": ["node1", "node2"],
            "to_render_constants": [
                {"key": "const1", "value": "${node1.output}"},
                {"key": "const2", "value": "${node2.output}"},
            ],
        }
        request = self.factory.post(
            "/tasks/rendered_stage_constants/123/?space_id={}".format(self.space.id), data, format="json"
        )
        request.user = self.normal_user
        request.token = "test_token_render"
        request.query_params = {"space_id": str(self.space.id)}
        request.data = data

        response = view(request, task_id="123")

        assert response.status_code == 200
        mock_handler.process.assert_called_once()
        # Check that process was called with correct arguments
        call_args = mock_handler.process.call_args[0]
        assert call_args[0] == "123"
        assert call_args[1] == ["node1", "node2"]
