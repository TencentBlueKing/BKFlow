"""条件网关调试求值。"""

import copy
from typing import Any, Dict, List

from bamboo_engine.template import Template
from bamboo_engine.utils.boolrule import BoolRule
from bamboo_engine.utils.constants import ExclusiveGatewayStrategy
from bamboo_engine.utils.string import transform_escape_char
from bkflow_feel.api import parse_expression

from bkflow.utils.mako import parse_mako_expression

DEBUGGABLE_GATEWAY_TYPES = {"ExclusiveGateway", "ConditionalParallelGateway"}


class GatewayEvaluationError(Exception):
    """网关条件无法完成求值。"""

    def __init__(self, message: str, condition_results: List[dict] = None):
        super().__init__(message)
        self.condition_results = condition_results or []


def _evaluate_expression(expression: str, context: dict, extra_info: dict) -> bool:
    parse_lang = extra_info.get("parse_lang")
    if parse_lang == "FEEL":
        return parse_expression(expression=expression)
    if parse_lang == "MAKO":
        return parse_mako_expression(expression=expression, context=context)
    return BoolRule(expression).test()


def _deformat_key(key: str) -> str:
    if isinstance(key, str) and key.startswith("${") and key.endswith("}"):
        return key[2:-1]
    return key


def _has_value(values: dict, key: str) -> bool:
    return key in values or _deformat_key(key) in values


def _get_value(values: dict, key: str, default: Any = None) -> Any:
    if key in values:
        return values[key]
    return values.get(_deformat_key(key), default)


def _build_hydrated_context(pipeline_tree: dict, values: dict) -> Dict[str, Any]:
    constants = pipeline_tree.get("constants", {})
    context = {}
    overridden_keys = set()
    for key, constant in constants.items():
        context[_deformat_key(key)] = _get_value(values, key, constant.get("value"))
    for key, value in values.items():
        raw_key = _deformat_key(key)
        context[raw_key] = value
        overridden_keys.add(raw_key)

    # Context.hydrate 会递归展开常量引用；这里用有界迭代复现该行为，并保持显式调试值优先。
    for _ in range(len(constants)):
        changed = False
        for key, constant in constants.items():
            raw_key = _deformat_key(key)
            if raw_key in overridden_keys:
                continue
            rendered = Template(copy.deepcopy(constant.get("value"))).render(context)
            if rendered != context.get(raw_key):
                context[raw_key] = rendered
                changed = True
        if not changed:
            break
    return {key: transform_escape_char(value) for key, value in context.items()}


def _source_node_id(constant: dict):
    source_info = constant.get("source_info") or {}
    return next(iter(source_info), None) if isinstance(source_info, dict) else None


def gateway_missing_vars(pipeline_tree: dict, gateway_id: str, values: dict) -> List[dict]:
    """返回网关条件依赖但尚未由前序节点产出的变量。"""

    gateway = pipeline_tree.get("gateways", {}).get(gateway_id) or {}
    references = set()
    for condition in gateway.get("conditions", {}).values():
        references.update(Template(condition.get("evaluate", "")).get_reference())

    constants = pipeline_tree.get("constants", {})
    missing = {}
    visited = set()
    pending = list(references)
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        constant = constants.get(key) or {}
        if _has_value(values, key):
            continue
        if constant.get("source_type") == "component_outputs":
            missing[key] = {"key": key, "source_node_id": _source_node_id(constant)}
            continue
        pending.extend(Template(copy.deepcopy(constant.get("value"))).get_reference())
    return [missing[key] for key in sorted(missing)]


def _is_first_match_strategy(gateway: dict) -> bool:
    strategy = (gateway.get("extra_info") or {}).get("strategy")
    return strategy in {
        ExclusiveGatewayStrategy.FIRST.name,
        ExclusiveGatewayStrategy.FIRST.value,
        str(ExclusiveGatewayStrategy.FIRST.value),
    }


def evaluate_gateway(pipeline_tree: dict, gateway_id: str, values: dict) -> dict:
    """按引擎条件语义计算网关命中的连线，不执行后续节点。"""

    gateway = pipeline_tree.get("gateways", {}).get(gateway_id)
    if not gateway or gateway.get("type") not in DEBUGGABLE_GATEWAY_TYPES:
        raise GatewayEvaluationError("节点不是可调试的条件网关")

    missing_vars = gateway_missing_vars(pipeline_tree, gateway_id, values)
    if missing_vars:
        keys = ", ".join(item["key"] for item in missing_vars)
        raise GatewayEvaluationError("网关条件依赖未满足：{}".format(keys))

    context = _build_hydrated_context(pipeline_tree, values)
    condition_results = []
    selected_flow_ids = []
    first_match = gateway.get("type") == "ExclusiveGateway" and _is_first_match_strategy(gateway)

    for flow_id, condition in gateway.get("conditions", {}).items():
        expression = condition.get("evaluate")
        if not isinstance(expression, str) or not expression.strip():
            raise GatewayEvaluationError("分支条件解析失败：条件表达式为空", condition_results)
        try:
            resolved_expression = Template(expression).render(context)
            matched = bool(_evaluate_expression(resolved_expression, context, gateway.get("extra_info") or {}))
        except Exception as error:
            raise GatewayEvaluationError("分支条件解析失败：{}".format(error), condition_results) from error

        condition_results.append(
            {
                "flow_id": flow_id,
                "name": condition.get("name", ""),
                "expression": expression,
                "resolved_expression": resolved_expression,
                "matched": matched,
            }
        )
        if matched:
            selected_flow_ids.append(flow_id)
            if first_match:
                break

    default_flow_id = (gateway.get("default_condition") or {}).get("flow_id")
    if not selected_flow_ids:
        if not default_flow_id:
            raise GatewayEvaluationError("所有分支条件均不满足，且未配置默认分支", condition_results)
        selected_flow_ids.append(default_flow_id)

    if gateway.get("type") == "ExclusiveGateway" and len(selected_flow_ids) > 1:
        raise GatewayEvaluationError("多个分支条件同时满足", condition_results)

    return {
        "selected_flow_ids": selected_flow_ids,
        "condition_results": condition_results,
    }
