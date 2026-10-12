"""Closed, bounded and deterministic P3 postcondition evaluation."""

import json
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType

from bkflow.harness.safety import (
    is_bounded_non_secret_json,
    is_harness_sensitive_key,
    safe_opaque_identifier,
)

POSTCONDITION_VERSION = "harness-postconditions-p3-v1"
MAX_POSTCONDITION_PREDICATES = 32
_TASK_STATES = frozenset({"READY", "RUNNING", "SUSPENDED", "FAILED", "FINISHED", "REVOKED", "CANCELLED"})
_STATUS_PRIORITY = {"PASSED": 0, "PENDING": 1, "UNAVAILABLE": 2, "FAILED": 3}


class PostconditionSpecError(ValueError):
    """The immutable server policy supplied an unsupported DSL value."""


@dataclass(frozen=True)
class NodeOutputEvidence:
    """Internal proof that one bounded node output response was or was not readable."""

    is_available: bool
    outputs: object
    reason: str

    @classmethod
    def available(cls, outputs):
        """Represent one successfully read output mapping."""
        return cls(True, outputs, "available")

    @classmethod
    def unavailable(cls, reason="node_detail_unavailable"):
        """Represent one failed or unsafe output read without downstream detail."""
        return cls(False, None, reason)


@dataclass(frozen=True)
class PostconditionEvaluation:
    """Safe aggregate result that excludes raw and expected output values."""

    status: str
    predicates: tuple

    def as_report(self):
        """Return a bounded JSON-ready summary."""
        return {"status": self.status, "predicates": [dict(item) for item in self.predicates]}


def _valid_identifier(value):
    return safe_opaque_identifier(value) is not None and not is_harness_sensitive_key(value)


def normalize_postcondition_spec(value):
    """Validate and canonicalize the closed P3 DSL supplied by server policy."""
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "operator", "predicates"}
        or value.get("version") != POSTCONDITION_VERSION
        or value.get("operator") != "all"
        or not isinstance(value.get("predicates"), list)
        or not 1 <= len(value["predicates"]) <= MAX_POSTCONDITION_PREDICATES
        or not is_bounded_non_secret_json(value)
    ):
        raise PostconditionSpecError("postcondition spec is invalid")
    normalized = deepcopy(value)
    for predicate in normalized["predicates"]:
        if not isinstance(predicate, dict) or not isinstance(predicate.get("type"), str):
            raise PostconditionSpecError("postcondition predicate is invalid")
        predicate_type = predicate["type"]
        if predicate_type == "TASK_STATE_IN":
            if set(predicate) != {"type", "allowed_states"}:
                raise PostconditionSpecError("task-state predicate is invalid")
            allowed = predicate["allowed_states"]
            if (
                not isinstance(allowed, list)
                or not 1 <= len(allowed) <= 32
                or len(allowed) != len(set(allowed))
                or any(type(item) is not str or item not in _TASK_STATES for item in allowed)
            ):
                raise PostconditionSpecError("task-state predicate is invalid")
            predicate["allowed_states"] = sorted(allowed)
        elif predicate_type in {"OUTPUT_EXISTS", "OUTPUT_EQUALS"}:
            fields = {"type", "node_id", "output_key"}
            if predicate_type == "OUTPUT_EQUALS":
                fields.add("expected_json")
            if (
                set(predicate) != fields
                or not _valid_identifier(predicate.get("node_id"))
                or not _valid_identifier(predicate.get("output_key"))
            ):
                raise PostconditionSpecError("output predicate is invalid")
        elif predicate_type == "WEBHOOK_DELIVERED":
            if (
                set(predicate) != {"type", "event_type", "correlation_id"}
                or not _valid_identifier(predicate.get("event_type"))
                or not _valid_identifier(predicate.get("correlation_id"))
            ):
                raise PostconditionSpecError("webhook predicate is invalid")
        else:
            raise PostconditionSpecError("postcondition predicate type is unsupported")
    return normalized


def _canonical_json(value):
    if not is_bounded_non_secret_json(value):
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class PostconditionEvaluator:
    """Evaluate only the fixed P3 conjunction without scripts or templates."""

    def __init__(self, spec):
        self.spec = MappingProxyType(normalize_postcondition_spec(spec))
        self.required_outputs = tuple(
            sorted(
                {
                    (predicate["node_id"], predicate["output_key"])
                    for predicate in self.spec["predicates"]
                    if predicate["type"] in {"OUTPUT_EXISTS", "OUTPUT_EQUALS"}
                }
            )
        )

    @staticmethod
    def _result(index, predicate_type, status, reason):
        return MappingProxyType(
            {
                "index": index,
                "type": predicate_type,
                "status": status,
                "reason": reason,
            }
        )

    def _evaluate_output(self, index, predicate, task_state, output_evidence):
        if task_state != "FINISHED":
            return self._result(index, predicate["type"], "PENDING", "task_not_finished")
        evidence = (output_evidence or {}).get(predicate["node_id"])
        if not isinstance(evidence, NodeOutputEvidence) or not evidence.is_available:
            reason = evidence.reason if isinstance(evidence, NodeOutputEvidence) else "node_detail_unavailable"
            return self._result(index, predicate["type"], "UNAVAILABLE", reason)
        if not isinstance(evidence.outputs, dict) or not is_bounded_non_secret_json(evidence.outputs):
            return self._result(index, predicate["type"], "UNAVAILABLE", "node_output_unsafe")
        exists = predicate["output_key"] in evidence.outputs
        if predicate["type"] == "OUTPUT_EXISTS":
            return self._result(
                index,
                predicate["type"],
                "PASSED" if exists else "FAILED",
                "output_exists" if exists else "output_missing",
            )
        if not exists:
            return self._result(index, predicate["type"], "FAILED", "output_missing")
        actual = _canonical_json(evidence.outputs[predicate["output_key"]])
        expected = _canonical_json(predicate["expected_json"])
        if actual is None:
            return self._result(index, predicate["type"], "UNAVAILABLE", "node_output_unsafe")
        matches = actual == expected
        return self._result(
            index,
            predicate["type"],
            "PASSED" if matches else "FAILED",
            "output_equal" if matches else "output_mismatch",
        )

    def evaluate(self, task_state, output_evidence=None):
        """Return one safe result; unavailable evidence never becomes success."""
        results = []
        for index, predicate in enumerate(self.spec["predicates"]):
            predicate_type = predicate["type"]
            if predicate_type == "TASK_STATE_IN":
                status = (
                    "PENDING"
                    if task_state is None
                    else ("PASSED" if task_state in predicate["allowed_states"] else "FAILED")
                )
                reason = (
                    "task_state_pending"
                    if task_state is None
                    else ("task_state_allowed" if status == "PASSED" else "task_state_disallowed")
                )
                results.append(self._result(index, predicate_type, status, reason))
            elif predicate_type in {"OUTPUT_EXISTS", "OUTPUT_EQUALS"}:
                results.append(self._evaluate_output(index, predicate, task_state, output_evidence))
            else:
                results.append(self._result(index, predicate_type, "UNAVAILABLE", "webhook_correlation_unavailable"))
        status = max((item["status"] for item in results), key=_STATUS_PRIORITY.__getitem__)
        return PostconditionEvaluation(status=status, predicates=tuple(results))


__all__ = [
    "NodeOutputEvidence",
    "POSTCONDITION_VERSION",
    "PostconditionEvaluation",
    "PostconditionEvaluator",
    "PostconditionSpecError",
    "normalize_postcondition_spec",
]
