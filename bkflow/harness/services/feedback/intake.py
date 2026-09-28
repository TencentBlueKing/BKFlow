"""Bounded, idempotent P4 feedback persistence over trusted Harness provenance."""

import hashlib

from django.db import transaction

from bkflow.harness.models import (
    EvidenceBundle,
    ExecutionRun,
    GenerationFeedback,
    HarnessRun,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import canonical_scope, sha256_json
from bkflow.harness.services.evidence import (
    EVIDENCE_REDACTION_VERSION,
    is_safe_evidence_ref,
    record_feedback_evidence,
    redact_evidence_payload,
)
from bkflow.harness.services.feedback.contracts import FeedbackIntakeRejected
from bkflow.harness.services.idempotency import (
    IdempotencyOutcome,
    IdempotencyScope,
    execute_idempotent,
)
from bkflow.harness.services.knowledge.security import redact_sensitive_text

TOOL_NAME = "submit_generation_feedback"
MAX_INLINE_SUMMARY_BYTES = 8 * 1024
_EMPTY_SUMMARY = "No textual summary provided."


def _trusted_run(context, run_id):
    """Resolve one run only through the complete server-owned authority tuple."""
    try:
        scope = canonical_scope(context.scope_type, context.scope_value)
    except ValueError:
        raise FeedbackIntakeRejected("CAPABILITY_FORBIDDEN", "run_id", repairable=False) from None
    try:
        return HarnessRun.objects.get(
            run_id=run_id,
            platform=context.platform_key,
            platform_app=context.platform_app,
            actor=context.actor,
            space_id=context.space_id,
            scope=scope,
            environment=context.target_environment,
            policy_version=context.policy_version,
        )
    except HarnessRun.DoesNotExist:
        raise FeedbackIntakeRejected("CAPABILITY_FORBIDDEN", "run_id", repairable=False) from None


def _trusted_revision(run, request):
    try:
        revision = WorkflowPlanRevision.objects.get(pk=request.revision_id, run=run)
    except WorkflowPlanRevision.DoesNotExist:
        raise FeedbackIntakeRejected("CAPABILITY_FORBIDDEN", "revision_id", repairable=False) from None
    if revision.plan_hash != request.expected_plan_hash:
        raise FeedbackIntakeRejected("PLAN_HASH_MISMATCH", "expected_plan_hash")
    return revision


def _trusted_execution(run, revision, execution_id):
    if execution_id is None:
        return None
    try:
        return ExecutionRun.objects.get(pk=execution_id, run=run, revision=revision)
    except ExecutionRun.DoesNotExist:
        raise FeedbackIntakeRejected("CAPABILITY_FORBIDDEN", "execution_id", repairable=False) from None


def _run_owns_artifact_ref(run, artifact_ref):
    """Match only explicit run artifact coordinates without dereferencing caller input."""
    if artifact_ref is None:
        return True
    for item in run.artifact_references:
        if item == artifact_ref:
            return True
        if isinstance(item, dict) and item.get("artifact_ref") == artifact_ref:
            return True
    return False


def _evidence_bundle(run, revision, execution):
    query = EvidenceBundle.objects.filter(run=run, revision=revision)
    if execution is not None:
        query = query.filter(execution=execution)
    return query.order_by("-finalized_at").first()


def _redacted_summary(summary, artifact_writer):
    """Redact first, then keep bounded inline text or one safe artifact reference."""
    summary = _EMPTY_SUMMARY if summary is None else summary
    redacted = redact_sensitive_text(summary)
    if len(redacted.encode("utf-8")) <= MAX_INLINE_SUMMARY_BYTES:
        return redacted, None
    if not callable(artifact_writer):
        raise FeedbackIntakeRejected("RETRYABLE_INFRA", "summary", retryable=True)
    try:
        artifact_ref = artifact_writer(
            {
                "type": "generation_feedback_summary",
                "content": redacted,
                "redaction_version": EVIDENCE_REDACTION_VERSION,
            }
        )
    except Exception:
        raise FeedbackIntakeRejected("RETRYABLE_INFRA", "summary", retryable=True) from None
    if not is_safe_evidence_ref(artifact_ref):
        raise FeedbackIntakeRejected("RETRYABLE_INFRA", "summary", retryable=True)
    return "[EXTERNALIZED] {}".format(artifact_ref), artifact_ref


def _idempotency_digest(context, run, idempotency_key):
    payload = "\x1f".join(
        (
            context.platform_app,
            context.actor,
            str(context.space_id),
            str(run.run_id),
            idempotency_key,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _response(context, run, revision, feedback, evidence, summary_artifact_ref):
    artifact = {
        "type": "generation_feedback",
        "feedback_ref": "feedback://generation/{}".format(feedback.id),
        "evidence_ref": "evidence://feedback/{}".format(evidence.id),
    }
    if summary_artifact_ref is not None:
        artifact["summary_artifact_ref"] = summary_artifact_ref
    return {
        "ok": True,
        "run_id": str(run.run_id),
        "revision_id": str(revision.id),
        "plan_hash": revision.plan_hash,
        "status": "FEEDBACK_RECORDED",
        "summary": "Generation feedback was recorded as untrusted evidence.",
        "artifact_refs": [artifact],
        "errors": [],
        "next_actions": [],
        "correlation_id": context.correlation_id,
    }


def submit_generation_feedback(context, request, *, retention_policy, artifact_writer=None):
    """Record one observation and Evidence event, never an improvement candidate."""
    run = _trusted_run(context, request.run_id)
    revision = _trusted_revision(run, request)
    execution = _trusted_execution(run, revision, request.execution_id)
    if not _run_owns_artifact_ref(run, request.correction_artifact_ref):
        raise FeedbackIntakeRejected("CAPABILITY_FORBIDDEN", "correction_artifact_ref", repairable=False)
    evidence_bundle = _evidence_bundle(run, revision, execution)
    scope = IdempotencyScope.for_run(
        context.platform_app,
        context.actor,
        context.space_id,
        TOOL_NAME,
        run,
        request.idempotency_key,
    )
    request_hash = sha256_json(
        {
            "request": request.as_dict(),
            "trusted_context": {
                "platform": context.platform_key,
                "platform_app": context.platform_app,
                "actor": context.actor,
                "space_id": context.space_id,
                "scope": run.scope,
                "environment": context.target_environment,
                "policy_version": context.policy_version,
                "mcp_contract_version": context.mcp_contract_version,
                "retention_policy_version": retention_policy.policy_version,
            },
        }
    )

    def persist_once():
        with transaction.atomic():
            locked_run = HarnessRun.objects.select_for_update().get(pk=run.pk)
            locked_revision = WorkflowPlanRevision.objects.get(pk=revision.pk, run=locked_run)
            if locked_revision.plan_hash != request.expected_plan_hash:
                raise FeedbackIntakeRejected("PLAN_HASH_MISMATCH", "expected_plan_hash")
            redacted_summary, summary_artifact_ref = _redacted_summary(request.summary, artifact_writer)
            redacted_outcome = redact_evidence_payload(request.observed_outcome)
            feedback = GenerationFeedback.objects.create(
                run=locked_run,
                revision=locked_revision,
                plan_hash=locked_revision.plan_hash,
                execution=execution,
                evidence_bundle=evidence_bundle,
                platform=context.platform_key,
                platform_app=context.platform_app,
                actor=context.actor,
                space_id=context.space_id,
                scope=locked_run.scope,
                target_environment=context.target_environment,
                policy_version=context.policy_version,
                feedback_type=request.feedback_type,
                rating=request.rating,
                redacted_summary=redacted_summary,
                correction_artifact_ref=request.correction_artifact_ref,
                observed_outcome=redacted_outcome,
                consent_scope=request.consent_scope,
                idempotency_digest=_idempotency_digest(context, locked_run, request.idempotency_key),
                redaction_version=EVIDENCE_REDACTION_VERSION,
            )
            evidence = record_feedback_evidence(
                feedback=feedback,
                summary_artifact_ref=summary_artifact_ref,
                retention_policy_version=retention_policy.policy_version,
                retention_days=retention_policy.retention_days,
                correlation_id=context.correlation_id,
            )
            response = _response(
                context,
                locked_run,
                locked_revision,
                feedback,
                evidence,
                summary_artifact_ref,
            )
            return IdempotencyOutcome(
                response_snapshot=response,
                run=locked_run,
                resource_reference=str(feedback.id),
            )

    return execute_idempotent(scope, request_hash, persist_once).response_snapshot
