"""P4 generation-feedback Harness APIGW transport contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.harness import models as harness_models
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.feedback.contracts import FeedbackRetentionPolicy
from bkflow.space.configs import (
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
    HarnessFeedbackEnabledConfig,
    SpaceConfigValueType,
    SuperusersConfig,
)
from bkflow.space.models import Space, SpaceConfig
from tests.interface.harness.p4_model_support import create_run_revision

ENVELOPE_KEYS = {
    "ok",
    "run_id",
    "revision_id",
    "plan_hash",
    "status",
    "summary",
    "artifact_refs",
    "errors",
    "next_actions",
    "correlation_id",
}


@pytest.fixture
def authorized_p4_space(db):
    space = Space.objects.create(
        name="Harness P4 transport space",
        app_code="trusted-p4-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    configs = (
        (HarnessEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (HarnessFeedbackEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (SuperusersConfig.name, SpaceConfigValueType.JSON.value, "", ["feedback-user"]),
        (
            HarnessDeploymentConfig.name,
            SpaceConfigValueType.JSON.value,
            "",
            {
                "platform_key": "bkaidev",
                "allowed_scope_types": ["project"],
                "scope_type": "project",
                "scope_value": str(space.id),
                "target_environment": "stag",
                "risk_policy_version": "risk-2026.09",
                "mcp_contract_version": "1.4.0",
            },
        ),
    )
    for name, value_type, text_value, json_value in configs:
        SpaceConfig.objects.create(
            space_id=space.id,
            name=name,
            value_type=value_type,
            text_value=text_value,
            json_value=json_value,
        )
    return space


def _path(space):
    return "/apigw/space/{}/harness/submit_generation_feedback/".format(space.id)


def _request(path, payload, *, app_code="trusted-p4-app", username="feedback-user", idempotency_header=None):
    headers = {"HTTP_X_REQUEST_ID": "p4-http-test"}
    if idempotency_header is not None:
        headers["HTTP_X_IDEMPOTENCY_KEY"] = idempotency_header
    request = APIRequestFactory().post(path, payload, format="json", **headers)
    request.app = SimpleNamespace(bk_app_code=app_code, verified=True)
    force_authenticate(request, user=SimpleNamespace(username=username, is_authenticated=True))
    return request


def _payload(run, revision, **overrides):
    payload = {
        "run_id": str(run.run_id),
        "revision_id": str(revision.id),
        "expected_plan_hash": revision.plan_hash,
        "feedback_type": "CORRECTION",
        "consent_scope": "harness_improvement",
        "idempotency_key": "p4-feedback-1",
        "rating": 2,
        "summary": "The generated flow selected the wrong service.",
        "correction_artifact_ref": "artifact://feedback/correction-1",
        "observed_outcome": {"expected": "service-a", "actual": "service-b"},
    }
    payload.update(overrides)
    return payload


def _approved_policy():
    return FeedbackRetentionPolicy.approved(
        policy_version="retention-2026.09-test",
        allowed_consent_scopes=("harness_improvement",),
        retention_days=30,
    )


def test_feedback_serializer_accepts_only_observation_fields_and_strict_wire_types():
    from bkflow.apigw.serializers.harness.feedback import (
        SubmitGenerationFeedbackSerializer,
    )

    run_id = "00000000-0000-4000-8000-000000000001"
    revision_id = "00000000-0000-4000-8000-000000000002"
    payload = {
        "run_id": run_id,
        "revision_id": revision_id,
        "expected_plan_hash": "a" * 64,
        "feedback_type": "ACCEPTED",
        "consent_scope": "harness_improvement",
        "idempotency_key": "p4-feedback-schema-1",
    }

    assert SubmitGenerationFeedbackSerializer(data=payload).is_valid()
    for field in ("owner_ref", "reviewer_ref", "status", "target_system", "target_tier", "space_id", "actor"):
        assert SubmitGenerationFeedbackSerializer(data={**payload, field: "forged"}).is_valid() is False
    assert SubmitGenerationFeedbackSerializer(data={**payload, "rating": True}).is_valid() is False
    assert SubmitGenerationFeedbackSerializer(data={**payload, "run_id": 1}).is_valid() is False
    assert (
        SubmitGenerationFeedbackSerializer(
            data={**payload, "correction_artifact_ref": "credential://provider/raw-secret"}
        ).is_valid()
        is False
    )


@pytest.mark.django_db
def test_feedback_route_uses_trusted_identity_and_records_only_redacted_observation(monkeypatch, authorized_p4_space):
    run, revision = create_run_revision(space_id=authorized_p4_space.id)
    monkeypatch.setattr("bkflow.harness.services.facade.production_feedback_retention_policy", _approved_policy)
    secret = "Bearer feedback-secret-sentinel"
    payload = _payload(
        run,
        revision,
        summary="Observed {} while checking the generated flow.".format(secret),
        observed_outcome={"access_token": secret, "result": "wrong service"},
    )
    path = _path(authorized_p4_space)

    response = resolve(path).func(
        _request(path, payload, idempotency_header=payload["idempotency_key"]),
        space_id=str(authorized_p4_space.id),
    )

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is True
    assert response.data["status"] == "FEEDBACK_RECORDED"
    feedback = harness_models.GenerationFeedback.objects.get()
    assert (
        feedback.platform,
        feedback.platform_app,
        feedback.actor,
        feedback.space_id,
        feedback.scope,
        feedback.target_environment,
        feedback.policy_version,
    ) == (
        "bkaidev",
        "trusted-p4-app",
        "feedback-user",
        authorized_p4_space.id,
        canonical_scope("project", str(authorized_p4_space.id)),
        "stag",
        "risk-2026.09",
    )
    assert feedback.run == run
    assert feedback.revision == revision
    assert feedback.observed_outcome["access_token"] == "[REDACTED]"
    assert secret not in feedback.redacted_summary
    assert secret not in repr(response.data)
    assert harness_models.ImprovementCandidate.objects.count() == 0


@pytest.mark.django_db
def test_production_feedback_retention_policy_is_fail_closed(authorized_p4_space):
    run, revision = create_run_revision(space_id=authorized_p4_space.id)
    path = _path(authorized_p4_space)

    response = resolve(path).func(
        _request(path, _payload(run, revision)),
        space_id=str(authorized_p4_space.id),
    )

    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    assert harness_models.GenerationFeedback.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("gate", ("old_contract", "feature_off"))
def test_feedback_contract_and_space_flag_fail_before_body_or_facade(monkeypatch, authorized_p4_space, gate):
    if gate == "old_contract":
        deployment = SpaceConfig.objects.get(space_id=authorized_p4_space.id, name=HarnessDeploymentConfig.name)
        deployment.json_value["mcp_contract_version"] = "1.3.0"
        deployment.save(update_fields=["json_value"])
    else:
        SpaceConfig.objects.filter(space_id=authorized_p4_space.id, name=HarnessFeedbackEnabledConfig.name).update(
            text_value="false"
        )
    downstream = Mock(side_effect=AssertionError("disabled feedback reached facade"))
    monkeypatch.setattr("bkflow.harness.services.facade.HarnessFacade.submit_generation_feedback", downstream)
    path = _path(authorized_p4_space)

    response = resolve(path).func(
        _request(path, {"summary": "Bearer secret body must not be parsed"}),
        space_id=str(authorized_p4_space.id),
    )

    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_feedback_idempotency_header_must_match_body_before_facade(monkeypatch, authorized_p4_space):
    run, revision = create_run_revision(space_id=authorized_p4_space.id)
    downstream = Mock(side_effect=AssertionError("mismatched idempotency reached facade"))
    monkeypatch.setattr("bkflow.harness.services.facade.HarnessFacade.submit_generation_feedback", downstream)
    payload = _payload(run, revision)
    path = _path(authorized_p4_space)

    response = resolve(path).func(
        _request(path, payload, idempotency_header="different-key"),
        space_id=str(authorized_p4_space.id),
    )

    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_feedback_route_rejects_cross_actor_run_ownership(monkeypatch, authorized_p4_space):
    run, revision = create_run_revision(space_id=authorized_p4_space.id, actor="different-run-owner")
    monkeypatch.setattr("bkflow.harness.services.facade.production_feedback_retention_policy", _approved_policy)
    path = _path(authorized_p4_space)

    response = resolve(path).func(
        _request(path, _payload(run, revision)),
        space_id=str(authorized_p4_space.id),
    )

    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert harness_models.GenerationFeedback.objects.count() == 0
