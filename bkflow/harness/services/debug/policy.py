"""Fail-closed request and trusted-authority policy for starting debug."""

import re
import uuid
from dataclasses import dataclass

from bkflow.harness.constants import (
    DebugControlAction,
    DebugExecutionMode,
    DebugMode,
    HarnessAction,
)
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.safety import (
    is_bounded_non_secret_json,
    is_harness_sensitive_key,
    is_safe_harness_text,
    is_safe_idempotency_key,
    safe_opaque_identifier,
)
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.knowledge.security import is_safe_opaque_uri


@dataclass(frozen=True)
class GlobalRealApprovalDecision:
    """Trusted, release-bound authorization for one exact global-real plan."""

    allowed: bool
    action: str
    release_manifest_id: str
    plan_hash: str
    target_environment: str


@dataclass(frozen=True)
class GlobalRealEnvironmentPolicy:
    """Server-owned allowlist for environments eligible for global Real."""

    allowed_environments: tuple

    def __post_init__(self):
        if (
            type(self.allowed_environments) is not tuple
            or not 1 <= len(self.allowed_environments) <= 32
            or len(set(self.allowed_environments)) != len(self.allowed_environments)
            or any(safe_opaque_identifier(environment) is None for environment in self.allowed_environments)
        ):
            raise ValueError("global real environment policy is invalid")


def is_global_real_debug_allowed(
    context,
    *,
    expected_plan_hash,
    expected_release_manifest_id,
    environment_policy,
    approval_decision,
):
    """Require every server-side and release-bound predicate for global Real."""
    from bkflow.harness.services.contract_versions import (
        is_harness_global_real_debug_enabled,
    )

    if (
        not isinstance(context, TrustedHarnessContext)
        or context.mcp_contract_version != "1.3.0"
        or not is_harness_global_real_debug_enabled(context.space_id)
    ):
        return False
    if type(environment_policy) is not GlobalRealEnvironmentPolicy:
        return False
    if context.target_environment not in environment_policy.allowed_environments:
        return False
    if type(approval_decision) is not GlobalRealApprovalDecision or approval_decision.allowed is not True:
        return False
    if approval_decision.action != HarnessAction.RUN_DEBUG_GLOBAL_REAL:
        return False
    try:
        manifest_id = str(uuid.UUID(expected_release_manifest_id))
    except (ValueError, TypeError, AttributeError):
        return False
    if manifest_id != expected_release_manifest_id or approval_decision.release_manifest_id != manifest_id:
        return False
    if not isinstance(expected_plan_hash, str) or re.fullmatch(r"[0-9a-f]{64}", expected_plan_hash) is None:
        return False
    return (
        approval_decision.plan_hash == expected_plan_hash
        and approval_decision.target_environment == context.target_environment
    )


class DebugStartRejected(ValueError):
    """A safe, categorized rejection that never includes request content."""

    def __init__(self, code, path, *, category=None, repairable=True, retryable=False):
        self.code = code
        self.path = path
        self.category = category
        self.repairable = repairable
        self.retryable = retryable
        super().__init__(code)


