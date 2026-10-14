"""保存配置与最近一次实际调试配置的独立状态。"""

import copy

import pytest
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader

from bkflow.template.debug.dependency import compute_debug_config_hashes
from bkflow.template.debug.service import DebugService, DebugStateError
from bkflow.template.models import (
    DebugContext,
    DebugNodeState,
    Template,
    TemplateSnapshot,
)


@pytest.fixture
def template(mocker):
    """使用真实草稿保存路径，所有执行请求由测试替身处理。"""
    mocker.patch("bkflow.statistics.tasks.template_post_save_statistics_task.delay")
    tree = {
        "activities": {
            node_id: {
                "id": node_id,
                "name": node_id,
                "type": "ServiceActivity",
                "component": {"code": "t", "version": "1", "data": {"text": {"value": "before"}}},
            }
            for node_id in ("A", "B")
        },
        "gateways": {},
        "flows": {},
        "constants": {},
        "outputs": [],
    }
    snapshot = TemplateSnapshot.create_snapshot(tree, "tester", "1.0.0")
    template = Template.objects.create(name="debug", space_id=1, snapshot_id=snapshot.id)
    snapshot.template_id = template.id
    snapshot.save()
    template.update_draft_snapshot(tree, "tester")
    return template


def context_nodes(template):
    """每次请求重新读取已保存的流程。"""
    return {node["node_id"]: node for node in DebugService(template.id).build_context_view()["nodes"]}


def edit_node(template, value="after"):
    """修改并保存 A，B 保持原配置。"""
    tree = copy.deepcopy(DebugService(template.id).pipeline_tree)
    tree["activities"]["A"]["component"]["data"]["text"]["value"] = value
    template.update_draft_snapshot(tree, "tester")
    return tree


def mock_run(template, node_id="A", result="success"):
    """用当前已保存配置完成一次单步 Mock。"""
    return DebugService(template.id).step_run(node_id, "tester", mode="mock", mock_result=result)


def engine_client(mocker):
    """引擎替身只返回确定的本地测试数据。"""
    client = mocker.MagicMock()
    client.create_task.return_value = {"result": True, "data": {"id": 123}}
    client.operate_task.return_value = {"result": True}
    client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA", "B": "rtB"}}
    client.get_task_node_detail.return_value = {"result": True, "data": {"outputs": []}}
    mocker.patch.object(DebugService, "_task_client", return_value=client)
    return client


