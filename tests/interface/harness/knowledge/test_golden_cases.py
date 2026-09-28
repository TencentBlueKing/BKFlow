"""Versioned P1 knowledge Golden Cases executed through the public Facade."""

import re
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from django.utils import timezone

from bkflow.harness.constants import (
    KnowledgeBindingStatus,
    KnowledgeRetrievalMode,
    KnowledgeTier,
    KnowledgeTrustLevel,
)
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import KnowledgeRetrievalAudit, KnowledgeSourceBinding
from bkflow.harness.services.facade import HarnessFacade
from bkflow.harness.services.knowledge.contracts import ProviderKnowledgeHit
from bkflow.harness.services.knowledge.eligibility import eligible_bindings
from bkflow.harness.services.knowledge.providers import KnowledgeProviderRegistry
from bkflow.harness.services.knowledge.router import KnowledgeRouter

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures/harness/knowledge_cases.yaml"
GROUP_COUNTS = {
    "global_public_common": 6,
    "platform_specific": 6,
    "space_private": 6,
    "scope_private": 6,
    "conflict_precedence": 4,
    "expired_or_retired": 3,
    "cross_space_denied": 3,
    "malicious_instruction": 2,
}
CASE_KEYS = {
    "id",
    "group",
    "query",
    "top_k",
    "data_classification",
    "trusted_context",
    "bindings",
    "provider_snapshot",
    "eligible_source_ids",
    "forbidden_source_ids",
    "expected_citations",
    "expected_tool_result",
    "expected_snapshot",
}
CONTEXT_KEYS = {
    "platform_key",
    "platform_app",
    "actor",
    "space_id",
    "scope_type",
    "scope_value",
    "target_environment",
    "policy_version",
    "mcp_contract_version",
    "correlation_id",
}
RESULT_KEYS = {"outcome", "ordered_source_ids", "conflict_resolutions", "error_codes", "policy_effect"}
BINDING_ALLOWED_KEYS = {
    "id",
    "tier",
    "platform_key",
    "space_id",
    "scope_type",
    "scope_value",
    "trust_level",
    "priority",
    "environment",
    "allowed_apps",
    "allowed_actors",
    "data_classification",
    "snapshot_version",
    "expires",
    "status",
}
PROVIDER_SNAPSHOT_KEYS = {"source_id", "hit_ref", "title", "excerpt", "snapshot_version", "score"}
EXPECTED_SNAPSHOT_KEYS = {
    "query_fingerprint",
    "hit_ids",
    "conflict_annotations",
    "warning_codes",
    "error_codes",
    "artifact_refs",
    "audit",
    "envelope",
}
NORMALIZED_AUDIT_KEYS = {
    "query_fingerprint",
    "redacted_query",
    "trusted_context_snapshot",
    "run_id",
    "eligible_source_ids",
    "provider_outcomes",
    "hit_refs",
    "snapshot_refs",
    "correlation_id",
    "outcome",
}
CALL_REF_PATTERN = re.compile(r"^knowledge-call://sha256/[0-9a-f]{64}$")
NORMALIZED_HIT_KEYS = {
    "hit_ref",
    "binding_id",
    "tier",
    "provider",
    "title",
    "excerpt",
    "citation_ref",
    "source_ref",
    "snapshot_version",
    "trust_level",
    "applicable_scope",
    "provider_score",
    "final_score",
    "expires_at",
    "policy_effect",
}
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


@pytest.fixture(scope="module")
def golden_fixture():
    """Load only the reviewed P1 fixture and freeze its top-level schema."""
    fixture = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert set(fixture) == {"fixture_version", "case_schema_version", "expected_source_catalog", "cases"}
    assert fixture["fixture_version"] == "harness-p1-knowledge-golden-v1"
    assert fixture["case_schema_version"] == 2
    return fixture


@pytest.fixture(scope="module")
def golden_cases(golden_fixture):
    return golden_fixture["cases"]


