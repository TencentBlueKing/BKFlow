"""Append-only and data-minimal knowledge retrieval audit contracts."""

import json
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from bkflow.harness.constants import (
    HarnessRunStatus,
    KnowledgeBindingStatus,
    KnowledgeRetrievalMode,
    KnowledgeTier,
    KnowledgeTrustLevel,
)
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    HarnessRun,
    KnowledgeRetrievalAudit,
    KnowledgeSourceBinding,
)
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.knowledge.contracts import ProviderKnowledgeHit
from bkflow.harness.services.knowledge.providers import KnowledgeProviderRegistry
from bkflow.harness.services.knowledge.redaction import REDACTED_VALUE
from bkflow.harness.services.knowledge.router import KnowledgeRouter


def trusted_context(**overrides):
    """Build immutable request authority for persistence assertions."""
    values = {
        "platform_key": "bkaidev",
        "platform_app": "trusted-app",
        "actor": "trusted-user",
        "space_id": 902,
        "scope_type": "project",
        "scope_value": "902",
        "target_environment": "stag",
        "policy_version": "risk-2026.09",
        "mcp_contract_version": "1.1.0",
        "correlation_id": "knowledge-audit-test",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


def create_binding(**overrides):
    """Persist one eligible source without credential-shaped provider metadata."""
    values = {
        "provider": "fixture-docs",
        "source_ref": "knowledge://audit/source",
        "tier": KnowledgeTier.PUBLIC,
        "platform_key": None,
        "space_id": None,
        "scope_type": None,
        "scope_value": None,
        "trust_level": KnowledgeTrustLevel.VERIFIED,
        "priority": 0,
        "environment": "stag",
        "allowed_apps": [],
        "allowed_actors": [],
        "data_classification": "internal",
        "snapshot_version": "2026.09.04",
        "last_verified_at": timezone.now(),
        "owner": "knowledge-owner",
        "reviewer": "security-reviewer",
        "status": KnowledgeBindingStatus.ACTIVE,
        "retrieval_mode": KnowledgeRetrievalMode.HYBRID,
        "max_top_k": 5,
        "redaction_policy": {"policy_ref": "redaction://workflow-guides/v1"},
        "credential_ref": "credential://id/42",
        "provider_config": {"collection": "workflow-guides"},
    }
    values.update(overrides)
    binding = KnowledgeSourceBinding(**values)
    binding.full_clean()
    binding.save()
    return binding


def provider_hit(excerpt="Complete document text that must never enter audit storage."):
    """Return one complete external hit through the real registry normalization path."""
    return ProviderKnowledgeHit(
        provider_hit_ref="provider-hit://audit/1",
        title="Restart service",
        excerpt=excerpt,
        citation_ref="provider-controlled-citation",
        source_snapshot="provider-controlled-snapshot",
        provider_score=0.9,
    )


class RecordingProvider:
    """Record only the provider boundary arguments needed to prove query flow."""

    def __init__(self, response):
        self.response = response
        self.queries = []

    def search(self, binding, query):
        self.queries.append(query.query)
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


def router_for(response):
    """Construct a router whose only test double is the external knowledge backend."""
    provider = RecordingProvider(response)
    registry = KnowledgeProviderRegistry({"fixture-docs": provider})
    return KnowledgeRouter(provider_registry=registry), provider


@pytest.mark.django_db
@pytest.mark.parametrize(
    "response,expected_outcome",
    [
        ([provider_hit()], "SUCCESS"),
        ([], "ZERO_RESULTS"),
        (TimeoutError("Bearer resolved-provider-secret"), "FAILED"),
    ],
)
def test_each_tool_call_appends_exactly_one_audit_for_success_zero_and_failure(response, expected_outcome):
    """Dropping or duplicating one terminal audit would break per-call accountability."""
    create_binding()
    router, _provider = router_for(response)

    router.search(
        trusted_context(),
        {"query": "restart service", "top_k": 5, "data_classification": "internal"},
    )

    assert KnowledgeRetrievalAudit.objects.count() == 1
    assert KnowledgeRetrievalAudit.objects.get().outcome == expected_outcome


@pytest.mark.django_db
def test_audit_persists_redacted_query_and_references_but_never_document_or_secret():
    """Persisting the raw provider payload would leak the search query, credential, or full document."""
    binding = create_binding()
    router, provider = router_for([provider_hit()])
    query = "Bearer resolved-query-secret"

    result = router.search(
        trusted_context(),
        {"query": query, "top_k": 5, "data_classification": "internal"},
    )

    audit = KnowledgeRetrievalAudit.objects.get()
    serialized = json.dumps(
        {
            "context": audit.trusted_context_snapshot,
            "query": audit.redacted_query,
            "bindings": audit.eligible_binding_ids,
            "calls": audit.provider_call_summaries,
            "hits": audit.hit_refs,
            "snapshots": audit.snapshot_refs,
        },
        sort_keys=True,
    )
    assert provider.queries == [REDACTED_VALUE]
    assert audit.redacted_query == REDACTED_VALUE
    assert audit.eligible_binding_ids == [binding.id]
    assert audit.hit_refs == [result.hits[0].hit_ref]
    assert audit.snapshot_refs[0].startswith("knowledge-snapshot://sha256/")
    assert "resolved-query-secret" not in serialized
    assert "resolved-provider-secret" not in serialized
    assert "credential://id/42" not in serialized
    assert "Complete document text" not in serialized
    assert "provider-controlled-citation" not in serialized


@pytest.mark.django_db
def test_audit_contains_only_eligible_binding_ids_and_safe_provider_summaries():
    """Recording queried-out rows would disclose the existence of a forbidden knowledge source."""
    eligible = create_binding()
    forbidden = create_binding(
        provider="forbidden-secret-provider",
        source_ref="knowledge://audit/forbidden",
        tier=KnowledgeTier.SPACE,
        platform_key="bkaidev",
        space_id=903,
    )
    router, _provider = router_for([])

    router.search(
        trusted_context(),
        {"query": "restart service", "top_k": 5, "data_classification": "internal"},
    )

    audit = KnowledgeRetrievalAudit.objects.get()
    serialized = json.dumps(audit.provider_call_summaries, sort_keys=True)
    assert audit.eligible_binding_ids == [eligible.id]
    assert forbidden.id not in audit.eligible_binding_ids
    assert "forbidden-secret-provider" not in serialized
    assert set(audit.provider_call_summaries[0]) <= KnowledgeRetrievalAudit.PROVIDER_CALL_FIELDS


@pytest.mark.django_db
def test_optional_run_id_is_linked_only_when_run_matches_trusted_context():
    """Trusting a model-supplied run id would attach evidence to another tenant's run."""
    create_binding()
    matching_run = HarnessRun.objects.create(
        platform="bkaidev",
        platform_app="trusted-app",
        actor="trusted-user",
        space_id=902,
        scope=canonical_scope("project", "902"),
        environment="stag",
        status=HarnessRunStatus.PLANNING,
        policy_version="risk-2026.09",
        mcp_contract_version="1.1.0",
        client_context={},
    )
    foreign_run = HarnessRun.objects.create(
        platform="bkaidev",
        platform_app="trusted-app",
        actor="another-user",
        space_id=903,
        scope=canonical_scope("project", "903"),
        environment="stag",
        status=HarnessRunStatus.PLANNING,
        policy_version="risk-2026.09",
        mcp_contract_version="1.1.0",
        client_context={},
    )
    router, _provider = router_for([])

    router.search(
        trusted_context(),
        {
            "query": "restart service",
            "top_k": 5,
            "data_classification": "internal",
            "run_id": str(matching_run.run_id),
        },
    )
    router.search(
        trusted_context(correlation_id="foreign-run-test"),
        {
            "query": "restart service",
            "top_k": 5,
            "data_classification": "internal",
            "run_id": str(foreign_run.run_id),
        },
    )

    audits = list(KnowledgeRetrievalAudit.objects.order_by("id"))
    assert audits[0].run_id == matching_run.id
    assert audits[1].run is None
    assert audits[1].correlation_id == "foreign-run-test"
    assert uuid.UUID(str(foreign_run.run_id)) != matching_run.run_id


@pytest.mark.django_db
def test_malformed_optional_run_id_cannot_abort_auditing():
    """Passing a non-UUID run reference must not suppress the retrieval result or its audit row."""
    create_binding()
    router, _provider = router_for([])

    result = router.search(
        trusted_context(),
        {
            "query": "restart service",
            "top_k": 5,
            "data_classification": "internal",
            "run_id": "not-a-uuid",
        },
    )

    assert result.error_codes == ()
    assert KnowledgeRetrievalAudit.objects.get().run is None


@pytest.mark.django_db
def test_redaction_expansion_keeps_audit_query_within_persistence_limit():
    """Expanding many short assignments to markers must not suppress the one terminal audit row."""
    create_binding()
    router, _provider = router_for([])
    query = ("password=x " * 166).strip()

    result = router.search(
        trusted_context(),
        {"query": query, "top_k": 5, "data_classification": "internal"},
    )

    audit = KnowledgeRetrievalAudit.objects.get()
    assert result.error_codes == ()
    assert len(audit.redacted_query) <= 2000
    assert "password=x" not in audit.redacted_query


@pytest.mark.django_db
def test_persisted_audit_rejects_instance_and_queryset_mutation_or_deletion():
    """Changing or deleting an existing row would violate the append-only evidence contract."""
    audit = KnowledgeRetrievalAudit.objects.create(
        trusted_context_snapshot={"space_id": 902},
        query_fingerprint="a" * 64,
        redacted_query="restart service",
        correlation_id="knowledge-audit-instance-immutable",
        duration_ms=1,
        outcome="SUCCESS",
    )
    audit.outcome = "FAILED"

    with pytest.raises(ValidationError, match="append-only"):
        audit.save()
    with pytest.raises(ValidationError, match="append-only"):
        audit.delete()
    with pytest.raises(ValidationError, match="append-only"):
        audit.hard_delete()
    with pytest.raises(ValidationError, match="append-only"):
        KnowledgeRetrievalAudit.objects.filter(pk=audit.pk).delete()

    persisted = KnowledgeRetrievalAudit.objects.get(pk=audit.pk)
    assert persisted.outcome == "SUCCESS"
    assert persisted.is_deleted is False


@pytest.mark.django_db
def test_initial_audit_create_and_bulk_create_remain_available():
    """The append-only guard must retain both supported initial insertion paths."""
    first = KnowledgeRetrievalAudit.objects.create(
        trusted_context_snapshot={"space_id": 902},
        query_fingerprint="a" * 64,
        redacted_query="restart service",
        correlation_id="knowledge-audit-create",
        duration_ms=1,
        outcome="SUCCESS",
    )
    second = KnowledgeRetrievalAudit(
        trusted_context_snapshot={"space_id": 902},
        query_fingerprint="b" * 64,
        redacted_query="deploy service",
        correlation_id="knowledge-audit-bulk-create",
        duration_ms=2,
        outcome="ZERO_RESULTS",
    )

    KnowledgeRetrievalAudit.objects.bulk_create([second])

    assert KnowledgeRetrievalAudit.objects.count() == 2
    assert KnowledgeRetrievalAudit.objects.get(pk=first.pk).outcome == "SUCCESS"
