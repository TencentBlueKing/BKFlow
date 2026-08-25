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
from django.conf import settings
from django.http import QueryDict
from pipeline.core.constants import PE
from rest_framework import status
from rest_framework.test import APIRequestFactory

from bkflow.task.models import TaskInstance, TaskMockData
from bkflow.task.views import TaskInstanceViewSet
from bkflow.utils.context import TaskContext
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db
class TestDebugCreateInstance:
    def test_debug_method_materializes_mock_with_fail_nodes(self):
        pipeline_tree = build_default_pipeline_tree()
        node_id = list(pipeline_tree[PE.activities].keys())[0]
        instance = TaskInstance.objects.create_instance(
            pipeline_tree=pipeline_tree,
            space_id=10,
            create_method="DEBUG",
            creator="admin",
            mock_data={
                "nodes": [node_id],
                "outputs": {node_id: {"k": "v"}},
                "fail_nodes": [node_id],
                "errors": {node_id: "boom"},
            },
        )
        mock = TaskMockData.objects.get(taskflow_id=instance.id)
        # 节点 id 经 replace_all_id 重映射，但单节点可断言键集合非空
        assert mock.data["nodes"]
        assert "fail_nodes" in mock.data and mock.data["fail_nodes"]
        assert "errors" in mock.data and list(mock.data["errors"].values()) == ["boom"]
        # fail_nodes/errors 与 nodes 同源，重映射后应保持一致的节点 id
        assert mock.data["fail_nodes"] == mock.data["nodes"]
        assert list(mock.data["errors"].keys()) == mock.data["fail_nodes"]

    def test_debug_task_is_mock_true(self):
        instance = TaskInstance.objects.create_instance(
            pipeline_tree=build_default_pipeline_tree(),
            space_id=10,
            create_method="DEBUG",
            creator="admin",
        )
        assert TaskContext(instance).is_mock is True


class TestShouldKeepDebugTasks:
    """不打数据库，用真实 QueryDict 覆盖 apply_token 的查询串。"""

    def _viewset(self, action, query_string=""):
        viewset = TaskInstanceViewSet()
        viewset.action = action
        viewset.request = MagicMock()
        viewset.request.query_params = QueryDict(query_string)
        return viewset

    def test_keep_debug_when_token_lists_by_id(self):
        """apply_token 的查询串带 id 时保留 DEBUG。"""
        viewset = self._viewset("list", "id=180&space_id=205&limit=1&offset=0")
        assert viewset._should_keep_debug_tasks() is True

    def test_keep_debug_when_filtered_by_create_method(self):
        """显式按 create_method 过滤时保留 DEBUG。"""
        viewset = self._viewset("list", "create_method=DEBUG&space_id=205")
        assert viewset._should_keep_debug_tasks() is True

    def test_hide_debug_on_browse_list(self):
        """普通列表浏览不带 id 时隐藏 DEBUG。"""
        viewset = self._viewset("list", "space_id=205&limit=1&offset=0")
        assert viewset._should_keep_debug_tasks() is False

    def test_keep_debug_on_retrieve(self):
        """详情接口不过滤 DEBUG。"""
        viewset = self._viewset("retrieve", "")
        assert viewset._should_keep_debug_tasks() is True


@pytest.mark.django_db
class TestTaskInstanceListDebugVisibility:
    """列表接口默认隐藏 DEBUG；按 id 精确查询时必须返回，供 apply_token 复用。"""

    def setup_method(self):
        self.factory = APIRequestFactory()

    def _create_tasks(self, space_id=205):
        debug_task = TaskInstance.objects.create_instance(
            pipeline_tree=build_default_pipeline_tree(), space_id=space_id, create_method="DEBUG", creator="admin"
        )
        api_task = TaskInstance.objects.create_instance(
            pipeline_tree=build_default_pipeline_tree(), space_id=space_id, create_method="API", creator="admin"
        )
        return debug_task, api_task

    def _list_request(self, query):
        request = self.factory.get("/task/", query)
        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN
        request.META[f"HTTP_{settings.APP_INTERNAL_SPACE_ID_HEADER_KEY}"] = str(query.get("space_id", "205"))
        request.META[f"HTTP_{settings.APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY}"] = "0"
        return request

    def _list(self, query):
        view = TaskInstanceViewSet.as_view({"get": "list"})
        return view(self._list_request(query))

    def test_list_hides_debug_by_default(self):
        """未指定 id / create_method 时，列表不返回 DEBUG 任务。"""
        debug_task, api_task = self._create_tasks()
        response = self._list({"space_id": 205, "limit": 10, "offset": 0})

        assert response.status_code == status.HTTP_200_OK
        result_ids = [item["id"] for item in response.data["data"]["results"]]
        assert api_task.id in result_ids
        assert debug_task.id not in result_ids

    def test_list_shows_debug_when_filtered_by_create_method(self):
        """create_method=DEBUG 时列表返回调试任务。"""
        debug_task, _ = self._create_tasks()
        response = self._list({"space_id": 205, "create_method": "DEBUG", "limit": 10, "offset": 0})

        assert response.status_code == status.HTTP_200_OK
        result_ids = [item["id"] for item in response.data["data"]["results"]]
        assert debug_task.id in result_ids

    def test_list_shows_debug_when_filtered_by_id(self):
        """apply_token 按 id + space_id 查列表，DEBUG 任务必须 count=1。"""
        debug_task, api_task = self._create_tasks()
        response = self._list({"id": debug_task.id, "space_id": 205, "limit": 1, "offset": 0})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is True
        assert response.data["data"]["count"] == 1
        assert response.data["data"]["results"][0]["id"] == debug_task.id
        assert response.data["data"]["results"][0]["create_method"] == "DEBUG"
        assert response.data["data"]["results"][0]["id"] != api_task.id

    def test_retrieve_keeps_debug(self):
        """详情接口能返回 DEBUG 任务。"""
        debug_task, _ = self._create_tasks()
        view = TaskInstanceViewSet.as_view({"get": "retrieve"})
        request = self._list_request({"space_id": 205})
        response = view(request, pk=debug_task.id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == debug_task.id
        assert response.data["data"]["create_method"] == "DEBUG"
