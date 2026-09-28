"""Fail-closed evidence redaction and artifact externalization tests."""

import json

import pytest
from django.core.exceptions import ValidationError

from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.models import EvidenceEvent, HarnessRun, WorkflowPlanRevision
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.evidence import (
    EVIDENCE_REDACTION_VERSION,
    MAX_EVIDENCE_DEPTH,
    MAX_EVIDENCE_INLINE_BYTES,
    MAX_EVIDENCE_ITEMS,
    MAX_EVIDENCE_STRING_BYTES,
    project_evidence_payload,
    record_evidence,
    redact_evidence_payload,
)


@pytest.fixture
def run_and_revision(db):
    """Persist the run/revision authority for evidence tests."""
    run = HarnessRun.objects.create(
        platform="bkaidev",
        platform_app="trusted-app",
        actor="dannydeng",
        space_id=902,
        scope=canonical_scope("project", "902"),
        environment="stag",
        status=HarnessRunStatus.DEBUGGING,
        policy_version="risk-2026.09",
        mcp_contract_version="1.2.0",
    )
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={},
        canonical_a2flow={},
        plan_hash="a" * 64,
    )
    return run, revision


def record_values(run, revision, **overrides):
    """Build one record_evidence call without caller-controlled authority fields."""
    values = {
        "run": run,
        "revision": revision,
        "event_type": "DEBUG_STEP_COMPLETED",
        "action": "run_debug",
        "payload": {"result": "ok"},
        "actor": "dannydeng",
        "correlation_id": "p2-evidence-test",
    }
    values.update(overrides)
    return values


