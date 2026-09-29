"""Shared exact-envelope transport adapter."""

import logging
import math
import os
import re
import time
import traceback
import uuid
from collections.abc import Mapping
from types import SimpleNamespace

from django.db import DatabaseError
from rest_framework.response import Response

from bkflow.harness.safety import (
    contains_secret_shaped_text,
    is_harness_sensitive_key,
    is_safe_harness_text,
    is_safe_idempotency_key,
    safe_opaque_identifier,
)
from bkflow.harness.services.context import correlation_id
from bkflow.harness.services.validator import WorkflowValidationFailure

logger = logging.getLogger("bkflow.harness")

_ENVELOPE_KEYS = frozenset(
    (
        "ok",
        "run_id",
        "revision_id",
        "plan_hash",
        "status",
        "summary",
        "artifact_refs",
        "errors",
        "next_actions",
        "correlation_id",
    )
)
_ERROR_CATEGORIES = frozenset(
    (
        "USER_INPUT",
        "CAPABILITY_NOT_FOUND",
        "AMBIGUOUS_CAPABILITY",
        "SCHEMA_DRIFT",
        "VALIDATION",
        "PERMISSION",
        "APPROVAL_REQUIRED",
        "APPROVAL_INVALID",
        "TOKEN_LEASE",
        "DEBUG_CONFLICT",
        "RUNTIME",
        "POSTCONDITION",
        "RETRYABLE_INFRA",
    )
)
_SAFE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.<>-]{0,127}$")
_SENSITIVE_ARTIFACT_METADATA_KEY = re.compile(r"traceback|providerdetail", re.I)
_REQUIRED_CREDENTIALS_KEY = "required_credentials"
_CREDENTIAL_KIND = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_SENSITIVE_CREDENTIAL_KIND = re.compile(
    r"credential|token|secret|password|authorization|apikey|traceback|providerdetail", re.I
)
_MAX_RESPONSE_BYTES = 65536
_MAX_ARTIFACT_DEPTH = 8
_MAX_ARTIFACT_ITEMS = 100
_MAX_ARTIFACT_KEY_BYTES = 256
_MAX_ARTIFACT_VALUE_BYTES = 16384
_MAX_NEXT_ACTIONS = 16
_MAX_NEXT_ACTION_BYTES = 128
_REDACTED_VALUE = "[REDACTED]"
_SAFE_ERROR_CODES = frozenset(WorkflowValidationFailure._DETAILS)
_KNOWLEDGE_TOOL = "search_workflow_knowledge"
_KNOWLEDGE_ARTIFACT_REF = re.compile(r"^[a-z][a-z0-9+.-]*://\S{1,252}$")
_KNOWLEDGE_WARNING_CODES = frozenset(
    ("KNOWLEDGE_SOURCE_FAILED", "KNOWLEDGE_RESULT_IN_ARTIFACT", "KNOWLEDGE_RESULT_TRUNCATED")
)
_APPROVAL_BOUND_TOOLS = frozenset(("publish_workflow", "start_workflow_execution", "control_workflow_execution"))
_SAFE_FAILURE_REMEDIATIONS = frozenset(("obtain_approval", "configure_release_policy", "manual_reconcile_execution"))


class HarnessPermissionDenied(Exception):
    """Carry a stable permission result through DRF's exception boundary."""

    def __init__(self, code):
        self.code = code
        super().__init__("Harness access denied.")


def _safe_identifier(value):
    """Return a bounded opaque identifier without reflecting raw downstream text."""
    return safe_opaque_identifier(value)


def _safe_path(value):
    """Preserve only bounded server coordinates, never a raw provider or client field name."""
    if isinstance(value, str) and _SAFE_PATH.match(value):
        return value
    return "request"


