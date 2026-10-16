"""外部流程结构变化不改写历史结果，也不作为节点配置变化。"""

import copy

import pytest

from bkflow.template.debug.dependency import compute_debug_config_hashes
from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, DebugNodeState
from tests.interface.template.debug import test_config_changed
from tests.interface.template.debug.test_snapshot import (
    save,
    snapshot_nodes,
    step,
    view,
)

template = test_config_changed.template


def connect(tree, order):
    """为节点重建串行连线，同时更新节点的 incoming/outgoing。"""
    edges = list(zip(["start", *order], [*order, "end"]))
    tree["flows"] = {f"{source}-{target}": {"source": source, "target": target} for source, target in edges}
    tree["start_event"] = {"id": "start", "outgoing": f"start-{order[0]}"}
    tree["end_event"] = {"id": "end", "incoming": f"{order[-1]}-end"}
    for previous, node_id, following in zip(["start", *order], order, [*order[1:], "end"]):
        tree["activities"][node_id].update(incoming=f"{previous}-{node_id}", outgoing=f"{node_id}-{following}")


def debug_connected_nodes(template):
    """建立可比较的历史结果，包含配置输入、输出和执行时间。"""
    save(template, lambda tree: connect(tree, ["A", "B"]))
    step(template, "A", mock_outputs={"result": "A"})
    step(template, "B", mock_outputs={"result": "B"})
    return snapshot_nodes(template)


@pytest.mark.django_db
class TestStructureChanges:
    def test_insert_node_preserves_existing_results_and_flags(self, template):
        """在已调试节点之后插入节点，不改变原节点状态、参数、日志及标记。"""
        before = debug_connected_nodes(template)

        def insert(tree):
            tree["activities"]["C"] = {**copy.deepcopy(tree["activities"]["A"]), "id": "C", "name": "C"}
            connect(tree, ["A", "C", "B"])

        save(template, insert)
        assert snapshot_nodes(template) == before
        current = {node["node_id"]: node for node in view(template)["nodes"]}
        assert current["C"]["status"] == "not_run"
        assert all(not node["config_changed"] for node in current.values())
        assert current["A"]["status"] == current["B"]["status"] == "finished"

    def test_rewire_preserves_results_but_parameter_edit_still_marks(self, template):
        """交换前后关系不标记，修改实际参数仍标记且不覆盖旧结果。"""
        before = debug_connected_nodes(template)
        save(template, lambda tree: connect(tree, ["B", "A"]))
        assert snapshot_nodes(template) == before
        save(template, lambda tree: tree["activities"]["A"]["component"]["data"]["text"].update(value="changed"))
        assert snapshot_nodes(template) == {**before, "A": {**before["A"], "config_changed": True}}

    def test_remove_other_node_keeps_survivor_and_deleted_history(self, template):
        """删除下游只标记已删除历史节点，保留幸存节点全部结果和原列表。"""
        before = debug_connected_nodes(template)

        def remove(tree):
            tree["activities"].pop("B")
            connect(tree, ["A"])

        save(template, remove)
        assert snapshot_nodes(template) == {
            "A": before["A"],
            "B": {**before["B"], "config_changed": True, "node_deleted": True},
        }

    @pytest.mark.parametrize("run_type", ["global", "step"])
    @pytest.mark.parametrize("status", ["FINISHED", "FAILED"])
    def test_rewire_while_running_does_not_invalidate_completion(self, template, mocker, run_type, status):
        """运行期间改连线，按旧任务回写的结果不被误判为参数变化。"""
        save(template, lambda tree: connect(tree, ["A", "B"]))
        client = test_config_changed.engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "runner")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "runner", mode="real")
        save(template, lambda tree: connect(tree, ["B", "A"]))
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": status, "children": {"rtA": {"state": status}}},
        }
        client.get_task_node_detail.return_value = {"result": True, "data": {"inputs": {"text": "executed"}}}
        node = snapshot_nodes(template)["A"]
        assert node["status"] == status.lower()
        assert node["config_changed"] is False
        assert node["configured_inputs"] == {"text": "before"}
        assert node["inputs"] == {"text": "executed"}

    @pytest.mark.parametrize("baseline", ["", None, "a" * 32, "v3:" + "b" * 32])
    def test_unknown_hash_version_waits_for_new_debug_baseline(self, template, baseline):
        """旧版或未知版本指纹不与新版直接比较，也不能用当前草稿覆盖历史基准。"""
        debug_connected_nodes(template)
        ctx = DebugContext.objects.get(template_id=template.id)
        for node in ctx.debug_snapshot["nodes"]:
            node["_config_hash"] = baseline
        ctx.save(update_fields=["debug_snapshot"])
        DebugNodeState.objects.filter(debug_context=ctx).update(debug_config_hash=baseline)
        stored = copy.deepcopy(ctx.debug_snapshot)
        save(template, lambda tree: tree["activities"]["A"]["component"]["data"]["text"].update(value="new draft"))
        assert all(not node["config_changed"] for node in snapshot_nodes(template).values())
        assert all(not node["config_changed"] for node in view(template)["nodes"])
        ctx.refresh_from_db()
        assert ctx.debug_snapshot == stored
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").debug_config_hash == baseline
        step(template, "A")
        save(template, lambda tree: tree["activities"]["A"]["component"]["data"]["text"].update(value="changed again"))
        assert snapshot_nodes(template)["A"]["config_changed"] is True
        assert snapshot_nodes(template)["B"]["config_changed"] is False

    def test_legacy_hash_still_detects_known_name_change(self, template):
        """忽略旧指纹不影响已有名称比较依据。"""
        step(template)
        ctx = DebugContext.objects.get(template_id=template.id)
        ctx.debug_snapshot["nodes"][0]["_config_hash"] = "a" * 32
        ctx.save(update_fields=["debug_snapshot"])
        DebugNodeState.objects.filter(debug_context=ctx).update(debug_config_hash="a" * 32)
        save(template, lambda tree: tree["activities"]["A"].update(name="renamed"))
        assert snapshot_nodes(template)["A"]["config_changed"] is True
        assert next(node for node in view(template)["nodes"] if node["node_id"] == "A")["config_changed"] is True

    @pytest.mark.parametrize("run_type", ["global", "step"])
    def test_old_worker_fingerprint_is_not_upgraded_from_new_draft(self, template, mocker, run_type):
        """旧实例发起的任务在新实例完成，仍保留旧指纹而非用新草稿补造新版基准。"""
        client = test_config_changed.engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "runner")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "runner", mode="real")
        old_hash = "a" * 32
        DebugContext.objects.filter(template_id=template.id).update(active_config_hashes={"A": old_hash})
        save(template, lambda tree: tree["activities"]["A"]["component"]["data"]["text"].update(value="new draft"))
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED"}}},
        }
        node = snapshot_nodes(template)["A"]
        assert node["status"] == "finished"
        assert node["config_changed"] is False
        assert node["configured_inputs"] == {"text": "before"}
        assert (
            DebugNodeState.objects.get(debug_context__template_id=template.id, node_id="A").debug_config_hash
            == old_hash
        )


