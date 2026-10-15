"""存量回填只使用历史证据，不覆盖新调试、重置或已有快照。"""

import copy
import io
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.expressions import RawSQL
from django.utils import timezone

from bkflow.template.debug.backfill import backfill_context
from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, DebugNodeState
from tests.interface.template.debug import test_config_changed

template = test_config_changed.template


def historical_task(template_id, task_id=101, names=None, step=False):
    """模拟 Engine 返回运行时 ID 和原始任务节点快照的不同形态。"""
    names = names or {"A": "old A", "B": "old B"}
    mapping = {node_id: f"rt{task_id}{node_id}" for node_id in names}
    activities = {
        mapping[node_id]: {
            "id": mapping[node_id],
            "template_node_id": node_id,
            "name": name,
            "type": "ServiceActivity",
        }
        for node_id, name in names.items()
    }
    order = ["start", *mapping.values(), "end"]
    return {
        "id": task_id,
        "template_id": template_id,
        "space_id": 1,
        "create_method": "DEBUG",
        "is_started": True,
        "executor": f"runner{task_id}",
        "pipeline_tree": {
            "name": "debug_single_node" if step else "flow",
            "activities": activities,
            "gateways": {},
            "start_event": {"id": "start"},
            "end_event": {"id": "end"},
            "flows": {str(i): {"source": a, "target": b} for i, (a, b) in enumerate(zip(order, order[1:]))},
        },
    }


@pytest.fixture
def legacy(template, mocker):
    """真实 Interface 表配合纯内存 Engine，禁止访问实际环境。"""
    ctx = DebugContext.objects.create(
        template_id=template.id, space_id=1, last_task_id=101, last_run_type="global", last_run_status="finished"
    )
    for node_id in ("A", "B"):
        DebugNodeState.objects.create(
            debug_context=ctx,
            node_id=node_id,
            status="finished",
            inputs={"original": node_id},
            outputs={"result": node_id},
            duration_ms=20,
            log_ref={"instance_id": 101, "node_id": f"rt101{node_id}", "version": "v3"},
            last_run_at=timezone.now(),
            # 当前 Mock 配置不能作为历史执行模式。
            execution_mode="mock",
        )
    tasks = {101: historical_task(template.id)}
    client = mocker.Mock()
    client.get_task_detail.side_effect = lambda task_id: {"result": True, "data": copy.deepcopy(tasks[task_id])}
    client.get_task_mock_data.side_effect = lambda task_id: {
        "result": True,
        "data": {"taskflow_id": task_id, "data": {"nodes": []}},
    }

    def original_node(task_id, data):
        """原始快照的 id 为模板节点 ID。"""
        node = tasks[task_id]["pipeline_tree"]["activities"][data["node_id"]]
        return {"result": True, "data": {**node, "id": node["template_node_id"]}}

    client.get_node_snapshot_config.side_effect = original_node
    factory = mocker.patch("bkflow.template.debug.backfill.TaskComponentClient", return_value=client)
    return ctx, tasks, client, factory


def state_rows(ctx):
    """比较所有节点字段，确保回填不改变运行态或比较基准。"""
    return list(DebugNodeState.objects.filter(debug_context=ctx).order_by("id").values())


def run_command(**kwargs):
    """读取命令逐行报告，默认只预览。"""
    stream = io.StringIO()
    call_command("backfill_debug_snapshots", stdout=stream, **kwargs)
    return [json.loads(line) for line in stream.getvalue().splitlines()]


