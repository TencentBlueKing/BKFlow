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
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from bkflow.task.models import (
    EngineSpaceConfig,
    EngineSpaceConfigValueType,
    PeriodicTask,
    TaskInstance,
    TaskMockData,
    TaskOperationRecord,
)
from bkflow.task.views import PeriodicTaskViewSet, TaskInstanceViewSet
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestTaskInstanceViewSet:
    """测试 TaskInstanceViewSet 视图"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.factory = APIRequestFactory()

    def _start_task_instance(self, task_instance, executor="test_user"):
        """启动任务实例并设置必要的状态

        模拟真实的 TaskOperation.start() 操作，包括：
        1. 设置启动状态和时间
        2. 计算树信息

        Args:
            task_instance: 任务实例
            executor: 执行者
        """
        from django.utils import timezone

        # 模拟 TaskOperation.start() 的核心逻辑
        # 1. CAS 更新任务状态
        TaskInstance.objects.filter(id=task_instance.id, is_started=False).update(
            start_time=timezone.now(), is_started=True, executor=executor
        )

        # 2. 计算树信息（这是 start 方法中重要的一步）
        task_instance.refresh_from_db()
        task_instance.calculate_tree_info()

        return task_instance

    def _create_request_with_auth(self, method, path, data=None, space_id="1", from_superuser="0", **kwargs):
        """创建带认证的请求"""
        if method == "get":
            request = self.factory.get(path, data, **kwargs)
        elif method == "post":
            request = self.factory.post(path, data, format="json", **kwargs)
        elif method == "delete":
            request = self.factory.delete(path, data, format="json", **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")

        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        # 设置自定义 headers
        if space_id:
            request.META[f"HTTP_{settings.APP_INTERNAL_SPACE_ID_HEADER_KEY}"] = space_id
        if from_superuser:
            request.META[f"HTTP_{settings.APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY}"] = from_superuser

        return request

    def test_create_task_instance(self):
        """测试创建任务实例"""
        view = TaskInstanceViewSet.as_view({"post": "create"})
        pipeline_tree = build_default_pipeline_tree()
        data = {
            "space_id": 1,
            "pipeline_tree": pipeline_tree,
            "name": "test_task",
            "creator": "test_creator",
        }

        request = self._create_request_with_auth("post", "/task/", data)
        response = view(request)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "test_task"
        assert "parameters" in response.data["data"]

    def test_get_serializer_class_create(self):
        """测试 get_serializer_class 方法 - create action"""
        view = TaskInstanceViewSet()
        view.action = "create"
        from bkflow.task.serializers import CreateTaskInstanceSerializer

        assert view.get_serializer_class() == CreateTaskInstanceSerializer

    def test_get_serializer_class_retrieve(self):
        """测试 get_serializer_class 方法 - retrieve action"""
        view = TaskInstanceViewSet()
        view.action = "retrieve"
        from bkflow.task.serializers import RetrieveTaskInstanceSerializer

        assert view.get_serializer_class() == RetrieveTaskInstanceSerializer

    def test_get_serializer_class_default(self):
        """测试 get_serializer_class 方法 - 默认"""
        view = TaskInstanceViewSet()
        view.action = "list"
        from bkflow.task.serializers import TaskInstanceSerializer

        assert view.get_serializer_class() == TaskInstanceSerializer

    def test_task_response_wrapper_with_standard_fields(self):
        """测试 task_response_wrapper - 标准格式"""
        view = TaskInstanceViewSet()
        data = {"result": True, "data": {"test": "value"}, "message": "success"}
        result = view.task_response_wrapper(data)
        assert result == data

    def test_task_response_wrapper_without_standard_fields(self):
        """测试 task_response_wrapper - 非标准格式"""
        view = TaskInstanceViewSet()
        view.default_response_wrapper = lambda x: {"wrapped": x}
        data = {"custom": "data"}
        result = view.task_response_wrapper(data)
        assert result == {"wrapped": data}

    def test_batch_delete_tasks_by_ids(self):
        """测试批量删除指定任务"""
        task1 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task2 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        view = TaskInstanceViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": 1, "task_ids": [task1.id, task2.id], "is_full": False}

        request = self._create_request_with_auth("post", "/task/batch_delete_tasks/", data)
        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True

        task1.refresh_from_db()
        task2.refresh_from_db()
        assert task1.is_deleted is True
        assert task2.is_deleted is True

    def test_batch_delete_tasks_full_non_mock(self):
        """测试批量删除所有任务（包括 Mock 和非 Mock）- is_mock=False"""
        TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=build_default_pipeline_tree(), create_method="MOCK"
        )

        view = TaskInstanceViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": 1, "is_full": True, "is_mock": False}

        request = self._create_request_with_auth("post", "/task/batch_delete_tasks/", data)
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # 当 is_mock=False 时，所有任务都应该被删除
        all_tasks = TaskInstance.objects.filter(space_id=1, is_deleted=False)
        assert all_tasks.count() == 0

    def test_batch_delete_tasks_full_with_mock(self):
        """测试批量删除所有 Mock 任务"""
        TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=build_default_pipeline_tree(), create_method="MOCK"
        )

        view = TaskInstanceViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": 1, "is_full": True, "is_mock": True}

        request = self._create_request_with_auth("post", "/task/batch_delete_tasks/", data)
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        mock_tasks = TaskInstance.objects.filter(space_id=1, is_deleted=False, create_method="MOCK")
        assert mock_tasks.count() == 0

    @patch("bkflow.task.views.TaskOperation")
    def test_operate_task_start(self, mock_task_operation):
        """测试任务操作 - start"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        mock_operation = MagicMock()
        mock_operation.start.return_value = MagicMock(result=True, data={}, message="success")
        mock_task_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "operate"})
        request = self._create_request_with_auth("post", f"/task/{task_instance.id}/operate/start/", {})

        response = view(request, pk=task_instance.id, operation="start")
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.TaskOperation")
    @patch("bkflow.task.views.InterfaceModuleClient")
    def test_operate_task_pause(self, mock_interface_client, mock_task_operation):
        """测试任务操作 - pause"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        # 启动任务
        self._start_task_instance(task_instance)

        mock_operation = MagicMock()
        mock_operation.pause.return_value = MagicMock(result=True, data={}, message="success")
        mock_task_operation.return_value = mock_operation

        # Mock InterfaceModuleClient
        mock_interface_client.return_value.broadcast_task_events.return_value = MagicMock()

        view = TaskInstanceViewSet.as_view({"post": "operate"})
        request = self._create_request_with_auth("post", f"/task/{task_instance.id}/operate/pause/", {})

        response = view(request, pk=task_instance.id, operation="pause")
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.TaskOperation")
    @patch("bkflow.task.views.InterfaceModuleClient")
    def test_operate_task_resume(self, mock_interface_client, mock_task_operation):
        """测试任务操作 - resume"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        # 启动任务
        self._start_task_instance(task_instance)

        mock_operation = MagicMock()
        mock_operation.resume.return_value = MagicMock(result=True, data={}, message="success")
        mock_task_operation.return_value = mock_operation

        # Mock InterfaceModuleClient
        mock_interface_client.return_value.broadcast_task_events.return_value = MagicMock()

        view = TaskInstanceViewSet.as_view({"post": "operate"})
        request = self._create_request_with_auth("post", f"/task/{task_instance.id}/operate/resume/", {})

        response = view(request, pk=task_instance.id, operation="resume")
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.TaskOperation")
    @patch("bkflow.task.views.InterfaceModuleClient")
    def test_operate_task_revoke(self, mock_interface_client, mock_task_operation):
        """测试任务操作 - revoke"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        # 启动任务
        self._start_task_instance(task_instance)

        mock_operation = MagicMock()
        mock_operation.revoke.return_value = MagicMock(result=True, data={}, message="success")
        mock_task_operation.return_value = mock_operation

        # Mock InterfaceModuleClient
        mock_interface_client.return_value.broadcast_task_events.return_value = MagicMock()

        view = TaskInstanceViewSet.as_view({"post": "operate"})
        request = self._create_request_with_auth("post", f"/task/{task_instance.id}/operate/revoke/", {})

        response = view(request, pk=task_instance.id, operation="revoke")
        assert response.status_code == status.HTTP_200_OK

    def test_operate_task_invalid_operation(self):
        """测试任务操作 - 无效操作"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        view = TaskInstanceViewSet.as_view({"post": "operate"})
        request = self._create_request_with_auth("post", f"/task/{task_instance.id}/operate/invalid/", {})

        with pytest.raises(Exception):  # ValidationError
            view(request, pk=task_instance.id, operation="invalid")

    @patch("bkflow.task.views.TaskOperation")
    def test_operate_task_with_custom_operator(self, mock_task_operation):
        """测试任务操作 - 自定义操作者"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        mock_operation = MagicMock()
        mock_operation.start.return_value = MagicMock(result=True, data={}, message="success")
        mock_task_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "operate"})
        data = {"operator": "custom_operator"}
        request = self._create_request_with_auth("post", f"/task/{task_instance.id}/operate/start/", data)

        response = view(request, pk=task_instance.id, operation="start")
        assert response.status_code == status.HTTP_200_OK
        mock_operation.start.assert_called_once()

    @patch("bkflow.task.views.start_trace")
    @patch("bkflow.task.views.TaskNodeOperation")
    def test_node_operate_retry(self, mock_node_operation, mock_start_trace):
        """测试节点操作 - retry"""
        # Mock start_trace 的上下文管理器
        mock_start_trace.return_value.__enter__ = MagicMock()
        mock_start_trace.return_value.__exit__ = MagicMock()

        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=pipeline_tree, template_id=1, executor="admin"
        )
        # 启动任务
        self._start_task_instance(task_instance)

        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.retry.return_value = MagicMock(result=True, data={}, message="success")
        mock_node_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "node_operate"})
        request = self._create_request_with_auth("post", f"/task/{task_instance.id}/node_operate/{node_id}/retry/", {})

        response = view(request, pk=task_instance.id, node_id=node_id, operation="retry")
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.start_trace")
    @patch("bkflow.task.views.TaskNodeOperation")
    def test_node_operate_skip(self, mock_node_operation, mock_start_trace):
        """测试节点操作 - skip"""
        # Mock start_trace 的上下文管理器
        mock_start_trace.return_value.__enter__ = MagicMock()
        mock_start_trace.return_value.__exit__ = MagicMock()

        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=pipeline_tree, template_id=1, executor="admin"
        )
        # 启动任务
        self._start_task_instance(task_instance)

        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.skip.return_value = MagicMock(result=True, data={}, message="success")
        mock_node_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "node_operate"})
        request = self._create_request_with_auth("post", f"/task/{task_instance.id}/node_operate/{node_id}/skip/", {})

        response = view(request, pk=task_instance.id, node_id=node_id, operation="skip")
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.start_trace")
    @patch("bkflow.task.views.TaskNodeOperation")
    def test_node_operate_callback(self, mock_node_operation, mock_start_trace):
        """测试节点操作 - callback"""
        # Mock start_trace 的上下文管理器
        mock_start_trace.return_value.__enter__ = MagicMock()
        mock_start_trace.return_value.__exit__ = MagicMock()

        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=pipeline_tree, template_id=1, executor="admin"
        )
        # 启动任务
        self._start_task_instance(task_instance)

        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.callback.return_value = MagicMock(result=True, data={}, message="success")
        mock_node_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "node_operate"})
        request = self._create_request_with_auth(
            "post", f"/task/{task_instance.id}/node_operate/{node_id}/callback/", {}
        )

        response = view(request, pk=task_instance.id, node_id=node_id, operation="callback")
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.start_trace")
    @patch("bkflow.task.views.TaskNodeOperation")
    def test_node_operate_forced_fail(self, mock_node_operation, mock_start_trace):
        """测试节点操作 - forced_fail"""
        # Mock start_trace 的上下文管理器
        mock_start_trace.return_value.__enter__ = MagicMock()
        mock_start_trace.return_value.__exit__ = MagicMock()

        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=pipeline_tree, template_id=1, executor="admin"
        )
        # 启动任务
        self._start_task_instance(task_instance)

        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.forced_fail.return_value = MagicMock(result=True, data={}, message="success")
        mock_node_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "node_operate"})
        request = self._create_request_with_auth(
            "post", f"/task/{task_instance.id}/node_operate/{node_id}/forced_fail/", {}
        )

        response = view(request, pk=task_instance.id, node_id=node_id, operation="forced_fail")
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.start_trace")
    @patch("bkflow.task.views.TaskNodeOperation")
    def test_node_operate_skip_exg(self, mock_node_operation, mock_start_trace):
        """测试节点操作 - skip_exg"""
        # Mock start_trace 的上下文管理器
        mock_start_trace.return_value.__enter__ = MagicMock()
        mock_start_trace.return_value.__exit__ = MagicMock()

        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=pipeline_tree, template_id=1, executor="admin"
        )
        # 启动任务
        self._start_task_instance(task_instance)

        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.skip_exg.return_value = MagicMock(result=True, data={}, message="success")
        mock_node_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "node_operate"})
        request = self._create_request_with_auth(
            "post", f"/task/{task_instance.id}/node_operate/{node_id}/skip_exg/", {}
        )

        response = view(request, pk=task_instance.id, node_id=node_id, operation="skip_exg")
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.start_trace")
    @patch("bkflow.task.views.TaskNodeOperation")
    def test_node_operate_skip_cpg(self, mock_node_operation, mock_start_trace):
        """测试节点操作 - skip_cpg"""
        # Mock start_trace 的上下文管理器
        mock_start_trace.return_value.__enter__ = MagicMock()
        mock_start_trace.return_value.__exit__ = MagicMock()

        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=pipeline_tree, template_id=1, executor="admin"
        )
        # 启动任务
        self._start_task_instance(task_instance)

        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.skip_cpg.return_value = MagicMock(result=True, data={}, message="success")
        mock_node_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "node_operate"})
        request = self._create_request_with_auth(
            "post", f"/task/{task_instance.id}/node_operate/{node_id}/skip_cpg/", {}
        )

        response = view(request, pk=task_instance.id, node_id=node_id, operation="skip_cpg")
        assert response.status_code == status.HTTP_200_OK

    def test_node_operate_invalid_operation(self):
        """测试节点操作 - 无效操作"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        node_id = list(pipeline_tree["activities"].keys())[0]

        view = TaskInstanceViewSet.as_view({"post": "node_operate"})
        request = self._create_request_with_auth(
            "post", f"/task/{task_instance.id}/node_operate/{node_id}/invalid/", {}
        )

        with pytest.raises(Exception):  # ValidationError
            view(request, pk=task_instance.id, node_id=node_id, operation="invalid")

    @patch("bkflow.task.views.start_trace")
    @patch("bkflow.task.views.TaskNodeOperation")
    def test_node_operate_subprocess_retry(self, mock_node_operation, mock_start_trace):
        """测试子流程节点操作 - retry"""
        # Mock start_trace 的上下文管理器
        mock_start_trace.return_value.__enter__ = MagicMock()
        mock_start_trace.return_value.__exit__ = MagicMock()

        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=pipeline_tree, trigger_method="subprocess", template_id=1, executor="admin"
        )
        # 启动任务
        self._start_task_instance(task_instance)

        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.retry.return_value = MagicMock(result=True, data={}, message="success")
        mock_node_operation.return_value = mock_operation

        # Mock change_parent_task_node_state_to_running 方法
        with patch.object(task_instance.__class__, "change_parent_task_node_state_to_running") as mock_change_state:
            view = TaskInstanceViewSet.as_view({"post": "node_operate"})
            request = self._create_request_with_auth(
                "post", f"/task/{task_instance.id}/node_operate/{node_id}/retry/", {}
            )

            response = view(request, pk=task_instance.id, node_id=node_id, operation="retry")
            assert response.status_code == status.HTTP_200_OK
            mock_change_state.assert_called_once()

    @patch("bkflow.task.views.start_trace")
    @patch("bkflow.task.views.TaskNodeOperation")
    def test_node_operate_subprocess_skip(self, mock_node_operation, mock_start_trace):
        """测试子流程节点操作 - skip"""
        # Mock start_trace 的上下文管理器
        mock_start_trace.return_value.__enter__ = MagicMock()
        mock_start_trace.return_value.__exit__ = MagicMock()

        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=pipeline_tree, trigger_method="subprocess", template_id=1, executor="admin"
        )
        # 启动任务
        self._start_task_instance(task_instance)

        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.skip.return_value = MagicMock(result=True, data={}, message="success")
        mock_node_operation.return_value = mock_operation

        # Mock change_parent_task_node_state_to_running 方法
        with patch.object(task_instance.__class__, "change_parent_task_node_state_to_running") as mock_change_state:
            view = TaskInstanceViewSet.as_view({"post": "node_operate"})
            request = self._create_request_with_auth(
                "post", f"/task/{task_instance.id}/node_operate/{node_id}/skip/", {}
            )

            response = view(request, pk=task_instance.id, node_id=node_id, operation="skip")
            assert response.status_code == status.HTTP_200_OK
            mock_change_state.assert_called_once()

    @patch("bkflow.task.views.TaskOperation")
    def test_get_states(self, mock_task_operation):
        """测试获取任务状态"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        # 启动任务
        self._start_task_instance(task_instance)

        mock_operation = MagicMock()
        mock_operation.get_task_states.return_value = MagicMock(result=True, data={"state": "RUNNING"})
        mock_task_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"get": "get_states"})
        request = self._create_request_with_auth("get", f"/task/{task_instance.id}/get_states/")

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.TaskOperation")
    def test_get_tasks_states(self, mock_task_operation):
        """测试批量获取任务状态"""
        task1 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task2 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        # 启动任务
        self._start_task_instance(task1)
        self._start_task_instance(task2)

        mock_operation = MagicMock()
        mock_operation.get_task_states.return_value = MagicMock(result=True, data={"state": "RUNNING"})
        mock_task_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "get_tasks_states"})
        data = {"space_id": 1, "task_ids": [task1.id, task2.id]}
        request = self._create_request_with_auth("post", "/task/get_tasks_states/", data)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert task1.id in response.data["data"]
        assert task2.id in response.data["data"]

    @patch("bkflow.task.views.TaskOperation")
    def test_get_tasks_states_with_failure(self, mock_task_operation):
        """测试批量获取任务状态 - 部分失败"""
        task1 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        # 启动任务
        self._start_task_instance(task1)

        mock_operation = MagicMock()
        mock_operation.get_task_states.return_value = MagicMock(result=False, data={})
        mock_task_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "get_tasks_states"})
        data = {"space_id": 1, "task_ids": [task1.id]}
        request = self._create_request_with_auth("post", "/task/get_tasks_states/", data)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][task1.id]["state"] is None

    def test_get_task_mock_data_exists(self):
        """测试获取任务 Mock 数据 - 数据存在"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        mock_data = {"outputs": {"node1": {"output1": "value1"}}}
        TaskMockData.objects.create(taskflow_id=task_instance.id, data=mock_data)

        view = TaskInstanceViewSet.as_view({"get": "get_task_mock_data"})
        request = self._create_request_with_auth("get", f"/task/{task_instance.id}/get_task_mock_data/")

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["data"] == mock_data

    def test_get_task_mock_data_not_exists(self):
        """测试获取任务 Mock 数据 - 数据不存在"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        view = TaskInstanceViewSet.as_view({"get": "get_task_mock_data"})
        request = self._create_request_with_auth("get", f"/task/{task_instance.id}/get_task_mock_data/")

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == {}

    @patch("bkflow.task.views.TaskOperation")
    def test_render_current_constants(self, mock_task_operation):
        """测试渲染当前全局变量"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        mock_operation = MagicMock()
        mock_operation.render_current_constants.return_value = MagicMock(
            result=True, data={"var1": "value1"}, message="success"
        )
        mock_task_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"get": "render_current_constants"})
        request = self._create_request_with_auth("get", f"/task/{task_instance.id}/render_current_constants/")

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.TaskOperation")
    def test_render_context_with_node_outputs(self, mock_task_operation):
        """测试使用节点输出渲染上下文"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        node_id = list(pipeline_tree["activities"].keys())[0]

        mock_operation = MagicMock()
        mock_operation.render_context_with_node_outputs.return_value = MagicMock(
            result=True, data={"var1": "rendered_value"}, message="success"
        )
        mock_task_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "render_context_with_node_outputs"})
        data = {"node_ids": [node_id], "to_render_constants": ["var1", "var2"]}
        request = self._create_request_with_auth(
            "post", f"/task/{task_instance.id}/render_context_with_node_outputs/", data
        )

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK

    @patch("bkflow.task.views.NodeLogDataSourceFactory")
    def test_get_node_log_success(self, mock_log_factory):
        """测试获取节点日志 - 成功"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        node_id = list(pipeline_tree["activities"].keys())[0]
        version = "v1"

        mock_data_source = MagicMock()
        mock_data_source.fetch_node_logs.return_value = {
            "result": True,
            "message": "success",
            "data": {"logs": "log line 1\nlog line 2\n", "page_info": {"page": 1, "page_size": 100, "total": 2}},
        }
        mock_log_factory.return_value.data_source = mock_data_source

        view = TaskInstanceViewSet.as_view({"get": "get_node_log"})
        request = self._create_request_with_auth(
            "get",
            f"/task/{task_instance.id}/get_task_node_log/{node_id}/{version}/",
            {"page": 1, "page_size": 100},
        )

        response = view(request, pk=task_instance.id, node_id=node_id, version=version)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True
        assert "page" in response.data

    @patch("bkflow.task.views.NodeLogDataSourceFactory")
    def test_get_node_log_failure(self, mock_log_factory):
        """测试获取节点日志 - 失败"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        node_id = list(pipeline_tree["activities"].keys())[0]
        version = "v1"

        mock_data_source = MagicMock()
        mock_data_source.fetch_node_logs.return_value = {"result": False, "message": "fetch failed", "data": None}
        mock_log_factory.return_value.data_source = mock_data_source

        view = TaskInstanceViewSet.as_view({"get": "get_node_log"})
        request = self._create_request_with_auth(
            "get",
            f"/task/{task_instance.id}/get_task_node_log/{node_id}/{version}/",
            {"page": 1, "page_size": 100},
        )

        response = view(request, pk=task_instance.id, node_id=node_id, version=version)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is False
        assert response.data["message"] == "fetch failed"

    def test_get_task_operation_record_all(self):
        """测试获取任务操作记录 - 所有记录"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        node_id = list(pipeline_tree["activities"].keys())[0]

        TaskOperationRecord.objects.create(
            instance_id=task_instance.id,
            node_id=node_id,
            operate_type="retry",
            operate_source="api",
            operator="test_user",
        )
        TaskOperationRecord.objects.create(
            instance_id=task_instance.id, operate_type="start", operate_source="api", operator="test_user"
        )

        view = TaskInstanceViewSet.as_view({"get": "get_task_operation_record"})
        request = self._create_request_with_auth("get", f"/task/{task_instance.id}/get_task_operation_record/")

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True
        assert len(response.data["data"]) == 2

    def test_get_task_operation_record_with_node_id(self):
        """测试获取任务操作记录 - 指定节点"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        node_id = list(pipeline_tree["activities"].keys())[0]

        TaskOperationRecord.objects.create(
            instance_id=task_instance.id,
            node_id=node_id,
            operate_type="retry",
            operate_source="api",
            operator="test_user",
        )
        TaskOperationRecord.objects.create(
            instance_id=task_instance.id, operate_type="start", operate_source="api", operator="test_user"
        )

        view = TaskInstanceViewSet.as_view({"get": "get_task_operation_record"})
        request = self._create_request_with_auth(
            "get", f"/task/{task_instance.id}/get_task_operation_record/", {"node_id": node_id}
        )

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True
        assert len(response.data["data"]) == 1

    def test_get_node_snapshot_config_success(self):
        """测试获取节点配置快照 - 成功"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        node_id = list(pipeline_tree["activities"].keys())[0]

        view = TaskInstanceViewSet.as_view({"get": "get_node_snapshot_config"})
        request = self._create_request_with_auth(
            "get", f"/task/{task_instance.id}/get_node_snapshot_config/", {"node_id": node_id}
        )

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True
        assert response.data["data"] is not None

    def test_get_engine_config_simplified(self):
        """测试获取引擎配置 - 简化格式"""
        EngineSpaceConfig.objects.create(
            interface_config_id=1,
            name="config1",
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="value1",
            space_id=1,
        )
        EngineSpaceConfig.objects.create(
            interface_config_id=2,
            name="config2",
            value_type=EngineSpaceConfigValueType.JSON.value,
            json_value={"key": "value"},
            space_id=1,
        )

        view = TaskInstanceViewSet.as_view({"get": "get_engine_config"})
        request = self._create_request_with_auth(
            "get", "/task/get_engine_config/", {"interface_config_ids": [1, 2], "simplified": True}
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True
        assert len(response.data["data"]) == 2
        assert response.data["data"][0]["key"] == "config1"
        assert response.data["data"][0]["value"] == "value1"
        assert response.data["data"][1]["key"] == "config2"
        assert response.data["data"][1]["value"] == {"key": "value"}

    def test_get_engine_config_detailed(self):
        """测试获取引擎配置 - 详细格式"""
        EngineSpaceConfig.objects.create(
            interface_config_id=3,
            name="config3",
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="value3",
            space_id=1,
        )

        view = TaskInstanceViewSet.as_view({"get": "get_engine_config"})
        request = self._create_request_with_auth(
            "get", "/task/get_engine_config/", {"interface_config_ids": [3], "simplified": False}
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True
        assert len(response.data["data"]) == 1
        assert "interface_config_id" in response.data["data"][0]

    def test_upsert_engine_config_create(self):
        """测试创建引擎配置"""
        view = TaskInstanceViewSet.as_view({"post": "upsert_engine_config"})
        data = {
            "interface_config_id": 100,
            "name": "new_config",
            "value_type": EngineSpaceConfigValueType.TEXT.value,
            "text_value": "new_value",
            "space_id": 1,
        }
        request = self._create_request_with_auth("post", "/task/upsert_engine_config/", data)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True

        config = EngineSpaceConfig.objects.get(interface_config_id=100)
        assert config.name == "new_config"
        assert config.text_value == "new_value"

    def test_upsert_engine_config_update(self):
        """测试更新引擎配置"""
        config = EngineSpaceConfig.objects.create(
            interface_config_id=101,
            name="old_name",
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="old_value",
            space_id=1,
        )

        view = TaskInstanceViewSet.as_view({"post": "upsert_engine_config"})
        data = {
            "interface_config_id": 101,
            "name": "updated_name",
            "value_type": EngineSpaceConfigValueType.TEXT.value,
            "text_value": "updated_value",
            "space_id": 1,
        }
        request = self._create_request_with_auth("post", "/task/upsert_engine_config/", data)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True

        config.refresh_from_db()
        assert config.name == "updated_name"
        assert config.text_value == "updated_value"

    def test_delete_engine_config_success(self):
        """测试删除引擎配置 - 成功"""
        EngineSpaceConfig.objects.create(
            interface_config_id=102,
            name="config_to_delete_1",
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="value",
            space_id=1,
        )
        EngineSpaceConfig.objects.create(
            interface_config_id=103,
            name="config_to_delete_2",
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="value",
            space_id=1,
        )

        view = TaskInstanceViewSet.as_view({"delete": "delete_engine_config"})
        request = self._create_request_with_auth(
            "delete", "/task/delete_engine_config/", {"interface_config_ids": [102, 103], "simplified": False}
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True

        assert not EngineSpaceConfig.objects.filter(interface_config_id=102).exists()
        assert not EngineSpaceConfig.objects.filter(interface_config_id=103).exists()

    def test_validate_task_info_invalid_space_id(self):
        """测试 validate_task_info 装饰器 - space_id 无效"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        view = TaskInstanceViewSet.as_view({"get": "get_states"})
        # 使用错误的 space_id
        request = self._create_request_with_auth("get", f"/task/{task_instance.id}/get_states/", space_id="999")

        response = view(request, pk=task_instance.id)
        assert response.status_code == 403
        assert response.data["result"] is False
        assert "space_id is invalid" in response.data["message"]

    def test_validate_task_info_from_superuser(self):
        """测试 validate_task_info 装饰器 - 超级用户"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        with patch("bkflow.task.views.TaskOperation") as mock_task_operation:
            mock_operation = MagicMock()
            mock_operation.get_task_states.return_value = MagicMock(result=True, data={"state": "RUNNING"})
            mock_task_operation.return_value = mock_operation

            view = TaskInstanceViewSet.as_view({"get": "get_states"})
            # 使用 from_superuser=1，即使 space_id 不匹配也应该允许访问
            request = self._create_request_with_auth(
                "get", f"/task/{task_instance.id}/get_states/", space_id="999", from_superuser="1"
            )

            response = view(request, pk=task_instance.id)
            assert response.status_code == status.HTTP_200_OK

    def test_validate_task_info_invalid_node_id_in_kwargs(self):
        """测试 validate_task_info 装饰器 - kwargs 中的无效 node_id"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        invalid_node_id = "invalid_node_id_123"

        view = TaskInstanceViewSet.as_view({"get": "get_node_log"})
        request = self._create_request_with_auth(
            "get",
            f"/task/{task_instance.id}/get_task_node_log/{invalid_node_id}/v1/",
            {"page": 1, "page_size": 100},
        )

        response = view(request, pk=task_instance.id, node_id=invalid_node_id, version="v1")
        assert response.status_code == 403
        assert response.data["result"] is False
        assert "node_id should be in task" in response.data["message"]

    def test_validate_task_info_invalid_node_id_in_query_params(self):
        """测试 validate_task_info 装饰器 - query_params 中的无效 node_id"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        invalid_node_id = "invalid_node_id_456"

        view = TaskInstanceViewSet.as_view({"get": "get_node_snapshot_config"})
        request = self._create_request_with_auth(
            "get", f"/task/{task_instance.id}/get_node_snapshot_config/", {"node_id": invalid_node_id}
        )

        response = view(request, pk=task_instance.id)
        assert response.status_code == 403
        assert response.data["result"] is False
        assert "node_id should be in task" in response.data["message"]

    def test_validate_task_info_invalid_node_id_in_data(self):
        """测试 validate_task_info 装饰器 - request.data 中的无效 node_id"""
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=pipeline_tree)
        invalid_node_id = "invalid_node_id_789"

        view = TaskInstanceViewSet.as_view({"post": "render_context_with_node_outputs"})
        data = {"node_id": invalid_node_id, "node_ids": [], "to_render_constants": []}
        request = self._create_request_with_auth(
            "post", f"/task/{task_instance.id}/render_context_with_node_outputs/", data
        )

        response = view(request, pk=task_instance.id)
        assert response.status_code == 403
        assert response.data["result"] is False
        assert "node_id should be in task" in response.data["message"]


@pytest.mark.django_db(transaction=True)
class TestPeriodicTaskViewSet:
    """测试 PeriodicTaskViewSet 视图"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.factory = APIRequestFactory()

    def _create_request(self, method, path, data=None):
        """创建请求"""
        if method == "get":
            request = self.factory.get(path, data)
        elif method == "post":
            request = self.factory.post(path, data, format="json")
        elif method == "delete":
            request = self.factory.delete(path, data, format="json")
        else:
            raise ValueError(f"Unsupported method: {method}")

        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False

        return request

    def test_create_periodic_task(self):
        """测试创建周期任务"""
        view = PeriodicTaskViewSet.as_view({"post": "create"})
        data = {
            "trigger_id": 1000,
            "template_id": 1,
            "name": "test_periodic_task",
            "cron": {
                "minute": "0",
                "hour": "*",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
            },
            "creator": "admin",
            "config": {},
        }

        request = self._create_request("post", "/periodic_task/", data)
        response = view(request)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"].name == "test_periodic_task"

    def test_update_periodic_task_success(self):
        """测试更新周期任务 - 成功"""
        # 先创建一个周期任务
        create_view = PeriodicTaskViewSet.as_view({"post": "create"})
        create_data = {
            "trigger_id": 2000,
            "template_id": 1,
            "name": "original_name",
            "cron": {
                "minute": "0",
                "hour": "*",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
            },
            "creator": "admin",
            "config": {},
        }

        request = self._create_request("post", "/periodic_task/", create_data)
        create_view(request)

        # 更新任务
        update_view = PeriodicTaskViewSet.as_view({"post": "update_task"})
        update_data = {
            "trigger_id": 2000,
            "name": "updated_name",
            "cron": {
                "minute": "30",
                "hour": "12",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
            },
            "config": {},
        }

        request = self._create_request("post", "/periodic_task/update/", update_data)
        response = update_view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "updated_name"

    def test_batch_delete_periodic_tasks(self):
        """测试批量删除周期任务"""
        # 创建两个周期任务
        create_view = PeriodicTaskViewSet.as_view({"post": "create"})
        for trigger_id in [3000, 3001]:
            data = {
                "trigger_id": trigger_id,
                "template_id": 1,
                "name": f"task_{trigger_id}",
                "cron": {
                    "minute": "0",
                    "hour": "*",
                    "day_of_week": "*",
                    "day_of_month": "*",
                    "month_of_year": "*",
                },
                "creator": "admin",
                "config": {},
            }
            request = self._create_request("post", "/periodic_task/", data)
            create_view(request)

        # 批量删除
        delete_view = PeriodicTaskViewSet.as_view({"post": "batch_delete"})
        request = self._create_request("post", "/periodic_task/batch_delete/", {"trigger_ids": [3000, 3001]})
        response = delete_view(request)
        assert response.status_code == status.HTTP_200_OK

        # 验证任务已删除
        assert not PeriodicTask.objects.filter(trigger_id=3000).exists()
        assert not PeriodicTask.objects.filter(trigger_id=3001).exists()

    def test_batch_delete_periodic_tasks_empty_list(self):
        """测试批量删除周期任务 - 空列表"""
        view = PeriodicTaskViewSet.as_view({"post": "batch_delete"})
        request = self._create_request("post", "/periodic_task/batch_delete/", {"trigger_ids": []})
        response = view(request)
        assert response.status_code == status.HTTP_200_OK
