"""调试快照与当前编辑配置分离的回归测试。"""

import copy

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from bkflow.template.debug.service import DebugService, DebugStateError
from bkflow.template.debug.snapshot import ordered_node_ids
from bkflow.template.models import DebugContext, DebugNodeState
from tests.interface.template.debug import test_config_changed

template = test_config_changed.template
engine_client = test_config_changed.engine_client


def save(template, update):
    """经草稿保存入口修改流程，下一次请求重新读取。"""
    tree = copy.deepcopy(DebugService(template.id).pipeline_tree)
    update(tree)
    for constant in tree.get("constants", {}).values():
        constant.setdefault("custom_type", "")
    template.update_draft_snapshot(tree, "editor")


def view(template):
    """读取当前状态和独立快照。"""
    return DebugService(template.id).build_context_view()


def step(template, node_id="A", **kwargs):
    """执行一次同步 Mock 调试。"""
    return DebugService(template.id).step_run(node_id, "runner", mode="mock", **kwargs)


def snapshot_nodes(template):
    """按 ID 索引历史快照节点。"""
    return {node["node_id"]: node for node in view(template)["debug_snapshot"]["nodes"]}


@pytest.mark.django_db
class TestDebugSnapshot:
    def test_edits_do_not_rewrite_snapshot(self, template):
        """名称、配置、Mock 预设和画布增删不改变已保存的结果。"""
        step(template, mock_outputs={"answer": 42})
        before = snapshot_nodes(template)["A"]
        assert before["node_name"] == "A"
        assert before["execution_mode"] == "mock"
        assert before["operator"] == "runner"
        assert not any(key.startswith("_") for key in before)
        save(template, lambda tree: tree["activities"]["A"].update(name="renamed"))
        after = snapshot_nodes(template)["A"]
        assert after == {**before, "config_changed": True}
        current = {node["node_id"]: node for node in view(template)["nodes"]}
        assert current["A"]["node_name"] == "renamed"
        assert current["A"]["config_changed"] is True
        DebugService(template.id).node_mock("A", mock_outputs={"answer": 99})
        assert snapshot_nodes(template)["A"] == after
        save(template, lambda tree: tree["activities"].pop("A"))
        data = view(template)
        assert [node["node_id"] for node in data["nodes"]] == ["B"]
        assert snapshot_nodes(template)["A"] == {**after, "node_deleted": True}
        assert not DebugNodeState.objects.filter(debug_context__template_id=template.id, node_id="A").exists()

    def test_restore_name_and_layout_do_not_mark(self, template):
        """名称恢复后解除标记；布局编辑不影响快照。"""
        step(template)
        before = snapshot_nodes(template)["A"]
        save(template, lambda tree: tree["activities"]["A"].update(name="new name"))
        assert snapshot_nodes(template)["A"]["config_changed"] is True
        save(template, lambda tree: tree["activities"]["A"].update(name="A", x=123, y=456))
        assert snapshot_nodes(template)["A"] == before

    def test_step_changes_only_target(self, template):
        """重新单步后更新目标名称和结果，其余节点历史保持原样。"""
        step(template, "B", mock_outputs={"old": True})
        before = snapshot_nodes(template)["B"]
        step(template)
        save(template, lambda tree: tree["activities"]["A"].update(name="new name"))
        step(template, mock_result="fail", mock_error="expected failure")
        nodes = snapshot_nodes(template)
        assert nodes["B"] == before
        assert nodes["A"]["node_name"] == "new name"
        assert nodes["A"]["status"] == "failed"
        assert nodes["A"]["config_changed"] is False

    @pytest.mark.parametrize("run_type", ["global", "step"])
    @pytest.mark.parametrize("state", ["FINISHED", "FAILED"])
    def test_runtime_deleted_node_still_writes_frozen_result(self, template, mocker, run_type, state):
        """运行期间删除节点，结果仍写入旧名称快照；新节点只出现在当前控制列表。"""
        client = engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "runner")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "runner", mode="real")
        old_tree = copy.deepcopy(svc.pipeline_tree)
        save(template, lambda tree: tree["activities"].pop("A"))
        save(template, lambda tree: tree["activities"].update(C={**old_tree["activities"]["A"], "id": "C"}))
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": state, "children": {"rtA": {"state": state, "elapsed_time": 2}}},
        }
        nodes = snapshot_nodes(template)
        assert nodes["A"]["node_name"] == "A"
        assert nodes["A"]["node_deleted"] is True
        assert nodes["A"]["status"] == state.lower()
        assert nodes["A"]["duration_ms"] == 2000
        assert nodes["A"]["log_ref"]["node_id"] == "rtA"
        assert "C" not in nodes
        # 下一次查询清理当前态，快照结果仍存在。
        assert snapshot_nodes(template) == nodes
        assert not DebugNodeState.objects.filter(debug_context__template_id=template.id, node_id="A").exists()

    @pytest.mark.parametrize("run_type", ["global", "step"])
    def test_runtime_rename_uses_launch_name(self, template, mocker, run_type):
        """旧运行完成不能把调试期间保存的新名称视为已经调试。"""
        client = engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "runner")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "runner", mode="real")
        save(template, lambda tree: tree["activities"]["A"].update(name="new"))
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED"}}},
        }
        node = snapshot_nodes(template)["A"]
        assert node["node_name"] == "A"
        assert node["config_changed"] is True
        assert DebugNodeState.objects.get(debug_context__template_id=template.id, node_id="A").debug_node_name == "A"

    @pytest.mark.parametrize("failure", ["create", "start"])
    def test_rejected_global_keeps_previous_snapshot(self, template, mocker, failure):
        """创建或启动失败不覆盖上次可查看的结果快照。"""
        step(template)
        before = snapshot_nodes(template)
        client = engine_client(mocker)
        getattr(client, "create_task" if failure == "create" else "operate_task").return_value = {"result": False}
        with pytest.raises(DebugStateError):
            DebugService(template.id).global_run({}, "runner")
        assert snapshot_nodes(template) == before

    def test_next_global_replaces_snapshot(self, template, mocker):
        """新的全局调试采用当前节点集合，移除上轮已经删除的节点。"""
        step(template)
        save(template, lambda tree: tree["activities"].pop("A"))
        client = engine_client(mocker)
        DebugService(template.id).global_run({}, "runner")
        client.get_task_states.return_value = {"result": False}
        assert list(snapshot_nodes(template)) == ["B"]

    def test_explicit_reset_clears_results(self, template):
        """显式重置可以清除快照；单节点重置只影响目标。"""
        step(template)
        step(template, "B")
        DebugService(template.id).reset(["A"])
        nodes = snapshot_nodes(template)
        assert nodes["A"]["status"] == "not_run"
        assert nodes["A"]["outputs"] == {}
        assert nodes["B"]["status"] == "finished"
        DebugService(template.id).reset()
        assert view(template)["debug_snapshot"] is None

    def test_legacy_snapshot_and_name_are_not_fabricated(self, template):
        """前一版模型仍可写入；新代码不推断旧名称、不回填历史快照。"""
        apps = MigrationLoader(connection).project_state([("template", "0014_debug_config_fingerprints")]).apps
        ctx = apps.get_model("template", "DebugContext").objects.create(template_id=template.id, space_id=1)
        apps.get_model("template", "DebugNodeState").objects.create(debug_context_id=ctx.pk, node_id="A")
        save(template, lambda tree: tree["activities"]["A"].update(name="new"))
        data = view(template)
        assert data["debug_snapshot"] is None
        assert data["nodes"][0]["config_changed"] is False
        assert DebugNodeState.objects.get(debug_context_id=ctx.pk, node_id="A").debug_node_name is None
        step(template)
        assert snapshot_nodes(template)["A"]["node_name"] == "new"
        assert DebugContext.objects.get(pk=ctx.pk).active_debug_snapshot == {}


