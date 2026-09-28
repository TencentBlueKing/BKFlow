"""Shared non-secret string and opaque-reference validation for knowledge boundaries."""

import base64
import binascii
import re
from urllib.parse import urlsplit

REDACTED_VALUE = "[REDACTED]"

_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "api_token",
    "app_secret",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "password",
    "passwd",
    "private_key",
    "secret",
    "set_cookie",
    "token",
}
_SENSITIVE_SUFFIXES = ("_access_token", "_api_key", "_api_token", "_app_secret", "_password", "_private_key")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----")
_TRUNCATED_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*$")
_BASIC_AUTHORIZATION = re.compile(r"\bbasic\s+([A-Za-z0-9+/]+={0,2})(?![A-Za-z0-9+/=])", re.IGNORECASE)
_BEARER_AUTHORIZATION = re.compile(r"\bbearer[ \t]+\S+", re.IGNORECASE)
_ASSIGNMENT_CANDIDATE = re.compile(
    r"\b(?P<key>[A-Za-z][A-Za-z0-9_-]*)(?P<before>[ \t]*)(?P<separator>[:=])"
    r"(?P<after>[ \t]*)(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;&]+)",
)
_EMBEDDED_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?P<prefix>[^A-Za-z0-9_-])"
    r"(?P<key>access[-_]?token|api[-_]?(?:key|token)|app[-_]?secret|authorization|cookie|credential(?:s)?|"
    r"passw(?:or)?d|private[-_]?key|secret|set[-_]?cookie|token)"
    r"(?P<before>[ \t]*)(?P<separator>[:=])(?P<after>[ \t]*)"
    r"(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;&]+)",
    re.IGNORECASE,
)
_COOKIE_HEADER = re.compile(r"\b(?:set[-_]?cookie|cookie)\s*:\s*[^\r\n]*", re.IGNORECASE)


def normalized_secret_key(key):
    """Normalize snake, kebab, header, and camel-case credential keys."""
    if not isinstance(key, str):
        return ""
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def is_sensitive_key(key):
    """Detect credential keys while retaining the dedicated credential-ref exception."""
    normalized = normalized_secret_key(key)
    if normalized == "credential_ref":
        return False
    return normalized in _SENSITIVE_KEYS or normalized.endswith(_SENSITIVE_SUFFIXES)


def _redact_basic_authorization(match):
    """Redact only Basic values that decode to the required user/password shape."""
    token = match.group(1)
    try:
        decoded = base64.b64decode(token + "=" * (-len(token) % 4), validate=True)
    except (binascii.Error, ValueError):
        return match.group(0)
    return REDACTED_VALUE if b":" in decoded else match.group(0)


def _redact_assignment(match):
    """Apply the exact mapping-key sensitivity contract to assignment-shaped text."""
    if not is_sensitive_key(match.group("key")):
        return match.group(0)
    return "{key}{before}{separator}{after}{redacted}".format(
        key=match.group("key"),
        before=match.group("before"),
        separator=match.group("separator"),
        after=match.group("after"),
        redacted=REDACTED_VALUE,
    )


def _redact_embedded_assignment(match):
    """Redact assignments nested after URI/path delimiters without consuming the URI scheme."""
    return "{prefix}{key}{before}{separator}{after}{redacted}".format(
        prefix=match.group("prefix"),
        key=match.group("key"),
        before=match.group("before"),
        separator=match.group("separator"),
        after=match.group("after"),
        redacted=REDACTED_VALUE,
    )


def redact_sensitive_text(value):
    """Remove recognized credential fragments while retaining surrounding ordinary text."""
    redacted = _PRIVATE_KEY.sub(REDACTED_VALUE, value)
    redacted = _TRUNCATED_PRIVATE_KEY.sub(REDACTED_VALUE, redacted)
    redacted = _COOKIE_HEADER.sub("Cookie: {}".format(REDACTED_VALUE), redacted)
    redacted = _BASIC_AUTHORIZATION.sub(_redact_basic_authorization, redacted)
    redacted = _BEARER_AUTHORIZATION.sub(REDACTED_VALUE, redacted)
    redacted = _ASSIGNMENT_CANDIDATE.sub(_redact_assignment, redacted)
    return _EMBEDDED_SENSITIVE_ASSIGNMENT.sub(_redact_embedded_assignment, redacted)


def is_bounded_non_secret_text(value, max_bytes, allow_empty=False):
    """Validate a UTF-8 string by bytes and reject every built-in secret shape."""
    if not isinstance(value, str) or (not value and not allow_empty):
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        return False
    return len(encoded) <= max_bytes and redact_sensitive_text(value) == value


def is_safe_opaque_uri(value, scheme, max_bytes):
    """Accept one explicit opaque namespace without authority credentials or URL side channels."""
    if not is_bounded_non_secret_text(value, max_bytes):
        return False
    try:
        parsed = urlsplit(value)
        username = parsed.username
        password = parsed.password
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == scheme
        and bool(parsed.netloc)
        and username is None
        and password is None
        and "?" not in value
        and "#" not in value
        and not parsed.query
        and not parsed.fragment
        and not any(character.isspace() for character in value)
    )
