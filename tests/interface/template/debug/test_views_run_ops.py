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

    def test_global_run_conflict_returns_409(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", locked_by="bob")
        view = DebugViewSet.as_view({"post": "global_run"})
        request = self.factory.post("/debug/global_run/", {"template_id": 1, "inputs": {}}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 409

    def test_reset_clears_results(self, mocker):
        self._patch_tree(mocker)
        ctx = DebugContext.objects.create(template_id=1, space_id=10)
        DebugNodeState.objects.create(debug_context=ctx, node_id="A", status="finished", outputs={"k": "v"})
        view = DebugViewSet.as_view({"post": "reset"})
        request = self.factory.post("/debug/reset/", {"template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert "A" in response.data["reset_node_ids"]
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").status == "not_run"

    def test_terminate_global_revokes(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", active_task_id=456)
        client = mocker.MagicMock()
        client.operate_task.return_value = {"result": True, "data": {}, "message": ""}
        mocker.patch.object(DebugService, "_task_client", return_value=client)

        view = DebugViewSet.as_view({"post": "terminate"})
        request = self.factory.post("/debug/terminate/", {"template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert response.data["status"] == "terminating"
        client.operate_task.assert_called_once_with(456, "revoke", {"operator": "admin"})

    def test_history_lists_debug_runs(self, mocker):
        self._patch_tree(mocker)
        client = mocker.MagicMock()
        client.task_list.return_value = {
            "result": True,
            "data": {"results": [{"id": 7, "creator": "admin", "start_time": "t", "is_finished": True}]},
            "message": "",
        }
        mocker.patch.object(DebugService, "_task_client", return_value=client)

        view = DebugViewSet.as_view({"get": "history"})
        request = self.factory.get("/debug/history/", {"template_id": 1})
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert response.data["runs"][0]["task_id"] == 7
        assert response.data["runs"][0]["status"] == "finished"

    def test_reset_while_running_returns_409(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", locked_by="bob")
        view = DebugViewSet.as_view({"post": "reset"})
        request = self.factory.post("/debug/reset/", {"template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 409

    def test_terminate_when_idle_returns_400(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="idle")
        view = DebugViewSet.as_view({"post": "terminate"})
        request = self.factory.post("/debug/terminate/", {"template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 400

    def test_terminate_node_uses_forced_fail(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", active_task_id=456)
        client = mocker.MagicMock()
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        client.node_operate.return_value = {"result": True, "data": {}, "message": ""}
        mocker.patch.object(DebugService, "_task_client", return_value=client)

        view = DebugViewSet.as_view({"post": "terminate"})
        request = self.factory.post("/debug/terminate/", {"template_id": 1, "node_id": "A"}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert response.data["status"] == "terminating"
        client.node_operate.assert_called_once_with(456, "rtA", "forced_fail", {"operator": "admin"})

    def test_terminate_failure_rolls_back_to_running(self, mocker):
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10, status="running", active_task_id=456)
        client = mocker.MagicMock()
        client.operate_task.return_value = {"result": False, "data": {}, "message": "no"}
        mocker.patch.object(DebugService, "_task_client", return_value=client)

        view = DebugViewSet.as_view({"post": "terminate"})
        request = self.factory.post("/debug/terminate/", {"template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 400
        assert DebugContext.objects.get(template_id=1).status == "running"
