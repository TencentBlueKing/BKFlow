"""调试结果的独立快照；不随草稿增删或重排。"""

import copy
import heapq

from bkflow.template.debug.dependency import DEBUG_CONFIG_HASH_PREFIX
from bkflow.utils.handlers import mask_sensitive_data_for_display

EXECUTED_CONFIG_PREFIX = "run:"


def executed_config_hash(config_hash):
    """在已有指纹中记录实际执行依据，重置状态时不丢失；不改变哈希算法版本。"""
    config_hash = config_hash or ""
    if config_hash.startswith(EXECUTED_CONFIG_PREFIX):
        return config_hash
    return EXECUTED_CONFIG_PREFIX + config_hash


def has_execution_baseline(config_hash, status, duration_ms):
    """兼容旧完成记录；旧版 not_run 指纹可能仅来自初始化，不能证明已调试。"""
    return (
        bool(config_hash and config_hash.startswith(EXECUTED_CONFIG_PREFIX))
        or status == "finished"
        # 真实执行失败会记录耗时；单步启动失败也会写 failed，但耗时为 None。
        or (status == "failed" and duration_ms is not None)
    )


def debug_nodes(tree):
    """返回当前层的活动和网关，子画布作为一个节点展示。"""
    return {**tree.get("activities", {}), **tree.get("gateways", {})}


def ordered_node_ids(tree):
    """按控制流稳定排序；忽略 DFS 回边，使循环节点只出现一次。

    从开始节点遍历，分支按节点 ID 稳定展开；拓扑排序保证汇聚在所有前驱之后。
    脱离主流程的节点最后处理，不依赖 JSON 对象键顺序或画布坐标。
    """
    nodes = debug_nodes(tree)
    graph = {node_id: set() for node_id in nodes}
    for flow in tree.get("flows", {}).values():
        source, target = flow.get("source"), flow.get("target")
        if source and target:
            graph.setdefault(source, set()).add(target)
            graph.setdefault(target, set())
    start = (tree.get("start_event") or {}).get("id")
    roots = ([start] if start in graph else []) + sorted(graph)
    colors, rank, edges = {}, {}, {node_id: set() for node_id in graph}
    for root in roots:
        if root in colors:
            continue
        colors[root] = 1
        rank[root] = len(rank)
        stack = [(root, iter(sorted(graph[root])))]
        while stack:
            source, children = stack[-1]
            target = next(children, None)
            if target is None:
                colors[source] = 2
                stack.pop()
                continue
            if colors.get(target) == 1:
                continue
            edges[source].add(target)
            if target not in colors:
                colors[target] = 1
                rank[target] = len(rank)
                stack.append((target, iter(sorted(graph[target]))))
    incoming = dict.fromkeys(graph, 0)
    for children in edges.values():
        for target in children:
            incoming[target] += 1
    ready = [(rank[node_id], node_id) for node_id, count in incoming.items() if not count]
    heapq.heapify(ready)
    ordered = []
    while ready:
        _, source = heapq.heappop(ready)
        if source in nodes:
            ordered.append(source)
        for target in edges[source]:
            incoming[target] -= 1
            if not incoming[target]:
                heapq.heappush(ready, (rank[target], target))
    return ordered


def config_changed(config_hash, node_name, current_node, current_hash, status, duration_ms):
    """只使用实际执行过的基准比较配置，未调试新节点不产生失效提示。"""
    if not has_execution_baseline(config_hash, status, duration_ms):
        return False
    if config_hash and config_hash.startswith(EXECUTED_CONFIG_PREFIX):
        config_hash = config_hash[len(EXECUTED_CONFIG_PREFIX) :]
    if current_node is None:
        return bool(config_hash)
    hash_changed = (
        isinstance(config_hash, str)
        and config_hash.startswith(DEBUG_CONFIG_HASH_PREFIX)
        and isinstance(current_hash, str)
        and current_hash.startswith(DEBUG_CONFIG_HASH_PREFIX)
        and config_hash != current_hash
    )
    return hash_changed or (node_name is not None and node_name != current_node.get("name", ""))


def configured_inputs(node):
    """提取调试时填写的参数值；不解析变量，不用执行结果或当前草稿补齐。"""
    node_type = node.get("type")
    if node_type == "ServiceActivity":
        component = node.get("component")
        data = component.get("data") if isinstance(component, dict) else None
    elif node_type in ("SubCanvas", "SubProcess"):
        pipeline = node.get("pipeline")
        constants = pipeline.get("constants") if isinstance(pipeline, dict) else None
        if not isinstance(constants, dict):
            return None
        data = {
            key: field
            for key, field in constants.items()
            if isinstance(field, dict) and field.get("show_type") == "show"
        }
    elif node_type in ("ExclusiveGateway", "ConditionalParallelGateway", "ParallelGateway", "ConvergeGateway"):
        return {}
    else:
        return None
    if not isinstance(data, dict):
        return None
    values = {key: field.get("value") if isinstance(field, dict) else field for key, field in data.items()}
    return mask_sensitive_data_for_display(values)


def node_result(state, node, operator):
    """冻结名称、运行结果和比较基准，不混入当前 Mock 预设或可执行性。"""
    return copy.deepcopy(
        {
            "node_id": state.node_id,
            "node_name": node.get("name", ""),
            "node_type": node.get("type", state.node_type),
            "execution_mode": state.execution_mode,
            "status": state.status,
            "waiting_reason": state.waiting_reason or None,
            "inputs": state.inputs,
            "configured_inputs": configured_inputs(node),
            "outputs": state.outputs,
            "duration_ms": state.duration_ms,
            "error_detail": state.error_detail or None,
            "log_ref": state.log_ref or None,
            "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
            "operator": operator,
            "_config_hash": (
                executed_config_hash(state.debug_config_hash)
                if has_execution_baseline(state.debug_config_hash, state.status, state.duration_ms)
                else None
            ),
            "_node_name": state.debug_node_name,
        }
    )


def merge_step_result(results, result, order):
    """单步只替换目标；新节点按本次流程插入，其余历史节点保持相对顺序。"""
    results = copy.deepcopy(results)
    node_id = result["node_id"]
    for index, previous in enumerate(results):
        if previous["node_id"] == node_id:
            results[index] = result
            return results
    following = set(order[order.index(node_id) + 1 :]) if node_id in order else set()
    index = next((i for i, previous in enumerate(results) if previous["node_id"] in following), len(results))
    results.insert(index, result)
    return results
