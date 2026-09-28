"""Stable Envelope boundary for P4 generation feedback intake."""

from django.core.exceptions import ValidationError
from django.db import DatabaseError

from bkflow.harness.contracts import HarnessContextError
from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.services.contract_versions import require_tool_enabled
from bkflow.harness.services.feedback.contracts import (
    FeedbackIntakeRejected,
    FeedbackRetentionPolicy,
    GenerationFeedbackRequest,
)
from bkflow.harness.services.feedback.intake import submit_generation_feedback
from bkflow.harness.services.validator import WorkflowValidationFailure


def _failure(context, rejection):
    error = WorkflowValidationFailure(
        rejection.code,
        path=rejection.path,
        repairable=rejection.repairable,
        retryable=rejection.retryable,
    ).as_error()
    return {
        "ok": False,
        "run_id": None,
        "revision_id": None,
        "plan_hash": None,
        "status": None,
        "summary": "Generation feedback was not recorded.",
        "artifact_refs": [],
        "errors": [error],
        "next_actions": [error["suggested_action"]],
        "correlation_id": context.correlation_id,
    }


def submit_generation_feedback_with_context(
    context,
    payload,
    *,
    retention_policy=None,
    artifact_writer=None,
):
    """Validate Tool, request, retention, and provenance before recording feedback."""
    try:
        require_tool_enabled(context, "submit_generation_feedback")
        request = GenerationFeedbackRequest.from_payload(payload)
        policy = retention_policy or FeedbackRetentionPolicy.disabled()
        if not isinstance(policy, FeedbackRetentionPolicy) or not policy.allows(request.consent_scope):
            raise FeedbackIntakeRejected("HARNESS_TOOL_UNAVAILABLE", "consent_scope", repairable=False)
        return submit_generation_feedback(
            context,
            request,
            retention_policy=policy,
            artifact_writer=artifact_writer,
        )
    except FeedbackIntakeRejected as rejection:
        return _failure(context, rejection)
    except HarnessContextError as error:
        return _failure(
            context,
            FeedbackIntakeRejected(error.code, "feedback", repairable=False),
        )
    except IdempotencyConflict:
        return _failure(
            context,
            FeedbackIntakeRejected("IDEMPOTENCY_CONFLICT", "idempotency_key", repairable=False),
        )
    except (IdempotencyInFlight, IdempotencyRecordImmutable, DatabaseError, ValidationError):
        return _failure(
            context,
            FeedbackIntakeRejected("RETRYABLE_INFRA", "feedback", retryable=True),
        )
    except Exception:
        return _failure(
            context,
            FeedbackIntakeRejected("RETRYABLE_INFRA", "feedback", retryable=True),
        )


__all__ = ["submit_generation_feedback_with_context"]
