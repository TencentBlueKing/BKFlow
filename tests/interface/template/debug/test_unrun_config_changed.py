"""未调试新节点与曾执行后重置的节点使用不同的配置比较依据。"""

import copy

import pytest

from bkflow.template.debug.dependency import compute_debug_config_hashes
from bkflow.template.debug.service import DebugService, DebugStateError
from bkflow.template.debug.snapshot import node_result
from bkflow.template.models import DebugContext, DebugNodeState
from tests.interface.template.debug import test_config_changed

template = test_config_changed.template
engine_client = test_config_changed.engine_client


def assert_node(view, changed, status="not_run"):
    """控制态和存在的结果快照必须同时遵循新节点比较规则。"""
    groups = [view["nodes"]]
    if view["debug_snapshot"]:
        groups.append(view["debug_snapshot"]["nodes"])
    for nodes in groups:
        node = next(node for node in nodes if node["node_id"] == "A")
        assert node["status"] == status
        assert node["config_changed"] is changed


def edit(template):
    """同时修改名称和参数，避免只修复指纹却遗漏名称比较。"""
    tree = test_config_changed.edit_node(template)
    tree["activities"]["A"]["name"] = "renamed"
    template.update_draft_snapshot(tree, "tester")
    return tree


@pytest.mark.django_db
class TestUnrunConfigChanged:
    @pytest.mark.parametrize("legacy", [False, True])
    @pytest.mark.parametrize("run_started", [False, True])
    def test_first_execution_not_reached_does_not_mark(self, template, mocker, legacy, run_started):
        """新节点经多次轮询、保存或全局启动，只要未执行到就不标记失效。"""
        svc = DebugService(template.id)
        ctx = svc.sync_node_states()
        if legacy:
            # 模拟旧版首次读取就写入的指纹及名称，以及已生成的 not_run 快照。
            ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
            ns.debug_config_hash = compute_debug_config_hashes(svc.pipeline_tree)["A"]
            ns.debug_node_name = "A"
            ns.save()
            ctx.debug_snapshot = {"nodes": [node_result(ns, svc.pipeline_tree["activities"]["A"], "tester")]}
            ctx.debug_snapshot["nodes"][0]["_config_hash"] = ns.debug_config_hash
            ctx.save(update_fields=["debug_snapshot"])
        edit(template)
        client = engine_client(mocker)
        if run_started:
            DebugService(template.id).global_run({}, "tester")
            client.get_task_states.return_value = {
                "result": True,
                "data": {
                    "state": "RUNNING",
                    "children": {"rtA": {"state": "READY"}, "rtB": {"state": "RUNNING"}},
                },
            }
        for _ in range(2):
            assert_node(DebugService(template.id).build_context_view(), False)

    @pytest.mark.parametrize("run_type", ["global", "step"])
    @pytest.mark.parametrize("failure", ["create", "start"])
    @pytest.mark.parametrize("legacy", [False, True])
    def test_rejected_first_run_does_not_establish_baseline(self, template, mocker, run_type, failure, legacy):
        """首次调试的创建或启动失败不能使初始配置成为已调试依据。"""
        DebugService(template.id).build_context_view()
        if legacy:
            DebugNodeState.objects.filter(debug_context__template_id=template.id, node_id="A").update(
                debug_config_hash=compute_debug_config_hashes(DebugService(template.id).pipeline_tree)["A"],
                debug_node_name="A",
            )
        edit(template)
        client = engine_client(mocker)
        if failure == "create":
            client.create_task.return_value = {"result": False}
        else:
            client.operate_task.return_value = {"result": False}
        svc = DebugService(template.id)
        with pytest.raises(DebugStateError):
            if run_type == "global":
                svc.global_run({}, "tester")
            else:
                mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
                svc.step_run("A", "tester", mode="real")
        node = test_config_changed.context_nodes(template)["A"]
        assert node["config_changed"] is False

    @pytest.mark.parametrize("legacy", [False, True])
    @pytest.mark.parametrize("reset_all", [False, True])
    @pytest.mark.parametrize("result", ["success", "fail"])
    def test_completed_then_reset_retains_baseline(self, template, legacy, reset_all, result):
        """实际执行成功或失败的节点重置为 not_run 后，仍以实际执行配置比较。"""
        test_config_changed.mock_run(template, result=result)
        if legacy:
            ctx = DebugContext.objects.get(template_id=template.id)
            raw_hash = compute_debug_config_hashes(DebugService(template.id).pipeline_tree)["A"]
            DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(debug_config_hash=raw_hash)
            ctx.debug_snapshot["nodes"][0]["_config_hash"] = raw_hash
            ctx.save(update_fields=["debug_snapshot"])
        DebugService(template.id).reset(None if reset_all else ["A"])
        edit(template)
        assert_node(DebugService(template.id).build_context_view(), True)

    def test_started_then_terminated_retains_baseline(self, template, mocker):
        """已进入真实等待的节点被终止重置后，仍保留已执行基准。"""
        client = engine_client(mocker)
        DebugService(template.id).global_run({}, "tester")
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "RUNNING", "children": {"rtA": {"state": "RUNNING", "schedule_type": "CALLBACK"}}},
        }
        assert_node(DebugService(template.id).build_context_view(), False, "waiting")
        client.node_operate.return_value = {"result": True}
        DebugService(template.id).terminate("A", "tester")
        client.get_task_states.return_value["data"]["children"] = {}
        edit(template)
        assert_node(DebugService(template.id).build_context_view(), True)

    @pytest.mark.parametrize("legacy", [False, True])
    def test_delete_restore_after_reset_keeps_execution_evidence(self, template, legacy):
        """删除重置后的节点再恢复同一 ID，不丢失保存在历史快照中的执行依据。"""
        test_config_changed.mock_run(template)
        if legacy:
            ctx = DebugContext.objects.get(template_id=template.id)
            ctx.debug_snapshot["nodes"][0]["_config_hash"] = compute_debug_config_hashes(
                DebugService(template.id).pipeline_tree
            )["A"]
            ctx.save(update_fields=["debug_snapshot"])
        else:
            DebugService(template.id).reset(["A"])
        tree = copy.deepcopy(DebugService(template.id).pipeline_tree)
        node = tree["activities"].pop("A")
        template.update_draft_snapshot(tree, "tester")
        DebugService(template.id).build_context_view()
        node["name"] = "renamed"
        tree["activities"]["A"] = node
        template.update_draft_snapshot(tree, "tester")
        view = DebugService(template.id).build_context_view()
        assert next(node for node in view["nodes"] if node["node_id"] == "A")["config_changed"] is True
        snapshot = next(node for node in view["debug_snapshot"]["nodes"] if node["node_id"] == "A")
        assert snapshot["config_changed"] is True
        assert snapshot["status"] == ("finished" if legacy else "not_run")

    def test_edit_before_first_execution_compares_only_after_node_starts(self, template, mocker):
        """全局调试尚未到达的新节点继续编辑不失效，开始执行旧配置时才提示差异。"""
        client = engine_client(mocker)
        DebugService(template.id).global_run({}, "tester")
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "RUNNING", "children": {"rtA": {"state": "READY"}}},
        }
        edit(template)
        assert_node(DebugService(template.id).build_context_view(), False)
        client.get_task_states.return_value["data"]["children"]["rtA"] = {
            "state": "RUNNING",
            "schedule_type": "CALLBACK",
        }
        assert_node(DebugService(template.id).build_context_view(), True, "waiting")

    @pytest.mark.parametrize("start_rejected", [False, True])
    def test_legacy_completed_baseline_survives_new_step_start(self, template, mocker, start_rejected):
        """旧版已调试节点重新单步，排队或启动失败不能丢失此前的真实基准。"""
        test_config_changed.mock_run(template)
        DebugNodeState.objects.filter(debug_context__template_id=template.id, node_id="A").update(
            debug_config_hash=compute_debug_config_hashes(DebugService(template.id).pipeline_tree)["A"]
        )
        edit(template)
        client = engine_client(mocker)
        mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
        if start_rejected:
            client.operate_task.return_value = {"result": False}
            with pytest.raises(DebugStateError):
                DebugService(template.id).step_run("A", "tester", mode="real")
        else:
            DebugService(template.id).step_run("A", "tester", mode="real")
            client.get_task_states.return_value = {"result": True, "data": {"state": "RUNNING", "children": {}}}
        view = DebugService(template.id).build_context_view()
        for nodes in (view["nodes"], view["debug_snapshot"]["nodes"]):
            assert next(node for node in nodes if node["node_id"] == "A")["config_changed"] is True

    def test_ambiguous_legacy_reset_defaults_to_false(self, template):
        """旧版重置已抹掉执行依据时，不凭首次读取也会产生的指纹猜测是否调试过。"""
        ctx = DebugService(template.id).sync_node_states()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        ns.debug_config_hash = compute_debug_config_hashes(DebugService(template.id).pipeline_tree)["A"]
        ns.debug_node_name = "A"
        ns.save()
        edit(template)
        assert_node(DebugService(template.id).build_context_view(), False)
        test_config_changed.mock_run(template)
        DebugService(template.id).reset(["A"])
        test_config_changed.edit_node(template, "changed-again")
        assert_node(DebugService(template.id).build_context_view(), True)
