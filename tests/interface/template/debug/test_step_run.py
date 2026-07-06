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

from bkflow.template.debug.service import (
    DebugConflictError,
    DebugService,
    DebugStateError,
)
from bkflow.template.models import DebugContext, DebugNodeState
from bkflow.template.views.debug import DebugViewSet

User = get_user_model()

TREE = {
    "activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
    "flows": {},
    "gateways": {},
    "constants": {
        "${g1}": {
            "key": "${g1}",
            "name": "g1",
            "show_type": "hide",
            "value": "",
            "source_type": "component_outputs",
            "source_info": {"A": ["k1"]},
            "custom_type": "",
            "source_tag": "",
        }
    },
}

# B 依赖 A 产出的 ${g1}：global_vars 为空时 B 不可单步（compute_can_step 门控）
TREE_DEP = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
        "B": {
            "id": "B",
            "type": "ServiceActivity",
            "component": {"code": "t", "data": {"y": {"hook": True, "value": "${g1}"}}},
        },
    },
    "flows": {},
    "gateways": {},
    "constants": {
        "${g1}": {
            "key": "${g1}",
            "name": "g1",
            "show_type": "hide",
            "value": "",
            "source_type": "component_outputs",
            "source_info": {"A": ["k1"]},
            "custom_type": "",
            "source_tag": "",
        }
    },
}


