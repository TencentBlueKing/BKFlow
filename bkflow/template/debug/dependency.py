"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import copy
import hashlib
import json
from typing import Dict, Set

from pipeline.core.data.expression import ConstantTemplate

from bkflow.pipeline_web.parser.format import classify_constants
from bkflow.template.utils import _system_constants_to_mako_str


def _hash_obj(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def compute_node_config_hash(activity: dict) -> str:
    """节点配置指纹：仅取影响执行的字段，忽略坐标/备注。"""
    payload = {
        "type": activity.get("type"),
        "component": activity.get("component", {}),
        "optional": activity.get("optional"),
    }
    if activity.get("type") == "SubCanvas":
        payload["loop_config"] = activity.get("loop_config", {})
        pipeline = activity.get("pipeline") or {}
        payload["pipeline"] = compute_tree_fingerprint(pipeline)
        payload["pipeline_outputs"] = pipeline.get("outputs", [])
    return _hash_obj(payload)


def _extract_referenced_var_keys(value) -> Set[str]:
    """从单个字段值中提取其引用的全局变量 key（形如 ``${var}``）。

    复用 ``ConstantTemplate`` 的引用解析能力：会递归 list/dict 并解析 mako 表达式
    （如 ``${var | length}``），返回的是裸变量名，这里统一包装回 ``${var}`` 形式。
    参考 ``bkflow/template/utils.py`` 的做法，先把内置 ``_system.`` 变量转义，避免 mako
    解析异常导致整字段引用丢失；并整体兜底 try/except，确保单个异常值不影响依赖图构建。
    """
    try:
        safe_value = _system_constants_to_mako_str(copy.deepcopy(value))
        return {"${%s}" % ref for ref in ConstantTemplate(safe_value).get_reference()}
    except Exception:
        return set()


def get_activity_referenced_var_keys(activity: dict) -> Set[str]:
    """提取节点执行时会消费的父画布变量。"""
    referenced_vars: Set[str] = set()
    component_data = activity.get("component", {}).get("data", {})
    for field in component_data.values():
        value = field.get("value") if isinstance(field, dict) else field
        referenced_vars |= _extract_referenced_var_keys(value)

    if activity.get("type") != "SubCanvas":
        return referenced_vars

    loop_params = activity.get("loop_config", {}).get("loop_params", {})
    referenced_vars |= _extract_referenced_var_keys(loop_params)
    inner_constants = (activity.get("pipeline") or {}).get("constants", {})
    for constant in inner_constants.values():
        if constant.get("show_type") != "show" or not constant.get("need_render", True):
            continue
        referenced_vars |= _extract_referenced_var_keys(constant.get("value"))
    return referenced_vars


def compute_tree_fingerprint(pipeline_tree: dict) -> dict:
    """各节点 config_hash + 拓扑/连线/常量/网关指纹"""
    activities = pipeline_tree.get("activities", {})
    flows = {
        fid: {"source": f.get("source"), "target": f.get("target")} for fid, f in pipeline_tree.get("flows", {}).items()
    }
    gateways = {gid: g.get("conditions", {}) for gid, g in pipeline_tree.get("gateways", {}).items()}
    constants = {
        key: {"source_type": c.get("source_type"), "source_info": c.get("source_info"), "value": c.get("value")}
        for key, c in pipeline_tree.get("constants", {}).items()
    }
    return {
        "nodes": {nid: compute_node_config_hash(act) for nid, act in activities.items()},
        "flows": _hash_obj(flows),
        "gateways": _hash_obj(gateways),
        "constants": _hash_obj(constants),
    }


def build_dependency_graph(pipeline_tree: dict) -> dict:
    """构建控制流图与数据流图（均为 producer_node -> set(consumer_node)）"""
    activities = pipeline_tree.get("activities", {})
    gateways = pipeline_tree.get("gateways", {})
    flows = pipeline_tree.get("flows", {})
    node_ids = set(activities.keys()) | set(gateways.keys())

    control: Dict[str, Set[str]] = {nid: set() for nid in node_ids}
    for flow in flows.values():
        src, tgt = flow.get("source"), flow.get("target")
        if src in control and tgt in node_ids:
            control[src].add(tgt)

    # 数据流：A 产出 ${var}（component_outputs.source_act），B 的 component.data 引用 ${var}
    # classify_constants 会就地写入 is_param，深拷贝避免污染传入的共享树
    classified = classify_constants(copy.deepcopy(pipeline_tree.get("constants", {})), is_subprocess=False)
    var_producer = {}  # ${var} -> producer_node_id
    for var_key, info in classified["data_inputs"].items():
        if info.get("type") == "splice" and info.get("source_act"):
            var_producer[var_key] = info["source_act"]

    data: Dict[str, Set[str]] = {nid: set() for nid in node_ids}
    for nid, act in activities.items():
        referenced_vars = get_activity_referenced_var_keys(act)
        producers = {var_producer[var_key] for var_key in referenced_vars if var_key in var_producer}
        for producer in producers:
            if producer in data and producer != nid:
                data[producer].add(nid)

    return {"control": control, "data": data}


def closure(seeds: Set[str], graph: dict) -> Set[str]:
    """沿控制流 ∪ 数据流并集做下游可达闭包（含种子自身）"""
    control, data = graph["control"], graph["data"]
    visited, stack = set(), list(seeds)
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for nxt in control.get(node, set()) | data.get(node, set()):
            if nxt not in visited:
                stack.append(nxt)
    return visited
