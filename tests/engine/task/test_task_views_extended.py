"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from bkflow.constants import TaskTriggerMethod
from bkflow.task.models import (
    EngineSpaceConfig,
    EngineSpaceConfigValueType,
    TaskFlowRelation,
    TaskInstance,
    TaskLabelRelation,
)
from bkflow.task.views import PeriodicTaskViewSet, TaskInstanceViewSet
from bkflow.utils.pipeline import build_default_pipeline_tree


def _make_request(factory, method, path, data=None, space_id=None, user=None):
    """构造带有必要权限属性的请求对象。"""
    kwargs = {}
    if data is not None:
        kwargs["data"] = data
        kwargs["format"] = "json"
    if space_id is not None:
        # Django 会将 HTTP_ 前缀 header 的 _ 转换为 -，并通过大小写不敏感匹配
        kwargs["HTTP_BKFLOW_INTERNAL_SPACE_ID"] = str(space_id)
    request = getattr(factory, method)(path, **kwargs)
    request.user = user or MagicMock()
    request.user.username = "test_user"
    request.user.is_superuser = False
    request.app_internal_token = settings.APP_INTERNAL_TOKEN
    return request


@pytest.mark.django_db(transaction=True)
class TestTaskInstanceListView:
    """测试任务列表查询（含 DEBUG 隐藏逻辑）"""

    def test_list_hides_debug_tasks_by_default(self):
        """列表默认隐藏 create_method=DEBUG 的任务"""
        TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=build_default_pipeline_tree(), create_method="DEBUG"
        )
        normal_task = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=build_default_pipeline_tree(), create_method="API"
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "list"})
        request = _make_request(factory, "get", "/task/", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        returned_ids = [item["id"] for item in response.data["data"]["results"]]
        assert normal_task.id in returned_ids
        assert all(t["create_method"] != "DEBUG" for t in response.data["data"]["results"])

    def test_list_keeps_debug_when_create_method_queried(self):
        """显式按 create_method=DEBUG 过滤时保留 DEBUG 任务"""
        debug_task = TaskInstance.objects.create_instance(
            space_id=2, pipeline_tree=build_default_pipeline_tree(), create_method="DEBUG"
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "list"})
        request = _make_request(factory, "get", "/task/?create_method=DEBUG", space_id=2)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        returned_ids = [item["id"] for item in response.data["data"]["results"]]
        assert debug_task.id in returned_ids

    def test_list_keeps_debug_when_pk_queried(self):
        """按主键查询时保留 DEBUG 任务"""
        debug_task = TaskInstance.objects.create_instance(
            space_id=3, pipeline_tree=build_default_pipeline_tree(), create_method="DEBUG"
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "list"})
        request = _make_request(factory, "get", f"/task/?id={debug_task.id}", space_id=3)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        returned_ids = [item["id"] for item in response.data["data"]["results"]]
        assert debug_task.id in returned_ids

    def test_list_attaches_labels(self):
        """列表返回的任务应附带 labels 信息"""
        task = TaskInstance.objects.create_instance(space_id=4, pipeline_tree=build_default_pipeline_tree())
        TaskLabelRelation.objects.create(task_id=task.id, label_id=10)

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "list"})
        request = _make_request(factory, "get", "/task/", space_id=4)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        task_data = next(t for t in response.data["data"]["results"] if t["id"] == task.id)
        assert task_data["labels"] == [10]


@pytest.mark.django_db(transaction=True)
class TestTaskLabelOperations:
    """测试任务标签相关操作"""

    def test_update_labels(self):
        """更新任务标签"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskLabelRelation.objects.create(task_id=task.id, label_id=1)

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "update_labels"})
        request = _make_request(
            factory, "post", f"/task/{task.id}/update_labels/", data={"label_ids": [2, 3]}, space_id=1
        )

        response = view(request, pk=task.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == [2, 3]
        assert set(TaskLabelRelation.objects.filter(task_id=task.id).values_list("label_id", flat=True)) == {2, 3}

    def test_get_task_label_ref_count(self):
        """获取标签引用数量"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskLabelRelation.objects.create(task_id=task.id, label_id=5)

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "get_task_label_ref_count"})
        request = _make_request(factory, "get", "/task/get_task_label_ref_count/?label_ids=5,6&space_id=1", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["5"] == 1
        assert response.data["data"]["6"] == 0

    def test_delete_task_label_relation(self):
        """删除任务标签关联关系"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskLabelRelation.objects.create(task_id=task.id, label_id=7)

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "delete_task_label_relation"})
        request = _make_request(
            factory, "post", "/task/delete_task_label_relation/", data={"label_ids": [7]}, space_id=1
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert TaskLabelRelation.objects.filter(label_id=7).count() == 0


@pytest.mark.django_db(transaction=True)
class TestTaskStatesViews:
    """测试任务状态查询相关视图"""

    def test_batch_get_task_states_missing_params(self):
        """缺少必要参数时返回 400"""
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "batch_get_task_states"})
        request = _make_request(factory, "get", "/task/batch_get_task_states/", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_batch_get_task_states_success(self, mocker):
        """批量获取任务状态成功"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        mocker.patch(
            "bkflow.task.operations.TaskOperation.get_task_states",
            return_value=MagicMock(result=True, data={"state": "RUNNING"}),
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "batch_get_task_states"})
        request = _make_request(
            factory, "get", f"/task/batch_get_task_states/?task_ids={task.id}&space_id=1", space_id=1
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][str(task.id)]["state"] == "RUNNING"

    def test_get_tasks_states_success(self, mocker):
        """POST 批量获取任务状态"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        mocker.patch(
            "bkflow.task.operations.TaskOperation.get_task_states",
            return_value=MagicMock(result=True, data={"state": "FINISHED"}),
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "get_tasks_states"})
        request = _make_request(
            factory, "post", "/task/get_tasks_states/", data={"task_ids": [task.id], "space_id": 1}, space_id=1
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][task.id]["state"] == "FINISHED"

    def test_get_tasks_states_failed_result(self, mocker):
        """任务状态查询失败时返回 None"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        mocker.patch(
            "bkflow.task.operations.TaskOperation.get_task_states",
            return_value=MagicMock(result=False, data={}),
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "get_tasks_states"})
        request = _make_request(
            factory, "post", "/task/get_tasks_states/", data={"task_ids": [task.id], "space_id": 1}, space_id=1
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][task.id]["state"] is None


