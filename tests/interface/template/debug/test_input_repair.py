"""历史输入修复必须匹配运行版本，不能改写其他快照信息或当前控制状态。"""

import copy
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from bkflow.template.debug.backfill import backfill_context
from bkflow.template.debug.input_repair import repair_snapshot_inputs
from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, DebugNodeState
from tests.interface.template.debug import test_backfill
from tests.interface.template.debug.test_backfill import (
    historical_task,
    run_command,
    state_rows,
)

template = test_backfill.template
legacy = test_backfill.legacy


@pytest.fixture
def existing_snapshot(legacy, mocker):
    """构造已有快照但 inputs 遗漏的记录，所有历史读取使用替身。"""
    ctx, tasks, client, _ = legacy
    assert backfill_context(ctx.pk, apply=True)["outcome"] == "applied"
    ctx.refresh_from_db()
    for node in ctx.debug_snapshot["nodes"]:
        node["inputs"] = {}
    ctx.save()
    details = {
        f"rt101{node_id}": {
            "id": f"rt101{node_id}",
            "version": "v3",
            "state": "FINISHED",
            "inputs": {"rendered": node_id, "credentials": "******", "nested": {"value": 0}},
        }
        for node_id in ("A", "B")
    }
    client.get_task_node_detail.side_effect = lambda task_id, node_id, data: {
        "result": True,
        "data": copy.deepcopy(details[node_id]),
    }
    factory = mocker.patch("bkflow.template.debug.input_repair.TaskComponentClient", return_value=client)
    return ctx, tasks, client, factory, details