@pytest.mark.django_db
class TestConfigChanged:
    def test_save_marks_only_changed_node_and_preserves_results(self, template):
        """重复保存不能消除变化，也不能重置调试结果。"""
        mock_run(template)
        DebugNodeState.objects.filter(debug_context__template_id=template.id, node_id="A").update(
            inputs={"original": "input"}, outputs={"original": "output"}, log_ref={"instance_id": 99}
        )
        before = context_nodes(template)["A"]
        tree = edit_node(template)
        template.update_draft_snapshot(tree, "tester")
        nodes = context_nodes(template)
        assert nodes["A"]["config_changed"] is True
        assert nodes["B"]["config_changed"] is False
        for key in ("status", "duration_ms", "error_detail", "log_ref"):
            assert nodes["A"][key] == before[key]
        state = DebugNodeState.objects.get(debug_context__template_id=template.id, node_id="A")
        assert state.inputs == {"original": "input"}
        assert state.outputs == {"original": "output"}

    def test_noop_layout_and_rolled_back_save_do_not_mark(self, template):
        """展示信息变化与保存回滚均不能制造配置变化。"""
        mock_run(template)
        tree = copy.deepcopy(DebugService(template.id).pipeline_tree)
        tree["location"] = [{"id": "A", "x": 200, "y": 100}]
        template.update_draft_snapshot(tree, "tester")
        assert context_nodes(template)["A"]["config_changed"] is False
        with transaction.atomic():
            edit_node(template)
            transaction.set_rollback(True)
        assert context_nodes(template)["A"]["config_changed"] is False

    @pytest.mark.parametrize("result", ["success", "fail"])
    def test_step_run_clears_only_the_executed_node(self, template, result):
        """成功和执行失败都算调试过，不清除其他节点的标记。"""
        mock_run(template)
        mock_run(template, "B")
        tree = edit_node(template)
        tree["activities"]["B"]["component"]["version"] = "2"
        template.update_draft_snapshot(tree, "tester")
        mock_run(template, result=result)
        nodes = context_nodes(template)
        assert nodes["A"]["config_changed"] is False
        assert nodes["A"]["status"] == ("finished" if result == "success" else "failed")
        assert nodes["B"]["config_changed"] is True

    def test_restoring_debugged_configuration_matches_again(self, template):
        """恢复到实际调试过的配置后，结果重新与配置一致。"""
        mock_run(template)
        edit_node(template)
        assert context_nodes(template)["A"]["config_changed"] is True
        edit_node(template, "before")
        assert context_nodes(template)["A"]["config_changed"] is False

    @pytest.mark.parametrize("run_type", ["global", "step"])
    @pytest.mark.parametrize("state", ["FINISHED", "FAILED"])
    def test_old_run_completion_cannot_clear_new_save(self, template, mocker, run_type, state):
        """调试 A 配置期间保存 B，旧任务结束后 B 仍需重新调试。"""
        mock_run(template)
        client = engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "tester")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "tester", mode="real")
        edit_node(template)
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": state, "children": {"rtA": {"state": state}}},
        }
        assert context_nodes(template)["A"]["config_changed"] is True
        assert context_nodes(template)["A"]["config_changed"] is True

    def test_global_run_clears_completed_but_not_unreached_nodes(self, template, mocker):
        """发起全局调试不代表所有节点都已按新配置执行。"""
        mock_run(template)
        mock_run(template, "B")
        tree = edit_node(template)
        tree["activities"]["B"]["component"]["version"] = "2"
        template.update_draft_snapshot(tree, "tester")
        client = engine_client(mocker)
        DebugService(template.id).global_run({}, "tester")
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FAILED", "children": {"rtA": {"state": "FAILED"}, "rtB": {"state": "READY"}}},
        }
        nodes = context_nodes(template)
        assert nodes["A"]["config_changed"] is False
        assert nodes["B"]["config_changed"] is True

    @pytest.mark.parametrize("run_type", ["global", "step"])
    @pytest.mark.parametrize("state", ["FINISHED", "FAILED"])
    def test_current_real_run_clears_marker_on_completion(self, template, mocker, run_type, state):
        """真实执行按最新配置成功或失败后均消除配置不一致。"""
        mock_run(template)
        edit_node(template)
        client = engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "tester")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "tester", mode="real")
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": state, "children": {"rtA": {"state": state}}},
        }
        assert context_nodes(template)["A"]["config_changed"] is False

    @pytest.mark.parametrize("failure", ["create", "start", "dependency"])
    def test_rejected_step_does_not_clear_marker(self, template, mocker, failure):
        """创建、启动或依赖检查失败均不能把配置记为已调试。"""
        mock_run(template)
        edit_node(template)
        client = engine_client(mocker)
        mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
        if failure == "create":
            client.create_task.return_value = {"result": False}
        elif failure == "start":
            client.operate_task.return_value = {"result": False}
        else:
            mocker.patch.object(DebugService, "compute_can_step", return_value=(False, ["${missing}"]))
        with pytest.raises(DebugStateError):
            DebugService(template.id).step_run("A", "tester", mode="real")
        assert context_nodes(template)["A"]["config_changed"] is True

    @pytest.mark.parametrize("status", ["finished", "failed", "not_run"])
    @pytest.mark.parametrize("baseline", ["", None])
    def test_legacy_result_without_baseline_defaults_to_false(self, template, status, baseline):
        """空基准的存量节点默认不标记，重新调试后才开始比较后续配置变化。"""
        ctx = DebugService(template.id).get_or_create_context()
        DebugNodeState.objects.create(debug_context=ctx, node_id="A", status=status, debug_config_hash=baseline)
        node = context_nodes(template)["A"]
        assert node["config_changed"] is False
        assert node["status"] == status
        edit_node(template)
        assert context_nodes(template)["A"]["config_changed"] is False
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").debug_config_hash == baseline
        mock_run(template)
        assert context_nodes(template)["A"]["config_changed"] is False
        edit_node(template, "after-second-debug")
        assert context_nodes(template)["A"]["config_changed"] is True

    def test_global_failure_does_not_reset_unknown_legacy_baseline(self, template, mocker):
        """全局调试未执行到的存量节点仍缺少基准，继续默认不标记。"""
        ctx = DebugService(template.id).get_or_create_context()
        DebugNodeState.objects.create(debug_context=ctx, node_id="B", status="finished")
        client = engine_client(mocker)
        DebugService(template.id).global_run({}, "tester")
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FAILED", "children": {"rtA": {"state": "FAILED"}, "rtB": {"state": "READY"}}},
        }
        assert context_nodes(template)["B"]["config_changed"] is False

    def test_new_node_is_not_run_without_stale_result(self, template):
        """新节点用 not_run 表示未调试，不伪造历史结果。"""
        node = context_nodes(template)["A"]
        assert node["status"] == "not_run"
        assert node["config_changed"] is False

    def test_non_versioned_snapshot_save_is_also_compared(self, template):
        """未开启版本管理时，直接保存的正式快照也参与比较。"""
        mock_run(template)
        tree = copy.deepcopy(DebugService(template.id).pipeline_tree)
        TemplateSnapshot.objects.filter(template_id=template.id, draft=True).update(is_deleted=True)
        tree["activities"]["A"]["component"]["version"] = "2"
        snapshot = TemplateSnapshot.create_snapshot(tree, "tester", "1.0.1")
        template.snapshot_id = snapshot.id
        template.save(update_fields=["snapshot_id"])
        assert context_nodes(template)["A"]["config_changed"] is True

    def test_mock_configuration_alone_does_not_clear_marker(self, template):
        """编辑 Mock 预设不代表已经重新调试。"""
        mock_run(template)
        edit_node(template)
        DebugService(template.id).node_mock("A", enable=True, mock_outputs={"answer": 42})
        assert context_nodes(template)["A"]["config_changed"] is True

    @pytest.mark.parametrize("expression, status", [("1 == 1", "finished"), ("broken(", "failed")])
    def test_gateway_step_updates_its_own_baseline(self, template, expression, status):
        """网关条件改变后，实际求值成功或失败均建立新基准。"""
        tree = copy.deepcopy(DebugService(template.id).pipeline_tree)
        tree["gateways"]["G"] = {
            "id": "G",
            "type": "ExclusiveGateway",
            "conditions": {"f1": {"name": "condition", "evaluate": "1 == 1"}},
            "extra_info": {"parse_lang": "boolrule"},
        }
        template.update_draft_snapshot(tree, "tester")
        DebugService(template.id).step_run("G", "tester")
        tree["gateways"]["G"]["conditions"]["f1"]["evaluate"] = "2 == 2"
        template.update_draft_snapshot(tree, "tester")
        assert context_nodes(template)["G"]["config_changed"] is True
        tree["gateways"]["G"]["conditions"]["f1"]["evaluate"] = expression
        template.update_draft_snapshot(tree, "tester")
        DebugService(template.id).step_run("G", "tester")
        node = context_nodes(template)["G"]
        assert node["config_changed"] is False
        assert node["status"] == status


