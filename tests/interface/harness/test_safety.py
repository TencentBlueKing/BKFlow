"""Shared Harness string and correlation safety contracts."""

import pytest

from bkflow.harness.safety import (
    contains_secret_shaped_text,
    is_safe_harness_text,
    normalize_correlation_id,
)


@pytest.mark.parametrize(
    "value",
    [
        "credential://id/123",
        "Bearer opaque-value",
        "x-bkapi-authorization opaque-value",
        "X_BKAPI_AUTHORIZATION=opaque-value",
        "authorization: Basic opaque-value",
        "access_token=opaque-value",
        '"clientSecret": "opaque-value"',
        "bk-app-secret = opaque-value",
        "api.key=opaque-value",
    ],
)
def test_secret_prefixes_and_assignments_are_detected(value):
    """Separator and casing variants cannot disguise credential-bearing text."""
    assert contains_secret_shaped_text(value) is True
    assert is_safe_harness_text(value) is False


@pytest.mark.parametrize(
    "value",
    [
        "rotate token after approval",
        "document the authorization model",
        "secret management policy",
        "credential kinds are selected by the server",
        "token-rotation-discussion",
    ],
)
def test_ordinary_security_language_without_a_value_assignment_remains_compatible(value):
    """Security vocabulary alone is not credential material and remains valid user text."""
    assert contains_secret_shaped_text(value) is False
    assert is_safe_harness_text(value) is True


def test_text_safety_rejects_invalid_unicode_and_explicit_overflow():
    """The shared policy closes both UTF-8 and caller-selected character/byte bounds."""
    assert is_safe_harness_text("bad\ud800") is False
    assert is_safe_harness_text("😀" * 3, max_chars=3, max_bytes=12) is True
    assert is_safe_harness_text("😀" * 4, max_chars=3, max_bytes=12) is False


@pytest.mark.parametrize(
    "unsafe",
    ["Bearer C2-CORRELATION-SENTINEL", "x" * 129, "bad\ud800", "contains spaces"],
)
def test_correlation_normalization_preserves_only_safe_opaque_identifiers(unsafe):
    """Safe tracing remains stable while a secret-shaped candidate is replaced, never hashed."""
    assert normalize_correlation_id("trace-safe_123") == "trace-safe_123"
    replacement = normalize_correlation_id(unsafe)
    assert replacement != unsafe
    assert len(replacement) == 32
    int(replacement, 16)
