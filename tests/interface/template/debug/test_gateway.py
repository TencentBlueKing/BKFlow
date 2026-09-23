"""条件网关单步求值测试。"""

import copy

import pytest

from bkflow.template.debug.gateway import (
    GatewayEvaluationError,
    evaluate_gateway,
    gateway_missing_vars,
)


def _constant(key, value, source_type="custom", source_info=None):
    return {
        "key": key,
        "name": key,
        "value": value,
        "source_type": source_type,
        "source_info": source_info or {},
        "source_tag": "",
        "show_type": "hide",
    }


def _gateway_tree(gateway_type="ExclusiveGateway"):
    return {
        "activities": {
            "producer": {
                "id": "producer",
                "type": "ServiceActivity",
                "component": {"code": "test", "data": {}},
            },
            "positive": {"id": "positive", "type": "ServiceActivity"},
            "negative": {"id": "negative", "type": "ServiceActivity"},
            "fallback": {"id": "fallback", "type": "ServiceActivity"},
        },
        "gateways": {
            "gateway": {
                "id": "gateway",
                "type": gateway_type,
                "incoming": "flow_in",
                "outgoing": ["flow_positive", "flow_negative", "flow_default"],
                "conditions": {
                    "flow_positive": {"name": "positive", "evaluate": "${count} > 0"},
                    "flow_negative": {"name": "negative", "evaluate": "${count} < 0"},
                },
                "default_condition": {"name": "default", "flow_id": "flow_default"},
                "extra_info": {"parse_lang": "boolrule"},
            }
        },
        "flows": {
            "flow_positive": {"id": "flow_positive", "source": "gateway", "target": "positive"},
            "flow_negative": {"id": "flow_negative", "source": "gateway", "target": "negative"},
            "flow_default": {"id": "flow_default", "source": "gateway", "target": "fallback"},
        },
        "constants": {
            "${count}": _constant("${count}", 0),
            "${produced}": _constant(
                "${produced}",
                "",
                source_type="component_outputs",
                source_info={"producer": ["value"]},
            ),
        },
    }


def test_evaluate_exclusive_gateway_selects_matching_flow():
    result = evaluate_gateway(_gateway_tree(), "gateway", {"${count}": 1})

    assert result["selected_flow_ids"] == ["flow_positive"]
    assert result["condition_results"] == [
        {
            "flow_id": "flow_positive",
            "name": "positive",
            "expression": "${count} > 0",
            "resolved_expression": "1 > 0",
            "matched": True,
        },
        {
            "flow_id": "flow_negative",
            "name": "negative",
            "expression": "${count} < 0",
            "resolved_expression": "1 < 0",
            "matched": False,
        },
    ]


def test_evaluate_exclusive_gateway_uses_default_flow():
    result = evaluate_gateway(_gateway_tree(), "gateway", {"${count}": 0})

    assert result["selected_flow_ids"] == ["flow_default"]
    assert [item["matched"] for item in result["condition_results"]] == [False, False]


def test_evaluate_exclusive_gateway_rejects_multiple_matches():
    tree = _gateway_tree()
    tree["gateways"]["gateway"]["conditions"] = {
        "flow_positive": {"name": "first", "evaluate": "1 == 1"},
        "flow_negative": {"name": "second", "evaluate": "2 == 2"},
    }

    with pytest.raises(GatewayEvaluationError, match="多个分支条件同时满足"):
        evaluate_gateway(tree, "gateway", {})


def test_evaluate_conditional_parallel_gateway_selects_all_matching_flows():
    tree = _gateway_tree("ConditionalParallelGateway")
    tree["gateways"]["gateway"]["conditions"] = {
        "flow_positive": {"name": "first", "evaluate": "${count} >= 1"},
        "flow_negative": {"name": "second", "evaluate": "${count} <= 1"},
    }

    result = evaluate_gateway(tree, "gateway", {"${count}": 1})

    assert result["selected_flow_ids"] == ["flow_positive", "flow_negative"]
    assert [item["matched"] for item in result["condition_results"]] == [True, True]


def test_gateway_missing_vars_reports_unavailable_produced_constant():
    tree = _gateway_tree()
    tree["gateways"]["gateway"]["conditions"]["flow_positive"]["evaluate"] = "${produced} == 1"

    assert gateway_missing_vars(tree, "gateway", {}) == [{"key": "${produced}", "source_node_id": "producer"}]
    assert gateway_missing_vars(tree, "gateway", {"${produced}": 1}) == []


def test_gateway_missing_vars_follows_constant_references():
    tree = _gateway_tree()
    tree["constants"]["${alias}"] = _constant("${alias}", "${produced}")
    tree["gateways"]["gateway"]["conditions"]["flow_positive"]["evaluate"] = "${alias} == 1"

    assert gateway_missing_vars(tree, "gateway", {}) == [{"key": "${produced}", "source_node_id": "producer"}]
    assert gateway_missing_vars(tree, "gateway", {"${produced}": 1}) == []


def test_evaluate_gateway_resolves_referenced_constants():
    tree = _gateway_tree()
    tree["constants"]["${alias}"] = _constant("${alias}", "${count}")
    tree["gateways"]["gateway"]["conditions"]["flow_positive"]["evaluate"] = "${alias} > 0"

    result = evaluate_gateway(tree, "gateway", {"${count}": 1})

    assert result["selected_flow_ids"] == ["flow_positive"]
    assert result["condition_results"][0]["resolved_expression"] == "1 > 0"


def test_evaluate_gateway_wraps_invalid_expression():
    tree = copy.deepcopy(_gateway_tree())
    tree["gateways"]["gateway"]["conditions"]["flow_positive"]["evaluate"] = ""

    with pytest.raises(GatewayEvaluationError, match="分支条件解析失败"):
        evaluate_gateway(tree, "gateway", {"${count}": 1})
