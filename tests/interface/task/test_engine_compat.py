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

from bkflow.interface.task.engine_compat import (
    empty_wrapped_result,
    enrich_task_list_result_labels,
    fallback_if_engine_route_missing,
    is_engine_route_missing,
    parse_task_ids,
)
from bkflow.interface.task.view import TaskInterfaceAdminViewSet, TaskInterfaceViewSet

ENGINE_404 = {
    "result": False,
    "message": (
        "Request API error, status_code: 404, url: http://engine/task/root_task_info/, method: GET, resp: Not Found"
    ),
}
ENGINE_405 = {
    "result": False,
    "message": "Request API error, status_code: 405, url: http://engine/task/get_node_outputs/, method: POST, resp: {}",
}
ENGINE_500 = {
    "result": False,
    "message": "Request API error, status_code: 500, url: http://engine/task/root_task_info/, method: GET, resp: boom",
}
# 旧 engine 有 SimpleGenericViewSet：缺路由的 DRF 404 会被改写成 HTTP 200
ENGINE_WRAPPED_NOT_FOUND = {
    "result": False,
    "data": {"detail": "未找到。"},
    "code": "not_found",
    "message": "未找到。",
}
ENGINE_WRAPPED_NOT_FOUND_EN = {
    "result": False,
    "data": {"detail": "Not found."},
    "code": "not_found",
    "message": "Not found.",
}
ENGINE_CUSTOM_NOT_FOUND = {
    "result": False,
    "data": {"detail": "task 123 not found"},
    "code": "not_found",
    "message": "task 123 not found",
}


class TestIsEngineRouteMissing:
    """识别旧 engine 缺少新路由的失败响应。"""

    def test_detects_404_from_http_client(self):
        assert is_engine_route_missing(ENGINE_404) is True

    def test_detects_405_from_http_client(self):
        assert is_engine_route_missing(ENGINE_405) is True

    def test_does_not_swallow_500(self):
        assert is_engine_route_missing(ENGINE_500) is False

    def test_does_not_treat_success_as_missing(self):
        assert is_engine_route_missing({"result": True, "data": {"has_children_taskflow": {1: False}}}) is False

    def test_ignores_non_dict(self):
        assert is_engine_route_missing(None) is False
        assert is_engine_route_missing("not found") is False

    def test_detects_wrapped_drf_not_found(self):
        assert is_engine_route_missing(ENGINE_WRAPPED_NOT_FOUND) is True

    def test_detects_wrapped_english_not_found(self):
        assert is_engine_route_missing(ENGINE_WRAPPED_NOT_FOUND_EN) is True

    def test_does_not_swallow_custom_not_found_message(self):
        assert is_engine_route_missing(ENGINE_CUSTOM_NOT_FOUND) is False


class TestFallbackIfEngineRouteMissing:
    """404/405 回空成功结构，其它结果原样返回。"""

    def test_returns_fallback_on_404(self):
        fallback = empty_wrapped_result({"tasks": [], "relations": {}})
        assert fallback_if_engine_route_missing(ENGINE_404, fallback) == fallback

    def test_keeps_success_payload(self):
        success = {"result": True, "data": {"has_children_taskflow": {1: True}}}
        assert fallback_if_engine_route_missing(success, empty_wrapped_result({})) == success

    def test_keeps_500_payload(self):
        assert fallback_if_engine_route_missing(ENGINE_500, empty_wrapped_result({})) == ENGINE_500


class TestParseTaskIds:
    def test_parses_comma_separated_ids(self):
        assert parse_task_ids("1,2,3") == [1, 2, 3]

    def test_skips_blank_and_invalid(self):
        assert parse_task_ids("1,,abc,2") == [1, 2]

    def test_empty(self):
        assert parse_task_ids(None) == []
        assert parse_task_ids("") == []


def _engine_404_message(path):
    return {
        "result": False,
        "message": f"Request API error, status_code: 404, url: http://engine/{path}, method: GET, resp: Not Found",
    }


