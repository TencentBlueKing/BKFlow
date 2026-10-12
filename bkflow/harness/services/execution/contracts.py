"""Closed contracts for the create/start execution Saga."""

import re
import uuid
from copy import deepcopy
from dataclasses import dataclass

from bkflow.harness.safety import (
    is_bounded_non_secret_json,
    is_safe_harness_text,
    is_safe_idempotency_key,
    safe_opaque_identifier,
)

RUNTIME_AUTHORIZATION_MODE = "harness_domain_service"
_BASE_FIELDS = frozenset(
    {
        "run_id",
        "manifest_id",
        "publication_id",
        "expected_plan_hash",
        "name",
        "constants",
        "idempotency_key",
    }
)
_APPROVED_FIELDS = _BASE_FIELDS | {"approval_request_id", "approval_receipt_ref"}
_GET_FIELDS = frozenset({"execution_id", "limit", "cursor"})
_CONTROL_COMMON_FIELDS = frozenset({"execution_id", "expected_manifest_hash", "action", "idempotency_key"})
_CONTROL_ACTION_FIELDS = {
    "pause": (frozenset(),),
    "resume": (frozenset(),),
    "revoke": (frozenset(),),
    "retry": (
        frozenset({"template_node_id", "loop"}),
        frozenset({"template_node_id", "loop", "inputs"}),
    ),
    "skip": (frozenset({"template_node_id", "loop"}),),
    "callback": (frozenset({"template_node_id", "callback_data"}),),
    "forced_fail": (frozenset({"template_node_id", "reason_code"}),),
    "skip_exg": (frozenset({"template_gateway_id", "template_flow_id"}),),
    "skip_cpg": (
        frozenset(
            {
                "template_gateway_id",
                "template_flow_ids",
                "template_converge_gateway_id",
            }
        ),
    ),
}
_CONTROL_APPROVAL_FIELDS = frozenset({"approval_request_id", "approval_receipt_ref"})
_FORCED_FAIL_REASON_CODES = frozenset({"operator_requested"})


class StartExecutionRejected(ValueError):
    """A safe failure projected through the common Harness envelope."""

    def __init__(
        self,
        code,
        path,
        *,
        category=None,
        repairable=True,
        retryable=False,
        approval_request_id=None,
        manual_reconcile=False,
    ):
        self.code = code
        self.path = path
        self.category = category
        self.repairable = repairable
        self.retryable = retryable
        self.approval_request_id = approval_request_id
        self.manual_reconcile = manual_reconcile
        super().__init__(code)


@dataclass(frozen=True)
class StartExecutionRequest:
    run_id: str
    manifest_id: str
    publication_id: str
    expected_plan_hash: str
    name: str
    constants: dict
    idempotency_key: str
    approval_request_id: str = None
    approval_receipt_ref: str = None

    @property
    def has_approval(self):
        return self.approval_request_id is not None

    def action_payload(self):
        """Exclude receipt material from durable hashes and replay snapshots."""
        return {
            "run_id": self.run_id,
            "manifest_id": self.manifest_id,
            "publication_id": self.publication_id,
            "expected_plan_hash": self.expected_plan_hash,
            "name": self.name,
            "constants": deepcopy(self.constants),
            "idempotency_key": self.idempotency_key,
            "approval_request_id": self.approval_request_id,
        }


@dataclass(frozen=True)
class GetExecutionRequest:
    """Closed, bounded read request for one owned execution."""

    execution_id: str
    limit: int = 20
    cursor: str = None


@dataclass(frozen=True)
class ControlExecutionRequest:
    """One normalized task or template-node control intent."""

    execution_id: str
    expected_manifest_hash: str
    action: str
    idempotency_key: str
    template_node_id: str = None
    loop: bool = None
    inputs: dict = None
    callback_data: dict = None
    reason_code: str = None
    template_gateway_id: str = None
    template_flow_id: str = None
    template_flow_ids: tuple = ()
    template_converge_gateway_id: str = None
    approval_request_id: str = None
    approval_receipt_ref: str = None

    @property
    def has_approval(self):
        return self.approval_request_id is not None

    def action_payload(self):
        """Return the receipt-free exact intent used for policy and idempotency."""
        payload = {
            "execution_id": self.execution_id,
            "expected_manifest_hash": self.expected_manifest_hash,
            "action": self.action,
            "idempotency_key": self.idempotency_key,
        }
        for name in (
            "template_node_id",
            "loop",
            "inputs",
            "callback_data",
            "reason_code",
            "template_gateway_id",
            "template_flow_id",
            "template_converge_gateway_id",
        ):
            value = getattr(self, name)
            if value is not None:
                payload[name] = deepcopy(value)
        if self.template_flow_ids:
            payload["template_flow_ids"] = list(self.template_flow_ids)
        return payload


