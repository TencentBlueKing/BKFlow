"""P1 federated knowledge-search APIGW transport contracts."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import DatabaseError
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.apigw.serializers.harness.knowledge import KnowledgeSearchSerializer
from bkflow.apigw.views.harness.knowledge import search_workflow_knowledge
from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.contracts import (
    KnowledgeConflictAnnotation,
    KnowledgeHit,
    KnowledgeSearchResult,
)
from bkflow.harness.models import HarnessRun
from bkflow.harness.permissions import HarnessPermission
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.facade import P1_ACTION_RISK, HarnessFacade
from bkflow.space.configs import (
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
    HarnessKnowledgeRouterEnabledConfig,
    SpaceConfigValueType,
    SuperusersConfig,
)
from bkflow.space.models import Space, SpaceConfig

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
KNOWLEDGE_PATH = "/apigw/space/{}/harness/search_workflow_knowledge/"


@pytest.fixture
def authorized_p1_space(db):
    """Create a fully trusted P1 deployment binding for a real endpoint call."""
    space = Space.objects.create(
        name="Harness P1 transport space",
        app_code="trusted-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    configs = (
        (HarnessEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (HarnessKnowledgeRouterEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (SuperusersConfig.name, SpaceConfigValueType.JSON.value, "", ["trusted-user"]),
        (
            HarnessDeploymentConfig.name,
            SpaceConfigValueType.JSON.value,
            "",
            {
                "platform_key": "bkaidev",
                "allowed_scope_types": ["project"],
                "scope_type": "project",
                "scope_value": "scope-1",
                "target_environment": "stag",
                "risk_policy_version": "risk-2026.09",
                "mcp_contract_version": "1.1.0",
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


def _request(path, payload, *, app_code="trusted-app", username="trusted-user", accept=None):
    """Construct a real DRF request whose identities are gateway-owned attributes."""
    headers = {"HTTP_X_REQUEST_ID": "knowledge-http-test"}
    if accept is not None:
        headers["HTTP_ACCEPT"] = accept
    request = APIRequestFactory().post(path, payload, format="json", **headers)
    request.app = SimpleNamespace(bk_app_code=app_code, verified=True)
    force_authenticate(request, user=SimpleNamespace(username=username, is_authenticated=True))
    return request


def _set_contract(space, version):
    """Change only the server-owned negotiated contract for one test."""
    config = SpaceConfig.objects.get(space_id=space.id, name=HarnessDeploymentConfig.name)
    config.json_value = {**config.json_value, "mcp_contract_version": version}
    config.save(update_fields=["json_value"])


def _set_knowledge_flag(space, enabled):
    """Change only the server-owned P1 feature switch for one test."""
    config = SpaceConfig.objects.get(space_id=space.id, name=HarnessKnowledgeRouterEnabledConfig.name)
    config.text_value = "true" if enabled else "false"
    config.save(update_fields=["text_value"])


def _hit(index=1, excerpt="Drain traffic before restart."):
    """Build one already-redacted advisory Router result."""
    return KnowledgeHit(
        hit_ref="knowledge-hit://sha256/{:064d}".format(index),
        binding_id=index,
        tier="SPACE",
        provider="fixture-docs",
        title="Restart service {}".format(index),
        excerpt=excerpt,
        citation_ref="citation://sha256/{:064d}".format(index),
        source_ref="knowledge://workflow-guides/source-{}".format(index),
        snapshot_version="sha256:{:064d}".format(index),
        trust_level="VERIFIED",
        applicable_scope="SPACE:bkaidev:1",
        provider_score=0.8,
        final_score=0.9,
        expires_at=None,
    )


def _result(*, hits=(), conflicts=(), artifact_refs=(), warning_codes=(), error_codes=()):
    """Build the complete Task 6 DTO consumed by the Facade."""
    return KnowledgeSearchResult(
        query_fingerprint="a" * 64,
        hits=tuple(hits),
        conflict_annotations=tuple(conflicts),
        artifact_refs=tuple(artifact_refs),
        warning_codes=tuple(warning_codes),
        error_codes=tuple(error_codes),
    )


class _RecordingRouter:
    """Replace only external retrieval while retaining the real transport and Facade."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def search(self, context, request):
        self.calls.append((context, request))
        return self.result


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "restart", "actor": "forged"},
        {"query": "restart", "platform_key": "forged"},
        {"query": "restart", "space_id": 999},
        {"query": "restart", "scope_type": "forged"},
        {"query": "restart", "environment": "prod"},
        {"query": "restart", "policy_version": "forged"},
        {"query": "restart", "mcp_contract_version": "9.9.9"},
        {"query": "restart", "correlation_id": "forged"},
    ],
)
def test_serializer_rejects_every_model_controlled_authority_field(payload):
    """Adding any client-owned identity alias must not influence knowledge routing."""
    assert KnowledgeSearchSerializer(data=payload).is_valid() is False


