"""取消 Mock 时重置本节点结果和产出变量，沿用下游依赖检查。"""

import copy
from unittest.mock import patch

import pytest

from bkflow.template.debug.service import (
    DebugConflictError,
    DebugService,
    DebugStateError,
)
from bkflow.template.models import DebugContext, DebugNodeState
from tests.interface.template.debug.test_step_run import TREE_DEP


@pytest.fixture
def completed_global_run(mocker):
    """通过真实服务入口完成全局调试；引擎请求全部由测试替身响应。"""
    tree = copy.deepcopy(TREE_DEP)
    for key, node_id, output_key in (("${extra}", "A", "extra"), ("${downstream}", "B", "value")):
        tree["constants"][key] = {
            **copy.deepcopy(tree["constants"]["${g1}"]),
            "key": key,
            "name": key,
            "source_info": {node_id: [output_key]},
        }
    svc = DebugService(template_id=1, space_id=10, pipeline_tree=tree)
    client = mocker.MagicMock()
    client.create_task.return_value = {"result": True, "data": {"id": 123}}
    client.operate_task.return_value = {"result": True}
    client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA", "B": "rtB"}}
    client.get_task_states.return_value = {
        "result": True,
        "data": {
            "state": "FINISHED",
            "children": {node_id: {"state": "FINISHED", "elapsed_time": 1} for node_id in ("rtA", "rtB")},
        },
    }

    def node_detail(task_id, node_id, **kwargs):
        """固定的执行输入输出用于验证快照清理及其他节点结果保留。"""
        outputs = {"k1": 10, "extra": 11} if node_id == "rtA" else {"value": 12}
        return {
            "result": True,
            "data": {"inputs": {"y": 10}, "outputs": [{"key": key, "value": val} for key, val in outputs.items()]},
        }

    client.get_task_node_detail.side_effect = node_detail
    mocker.patch.object(svc, "_task_client", return_value=client)
    svc.global_run({"${manual}": 13}, "tester")
    assert svc.build_context_view()["status"] == "idle"
    return svc, client


def snapshot_nodes(view):
    """按节点 ID 读取当前结果快照。"""
    return {node["node_id"]: node for node in view["debug_snapshot"]["nodes"]}


