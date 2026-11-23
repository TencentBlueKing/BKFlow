"""取消 Mock 与单步启动、过期锁回收之间的事务边界回归。"""

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from django.db import connection, connections, transaction
from django.utils import timezone

from bkflow.template.debug.service import (
    DebugConflictError,
    DebugService,
    DebugStateError,
)
from bkflow.template.models import DebugContext, DebugNodeState
from tests.interface.template.debug.test_step_run import TREE_DEP, TREE_GATEWAY

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(params=["B", "G"])
def consumer(request, mocker):
    """普通节点和条件网关都依赖 A 的产出；引擎调用使用替身。"""
    node_id = request.param
    tree = copy.deepcopy(TREE_DEP if node_id == "B" else TREE_GATEWAY)
    svc = DebugService(template_id=1, space_id=10, pipeline_tree=tree)
    svc.node_mock("A", mock_outputs={"k1": 20})
    client = mocker.MagicMock()
    client.create_task.return_value = {"result": True, "data": {"id": 123}}
    client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA", "B": "rtB"}}
    client.operate_task.return_value = {"result": True}
    mocker.patch.object(svc, "_task_client", return_value=client)
    return svc, node_id, client


def change_after_initial_read(svc, mocker, change):
    """另一请求在首次读取上下文后提交修改，保留调用方手中的旧对象。"""
    original = svc.sync_node_states

    def sync_then_change():
        ctx = original()
        other = DebugService(template_id=1, space_id=10, pipeline_tree=svc.pipeline_tree)
        change(other)
        return ctx

    mocker.patch.object(svc, "sync_node_states", side_effect=sync_then_change)


def test_cancel_before_step_lock_blocks_stale_inputs(consumer, mocker):
    """取消先提交时，即使单步已读过旧变量，也须重新检查并拒绝执行。"""
    svc, node_id, client = consumer
    change_after_initial_read(svc, mocker, lambda other: other.node_mock("A", enable=False))

    with pytest.raises(DebugStateError, match="依赖未满足"):
        svc.step_run(node_id, "tester")

    client.create_task.assert_not_called()
    ctx = svc.get_or_create_context()
    assert ctx.status == "idle" and ctx.locked_at is None
    assert "${g1}" not in ctx.global_vars
    assert DebugNodeState.objects.get(debug_context=ctx, node_id=node_id).status == "not_run"


def test_step_reads_latest_variables(consumer, mocker):
    """依赖仍满足时使用新值，不能仅重新判定存在后继续使用旧输入。"""
    svc, node_id, client = consumer
    change_after_initial_read(svc, mocker, lambda other: other.node_mock("A", mock_outputs={"k1": -3}))
    result = svc.step_run(node_id, "tester")
    if node_id == "B":
        assert client.create_task.call_args.args[0]["pipeline_tree"]["constants"]["${g1}"]["value"] == -3
    else:
        assert result["selected_flow_ids"] == ["flow_default"]


def test_explicit_overrides_still_work_after_cancel(consumer, mocker):
    """显式输入覆盖不受缺失全局变量影响，保持原有普通节点和网关行为。"""
    svc, node_id, client = consumer
    change_after_initial_read(svc, mocker, lambda other: other.node_mock("A", enable=False))
    result = svc.step_run(node_id, "tester", input_overrides={"${g1}": -3})
    if node_id == "B":
        assert client.create_task.call_args.args[0]["pipeline_tree"]["constants"]["${g1}"]["value"] == -3
    else:
        assert result["selected_flow_ids"] == ["flow_default"]


def test_step_conflict_preserves_other_run(consumer, mocker):
    """预检之后启动的新运行不能被当前单步覆盖或释放。"""
    svc, node_id, client = consumer
    change_after_initial_read(svc, mocker, lambda other: other._acquire_lock(other.get_or_create_context(), "other"))
    with pytest.raises(DebugConflictError):
        svc.step_run(node_id, "tester")
    ctx = svc.get_or_create_context()
    assert ctx.status == "running" and ctx.locked_by == "other"
    client.create_task.assert_not_called()


def test_real_step_calls_engine_after_transaction_commits(mocker):
    """执行锁先提交，引擎请求不占用数据库行锁，期间取消会被运行状态拒绝。"""
    svc = DebugService(template_id=1, space_id=10, pipeline_tree=copy.deepcopy(TREE_DEP))
    svc.node_mock("A", mock_outputs={"k1": 20})
    client = mocker.MagicMock()

    def create_task(payload):
        assert not connection.in_atomic_block
        assert svc.get_or_create_context().status == "running"
        with pytest.raises(DebugConflictError):
            svc.node_mock("A", enable=False)
        return {"result": True, "data": {"id": 123}}

    client.create_task.side_effect = create_task
    client.get_node_id_map.return_value = {"result": True, "data": {"B": "rtB"}}
    client.operate_task.return_value = {"result": True}
    mocker.patch.object(svc, "_task_client", return_value=client)
    assert svc.step_run("B", "tester")["status"] == "running"


