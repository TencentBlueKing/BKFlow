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

from bkflow.template.debug.service import DebugConflictError, DebugService
from bkflow.template.models import DebugNodeState

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