@pytest.mark.django_db
class TestCancelMock:
    @pytest.mark.parametrize("mock_run", [None, "success", "fail"])
    def test_cancel_resets_results_and_blocks_downstream(self, completed_global_run, mock_run):
        """仅配置、实际 Mock 成功或失败后取消，都清除本节点结果并拦截缺失依赖。"""
        svc, client = completed_global_run
        before = snapshot_nodes(svc.build_context_view())
        svc.node_mock("A", mock_outputs={"k1": 20})
        if mock_run:
            svc.step_run("A", "tester", mode="mock", mock_result=mock_run, mock_error="expected failure")

        result = svc.node_mock("A", enable=False)

        assert result == {
            "node_id": "A",
            "execution_mode": "real",
            "updated_global_vars": {"${downstream}": 12, "${manual}": 13},
        }
        state = DebugNodeState.objects.get(debug_context__template_id=1, node_id="A")
        assert state.status == "not_run"
        assert state.execution_mode == "real"
        assert state.inputs == state.outputs == state.error_detail == state.log_ref == {}
        assert state.duration_ms is None and state.last_run_at is None
        assert state.waiting_reason == ""
        assert state.mock_outputs == {"k1": 20}

        view = svc.build_context_view()
        nodes = snapshot_nodes(view)
        assert nodes["B"] == before["B"]
        assert nodes["A"]["status"] == "not_run"
        assert nodes["A"]["execution_mode"] == "real"
        assert nodes["A"]["inputs"] == nodes["A"]["outputs"] == {}
        for key in ("duration_ms", "last_run_at", "error_detail", "log_ref", "waiting_reason"):
            assert nodes["A"][key] is None
        assert nodes["A"]["configured_inputs"] == before["A"]["configured_inputs"]
        consumer = next(node for node in view["nodes"] if node["node_id"] == "B")
        assert consumer["status"] == "finished"
        assert consumer["can_step"] is False
        assert consumer["missing_vars"] == [{"key": "${g1}", "source_node_id": "A"}]
        client.reset_mock()
        with pytest.raises(DebugStateError, match="依赖未满足"):
            svc.step_run("B", "tester", mode="real")
        client.create_task.assert_not_called()

        # 上游再次真实执行产生变量后，下游恢复可执行；重复取消不再清理新结果。
        svc.step_run("A", "tester", mode="real")
        rerun_view = svc.build_context_view()
        assert rerun_view["global_vars"]["${g1}"] == 10
        assert next(node for node in rerun_view["nodes"] if node["node_id"] == "B")["can_step"] is True
        svc.node_mock("A", enable=False)
        assert svc.build_context_view() == rerun_view

    def test_cancel_removes_all_bound_outputs_after_preset_changes(self, completed_global_run):
        """清理范围按节点绑定，包含已从 Mock 预设移除和未被 Mock 覆盖的旧产出。"""
        svc, _ = completed_global_run
        svc.node_mock("A", mock_outputs={"k1": 20})
        svc.node_mock("A", mock_outputs={})
        result = svc.node_mock("A", enable=False)
        assert result["updated_global_vars"] == {"${downstream}": 12, "${manual}": 13}

    def test_cancel_real_node_preserves_existing_run(self, completed_global_run):
        """未开启 Mock 的节点收到重复关闭请求，不丢失已有真实调试结果。"""
        svc, _ = completed_global_run
        before = svc.build_context_view()
        svc.node_mock("A", enable=False)
        assert svc.build_context_view() == before

    def test_cancel_failed_mock_preset_keeps_preset_but_discards_previous_outputs(self, completed_global_run):
        """失败预设不产生新输出，取消时仍清理本节点此前产出并保留失败预设。"""
        svc, _ = completed_global_run
        svc.node_mock("A", mock_result="fail", mock_error="preset failure")
        result = svc.node_mock("A", enable=False)
        assert result["updated_global_vars"] == {"${downstream}": 12, "${manual}": 13}
        state = DebugNodeState.objects.get(debug_context__template_id=1, node_id="A")
        assert state.status == "not_run"
        assert state.mock_result == "fail" and state.mock_error == "preset failure"

    def test_cancel_before_first_run_does_not_create_snapshot(self):
        """仅保存预设后取消也会清变量，但不补造不存在的历史快照。"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_DEP)
        svc.node_mock("A", mock_outputs={"k1": 20})
        svc.node_mock("A", enable=False)
        view = svc.build_context_view()
        assert view["debug_snapshot"] is None
        assert view["global_vars"] == {}
        assert svc.compute_can_step(svc.get_or_create_context(), "B")[0] is False

    def test_explicit_input_override_remains_available(self, completed_global_run):
        """保留原有显式输入覆盖能力，取消 Mock 不扩大单步依赖限制。"""
        svc, client = completed_global_run
        svc.node_mock("A", mock_outputs={"k1": 20})
        svc.node_mock("A", enable=False)
        result = svc.step_run("B", "tester", mode="real", input_overrides={"${g1}": 99})
        assert result["status"] == "running"
        assert client.create_task.call_args.args[0]["pipeline_tree"]["constants"]["${g1}"]["value"] == 99

    @pytest.mark.parametrize("status", ["running", "terminating"])
    def test_cancel_rejected_during_run(self, completed_global_run, status):
        """调试锁有效时拒绝取消，不提前清理预设、结果或变量。"""
        svc, _ = completed_global_run
        svc.node_mock("A", mock_outputs={"k1": 20})
        ctx = svc.get_or_create_context()
        before = copy.deepcopy(ctx.debug_snapshot)
        ctx.status = status
        ctx.save(update_fields=["status"])
        with pytest.raises(DebugConflictError):
            svc.node_mock("A", enable=False)
        ctx.refresh_from_db()
        assert ctx.debug_snapshot == before
        assert ctx.global_vars["${g1}"] == 20
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").execution_mode == "mock"

    def test_cancel_rechecks_context_after_taking_lock(self, completed_global_run, mocker):
        """首次读取之后有任务启动时，以加锁后读到的状态为准，拒绝清理。"""
        svc, _ = completed_global_run
        svc.node_mock("A", mock_outputs={"k1": 20})
        stale_context = svc.get_or_create_context()
        mocker.patch.object(svc, "get_or_create_context", return_value=stale_context)
        DebugContext.objects.filter(pk=stale_context.pk).update(status="running")
        with pytest.raises(DebugConflictError):
            svc.node_mock("A", enable=False)
        stale_context.refresh_from_db()
        assert stale_context.global_vars["${g1}"] == 20
        assert DebugNodeState.objects.get(debug_context=stale_context, node_id="A").execution_mode == "mock"

    def test_cancel_rolls_back_all_changes_when_persisting_variables_fails(self, completed_global_run):
        """节点状态、快照和变量必须一并提交，不能在变量保存失败后留下半重置状态。"""
        svc, _ = completed_global_run
        svc.node_mock("A", mock_outputs={"k1": 20})
        before = svc.build_context_view()
        original_save = DebugContext.save

        def fail_global_vars_save(instance, *args, **kwargs):
            """仅在清理变量的持久化阶段模拟失败。"""
            if "global_vars" in kwargs.get("update_fields", []):
                raise RuntimeError("simulated write failure")
            return original_save(instance, *args, **kwargs)

        with patch.object(DebugContext, "save", fail_global_vars_save):
            with pytest.raises(RuntimeError, match="simulated write failure"):
                svc.node_mock("A", enable=False)
        assert svc.build_context_view() == before