@pytest.fixture
def legacy_debug_models(db):
    """加载新增指纹字段之前的模型，在当前迁移后的表结构上模拟旧实例。"""
    apps = MigrationLoader(connection).project_state([("template", "0013_debug_node_revoked_status")]).apps
    return apps.get_model("template", "DebugContext"), apps.get_model("template", "DebugNodeState")


@pytest.mark.django_db
class TestRollingMigrationCompatibility:
    def test_old_instance_can_create_context(self, template, legacy_debug_models):
        """迁移后旧实例仍可首次创建上下文，不需要填写新增字段。"""
        old_context, _ = legacy_debug_models
        ctx, created = old_context.objects.get_or_create(
            template_id=template.id, defaults={"space_id": template.space_id}
        )
        assert created is True
        assert not DebugContext.objects.get(pk=ctx.pk).active_config_hashes
        assert context_nodes(template)["A"]["status"] == "not_run"

    def test_old_instance_can_bulk_create_nodes(self, template, legacy_debug_models):
        """旧实例批量创建节点后，新实例可读取并在重新调试后建立基准。"""
        _, old_node = legacy_debug_models
        ctx = DebugService(template.id).get_or_create_context()
        old_node.objects.bulk_create(
            [old_node(debug_context_id=ctx.pk, node_id=node_id) for node_id in ("A", "B")],
            ignore_conflicts=True,
        )
        # 忽略冲突不能悄悄丢弃因新增列不兼容而插入失败的节点。
        states = list(DebugNodeState.objects.filter(debug_context=ctx))
        assert len(states) == 2
        assert all(not state.debug_config_hash for state in states)
        assert all(node["config_changed"] is False for node in context_nodes(template).values())
        mock_run(template)
        assert context_nodes(template)["A"]["config_changed"] is False
        assert context_nodes(template)["B"]["config_changed"] is False

    @pytest.mark.parametrize("state, status", [("FINISHED", "finished"), ("FAILED", "failed")])
    def test_run_without_fingerprints_can_finish(self, template, mocker, state, status):
        """缺少运行指纹的旧任务完成时不报错，也不凭当前配置补写基准。"""
        ctx = DebugService(template.id).sync_node_states()
        DebugContext.objects.filter(pk=ctx.pk).update(
            status="running", active_task_id=123, active_run_type="global", active_config_hashes=None
        )
        DebugNodeState.objects.filter(debug_context=ctx).update(debug_config_hash=None)
        client = engine_client(mocker)
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": state, "children": {"rtA": {"state": state}}},
        }
        node = context_nodes(template)["A"]
        assert node["status"] == status
        assert node["config_changed"] is False
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").debug_config_hash is None

    @pytest.mark.parametrize("run_type", ["global", "step"])
    def test_new_real_run_establishes_baseline_from_null(self, template, mocker, run_type):
        """空指纹上下文完成真实调试后，正常识别后续配置变化。"""
        ctx = DebugService(template.id).sync_node_states()
        DebugContext.objects.filter(pk=ctx.pk).update(active_config_hashes=None)
        DebugNodeState.objects.filter(debug_context=ctx).update(debug_config_hash=None)
        assert all(node["config_changed"] is False for node in context_nodes(template).values())
        client = engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "tester")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "tester", mode="real")
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED"}}},
        }
        assert context_nodes(template)["A"]["config_changed"] is False
        assert context_nodes(template)["B"]["config_changed"] is False
        edit_node(template)
        assert context_nodes(template)["A"]["config_changed"] is True