class TestTaskInterfaceEngineRouteCompat:
    """interface 在旧 engine 缺路由时回空成功结构，不影响已升级 engine。"""

    def _request(self, query_params=None, data=None):
        request = MagicMock()
        request.user.is_superuser = True
        request.query_params = query_params or {}
        request.data = data or {}
        return request

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_root_task_info_falls_back_when_engine_404(self, mock_client_class):
        mock_client = mock.Mock()
        mock_client.root_task_info.return_value = ENGINE_404
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet()
        view.get_space_id = lambda request: 1
        response = view.root_task_info(self._request({"task_ids": "11,22", "space_id": "1"}))

        assert response.data["result"] is True
        assert response.data["data"]["has_children_taskflow"] == {11: False, 22: False}

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_root_task_info_passthrough_when_engine_ok(self, mock_client_class):
        success = {"result": True, "data": {"has_children_taskflow": {11: True}}, "code": "0", "message": ""}
        mock_client = mock.Mock()
        mock_client.root_task_info.return_value = success
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet()
        view.get_space_id = lambda request: 1
        response = view.root_task_info(self._request({"task_ids": "11", "space_id": "1"}))

        assert response.data == success

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_root_task_info_does_not_swallow_500(self, mock_client_class):
        mock_client = mock.Mock()
        mock_client.root_task_info.return_value = ENGINE_500
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet()
        view.get_space_id = lambda request: 1
        response = view.root_task_info(self._request({"task_ids": "11", "space_id": "1"}))

        assert response.data["result"] is False
        assert "status_code: 500" in response.data["message"]

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_root_task_info_falls_back_when_engine_wraps_not_found(self, mock_client_class):
        mock_client = mock.Mock()
        mock_client.root_task_info.return_value = ENGINE_WRAPPED_NOT_FOUND
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet()
        view.get_space_id = lambda request: 1
        response = view.root_task_info(self._request({"task_ids": "2,1", "space_id": "240"}))

        assert response.data["result"] is True
        assert response.data["data"]["has_children_taskflow"] == {2: False, 1: False}

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_list_children_taskflow_falls_back_when_engine_404(self, mock_client_class):
        mock_client = mock.Mock()
        mock_client.list_children_taskflow.return_value = _engine_404_message("task/list_children_taskflow/")
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet()
        view.get_space_id = lambda request: 1
        response = view.list_children_taskflow(self._request({"space_id": "1"}), task_id=99)

        assert response.data["result"] is True
        assert response.data["data"] == {"tasks": [], "relations": {}}

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_node_outputs_falls_back_when_engine_404(self, mock_client_class):
        mock_client = mock.Mock()
        mock_client.get_node_outputs.return_value = _engine_404_message("task/get_node_outputs/")
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet()
        view.get_space_id = lambda request: 1
        response = view.get_node_outputs(self._request(data={"space_id": 1, "task_id": 1, "node_ids": ["n1"]}))

        assert response.data["result"] is True
        assert response.data["data"] == []

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_tasks_pipeline_falls_back_when_engine_404(self, mock_client_class):
        mock_client = mock.Mock()
        mock_client.get_tasks_pipeline.return_value = _engine_404_message("task/get_tasks_pipeline/")
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet()
        view.get_space_id = lambda request: 1
        response = view.get_tasks_pipeline(self._request({"space_id": "1", "task_ids": "1"}))

        assert response.data["result"] is True
        assert response.data["data"] == {}

    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_batch_get_task_states_falls_back_when_engine_404(self, mock_client_class):
        mock_client = mock.Mock()
        mock_client.batch_get_task_states.return_value = _engine_404_message("task/batch_get_task_states/")
        mock_client_class.return_value = mock_client

        view = TaskInterfaceViewSet()
        view.get_space_id = lambda request: 1
        response = view.batch_get_task_states(self._request({"space_id": "1", "task_ids": "1"}))

        assert response.data["result"] is True
        assert response.data["data"] == {}


class TestEnrichTaskListResultLabels:
    """任务列表 labels 兼容：缺字段当空，失败响应原样返回。"""

    def test_fills_empty_labels_for_legacy_engine_items(self):
        result = {"result": True, "data": {"results": [{"id": 1, "name": "legacy"}]}}
        enrich_task_list_result_labels(result, labels_map_getter=lambda ids: {})
        assert result["data"]["results"][0]["labels"] == []

    def test_passthrough_failed_engine_result(self):
        failed = {"result": False, "message": "boom"}
        assert enrich_task_list_result_labels(failed, labels_map_getter=lambda ids: {}) == failed


class TestGetTaskListOldEngineLabels:
    """旧 engine 任务列表没有 labels 时，管理端列表不能 500。"""

    def _request(self, query_params=None):
        params = dict(query_params or {})
        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.copy.return_value = params
        request.query_params.get.side_effect = params.get
        return request

    @mock.patch("bkflow.interface.task.view.Label.get_label_ids_by_names", return_value=[])
    @mock.patch("bkflow.interface.task.view.Label.objects.get_labels_map")
    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_list_tolerates_missing_labels(self, mock_client_class, mock_get_labels_map, _mock_ids):
        mock_get_labels_map.return_value = {}
        mock_client = mock.Mock()
        mock_client.task_list.return_value = {
            "result": True,
            "data": {"results": [{"id": 2401, "name": "legacy task"}]},
        }
        mock_client_class.return_value = mock_client

        response = TaskInterfaceAdminViewSet().get_task_list(self._request({"space_id": "240"}), space_id=240)

        assert response.data["result"] is True
        assert response.data["data"]["results"][0]["id"] == 2401
        assert response.data["data"]["results"][0]["labels"] == []

    @mock.patch("bkflow.interface.task.view.Label.get_label_ids_by_names", return_value=[])
    @mock.patch("bkflow.interface.task.view.Label.objects.get_labels_map")
    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_list_keeps_existing_labels(self, mock_client_class, mock_get_labels_map, _mock_ids):
        mock_get_labels_map.return_value = {7: {"id": 7, "name": "prod"}}
        mock_client = mock.Mock()
        mock_client.task_list.return_value = {
            "result": True,
            "data": {"results": [{"id": 1, "name": "new engine task", "labels": [7]}]},
        }
        mock_client_class.return_value = mock_client

        response = TaskInterfaceAdminViewSet().get_task_list(self._request({}), space_id=1)

        assert response.data["data"]["results"][0]["labels"] == [{"id": 7, "name": "prod"}]
        mock_get_labels_map.assert_called_once_with({7})

    @mock.patch("bkflow.interface.task.view.Label.get_label_ids_by_names", return_value=[])
    @mock.patch("bkflow.interface.task.view.Label.objects.get_labels_map")
    @mock.patch("bkflow.interface.task.view.TaskComponentClient")
    def test_get_task_list_passthrough_when_engine_fails(self, mock_client_class, mock_get_labels_map, _mock_ids):
        failed = {"result": False, "message": "Request API error, status_code: 500, url: http://engine/task/"}
        mock_client = mock.Mock()
        mock_client.task_list.return_value = failed
        mock_client_class.return_value = mock_client

        response = TaskInterfaceAdminViewSet().get_task_list(self._request({}), space_id=1)

        assert response.data == failed
        mock_get_labels_map.assert_not_called()
