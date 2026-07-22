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

PIPELINE = {
    "activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
    "flows": {},
    "gateways": {},
    "constants": {},
}


def _create_task_payload(client):
    call = client.create_task.call_args
    return call.args[0] if call.args else call.kwargs


@pytest.mark.django_db
class TestGlobalRun:
    def _svc(self, mocker, create_ok=True, task_id=456):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        client = mocker.MagicMock()
        client.create_task.return_value = {"result": create_ok, "data": {"id": task_id}, "message": ""}
        client.operate_task.return_value = {"result": True, "data": {}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)
        return svc, client

    def test_global_run_locks_resets_and_starts(self, mocker):
        svc, client = self._svc(mocker)
        ctx = svc.get_or_create_context()
        DebugNodeState.objects.create(
            debug_context=ctx,
            node_id="A",
            status="finished",
            outputs={"k": "v"},
            execution_mode="mock",
            mock_outputs={"k": "v"},
        )

        result = svc.global_run(inputs={"${biz}": "100"}, operator="admin")

        ctx.refresh_from_db()
        assert result["task_id"] == 456
        assert ctx.status == "running"
        assert ctx.active_task_id == 456
        assert ctx.active_run_type == "global"
        assert ctx.active_node_id == ""
        assert ctx.last_task_id == 456
        assert ctx.last_run_type == "global"
        assert ctx.last_run_status == "running"
        assert ctx.last_error_detail == {}
        assert ctx.last_inputs == {"${biz}": "100"}

        # 重置运行结果、保留 mock 配置
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "not_run" and ns.outputs == {}
        assert ns.execution_mode == "mock" and ns.mock_outputs == {"k": "v"}

        # 物化 mock_data 与 create_method 传入 create_task
        sent = _create_task_payload(client)
        assert sent["create_method"] == "DEBUG"
        assert sent["mock_data"] == {"nodes": ["A"], "outputs": {"A": {"k": "v"}}, "fail_nodes": [], "errors": {}}

        # 启动调用使用 operate_task(task_id, "start", {...})
        client.operate_task.assert_called_once_with(456, "start", {"operator": "admin"})

    def test_global_run_passes_inputs_as_constants(self, mocker):
        svc, client = self._svc(mocker)
        svc.get_or_create_context()

        svc.global_run(inputs={"${biz}": "100"}, operator="admin")

        sent = _create_task_payload(client)
        assert sent["constants"] == {"${biz}": "100"}

    def test_global_run_rejects_when_not_idle(self, mocker):
        svc, _ = self._svc(mocker)
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.locked_by = "bob"
        ctx.save()

        with pytest.raises(Exception) as exc:
            svc.global_run(inputs={}, operator="admin")
        assert "bob" in str(exc.value)

    def test_global_run_releases_lock_on_create_failure(self, mocker):
        """create 失败：释放锁、不残留 active_task_id，且不尝试删除（无任务被创建）"""
        svc, client = self._svc(mocker, create_ok=False)
        ctx = svc.get_or_create_context()

        with pytest.raises(Exception):
            svc.global_run(inputs={}, operator="admin")

        ctx.refresh_from_db()
        assert ctx.status == "idle"
        assert ctx.locked_by == ""
        assert ctx.active_task_id is None
        client.delete_task.assert_not_called()

    def test_global_run_releases_lock_on_start_failure(self, mocker):
        """start 失败：释放锁、清空 active_task_id，并清理已创建的孤儿任务"""
        svc, client = self._svc(mocker)
        client.operate_task.return_value = {"result": False, "data": {}, "message": "start boom"}
        ctx = svc.get_or_create_context()

        with pytest.raises(Exception):
            svc.global_run(inputs={}, operator="admin")

        ctx.refresh_from_db()
        assert ctx.status == "idle"
        assert ctx.locked_by == ""
        assert ctx.active_task_id is None
        assert ctx.last_task_id == 456
        assert ctx.last_run_type == "global"
        assert ctx.last_run_status == "failed"
        assert ctx.last_error_detail == {"type": "start", "message": "start boom", "task_id": 456}
        client.delete_task.assert_called_once_with(456)

    def test_acquire_lock_conflict_branch(self, mocker):
        """直接验证 CAS 0 行更新分支：被既有锁占用时抛 DebugConflictError"""
        svc, _ = self._svc(mocker)
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.locked_by = "carol"
        ctx.save()

        with pytest.raises(DebugConflictError) as exc:
            svc._acquire_lock(ctx, "admin")
        assert "carol" in str(exc.value)

    def test_global_run_materializes_fail_node(self, mocker):
        """mock_result=fail 的节点应物化为 fail_nodes 与 errors"""
        svc, client = self._svc(mocker)
        ctx = svc.get_or_create_context()
        DebugNodeState.objects.create(
            debug_context=ctx,
            node_id="A",
            execution_mode="mock",
            mock_result="fail",
            mock_error="boom",
        )

        svc.global_run(inputs={}, operator="admin")

        sent = _create_task_payload(client)
        assert sent["mock_data"]["fail_nodes"] == ["A"]
        assert sent["mock_data"]["errors"] == {"A": "boom"}