def graph_tree(edges):
    """构造与 JSON 键顺序无关的控制流。"""
    node_ids = {node for edge in edges for node in edge} - {"start", "end"}
    return {
        "activities": {node: {"name": node} for node in sorted(node_ids, reverse=True)},
        "flows": {str(i): {"source": source, "target": target} for i, (source, target) in enumerate(edges)},
        "start_event": {"id": "start"},
    }


def test_order_handles_parallel_merge_and_loop():
    """串行、并行汇聚和回边同时存在时，每个节点只展示一次且汇聚位于分支之后。"""
    tree = graph_tree(
        [
            ("start", "Z"),
            ("Z", "B"),
            ("Z", "C"),
            ("B", "D"),
            ("D", "A"),
            ("C", "A"),
            ("A", "Z"),
            ("A", "end"),
        ]
    )
    assert ordered_node_ids(tree) == ["Z", "B", "D", "C", "A"]
    tree["flows"] = dict(reversed(list(tree["flows"].items())))
    assert ordered_node_ids(tree) == ["Z", "B", "D", "C", "A"]


@pytest.mark.django_db
def test_step_inserts_new_node_without_reordering_history(template):
    """单步新节点按逻辑位置插入；保存连线变化不重排已有快照。"""
    save(template, lambda tree: tree.update(flows={"f": {"source": "B", "target": "A"}}, start_event={"id": "B"}))
    step(template, "A")
    step(template, "B")
    assert [node["node_id"] for node in view(template)["debug_snapshot"]["nodes"]] == ["B", "A"]
    save(template, lambda tree: tree.update(flows={"f": {"source": "A", "target": "B"}}, start_event={"id": "A"}))
    assert [node["node_id"] for node in view(template)["debug_snapshot"]["nodes"]] == ["B", "A"]