def _failure_envelope(context, code="SCHEMA_VALIDATION_ERROR", category=None, retryable=False):
    """Build one frozen failure shape without accepting message text from an untrusted boundary."""
    error = WorkflowValidationFailure(
        code, path="request", category=category, repairable=not retryable, retryable=retryable
    ).as_error()
    return {
        "ok": False,
        "run_id": None,
        "revision_id": None,
        "plan_hash": None,
        "status": None,
        "summary": "Workflow validation requires repair.",
        "artifact_refs": [],
        "errors": [error],
        "next_actions": [error["suggested_action"]],
        "correlation_id": _safe_identifier(context.correlation_id),
    }


def _permission_context(request, view):
    """Build the minimal safe audit context available before HarnessPermission succeeds."""
    try:
        space_id = int(getattr(view, "kwargs", {}).get("space_id"))
    except (TypeError, ValueError):
        space_id = None
    return SimpleNamespace(
        actor=getattr(getattr(request, "user", None), "username", None),
        space_id=space_id,
        correlation_id=correlation_id(request),
    )


def harness_view(tool):
    """Adapt only HarnessPermission denials while retaining DRF's normal view dispatch."""

    def decorate(view):
        base_view = view.cls

        class HarnessAPIView(base_view):
            def permission_denied(self, request, message=None, code=None):
                failure = getattr(request, "harness_authorization_error", None)
                raise HarnessPermissionDenied(getattr(failure, "code", "HARNESS_ACCESS_DENIED"))

            def handle_exception(self, exc):
                if isinstance(exc, HarnessPermissionDenied):
                    context = _permission_context(self.request, self)
                    result = _failure_envelope(context, exc.code, category="PERMISSION")
                    _audit(context, tool, result, 0)
                    return Response(result)
                return super().handle_exception(exc)

        wrapped = HarnessAPIView.as_view()
        wrapped.__name__ = view.__name__
        wrapped.__doc__ = view.__doc__
        return wrapped

    return decorate


def envelope(context, serializer):
    """Adapt rejected transport input to the frozen safe response shape."""
    result = _failure_envelope(context)
    if serializer is not None:
        # 仅引用服务端声明字段，不透传 DRF 文案、未知字段名或客户端值。
        paths = [name for name in serializer.fields if name in serializer.errors]
        result["errors"] = []
        for path in (paths or ["request"])[:16]:
            error = WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path).as_error()
            error["message"] = "The tool arguments do not match the request schema."
            error["suggested_action"] = "repair_tool_arguments"
            result["errors"].append(error)
        result["next_actions"] = ["repair_tool_arguments"]
    return result


def _log_failure(context, method, error):
    """记录有界代码坐标，不记录异常文案、请求、局部变量或原始堆栈。"""
    frames = [
        {
            "file": _safe_identifier(os.path.basename(frame.f_code.co_filename)),
            "function": _safe_identifier(frame.f_code.co_name),
            "line": line,
        }
        for frame, line in traceback.walk_tb(error.__traceback__)
    ][-8:]
    logger.error(
        "harness internal failure",
        extra={
            "harness_failure": {
                "tool": method,
                "correlation": _safe_identifier(context.correlation_id),
                "exception_type": _safe_identifier(type(error).__name__),
                "frames": frames,
            }
        },
    )


def _safe_artifact_refs(value, max_depth=_MAX_ARTIFACT_DEPTH):
    """Keep only bounded canonical service artifacts in a successful frozen response."""
    if not isinstance(value, list):
        return None
    if _contains_reserved_approval_projection(value):
        return None
    if not _safe_artifact_value(value, max_depth=max_depth):
        return None
    if _contains_secret_value(value):
        return None
    return value


