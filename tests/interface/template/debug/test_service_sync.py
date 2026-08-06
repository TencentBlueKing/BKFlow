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

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugNodeState

PIPELINE = {
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
            "custom_type": "",
            "source_tag": "",
            "source_info": {"A": ["k1"]},
        }
    },
}

PIPELINE_GATEWAY = {
    "activities": {},
    "flows": {
        "flow_positive": {"id": "flow_positive", "source": "G", "target": "positive"},
        "flow_default": {"id": "flow_default", "source": "G", "target": "fallback"},
    },
    "gateways": {
        "G": {
            "id": "G",
            "type": "ExclusiveGateway",
            "conditions": {"flow_positive": {"name": "positive", "evaluate": "${count} > 0"}},
            "default_condition": {"flow_id": "flow_default"},
            "extra_info": {"parse_lang": "boolrule"},
        }
    },
    "constants": {
        "${count}": {
            "key": "${count}",
            "name": "count",
            "show_type": "hide",
            "value": 0,
            "source_type": "custom",
            "custom_type": "int",
            "source_tag": "",
            "source_info": {},
        }
    },
}


@pytest.mark.django_db
class TestSyncFromDebugTask:
    def test_sync_writes_back_status_and_global_vars(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "running"
        ctx.active_task_id = 456
        ctx.active_run_type = "global"
        ctx.last_task_id = 456
        ctx.last_run_type = "global"
        ctx.last_run_status = "running"
        ctx.save()

        client = mocker.MagicMock()
        # 任务整体结束
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED", "elapsed_time": 2}}},
            "message": "",
        }
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        # 节点 A 的输出（含产出 k1）
        client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"outputs": [{"key": "k1", "value": "produced"}], "version": "v1"},
            "message": "",
        }
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)
        ctx.refresh_from_db()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "finished"
        assert ns.log_ref == {"instance_id": 456, "node_id": "rtA", "version": "v1"}
        assert ctx.global_vars.get("${g1}") == "produced"
        assert ctx.status == "idle"  # 整体结束后解锁
        assert ctx.active_task_id is None
        assert ctx.active_run_type == ""
        assert ctx.last_task_id == 456
        assert ctx.last_run_type == "global"
        assert ctx.last_run_status == "finished"
        assert ctx.last_error_detail == {}

    def test_sync_running_task_does_not_release_lock(self, mocker):
        """任务运行中：回写节点态与耗时，但不释放锁"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "running"
        ctx.active_task_id = 456
        ctx.save()

        client = mocker.MagicMock()
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "RUNNING", "children": {"rtA": {"state": "RUNNING", "elapsed_time": 1}}},
            "message": "",
        }
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)
        ctx.refresh_from_db()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ctx.status == "running"  # 未结束，不解锁
        assert ns.status == "running"
        assert ns.duration_ms == 1000  # elapsed_time(s) -> ms

    def test_sync_step_callback_is_waiting_and_keeps_lock(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "running"
        ctx.active_task_id = 456
        ctx.active_run_type = "step"
        ctx.active_node_id = "A"
        ctx.last_task_id = 456
        ctx.last_run_type = "step"
        ctx.last_run_status = "running"
        ctx.save()

        client = mocker.MagicMock()
        client.get_task_states.return_value = {
            "result": True,
            "data": {
                "state": "RUNNING",
                "children": {"rtA": {"state": "RUNNING", "elapsed_time": 2, "schedule_type": "CALLBACK"}},
            },
            "message": "",
        }
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)

        ctx.refresh_from_db()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "waiting"
        assert ns.waiting_reason == "callback"
        assert ctx.status == "running"
        assert ctx.active_task_id == 456
        assert ctx.last_run_status == "waiting"
        client.get_task_states.assert_called_once_with(456, data={"with_ex_data": True, "include_schedule": True})

    def test_sync_step_completion_writes_outputs_and_releases_lock(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "running"
        ctx.active_task_id = 456
        ctx.active_run_type = "step"
        ctx.active_node_id = "A"
        ctx.last_task_id = 456
        ctx.last_run_type = "step"
        ctx.last_run_status = "waiting"
        ctx.save()

        client = mocker.MagicMock()
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED", "elapsed_time": 3}}},
            "message": "",
        }
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"outputs": [{"key": "k1", "value": "produced"}], "version": "v2"},
            "message": "",
        }
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)

        ctx.refresh_from_db()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "finished"
        assert ns.waiting_reason == ""
        assert ns.duration_ms == 3000
        assert ns.outputs == {"k1": "produced"}
        assert ctx.global_vars["${g1}"] == "produced"
        assert ctx.status == "idle"
        assert ctx.active_task_id is None
        assert ctx.active_run_type == ""
        assert ctx.active_node_id == ""
        assert ctx.last_task_id == 456
        assert ctx.last_run_status == "finished"

    @pytest.mark.parametrize(
        "child",
        [
            {"state": "RUNNING", "elapsed_time": 3},
            {"state": "RUNNING", "elapsed_time": 3, "schedule_type": "POLL"},
            {"state": "SUSPENDED", "elapsed_time": 3},
        ],
        ids=["running", "waiting", "paused"],
    )
    def test_sync_revoked_task_resets_active_node(self, mocker, child):
        """全局调试终止后整体记为 revoked，活跃节点恢复为未调试。"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "terminating"
        ctx.active_task_id = 456
        ctx.active_run_type = "global"
        ctx.last_task_id = 456
        ctx.last_run_type = "global"
        ctx.last_run_status = "running"
        ctx.save()

        client = mocker.MagicMock()
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "REVOKED", "children": {"rtA": child}},
            "message": "",
        }
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)

        ctx.refresh_from_db()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "not_run"
        assert ns.waiting_reason == ""
        assert ns.duration_ms is None
        assert ctx.status == "idle"
        assert ctx.active_task_id is None
        assert ctx.last_task_id == 456
        assert ctx.last_run_status == "revoked"
        assert ctx.last_error_detail == {}

    @pytest.mark.parametrize("stale_status", ["running", "waiting", "paused", "revoked"])
    def test_sync_repairs_stale_active_node_after_revoked_task_was_released(self, mocker, stale_status):
        """兼容发布前遗留状态：已终止全局调试的活跃节点恢复为未调试。"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "idle"
        ctx.active_task_id = None
        ctx.last_task_id = 456
        ctx.last_run_status = "revoked"
        ctx.save()
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(
            status=stale_status,
            waiting_reason="poll",
            inputs={"input": "value"},
            outputs={"output": "value"},
            duration_ms=3000,
            error_detail={"message": "old error"},
            log_ref={"instance_id": 456},
        )
        task_client = mocker.patch.object(svc, "_task_client")

        svc.sync_from_debug_task(ctx)

        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "not_run"
        assert ns.waiting_reason == ""
        assert ns.inputs == {}
        assert ns.outputs == {}
        assert ns.duration_ms is None
        assert ns.error_detail == {}
        assert ns.log_ref == {}
        task_client.assert_not_called()

    def test_sync_gateway_failure_fetches_detail_when_state_ex_data_is_empty(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE_GATEWAY)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "running"
        ctx.active_task_id = 456
        ctx.active_run_type = "global"
        ctx.last_task_id = 456
        ctx.last_run_type = "global"
        ctx.last_run_status = "running"
        ctx.save()

        client = mocker.MagicMock()
        client.get_task_states.return_value = {
            "result": True,
            "data": {
                "state": "FAILED",
                "children": {"rt_gateway": {"state": "FAILED", "elapsed_time": 0}},
                "ex_data": {},
            },
            "message": "",
        }
        client.get_node_id_map.return_value = {
            "result": True,
            "data": {"A": "rtA", "G": "rt_gateway"},
            "message": "",
        }
        client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"ex_data": "multiple conditions meet", "outputs": []},
            "message": "",
        }
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)

        ctx.refresh_from_db()
        assert ctx.status == "idle"
        assert ctx.active_task_id is None
        assert ctx.last_task_id == 456
        assert ctx.last_run_status == "failed"
        assert ctx.last_error_detail == {
            "type": "runtime",
            "message": "multiple conditions meet",
            "task_id": 456,
            "failures": [
                {
                    "node_id": "rt_gateway",
                    "template_node_id": "G",
                    "message": "multiple conditions meet",
                }
            ],
        }
        gateway = DebugNodeState.objects.get(debug_context=ctx, node_id="G")
        assert gateway.status == "failed"
        assert gateway.error_detail == {"type": "runtime", "message": "multiple conditions meet"}
        client.get_task_node_detail.assert_called_once_with(456, "rt_gateway", data={"include_data": True})

    def test_sync_finished_gateway_persists_selected_flows(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE_GATEWAY)
        ctx = svc.sync_node_states()
        ctx.status = "running"
        ctx.active_task_id = 456
        ctx.active_run_type = "global"
        ctx.global_vars = {"${count}": 1}
        ctx.last_run_status = "running"
        ctx.save()

        client = mocker.MagicMock()
        client.get_task_states.return_value = {
            "result": True,
            "data": {
                "state": "FINISHED",
                "children": {"rt_gateway": {"state": "FINISHED", "elapsed_time": 0.1}},
            },
            "message": "",
        }
        client.get_node_id_map.return_value = {"result": True, "data": {"G": "rt_gateway"}, "message": ""}
        client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"outputs": [], "version": "v1"},
            "message": "",
        }
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)

        gateway = DebugNodeState.objects.get(debug_context=ctx, node_id="G")
        assert gateway.status == "finished"
        assert gateway.outputs["selected_flow_ids"] == ["flow_positive"]
        assert gateway.outputs["condition_results"][0]["matched"] is True
        assert gateway.log_ref == {"instance_id": 456, "node_id": "rt_gateway", "version": "v1"}

    def test_sync_returns_early_when_node_id_map_fails(self, mocker):
        """id_map 调用失败：不回写、不释放锁，结束结果可在下次重试"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "running"
        ctx.active_task_id = 456
        ctx.save()

        client = mocker.MagicMock()
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED", "elapsed_time": 2}}},
            "message": "",
        }
        client.get_node_id_map.return_value = {"result": False, "data": {}, "message": "boom"}
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)
        ctx.refresh_from_db()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ctx.status == "running"  # 未释放锁（Must-fix #1）
        assert ns.status == "not_run"  # 无任何回写
