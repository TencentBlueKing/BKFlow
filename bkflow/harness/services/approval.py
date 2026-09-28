"""Fail-closed, action-bound approval receipt verification."""

import hashlib
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime

from django.utils import timezone

from bkflow.harness.constants import HarnessAction
from bkflow.harness.safety import is_bounded_non_secret_json, is_safe_harness_text
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.knowledge.security import is_safe_opaque_uri


class ApprovalInvalid(ValueError):
    """The configured verifier returned a malformed unsafe decision."""


class InMemoryApprovalReplayGuard:
    """Process-local replay guard for tests; production must inject a durable guard."""

    def __init__(self):
        self._claimed = set()
        self._lock = threading.Lock()

    def claim_once(self, receipt_digest, claims_digest, expires_at):
        """Atomically claim one receipt identity inside this process."""
        key = receipt_digest
        with self._lock:
            if key in self._claimed:
                return False
            self._claimed.add(key)
            return True


@dataclass(frozen=True)
class ApprovalDecision:
    """Normalized non-secret verifier decision safe for Evidence."""

    allowed: bool
    provider: str
    receipt_digest: str
    claims_digest: str
    reason: str
    verifier_version: str = ""
    expires_at: datetime = None

    @property
    def failure_code(self):
        """Map verifier absence separately from invalid or uncertain evidence."""
        if self.allowed:
            return None
        return "APPROVAL_REQUIRED" if self.reason == "verifier_unavailable" else "APPROVAL_INVALID"

    def __repr__(self):
        return (
            "ApprovalDecision(allowed={!r}, provider={!r}, receipt_digest={!r}, "
            "claims_digest={!r}, reason={!r}, verifier_version={!r})"
        ).format(
            self.allowed,
            self.provider,
            self.receipt_digest,
            self.claims_digest,
            self.reason,
            self.verifier_version,
        )


def _json_claims(value):
    """Normalize the closed, scalar claim map without traversing provider graphs."""
    if not isinstance(value, dict):
        raise ValueError("approval claims must be an object")
    normalized = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("approval claim names must be strings")
        if isinstance(item, (datetime, date)):
            normalized[key] = item.isoformat()
        elif item is None or isinstance(item, (bool, int, float, str)):
            normalized[key] = item
        else:
            raise ValueError("approval claim values must be scalar")
    return normalized


def _receipt_digest(receipt_ref):
    value = receipt_ref if isinstance(receipt_ref, str) else "invalid-receipt-reference"
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _decision(receipt_ref, expected_claims, reason, *, provider="unconfigured"):
    try:
        claims = _json_claims(expected_claims)
    except (TypeError, ValueError, UnicodeError):
        claims = {}
    return ApprovalDecision(
        allowed=False,
        provider=provider,
        receipt_digest=_receipt_digest(receipt_ref),
        claims_digest=sha256_json(claims),
        reason=reason,
    )


def _is_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _valid_expected_claims(value, schemas):
    """Validate types and closed action authority for P2 and P3 claim shapes."""
    keys = frozenset(value)
    if keys not in schemas:
        return False
    if isinstance(value.get("space_id"), bool) or not isinstance(value.get("space_id"), int) or value["space_id"] <= 0:
        return False
    common_text = ("actor", "platform_app", "environment", "action")
    if any(not is_safe_harness_text(value.get(name), max_chars=255, allow_empty=False) for name in common_text):
        return False
    if not _is_hash(value.get("plan_hash")):
        return False
    if "action_digest" in value:
        return (
            _is_hash(value.get("action_digest"))
            and value.get("action") in HarnessAction.values
            and is_safe_harness_text(value.get("scope"), max_chars=255, allow_empty=False)
        )
    expires_after = value.get("expires_after")
    try:
        parsed_expiry = datetime.fromisoformat(expires_after)
    except (TypeError, ValueError):
        return False
    return (
        value.get("action") == "run_debug_real_step"
        and timezone.is_aware(parsed_expiry)
        and all(
            is_safe_harness_text(value.get(name), max_chars=255, allow_empty=False)
            for name in ("scope_type", "scope_value", "node_id")
        )
    )