@pytest.mark.django_db
@pytest.mark.parametrize("run_type", ["global", "step"])
def test_delete_while_engine_creates_task_preserves_active_node(template, mocker, run_type):
    """引擎创建尚未返回时，另一请求删除草稿并查询上下文也不能删除运行节点。"""
    client = engine_client(mocker)
    client.get_task_states.return_value = {"result": False}

    def creating(data):
        save(template, lambda tree: tree["activities"].pop("A"))
        assert all(node["node_id"] != "A" for node in view(template)["nodes"])
        assert DebugNodeState.objects.filter(debug_context__template_id=template.id, node_id="A").exists()
        return {"result": True, "data": {"id": 123}}

    client.create_task.side_effect = creating
    if run_type == "global":
        DebugService(template.id).global_run({}, "runner")
    else:
        mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
        DebugService(template.id).step_run("A", "runner", mode="real")
    assert snapshot_nodes(template)["A"]["node_deleted"] is True


@pytest.mark.django_db
def test_real_step_override_keeps_runtime_mode_in_snapshot(template, mocker):
    """单步覆盖 Mock 配置时，快照记录真实执行模式，当前配置仍保留。"""
    DebugService(template.id).node_mock("A", enable=True)
    client = engine_client(mocker)
    mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
    DebugService(template.id).step_run("A", "runner", mode="real")
    client.get_task_states.return_value = {
        "result": True,
        "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED"}}},
    }
    assert snapshot_nodes(template)["A"]["execution_mode"] == "real"
    assert next(node for node in view(template)["nodes"] if node["node_id"] == "A")["execution_mode"] == "mock"


@pytest.mark.django_db
def test_gateway_snapshot_uses_original_conditions(template, mocker):
    """真实运行期间修改网关条件，完成回写仍使用运行前条件。"""
    from tests.interface.template.debug.test_gateway import _gateway_tree

    tree = _gateway_tree()
    for constant in tree["constants"].values():
        constant["custom_type"] = ""
    tree["gateways"]["gateway"]["name"] = "old gateway"
    template.update_draft_snapshot(tree, "editor")
    client = engine_client(mocker)
    client.get_node_id_map.return_value = {"result": True, "data": {"gateway": "rtG"}}
    DebugService(template.id).global_run({"${count}": 1}, "runner")
    save(
        template, lambda current: current["gateways"]["gateway"]["conditions"]["flow_positive"].update(evaluate="False")
    )
    client.get_task_states.return_value = {
        "result": True,
        "data": {"state": "FINISHED", "children": {"rtG": {"state": "FINISHED"}}},
    }
    node = snapshot_nodes(template)["gateway"]
    assert node["configured_inputs"] == {}
    assert node["outputs"]["selected_flow_ids"] == ["flow_positive"]
    assert node["config_changed"] is True


