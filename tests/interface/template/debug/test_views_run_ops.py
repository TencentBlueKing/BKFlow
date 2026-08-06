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

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, DebugNodeState
from bkflow.template.views.debug import DebugViewSet

User = get_user_model()

TREE = {
    "activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
    "flows": {},
    "gateways": {},
    "constants": {},
}


@pytest.mark.django_db
class TestRunOpsViews:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user, _ = User.objects.update_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )

    def _patch_tree(self, mocker):
        mocker.patch(
            "bkflow.template.debug.service.DebugService.pipeline_tree",
            new_callable=mocker.PropertyMock,
            return_value=TREE,
        )
        mocker.patch(
            "bkflow.template.debug.service.DebugService.space_id",
            new_callable=mocker.PropertyMock,
            return_value=10,
        )

    def test_global_run_conflict_returns_standard_error(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", locked_by="bob")
        view = DebugViewSet.as_view({"post": "global_run"})
        request = self.factory.post(
            "/debug/global_run/", {"space_id": 10, "template_id": 1, "inputs": {}}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["result"] is False

    def test_reset_clears_results(self, mocker):
        self._patch_tree(mocker)
        ctx = DebugContext.objects.create(template_id=1, space_id=10)
        DebugNodeState.objects.create(debug_context=ctx, node_id="A", status="finished", outputs={"k": "v"})
        view = DebugViewSet.as_view({"post": "reset"})
        request = self.factory.post("/debug/reset/", {"space_id": 10, "template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert "A" in response.data["data"]["reset_node_ids"]
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").status == "not_run"

    def test_terminate_global_revokes(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", active_task_id=456)
        client = mocker.MagicMock()
        client.operate_task.return_value = {"result": True, "data": {}, "message": ""}
        mocker.patch.object(DebugService, "_task_client", return_value=client)

        view = DebugViewSet.as_view({"post": "terminate"})
        request = self.factory.post("/debug/terminate/", {"space_id": 10, "template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert response.data["data"]["status"] == "terminating"
        client.operate_task.assert_called_once_with(456, "revoke", {"operator": "admin"})

    def test_history_lists_debug_runs(self, mocker):
        self._patch_tree(mocker)
        client = mocker.MagicMock()
        client.task_list.return_value = {
            "result": True,
            "data": {"results": [{"id": 7, "creator": "admin", "start_time": "t", "is_finished": True}]},
            "message": "",
        }
        client.get_tasks_states.return_value = {
            "result": True,
            "data": {"7": {"state": "FAILED"}},
            "message": "",
        }
        mocker.patch.object(DebugService, "_task_client", return_value=client)

        view = DebugViewSet.as_view({"get": "history"})
        request = self.factory.get("/debug/history/", {"space_id": 10, "template_id": 1})
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert response.data["data"]["runs"][0]["task_id"] == 7
        assert response.data["data"]["runs"][0]["status"] == "failed"
        client.get_tasks_states.assert_called_once_with(data={"task_ids": [7], "space_id": 10})

    def test_reset_while_running_returns_standard_error(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", locked_by="bob")
        view = DebugViewSet.as_view({"post": "reset"})
        request = self.factory.post("/debug/reset/", {"space_id": 10, "template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["result"] is False

    def test_terminate_when_idle_returns_standard_error(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="idle")
        view = DebugViewSet.as_view({"post": "terminate"})
        request = self.factory.post("/debug/terminate/", {"space_id": 10, "template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["result"] is False

    def test_terminate_node_uses_forced_fail_and_resets_node(self, mocker):
        """单节点终止后立即恢复未调试并释放调试锁。"""
        self._patch_tree(mocker)
        ctx = DebugContext.objects.create(
            template_id=1,
            space_id=10,
            status="running",
            active_task_id=456,
            active_run_type="step",
            active_node_id="A",
            last_task_id=456,
            last_run_type="step",
            last_run_status="waiting",
            last_error_detail={"type": "runtime", "message": "old error"},
        )
        DebugNodeState.objects.create(
            debug_context=ctx,
            node_id="A",
            status="waiting",
            waiting_reason="poll",
            inputs={"input": "value"},
            outputs={"output": "value"},
            duration_ms=3000,
            error_detail={"message": "old error"},
            log_ref={"instance_id": 456, "node_id": "rtA", "version": "v1"},
        )
        client = mocker.MagicMock()
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        client.node_operate.return_value = {"result": True, "data": {}, "message": ""}
        mocker.patch.object(DebugService, "_task_client", return_value=client)

        view = DebugViewSet.as_view({"post": "terminate"})
        request = self.factory.post(
            "/debug/terminate/", {"space_id": 10, "template_id": 1, "node_id": "A"}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert response.data["data"] == {"status": "idle", "reset_node_ids": ["A"]}
        client.node_operate.assert_called_once_with(
            456,
            "rtA",
            "forced_fail",
            {"operator": "admin", "suppress_failure_side_effects": True},
        )

        ctx.refresh_from_db()
        node_state = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert node_state.status == "not_run"
        assert node_state.waiting_reason == ""
        assert node_state.inputs == {}
        assert node_state.outputs == {}
        assert node_state.duration_ms is None
        assert node_state.error_detail == {}
        assert node_state.log_ref == {}
        assert ctx.status == "idle"
        assert ctx.active_task_id is None
        assert ctx.active_run_type == ""
        assert ctx.active_node_id == ""
        assert ctx.last_task_id == 456
        assert ctx.last_run_type == "step"
        assert ctx.last_run_status == "not_run"
        assert ctx.last_error_detail == {}

    def test_terminate_failure_rolls_back_to_running(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", active_task_id=456)
        client = mocker.MagicMock()
        client.operate_task.return_value = {"result": False, "data": {}, "message": "no"}
        mocker.patch.object(DebugService, "_task_client", return_value=client)

        view = DebugViewSet.as_view({"post": "terminate"})
        request = self.factory.post("/debug/terminate/", {"space_id": 10, "template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert response.data["result"] is False
        assert DebugContext.objects.get(template_id=1).status == "running"