@pytest.mark.django_db
class TestDebugSnapshotBackfill:
    def test_preview_and_idempotent_apply(self, legacy, template):
        """预览零写入；实际回填保存旧名称和结果，重复执行不再查询引擎。"""
        ctx, tasks, client, factory = legacy
        before = state_rows(ctx)
        assert backfill_context(ctx.pk) == {"outcome": "ready", "nodes": 2}
        ctx.refresh_from_db()
        assert ctx.debug_snapshot is None
        assert state_rows(ctx) == before
        assert backfill_context(ctx.pk, apply=True) == {"outcome": "applied", "nodes": 2}
        ctx.refresh_from_db()
        nodes = ctx.debug_snapshot["nodes"]
        assert [node["node_id"] for node in nodes] == ["A", "B"]
        assert nodes[0]["node_name"] == "old A"
        assert nodes[0]["outputs"] == {"result": "A"}
        assert nodes[0]["inputs"] == {"original": "A"}
        assert nodes[0]["log_ref"]["version"] == "v3"
        assert nodes[0]["duration_ms"] == 20
        assert nodes[0]["operator"] == "runner101"
        assert nodes[0]["execution_mode"] == "real"
        assert state_rows(ctx) == before
        factory.assert_called_with(space_id=1)
        calls = factory.call_count
        assert backfill_context(ctx.pk, apply=True)["reason"] == "snapshot_exists_or_reset"
        assert factory.call_count == calls
        view = DebugService(template.id).build_context_view()
        assert all(not node["config_changed"] for node in view["debug_snapshot"]["nodes"])
        assert ctx.active_debug_snapshot is None
        client.create_task.assert_not_called()
        client.operate_task.assert_not_called()

    def test_existing_baselines_are_preserved(self, legacy, template):
        """已有配置及名称基准不能被历史任务或当前草稿重算覆盖。"""
        ctx, _, _, _ = legacy
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(
            debug_config_hash="original-hash", debug_node_name="original name"
        )
        before = state_rows(ctx)
        backfill_context(ctx.pk, apply=True)
        assert state_rows(ctx) == before
        data = DebugService(template.id).build_context_view()
        assert data["debug_snapshot"]["nodes"][0]["config_changed"] is True

    def test_step_uses_its_own_task_and_global_order(self, legacy, template):
        """全局结果之后单步一个节点，名称、执行人来自各自任务，顺序沿用全局历史。"""
        ctx, tasks, _, _ = legacy
        tasks[102] = historical_task(template.id, 102, {"A": "step A"}, step=True)
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(
            log_ref={"instance_id": 102, "node_id": "rt102A"}
        )
        ctx.last_run_type, ctx.last_task_id = "step", 102
        ctx.save()
        assert backfill_context(ctx.pk, apply=True)["outcome"] == "applied"
        ctx.refresh_from_db()
        assert [(n["node_name"], n["operator"]) for n in ctx.debug_snapshot["nodes"]] == [
            ("step A", "runner102"),
            ("old B", "runner101"),
        ]

    def test_single_step_can_be_recovered(self, legacy, template):
        """只有一个已执行节点时不需要猜测多个单步之间的流程顺序。"""
        ctx, tasks, _, _ = legacy
        tasks[101] = historical_task(template.id, names={"A": "single A"}, step=True)
        DebugNodeState.objects.filter(debug_context=ctx, node_id="B").update(status="not_run", log_ref={})
        ctx.last_run_type = "step"
        ctx.save()
        assert backfill_context(ctx.pk, apply=True) == {"outcome": "applied", "nodes": 1}

    def test_multiple_steps_without_full_history_are_skipped(self, legacy, template):
        """多个单步任务没有完整流程顺序依据，整条跳过。"""
        ctx, tasks, _, _ = legacy
        tasks[101] = historical_task(template.id, names={"A": "A"}, step=True)
        tasks[102] = historical_task(template.id, 102, {"B": "B"}, step=True)
        DebugNodeState.objects.filter(debug_context=ctx, node_id="B").update(
            log_ref={"instance_id": 102, "node_id": "rt102B"}
        )
        ctx.last_run_type, ctx.last_task_id = "step", 102
        ctx.save()
        assert backfill_context(ctx.pk, apply=True)["reason"] == "ambiguous_order"
        ctx.refresh_from_db()
        assert ctx.debug_snapshot is None

    def test_global_unreached_nodes_and_new_draft_nodes(self, legacy):
        """全局任务未执行节点可展示；后加到草稿的节点不进入旧快照。"""
        ctx, _, _, _ = legacy
        DebugNodeState.objects.filter(debug_context=ctx, node_id="B").update(status="not_run", log_ref={}, outputs={})
        DebugNodeState.objects.create(debug_context=ctx, node_id="C")
        assert backfill_context(ctx.pk, apply=True)["nodes"] == 2
        ctx.refresh_from_db()
        assert ctx.debug_snapshot["nodes"][1]["status"] == "not_run"

    def test_runtime_conversion_uses_original_node_type(self, legacy):
        """活动的原始类型与历史 Mock 模式来自任务快照，不从当前控制态推断。"""
        ctx, _, client, _ = legacy
        client.get_node_snapshot_config.side_effect = lambda task_id, data: {
            "result": True,
            "data": {"id": data["node_id"][-1], "type": "SubCanvas", "name": "old canvas"},
        }
        client.get_task_mock_data.side_effect = None
        client.get_task_mock_data.return_value = {
            "result": True,
            "data": {"taskflow_id": 101, "data": {"nodes": ["rt101A"]}},
        }
        backfill_context(ctx.pk, apply=True)
        ctx.refresh_from_db()
        assert ctx.debug_snapshot["nodes"][0]["node_type"] == "SubCanvas"
        assert ctx.debug_snapshot["nodes"][0]["execution_mode"] == "mock"

    @pytest.mark.parametrize("snapshot", [{}, {"nodes": []}, {"nodes": [{"node_id": "new"}]}])
    def test_existing_or_reset_snapshot_is_never_overwritten(self, legacy, snapshot):
        """空对象也是主动重置标记，不能当作缺失快照。"""
        ctx, _, _, factory = legacy
        DebugContext.objects.filter(pk=ctx.pk).update(debug_snapshot=snapshot)
        assert backfill_context(ctx.pk, apply=True)["reason"] == "snapshot_exists_or_reset"
        factory.assert_not_called()

    def test_json_null_is_not_sql_null(self, legacy):
        """只允许 SQL NULL，不能误报未写入的 JSON null 为回填成功。"""
        ctx, _, _, factory = legacy
        DebugContext.objects.filter(pk=ctx.pk).update(debug_snapshot=RawSQL("%s", ["null"]))
        assert backfill_context(ctx.pk, apply=True)["reason"] == "snapshot_exists_or_reset"
        factory.assert_not_called()

    @pytest.mark.parametrize("status", ["running", "terminating"])
    def test_running_context_is_skipped(self, legacy, status):
        """回填不能接管存量运行中的任务。"""
        ctx, _, _, factory = legacy
        DebugContext.objects.filter(pk=ctx.pk).update(status=status)
        assert backfill_context(ctx.pk, apply=True)["reason"] == "context_active"
        factory.assert_not_called()

    @pytest.mark.parametrize("field,value", [("space_id", 2), ("template_id", 999), ("create_method", "API")])
    def test_foreign_task_is_skipped(self, legacy, field, value):
        """即使接口返回成功，也复核任务空间、模板与 DEBUG 类型。"""
        ctx, tasks, _, _ = legacy
        tasks[101][field] = value
        assert backfill_context(ctx.pk, apply=True)["reason"] == "task_identity_mismatch"

    @pytest.mark.parametrize(
        "field,value,reason",
        [
            ("log_ref", {}, "missing_log_ref"),
            ("status", "paused", "unfinished_nodes"),
            ("log_ref", {"instance_id": 101, "node_id": "wrong"}, "invalid_node_mapping"),
        ],
    )
    def test_incomplete_node_history_is_skipped(self, legacy, field, value, reason):
        """没有任务的同步 Mock、残留运行态或错误 ID 映射均不能猜测恢复。"""
        ctx, _, _, _ = legacy
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(**{field: value})
        assert backfill_context(ctx.pk, apply=True)["reason"] == reason

    def test_deleted_node_state_is_not_fabricated(self, legacy):
        """历史流程包含已丢失的节点状态时整条跳过，不补造空结果。"""
        ctx, _, _, _ = legacy
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").delete()
        assert backfill_context(ctx.pk, apply=True)["reason"] == "missing_node_state"

    def test_parallel_order_uses_template_ids(self, legacy):
        """并行分支的运行时 ID 顺序与模板 ID 相反时，仍按模板 ID 稳定排序。"""
        ctx, tasks, _, _ = legacy
        tree = tasks[101]["pipeline_tree"]
        for node_id, runtime_id in (("A", "z"), ("B", "a")):
            node = tree["activities"].pop(f"rt101{node_id}")
            node["id"] = runtime_id
            tree["activities"][runtime_id] = node
            DebugNodeState.objects.filter(debug_context=ctx, node_id=node_id).update(
                log_ref={"instance_id": 101, "node_id": runtime_id}
            )
        tree["flows"] = {
            str(i): {"source": source, "target": target}
            for i, (source, target) in enumerate([("start", "z"), ("start", "a"), ("z", "end"), ("a", "end")])
        }
        assert backfill_context(ctx.pk, apply=True)["outcome"] == "applied"
        ctx.refresh_from_db()
        assert [node["node_id"] for node in ctx.debug_snapshot["nodes"]] == ["A", "B"]

    def test_inconsistent_global_histories_are_skipped(self, legacy, template):
        """不同全局任务的流程顺序冲突时，不选择一个覆盖另一个。"""
        ctx, tasks, _, _ = legacy
        tasks[102] = historical_task(template.id, 102, {"B": "B", "A": "A"})
        DebugNodeState.objects.filter(debug_context=ctx, node_id="B").update(
            log_ref={"instance_id": 102, "node_id": "rt102B"}
        )
        assert backfill_context(ctx.pk, apply=True)["reason"] == "ambiguous_order"

    @pytest.mark.parametrize("field,value", [("activities", []), ("flows", {}), ("gateways", None)])
    def test_incomplete_pipeline_is_skipped(self, legacy, field, value):
        """历史流程结构缺失时报告跳过，不能凭 ID 排出伪造的流程顺序。"""
        ctx, tasks, _, _ = legacy
        tasks[101]["pipeline_tree"][field] = value
        assert backfill_context(ctx.pk, apply=True)["outcome"] == "skipped"
        ctx.refresh_from_db()
        assert ctx.debug_snapshot is None

    @pytest.mark.parametrize("mock_data", [{}, {"taskflow_id": 101, "data": None}])
    def test_missing_mock_metadata_is_skipped(self, legacy, mock_data):
        """缺少执行模式依据时不能把当前 Mock 设置当作历史值。"""
        ctx, _, client, _ = legacy
        client.get_task_mock_data.side_effect = None
        client.get_task_mock_data.return_value = {"result": True, "data": mock_data}
        assert backfill_context(ctx.pk, apply=True)["reason"] == "missing_mock_history"

    @pytest.mark.parametrize("change", ["reset", "new_run", "node_result", "node_deleted"])
    def test_change_during_history_read_prevents_write(self, legacy, change):
        """远程读取期间发生重置、新运行或节点变化，事务内复核必须拒绝旧计划。"""
        ctx, _, client, _ = legacy
        original = client.get_node_snapshot_config.side_effect

        def read_then_change(*args, **kwargs):
            if change == "reset":
                DebugService(ctx.template_id).reset_run_results(ctx)
            elif change == "new_run":
                DebugContext.objects.filter(pk=ctx.pk).update(debug_snapshot={"nodes": []}, status="running")
            elif change == "node_result":
                DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(outputs={"new": True})
            else:
                DebugNodeState.objects.filter(debug_context=ctx, node_id="A").delete()
            return original(*args, **kwargs)

        client.get_node_snapshot_config.side_effect = read_then_change
        assert backfill_context(ctx.pk, apply=True)["reason"] == "concurrent_change"

    def test_stale_reset_clears_snapshot_created_by_backfill(self, legacy):
        """重置持有回填前的旧对象，拿到锁后仍须读取并清理新补的快照。"""
        ctx, _, _, _ = legacy
        assert ctx.debug_snapshot is None
        backfill_context(ctx.pk, apply=True)
        DebugService(ctx.template_id).reset_run_results(ctx, node_ids=["A"])
        ctx.refresh_from_db()
        nodes = ctx.debug_snapshot["nodes"]
        assert nodes[0]["status"] == "not_run"
        assert nodes[0]["outputs"] == {}
        assert nodes[1]["status"] == "finished"
        DebugService(ctx.template_id).reset_run_results(ctx)
        ctx.refresh_from_db()
        assert ctx.debug_snapshot == {}

    def test_reset_legacy_context_leaves_explicit_marker(self, legacy):
        """未回填的旧记录全量重置后也留下标记，防止后续回填复活结果。"""
        ctx, _, _, _ = legacy
        DebugService(ctx.template_id).reset_run_results(ctx)
        assert backfill_context(ctx.pk, apply=True)["reason"] == "snapshot_exists_or_reset"