def _contains_reserved_approval_projection(value):
    """Reserve approval handles for the transport's verified top-level projection."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", key.lower()) if isinstance(key, str) else ""
            if normalized_key == "approvalrequestid":
                return True
            if normalized_key == "type" and isinstance(item, str):
                normalized_type = re.sub(r"[^a-z0-9]", "", item.lower())
                if normalized_type == "approvalrequest":
                    return True
            if _contains_reserved_approval_projection(item):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_reserved_approval_projection(item) for item in value)
    return False


def _contains_secret_value(value):
    """Reject credential-like values without treating public schema field names as secrets."""
    if isinstance(value, Mapping):
        return any(_contains_secret_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret_value(item) for item in value)
    return contains_secret_shaped_text(value)


def _bounded_artifact_key(value):
    """Return whether one artifact mapping key is valid bounded public text."""
    if not isinstance(value, str):
        return False
    return is_safe_harness_text(
        value,
        max_chars=_MAX_ARTIFACT_KEY_BYTES,
        max_bytes=_MAX_ARTIFACT_KEY_BYTES,
        allow_empty=False,
    )


def _is_sensitive_artifact_key(value):
    """Identify credential-bearing key names after bounded-text validation."""
    if not _bounded_artifact_key(value):
        return False
    normalized = re.sub(r"[^a-z0-9]", "", value.lower())
    return is_harness_sensitive_key(value) or _SENSITIVE_ARTIFACT_METADATA_KEY.search(normalized) is not None


def _safe_artifact_key(value):
    """Reject malformed and secret-like artifact mapping keys before they can be reflected."""
    return _bounded_artifact_key(value) and not _is_sensitive_artifact_key(value)


def _safe_required_credentials(value):
    """Allow Task 5's fixed public credential-kind list without permitting credential values."""
    if not isinstance(value, list) or len(value) > _MAX_ARTIFACT_ITEMS:
        return False
    for kind in value:
        if not isinstance(kind, str) or not _CREDENTIAL_KIND.match(kind):
            return False
        try:
            encoded = kind.encode("utf-8")
        except UnicodeError:
            return False
        normalized = re.sub(r"[^a-z0-9]", "", kind.lower())
        if (
            len(encoded) > _MAX_ARTIFACT_KEY_BYTES
            or _SENSITIVE_CREDENTIAL_KIND.search(normalized) is not None
            or contains_secret_shaped_text(kind)
        ):
            return False
    return True


def _safe_artifact_value(value, depth=0, max_depth=_MAX_ARTIFACT_DEPTH):
    """Recursively accept only bounded JSON-safe artifact mappings and values."""
    if depth > max_depth:
        return False
    if isinstance(value, Mapping):
        if len(value) > _MAX_ARTIFACT_ITEMS:
            return False
        for key, item in value.items():
            if key == _REQUIRED_CREDENTIALS_KEY:
                if not _safe_required_credentials(item):
                    return False
            elif _is_sensitive_artifact_key(key) and item == _REDACTED_VALUE:
                continue
            elif not _safe_artifact_key(key) or not _safe_artifact_value(item, depth + 1, max_depth):
                return False
        return True
    if isinstance(value, list):
        return len(value) <= _MAX_ARTIFACT_ITEMS and all(
            _safe_artifact_value(item, depth + 1, max_depth) for item in value
        )
    if isinstance(value, str):
        return is_safe_harness_text(
            value,
            max_chars=_MAX_ARTIFACT_VALUE_BYTES,
            max_bytes=_MAX_ARTIFACT_VALUE_BYTES,
        )
    if isinstance(value, float):
        return math.isfinite(value)
    return isinstance(value, (int, bool, type(None)))


def _safe_error(value):
    """Regenerate one public error from the closed P0 code taxonomy."""
    value = value if isinstance(value, Mapping) else {}
    code = value.get("code")
    if not isinstance(code, str) or code not in _SAFE_ERROR_CODES:
        code = "RETRYABLE_INFRA"
    return WorkflowValidationFailure(
        code,
        path=_safe_path(value.get("path")),
        repairable=value.get("repairable") is True,
        retryable=value.get("retryable") is True,
    ).as_error()