def test_serializer_accepts_only_the_bounded_public_request_contract():
    """Removing bounds or the closed client-context shape would widen the Tool contract."""
    serializer = KnowledgeSearchSerializer(
        data={
            "query": "restart service safely",
            "top_k": 20,
            "run_id": "00000000-0000-0000-0000-000000000001",
            "data_classification": "internal",
            "client_context": {"conversation_ref": "conversation-1", "agent_release": "release-1"},
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert KnowledgeSearchSerializer(data={"query": "restart", "top_k": 21}).is_valid() is False
    assert (
        KnowledgeSearchSerializer(data={"query": "restart", "client_context": {"actor": "forged"}}).is_valid() is False
    )


@pytest.mark.django_db
def test_contract_1_0_rejects_p1_before_facade_dispatch(monkeypatch, authorized_p1_space):
    """A negotiated P0 connection must never reach the fifth Tool implementation."""
    _set_contract(authorized_p1_space, "1.0.0")
    downstream = Mock()
    monkeypatch.setattr(HarnessFacade, "search_workflow_knowledge", downstream)
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(_request(path, {"query": "restart"}), space_id=str(authorized_p1_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    assert response.data["errors"][0]["category"] == "PERMISSION"
    assert response.data["errors"][0]["suggested_action"] == "negotiate_harness_contract"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_contract_gate_precedes_even_invalid_model_input(monkeypatch, authorized_p1_space):
    """Parsing a disabled Tool body first would expose or spend work on an unavailable contract surface."""
    _set_contract(authorized_p1_space, "1.0.0")
    downstream = Mock()
    monkeypatch.setattr(HarnessFacade, "search_workflow_knowledge", downstream)
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(
        _request(path, {"query": "restart", "actor": "forged"}), space_id=str(authorized_p1_space.id)
    )

    assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_disabled_p1_flag_rejects_p1_without_affecting_the_route(monkeypatch, authorized_p1_space):
    """Disabling only P1 must fail closed before any provider-backed Router call."""
    _set_knowledge_flag(authorized_p1_space, False)
    downstream = Mock()
    monkeypatch.setattr(HarnessFacade, "search_workflow_knowledge", downstream)
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(_request(path, {"query": "restart"}), space_id=str(authorized_p1_space.id))

    assert response.status_code == 200
    assert response.data["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    downstream.assert_not_called()


@pytest.mark.django_db
def test_tool_gate_database_error_is_one_safe_audited_retryable_response(monkeypatch, authorized_p1_space, caplog):
    """A SpaceConfig outage must not escape DRF, expose DB text, or invoke the Facade."""
    sentinel = "DB-SENTINEL resolved-secret host=private-db"
    original_get_config = SpaceConfig.get_config.__func__

    def failing_get_config(cls, space_id, config_name, *args, **kwargs):
        if config_name == HarnessKnowledgeRouterEnabledConfig.name:
            raise DatabaseError(sentinel)
        return original_get_config(cls, space_id, config_name, *args, **kwargs)

    monkeypatch.setattr(SpaceConfig, "get_config", classmethod(failing_get_config))
    downstream = Mock()
    monkeypatch.setattr(HarnessFacade, "search_workflow_knowledge", downstream)
    caplog.set_level("INFO", logger="bkflow.harness")
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(_request(path, {"query": "restart"}), space_id=str(authorized_p1_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response.data["errors"][0]["retryable"] is True
    assert sentinel not in str(response.data)
    assert sentinel not in caplog.text
    downstream.assert_not_called()
    audit_records = [record for record in caplog.records if hasattr(record, "harness_audit")]
    assert len(audit_records) == 1
    assert audit_records[0].harness_audit["tool"] == "search_workflow_knowledge"
    assert audit_records[0].harness_audit["risk"] == "L0"
    assert audit_records[0].harness_audit["result"] is False


@pytest.mark.django_db
def test_contract_1_1_and_flag_expose_one_l0_advisory_search(monkeypatch, authorized_p1_space, caplog):
    """Changing trusted-context use or policy effect must fail at the real route boundary."""
    router = _RecordingRouter(_result(hits=[_hit()]))
    monkeypatch.setattr(HarnessFacade, "_knowledge_router", lambda self: router)
    caplog.set_level("INFO", logger="bkflow.harness")
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)
    payload = {
        "query": "restart service safely",
        "top_k": 3,
        "data_classification": "internal",
        "client_context": {"conversation_ref": "conversation-1", "agent_release": "release-1"},
    }

    response = resolve(path).func(_request(path, payload), space_id=str(authorized_p1_space.id))

    assert response.status_code == 200
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is True
    assert response.data["status"] == "COMPLETED"
    assert response.data["correlation_id"] == "knowledge-http-test"
    artifact = response.data["artifact_refs"][0]
    assert artifact["type"] == "knowledge_search"
    assert artifact["payload"]["hits"][0]["policy_effect"] == "ADVISORY"
    assert artifact["payload"]["policy_effect"] == "ADVISORY"
    context, router_request = router.calls[0]
    assert (context.platform_key, context.platform_app, context.actor, context.space_id) == (
        "bkaidev",
        "trusted-app",
        "trusted-user",
        authorized_p1_space.id,
    )
    assert router_request == {"query": "restart service safely", "top_k": 3, "data_classification": "internal"}
    assert P1_ACTION_RISK == {"search_workflow_knowledge": "L0"}
    assert caplog.records[-1].harness_audit["risk"] == "L0"


@pytest.mark.django_db
def test_conflict_annotations_remain_json_safe_through_the_transport(monkeypatch, authorized_p1_space):
    """Leaving tuple-valued alternative refs in a conflict would turn a valid search into infrastructure failure."""
    conflict = KnowledgeConflictAnnotation(
        topic_ref="knowledge-topic://sha256/{}".format("b" * 64),
        resolution="BUSINESS_SPECIFICITY",
        preferred_hit_ref="knowledge-hit://sha256/{}".format("1" * 64),
        alternative_hit_refs=("knowledge-hit://sha256/{}".format("2" * 64),),
    )
    router = _RecordingRouter(_result(hits=[_hit()], conflicts=[conflict]))
    monkeypatch.setattr(HarnessFacade, "_knowledge_router", lambda self: router)
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(_request(path, {"query": "restart"}), space_id=str(authorized_p1_space.id))

    assert response.data["ok"] is True
    annotations = response.data["artifact_refs"][0]["payload"]["conflict_annotations"]
    assert annotations[0]["alternative_hit_refs"] == ["knowledge-hit://sha256/{}".format("2" * 64)]


@pytest.mark.django_db
def test_unknown_body_field_never_reaches_the_router(monkeypatch, authorized_p1_space):
    """A forged route or identity field cannot survive the closed serializer."""
    router = _RecordingRouter(_result())
    monkeypatch.setattr(HarnessFacade, "_knowledge_router", lambda self: router)
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(
        _request(path, {"query": "restart", "platform": "other-platform"}),
        space_id=str(authorized_p1_space.id),
    )

    assert response.data["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert router.calls == []


@pytest.mark.django_db
def test_optional_run_must_belong_to_the_complete_trusted_context(monkeypatch, authorized_p1_space):
    """Accepting an existing foreign run UUID would join retrieval evidence across tenants."""
    foreign_run = HarnessRun.objects.create(
        platform="bkaidev",
        platform_app="trusted-app",
        actor="foreign-user",
        space_id=authorized_p1_space.id + 1,
        scope=canonical_scope("project", "other-scope"),
        environment="stag",
        status=HarnessRunStatus.PLANNING,
        policy_version="risk-2026.09",
        mcp_contract_version="1.1.0",
        client_context={},
    )
    router = _RecordingRouter(_result())
    monkeypatch.setattr(HarnessFacade, "_knowledge_router", lambda self: router)
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(
        _request(path, {"query": "restart", "run_id": str(foreign_run.run_id)}),
        space_id=str(authorized_p1_space.id),
    )

    assert response.data["ok"] is False
    assert response.data["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert response.data["errors"][0]["category"] == "PERMISSION"
    assert router.calls == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "router_result,expected_ok,expected_code",
    [
        (_result(), True, None),
        (_result(error_codes=["RETRYABLE_INFRA"]), False, "RETRYABLE_INFRA"),
    ],
)
def test_empty_and_provider_timeout_results_keep_normalized_envelope_semantics(
    monkeypatch, authorized_p1_space, router_result, expected_ok, expected_code
):
    """Conflating zero results with an outage would make the Agent retry healthy empty searches."""
    router = _RecordingRouter(router_result)
    monkeypatch.setattr(HarnessFacade, "_knowledge_router", lambda self: router)
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(_request(path, {"query": "restart"}), space_id=str(authorized_p1_space.id))

    assert response.data["ok"] is expected_ok
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["artifact_refs"][0]["payload"]["hits"] == []
    if expected_code:
        assert response.data["errors"][0]["code"] == expected_code
        assert response.data["errors"][0]["retryable"] is True
    else:
        assert response.data["errors"] == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "excerpt,hit_count,accept",
    [
        (("\u2028\u2029" * 2000), 3, "application/json"),
        ("x" * 2200, 20, "application/json; indent=8"),
    ],
    ids=("escaped-line-separators", "indented-json"),
)
def test_complete_ten_key_http_envelope_uses_the_negotiated_renderer_budget(
    monkeypatch, authorized_p1_space, excerpt, hit_count, accept
):
    """Canonical compact bytes cannot stand in for escaping or indenting by the accepted DRF renderer."""
    large_hits = [_hit(index, excerpt=excerpt) for index in range(1, hit_count + 1)]
    router = _RecordingRouter(
        _result(
            hits=large_hits,
            artifact_refs=["knowledge-artifact://sha256/server-written-result"],
            warning_codes=["KNOWLEDGE_RESULT_IN_ARTIFACT"],
        )
    )
    monkeypatch.setattr(HarnessFacade, "_knowledge_router", lambda self: router)
    path = KNOWLEDGE_PATH.format(authorized_p1_space.id)

    response = resolve(path).func(
        _request(path, {"query": "restart"}, accept=accept), space_id=str(authorized_p1_space.id)
    )
    response.render()

    assert len(response.content) <= 65536
    assert set(response.data) == ENVELOPE_KEYS
    assert response.data["ok"] is True
    payload = response.data["artifact_refs"][0]["payload"]
    assert payload["hits"] == []
    assert payload["conflict_annotations"] == []
    assert payload["artifact_refs"] == ["knowledge-artifact://sha256/server-written-result"]
    assert "KNOWLEDGE_ENVELOPE_TRUNCATED" in payload["warning_codes"]
    assert excerpt[:100] not in json.dumps(response.data, ensure_ascii=False)


def test_p1_view_is_one_post_only_harness_permission_endpoint():
    """Adding an alternate permission or verb would bypass the single Harness dispatch path."""
    assert search_workflow_knowledge.cls.permission_classes == [HarnessPermission]
    assert set(search_workflow_knowledge.cls.http_method_names) == {"options", "post"}
