"""Closed P4 feedback request and retention-policy contracts."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from bkflow.harness.constants import GenerationFeedbackType
from bkflow.harness.safety import is_safe_idempotency_key
from bkflow.harness.services.evidence import (
    is_safe_evidence_ref,
    redact_evidence_payload,
)
from bkflow.harness.services.knowledge.security import is_bounded_non_secret_text

MAX_FEEDBACK_SUMMARY_BYTES = 64 * 1024


class FeedbackIntakeRejected(ValueError):
    """A normalized rejection that never includes caller-controlled content."""

    def __init__(self, code, path, *, repairable=True, retryable=False):
        self.code = code
        self.path = path
        self.repairable = repairable
        self.retryable = retryable
        super().__init__(code)


def _uuid_text(value, path):
    """Return one canonical UUID string without reflecting invalid input."""
    try:
        return str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError):
        raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", path) from None


def _sha256_text(value, path):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", path)
    return value


@dataclass(frozen=True)
class FeedbackRetentionPolicy:
    """Explicit deployment decision required before retaining real feedback."""

    enabled: bool
    policy_version: str = None
    allowed_consent_scopes: tuple = ()
    retention_days: int = None

    @classmethod
    def disabled(cls):
        """Represent the P4 Task 1 `intake_disabled` fail-closed mode."""
        return cls(enabled=False)

    @classmethod
    def approved(cls, *, policy_version, allowed_consent_scopes, retention_days):
        """Build one pre-approved, bounded retention decision."""
        scopes = tuple(allowed_consent_scopes)
        if (
            not is_bounded_non_secret_text(policy_version, 64)
            or isinstance(retention_days, bool)
            or not isinstance(retention_days, int)
            or not 1 <= retention_days <= 3650
            or not scopes
            or len(scopes) > 20
            or len(scopes) != len(set(scopes))
            or not all(is_bounded_non_secret_text(scope, 64) for scope in scopes)
        ):
            raise ValueError("invalid feedback retention policy")
        return cls(
            enabled=True,
            policy_version=policy_version,
            allowed_consent_scopes=scopes,
            retention_days=retention_days,
        )

    def allows(self, consent_scope):
        return self.enabled is True and consent_scope in self.allowed_consent_scopes


@dataclass(frozen=True)
class GenerationFeedbackRequest:
    """Validated user observation containing no authority or lifecycle fields."""

    run_id: str
    revision_id: str
    expected_plan_hash: str
    feedback_type: str
    consent_scope: str
    idempotency_key: str
    rating: int = None
    summary: str = None
    correction_artifact_ref: str = None
    execution_id: str = None
    observed_outcome: object = None

    ALLOWED_FIELDS = frozenset(
        {
            "run_id",
            "revision_id",
            "expected_plan_hash",
            "feedback_type",
            "consent_scope",
            "idempotency_key",
            "rating",
            "summary",
            "correction_artifact_ref",
            "execution_id",
            "observed_outcome",
        }
    )

    @classmethod
    def from_payload(cls, payload):
        """Reject unknown fields before any trusted reference or artifact lookup."""
        if not isinstance(payload, Mapping) or set(payload) - cls.ALLOWED_FIELDS:
            raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "request")
        required = {
            "run_id",
            "revision_id",
            "expected_plan_hash",
            "feedback_type",
            "consent_scope",
            "idempotency_key",
        }
        if not required.issubset(payload):
            raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "request")
        summary = payload.get("summary")
        if summary is not None:
            if not isinstance(summary, str):
                raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "summary")
            try:
                summary_bytes = len(summary.encode("utf-8"))
            except UnicodeError:
                raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "summary") from None
            if summary_bytes > MAX_FEEDBACK_SUMMARY_BYTES:
                raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "summary")
        rating = payload.get("rating")
        if rating is not None and (isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5):
            raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "rating")
        feedback_type = payload.get("feedback_type")
        if feedback_type not in GenerationFeedbackType.values:
            raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "feedback_type")
        consent_scope = payload.get("consent_scope")
        if not is_bounded_non_secret_text(consent_scope, 64):
            raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "consent_scope")
        idempotency_key = payload.get("idempotency_key")
        if not is_safe_idempotency_key(idempotency_key):
            raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "idempotency_key")
        correction_ref = payload.get("correction_artifact_ref")
        if correction_ref is not None and not is_safe_evidence_ref(correction_ref):
            raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "correction_artifact_ref")
        observed_outcome = payload.get("observed_outcome", {})
        try:
            redact_evidence_payload(observed_outcome)
        except Exception:
            raise FeedbackIntakeRejected("SCHEMA_VALIDATION_ERROR", "observed_outcome") from None
        execution_id = payload.get("execution_id")
        return cls(
            run_id=_uuid_text(payload.get("run_id"), "run_id"),
            revision_id=_uuid_text(payload.get("revision_id"), "revision_id"),
            expected_plan_hash=_sha256_text(payload.get("expected_plan_hash"), "expected_plan_hash"),
            feedback_type=feedback_type,
            consent_scope=consent_scope,
            idempotency_key=idempotency_key,
            rating=rating,
            summary=summary,
            correction_artifact_ref=correction_ref,
            execution_id=_uuid_text(execution_id, "execution_id") if execution_id is not None else None,
            observed_outcome=observed_outcome,
        )

    def as_dict(self):
        """Return the stable request identity used only for canonical hashing."""
        return {
            "run_id": self.run_id,
            "revision_id": self.revision_id,
            "expected_plan_hash": self.expected_plan_hash,
            "feedback_type": self.feedback_type,
            "consent_scope": self.consent_scope,
            "idempotency_key": self.idempotency_key,
            "rating": self.rating,
            "summary": self.summary,
            "correction_artifact_ref": self.correction_artifact_ref,
            "execution_id": self.execution_id,
            "observed_outcome": self.observed_outcome,
        }