def _safe_next_actions(context, value):
    """Keep bounded, unique navigation only inside the negotiated Harness Tool set."""
    if not isinstance(value, list) or len(value) > _MAX_NEXT_ACTIONS:
        return []
    from bkflow.harness.services.contract_versions import tools_for_contract

    try:
        allowed = tools_for_contract(context.mcp_contract_version)
    except Exception:
        return []
    actions = []
    for action in value:
        if (
            isinstance(action, str)
            and action in allowed
            and is_safe_harness_text(
                action,
                max_chars=_MAX_NEXT_ACTION_BYTES,
                max_bytes=_MAX_NEXT_ACTION_BYTES,
                allow_empty=False,
            )
            and action not in actions
        ):
            actions.append(action)
    return actions


def _safe_failure_next_actions(errors, raw_next_actions):
    """Keep regenerated taxonomy remediation plus a tiny fixed service remediation set."""
    actions = list(dict.fromkeys(error["suggested_action"] for error in errors))
    if isinstance(raw_next_actions, list) and len(raw_next_actions) <= _MAX_NEXT_ACTIONS:
        for action in raw_next_actions:
            if (
                isinstance(action, str)
                and action in _SAFE_FAILURE_REMEDIATIONS
                and is_safe_harness_text(
                    action,
                    max_chars=_MAX_NEXT_ACTION_BYTES,
                    max_bytes=_MAX_NEXT_ACTION_BYTES,
                    allow_empty=False,
                )
                and action not in actions
            ):
                actions.append(action)
    return actions[:_MAX_NEXT_ACTIONS]


def _canonical_approval_request_id(value):
    """Accept only a canonical UUID before projecting an approval handle."""
    if not isinstance(value, str):
        return None
    try:
        return value if str(uuid.UUID(value)) == value else None
    except (TypeError, ValueError, AttributeError):
        return None


def _safe_domain_result(context, result, method):
    """Copy only the frozen domain contract and regenerate every human-readable error field."""
    if not isinstance(result, Mapping):
        return _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)
    raw_result = dict(result)
    approval_request_id = None
    if set(raw_result) == _ENVELOPE_KEYS | {"approval_request_id"} and method in _APPROVAL_BOUND_TOOLS:
        approval_request_id = _canonical_approval_request_id(raw_result.pop("approval_request_id"))
    if set(raw_result) != _ENVELOPE_KEYS or ("approval_request_id" in result and approval_request_id is None):
        return _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)
    result = raw_result
    raw_errors = result.get("errors")
    if approval_request_id is not None and (
        result.get("ok") is not False
        or not isinstance(raw_errors, list)
        or len(raw_errors) != 1
        or not isinstance(raw_errors[0], Mapping)
        or raw_errors[0].get("code") != "APPROVAL_REQUIRED"
    ):
        return _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)
    if result.get("ok") is True:
        if approval_request_id is not None:
            return _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)
        raw_artifacts = result.get("artifact_refs")
        # 精确 Schema 多了 artifact/payload/IO/field 包装层；其他响应维持原深度。
        schema_response = (
            method == "get_plugin_schema"
            and isinstance(raw_artifacts, list)
            and len(raw_artifacts) == 1
            and isinstance(raw_artifacts[0], Mapping)
            and raw_artifacts[0].get("type") == "plugin_schema"
        )
        artifact_refs = _safe_artifact_refs(
            raw_artifacts, max_depth=_MAX_ARTIFACT_DEPTH + (4 if schema_response else 0)
        )
        if artifact_refs is None:
            return _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)
        return {
            "ok": True,
            "run_id": _safe_identifier(result.get("run_id")),
            "revision_id": _safe_identifier(result.get("revision_id")),
            "plan_hash": _safe_identifier(result.get("plan_hash")),
            "status": _safe_identifier(result.get("status")),
            "summary": (
                "Workflow draft created; stop the draft-only workflow."
                if method == "create_workflow_draft" and result.get("status") == "DRAFT_READY"
                else "Harness request accepted."
            ),
            "artifact_refs": artifact_refs,
            "errors": [],
            # Also project old idempotency snapshots without rewriting durable evidence.
            "next_actions": (
                []
                if method == "create_workflow_draft" and result.get("status") == "DRAFT_READY"
                else _safe_next_actions(context, result.get("next_actions"))
            ),
            "correlation_id": _safe_identifier(context.correlation_id),
        }
    safe_errors = [_safe_error(error) for error in raw_errors] if isinstance(raw_errors, list) and raw_errors else []
    if not safe_errors:
        safe_errors = [_safe_error({"code": "RETRYABLE_INFRA", "retryable": True})]
    if _contains_reserved_approval_projection(result.get("artifact_refs")):
        return _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)
    artifact_refs = _safe_artifact_refs(result.get("artifact_refs")) or []
    if approval_request_id is not None:
        approval_artifact = {"type": "approval_request", "approval_request_id": approval_request_id}
        artifact_refs = [approval_artifact, *artifact_refs[: _MAX_ARTIFACT_ITEMS - 1]]
    return {
        "ok": False,
        "run_id": _safe_identifier(result.get("run_id")),
        "revision_id": _safe_identifier(result.get("revision_id")),
        "plan_hash": _safe_identifier(result.get("plan_hash")),
        "status": _safe_identifier(result.get("status")),
        "summary": "Workflow validation requires repair.",
        "artifact_refs": artifact_refs,
        "errors": safe_errors,
        "next_actions": _safe_failure_next_actions(safe_errors, result.get("next_actions")),
        "correlation_id": _safe_identifier(context.correlation_id),
    }


