"""从仍可核实的历史任务回填旧调试结果；不读取当前草稿推断历史。"""

import copy

from django.db import transaction

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.template.debug.snapshot import debug_nodes, node_result, ordered_node_ids
from bkflow.template.models import DebugContext, DebugNodeState, Template

RESULT_STATUSES = {"finished", "failed", "revoked"}


class BackfillSkipped(Exception):
    """历史依据不足或记录已经变化，保留原数据。"""


class HistoryUnavailable(Exception):
    """历史接口不可用，记录错误后允许重试。"""


def _read_history(method, *args, **kwargs):
    """只接收成功响应；不将可能包含凭证的响应或异常写入报告。"""
    try:
        response = method(*args, **kwargs)
    except Exception as exc:
        raise HistoryUnavailable("engine_request_failed") from exc
    if not isinstance(response, dict) or not response.get("result"):
        raise HistoryUnavailable("engine_request_failed")
    data = response.get("data")
    if not isinstance(data, dict):
        raise BackfillSkipped("invalid_history")
    return data


class HistoricalTask:
    """一个历史任务的节点和顺序，模板 ID 与运行时 ID 分开使用。"""

    def __init__(self, client, task_id, context):
        self.client = client
        self.task_id = task_id
        self.detail = _read_history(client.get_task_detail, task_id)
        if (
            self.detail.get("id") != task_id
            or self.detail.get("space_id") != context["space_id"]
            or self.detail.get("template_id") != context["template_id"]
            or self.detail.get("create_method") != "DEBUG"
            or not self.detail.get("is_started")
            or self.detail.get("is_deleted")
            or self.detail.get("is_expired")
        ):
            raise BackfillSkipped("task_identity_mismatch")
        tree = self.detail.get("pipeline_tree")
        if not isinstance(tree, dict) or any(
            not isinstance(tree.get(key), dict)
            for key in ("activities", "gateways", "flows", "start_event", "end_event")
        ):
            raise BackfillSkipped("missing_pipeline")
        self.is_step = tree.get("name") == "debug_single_node"
        self.runtime_nodes = debug_nodes(tree)
        self.runtime_ids = {}
        for runtime_id, node in self.runtime_nodes.items():
            if not isinstance(node, dict) or node.get("id") != runtime_id:
                raise BackfillSkipped("invalid_node_mapping")
            template_id = node.get("template_node_id")
            if (
                not isinstance(template_id, str)
                or not template_id
                or template_id in self.runtime_ids
                or template_id in ("start_event", "end_event")
            ):
                raise BackfillSkipped("invalid_node_mapping")
            self.runtime_ids[template_id] = runtime_id
        if self.is_step and len(self.runtime_ids) != 1:
            raise BackfillSkipped("invalid_pipeline")
        self.activities = set(tree["activities"])
        self.nodes = {}
        # 排序必须用模板节点 ID，否则运行时随机 ID 会改变并行分支的展示顺序。
        mapping = {runtime_id: template_id for template_id, runtime_id in self.runtime_ids.items()}
        for key in ("start_event", "end_event"):
            event_id = (tree.get(key) or {}).get("id")
            if not isinstance(event_id, str) or not event_id or event_id in mapping:
                raise BackfillSkipped("invalid_pipeline")
            mapping[event_id] = key
        edges = []
        successors = {node_id: set() for node_id in mapping.values()}
        for flow in tree.get("flows", {}).values():
            if (
                not isinstance(flow, dict)
                or not isinstance(flow.get("source"), str)
                or not isinstance(flow.get("target"), str)
                or flow["source"] not in mapping
                or flow["target"] not in mapping
            ):
                raise BackfillSkipped("invalid_pipeline")
            edges.append((mapping[flow["source"]], mapping[flow["target"]]))
            successors[mapping[flow["source"]]].add(mapping[flow["target"]])
        pending, reachable = ["start_event"], set()
        while pending:
            node_id = pending.pop()
            if node_id not in reachable:
                reachable.add(node_id)
                pending.extend(successors[node_id] - reachable)
        if reachable != set(successors):
            raise BackfillSkipped("invalid_pipeline")
        self.topology = (sorted(self.runtime_ids), sorted(edges))
        self.order = ordered_node_ids(
            {
                "activities": dict.fromkeys(self.runtime_ids, {}),
                "start_event": {"id": "start_event"},
                "flows": {str(i): {"source": src, "target": dst} for i, (src, dst) in enumerate(edges)},
            }
        )
        mock = _read_history(client.get_task_mock_data, task_id)
        mock_data = mock.get("data")
        if (
            mock.get("taskflow_id") != task_id
            or not isinstance(mock_data, dict)
            or not isinstance(mock_data.get("nodes"), list)
            or any(not isinstance(nid, str) or nid not in self.runtime_nodes for nid in mock_data["nodes"])
        ):
            raise BackfillSkipped("missing_mock_history")
        self.mock_nodes = set(mock["data"]["nodes"])

    def node(self, node_id):
        """活动从原始任务快照取名称和类型，避免子画布执行转换改变类型。"""
        if node_id not in self.nodes:
            runtime_id = self.runtime_ids[node_id]
            node = self.runtime_nodes[runtime_id]
            if runtime_id in self.activities:
                node = _read_history(self.client.get_node_snapshot_config, self.task_id, data={"node_id": runtime_id})
                if node.get("id") != node_id:
                    raise BackfillSkipped("invalid_node_mapping")
            if not isinstance(node.get("name"), str) or not isinstance(node.get("type"), str):
                raise BackfillSkipped("missing_node_metadata")
            self.nodes[node_id] = node
        return self.nodes[node_id]