@pytest.mark.django_db(transaction=True)
class TestTaskPipelineAndChildrenViews:
    """测试任务 pipeline 和子任务相关视图"""

    def test_get_tasks_pipeline_success(self, mocker):
        """批量获取任务 pipeline 树"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        # mock TaskExecutionSnapshot 查询
        mocker.patch(
            "bkflow.task.views.TaskExecutionSnapshot.objects.filter",
            return_value=[MagicMock(id=task.execution_snapshot_id, data={"a": 1})],
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "get_tasks_pipeline"})
        request = _make_request(factory, "get", f"/task/get_tasks_pipeline/?task_ids={task.id}&space_id=1", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][str(task.id)] == {"a": 1}

    def test_get_tasks_pipeline_empty_task_ids(self):
        """task_ids 为空时返回空字典"""
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "get_tasks_pipeline"})
        request = _make_request(factory, "get", "/task/get_tasks_pipeline/?task_ids=&space_id=1", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == {}

    def test_list_children_taskflow_no_root(self):
        """未提供 root task_id 时返回空列表"""
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "list_children_taskflow"})
        request = _make_request(factory, "get", "/task/list_children_taskflow/", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["tasks"] == []

    def test_list_children_taskflow_with_children(self):
        """查询包含子任务流的任务列表"""
        root_task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        child_task = TaskInstance.objects.create_instance(
            space_id=1,
            pipeline_tree=build_default_pipeline_tree(),
            trigger_method=TaskTriggerMethod.subprocess.name,
        )
        TaskFlowRelation.objects.create(task_id=child_task.id, parent_task_id=root_task.id, root_task_id=root_task.id)

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "list_children_taskflow"})
        request = _make_request(factory, "get", f"/task/list_children_taskflow/?task_id={root_task.id}", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        returned_ids = [t["id"] for t in response.data["data"]["tasks"]]
        assert child_task.id in returned_ids
        assert response.data["data"]["relations"][child_task.id] == root_task.id

    def test_root_task_info_no_params(self):
        """未提供 task_ids 时返回空字典"""
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "root_task_info"})
        request = _make_request(factory, "get", "/task/root_task_info/", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == {"has_children_taskflow": {}}

    def test_root_task_info_invalid_params(self):
        """task_ids 格式错误时返回 400"""
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "root_task_info"})
        request = _make_request(factory, "get", "/task/root_task_info/?task_ids=abc", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_root_task_info_with_children(self):
        """查询任务是否包含子任务流"""
        root_task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        child_task = TaskInstance.objects.create_instance(
            space_id=1,
            pipeline_tree=build_default_pipeline_tree(),
            trigger_method=TaskTriggerMethod.subprocess.name,
        )
        TaskFlowRelation.objects.create(task_id=child_task.id, parent_task_id=root_task.id, root_task_id=root_task.id)

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "root_task_info"})
        request = _make_request(factory, "get", f"/task/root_task_info/?task_ids={root_task.id}", space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["has_children_taskflow"][root_task.id] is True


@pytest.mark.django_db(transaction=True)
class TestNodeOutputsView:
    """测试节点输出查询视图"""

    def test_get_node_outputs_task_not_found(self):
        """任务不存在时返回失败"""
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "get_node_outputs"})
        request = _make_request(
            factory,
            "post",
            "/task/get_node_outputs/",
            data={"task_id": 99999, "space_id": 1, "node_ids": ["n1"]},
            space_id=1,
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is False

    def test_get_node_outputs_invalid_node(self):
        """节点不属于任务时返回失败"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "get_node_outputs"})
        request = _make_request(
            factory,
            "post",
            "/task/get_node_outputs/",
            data={"task_id": task.id, "space_id": 1, "node_ids": ["invalid_node"]},
            space_id=1,
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["result"] is False

    def test_get_node_outputs_success(self, mocker):
        """节点输出查询成功"""
        task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        node_id = list(task.execution_data["activities"].keys())[0]
        mocker.patch(
            "bkflow.task.operations.TaskNodeOperation.get_node_outputs",
            return_value=MagicMock(result=True, data={"key": "value"}),
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "get_node_outputs"})
        request = _make_request(
            factory,
            "post",
            "/task/get_node_outputs/",
            data={"task_id": task.id, "space_id": 1, "node_ids": [node_id]},
            space_id=1,
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][0][node_id] == {"key": "value"}