@pytest.mark.django_db
class TestSnapshotInputRepair:
    def test_preview_apply_and_idempotence(self, existing_snapshot):
        """只补输入，预览零写入，重复执行不再读取引擎。"""
        ctx, _, client, factory, details = existing_snapshot
        before = copy.deepcopy(ctx.debug_snapshot)
        rows = state_rows(ctx)
        assert repair_snapshot_inputs(ctx.pk) == {"outcome": "ready", "nodes": 2}
        ctx.refresh_from_db()
        assert ctx.debug_snapshot == before
        assert repair_snapshot_inputs(ctx.pk, apply=True) == {"outcome": "applied", "nodes": 2}
        ctx.refresh_from_db()
        for old, new in zip(before["nodes"], ctx.debug_snapshot["nodes"]):
            assert new == {**old, "inputs": details[old["log_ref"]["node_id"]]["inputs"]}
        assert state_rows(ctx) == rows
        calls = factory.call_count
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == "no_missing_inputs"
        assert factory.call_count == calls
        client.create_task.assert_not_called()
        client.operate_task.assert_not_called()

    def test_each_node_uses_own_task_including_failed_deleted_node(self, existing_snapshot, template):
        """单步覆盖和已从草稿删除的节点仍按自己的历史引用恢复。"""
        ctx, tasks, client, _, details = existing_snapshot
        tasks[102] = historical_task(template.id, 102, {"A": "step A"}, step=True)
        node = ctx.debug_snapshot["nodes"][0]
        node.update(status="failed", log_ref={"instance_id": 102, "node_id": "rt102A", "version": "v4"})
        ctx.save()
        details["rt102A"] = {"id": "rt102A", "version": "v4", "state": "FAILED", "inputs": {"step": True}}
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").delete()
        tree = copy.deepcopy(DebugService(template.id).pipeline_tree)
        tree["activities"].pop("A")
        template.update_draft_snapshot(tree, "editor")
        assert repair_snapshot_inputs(ctx.pk, apply=True)["nodes"] == 2
        ctx.refresh_from_db()
        assert ctx.debug_snapshot["nodes"][0]["inputs"] == {"step": True}
        assert not DebugNodeState.objects.filter(debug_context=ctx, node_id="A").exists()
        assert [call.args[:2] for call in client.get_task_node_detail.call_args_list] == [
            (102, "rt102A"),
            (101, "rt101B"),
        ]

    def test_preserves_nonempty_and_unexecuted_inputs(self, existing_snapshot):
        """已有输入、未运行节点、网关和本地 Mock 都不向引擎补造输入。"""
        ctx, _, _, factory, _ = existing_snapshot
        first = ctx.debug_snapshot["nodes"][0]
        first["inputs"] = {"keep": False}
        ctx.debug_snapshot["nodes"][1]["status"] = "not_run"
        ctx.debug_snapshot["nodes"].extend(
            [
                {**copy.deepcopy(first), "inputs": {}, "node_type": "ParallelGateway"},
                {**copy.deepcopy(first), "inputs": {}, "log_ref": None},
            ]
        )
        ctx.save()
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == "no_missing_inputs"
        factory.assert_not_called()

    @pytest.mark.parametrize(
        "changes,reason",
        [
            ({"debug_snapshot": None}, "snapshot_missing_or_reset"),
            ({"debug_snapshot": {}}, "snapshot_missing_or_reset"),
            ({"debug_snapshot": {"nodes": []}}, "no_missing_inputs"),
            ({"status": "running"}, "context_active"),
            ({"active_task_id": 101}, "context_active"),
            ({"active_debug_snapshot": {"node_ids": ["A"]}}, "context_active"),
            ({"is_deleted": True}, "context_deleted"),
        ],
    )
    def test_ineligible_context_is_not_read(self, existing_snapshot, changes, reason):
        """重置、缺失快照和正在调试等上下文不得被修复复活。"""
        ctx, _, _, factory, _ = existing_snapshot
        DebugContext.objects.filter(pk=ctx.pk).update(**changes)
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == reason
        factory.assert_not_called()

    @pytest.mark.parametrize(
        "change,reason",
        [
            ({"version": "other-run"}, "node_version_mismatch"),
            ({"id": "other-node"}, "node_version_mismatch"),
            ({"state": "RUNNING"}, "node_state_mismatch"),
            ({"inputs": None}, "missing_execution_inputs"),
            ({"inputs": []}, "missing_execution_inputs"),
        ],
    )
    def test_bad_second_node_prevents_partial_write(self, existing_snapshot, change, reason):
        """版本漂移、运行中或数据缺失时整条跳过，避免混入其他轮次。"""
        ctx, _, _, _, details = existing_snapshot
        before = copy.deepcopy(ctx.debug_snapshot)
        details["rt101B"].update(change)
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == reason
        ctx.refresh_from_db()
        assert ctx.debug_snapshot == before

    @pytest.mark.parametrize(
        "field,value",
        [("space_id", 999), ("template_id", 999), ("create_method", "API"), ("is_deleted", True), ("is_expired", True)],
    )
    def test_task_identity_is_checked(self, existing_snapshot, field, value):
        """不可跨空间、跨模板或恢复已删除/过期任务。"""
        ctx, tasks, client, _, _ = existing_snapshot
        tasks[101][field] = value
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == "task_identity_mismatch"
        client.get_task_node_detail.assert_not_called()

    def test_node_mapping_is_checked(self, existing_snapshot):
        """运行时节点必须属于快照中的模板节点。"""
        ctx, tasks, client, _, _ = existing_snapshot
        tasks[101]["pipeline_tree"]["activities"]["rt101A"]["template_node_id"] = "another-node"
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == "invalid_node_mapping"
        client.get_task_node_detail.assert_not_called()

    @pytest.mark.parametrize("version", [None, "", "v1"])
    def test_unknown_version_is_skipped(self, existing_snapshot, version):
        """无版本或旧兜底版本不能证明参数来自同一次执行。"""
        ctx, _, client, _, _ = existing_snapshot
        ctx.debug_snapshot["nodes"][0]["log_ref"]["version"] = version
        ctx.save()
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == "missing_log_ref"
        client.get_task_node_detail.assert_not_called()

    def test_empty_actual_inputs_are_not_fabricated(self, existing_snapshot):
        """引擎同版本输入本来为空时保持空值。"""
        ctx, _, _, _, details = existing_snapshot
        for detail in details.values():
            detail["inputs"] = {}
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == "no_execution_inputs"

    @pytest.mark.parametrize("change", ["reset", "new_run", "new_snapshot"])
    def test_concurrent_change_wins(self, existing_snapshot, change):
        """远程读取期间的新运行、重置和快照更新都优先于修复。"""
        ctx, _, client, _, _ = existing_snapshot
        original = client.get_task_node_detail.side_effect

        def read_and_change(*args, **kwargs):
            if change == "reset":
                DebugService(ctx.template_id).reset()
            else:
                fields = {"status": "running"} if change == "new_run" else {"debug_snapshot": {"nodes": []}}
                DebugContext.objects.filter(pk=ctx.pk).update(**fields)
            return original(*args, **kwargs)

        client.get_task_node_detail.side_effect = read_and_change
        assert repair_snapshot_inputs(ctx.pk, apply=True)["reason"] == "concurrent_change"
        ctx.refresh_from_db()
        if change != "new_run":
            assert ctx.debug_snapshot == ({} if change == "reset" else {"nodes": []})

    def test_command_preview_and_apply(self, existing_snapshot):
        """新参数复用范围和预览约束，普通回填模式仍跳过已有快照。"""
        ctx, _, _, _, _ = existing_snapshot
        assert run_command(template_id=[ctx.template_id])[0]["reason"] == "snapshot_exists_or_reset"
        report = run_command(template_id=[ctx.template_id], repair_inputs=True)
        assert report[-1]["operation"] == "repair_inputs"
        assert report[-1]["mode"] == "dry_run"
        ctx.refresh_from_db()
        assert ctx.debug_snapshot["nodes"][0]["inputs"] == {}
        report = run_command(template_id=[ctx.template_id], repair_inputs=True, apply=True)
        assert report[-1]["counts"] == {"applied": 1}

    def test_engine_error_does_not_leak_payload(self, existing_snapshot):
        """接口失败报告不含输入或异常正文，也不会写入部分节点。"""
        ctx, _, client, _, _ = existing_snapshot
        before = copy.deepcopy(ctx.debug_snapshot)
        client.get_task_node_detail.side_effect = RuntimeError("sensitive-input")
        stream = io.StringIO()
        with pytest.raises(CommandError):
            call_command(
                "backfill_debug_snapshots", template_id=[ctx.template_id], repair_inputs=True, apply=True, stdout=stream
            )
        assert "sensitive-input" not in stream.getvalue()
        assert "engine_request_failed" in stream.getvalue()
        ctx.refresh_from_db()
        assert ctx.debug_snapshot == before
