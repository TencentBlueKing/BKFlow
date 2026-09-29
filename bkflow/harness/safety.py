"""Shared JSON and text-safety primitives for Harness boundaries."""

import json
import math
import re
import uuid

from bkflow.harness.services.knowledge.security import (
    is_sensitive_key,
    redact_sensitive_text,
)

MAX_HARNESS_TEXT_CHARS = 4096
MAX_HARNESS_TEXT_BYTES = 16384
MAX_OPAQUE_IDENTIFIER_CHARS = 128
MAX_IDEMPOTENCY_KEY_CHARS = 255
MAX_IDEMPOTENCY_KEY_BYTES = MAX_IDEMPOTENCY_KEY_CHARS * 4
MAX_HARNESS_JSON_DEPTH = 8
MAX_HARNESS_JSON_ITEMS = 100
MAX_HARNESS_JSON_KEY_CHARS = 128
MAX_HARNESS_JSON_STRING_CHARS = 4096
MAX_HARNESS_JSON_STRING_BYTES = 16384
MAX_HARNESS_JSON_TOTAL_BYTES = 65536

# Deliberately not a generic X-* exception: custom names may carry credentials.
PUBLIC_HTTP_HEADER_NAMES = frozenset(
    (
        "accept",
        "accept-language",
        "content-type",
        "content-language",
        "cache-control",
        "x-test-case",
        "x-request-id",
        "x-correlation-id",
    )
)
HTTP_HEADER_INPUT = "bk_http_request_header"

_SAFE_OPAQUE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SENSITIVE_JSON_KEY = re.compile(
    r"secret|token|password|credential|authorization|headers?|apikey|accesskey|^auth$",
    re.I,
)
_CREDENTIAL_URI = re.compile(r"credential://", re.I)
_BEARER_VALUE = re.compile(r"(?<![A-Za-z0-9])bearer\s+\S+", re.I)
_BKAPI_AUTHORIZATION_VALUE = re.compile(
    r"(?<![A-Za-z0-9])x[\s._-]*bkapi[\s._-]*authorization(?:\s*[:=]\s*|\s+)\S+",
    re.I,
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?<![A-Za-z0-9])['\"]?(?:"
    r"authorization|auth|credential|password|"
    r"(?:access|refresh|api|client|bk[\s._-]*app)?[\s._-]*token|"
    r"(?:api[\s._-]*key|apikey)|(?:client|bk[\s._-]*app)?[\s._-]*secret"
    r")[\s]*['\"]?[\s]*[:=][\s]*['\"]?\S+",
    re.I,
)


def contains_secret_shaped_text(value):
    """Return whether a string carries a credential prefix or secret assignment."""
    if not isinstance(value, str):
        return False
    if redact_sensitive_text(value) != value:
        return True
    return any(
        pattern.search(value) is not None
        for pattern in (
            _CREDENTIAL_URI,
            _BEARER_VALUE,
            _BKAPI_AUTHORIZATION_VALUE,
            _SECRET_ASSIGNMENT,
        )
    )


def contains_credential_uri(value):
    """Return whether a string embeds a runtime credential reference."""
    return isinstance(value, str) and _CREDENTIAL_URI.search(value) is not None


def is_harness_sensitive_key(key):
    """Apply built-in key redaction plus stricter Harness runtime aliases."""
    if not isinstance(key, str):
        return True
    normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
    return is_sensitive_key(key) or _SENSITIVE_JSON_KEY.search(normalized_key) is not None


def is_safe_harness_text(
    value,
    *,
    max_chars=MAX_HARNESS_TEXT_CHARS,
    max_bytes=MAX_HARNESS_TEXT_BYTES,
    allow_empty=True,
):
    """Accept one bounded UTF-8 string only when it is not secret-shaped."""
    if not isinstance(value, str) or (not allow_empty and not value) or len(value) > max_chars:
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        return False
    return len(encoded) <= max_bytes and not contains_secret_shaped_text(value)


def _is_public_http_header_field(path, key, value):
    """Recognize only a literal, closed public-header list at the a2flow input boundary."""
    if not (
        len(path) == 3
        and path[0] == "nodes"
        and isinstance(path[1], int)
        and path[2] in ("inputs", "data")
        and key == HTTP_HEADER_INPUT
    ):
        return False
    if isinstance(value, dict):
        if (
            set(value) not in ({"hook", "value"}, {"hook", "need_render", "value"})
            or value.get("hook") is not False
            or ("need_render" in value and not isinstance(value["need_render"], bool))
        ):
            return False
        value = value["value"]
    if not isinstance(value, list) or len(value) > MAX_HARNESS_JSON_ITEMS:
        return False
    for row in value:
        if not isinstance(row, dict) or set(row) != {"name", "value"}:
            return False
        if not isinstance(row["name"], str) or row["name"].lower() not in PUBLIC_HTTP_HEADER_NAMES:
            return False
        text = row["value"]
        if not is_safe_harness_text(text) or any(ord(char) < 32 or ord(char) == 127 for char in text):
            return False
        if "${" in text or "<%" in text:
            return False
    return True


def is_bounded_non_secret_json(value, *, allow_public_http_headers=False):
    """Accept strict JSON only within the shared Harness size and secret policy."""

    def visit(item, depth, path=()):
        if depth > MAX_HARNESS_JSON_DEPTH:
            return False
        if isinstance(item, dict):
            if len(item) > MAX_HARNESS_JSON_ITEMS:
                return False
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > MAX_HARNESS_JSON_KEY_CHARS:
                    return False
                permitted_header = allow_public_http_headers and _is_public_http_header_field(path, key, child)
                if (is_harness_sensitive_key(key) and not permitted_header) or not visit(
                    child, depth + 1, path + (key,)
                ):
                    return False
            return True
        if isinstance(item, list):
            return len(item) <= MAX_HARNESS_JSON_ITEMS and all(
                visit(child, depth + 1, path + (index,)) for index, child in enumerate(item)
            )
        if isinstance(item, str):
            return is_safe_harness_text(
                item,
                max_chars=MAX_HARNESS_JSON_STRING_CHARS,
                max_bytes=MAX_HARNESS_JSON_STRING_BYTES,
            )
        if isinstance(item, float):
            return math.isfinite(item)
        return item is None or isinstance(item, (bool, int))

    if not visit(value, 0):
        return False
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, UnicodeError, ValueError):
        return False
    return len(encoded) <= MAX_HARNESS_JSON_TOTAL_BYTES


def safe_opaque_identifier(value):
    """Return a bounded non-secret ASCII identifier, or ``None`` when unsafe."""
    if not is_safe_harness_text(
        value,
        max_chars=MAX_OPAQUE_IDENTIFIER_CHARS,
        max_bytes=MAX_OPAQUE_IDENTIFIER_CHARS,
        allow_empty=False,
    ):
        return None
    return value if _SAFE_OPAQUE_IDENTIFIER.fullmatch(value) else None


def is_safe_idempotency_key(value):
    """Validate the one raw client identifier persisted by both write Tools."""
    return is_safe_harness_text(
        value,
        max_chars=MAX_IDEMPOTENCY_KEY_CHARS,
        max_bytes=MAX_IDEMPOTENCY_KEY_BYTES,
        allow_empty=False,
    )


def normalize_correlation_id(value):
    """Keep a safe tracing identifier or replace it with a new opaque value."""
    return safe_opaque_identifier(value) or uuid.uuid4().hex