@dataclass(frozen=True)
class StartDebugRequest:
    """Closed write request containing references, never trusted identity fields."""

    run_id: str
    revision_id: str
    expected_plan_hash: str
    mode: str
    idempotency_key: str

    def as_dict(self):
        """Return the canonical request identity persisted by idempotency."""
        return {
            "run_id": self.run_id,
            "revision_id": self.revision_id,
            "expected_plan_hash": self.expected_plan_hash,
            "mode": self.mode,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class RunDebugRequest:
    """Closed tagged request for one step or global debug dispatch."""

    session_id: str
    expected_plan_hash: str
    mode: str
    execution_mode: str
    idempotency_key: str
    node_id: str = None
    input_overrides: dict = None
    mock_result: str = None
    mock_outputs: dict = None
    mock_error: str = None
    approval_receipt_ref: str = None
    inputs: dict = None

    def as_dict(self):
        if self.mode == DebugMode.GLOBAL:
            return {
                "session_id": self.session_id,
                "expected_plan_hash": self.expected_plan_hash,
                "mode": self.mode,
                "execution_mode": self.execution_mode,
                "inputs": self.inputs,
                "idempotency_key": self.idempotency_key,
            }
        value = {
            "session_id": self.session_id,
            "expected_plan_hash": self.expected_plan_hash,
            "mode": self.mode,
            "execution_mode": self.execution_mode,
            "node_id": self.node_id,
            "input_overrides": self.input_overrides,
            "mock_result": self.mock_result,
            "mock_outputs": self.mock_outputs,
            "mock_error": self.mock_error,
            "idempotency_key": self.idempotency_key,
        }
        if self.approval_receipt_ref is not None:
            value["approval_receipt_ref"] = self.approval_receipt_ref
        return value


@dataclass(frozen=True)
class GetDebugSessionRequest:
    """Closed read request for one owned session Evidence stream."""

    session_id: str
    limit: int = 20
    cursor: str = None
    node_limit: int = 10
    node_cursor: str = None
    node_id: str = None


@dataclass(frozen=True)
class ControlDebugSessionRequest:
    """Closed tagged mutation request for one owned debug session."""

    session_id: str
    expected_plan_hash: str
    action: str
    idempotency_key: str
    node_ids: list = None
    node_id: str = None
    enabled: bool = None
    mock_result: str = None
    mock_outputs: dict = None
    mock_error: str = None
    key: str = None
    value: object = None

    def as_dict(self):
        """Return only the action-specific canonical request fields."""
        common = {
            "session_id": self.session_id,
            "expected_plan_hash": self.expected_plan_hash,
            "action": self.action,
            "idempotency_key": self.idempotency_key,
        }
        if self.action == DebugControlAction.RESET:
            return {**common, "node_ids": self.node_ids}
        if self.action == DebugControlAction.TERMINATE:
            return {**common, **({"node_id": self.node_id} if self.node_id is not None else {})}
        if self.action == DebugControlAction.SET_NODE_MOCK:
            return {
                **common,
                "node_id": self.node_id,
                "enabled": self.enabled,
                "mock_result": self.mock_result,
                "mock_outputs": self.mock_outputs,
                "mock_error": self.mock_error,
            }
        return {**common, "key": self.key, "value": self.value}


def validate_start_request(payload):
    """Parse exactly the five fields admitted by ``start_debug_session``."""
    required = {"run_id", "revision_id", "expected_plan_hash", "mode", "idempotency_key"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "request")
    if payload["mode"] not in DebugMode.values:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "mode")
    if not is_safe_idempotency_key(payload["idempotency_key"]):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "idempotency_key")
    if (
        not isinstance(payload["expected_plan_hash"], str)
        or re.fullmatch(r"[0-9a-f]{64}", payload["expected_plan_hash"]) is None
    ):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "expected_plan_hash")
    for field_name in ("run_id", "revision_id"):
        value = payload[field_name]
        try:
            parsed = str(uuid.UUID(value)) if isinstance(value, str) else None
        except (ValueError, AttributeError):
            parsed = None
        if parsed != value:
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", field_name)
    return StartDebugRequest(**{key: payload[key] for key in required})


def validate_run_request(payload):
    """Parse one exact mode-tagged run request without accepting authority fields."""
    common = {"session_id", "expected_plan_hash", "mode", "execution_mode", "idempotency_key"}
    if not isinstance(payload, dict) or payload.get("mode") not in DebugMode.values:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "request")
    if payload["mode"] == DebugMode.GLOBAL:
        expected = common | {"inputs"}
    else:
        expected = common | {"node_id", "input_overrides", "mock_result", "mock_outputs", "mock_error"}
        if payload.get("execution_mode") == DebugExecutionMode.REAL and "approval_receipt_ref" in payload:
            expected.add("approval_receipt_ref")
    if set(payload) != expected:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "request")
    try:
        parsed_session_id = str(uuid.UUID(payload["session_id"]))
    except (ValueError, TypeError, AttributeError):
        parsed_session_id = None
    if parsed_session_id != payload.get("session_id"):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "session_id")
    if (
        not isinstance(payload.get("expected_plan_hash"), str)
        or re.fullmatch(r"[0-9a-f]{64}", payload["expected_plan_hash"]) is None
    ):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "expected_plan_hash")
    if payload.get("execution_mode") not in DebugExecutionMode.values:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "execution_mode")
    if not is_safe_idempotency_key(payload.get("idempotency_key")):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "idempotency_key")
    if payload["mode"] == DebugMode.GLOBAL:
        if payload["execution_mode"] != DebugExecutionMode.MOCK:
            code = (
                "APPROVAL_REQUIRED"
                if payload["execution_mode"] == DebugExecutionMode.REAL
                else "SCHEMA_VALIDATION_ERROR"
            )
            raise DebugStartRejected(code, "execution_mode", repairable=False)
        if not isinstance(payload.get("inputs"), dict) or not is_bounded_non_secret_json(payload["inputs"]):
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "inputs")
        return RunDebugRequest(**payload)
    if safe_opaque_identifier(payload.get("node_id")) is None:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_id")
    for field_name in ("input_overrides", "mock_outputs"):
        value = payload.get(field_name)
        if not isinstance(value, dict) or not is_bounded_non_secret_json(value):
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", field_name)
    if payload.get("mock_result") not in {"success", "fail"} or not is_safe_harness_text(
        payload.get("mock_error"), max_chars=4096, max_bytes=16384
    ):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "mock_result")
    receipt_ref = payload.get("approval_receipt_ref")
    if receipt_ref is not None and not is_safe_opaque_uri(receipt_ref, "approval", 255):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "approval_receipt_ref")
    return RunDebugRequest(**payload)


def _validated_session_id(value):
    try:
        parsed = str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        parsed = None
    if parsed != value:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "session_id")
    return parsed


