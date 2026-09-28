"""Bounded, non-secret evidence construction for Harness lifecycle events."""

import hashlib
import json
import math
from collections.abc import Mapping
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import IntegrityError, router, transaction
from django.utils import timezone

from bkflow.harness.safety import (
    contains_credential_uri,
    contains_secret_shaped_text,
    is_harness_sensitive_key,
)
from bkflow.harness.services.knowledge.security import (
    REDACTED_VALUE,
    is_bounded_non_secret_text,
    redact_sensitive_text,
)

EVIDENCE_REDACTION_VERSION = "builtin-credential-v1"
MAX_EVIDENCE_DEPTH = 8
MAX_EVIDENCE_ITEMS = 100
MAX_EVIDENCE_STRING_BYTES = 16 * 1024
MAX_EVIDENCE_TOTAL_BYTES = 64 * 1024
MAX_EVIDENCE_INLINE_BYTES = 8 * 1024
MAX_EVIDENCE_ARTIFACT_REFS = 20
MAX_PROJECTION_TOTAL_NODES = 1000
MAX_PROJECTION_TOTAL_TEXT_BYTES = 64 * 1024

_CYCLE_VALUE = "[CYCLE]"
_TRUNCATED_VALUE = "[TRUNCATED]"


def evidence_projection_omission_reason(value):
    """Return the fixed omission reason only for the exact safe marker shape."""
    expected = {
        "omitted": True,
        "reason": "projection_budget_exceeded",
        "redaction_version": EVIDENCE_REDACTION_VERSION,
    }
    return expected["reason"] if value == expected else None


