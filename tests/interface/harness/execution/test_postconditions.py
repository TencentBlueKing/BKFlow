"""Closed and bounded P3 postcondition DSL contracts."""

import pytest

from bkflow.harness.services.execution.postconditions import (
    NodeOutputEvidence,
    PostconditionEvaluator,
    PostconditionSpecError,
    normalize_postcondition_spec,
)


def spec(*predicates):
    return {
        "version": "harness-postconditions-p3-v1",
        "operator": "all",
        "predicates": list(predicates),
    }


def test_all_predicates_pass_with_canonical_json_equality():
    evaluator = PostconditionEvaluator(
        spec(
            {"type": "TASK_STATE_IN", "allowed_states": ["FINISHED"]},
            {"type": "OUTPUT_EXISTS", "node_id": "A", "output_key": "result"},
            {
                "type": "OUTPUT_EQUALS",
                "node_id": "A",
                "output_key": "result",
                "expected_json": {"b": [2, 3], "a": 1},
            },
        )
    )

    result = evaluator.evaluate(
        "FINISHED",
        {"A": NodeOutputEvidence.available({"result": {"a": 1, "b": [2, 3]}})},
    )

    assert result.status == "PASSED"
    assert [item["status"] for item in result.as_report()["predicates"]] == ["PASSED"] * 3
    assert evaluator.required_outputs == (("A", "result"),)


def test_json_boolean_is_not_equal_to_integer():
    evaluator = PostconditionEvaluator(
        spec({"type": "OUTPUT_EQUALS", "node_id": "A", "output_key": "result", "expected_json": True})
    )

    result = evaluator.evaluate("FINISHED", {"A": NodeOutputEvidence.available({"result": 1})})

    assert result.status == "FAILED"
    assert result.as_report()["predicates"][0] == {
        "index": 0,
        "type": "OUTPUT_EQUALS",
        "status": "FAILED",
        "reason": "output_mismatch",
    }


def test_nonterminal_output_is_pending_and_missing_finished_output_fails():
    evaluator = PostconditionEvaluator(spec({"type": "OUTPUT_EXISTS", "node_id": "A", "output_key": "result"}))

    assert evaluator.evaluate("RUNNING").status == "PENDING"
    assert evaluator.evaluate("FINISHED", {"A": NodeOutputEvidence.available({})}).status == "FAILED"


def test_unavailable_output_and_recognized_webhook_predicate_fail_closed():
    output = PostconditionEvaluator(
        spec({"type": "OUTPUT_EQUALS", "node_id": "A", "output_key": "result", "expected_json": "ok"})
    ).evaluate("FINISHED", {"A": NodeOutputEvidence.unavailable("node_detail_unavailable")})
    webhook = PostconditionEvaluator(
        spec(
            {
                "type": "WEBHOOK_DELIVERED",
                "event_type": "task_finished",
                "correlation_id": "harness-correlation-1",
            }
        )
    ).evaluate("FINISHED")

    assert output.status == "UNAVAILABLE"
    assert output.as_report()["predicates"][0]["reason"] == "node_detail_unavailable"
    assert webhook.status == "UNAVAILABLE"
    assert webhook.as_report()["predicates"][0]["reason"] == "webhook_correlation_unavailable"


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        {"version": "harness-postconditions-p3-v1", "operator": "all", "predicates": [], "extra": True},
        spec({"type": "UNKNOWN", "script": "return true"}),
        spec({"type": "OUTPUT_EXISTS", "node_id": "A", "output_key": "result", "script": "x"}),
        spec({"type": "TASK_STATE_IN", "allowed_states": ["FINISHED"], "expression": "x"}),
        spec(*({"type": "TASK_STATE_IN", "allowed_states": ["FINISHED"]} for _ in range(33))),
        spec({"type": "OUTPUT_EQUALS", "node_id": "A", "output_key": "result", "expected_json": float("nan")}),
        spec({"type": "WEBHOOK_DELIVERED", "event_type": "task", "correlation_id": "Bearer secret"}),
    ],
)
def test_schema_is_closed_versioned_and_bounded(invalid):
    with pytest.raises(PostconditionSpecError):
        normalize_postcondition_spec(invalid)