def _binding_values(case, definition):
    """Expand only reviewed fixture shorthand into a complete governed binding."""
    context = case["trusted_context"]
    tier = definition["tier"]
    dimensions = {
        KnowledgeTier.GLOBAL: (None, None, None, None),
        KnowledgeTier.PUBLIC: (None, None, None, None),
        KnowledgeTier.PLATFORM: (
            definition.get("platform_key", context["platform_key"]),
            None,
            None,
            None,
        ),
        KnowledgeTier.SPACE: (
            definition.get("platform_key", context["platform_key"]),
            definition.get("space_id", context["space_id"]),
            None,
            None,
        ),
        KnowledgeTier.SCOPE: (
            definition.get("platform_key", context["platform_key"]),
            definition.get("space_id", context["space_id"]),
            definition.get("scope_type", context["scope_type"]),
            definition.get("scope_value", context["scope_value"]),
        ),
    }[tier]
    expires_at = None
    if definition.get("expires") == "past":
        expires_at = timezone.now() - timezone.timedelta(days=1)
    return {
        "provider": "golden-provider",
        "source_ref": "knowledge://golden/{}".format(definition["id"]),
        "tier": tier,
        "platform_key": dimensions[0],
        "space_id": dimensions[1],
        "scope_type": dimensions[2],
        "scope_value": dimensions[3],
        "trust_level": definition.get("trust_level", KnowledgeTrustLevel.VERIFIED),
        "priority": definition.get("priority", 0),
        "environment": definition.get("environment", context["target_environment"]),
        "allowed_apps": definition.get("allowed_apps", []),
        "allowed_actors": definition.get("allowed_actors", []),
        "data_classification": definition.get("data_classification", case["data_classification"]),
        "snapshot_version": definition.get("snapshot_version", "golden-binding-v1"),
        "expires_at": expires_at,
        "last_verified_at": timezone.now(),
        "owner": "golden-owner",
        "reviewer": "golden-reviewer",
        "status": definition.get("status", KnowledgeBindingStatus.ACTIVE),
        "retrieval_mode": KnowledgeRetrievalMode.HYBRID,
        "max_top_k": 5,
        "redaction_policy": {"policy_ref": "redaction://golden/v1"},
        "credential_ref": None,
        "provider_config": {"collection": "golden-corpus"},
    }


class _GoldenProvider:
    """The only mocked boundary: deterministic external provider retrieval."""

    def __init__(self, snapshots, bindings_by_fixture_id):
        self.snapshots = {item["source_id"]: item for item in snapshots}
        self.fixture_id_by_source_ref = {
            binding.source_ref: fixture_id for fixture_id, binding in bindings_by_fixture_id.items()
        }
        self.calls = []

    def search(self, binding, query):
        source_id = self.fixture_id_by_source_ref[binding.source_ref]
        self.calls.append(source_id)
        snapshot = self.snapshots[source_id]
        return [
            ProviderKnowledgeHit(
                provider_hit_ref="provider-hit://golden/{}/{}".format(source_id, snapshot["hit_ref"]),
                title=snapshot["title"],
                excerpt=snapshot["excerpt"],
                citation_ref="provider-controlled-and-replaced",
                source_snapshot=snapshot["snapshot_version"],
                provider_score=snapshot["score"],
            )
        ]


def _execute_case(case):
    """Execute the real Facade -> Router path after persisting reviewed bindings."""
    context = TrustedHarnessContext(**case["trusted_context"])
    bindings = {}
    for definition in case["bindings"]:
        binding = KnowledgeSourceBinding(**_binding_values(case, definition))
        binding.full_clean()
        binding.save()
        bindings[definition["id"]] = binding
    eligible = tuple(eligible_bindings(context, case["data_classification"]))
    provider = _GoldenProvider(case["provider_snapshot"], bindings)
    registry = KnowledgeProviderRegistry({"golden-provider": provider})
    router = KnowledgeRouter(provider_registry=registry)
    facade = HarnessFacade()
    facade._knowledge_router = lambda: router
    envelope = facade.search_workflow_knowledge(
        context,
        {"query": case["query"], "top_k": case["top_k"], "data_classification": case["data_classification"]},
    )
    fixture_id_by_binding_id = {binding.id: fixture_id for fixture_id, binding in bindings.items()}
    audit = KnowledgeRetrievalAudit.objects.get(correlation_id=case["trusted_context"]["correlation_id"])
    return envelope, audit, provider, eligible, fixture_id_by_binding_id


def _normalize_envelope(envelope, fixture_id_by_binding_id):
    """Normalize only runtime database identities; all governed values remain literal."""
    normalized = deepcopy(envelope)
    if normalized["artifact_refs"]:
        for hit in normalized["artifact_refs"][0]["payload"]["hits"]:
            hit["binding_id"] = fixture_id_by_binding_id[hit["binding_id"]]
    return normalized