@pytest.mark.parametrize("node_type", ["SubCanvas", "SubProcess"])
def test_nested_execution_configuration_excludes_canvas_layout(node_type):
    """子画布的参数变化影响容器指纹，内部布局变化不影响指纹。"""
    inner = {"activities": {"A": {"type": "ServiceActivity", "component": {"data": {"name": "first"}}}}}
    tree = {"activities": {"S": {"type": node_type, "pipeline": inner, "loop_config": {"loop_times": 2}}}}
    before = compute_debug_config_hashes(tree)
    inner["location"] = [{"id": "A", "x": 999}]
    inner["activities"]["A"]["name"] = "display only"
    assert compute_debug_config_hashes(tree) == before
    inner["activities"]["A"]["component"]["data"]["name"] = "second"
    assert compute_debug_config_hashes(tree) != before


@pytest.mark.parametrize("field", ["auto_retry", "timeout_config", "error_ignorable", "version", "loop_config"])
def test_execution_options_are_not_omitted_from_fingerprint(field):
    """重试、超时、子流程版本等执行字段均影响配置一致性。"""
    tree = {"activities": {"A": {"type": "ServiceActivity", "component": {"code": "t"}}}}
    before = compute_debug_config_hashes(tree)
    tree["activities"]["A"][field] = {"enable": True}
    assert compute_debug_config_hashes(tree) != before
