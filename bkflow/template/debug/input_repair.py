"""按快照保存的任务、节点和运行版本修复遗漏的执行输入。"""

import copy

from django.db import transaction

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.template.debug.backfill import (
    BackfillSkipped,
    HistoryUnavailable,
    _read_history,
    read_debug_task,
)
from bkflow.template.models import DebugContext, Template


class SnapshotInputReader:
    """只取同一运行版本的实际输入，不渲染当前草稿或猜测旧参数。"""

    def __init__(self, context):
        self.context = context
        self.tasks = {}
        try:
            self.client = TaskComponentClient(space_id=context["space_id"])
        except Exception as exc:
            raise HistoryUnavailable("engine_client_unavailable") from exc

    def read(self, node):
        """先核实任务及节点映射，再核对详情的状态和版本。"""
        ref = node["log_ref"]
        if not isinstance(ref, dict):
            raise BackfillSkipped("missing_log_ref")
        task_id, runtime_id, version = ref.get("instance_id"), ref.get("node_id"), ref.get("version")
        if (
            type(task_id) is not int
            or task_id <= 0
            or not isinstance(runtime_id, str)
            or not runtime_id
            or not isinstance(version, str)
            or not version
            or version == "v1"  # 旧同步代码的兜底值不构成可核实的版本。
        ):
            raise BackfillSkipped("missing_log_ref")
        if task_id not in self.tasks:
            self.tasks[task_id] = read_debug_task(self.client, task_id, self.context)
        tree = self.tasks[task_id].get("pipeline_tree")
        activities = tree.get("activities") if isinstance(tree, dict) else None
        runtime_node = activities.get(runtime_id) if isinstance(activities, dict) else None
        if (
            not isinstance(runtime_node, dict)
            or runtime_node.get("id") != runtime_id
            or not node.get("node_id")
            or runtime_node.get("template_node_id") != node["node_id"]
        ):
            raise BackfillSkipped("invalid_node_mapping")
        detail = _read_history(
            self.client.get_task_node_detail,
            task_id,
            runtime_id,
            data={"include_data": True, "include_loop_outputs": True},
        )
        if detail.get("id") != runtime_id or detail.get("version") != version:
            raise BackfillSkipped("node_version_mismatch")
        if detail.get("state") != node["status"].upper():
            raise BackfillSkipped("node_state_mismatch")
        if not isinstance(detail.get("inputs"), dict):
            raise BackfillSkipped("missing_execution_inputs")
        # Engine 节点详情接口负责脱敏；不读取底层数据库中的原始执行数据。
        return copy.deepcopy(detail["inputs"])


def _check_context(context):
    """只修复空闲且已有结果快照的有效模板。"""
    if context is None or context["is_deleted"]:
        raise BackfillSkipped("context_deleted")
    if context["status"] != "idle" or context["active_task_id"] or context["active_debug_snapshot"]:
        raise BackfillSkipped("context_active")
    snapshot = context["debug_snapshot"]
    if not snapshot:
        raise BackfillSkipped("snapshot_missing_or_reset")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("nodes"), list):
        raise BackfillSkipped("invalid_snapshot")
    if not Template.objects.filter(id=context["template_id"], space_id=context["space_id"], is_deleted=False).exists():
        raise BackfillSkipped("template_unavailable")


def repair_snapshot_inputs(context_id, apply=False):
    """仅补空输入；整条预检成功后加锁比较快照，保留其余字段和当前节点状态。"""
    try:
        context = DebugContext.objects.filter(pk=context_id).values().first()
        _check_context(context)
        snapshot = copy.deepcopy(context["debug_snapshot"])
        candidates = []
        for node in snapshot["nodes"]:
            if not isinstance(node, dict):
                raise BackfillSkipped("invalid_snapshot")
            if (
                node.get("node_type") in ("ServiceActivity", "SubProcess")
                and node.get("status") in ("finished", "failed")
                and node.get("inputs") == {}
                and node.get("log_ref")
            ):
                candidates.append(node)
        if not candidates:
            raise BackfillSkipped("no_missing_inputs")
        reader = SnapshotInputReader(context)
        repaired = 0
        for node in candidates:
            inputs = reader.read(node)
            if inputs:
                node["inputs"] = inputs
                repaired += 1
        if not repaired:
            raise BackfillSkipped("no_execution_inputs")
        if apply:
            with transaction.atomic():
                current = DebugContext.objects.select_for_update().filter(pk=context_id).values().first()
                if current != context:
                    raise BackfillSkipped("concurrent_change")
                _check_context(current)
                DebugContext.objects.filter(pk=context_id).update(debug_snapshot=snapshot)
        return {"outcome": "applied" if apply else "ready", "nodes": repaired}
    except BackfillSkipped as exc:
        return {"outcome": "skipped", "reason": str(exc)}
    except HistoryUnavailable as exc:
        return {"outcome": "error", "reason": str(exc)}