def _normalize_audit(audit, fixture_id_by_binding_id):
    """Read actual audit identities and validate dynamic fields without reconstructing evidence."""
    binding_ids = list(audit.eligible_binding_ids)
    summaries = list(audit.provider_call_summaries)
    assert len(binding_ids) == len(set(binding_ids))
    assert all(binding_id in fixture_id_by_binding_id for binding_id in binding_ids)
    assert len(summaries) == len(binding_ids)
    provider_outcomes = []
    call_refs = []
    for binding_id, summary in zip(binding_ids, summaries):
        required_fields = {"provider", "call_ref", "snapshot_ref", "duration_ms", "hit_count", "outcome"}
        assert required_fields <= set(summary) <= required_fields | {"error_code"}
        assert isinstance(summary["duration_ms"], int) and not isinstance(summary["duration_ms"], bool)
        assert 0 <= summary["duration_ms"] <= 3_600_000
        assert CALL_REF_PATTERN.fullmatch(summary["call_ref"])
        call_refs.append(summary["call_ref"])
        provider_outcomes.append(
            {
                "source_id": fixture_id_by_binding_id[binding_id],
                "provider": summary["provider"],
                "snapshot_ref": summary["snapshot_ref"],
                "hit_count": summary["hit_count"],
                "outcome": summary["outcome"],
                "error_code": summary.get("error_code"),
            }
        )
    assert len(call_refs) == len(set(call_refs))
    return {
        "query_fingerprint": audit.query_fingerprint,
        "redacted_query": audit.redacted_query,
        "trusted_context_snapshot": audit.trusted_context_snapshot,
        "run_id": audit.run_id,
        "eligible_source_ids": [fixture_id_by_binding_id[binding_id] for binding_id in binding_ids],
        "provider_outcomes": provider_outcomes,
        "hit_refs": audit.hit_refs,
        "snapshot_refs": audit.snapshot_refs,
        "correlation_id": audit.correlation_id,
        "outcome": audit.outcome,
    }


def _assert_exact_snapshot(envelope, audit, case, catalog, eligible, fixture_id_by_binding_id):
    """Compare runtime observations to independent literals without production helper reuse."""
    expected = case["expected_snapshot"]
    normalized_envelope = _normalize_envelope(envelope, fixture_id_by_binding_id)
    payload = normalized_envelope["artifact_refs"][0]["payload"]
    assert payload["query_fingerprint"] == expected["query_fingerprint"]
    assert payload["hits"] == [catalog[source_id] for source_id in expected["hit_ids"]]
    assert payload["conflict_annotations"] == expected["conflict_annotations"]
    assert payload["warning_codes"] == expected["warning_codes"]
    assert payload["artifact_refs"] == expected["artifact_refs"]
    assert [error["code"] for error in normalized_envelope["errors"]] == expected["error_codes"]
    assert len(audit.eligible_binding_ids) == len(expected["audit"]["eligible_source_ids"])
    assert len(audit.eligible_binding_ids) == len(case["eligible_source_ids"])
    assert len(fixture_id_by_binding_id) == len(case["bindings"])
    assert _normalize_audit(audit, fixture_id_by_binding_id) == expected["audit"]
    payload["hit_ids"] = [hit["binding_id"] for hit in payload.pop("hits")]
    assert normalized_envelope == expected["envelope"]


def test_fixture_has_exact_schema_unique_ids_and_approved_36_case_distribution(golden_fixture, golden_cases):
    """The release corpus cannot silently shrink, rename, or omit a frozen input/output fact."""
    assert len(golden_cases) == 36
    assert Counter(case["group"] for case in golden_cases) == GROUP_COUNTS
    assert len({case["id"] for case in golden_cases}) == 36
    catalog = golden_fixture["expected_source_catalog"]
    assert catalog
    assert all(set(hit) == NORMALIZED_HIT_KEYS for hit in catalog.values())
    for case in golden_cases:
        assert set(case) == CASE_KEYS
        assert set(case["trusted_context"]) == CONTEXT_KEYS
        assert set(case["expected_tool_result"]) == RESULT_KEYS
        assert set(case["expected_snapshot"]) == EXPECTED_SNAPSHOT_KEYS
        assert set(case["expected_snapshot"]["audit"]) == NORMALIZED_AUDIT_KEYS
        assert set(case["expected_snapshot"]["envelope"]) == ENVELOPE_KEYS
        binding_ids = [binding["id"] for binding in case["bindings"]]
        snapshot_ids = [snapshot["source_id"] for snapshot in case["provider_snapshot"]]
        assert all({"id", "tier"} <= set(binding) <= BINDING_ALLOWED_KEYS for binding in case["bindings"])
        assert all(set(snapshot) == PROVIDER_SNAPSHOT_KEYS for snapshot in case["provider_snapshot"])
        assert len(binding_ids) == len(set(binding_ids))
        assert set(snapshot_ids) == set(case["eligible_source_ids"])
        assert set(case["eligible_source_ids"]).isdisjoint(case["forbidden_source_ids"])
        assert set(case["eligible_source_ids"]) | set(case["forbidden_source_ids"]) == set(binding_ids)
        assert case["expected_citations"] == case["expected_tool_result"]["ordered_source_ids"]
        assert case["expected_snapshot"]["hit_ids"] == case["expected_citations"]
        assert set(case["expected_snapshot"]["hit_ids"]) <= set(catalog)


