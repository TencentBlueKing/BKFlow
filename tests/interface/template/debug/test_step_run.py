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

import copy

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

TREE_GATEWAY = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
    },
    "flows": {
        "flow_positive": {"id": "flow_positive", "source": "G", "target": "A"},
        "flow_default": {"id": "flow_default", "source": "G", "target": "A"},
    },
    "gateways": {
        "G": {
            "id": "G",
            "type": "ExclusiveGateway",
            "conditions": {"flow_positive": {"name": "positive", "evaluate": "${g1} > 0"}},
            "default_condition": {"flow_id": "flow_default"},
            "extra_info": {"parse_lang": "boolrule"},
        }
    },
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

TREE_CONTROL_GATEWAYS = {
    "activities": {},
    "flows": {},
    "gateways": {
        "PG": {"id": "PG", "type": "ParallelGateway"},
        "CG": {"id": "CG", "type": "ConvergeGateway"},
    },
    "constants": {},
}


@pytest.mark.django_db
class TestStepRunAndMock:
    def test_step_run_gateway_evaluates_path_without_creating_task(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_GATEWAY)
        ctx = svc.get_or_create_context()
        ctx.global_vars = {"${g1}": 1}
        ctx.save(update_fields=["global_vars"])
        svc.sync_node_states()
        client = mocker.MagicMock()
        mocker.patch.object(svc, "_task_client", return_value=client)

        result = svc.step_run(node_id="G", operator="admin", mode="real")

        assert result["status"] == "finished"
        assert result["selected_flow_ids"] == ["flow_positive"]
        assert result["condition_results"][0]["matched"] is True
        assert "task_id" not in result
        client.create_task.assert_not_called()
        ctx.refresh_from_db()
        assert ctx.status == "idle"
        assert ctx.last_run_type == "step"
        assert ctx.last_run_status == "finished"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="G")
        assert ns.status == "finished"
        assert ns.outputs["selected_flow_ids"] == ["flow_positive"]

    def test_step_run_gateway_rejects_mock_mode(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_GATEWAY)
        svc.sync_node_states()

        with pytest.raises(DebugStateError, match="条件网关不支持 Mock"):
            svc.step_run(node_id="G", operator="admin", mode="mock")

    def test_node_mock_rejects_gateway(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_GATEWAY)
        svc.sync_node_states()

        with pytest.raises(DebugStateError, match="条件网关不支持 Mock"):
            svc.node_mock(node_id="G", enable=True)

    @pytest.mark.parametrize("node_id", ["PG", "CG"])
    def test_control_gateway_rejects_mock(self, node_id):
        """并行、汇聚网关只记录全局调试状态，不支持 Mock。"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_CONTROL_GATEWAYS)
        svc.sync_node_states()

        with pytest.raises(DebugStateError, match="网关节点不支持 Mock"):
            svc.node_mock(node_id=node_id, enable=True)

    @pytest.mark.parametrize("node_id", ["PG", "CG"])
    def test_control_gateway_rejects_step_run(self, node_id):
        """并行、汇聚网关只记录全局调试状态，不支持单步调试。"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_CONTROL_GATEWAYS)
        svc.sync_node_states()

        with pytest.raises(DebugStateError, match="网关节点不支持单步调试"):
            svc.step_run(node_id=node_id, operator="admin", mode="real")

    def test_step_run_gateway_is_blocked_when_output_dependency_is_missing(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_GATEWAY)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        client = mocker.MagicMock()
        mocker.patch.object(svc, "_task_client", return_value=client)

        with pytest.raises(DebugStateError) as exc_info:
            svc.step_run(node_id="G", operator="admin", mode="real")

        assert exc_info.value.args[0] == {
            "detail": "依赖未满足",
            "missing_vars": [{"key": "${g1}", "source_node_id": "A"}],
        }
        client.create_task.assert_not_called()
        ctx.refresh_from_db()
        assert ctx.status == "idle"

    def test_step_run_gateway_failure_is_persisted_and_releases_lock(self):
        tree = copy.deepcopy(TREE_GATEWAY)
        tree["gateways"]["G"]["conditions"] = {
            "flow_positive": {"name": "first", "evaluate": "1 == 1"},
            "flow_default": {"name": "second", "evaluate": "2 == 2"},
        }
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=tree)
        ctx = svc.sync_node_states()

        result = svc.step_run(node_id="G", operator="admin", mode="real")

        assert result["status"] == "failed"
        assert result["error_detail"]["type"] == "gateway"
        assert "多个分支条件同时满足" in result["error_detail"]["message"]
        ctx.refresh_from_db()
        assert ctx.status == "idle"
        assert ctx.last_run_status == "failed"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="G")
        assert ns.status == "failed"

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

    def test_step_run_real_starts_async_and_tracks_active_task(self, mocker):
        """real 单步命中活动 runtime id，启动后立即返回并由 context 后续追踪。"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()

        client = mocker.MagicMock()
        # 修正 #1：创建任务返回的 id 在 data.id；修正 #2：启动用 operate_task
        client.create_task.return_value = {"result": True, "data": {"id": 789}, "message": ""}
        client.operate_task.return_value = {"result": True, "data": {}, "message": ""}
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)

        result = svc.step_run(node_id="A", operator="admin", mode="real")
        assert result == {
            "node_id": "A",
            "task_id": 789,
            "status": "running",
            "log_ref": {"instance_id": 789, "node_id": "rtA", "version": "v1"},
        }
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.log_ref == {"instance_id": 789, "node_id": "rtA", "version": "v1"}
        ctx.refresh_from_db()
        assert ctx.status == "running"
        assert ctx.active_task_id == 789
        assert ctx.active_run_type == "step"
        assert ctx.active_node_id == "A"
        assert ctx.last_task_id == 789
        assert ctx.last_run_type == "step"
        assert ctx.last_run_status == "running"
        client.get_task_states.assert_not_called()
        client.get_task_node_detail.assert_not_called()

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
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
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

    def test_step_run_real_missing_runtime_id_cleans_up(self, mocker):
        """单步任务无法定位 runtime id 时立即清理，不留下无法同步的 active task。"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()

        client = mocker.MagicMock()
        client.create_task.return_value = {"result": True, "data": {"id": 789}, "message": ""}
        client.operate_task.return_value = {"result": True, "data": {}, "message": ""}
        client.get_node_id_map.return_value = {"result": True, "data": {}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)

        with pytest.raises(DebugStateError):
            svc.step_run(node_id="A", operator="admin", mode="real")

        client.delete_task.assert_called_once_with(789)
        ctx.refresh_from_db()
        assert ctx.status == "idle"
        assert ctx.active_task_id is None

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

    def _patch_tree(self, mocker, tree=TREE):
        mocker.patch(
            "bkflow.template.debug.service.DebugService.pipeline_tree",
            new_callable=mocker.PropertyMock,
            return_value=tree,
        )
        mocker.patch(
            "bkflow.template.debug.service.DebugService.space_id",
            new_callable=mocker.PropertyMock,
            return_value=10,
        )

    def test_node_mock_bad_node_returns_standard_error(self, mocker):
        """node_mock 视图：未知 node_id 返回标准错误协议。"""
        self._patch_tree(mocker)
        DebugContext.objects.create(template_id=1, space_id=10)
        view = DebugViewSet.as_view({"post": "node_mock"})
        request = self.factory.post("/debug/node_mock/", {"template_id": 1, "node_id": "ZZZ"}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["result"] is False
        assert response.data["data"]["detail"] == "{'detail': '节点不存在', 'node_id': 'ZZZ'}"

    def test_step_run_gateway_returns_selected_flows_in_standard_response(self, mocker):
        self._patch_tree(mocker, tree=TREE_GATEWAY)
        DebugContext.objects.create(template_id=1, space_id=10, global_vars={"${g1}": 1})
        view = DebugViewSet.as_view({"post": "step_run"})
        request = self.factory.post(
            "/debug/step_run/",
            {"space_id": 10, "template_id": 1, "node_id": "G", "mode": "real"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = view(request)

        assert response.status_code == 200
        assert response.data["result"] is True
        assert response.data["data"]["status"] == "finished"
        assert response.data["data"]["selected_flow_ids"] == ["flow_positive"]
        assert response.data["data"]["condition_results"][0]["matched"] is True