@pytest.mark.parametrize(
    "node_type",
    ["ServiceActivity", "ParallelGateway", "ConvergeGateway", "ExclusiveGateway", "ConditionalParallelGateway"],
)
def test_external_connections_do_not_change_versioned_hash(node_type):
    """节点连线字段、数组顺序或表示形式变化不改变配置指纹。"""
    key = "activities" if node_type == "ServiceActivity" else "gateways"
    node = {"type": node_type, "incoming": "in", "outgoing": ["out1", "out2"]}
    tree = {key: {"A": node}}
    before = compute_debug_config_hashes(tree)
    node.update(incoming=["new-in"], outgoing=["out2", "out1"])
    assert compute_debug_config_hashes(tree) == before
    assert before["A"].startswith("v2:")
    assert len(before["A"]) <= DebugNodeState._meta.get_field("debug_config_hash").max_length


@pytest.mark.parametrize("node_type", ["SubCanvas", "SubProcess"])
def test_nested_structure_is_still_container_configuration(node_type):
    """容器外部连线忽略，内部执行结构变化仍视为容器自身配置变化。"""
    node = {
        "type": node_type,
        "incoming": "in",
        "outgoing": "out",
        "pipeline": {
            "activities": {"A": {"type": "ServiceActivity"}, "B": {"type": "ServiceActivity"}},
            "flows": {"f": {"source": "A", "target": "B"}},
        },
    }
    tree = {"activities": {"S": node}}
    before = compute_debug_config_hashes(tree)
    node.update(incoming="new-in", outgoing="new-out")
    assert compute_debug_config_hashes(tree) == before
    node["pipeline"]["flows"]["f"]["target"] = "A"
    assert compute_debug_config_hashes(tree) != before