@pytest.mark.django_db
@pytest.mark.parametrize("case_index", range(36))
def test_golden_case_runs_real_facade_acl_registry_router_and_matches_exact_snapshot(
    golden_fixture, golden_cases, case_index
):
    """Compare complete literals with real Facade/Router/audit observations, not fixture fields alone."""
    case = golden_cases[case_index]
    envelope, audit, provider, eligible, fixture_id_by_binding_id = _execute_case(case)
    payload = envelope["artifact_refs"][0]["payload"]
    observed_eligible = [fixture_id_by_binding_id[binding.id] for binding in eligible]
    observed_hits = [fixture_id_by_binding_id[hit["binding_id"]] for hit in payload["hits"]]
    expected = case["expected_tool_result"]

    assert observed_eligible == case["eligible_source_ids"]
    assert provider.calls == case["eligible_source_ids"]
    assert not set(provider.calls) & set(case["forbidden_source_ids"])
    assert observed_hits == expected["ordered_source_ids"] == case["expected_citations"]
    assert [item["resolution"] for item in payload["conflict_annotations"]] == expected["conflict_resolutions"]
    assert [error["code"] for error in envelope["errors"]] == expected["error_codes"]
    assert all(hit["policy_effect"] == expected["policy_effect"] for hit in payload["hits"])
    assert audit.outcome == expected["outcome"]
    assert not set(audit.eligible_binding_ids) & {
        binding_id
        for binding_id, fixture_id in fixture_id_by_binding_id.items()
        if fixture_id in case["forbidden_source_ids"]
    }
    _assert_exact_snapshot(
        envelope,
        audit,
        case,
        golden_fixture["expected_source_catalog"],
        eligible,
        fixture_id_by_binding_id,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("mutation", ["citation_ref", "snapshot_version", "excerpt", "conflict_topic"])
def test_exact_snapshot_detects_reference_content_snapshot_and_conflict_mutations(golden_fixture, mutation):
    """Prove semantic drift cannot pass merely because source ordering stays unchanged."""
    case = next(item for item in golden_fixture["cases"] if item["id"] == "conflict-business-specificity")
    envelope, audit, _provider, eligible, fixture_id_by_binding_id = _execute_case(case)
    mutated_case = deepcopy(case)
    mutated_catalog = deepcopy(golden_fixture["expected_source_catalog"])
    first_source_id = mutated_case["expected_snapshot"]["hit_ids"][0]
    if mutation == "conflict_topic":
        mutated_case["expected_snapshot"]["conflict_annotations"][0]["topic_ref"] = "knowledge-topic://mutated"
    else:
        mutated_catalog[first_source_id][mutation] = "mutated"

    with pytest.raises(AssertionError):
        _assert_exact_snapshot(
            envelope,
            audit,
            mutated_case,
            mutated_catalog,
            eligible,
            fixture_id_by_binding_id,
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mutation",
    [
        "eligible_empty",
        "eligible_reordered",
        "eligible_unknown",
        "eligible_duplicate",
        "extra_summary",
        "missing_summary",
        "reordered_summary",
        "trusted_context",
        "run_attachment",
    ],
)
def test_exact_snapshot_rejects_mutated_actual_audit_identity_and_cardinality(golden_fixture, mutation):
    """Audit expectations must be derived from the persisted row, never reconstructed from expected inputs."""
    case = next(item for item in golden_fixture["cases"] if item["id"] == "conflict-business-specificity")
    envelope, audit, _provider, eligible, fixture_id_by_binding_id = _execute_case(case)
    if mutation == "eligible_empty":
        audit.eligible_binding_ids = []
    elif mutation == "eligible_reordered":
        audit.eligible_binding_ids = list(reversed(audit.eligible_binding_ids))
    elif mutation == "eligible_unknown":
        audit.eligible_binding_ids = [999999] + audit.eligible_binding_ids[1:]
    elif mutation == "eligible_duplicate":
        audit.eligible_binding_ids = [audit.eligible_binding_ids[0]] * 2 + audit.eligible_binding_ids[2:]
    elif mutation == "extra_summary":
        audit.provider_call_summaries = audit.provider_call_summaries + [deepcopy(audit.provider_call_summaries[0])]
    elif mutation == "missing_summary":
        audit.provider_call_summaries = audit.provider_call_summaries[:-1]
    elif mutation == "reordered_summary":
        audit.provider_call_summaries = list(reversed(audit.provider_call_summaries))
    elif mutation == "trusted_context":
        audit.trusted_context_snapshot = {**audit.trusted_context_snapshot, "space_id": 999}
    else:
        audit.run_id = 999

    with pytest.raises(AssertionError):
        _assert_exact_snapshot(
            envelope,
            audit,
            case,
            golden_fixture["expected_source_catalog"],
            eligible,
            fixture_id_by_binding_id,
        )