def _rendered_response_bytes(request, result):
    """Measure the bytes emitted by this request's negotiated DRF renderer."""
    renderer = getattr(request, "accepted_renderer", None)
    accepted_media_type = getattr(request, "accepted_media_type", None)
    parser_context = getattr(request, "parser_context", None)
    if renderer is None or not isinstance(accepted_media_type, str) or not isinstance(parser_context, Mapping):
        return None

    renderer_context = {
        "view": parser_context.get("view"),
        "args": parser_context.get("args", ()),
        "kwargs": parser_context.get("kwargs", {}),
        "request": request,
    }
    probe = Response(result)
    probe.accepted_renderer = renderer
    probe.accepted_media_type = accepted_media_type
    probe.renderer_context = renderer_context
    try:
        rendered = probe.rendered_content
    except Exception:
        return None
    if not isinstance(rendered, bytes):
        return None
    return len(rendered)


def _knowledge_overflow_result(request, context, result):
    """Replace oversized inline hits with trusted artifact refs and an explicit truncation marker."""
    refs = []
    warnings = []
    query_fingerprint = None
    raw_artifacts = result.get("artifact_refs")
    if isinstance(raw_artifacts, list) and len(raw_artifacts) == 1 and isinstance(raw_artifacts[0], Mapping):
        artifact = raw_artifacts[0]
        payload = artifact.get("payload") if artifact.get("type") == "knowledge_search" else None
        if isinstance(payload, Mapping) and payload.get("policy_effect") == "ADVISORY":
            query_fingerprint = _safe_identifier(payload.get("query_fingerprint"))
            raw_refs = payload.get("artifact_refs")
            if isinstance(raw_refs, list):
                refs = [
                    ref
                    for ref in raw_refs
                    if isinstance(ref, str)
                    and len(ref.encode("utf-8")) <= 255
                    and _KNOWLEDGE_ARTIFACT_REF.fullmatch(ref)
                    and not contains_secret_shaped_text(ref)
                ]
            raw_warnings = payload.get("warning_codes")
            if isinstance(raw_warnings, list):
                warnings = [warning for warning in raw_warnings if warning in _KNOWLEDGE_WARNING_CODES]

    warnings = list(dict.fromkeys(warnings + ["KNOWLEDGE_ENVELOPE_TRUNCATED"]))
    bounded = dict(result)
    while True:
        bounded["artifact_refs"] = [
            {
                "type": "knowledge_search",
                "payload": {
                    "query_fingerprint": query_fingerprint,
                    "hits": [],
                    "conflict_annotations": [],
                    "artifact_refs": refs,
                    "warning_codes": warnings,
                    "policy_effect": "ADVISORY",
                },
            }
        ]
        rendered_bytes = _rendered_response_bytes(request, bounded)
        if rendered_bytes is not None and rendered_bytes <= _MAX_RESPONSE_BYTES:
            return bounded
        if refs:
            refs.pop()
            continue
        return _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)


