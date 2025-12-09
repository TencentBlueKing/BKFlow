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

from bkflow.task.models import TaskInstance, TaskMockData
from bkflow.task.views import TaskInstanceViewSet
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestTaskInstanceViewSet:
    """测试 TaskInstanceViewSet 视图"""

    def test_create_task_instance(self):
        """测试创建任务实例"""
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "create"})
        pipeline_tree = build_default_pipeline_tree()
        data = {
            "space_id": 1,
            "pipeline_tree": pipeline_tree,
            "name": "test_task",
            "creator": "test_creator",
        }

        request = factory.post("/task/", data, format="json")
        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        # 设置内部 token，AppInternalPermission 需要这个属性
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        response = view(request)
        assert response.status_code == status.HTTP_201_CREATED
        # 响应数据被 task_response_wrapper 包装，实际数据在 data 字段中
        assert response.data["data"]["name"] == "test_task"

    def test_batch_delete_tasks(self):
        """测试批量删除任务"""
        factory = APIRequestFactory()
        # 创建测试任务
        task1 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task2 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        view = TaskInstanceViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": 1, "task_ids": [task1.id, task2.id], "is_full": False}

        request = factory.post("/task/batch_delete_tasks/", data, format="json")
        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True

        # 验证任务已被标记为删除
        task1.refresh_from_db()
        task2.refresh_from_db()
        assert task1.is_deleted is True
        assert task2.is_deleted is True

    def test_batch_delete_tasks_full(self):
        """测试批量删除所有任务"""
        factory = APIRequestFactory()
        # 创建测试任务
        TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        view = TaskInstanceViewSet.as_view({"post": "batch_delete"})
        # 当 is_full=True 时，必须提供 is_mock 参数
        data = {"space_id": 1, "is_full": True, "is_mock": False}

        request = factory.post("/task/batch_delete_tasks/", data, format="json")
        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # 验证所有任务已被标记为删除
        tasks = TaskInstance.objects.filter(space_id=1, is_deleted=False)
        assert tasks.count() == 0

    def test_get_task_mock_data(self):
        """测试获取任务 Mock 数据"""
        factory = APIRequestFactory()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        mock_data = {"outputs": {"node1": {"output1": "value1"}}}
        TaskMockData.objects.create(taskflow_id=task_instance.id, data=mock_data)

        view = TaskInstanceViewSet.as_view({"get": "get_task_mock_data"})
        request = factory.get(f"/task/{task_instance.id}/get_task_mock_data/")
        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK
        # 响应数据被 task_response_wrapper 包装，实际数据在 data 字段中
        # task_mock_data.to_json() 返回的是包含 id, taskflow_id, data 的字典
        assert response.data["data"]["data"] == mock_data

    def test_get_task_mock_data_not_exist(self):
        """测试获取不存在的 Mock 数据"""
        factory = APIRequestFactory()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        view = TaskInstanceViewSet.as_view({"get": "get_task_mock_data"})
        request = factory.get(f"/task/{task_instance.id}/get_task_mock_data/")
        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK
        # 响应数据被 task_response_wrapper 包装，实际数据在 data 字段中
        assert response.data["data"] == {}

    @patch("bkflow.task.views.TaskOperation")
    def test_operate_task(self, mock_task_operation):
        """测试任务操作"""
        factory = APIRequestFactory()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_instance.is_started = True
        task_instance.save()

        mock_operation = MagicMock()
        mock_operation.start.return_value = MagicMock(result=True, data={}, message="success")
        mock_task_operation.return_value = mock_operation

        view = TaskInstanceViewSet.as_view({"post": "operate"})
        # 使用 HTTP_ 前缀设置自定义 header
        request = factory.post(
            f"/task/{task_instance.id}/operate/start/",
            {},
            format="json",
            HTTP_BKFLOW_INTERNAL_SPACE_ID="1",
        )
        request.user = MagicMock()
        request.user.username = "test_operator"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        response = view(request, pk=task_instance.id, operation="start")
        assert response.status_code == status.HTTP_200_OK

    def test_get_states(self, mocker):
        """测试获取任务状态"""
        factory = APIRequestFactory()
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_instance.is_started = True
        task_instance.save()

        view = TaskInstanceViewSet.as_view({"get": "get_states"})
        # 使用 HTTP_ 前缀设置自定义 header
        request = factory.get(f"/task/{task_instance.id}/get_states/", HTTP_BKFLOW_INTERNAL_SPACE_ID="1")
        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        mocker.patch(
            "bkflow.task.operations.TaskOperation.get_task_states",
            return_value=MagicMock(result=True, data={"state": "RUNNING"}),
        )

        response = view(request, pk=task_instance.id)
        assert response.status_code == status.HTTP_200_OK