def build_legacy_snapshot(context, states):
    """全局历史提供顺序，各节点自己的任务提供名称；无法完整匹配时整条跳过。"""
    results = {state.node_id: state for state in states if state.status in RESULT_STATUSES}
    if not results:
        raise BackfillSkipped("no_results")
    if any(state.status not in RESULT_STATUSES | {"not_run"} for state in states):
        raise BackfillSkipped("unfinished_nodes")
    refs = {}
    for node_id, state in results.items():
        ref = state.log_ref or {}
        if not isinstance(ref, dict):
            raise BackfillSkipped("missing_log_ref")
        task_id = ref.get("instance_id")
        if type(task_id) is not int or task_id <= 0 or not isinstance(ref.get("node_id"), str):
            raise BackfillSkipped("missing_log_ref")
        refs[node_id] = task_id
    task_ids = set(refs.values())
    if context["last_run_type"] == "global" and context["last_task_id"]:
        task_ids.add(context["last_task_id"])
    try:
        client = TaskComponentClient(space_id=context["space_id"])
    except Exception as exc:
        raise HistoryUnavailable("engine_client_unavailable") from exc
    tasks = {task_id: HistoricalTask(client, task_id, context) for task_id in sorted(task_ids)}
    for node_id, task_id in refs.items():
        if tasks[task_id].runtime_ids.get(node_id) != results[node_id].log_ref["node_id"]:
            raise BackfillSkipped("invalid_node_mapping")
    full_tasks = [task for task in tasks.values() if not task.is_step]
    states_by_id = {state.node_id: state for state in states}
    if full_tasks:
        anchor = full_tasks[-1]
        if any(task.topology != anchor.topology for task in full_tasks):
            raise BackfillSkipped("ambiguous_order")
        if not set(results).issubset(anchor.runtime_ids):
            raise BackfillSkipped("ambiguous_order")
        if not set(anchor.runtime_ids).issubset(states_by_id):
            raise BackfillSkipped("missing_node_state")
        order = anchor.order
    elif len(results) == 1:
        order = list(results)
        anchor = tasks[refs[order[0]]]
    else:
        raise BackfillSkipped("ambiguous_order")
    nodes = []
    for node_id in order:
        state = states_by_id[node_id]
        task = tasks[refs[node_id]] if node_id in refs else anchor
        node = node_result(state, task.node(node_id), task.detail.get("executor") or "")
        node["execution_mode"] = "mock" if task.runtime_ids[node_id] in task.mock_nodes else "real"
        # 引擎名称已经清洗/截断，不能据此重建原始草稿的名称比较基准；配置哈希同样沿用旧值。
        nodes.append(node)
    return {"nodes": nodes}


def _check_context(context):
    """只回填 SQL NULL，显式重置留下的空对象也必须跳过。"""
    if context["debug_snapshot"] is not None:
        raise BackfillSkipped("snapshot_exists_or_reset")
    if context["is_deleted"]:
        raise BackfillSkipped("context_deleted")
    if context["status"] != "idle" or context["active_task_id"] or context["active_debug_snapshot"]:
        raise BackfillSkipped("context_active")
    if not Template.objects.filter(id=context["template_id"], space_id=context["space_id"], is_deleted=False).exists():
        raise BackfillSkipped("template_unavailable")


def backfill_context(context_id, apply=False):
    """远程读取在事务外；写入时锁定并比较上下文和全部节点，避免覆盖新调试或重置。"""
    try:
        context = DebugContext.objects.filter(pk=context_id).values().first()
        if context is None:
            raise BackfillSkipped("context_deleted")
        _check_context(context)
        if not DebugContext.objects.filter(pk=context_id, debug_snapshot__isnull=True).exists():
            raise BackfillSkipped("snapshot_exists_or_reset")
        rows = list(DebugNodeState.objects.filter(debug_context_id=context_id).order_by("id").values())
        states = [DebugNodeState(**copy.deepcopy(row)) for row in rows]
        snapshot = build_legacy_snapshot(context, states)
        if apply:
            with transaction.atomic():
                current = DebugContext.objects.select_for_update().filter(pk=context_id).values().first()
                current_rows = list(
                    DebugNodeState.objects.select_for_update()
                    .filter(debug_context_id=context_id)
                    .order_by("id")
                    .values()
                )
                if current != context or current_rows != rows:
                    raise BackfillSkipped("concurrent_change")
                _check_context(current)
                updated = DebugContext.objects.filter(pk=context_id, debug_snapshot__isnull=True).update(
                    debug_snapshot=snapshot
                )
                if not updated:
                    raise BackfillSkipped("concurrent_change")
        return {"outcome": "applied" if apply else "ready", "nodes": len(snapshot["nodes"])}
    except BackfillSkipped as exc:
        return {"outcome": "skipped", "reason": str(exc)}
    except HistoryUnavailable as exc:
        return {"outcome": "error", "reason": str(exc)}