@pytest.mark.parametrize("invalid_node", ["missing", "G"])
def test_stale_reclaim_commits_before_invalid_mock_request(mocker, invalid_node):
    """引擎撤销在事务外执行；后续未知节点或网关校验失败不回滚已回收状态。"""
    svc = DebugService(template_id=1, space_id=10, pipeline_tree=copy.deepcopy(TREE_GATEWAY))
    ctx = svc.sync_node_states()
    DebugContext.objects.filter(pk=ctx.pk).update(
        status="running", locked_at=timezone.now() - timedelta(minutes=30), active_task_id=999
    )
    client = mocker.MagicMock()
    revoke_transactions = []

    def revoke(*args):
        revoke_transactions.append(connection.in_atomic_block)
        assert not connection.in_atomic_block
        assert svc.get_or_create_context().status == "idle"
        return {"result": True}

    client.operate_task.side_effect = revoke
    mocker.patch.object(svc, "_task_client", return_value=client)
    with pytest.raises(DebugStateError):
        svc.node_mock(invalid_node, enable=False)
    client.operate_task.assert_called_once_with(999, "revoke", {"operator": "system"})
    assert revoke_transactions == [False]
    ctx.refresh_from_db()
    assert ctx.status == "idle" and ctx.active_task_id is None and ctx.locked_at is None


@pytest.mark.parametrize("during_revoke", ["timeout", "new_run", "save_failure"])
def test_stale_reclaim_is_independent_of_mock_configuration(mocker, during_revoke):
    """撤销超时、回收期间新运行及配置落库失败均不把已回收锁恢复为旧任务。"""
    svc = DebugService(template_id=1, space_id=10, pipeline_tree=copy.deepcopy(TREE_DEP))
    svc.node_mock("A", mock_outputs={"k1": 20})
    ctx = svc.get_or_create_context()
    DebugContext.objects.filter(pk=ctx.pk).update(
        status="running", locked_at=timezone.now() - timedelta(minutes=30), active_task_id=999
    )
    client = mocker.MagicMock()
    revoke_transactions = []

    def revoke(*args):
        revoke_transactions.append(connection.in_atomic_block)
        assert not connection.in_atomic_block
        if during_revoke == "timeout":
            raise TimeoutError("engine unavailable")
        if during_revoke == "new_run":
            svc._acquire_lock(svc.get_or_create_context(), "other")
        return {"result": True}

    client.operate_task.side_effect = revoke
    mocker.patch.object(svc, "_task_client", return_value=client)
    original_save = DebugContext.save

    def save(instance, *args, **kwargs):
        if "global_vars" in kwargs.get("update_fields", []):
            raise RuntimeError("write failed")
        return original_save(instance, *args, **kwargs)

    if during_revoke == "save_failure":
        mocker.patch.object(DebugContext, "save", save)
        with pytest.raises(RuntimeError, match="write failed"):
            svc.node_mock("A", enable=False)
    elif during_revoke == "new_run":
        with pytest.raises(DebugConflictError):
            svc.node_mock("A", enable=False)
    else:
        svc.node_mock("A", enable=False)
    assert revoke_transactions == [False]
    ctx.refresh_from_db()
    assert ctx.active_task_id is None
    assert ctx.status == ("running" if during_revoke == "new_run" else "idle")
    if during_revoke == "new_run":
        assert ctx.locked_by == "other"
    state = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
    assert state.execution_mode == ("real" if during_revoke == "timeout" else "mock")
    assert ("${g1}" in ctx.global_vars) == (during_revoke != "timeout")


@pytest.mark.parametrize("first", ["cancel", "step"])
def test_mysql_cancel_and_step_serialize(consumer, first):
    """两个真实连接竞争同一上下文：取消先提交则单步拒绝；执行先提交则取消拒绝。"""
    if connection.vendor != "mysql":
        pytest.skip("requires MySQL row locks")
    svc, node_id, client = consumer
    waiting = Event()

    def mark_lock_attempt(execute, sql, params, many, context):
        if "template_debugcontext" in sql.lower() and ("FOR UPDATE" in sql.upper() or sql.startswith("UPDATE")):
            waiting.set()
        return execute(sql, params, many, context)

    def competing_request():
        connections.close_all()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")
            other = DebugService(template_id=1, space_id=10, pipeline_tree=copy.deepcopy(svc.pipeline_tree))
            other._task_client = lambda: client
            with connection.execute_wrapper(mark_lock_attempt):
                if first == "cancel":
                    return other.step_run(node_id, "other")
                return other.node_mock("A", enable=False)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            DebugContext.objects.select_for_update().get(template_id=1)
            if first == "cancel":
                svc.node_mock("A", enable=False)
            else:
                # 持有真实执行锁，模拟单步已准备完成但事务尚未提交。
                svc._acquire_lock(svc.get_or_create_context(), "tester")
            future = pool.submit(competing_request)
            assert waiting.wait(5), "competing request did not reach the context lock"
            assert not future.done()
        expected_error = DebugStateError if first == "cancel" else DebugConflictError
        with pytest.raises(expected_error):
            future.result(timeout=10)
    client.create_task.assert_not_called()
    ctx = svc.get_or_create_context()
    assert ctx.status == ("idle" if first == "cancel" else "running")
    assert ("${g1}" in ctx.global_vars) == (first != "cancel")