@pytest.mark.django_db
def test_output_mapping_uses_launch_tree(template, mocker):
    """调试期间重新绑定输出变量，旧运行只写入原来的变量名。"""
    from tests.interface.template.debug.test_gateway import _constant

    save(
        template,
        lambda tree: tree["constants"].update(
            {"${old}": _constant("${old}", "", "component_outputs", {"A": ["answer"]})}
        ),
    )
    client = engine_client(mocker)
    DebugService(template.id).global_run({}, "runner")
    save(
        template,
        lambda tree: tree.update(constants={"${new}": _constant("${new}", "", "component_outputs", {"A": ["answer"]})}),
    )
    client.get_task_states.return_value = {
        "result": True,
        "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED"}}},
    }
    client.get_task_node_detail.return_value = {"result": True, "data": {"outputs": [{"key": "answer", "value": 42}]}}
    data = view(template)
    assert data["global_vars"] == {"${old}": 42}


@pytest.mark.django_db
def test_gateway_step_records_named_snapshot(template):
    """同步网关单步也建立名称和求值结果快照。"""
    from tests.interface.template.debug.test_gateway import _gateway_tree

    tree = _gateway_tree()
    for constant in tree["constants"].values():
        constant["custom_type"] = ""
    tree["gateways"]["gateway"]["name"] = "choose branch"
    template.update_draft_snapshot(tree, "editor")
    DebugService(template.id).step_run("gateway", "runner", input_overrides={"${count}": 1})
    node = snapshot_nodes(template)["gateway"]
    assert node["node_name"] == "choose branch"
    assert node["outputs"]["selected_flow_ids"] == ["flow_positive"]
    assert node["execution_mode"] == "real"
    assert node["config_changed"] is False


@pytest.mark.django_db
def test_terminate_preserves_completed_snapshot_results(template, mocker):
    """全局终止保留已完成节点快照，只重置仍活跃的节点。"""
    client = engine_client(mocker)
    DebugService(template.id).global_run({}, "runner")
    client.get_task_states.return_value = {
        "result": True,
        "data": {"state": "RUNNING", "children": {"rtA": {"state": "FINISHED"}, "rtB": {"state": "RUNNING"}}},
    }
    assert snapshot_nodes(template)["B"]["status"] == "running"
    DebugService(template.id).terminate(operator="runner")
    client.get_task_states.return_value["data"]["state"] = "REVOKED"
    client.get_task_states.return_value["data"]["children"]["rtB"]["state"] = "REVOKED"
    nodes = snapshot_nodes(template)
    assert nodes["A"]["status"] == "finished"
    assert nodes["A"]["log_ref"]["instance_id"] == 123
    assert nodes["B"]["status"] == "not_run"
    assert nodes["B"]["log_ref"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("failure", ["dependency", "create", "start"])
def test_rejected_step_keeps_previous_snapshot(template, mocker, failure):
    """单步请求未实际执行时不能覆盖旧快照及名称基准。"""
    step(template)
    save(template, lambda tree: tree["activities"]["A"].update(name="renamed"))
    before = snapshot_nodes(template)
    client = engine_client(mocker)
    mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
    if failure == "dependency":
        mocker.patch.object(DebugService, "compute_can_step", return_value=(False, ["${missing}"]))
    else:
        getattr(client, "create_task" if failure == "create" else "operate_task").return_value = {"result": False}
    with pytest.raises(DebugStateError):
        DebugService(template.id).step_run("A", "runner", mode="real")
    assert snapshot_nodes(template) == before
