"""任务状态信号的调用上下文。"""

from contextlib import contextmanager
from contextvars import ContextVar

_SUPPRESSED_NODE_FAILURES = ContextVar("suppressed_node_failures", default=frozenset())


@contextmanager
def suppress_node_failure_side_effects(root_pipeline_id, node_id):
    """在当前调用链内屏蔽指定节点 FAILED 的重试、回调和失败消息。"""
    suppressed = _SUPPRESSED_NODE_FAILURES.get()
    token = _SUPPRESSED_NODE_FAILURES.set(suppressed | {(root_pipeline_id, node_id)})
    try:
        yield
    finally:
        _SUPPRESSED_NODE_FAILURES.reset(token)


def is_node_failure_side_effects_suppressed(root_pipeline_id, node_id):
    """判断指定节点的 FAILED 是否处于副作用屏蔽上下文。"""
    return (root_pipeline_id, node_id) in _SUPPRESSED_NODE_FAILURES.get()