@pytest.mark.django_db
class TestStepRunAndMock:
    def test_step_run_mock_success_writes_global_vars(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        result = svc.step_run(
            node_id="A", operator="admin", mode="mock", mock_result="success", mock_outputs={"k1": "produced"}
        )
        assert result["status"] == "finished"
        assert result["outputs"] == {"k1": "produced"}
        ctx.refresh_from_db()
        assert ctx.global_vars["${g1}"] == "produced"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "finished" and ns.log_ref in (None, {})

    def test_step_run_mock_fail_sets_failed_no_writeback(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        result = svc.step_run(node_id="A", operator="admin", mode="mock", mock_result="fail", mock_error="boom")
        assert result["status"] == "failed"
        assert result["error_detail"]["message"] == "boom"
        ctx.refresh_from_db()
        assert "${g1}" not in ctx.global_vars

    def test_node_mock_sets_execution_mode_mock_and_writes_back(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        result = svc.node_mock(node_id="A", enable=True, mock_result="success", mock_outputs={"k1": "v"})
        assert result["execution_mode"] == "mock"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.execution_mode == "mock" and ns.mock_outputs == {"k1": "v"}
        ctx.refresh_from_db()
        assert ctx.global_vars["${g1}"] == "v"

    def test_node_mock_disable_keeps_presets(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        svc.node_mock(node_id="A", enable=True, mock_result="success", mock_outputs={"k1": "v"})
        result = svc.node_mock(node_id="A", enable=False)
        assert result["execution_mode"] == "real"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.execution_mode == "real" and ns.mock_outputs == {"k1": "v"}

    def test_context_var_sets_value(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        svc.get_or_create_context()
        result = svc.set_context_var(key="${biz}", value="200")
        assert result["global_vars"]["${biz}"] == "200"

    def test_context_var_blocked_when_running(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.save()
        with pytest.raises(DebugConflictError):
            svc.set_context_var(key="${biz}", value="200")

    def test_node_mock_does_not_mark_status(self):
        """配置 mock 不应把节点标记为 finished（评审 #3）"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        svc.node_mock(node_id="A", enable=True, mock_result="success", mock_outputs={"k1": "v"})
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "not_run"  # 仅配置，未运行

    def test_step_run_real_targets_activity_and_records_duration(self, mocker):
        """real 单步应命中活动 runtime id（非 start/end 事件）并落库耗时（评审 #1/#2）"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()

        client = mocker.MagicMock()
        # 修正 #1：创建任务返回的 id 在 data.id；修正 #2：启动用 operate_task
        client.create_task.return_value = {"result": True, "data": {"id": 789}, "message": ""}
        client.operate_task.return_value = {"result": True, "data": {}, "message": ""}
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        client.get_task_states.return_value = {
            "result": True,
            "data": {
                "state": "FINISHED",
                "children": {
                    "start_evt": {"state": "FINISHED", "elapsed_time": 0},
                    "rtA": {"state": "FINISHED", "elapsed_time": 3},
                },
            },
            "message": "",
        }
        client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"outputs": [{"key": "k1", "value": "produced"}], "version": "v1"},
            "message": "",
        }
        mocker.patch.object(svc, "_task_client", return_value=client)

        result = svc.step_run(node_id="A", operator="admin", mode="real")
        assert result["status"] == "finished"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.log_ref == {"instance_id": 789, "node_id": "rtA", "version": "v1"}
        assert ns.duration_ms == 3000
        ctx.refresh_from_db()
        assert ctx.global_vars["${g1}"] == "produced"

    def test_step_run_real_create_failure_raises_and_releases_lock(self, mocker):
        """create 失败：抛 DebugStateError、释放锁、无任务故不清理（I-1）"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()

        client = mocker.MagicMock()
        client.create_task.return_value = {"result": False, "message": "x"}
        mocker.patch.object(svc, "_task_client", return_value=client)

        with pytest.raises(DebugStateError):
            svc.step_run(node_id="A", operator="admin", mode="real")
        ctx.refresh_from_db()
        assert ctx.status == "idle"
        client.delete_task.assert_not_called()

    def test_step_run_real_start_failure_cleans_up(self, mocker):
        """start 失败：抛 DebugStateError、删除孤儿任务、节点解卡、释放锁（I-2）"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()

        client = mocker.MagicMock()
        client.create_task.return_value = {"result": True, "data": {"id": 789}, "message": ""}
        client.operate_task.return_value = {"result": False, "message": "no"}
        mocker.patch.object(svc, "_task_client", return_value=client)

        with pytest.raises(DebugStateError):
            svc.step_run(node_id="A", operator="admin", mode="real")
        ctx.refresh_from_db()
        assert ctx.status == "idle"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status != "running"
        client.delete_task.assert_called_once_with(789)

    def test_step_run_real_blocked_by_can_step(self, mocker):
        """依赖未满足：抛 DebugStateError(missing_vars)，门控在抢锁/建任务前，零引擎交互"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_DEP)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()

        client = mocker.MagicMock()
        mocker.patch.object(svc, "_task_client", return_value=client)

        with pytest.raises(DebugStateError) as exc_info:
            svc.step_run(node_id="B", operator="admin", mode="real")
        assert "missing_vars" in exc_info.value.args[0]
        client.create_task.assert_not_called()
        ctx.refresh_from_db()
        assert ctx.status == "idle"

    def test_step_run_real_failed_node_keeps_task(self, mocker):
        """引擎正常跑完但节点失败：正常返回 failed，不删任务（log_ref 仍可查日志），不回写全局变量"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()

        client = mocker.MagicMock()
        client.create_task.return_value = {"result": True, "data": {"id": 789}, "message": ""}
        client.operate_task.return_value = {"result": True, "data": {}, "message": ""}
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FAILED", "children": {"rtA": {"state": "FAILED", "elapsed_time": 1}}},
            "message": "",
        }
        client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"ex_data": "boom", "version": "v1"},
            "message": "",
        }
        mocker.patch.object(svc, "_task_client", return_value=client)

        result = svc.step_run(node_id="A", operator="admin", mode="real")
        assert result["status"] == "failed"
        assert result["error_detail"]
        client.delete_task.assert_not_called()
        ctx.refresh_from_db()
        assert "${g1}" not in ctx.global_vars
        assert ctx.status == "idle"

    def test_step_run_bad_node_raises_state_error(self):
        """未知 node_id 收敛为 DebugStateError，而非 DoesNotExist/500（I-5）"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        svc.get_or_create_context()
        svc.sync_node_states()
        with pytest.raises(DebugStateError):
            svc.step_run(node_id="ZZZ", operator="admin", mode="mock")


@pytest.mark.django_db
class TestStepRunViews:
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

    def test_node_mock_bad_node_returns_400(self, mocker):
        """node_mock 视图：未知 node_id 返回 400 而非 500（I-5）"""
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10)
        view = DebugViewSet.as_view({"post": "node_mock"})
        request = self.factory.post(
            "/debug/node_mock/", {"space_id": 10, "template_id": 1, "node_id": "ZZZ"}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 400
        assert response.data["detail"] == {"detail": "节点不存在", "node_id": "ZZZ"}
