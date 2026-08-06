"""任务状态信号处理测试。"""

from bamboo_engine import states as bamboo_engine_states

from bkflow.task.signals.context import (
    is_node_failure_side_effects_suppressed,
    suppress_node_failure_side_effects,
)
from bkflow.task.signals.handlers import bamboo_engine_eri_post_set_state_handler


def test_terminating_debug_failure_skips_failure_side_effects(mocker):
    """调试终止产生的 FAILED 不应触发重试、失败回调和失败消息。"""
    suppressed = mocker.patch(
        "bkflow.task.signals.handlers.is_node_failure_side_effects_suppressed",
        return_value=True,
        create=True,
    )
    dispatch_retry = mocker.patch("bkflow.task.signals.handlers._dispatch_auto_retry_node_task")
    check_callback = mocker.patch("bkflow.task.signals.handlers._check_and_callback")
    send_message = mocker.patch("bkflow.task.signals.handlers.send_task_message.apply_async")
    timeout_update = mocker.patch("bkflow.task.signals.handlers._node_timeout_info_update")

    bamboo_engine_eri_post_set_state_handler(
        sender=None,
        node_id="runtime-node",
        to_state=bamboo_engine_states.FAILED,
        version="v1",
        root_id="debug-root",
        parent_id="debug-root",
        loop=1,
    )

    suppressed.assert_called_once_with("debug-root", "runtime-node")
    dispatch_retry.assert_not_called()
    check_callback.assert_not_called()
    send_message.assert_not_called()
    timeout_update.assert_called_once_with(mocker.ANY, bamboo_engine_states.FAILED, "runtime-node", "v1")


def test_failure_side_effect_suppression_only_applies_inside_context():
    """副作用屏蔽仅在指定节点的当前调用上下文内生效。"""
    assert not is_node_failure_side_effects_suppressed("debug-root", "runtime-node")

    with suppress_node_failure_side_effects("debug-root", "runtime-node"):
        assert is_node_failure_side_effects_suppressed("debug-root", "runtime-node")
        assert not is_node_failure_side_effects_suppressed("debug-root", "other-node")

    assert not is_node_failure_side_effects_suppressed("debug-root", "runtime-node")


def test_normal_failure_keeps_failure_side_effects(mocker):
    """普通 FAILED 仍执行自动重试判断、失败回调和失败消息。"""
    dispatch_retry = mocker.patch(
        "bkflow.task.signals.handlers._dispatch_auto_retry_node_task",
        return_value=False,
    )
    check_callback = mocker.patch("bkflow.task.signals.handlers._check_and_callback")
    send_message = mocker.patch("bkflow.task.signals.handlers.send_task_message.apply_async")
    timeout_update = mocker.patch("bkflow.task.signals.handlers._node_timeout_info_update")

    bamboo_engine_eri_post_set_state_handler(
        sender=None,
        node_id="runtime-node",
        to_state=bamboo_engine_states.FAILED,
        version="v1",
        root_id="normal-root",
        parent_id="normal-root",
        loop=1,
    )

    dispatch_retry.assert_called_once_with("normal-root", "runtime-node")
    check_callback.assert_called_once_with("normal-root", task_success=False)
    send_message.assert_called_once()
    timeout_update.assert_called_once_with(mocker.ANY, bamboo_engine_states.FAILED, "runtime-node", "v1")