def _bounded_response(request, context, result, method):
    """Enforce the complete ten-key Envelope budget before any HTTP response is built."""
    rendered_bytes = _rendered_response_bytes(request, result)
    if rendered_bytes is not None and rendered_bytes <= _MAX_RESPONSE_BYTES:
        return result
    if method == _KNOWLEDGE_TOOL:
        return _knowledge_overflow_result(request, context, result)
    return _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)


def _audit(context, method, result, duration_ms, risk=None):
    """Emit only fixed, bounded audit metadata for every success and failure response."""
    from bkflow.harness.services.facade import (
        P0_ACTION_RISK,
        P1_ACTION_RISK,
        P2_ACTION_RISK,
        P3_ACTION_RISK,
        P4_ACTION_RISK,
    )

    risks = {**P0_ACTION_RISK, **P1_ACTION_RISK, **P2_ACTION_RISK, **P3_ACTION_RISK, **P4_ACTION_RISK}

    event = {
        "tool": method,
        "risk": risk if risk in {"L0", "L1", "L2", "L3"} else risks[method],
        "caller": _safe_identifier(context.actor),
        "space": context.space_id if isinstance(context.space_id, int) else None,
        "run": _safe_identifier(result.get("run_id")),
        "revision": _safe_identifier(result.get("revision_id")),
        "correlation": _safe_identifier(context.correlation_id),
        "result": result.get("ok") is True,
        "duration_ms": max(0, min(int(duration_ms), 2147483647)),
    }
    logger.info("harness audit", extra={"harness_audit": event})


def _idempotency_header_matches(request, serializer_class):
    """Treat the optional header only as a body-key consistency assertion."""
    policy = getattr(serializer_class, "idempotency_header_policy", "ignore")
    header = request.META.get("HTTP_X_IDEMPOTENCY_KEY")
    if header is None or policy == "ignore":
        return True
    if policy == "reject":
        return False
    try:
        body = request.data
    except Exception:
        return False
    return (
        policy == "match_body"
        and isinstance(body, Mapping)
        and is_safe_idempotency_key(header)
        and body.get("idempotency_key") == header
    )


def dispatch(request, serializer_class, method):
    """Parse transport input then invoke exactly one Facade method."""
    from bkflow.harness.contracts import HarnessContextError
    from bkflow.harness.services.contract_versions import require_tool_enabled
    from bkflow.harness.services.facade import HarnessFacade

    context = request.harness_context
    started = time.monotonic()
    audit_risk = None
    try:
        require_tool_enabled(context, method)
    except HarnessContextError as error:
        result = _failure_envelope(context, error.code, category="PERMISSION")
    except DatabaseError as error:
        _log_failure(context, method, error)
        result = _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)
    else:
        if not _idempotency_header_matches(request, serializer_class):
            result = _failure_envelope(context)
        else:
            serializer = serializer_class(data=request.data)
            if not serializer.is_valid():
                result = envelope(context, serializer)
            else:
                if method == "control_workflow_execution":
                    from bkflow.harness.services.release.policy import ACTION_RISK

                    audit_risk = ACTION_RISK.get(serializer.validated_data.get("action"))
                try:
                    result = _safe_domain_result(
                        context,
                        getattr(HarnessFacade(), method)(context, serializer.validated_data),
                        method,
                    )
                except Exception as error:
                    _log_failure(context, method, error)
                    result = _failure_envelope(context, "RETRYABLE_INFRA", category="RETRYABLE_INFRA", retryable=True)
    result = _bounded_response(request, context, result, method)
    _audit(context, method, result, (time.monotonic() - started) * 1000, risk=audit_risk)
    return Response(result)
