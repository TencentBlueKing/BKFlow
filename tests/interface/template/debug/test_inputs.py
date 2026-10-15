"""调试输入来自实际执行数据，不使用当前草稿或上次运行参数。"""

import copy

import pytest

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugNodeState
from tests.interface.template.debug import test_config_changed
from tests.interface.template.debug.test_snapshot import save, snapshot_nodes

template = test_config_changed.template


@pytest.mark.django_db
class TestDebugInputs:
    @pytest.mark.parametrize("run_type", ["global", "step"])
    @pytest.mark.parametrize("state", ["FINISHED", "FAILED"])
    def test_sync_captures_execution_inputs(self, template, mocker, run_type, state):
        """成功和失败都保存已渲染输入，之后保存草稿不改变这次输入。"""
        client = test_config_changed.engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "runner")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "runner", mode="real")
        inputs = {"text": "rendered", "query": {"filters": ["before"]}, "credentials": "******"}
        client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"inputs": inputs, "outputs": [], "version": "v-real"},
        }
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": state, "children": {"rtA": {"state": state}}},
        }
        save(template, lambda tree: tree["activities"]["A"]["component"]["data"]["text"].update(value="new draft"))
        node = snapshot_nodes(template)["A"]
        assert node["inputs"] == inputs
        assert node["status"] == state.lower()
        assert DebugNodeState.objects.get(debug_context__template_id=template.id, node_id="A").inputs == inputs
        inputs["query"]["filters"].append("later change")
        assert snapshot_nodes(template)["A"] == node

    @pytest.mark.parametrize("mode", ["real", "mock"])
    def test_step_does_not_reuse_previous_inputs(self, template, mocker, mode):
        """单步启动和不经过引擎的 Mock 不能复用上次运行输入。"""
        svc = DebugService(template.id)
        ctx = svc.sync_node_states()
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(inputs={"previous": "run"})
        client = test_config_changed.engine_client(mocker)
        client.get_task_states.return_value = {"result": False}
        mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
        svc.step_run("A", "runner", mode=mode)
        assert snapshot_nodes(template)["A"]["inputs"] == {}
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").inputs == {}

    @pytest.mark.parametrize(
        "detail",
        [
            {"result": False},
            {"result": True, "data": {}},
            {"result": True, "data": {"inputs": None}},
            {"result": True, "data": {"inputs": []}},
        ],
    )
    def test_missing_inputs_do_not_erase_recorded_inputs(self, template, mocker, detail):
        """接口失败或缺少合法输入对象时不把已读取参数清空。"""
        client = test_config_changed.engine_client(mocker)
        svc = DebugService(template.id)
        svc.global_run({}, "runner")
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "RUNNING", "children": {"rtA": {"state": "FINISHED"}, "rtB": {"state": "RUNNING"}}},
        }
        client.get_task_node_detail.return_value = {"result": True, "data": {"inputs": {"saved": True}}}
        assert snapshot_nodes(template)["A"]["inputs"] == {"saved": True}
        client.get_task_node_detail.return_value = copy.deepcopy(detail)
        assert snapshot_nodes(template)["A"]["inputs"] == {"saved": True}