def validate_get_request(payload):
    """Parse a bounded Evidence-page request without admitting identity fields."""
    allowed = {"session_id", "limit", "cursor", "node_limit", "node_cursor", "node_id"}
    if not isinstance(payload, dict) or not {"session_id"} <= set(payload) <= allowed:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "request")
    session_id = _validated_session_id(payload.get("session_id"))
    limit = payload.get("limit", 20)
    cursor = payload.get("cursor")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "limit")
    if cursor is not None and (
        not isinstance(cursor, str) or len(cursor) > 512 or re.fullmatch(r"[A-Za-z0-9_-]+", cursor) is None
    ):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "cursor")
    node_limit = payload.get("node_limit", 10)
    node_cursor = payload.get("node_cursor")
    node_id = payload.get("node_id")
    if isinstance(node_limit, bool) or not isinstance(node_limit, int) or not 1 <= node_limit <= 20:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_limit")
    if node_cursor is not None and (
        not isinstance(node_cursor, str)
        or len(node_cursor) > 512
        or re.fullmatch(r"[A-Za-z0-9_-]+", node_cursor) is None
    ):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_cursor")
    if node_id is not None and not is_safe_harness_text(node_id, max_chars=255, max_bytes=1020):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_id")
    if node_id is not None and (not node_id or node_cursor is not None):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_id")
    return GetDebugSessionRequest(
        session_id=session_id,
        limit=limit,
        cursor=cursor,
        node_limit=node_limit,
        node_cursor=node_cursor,
        node_id=node_id,
    )


def validate_control_request(payload):
    """Parse one exact action-tagged control request and reject secrets up front."""
    common = {"session_id", "expected_plan_hash", "action", "idempotency_key"}
    if not isinstance(payload, dict) or payload.get("action") not in DebugControlAction.values:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "request")
    action = payload["action"]
    if action == DebugControlAction.RESET:
        expected = common | {"node_ids"}
    elif action == DebugControlAction.TERMINATE:
        expected = common | ({"node_id"} if "node_id" in payload else set())
    elif action == DebugControlAction.SET_NODE_MOCK:
        expected = common | {"node_id", "enabled", "mock_result", "mock_outputs", "mock_error"}
    else:
        expected = common | {"key", "value"}
    if set(payload) != expected:
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "request")
    _validated_session_id(payload.get("session_id"))
    if (
        not isinstance(payload.get("expected_plan_hash"), str)
        or re.fullmatch(r"[0-9a-f]{64}", payload["expected_plan_hash"]) is None
    ):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "expected_plan_hash")
    if not is_safe_idempotency_key(payload.get("idempotency_key")):
        raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "idempotency_key")
    if action == DebugControlAction.RESET:
        node_ids = payload.get("node_ids")
        if (
            not isinstance(node_ids, list)
            or len(node_ids) > 100
            or any(safe_opaque_identifier(node_id) is None for node_id in node_ids)
            or len(node_ids) != len(set(node_ids))
        ):
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_ids")
    elif action == DebugControlAction.TERMINATE:
        if payload.get("node_id") is not None and safe_opaque_identifier(payload["node_id"]) is None:
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_id")
    elif action == DebugControlAction.SET_NODE_MOCK:
        if (
            safe_opaque_identifier(payload.get("node_id")) is None
            or not isinstance(payload.get("enabled"), bool)
            or payload.get("mock_result") not in {"success", "fail"}
            or not isinstance(payload.get("mock_outputs"), dict)
            or not is_bounded_non_secret_json(payload["mock_outputs"])
            or not is_safe_harness_text(payload.get("mock_error"), max_chars=4096, max_bytes=16384)
        ):
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "set_node_mock")
    else:
        key = payload.get("key")
        match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_.-]{0,127})\}", key or "")
        if (
            match is None
            or is_harness_sensitive_key(match.group(1))
            or not is_bounded_non_secret_json(payload.get("value"))
        ):
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "set_context_var")
    return ControlDebugSessionRequest(**payload)


def context_matches_run(context, run):
    """Require every server-owned run dimension to match the trusted call."""
    if not isinstance(context, TrustedHarnessContext):
        return False
    try:
        scope = canonical_scope(context.scope_type, context.scope_value)
    except ValueError:
        return False
    return {
        "platform": run.platform,
        "platform_app": run.platform_app,
        "actor": run.actor,
        "space_id": run.space_id,
        "scope": run.scope,
        "environment": run.environment,
        "policy_version": run.policy_version,
        "mcp_contract_version": run.mcp_contract_version,
    } == {
        "platform": context.platform_key,
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope": scope,
        "environment": context.target_environment,
        "policy_version": context.policy_version,
        "mcp_contract_version": context.mcp_contract_version,
    }


def trusted_context_snapshot(context):
    """Persist the complete minimum authority snapshot required by DebugSession."""
    return {
        "platform_key": context.platform_key,
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope_type": context.scope_type,
        "scope_value": context.scope_value,
        "target_environment": context.target_environment,
        "policy_version": context.policy_version,
        "mcp_contract_version": context.mcp_contract_version,
        "correlation_id": context.correlation_id,
    }