def canonical_bytes(value):
    """Serialize expected evidence independently from the implementation helper."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def test_redaction_is_recursive_cycle_safe_stable_and_non_mutating():
    """Nested credentials and cycles become deterministic safe markers without changing caller input."""
    nested = {"authorization": "Bearer raw-auth", "ordinary": "token=raw-inline"}
    payload = {"z": [nested], "password": "raw-password", "a": {"safe": "value"}}
    payload["cycle"] = payload

    first = redact_evidence_payload(payload)
    second = redact_evidence_payload(payload)

    assert list(first) == ["a", "cycle", "password", "z"]
    assert first == second
    assert first["password"] == "[REDACTED]"
    assert first["z"][0]["authorization"] == "[REDACTED]"
    assert first["z"][0]["ordinary"] == "[REDACTED]"
    assert first["cycle"] == "[CYCLE]"
    assert nested == {"authorization": "Bearer raw-auth", "ordinary": "token=raw-inline"}
    assert payload["cycle"] is payload
    assert "raw-auth" not in canonical_bytes(first).decode("utf-8")
    assert "raw-password" not in canonical_bytes(first).decode("utf-8")


@pytest.mark.parametrize(
    "value",
    [
        'Authorization: Digest username="user", response="raw-digest"',
        "X-Safe: visible\r\nCookie: session=raw-cookie\r\nX-Other: visible",
    ],
)
def test_secret_shaped_text_is_redacted_as_one_indivisible_value(value):
    """Partial header redaction cannot leave credential structure or sibling fragments."""
    assert redact_evidence_payload({"message": value}) == {"message": "[REDACTED]"}


def test_projection_budget_omits_without_digesting_truncated_content(monkeypatch):
    """Large values are rejected before regex work and distinct tails share no false digest."""
    from bkflow.harness.services import evidence

    regex_scan = monkeypatch.setattr(
        evidence,
        "contains_secret_shaped_text",
        lambda _value: (_ for _ in ()).throw(AssertionError("regex must not inspect oversized text")),
    )
    first = project_evidence_payload({"large": "x" * 20000 + "first-tail"})
    second = project_evidence_payload({"large": "x" * 20000 + "second-tail"})

    assert regex_scan is None
    assert (
        first
        == second
        == {
            "omitted": True,
            "reason": "projection_budget_exceeded",
            "redaction_version": EVIDENCE_REDACTION_VERSION,
        }
    )
    assert "content_sha256" not in first
    assert "redacted_size_bytes" not in first


def test_redaction_bounds_utf8_depth_items_strings_and_total_output():
    """Adversarial JSON cannot exceed the fixed evidence recursion and byte budgets."""
    deep = {"value": "leaf"}
    for _index in range(MAX_EVIDENCE_DEPTH + 3):
        deep = {"nested": deep}
    payload = {
        "items": list(range(MAX_EVIDENCE_ITEMS + 20)),
        "unicode": "😀" * (MAX_EVIDENCE_STRING_BYTES + 20),
        "deep": deep,
    }

    redacted = redact_evidence_payload(payload)
    encoded = canonical_bytes(redacted)

    assert len(encoded) <= 64 * 1024
    assert len(redacted["items"]) <= MAX_EVIDENCE_ITEMS + 1
    assert len(redacted["unicode"].encode("utf-8")) <= MAX_EVIDENCE_STRING_BYTES
    assert "[TRUNCATED]" in encoded.decode("utf-8")


def test_unknown_redaction_version_fails_without_echoing_caller_data():
    """A caller cannot select an unknown policy to weaken built-in credential removal."""
    sentinel = "raw-token-must-not-escape"

    with pytest.raises(ValidationError) as error:
        redact_evidence_payload({"token": sentinel}, redaction_version="caller-policy")

    assert sentinel not in str(error.value)


@pytest.mark.django_db
def test_record_evidence_redacts_before_model_construction_and_persistence(run_and_revision, monkeypatch):
    """Raw credentials are absent from constructor arguments and the durable event row."""
    run, revision = run_and_revision
    sentinel = "raw-constructor-secret"
    captured = {}
    real_create = EvidenceEvent.objects.create

    def checked_create(**kwargs):
        captured.update(kwargs)
        assert sentinel not in repr(kwargs)
        return real_create(**kwargs)

    monkeypatch.setattr(EvidenceEvent.objects, "create", checked_create)
    event = record_evidence(
        **record_values(
            run,
            revision,
            payload={"credential": sentinel, "message": "Authorization: Bearer {}".format(sentinel)},
        )
    )

    persisted = EvidenceEvent.objects.get(pk=event.pk)
    assert captured["redaction_version"] == EVIDENCE_REDACTION_VERSION
    assert sentinel not in repr(captured)
    assert sentinel not in repr(persisted.redacted_payload)
    assert persisted.redacted_payload["credential"] == "[REDACTED]"


@pytest.mark.django_db
def test_large_evidence_writes_only_redacted_artifact_and_safe_reference(run_and_revision):
    """Large safe content is externalized after redaction and only its opaque ref stays inline."""
    run, revision = run_and_revision
    sentinel = "raw-large-secret"
    written = []

    def artifact_writer(payload):
        written.append(payload)
        return "artifact://evidence/sha256/abc123"

    event = record_evidence(
        **record_values(
            run,
            revision,
            payload={"token": sentinel, "content": "x" * (MAX_EVIDENCE_INLINE_BYTES + 100)},
            artifact_writer=artifact_writer,
        )
    )

    assert len(written) == 1
    assert sentinel not in repr(written)
    assert written[0]["token"] == "[REDACTED]"
    assert event.redacted_payload == {"externalized": True}
    assert event.artifact_refs == ["artifact://evidence/sha256/abc123"]
    assert sentinel not in repr(EvidenceEvent.objects.values().get(pk=event.pk))


@pytest.mark.django_db
def test_over_total_budget_evidence_still_requires_artifact_writer(run_and_revision):
    """A total-budget summary is externalized instead of silently becoming a small inline digest."""
    run, revision = run_and_revision
    written = []
    payload = {"part-{:03d}".format(index): "x" * MAX_EVIDENCE_STRING_BYTES for index in range(20)}

    event = record_evidence(
        **record_values(
            run,
            revision,
            payload=payload,
            artifact_writer=lambda value: written.append(value) or "artifact://evidence/sha256/over-total-budget",
        )
    )

    assert len(written) == 1
    assert written[0]["_truncated"] is True
    assert len(written[0]["_redacted_sha256"]) == 64
    assert event.redacted_payload == {"externalized": True}


def test_redaction_key_collision_is_stable_across_mapping_insertion_order():
    """Keys that truncate to one safe value retain deterministic suffix assignment and values."""
    shared_prefix = "k" * 128
    left = {shared_prefix + "z": "last", shared_prefix + "a": "first"}
    right = {shared_prefix + "a": "first", shared_prefix + "z": "last"}

    assert redact_evidence_payload(left) == redact_evidence_payload(right)


@pytest.mark.django_db
@pytest.mark.parametrize("failure", ["missing", "invalid", "raises"])
def test_large_evidence_fails_closed_without_a_real_safe_artifact(run_and_revision, failure, caplog):
    """Missing, invalid, or failed artifact storage never creates a fictional evidence reference."""
    run, revision = run_and_revision
    sentinel = "raw-writer-secret"
    artifact_writer = None
    if failure == "invalid":

        def artifact_writer(_payload):
            return "https://user:password@example.com/evidence?token={}".format(sentinel)

    elif failure == "raises":

        def artifact_writer(_payload):
            raise RuntimeError(sentinel)

    with pytest.raises(ValidationError) as error:
        record_evidence(
            **record_values(
                run,
                revision,
                payload={"password": sentinel, "content": "x" * (MAX_EVIDENCE_INLINE_BYTES + 100)},
                artifact_writer=artifact_writer,
            )
        )

    assert EvidenceEvent.objects.count() == 0
    assert sentinel not in str(error.value)
    assert sentinel not in caplog.text


@pytest.mark.django_db
def test_small_evidence_never_calls_artifact_writer(run_and_revision):
    """Inline evidence remains self-contained and cannot create an unnecessary external artifact."""
    run, revision = run_and_revision

    def artifact_writer(_payload):
        raise AssertionError("small evidence must stay inline")

    event = record_evidence(**record_values(run, revision, artifact_writer=artifact_writer))

    assert event.redacted_payload == {"result": "ok"}
    assert event.artifact_refs == []


@pytest.mark.django_db
def test_invalid_authority_fails_before_large_artifact_side_effect(run_and_revision):
    """A rejected actor or relation cannot leave an orphan evidence artifact."""
    run, revision = run_and_revision
    calls = []

    with pytest.raises(ValidationError):
        record_evidence(
            **record_values(
                run,
                revision,
                actor="foreign-user",
                payload={"content": "x" * (MAX_EVIDENCE_INLINE_BYTES + 100)},
                artifact_writer=lambda payload: calls.append(payload) or "artifact://evidence/orphan",
            )
        )

    assert calls == []
