"""Persistence boundaries for immutable P4 generation feedback."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from bkflow.harness import models as harness_models
from bkflow.harness.services.evidence import EVIDENCE_REDACTION_VERSION
from tests.interface.harness.p4_model_support import (
    create_run_revision,
    feedback_values,
)


@pytest.mark.django_db
def test_feedback_binds_exact_trusted_revision_and_is_append_only():
    """A stored observation keeps provenance without changing the historical run outcome."""
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))

    assert feedback.run_id == run.id
    assert feedback.revision_id == revision.id
    assert feedback.plan_hash == revision.plan_hash
    assert feedback.space_id == run.space_id
    assert feedback.scope == run.scope
    assert feedback.redaction_version == EVIDENCE_REDACTION_VERSION
    assert run.status == "EVIDENCE_FINALIZED"

    feedback.redacted_summary = "rewritten observation"
    with pytest.raises(ValidationError):
        feedback.save()
    with pytest.raises(ValidationError):
        harness_models.GenerationFeedback.objects.filter(pk=feedback.pk).update(rating=5)
    with pytest.raises(ValidationError):
        feedback.delete()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"plan_hash": "c" * 64},
        {"platform_app": "caller-forged-app"},
        {"actor": "caller-forged-actor"},
        {"space_id": 999},
        {"scope": "project:999"},
        {"redacted_summary": "authorization: bearer raw-secret-token-value"},
        {"observed_outcome": {"password": "raw-secret"}},
        {"correction_artifact_ref": "https://credential.example.test/correction"},
        {"rating": 0},
        {"rating": 6},
        {"redaction_version": "caller-policy"},
    ],
)
def test_feedback_rejects_forged_provenance_secrets_and_invalid_bounds(overrides):
    """Direct ORM writes cannot weaken provenance, consent, redaction, or value bounds."""
    run, revision = create_run_revision()

    with pytest.raises(ValidationError):
        harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision, **overrides))


@pytest.mark.django_db
def test_feedback_rejects_cross_run_revision_and_scopes_idempotency_to_identity():
    """A digest replays only inside the same trusted app, actor, space, and run."""
    run, revision = create_run_revision()
    _other_run, other_revision = create_run_revision(space_id=907)

    with pytest.raises(ValidationError):
        harness_models.GenerationFeedback.objects.create(**feedback_values(run, other_revision))

    harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    with pytest.raises((ValidationError, IntegrityError)), transaction.atomic():
        harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