def _uuid(value, path):
    try:
        normalized = str(uuid.UUID(value))
    except (TypeError, ValueError, AttributeError):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", path) from None
    if not isinstance(value, str) or value != normalized:
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", path)
    return value


def validate_start_execution_request(payload):
    if not isinstance(payload, dict) or set(payload) not in {_BASE_FIELDS, _APPROVED_FIELDS}:
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "request")
    values = deepcopy(payload)
    for name in ("run_id", "manifest_id", "publication_id"):
        values[name] = _uuid(values[name], name)
    if set(payload) == _APPROVED_FIELDS:
        values["approval_request_id"] = _uuid(values["approval_request_id"], "approval_request_id")
        if not is_safe_harness_text(values["approval_receipt_ref"], max_chars=255, max_bytes=1024, allow_empty=False):
            raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "approval_receipt_ref")
    if (
        not isinstance(values["expected_plan_hash"], str)
        or re.fullmatch(r"[0-9a-f]{64}", values["expected_plan_hash"]) is None
    ):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "expected_plan_hash")
    if not is_safe_harness_text(values["name"], max_chars=128, max_bytes=512, allow_empty=False):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "name")
    if not isinstance(values["constants"], dict) or not is_bounded_non_secret_json(values["constants"]):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "constants")
    if not is_safe_idempotency_key(values["idempotency_key"]) or len(values["idempotency_key"]) > 128:
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "idempotency_key")
    return StartExecutionRequest(**values)


def validate_get_execution_request(payload):
    """Reject unknown fields and non-canonical identifiers before persistence reads."""
    if not isinstance(payload, dict) or "execution_id" not in payload or not set(payload) <= _GET_FIELDS:
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "request")
    execution_id = _uuid(payload["execution_id"], "execution_id")
    limit = payload.get("limit", 20)
    cursor = payload.get("cursor")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "limit")
    if cursor is not None and not is_safe_harness_text(cursor, max_chars=512, max_bytes=2048, allow_empty=False):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "cursor")
    return GetExecutionRequest(execution_id=execution_id, limit=limit, cursor=cursor)


def validate_control_execution_request(payload):
    """Validate the exact tagged wire shape before any authority lookup."""
    if not isinstance(payload, dict):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "request")
    action = payload.get("action")
    if not isinstance(action, str) or action not in _CONTROL_ACTION_FIELDS:
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "action")
    expected_shapes = tuple(_CONTROL_COMMON_FIELDS | fields for fields in _CONTROL_ACTION_FIELDS[action])
    if set(payload) in tuple(shape | _CONTROL_APPROVAL_FIELDS for shape in expected_shapes):
        approved = True
    elif set(payload) in expected_shapes:
        approved = False
    else:
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "request")
    values = deepcopy(payload)
    values["execution_id"] = _uuid(values["execution_id"], "execution_id")
    if (
        not isinstance(values["expected_manifest_hash"], str)
        or re.fullmatch(r"[0-9a-f]{64}", values["expected_manifest_hash"]) is None
    ):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "expected_manifest_hash")
    if not is_safe_idempotency_key(values["idempotency_key"]) or len(values["idempotency_key"]) > 128:
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "idempotency_key")
    if approved:
        values["approval_request_id"] = _uuid(values["approval_request_id"], "approval_request_id")
        if not is_safe_harness_text(values["approval_receipt_ref"], max_chars=255, max_bytes=1024, allow_empty=False):
            raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "approval_receipt_ref")
    for name in (
        "template_node_id",
        "template_gateway_id",
        "template_flow_id",
        "template_converge_gateway_id",
    ):
        if name in values and safe_opaque_identifier(values[name]) is None:
            raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", name)
    if "loop" in values and not isinstance(values["loop"], bool):
        raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "loop")
    for name in ("inputs", "callback_data"):
        if name in values and (not isinstance(values[name], dict) or not is_bounded_non_secret_json(values[name])):
            raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", name)
    if "reason_code" in values:
        reason_code = values["reason_code"]
        if not isinstance(reason_code, str) or reason_code not in _FORCED_FAIL_REASON_CODES:
            raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "reason_code")
    if "template_flow_ids" in values:
        flow_ids = values["template_flow_ids"]
        if (
            not isinstance(flow_ids, list)
            or not 1 <= len(flow_ids) <= 32
            or any(safe_opaque_identifier(item) is None for item in flow_ids)
            or len(flow_ids) != len(set(flow_ids))
        ):
            raise StartExecutionRejected("SCHEMA_VALIDATION_ERROR", "template_flow_ids")
        values["template_flow_ids"] = tuple(flow_ids)
    return ControlExecutionRequest(**values)


__all__ = [
    "ControlExecutionRequest",
    "RUNTIME_AUTHORIZATION_MODE",
    "GetExecutionRequest",
    "StartExecutionRejected",
    "StartExecutionRequest",
    "validate_start_execution_request",
    "validate_get_execution_request",
    "validate_control_execution_request",
]
