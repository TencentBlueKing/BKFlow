"""Non-mutating redaction boundary for untrusted knowledge payloads."""

import re
from collections.abc import Mapping

from bkflow.harness.services.knowledge.contracts import KNOWLEDGE_REDACTION_BASELINE
from bkflow.harness.services.knowledge.security import (
    REDACTED_VALUE,
    is_sensitive_key,
    normalized_secret_key,
    redact_sensitive_text,
)

REDACTED_CYCLE_VALUE = "[REDACTED_CYCLE]"
MAX_POLICY_VERSION_BYTES = 128
MAX_CREDENTIAL_REF_BYTES = 255

_CREDENTIAL_REF = re.compile(r"^credential://id/([1-9][0-9]{0,18})$")


def _safe_credential_ref(value):
    """Accept only the bounded opaque credential URI shape persisted by trusted bindings."""
    if not isinstance(value, str):
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        return False
    return len(encoded) <= MAX_CREDENTIAL_REF_BYTES and _CREDENTIAL_REF.fullmatch(value) is not None


def _redact(value, active_containers):
    """Recursively clone supported payload containers and remove credential material."""
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active_containers:
            return REDACTED_CYCLE_VALUE
        active_containers.add(identity)
        try:
            return {
                key: (
                    item
                    if normalized_secret_key(key) == "credential_ref" and _safe_credential_ref(item)
                    else (
                        REDACTED_VALUE
                        if is_sensitive_key(key) or normalized_secret_key(key) == "credential_ref"
                        else _redact(item, active_containers)
                    )
                )
                for key, item in value.items()
            }
        finally:
            active_containers.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active_containers:
            return REDACTED_CYCLE_VALUE
        active_containers.add(identity)
        try:
            redacted = [_redact(item, active_containers) for item in value]
            return tuple(redacted) if isinstance(value, tuple) else redacted
        finally:
            active_containers.remove(identity)
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value


def knowledge_redaction_baseline(policy_version):
    """Map every bounded policy provenance label to the mandatory P1 built-in baseline."""
    if (
        not isinstance(policy_version, str)
        or not policy_version
        or len(policy_version.encode("utf-8")) > MAX_POLICY_VERSION_BYTES
    ):
        raise ValueError("policy_version must be a bounded non-empty string")
    return KNOWLEDGE_REDACTION_BASELINE


def redact_knowledge_payload(value, policy_version):
    """Apply the mandatory built-in baseline; labels are provenance only and cannot weaken it."""
    knowledge_redaction_baseline(policy_version)
    return _redact(value, set())