@pytest.mark.django_db(transaction=True)
class TestEngineConfigViews:
    """测试引擎空间配置相关视图"""

    def test_get_engine_config_success(self):
        """获取引擎空间配置"""
        EngineSpaceConfig.objects.create(
            interface_config_id=100,
            name="test_config",
            space_id=1,
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="hello",
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "get_engine_config"})
        request = _make_request(
            factory, "get", "/task/get_engine_config/?interface_config_ids=100&simplified=false", space_id=1
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][0]["name"] == "test_config"

    def test_get_engine_config_simplified(self):
        """简化模式获取引擎空间配置"""
        EngineSpaceConfig.objects.create(
            interface_config_id=101,
            name="json_config",
            space_id=1,
            value_type=EngineSpaceConfigValueType.JSON.value,
            json_value={"k": "v"},
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "get_engine_config"})
        request = _make_request(
            factory, "get", "/task/get_engine_config/?interface_config_ids=101&simplified=true", space_id=1
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][0]["value"] == {"k": "v"}

    def test_upsert_engine_config_create(self):
        """创建引擎空间配置"""
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "upsert_engine_config"})
        data = {
            "interface_config_id": 200,
            "name": "new_config",
            "space_id": 1,
            "value_type": EngineSpaceConfigValueType.TEXT.value,
            "text_value": "abc",
        }
        request = _make_request(factory, "post", "/task/upsert_engine_config/", data=data, space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert EngineSpaceConfig.objects.filter(interface_config_id=200).exists()

    def test_upsert_engine_config_update(self):
        """更新已存在的引擎空间配置"""
        config = EngineSpaceConfig.objects.create(
            interface_config_id=201,
            name="old_config",
            space_id=1,
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="old",
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"post": "upsert_engine_config"})
        data = {
            "interface_config_id": 201,
            "name": "old_config",
            "space_id": 1,
            "value_type": EngineSpaceConfigValueType.TEXT.value,
            "text_value": "new",
        }
        request = _make_request(factory, "post", "/task/upsert_engine_config/", data=data, space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        config.refresh_from_db()
        assert config.text_value == "new"

    def test_delete_engine_config(self):
        """删除引擎空间配置"""
        EngineSpaceConfig.objects.create(
            interface_config_id=202,
            name="del_config",
            space_id=1,
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="x",
        )

        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"delete": "delete_engine_config"})
        request = _make_request(
            factory, "delete", "/task/delete_engine_config/", data={"interface_config_ids": [202]}, space_id=1
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        assert not EngineSpaceConfig.objects.filter(interface_config_id=202).exists()


@pytest.mark.django_db(transaction=True)
class TestPeriodicTaskViewSet:
    """测试周期任务视图"""

    def test_create_periodic_task(self, mocker):
        """创建周期任务"""
        mocker.patch(
            "bkflow.task.models.PeriodicTask.objects.create_task",
            return_value={"id": 1, "name": "periodic"},
        )

        factory = APIRequestFactory()
        view = PeriodicTaskViewSet.as_view({"post": "create"})
        data = {
            "trigger_id": 1,
            "template_id": 1,
            "name": "periodic",
            "cron": "* * * * *",
            "creator": "test_user",
            "config": {},
        }
        request = _make_request(factory, "post", "/periodic_task/", data=data, space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_201_CREATED

    def test_update_periodic_task_not_found(self, mocker):
        """更新不存在的周期任务返回 404"""
        mocker.patch(
            "bkflow.task.models.PeriodicTask.objects.filter",
            return_value=MagicMock(first=MagicMock(return_value=None)),
        )

        factory = APIRequestFactory()
        view = PeriodicTaskViewSet.as_view({"post": "update_task"})
        request = _make_request(factory, "post", "/periodic_task/update/", data={"trigger_id": 999}, space_id=1)

        response = view(request)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_periodic_task(self, mocker):
        """删除周期任务"""
        mock_instance = MagicMock()
        mock_instance.delete = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value.select_related.return_value = [mock_instance]
        mocker.patch.object(PeriodicTaskViewSet, "get_queryset", return_value=mock_qs)

        factory = APIRequestFactory()
        view = PeriodicTaskViewSet.as_view({"post": "batch_delete"})
        request = _make_request(
            factory, "post", "/periodic_task/batch_delete/", data={"trigger_ids": [1, 2]}, space_id=1
        )

        response = view(request)
        assert response.status_code == status.HTTP_200_OK
        mock_instance.delete.assert_called_once()