class ApprovalVerifier:
    """Verify closed provider receipts against complete immutable expected claims."""

    EXPECTED_CLAIM_SCHEMAS = (
        frozenset(
            {
                "actor",
                "platform_app",
                "space_id",
                "scope",
                "environment",
                "plan_hash",
                "action",
                "action_digest",
            }
        ),
        frozenset(
            {
                "actor",
                "platform_app",
                "space_id",
                "scope_type",
                "scope_value",
                "environment",
                "plan_hash",
                "action",
                "node_id",
                "expires_after",
            }
        ),
    )
    RESPONSE_FIELDS = frozenset(
        {
            "allowed",
            "provider",
            "receipt_ref",
            "claims",
            "expires_at",
            "revoked",
            "reason",
            "verifier_version",
        }
    )

    def __init__(self, backend=None, replay_guard=None):
        self._backend = backend
        self._replay_guard = replay_guard

    def verify(self, receipt_ref, expected_claims):
        """Return a safe decision; never raise or trust caller/prompt approval text."""
        try:
            expected = _json_claims(expected_claims)
        except (TypeError, ValueError, UnicodeError):
            return _decision(receipt_ref, {}, "invalid_expected_claims")
        if (
            not is_safe_opaque_uri(receipt_ref, "approval", 255)
            or not isinstance(expected, dict)
            or not is_bounded_non_secret_json(expected)
        ):
            return _decision(receipt_ref, expected_claims, "invalid_verifier_result")
        if not _valid_expected_claims(expected, self.EXPECTED_CLAIM_SCHEMAS):
            return _decision(receipt_ref, expected, "invalid_expected_claims")
        if self._backend is None:
            return _decision(receipt_ref, expected, "verifier_unavailable")
        try:
            result = self._backend.verify(receipt_ref)
        except Exception:
            return _decision(receipt_ref, expected, "verifier_uncertain", provider="configured")
        if not isinstance(result, dict) or set(result) != self.RESPONSE_FIELDS:
            return _decision(receipt_ref, expected, "invalid_verifier_result", provider="configured")

        provider = result.get("provider")
        if not is_safe_harness_text(provider, max_chars=64, max_bytes=256, allow_empty=False):
            return _decision(receipt_ref, expected, "invalid_verifier_result", provider="configured")
        if result.get("receipt_ref") != receipt_ref:
            return _decision(receipt_ref, expected, "receipt_mismatch", provider=provider)
        if not isinstance(result.get("allowed"), bool) or not isinstance(result.get("revoked"), bool):
            return _decision(receipt_ref, expected, "invalid_verifier_result", provider=provider)
        expires_at = result.get("expires_at")
        if not isinstance(expires_at, datetime) or timezone.is_naive(expires_at):
            return _decision(receipt_ref, expected, "invalid_verifier_result", provider=provider)
        if result["revoked"]:
            return _decision(receipt_ref, expected, "receipt_revoked", provider=provider)
        if expires_at <= timezone.now():
            return _decision(receipt_ref, expected, "receipt_expired", provider=provider)
        try:
            provider_claims = _json_claims(result.get("claims"))
        except (TypeError, ValueError, UnicodeError):
            return _decision(receipt_ref, expected, "invalid_verifier_result", provider=provider)
        if provider_claims != expected:
            return _decision(receipt_ref, expected, "claim_mismatch", provider=provider)
        reason = result.get("reason")
        verifier_version = result.get("verifier_version")
        if not is_safe_harness_text(
            reason, max_chars=128, max_bytes=512, allow_empty=False
        ) or not is_safe_harness_text(verifier_version, max_chars=64, max_bytes=256, allow_empty=False):
            return _decision(receipt_ref, expected, "invalid_verifier_result", provider=provider)
        if not result["allowed"]:
            return _decision(receipt_ref, expected, reason, provider=provider)

        digest = _receipt_digest(receipt_ref)
        claims_digest = sha256_json(expected)
        if self._replay_guard is None:
            return _decision(receipt_ref, expected, "replay_guard_unavailable", provider=provider)
        try:
            claimed = self._replay_guard.claim_once(digest, claims_digest, expires_at)
        except Exception:
            return _decision(receipt_ref, expected, "replay_guard_uncertain", provider=provider)
        if claimed is not True:
            return _decision(receipt_ref, expected, "receipt_reused", provider=provider)
        return ApprovalDecision(
            allowed=True,
            provider=provider,
            receipt_digest=digest,
            claims_digest=claims_digest,
            reason=reason,
            verifier_version=verifier_version,
            expires_at=expires_at,
        )


def normalize_approval_decision(decision, receipt_ref):
    """Validate a custom verifier output retained for P2 adapter compatibility."""
    expected_receipt_digest = _receipt_digest(receipt_ref)
    if (
        not isinstance(decision, ApprovalDecision)
        or not isinstance(decision.allowed, bool)
        or not is_safe_harness_text(decision.provider, max_chars=64, max_bytes=256, allow_empty=False)
        or decision.receipt_digest != expected_receipt_digest
        or not isinstance(decision.claims_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", decision.claims_digest) is None
        or not is_safe_harness_text(decision.reason, max_chars=128, max_bytes=512, allow_empty=False)
    ):
        raise ApprovalInvalid("approval verifier returned an invalid decision")
    return decision