def _canonical_bytes(value):
    """Serialize already-redacted JSON using the deterministic Harness representation."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _truncate_utf8(value, max_bytes, state):
    """Return a valid UTF-8 prefix no larger than ``max_bytes``."""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    state["requires_artifact"] = True
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _safe_mapping_key(key, state):
    """Keep bounded redacted string keys and reject non-JSON mapping keys."""
    if not isinstance(key, str):
        raise ValidationError("Evidence payload contains an unsupported key")
    try:
        redacted = redact_sensitive_text(key)
        return _truncate_utf8(redacted, 128, state)
    except UnicodeError:
        raise ValidationError("Evidence payload contains invalid text") from None


def _redact_value(value, *, depth, ancestors, state):
    """Recursively copy and redact one JSON value without following cycles forever."""
    if isinstance(value, str):
        try:
            if contains_credential_uri(value) or contains_secret_shaped_text(value):
                return REDACTED_VALUE
            return _truncate_utf8(value, MAX_EVIDENCE_STRING_BYTES, state)
        except UnicodeError:
            return _TRUNCATED_VALUE
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError("Evidence payload contains an unsupported number")
        return value
    if isinstance(value, (Mapping, list, tuple)):
        identity = id(value)
        if identity in ancestors:
            return _CYCLE_VALUE
        if depth >= MAX_EVIDENCE_DEPTH:
            state["requires_artifact"] = True
            return _TRUNCATED_VALUE
        ancestors.add(identity)
        try:
            if isinstance(value, Mapping):
                entries = []
                for original_key, original_value in value.items():
                    safe_key = _safe_mapping_key(original_key, state)
                    entries.append((safe_key, original_key, original_value))
                entries.sort(key=lambda item: (item[0], item[1]))
                result = {}
                for index, (safe_key, original_key, original_value) in enumerate(entries[:MAX_EVIDENCE_ITEMS]):
                    output_key = safe_key
                    if output_key in result:
                        output_key = "{}#{}".format(output_key, index)
                    result[output_key] = (
                        REDACTED_VALUE
                        if is_harness_sensitive_key(original_key)
                        else _redact_value(
                            original_value,
                            depth=depth + 1,
                            ancestors=ancestors,
                            state=state,
                        )
                    )
                if len(entries) > MAX_EVIDENCE_ITEMS:
                    state["requires_artifact"] = True
                    result["_truncated_items"] = len(entries) - MAX_EVIDENCE_ITEMS
                return result

            result = [
                _redact_value(item, depth=depth + 1, ancestors=ancestors, state=state)
                for item in value[:MAX_EVIDENCE_ITEMS]
            ]
            if len(value) > MAX_EVIDENCE_ITEMS:
                state["requires_artifact"] = True
                result.append(_TRUNCATED_VALUE)
            return result
        finally:
            ancestors.remove(identity)
    raise ValidationError("Evidence payload contains an unsupported value")


def _redact_with_metadata(payload, redaction_version):
    """Return bounded redacted JSON plus whether loss requires an external artifact."""
    if redaction_version != EVIDENCE_REDACTION_VERSION:
        raise ValidationError("Evidence redaction policy is unavailable")
    state = {"requires_artifact": False}
    redacted = _redact_value(payload, depth=0, ancestors=set(), state=state)
    encoded = _canonical_bytes(redacted)
    if len(encoded) <= MAX_EVIDENCE_TOTAL_BYTES:
        return redacted, state["requires_artifact"]
    return (
        {
            "_truncated": True,
            "_redacted_sha256": hashlib.sha256(encoded).hexdigest(),
        },
        True,
    )


def redact_evidence_payload(payload, *, redaction_version=EVIDENCE_REDACTION_VERSION):
    """Return one deterministic bounded deep copy with mandatory credential redaction.

    Unknown policy versions fail closed. Callers cannot replace or weaken the
    built-in key and text credential rules.
    """
    return _redact_with_metadata(payload, redaction_version)[0]


def _within_projection_work_budget(payload):
    """Reject expensive SDK projections before any credential regex is evaluated."""
    state = {"nodes": 0, "text_bytes": 0}

    def visit(value, depth, ancestors):
        state["nodes"] += 1
        if state["nodes"] > MAX_PROJECTION_TOTAL_NODES or depth > MAX_EVIDENCE_DEPTH:
            return False
        if isinstance(value, str):
            if len(value) > MAX_EVIDENCE_STRING_BYTES:
                return False
            try:
                state["text_bytes"] += len(value.encode("utf-8"))
            except UnicodeError:
                return False
            return state["text_bytes"] <= MAX_PROJECTION_TOTAL_TEXT_BYTES
        if value is None or isinstance(value, (bool, int)):
            return True
        if isinstance(value, float):
            return math.isfinite(value)
        if not isinstance(value, (Mapping, list, tuple)):
            return False
        identity = id(value)
        if identity in ancestors:
            return True
        if depth >= MAX_EVIDENCE_DEPTH or len(value) > MAX_EVIDENCE_ITEMS:
            return False
        ancestors.add(identity)
        try:
            if isinstance(value, Mapping):
                for key, item in value.items():
                    if not isinstance(key, str) or len(key) > 128:
                        return False
                    try:
                        state["text_bytes"] += len(key.encode("utf-8"))
                    except UnicodeError:
                        return False
                    if state["text_bytes"] > MAX_PROJECTION_TOTAL_TEXT_BYTES or not visit(item, depth + 1, ancestors):
                        return False
                return True
            return all(visit(item, depth + 1, ancestors) for item in value)
        finally:
            ancestors.remove(identity)

    return visit(payload, 0, set())


def project_evidence_payload(payload, *, inline_bytes=MAX_EVIDENCE_INLINE_BYTES):
    """Return safe inline data or constant omission metadata within fixed work."""
    if isinstance(inline_bytes, bool) or not isinstance(inline_bytes, int) or inline_bytes <= 0:
        raise ValidationError("Evidence inline projection budget is invalid")
    omitted = {
        "omitted": True,
        "reason": "projection_budget_exceeded",
        "redaction_version": EVIDENCE_REDACTION_VERSION,
    }
    if not _within_projection_work_budget(payload):
        return omitted
    redacted, requires_artifact = _redact_with_metadata(payload, EVIDENCE_REDACTION_VERSION)
    encoded = _canonical_bytes(redacted)
    if not requires_artifact and len(encoded) <= inline_bytes:
        return redacted
    return omitted


def prepare_evidence_artifact_payload(payload):
    """Return safe artifact content only when finite projection work was proven.

    Values outside the same depth, item, node, string, and total-text budget
    used by inline projection are deliberately not traversed or scanned again.
    Callers must keep the constant omission metadata instead of invoking an
    external writer for those values.
    """
    if not _within_projection_work_budget(payload):
        return None
    redacted, requires_artifact = _redact_with_metadata(payload, EVIDENCE_REDACTION_VERSION)
    if requires_artifact or len(_canonical_bytes(redacted)) > MAX_EVIDENCE_TOTAL_BYTES:
        return None
    return redacted


def is_safe_evidence_ref(value):
    """Validate a generic opaque artifact ref without credentials or URL side channels."""
    if not is_bounded_non_secret_text(value, 255):
        return False
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return False
    return (
        bool(parsed.scheme)
        and parsed.scheme not in {"credential", "http", "https"}
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and "?" not in value
        and "#" not in value
        and not parsed.query
        and not parsed.fragment
        and not any(character.isspace() for character in value)
    )


def validate_evidence_artifact_refs(refs):
    """Return whether refs are a bounded, duplicate-free list of safe opaque identifiers."""
    return (
        isinstance(refs, list)
        and len(refs) <= MAX_EVIDENCE_ARTIFACT_REFS
        and len(refs) == len(set(refs))
        and all(is_safe_evidence_ref(item) for item in refs)
    )


def validate_redacted_evidence_payload(payload):
    """Return whether direct model input is already redacted and fits the inline budget."""
    try:
        redacted = redact_evidence_payload(payload)
        return redacted == payload and len(_canonical_bytes(payload)) <= MAX_EVIDENCE_INLINE_BYTES
    except (TypeError, ValueError, ValidationError, UnicodeError):
        return False


def record_evidence(
    *,
    run,
    revision,
    event_type,
    action,
    payload,
    actor,
    correlation_id,
    debug_session=None,
    execution=None,
    artifact_writer=None,
    redaction_version=EVIDENCE_REDACTION_VERSION,
    occurred_at=None,
):
    """Redact before model construction and append one bounded evidence event.

    Oversized inline evidence requires a real writer. Writer exceptions and
    unsafe references are replaced with one constant validation error so raw
    credential material cannot escape through ordinary exception text.
    """
    redacted, requires_artifact = _redact_with_metadata(payload, redaction_version)
    needs_artifact = requires_artifact or len(_canonical_bytes(redacted)) > MAX_EVIDENCE_INLINE_BYTES
    inline_payload = {"externalized": True} if needs_artifact else redacted
    artifact_refs = ["artifact://pending/preflight"] if needs_artifact else []

    from bkflow.harness.models import EvidenceEvent

    values = {
        "run": run,
        "revision": revision,
        "debug_session": debug_session,
        "execution": execution,
        "event_type": event_type,
        "action": action,
        "redacted_payload": inline_payload,
        "artifact_refs": artifact_refs,
        "actor": actor,
        "correlation_id": correlation_id,
        "redaction_version": EVIDENCE_REDACTION_VERSION,
    }
    if occurred_at is not None:
        values["occurred_at"] = occurred_at

    # Fail before an external artifact side effect when authority, relations,
    # event metadata, or the already-redacted inline representation is invalid.
    # The pending ref exists only on this unsaved validation object.
    EvidenceEvent(**values).full_clean(validate_unique=False)

    if execution is not None and needs_artifact:
        raise ValidationError("Execution Evidence artifact outbox is unavailable")
    if needs_artifact:
        if not callable(artifact_writer):
            raise ValidationError("Evidence artifact storage is unavailable")
        try:
            artifact_ref = artifact_writer(redacted)
        except Exception:
            raise ValidationError("Evidence artifact storage failed") from None
        if not is_safe_evidence_ref(artifact_ref):
            raise ValidationError("Evidence artifact reference is invalid")
        artifact_refs = [artifact_ref]
        values["artifact_refs"] = artifact_refs
    return EvidenceEvent.objects.create(**values)


def record_feedback_evidence(
    *, feedback, summary_artifact_ref, retention_policy_version, retention_days, correlation_id
):
    """Append a compact provenance event without copying untrusted feedback text."""
    payload = {
        "feedback_ref": "feedback://generation/{}".format(feedback.id),
        "feedback_type": feedback.feedback_type,
        "execution_ref": "execution://harness/{}".format(feedback.execution_id) if feedback.execution_id else None,
        "evidence_bundle_ref": (
            "evidence-bundle://harness/{}".format(feedback.evidence_bundle_id) if feedback.evidence_bundle_id else None
        ),
        "rating_present": feedback.rating is not None,
        "consent_scope": feedback.consent_scope,
        "retention_state": "policy_bound",
        "retention_policy_version": retention_policy_version,
        "retention_days": retention_days,
        "summary_externalized": summary_artifact_ref is not None,
        "summary_artifact_ref": summary_artifact_ref,
    }
    return record_evidence(
        run=feedback.run,
        revision=feedback.revision,
        event_type="GENERATION_FEEDBACK_RECORDED",
        action="submit_generation_feedback",
        payload=payload,
        actor=feedback.actor,
        correlation_id=correlation_id,
    )


def finalize_evidence_bundle(execution, *, artifact_writer=None):
    """Close the event stream and finalize one bounded terminal EvidenceBundle.

    ``artifact_writer`` is reserved for a future durable outbox integration.
    Until that protocol exists, overflow fails closed without external effects.
    """
    from bkflow.harness.models import EvidenceBundle, EvidenceEvent, ExecutionRun

    if not isinstance(execution, ExecutionRun) or execution.pk is None:
        raise ValidationError("Evidence bundle requires a persisted execution")
    using = router.db_for_write(EvidenceBundle, instance=execution)
    with transaction.atomic(using=using):
        try:
            locked = (
                ExecutionRun._base_manager.using(using)
                .select_for_update()
                .select_related("run", "revision")
                .get(pk=execution.pk)
            )
        except ExecutionRun.DoesNotExist:
            raise ValidationError("Evidence bundle execution does not exist") from None
        existing = EvidenceBundle._base_manager.using(using).filter(execution_id=locked.pk).first()
        if existing is not None:
            return existing
        if locked.status not in locked.TERMINAL or locked.postcondition_status in {
            locked.PostconditionStatus.PENDING,
            locked.PostconditionStatus.RUNNING,
        }:
            raise ValidationError("Evidence bundle requires terminal execution and completed postconditions")

        event_rows = list(
            EvidenceEvent._base_manager.using(using)
            .filter(execution_id=locked.pk, run_id=locked.run_id, revision_id=locked.revision_id)
            .order_by("occurred_at", "id")
            .values_list("id", "artifact_refs")[: MAX_EVIDENCE_ITEMS + 1]
        )
        if not event_rows:
            raise ValidationError("Evidence bundle requires execution Evidence")
        if len(event_rows) > MAX_EVIDENCE_ITEMS:
            raise ValidationError("Evidence bundle exceeds the event reference budget")
        event_refs = [str(event_id) for event_id, _artifact_refs in event_rows]
        artifact_refs = []
        seen = set()
        for _event_id, event_artifact_refs in event_rows:
            for reference in event_artifact_refs:
                if reference not in seen:
                    seen.add(reference)
                    artifact_refs.append(reference)
                if len(artifact_refs) > MAX_EVIDENCE_ITEMS:
                    raise ValidationError("Evidence bundle exceeds the artifact reference budget")
        outcome = {
            ExecutionRun.Status.SUCCEEDED: EvidenceBundle.Outcome.SUCCEEDED,
            ExecutionRun.Status.FAILED: EvidenceBundle.Outcome.FAILED,
            ExecutionRun.Status.CANCELLED: EvidenceBundle.Outcome.CANCELLED,
        }[locked.status]
        values = {
            "run": locked.run,
            "revision": locked.revision,
            "execution": locked,
            "evidence_event_refs": event_refs,
            "artifact_refs": artifact_refs,
            "redaction_version": EVIDENCE_REDACTION_VERSION,
            "outcome": outcome,
            "finalized_at": max(filter(None, (locked.terminal_at, timezone.now()))),
            "retention_class": EvidenceBundle.RetentionClass.STANDARD,
        }
        try:
            with transaction.atomic(using=using):
                return EvidenceBundle._base_manager.using(using).create(**values)
        except IntegrityError:
            existing = EvidenceBundle._base_manager.using(using).filter(execution_id=locked.pk).first()
            if existing is None:
                raise
            return existing