@pytest.mark.django_db
class TestBackfillCommand:
    def test_scope_limit_cursor_and_default_preview(self, legacy):
        """范围交集、分页游标及默认预览有效。"""
        ctx, _, _, _ = legacy
        second = DebugContext.objects.create(template_id=999, space_id=2)
        report = run_command(space_id=[1], template_id=[ctx.template_id], batch_size=1)
        assert report[-1]["counts"] == {"ready": 1}
        assert report[-1]["mode"] == "dry_run"
        ctx.refresh_from_db()
        assert ctx.debug_snapshot is None
        report = run_command(all=True, limit=1, batch_size=1)
        assert report[-1]["next_after_id"] == ctx.pk
        assert report[-1]["has_more"] is True
        report = run_command(all=True, after_id=ctx.pk)
        assert report[0]["id"] == second.pk
        assert report[-1]["counts"] == {"skipped": 1}

    def test_scan_does_not_follow_new_contexts(self, legacy):
        """分页上界固定，扫描中新增上下文不进入本轮。"""
        ctx, _, client, _ = legacy
        original = client.get_task_detail.side_effect

        def read_and_create(task_id):
            DebugContext.objects.create(template_id=999, space_id=1)
            return original(task_id)

        client.get_task_detail.side_effect = read_and_create
        report = run_command(all=True, batch_size=1)
        assert report[-1]["scanned"] == 1
        assert report[-1]["next_after_id"] == ctx.pk

    def test_failure_does_not_stop_other_contexts(self, legacy, template):
        """单个历史任务失败不影响后续记录，并发变化和失败记录均可重试。"""
        ctx, _, client, _ = legacy
        second = DebugContext.objects.create(template_id=999, space_id=1)
        client.get_task_detail.side_effect = RuntimeError("unavailable")
        stream = io.StringIO()
        with pytest.raises(CommandError):
            call_command("backfill_debug_snapshots", all=True, batch_size=1, stdout=stream)
        report = [json.loads(line) for line in stream.getvalue().splitlines()]
        assert report[1]["id"] == second.pk
        assert report[-1]["counts"] == {"error": 1, "skipped": 1}

    def test_apply_and_missing_scope(self, legacy):
        """显式 apply 才写入，无范围不能意外扫描全库。"""
        ctx, _, _, _ = legacy
        with pytest.raises(CommandError, match="请指定"):
            run_command()
        report = run_command(template_id=[ctx.template_id], apply=True)
        assert report[-1]["counts"] == {"applied": 1}

    @pytest.mark.parametrize("kwargs", [{"batch_size": 0}, {"limit": 0}, {"after_id": -1}, {"space_id": [-1]}])
    def test_invalid_arguments(self, kwargs):
        """拒绝非法批量参数。"""
        with pytest.raises(CommandError):
            run_command(template_id=[1], **kwargs)

    def test_wrong_module(self, settings):
        """Engine 进程不能直接运行 Interface 数据回填。"""
        from types import SimpleNamespace

        settings.BKFLOW_MODULE = SimpleNamespace(type="engine")
        with pytest.raises(CommandError, match="Interface"):
            run_command(all=True)

    def test_engine_failure_is_reported_without_sensitive_data(self, legacy):
        """读取失败不写入，继续输出汇总并以失败退出；不回显响应里的敏感内容。"""
        ctx, _, client, _ = legacy
        client.get_task_detail.side_effect = RuntimeError("secret-input-token")
        stream = io.StringIO()
        with pytest.raises(CommandError, match="部分历史任务读取失败"):
            call_command("backfill_debug_snapshots", all=True, apply=True, stdout=stream)
        report = stream.getvalue()
        assert "secret-input-token" not in report
        assert '"error": 1' in report
        assert "engine_request_failed" in report
        ctx.refresh_from_db()
        assert ctx.debug_snapshot is None
