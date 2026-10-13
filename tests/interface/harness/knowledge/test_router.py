"""Federated knowledge routing, merge, and failure isolation contracts."""

import json
import threading
import time
from dataclasses import fields

import pytest
from django.utils import timezone

from bkflow.harness.constants import (
    KnowledgeBindingStatus,
    KnowledgeRetrievalMode,
    KnowledgeTier,
    KnowledgeTrustLevel,
)
from bkflow.harness.contracts import KnowledgeHit, TrustedHarnessContext
from bkflow.harness.models import KnowledgeRetrievalAudit, KnowledgeSourceBinding
from bkflow.harness.services.knowledge.audit import opaque_digest_ref
from bkflow.harness.services.knowledge.contracts import (
    KnowledgeProviderQuery,
    ProviderKnowledgeHit,
)
from bkflow.harness.services.knowledge.providers import KnowledgeProviderRegistry
from bkflow.harness.services.knowledge.router import KnowledgeRouter


def trusted_context(**overrides):
    """Build the immutable authority normally derived from the APIGW request."""
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
        "correlation_id": "knowledge-router-test",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


def binding_values(source_ref, **overrides):
    """Build one complete eligible binding with an independently selected source."""
    values = {
        "provider": "fixture-docs",
        "source_ref": source_ref,
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
        "credential_ref": None,
        "provider_config": {"collection": "workflow-guides"},
    }
    values.update(overrides)
    return values


def create_binding(source_suffix, **overrides):
    """Persist one valid binding using a non-secret source reference."""
    source_ref = overrides.pop("source_ref", "knowledge://workflow-guides/{}".format(source_suffix))
    binding = KnowledgeSourceBinding(**binding_values(source_ref, **overrides))
    binding.full_clean()
    binding.save()
    return binding


def provider_hit(hit_ref, title="Restart service", excerpt="Drain traffic before restart.", score=0.8):
    """Return a complete provider hit; registry will replace provider-controlled citations."""
    return ProviderKnowledgeHit(
        provider_hit_ref=hit_ref,
        title=title,
        excerpt=excerpt,
        citation_ref="provider-controlled-citation",
        source_snapshot="provider-controlled-snapshot",
        provider_score=score,
    )


class SourceAwareProvider:
    """Deterministic provider whose source-specific behavior is visible to assertions."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def search(self, binding, query):
        self.calls.append((binding.id, binding.source_ref, query.top_k, query.query))
        response = self.responses[binding.source_ref]
        if isinstance(response, BaseException):
            raise response
        return response


def router_with(responses, **kwargs):
    """Construct the real registry/router stack while mocking only external retrieval."""
    provider = SourceAwareProvider(responses)
    registry = KnowledgeProviderRegistry({"fixture-docs": provider})
    return KnowledgeRouter(provider_registry=registry, **kwargs), provider


def request(**overrides):
    """Build the public Task 6 request before Task 7 serializer wiring."""
    values = {"query": "restart service safely", "top_k": 10, "data_classification": "internal"}
    values.update(overrides)
    return values


def tier_dimensions(tier):
    """Return the exact trusted dimensions required by one knowledge tier."""
    return {
        KnowledgeTier.GLOBAL: {},
        KnowledgeTier.PUBLIC: {},
        KnowledgeTier.PLATFORM: {"platform_key": "bkaidev"},
        KnowledgeTier.SPACE: {"platform_key": "bkaidev", "space_id": 902},
        KnowledgeTier.SCOPE: {
            "platform_key": "bkaidev",
            "space_id": 902,
            "scope_type": "project",
            "scope_value": "902",
        },
    }[tier]


@pytest.mark.django_db
def test_router_filters_forbidden_bindings_before_any_provider_dispatch():
    """Moving ACL checks after provider search would expose a cross-space source."""
    allowed = create_binding("allowed")
    forbidden = create_binding(
        "forbidden",
        tier=KnowledgeTier.SPACE,
        platform_key="bkaidev",
        space_id=903,
    )
    responses = {allowed.source_ref: [provider_hit("provider-hit://allowed/1")]}
    router, provider = router_with(responses)

    result = router.search(trusted_context(), request())

    assert result.error_codes == ()
    assert [call[0] for call in provider.calls] == [allowed.id]
    assert forbidden.id not in KnowledgeRetrievalAudit.objects.get().eligible_binding_ids


@pytest.mark.django_db
def test_router_clamps_each_provider_query_to_the_binding_top_k():
    """Using only the caller limit would bypass a source owner's lower retrieval budget."""
    binding = create_binding("bounded", max_top_k=2)
    responses = {
        binding.source_ref: [
            provider_hit("provider-hit://bounded/1"),
            provider_hit("provider-hit://bounded/2"),
            provider_hit("provider-hit://bounded/3"),
        ]
    }
    router, provider = router_with(responses)

    result = router.search(trusted_context(), request(top_k=5))

    assert provider.calls[0][2] == 2
    assert len(result.hits) == 2


@pytest.mark.django_db
def test_router_deduplicates_by_source_snapshot_and_provider_hit_ref():
    """Deduplicating by title alone would collapse distinct evidence or retain duplicate evidence."""
    public = create_binding("shared", source_ref="knowledge://workflow-guides/shared")
    scope = create_binding(
        "shared-scope",
        source_ref="knowledge://workflow-guides/shared",
        tier=KnowledgeTier.SCOPE,
        platform_key="bkaidev",
        space_id=902,
        scope_type="project",
        scope_value="902",
    )
    responses = {
        public.source_ref: [provider_hit("provider-hit://shared/1")],
    }
    router, _provider = router_with(responses)

    result = router.search(trusted_context(), request())

    assert len(result.hits) == 1
    assert result.hits[0].binding_id == scope.id


@pytest.mark.django_db
def test_content_digest_snapshot_prevents_changed_content_from_being_deduplicated():
    """Using only the governed binding version would collapse different content behind one provider hit ref."""
    public = create_binding("changing", source_ref="knowledge://workflow-guides/changing")
    create_binding(
        "changing-scope",
        source_ref=public.source_ref,
        tier=KnowledgeTier.SCOPE,
        platform_key="bkaidev",
        space_id=902,
        scope_type="project",
        scope_value="902",
    )

    class ContentChangingProvider:
        """Return different content for the same governed source, version, and provider hit identity."""

        def search(self, binding, query):
            excerpt = "scope content B" if binding.tier == KnowledgeTier.SCOPE else "public content A"
            return [provider_hit("provider-hit://changing/1", excerpt=excerpt)]

    router = KnowledgeRouter(provider_registry=KnowledgeProviderRegistry({"fixture-docs": ContentChangingProvider()}))

    result = router.search(trusted_context(), request(top_k=2))

    assert len(result.hits) == 2
    assert len({hit.snapshot_version for hit in result.hits}) == 2
    assert all(hit.snapshot_version.startswith("sha256:") for hit in result.hits)
    assert len(KnowledgeRetrievalAudit.objects.get().snapshot_refs) == 2


@pytest.mark.django_db
def test_changed_content_changes_hit_and_audit_snapshot_across_calls():
    """Reusing one binding version in audits would make later content changes impossible to prove."""
    binding = create_binding("changing-over-time")

    class SequentialContentProvider:
        """Expose two provider bodies under one stable provider hit identity."""

        def __init__(self):
            self.calls = 0

        def search(self, binding, query):
            self.calls += 1
            return [provider_hit("provider-hit://changing-over-time/1", excerpt="content {}".format(self.calls))]

    router = KnowledgeRouter(provider_registry=KnowledgeProviderRegistry({"fixture-docs": SequentialContentProvider()}))

    first = router.search(trusted_context(correlation_id="content-a"), request(top_k=1))
    second = router.search(trusted_context(correlation_id="content-b"), request(top_k=1))
    audits = list(KnowledgeRetrievalAudit.objects.order_by("id"))

    assert first.hits[0].source_ref == binding.source_ref
    assert first.hits[0].snapshot_version != second.hits[0].snapshot_version
    assert audits[0].snapshot_refs != audits[1].snapshot_refs


@pytest.mark.django_db
def test_business_guidance_prefers_scope_space_platform_then_public():
    """A score-only merge would let generic guidance outrank a trusted matching scope."""
    responses = {}
    for tier in (KnowledgeTier.PUBLIC, KnowledgeTier.PLATFORM, KnowledgeTier.SPACE, KnowledgeTier.SCOPE):
        binding = create_binding(tier.lower(), tier=tier, **tier_dimensions(tier))
        responses[binding.source_ref] = [
            provider_hit(
                "provider-hit://{}/1".format(tier.lower()),
                title="Restart service",
                excerpt="{} preference".format(tier),
                score=0.5,
            )
        ]
    router, _provider = router_with(responses)

    result = router.search(trusted_context(), request(top_k=4))

    assert [hit.tier for hit in result.hits] == [
        KnowledgeTier.SCOPE,
        KnowledgeTier.SPACE,
        KnowledgeTier.PLATFORM,
        KnowledgeTier.PUBLIC,
    ]
    assert result.conflict_annotations[0].resolution == "BUSINESS_SPECIFICITY"
    assert result.conflict_annotations[0].preferred_hit_ref == result.hits[0].hit_ref


@pytest.mark.django_db
def test_global_guidance_is_preserved_as_advisory_and_requires_policy_validation():
    """Treating business content as an override could silently replace a documented global guardrail."""
    global_binding = create_binding("global", tier=KnowledgeTier.GLOBAL)
    scope_binding = create_binding(
        "scope",
        tier=KnowledgeTier.SCOPE,
        platform_key="bkaidev",
        space_id=902,
        scope_type="project",
        scope_value="902",
    )
    responses = {
        global_binding.source_ref: [
            provider_hit("provider-hit://global/1", excerpt="Require approval before restart.")
        ],
        scope_binding.source_ref: [provider_hit("provider-hit://scope/1", excerpt="Restart without approval.")],
    }
    router, _provider = router_with(responses)

    result = router.search(trusted_context(), request(top_k=2))

    assert [hit.tier for hit in result.hits] == [KnowledgeTier.GLOBAL, KnowledgeTier.SCOPE]
    assert all(hit.policy_effect == "ADVISORY" for hit in result.hits)
    assert result.conflict_annotations == (result.conflict_annotations[0],)
    assert result.conflict_annotations[0].resolution == "GLOBAL_POLICY_VALIDATION_REQUIRED"
    assert result.conflict_annotations[0].preferred_hit_ref == result.hits[0].hit_ref


@pytest.mark.django_db
@pytest.mark.parametrize(
    "preferred_tier,alternative_tier,expected_resolution",
    [
        (KnowledgeTier.GLOBAL, KnowledgeTier.SCOPE, "GLOBAL_POLICY_VALIDATION_REQUIRED"),
        (KnowledgeTier.SCOPE, KnowledgeTier.SPACE, "BUSINESS_SPECIFICITY"),
    ],
)
def test_conflict_detection_precedes_top_k_even_when_only_preferred_hit_is_inline(
    preferred_tier, alternative_tier, expected_resolution
):
    """Detecting conflicts after top-k would hide a contradictory lower-precedence source from the caller."""
    bindings = []
    responses = {}
    for tier, excerpt in ((preferred_tier, "preferred advice"), (alternative_tier, "contradictory advice")):
        binding = create_binding("conflict-{}".format(tier.lower()), tier=tier, **tier_dimensions(tier))
        bindings.append(binding)
        responses[binding.source_ref] = [
            provider_hit("provider-hit://conflict/{}/1".format(tier.lower()), excerpt=excerpt)
        ]
    router, _provider = router_with(responses)

    result = router.search(trusted_context(), request(top_k=1))

    assert len(result.hits) == 1
    assert result.hits[0].tier == preferred_tier
    assert len(result.conflict_annotations) == 1
    annotation = result.conflict_annotations[0]
    assert annotation.resolution == expected_resolution
    assert annotation.preferred_hit_ref == result.hits[0].hit_ref
    assert len(annotation.alternative_hit_refs) == 1
    assert annotation.alternative_hit_refs[0] != result.hits[0].hit_ref


@pytest.mark.django_db
def test_conflict_annotation_budget_is_applied_after_filtering_to_selected_preferred_hits():
    """Unselected earlier topics must not consume the bounded annotation budget before top-k relevance filtering."""
    responses = {}
    for topic_index in range(20):
        for alternative_index, excerpt in enumerate(("advice A", "advice B")):
            binding = create_binding("earlier-{}-{}".format(topic_index, alternative_index))
            responses[binding.source_ref] = [
                provider_hit(
                    "provider-hit://earlier/{}/{}".format(topic_index, alternative_index),
                    title="aa-topic-{:02d}".format(topic_index),
                    excerpt=excerpt,
                )
            ]

    global_binding = create_binding("selected-global", tier=KnowledgeTier.GLOBAL)
    scope_binding = create_binding(
        "selected-scope",
        tier=KnowledgeTier.SCOPE,
        **tier_dimensions(KnowledgeTier.SCOPE),
    )
    responses[global_binding.source_ref] = [
        provider_hit("provider-hit://selected/global", title="zz-selected", excerpt="global advice")
    ]
    responses[scope_binding.source_ref] = [
        provider_hit("provider-hit://selected/scope", title="zz-selected", excerpt="scope advice")
    ]
    router, _provider = router_with(responses)

    result = router.search(trusted_context(), request(top_k=1))

    assert result.hits[0].binding_id == global_binding.id
    assert len(result.conflict_annotations) == 1
    assert result.conflict_annotations[0].preferred_hit_ref == result.hits[0].hit_ref


@pytest.mark.django_db
def test_artifact_and_inline_truncation_preserve_conflicts_found_before_top_k():
    """Recomputing annotations from the shortened payload would erase hidden contradictory evidence."""
    scope = create_binding("artifact-conflict-scope", tier=KnowledgeTier.SCOPE, **tier_dimensions(KnowledgeTier.SCOPE))
    space = create_binding("artifact-conflict-space", tier=KnowledgeTier.SPACE, **tier_dimensions(KnowledgeTier.SPACE))
    responses = {
        scope.source_ref: [provider_hit("provider-hit://artifact-conflict/scope", excerpt="scope advice")],
        space.source_ref: [provider_hit("provider-hit://artifact-conflict/space", excerpt="space advice")],
    }
    written = []

    def artifact_writer(payload):
        written.append(payload)
        return "knowledge-artifact://sha256/conflict-result"

    artifact_router, _provider = router_with(responses, artifact_writer=artifact_writer, inline_result_bytes=300)
    artifact_result = artifact_router.search(trusted_context(), request(top_k=1))

    assert artifact_result.hits == ()
    assert len(written[0]["hits"]) == 1
    assert len(written[0]["conflict_annotations"]) == 1
    assert written[0]["conflict_annotations"][0]["preferred_hit_ref"] == written[0]["hits"][0]["hit_ref"]
    assert written[0]["conflict_annotations"][0]["alternative_hit_refs"][0] != written[0]["hits"][0]["hit_ref"]

    truncation_router, _provider = router_with(responses, inline_result_bytes=1200)
    truncated = truncation_router.search(trusted_context(correlation_id="truncated-conflict"), request(top_k=2))

    assert truncated.warning_codes == ("KNOWLEDGE_RESULT_TRUNCATED",)
    assert len(truncated.hits) == 1
    assert len(truncated.conflict_annotations) == 1
    assert truncated.conflict_annotations[0].preferred_hit_ref == truncated.hits[0].hit_ref


@pytest.mark.django_db
def test_tie_breaking_is_stable_across_repeated_searches():
    """Depending on provider or database iteration order would make prompts irreproducible."""
    first = create_binding("first")
    second = create_binding("second")
    responses = {
        first.source_ref: [provider_hit("provider-hit://first/1", title="First")],
        second.source_ref: [provider_hit("provider-hit://second/1", title="Second")],
    }
    router, _provider = router_with(responses)

    first_result = router.search(trusted_context(), request(top_k=2))
    second_result = router.search(trusted_context(), request(top_k=2))

    assert [hit.binding_id for hit in first_result.hits] == [first.id, second.id]
    assert first_result.hits == second_result.hits


@pytest.mark.django_db
def test_partial_provider_failure_returns_usable_hits_and_bounded_warning():
    """Failing the whole search would discard usable knowledge from healthy sources."""
    healthy = create_binding("healthy")
    failed = create_binding("failed")
    router, _provider = router_with(
        {
            healthy.source_ref: [provider_hit("provider-hit://healthy/1")],
            failed.source_ref: TimeoutError("Bearer resolved-provider-secret"),
        }
    )

    result = router.search(trusted_context(), request())

    assert len(result.hits) == 1
    assert result.error_codes == ()
    assert result.warning_codes == ("KNOWLEDGE_SOURCE_FAILED",)
    audit = KnowledgeRetrievalAudit.objects.get()
    assert audit.outcome == "PARTIAL_SUCCESS"
    assert failed.id in audit.eligible_binding_ids
    assert {summary["outcome"] for summary in audit.provider_call_summaries} == {"SUCCESS", "FAILED"}
    assert all(summary.get("error_code") in {None, "RETRYABLE_INFRA"} for summary in audit.provider_call_summaries)
    assert "resolved-provider-secret" not in repr(result) + repr(audit.provider_call_summaries)


@pytest.mark.django_db
def test_successful_zero_hits_recover_without_infrastructure_error():
    """Conflating an empty source with a failed source would trigger pointless retries."""
    empty = create_binding("empty")
    create_binding("failed", provider="unregistered-docs")
    router, _provider = router_with({empty.source_ref: []})

    result = router.search(trusted_context(), request())

    assert result.hits == ()
    assert result.error_codes == ()
    assert result.warning_codes == ("KNOWLEDGE_SOURCE_FAILED",)
    assert KnowledgeRetrievalAudit.objects.get().outcome == "ZERO_RESULTS"


@pytest.mark.django_db
def test_all_provider_failures_return_only_normalized_retryable_infra():
    """Reflecting an adapter exception would leak provider details and suppress the retry contract."""
    first = create_binding("first")
    second = create_binding("second")
    router, _provider = router_with(
        {
            first.source_ref: TimeoutError("provider host and resolved-secret-one"),
            second.source_ref: RuntimeError("provider host and resolved-secret-two"),
        }
    )

    result = router.search(trusted_context(), request(query="Bearer resolved-query-secret"))

    assert result.hits == ()
    assert result.error_codes == ("RETRYABLE_INFRA",)
    assert result.warning_codes == ()
    serialized = repr(result) + repr(KnowledgeRetrievalAudit.objects.get().provider_call_summaries)
    assert "resolved-secret-one" not in serialized
    assert "resolved-secret-two" not in serialized
    assert "resolved-query-secret" not in serialized
    assert KnowledgeRetrievalAudit.objects.get().eligible_binding_ids == [first.id, second.id]
    assert KnowledgeRetrievalAudit.objects.get().outcome == "FAILED"


@pytest.mark.django_db
def test_provider_fanout_uses_one_total_deadline_and_keeps_running_slots_until_completion():
    """Sequential per-source timeouts or early slot release would exceed the request budget and worker ceiling."""
    bindings = [create_binding("slow-{}".format(index)) for index in range(4)]
    release = threading.Event()
    state_lock = threading.Lock()
    active = 0
    max_active = 0
    calls = []

    class SlowProvider:
        """Hold real registry workers so the test can observe deadline and slot ownership."""

        def search(self, binding, query):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
                calls.append(binding.id)
            try:
                release.wait(timeout=1)
                return []
            finally:
                with state_lock:
                    active -= 1

    registry = KnowledgeProviderRegistry(
        {"fixture-docs": SlowProvider()}, timeout_seconds=0.08, max_workers=2, max_in_flight=2
    )
    router = KnowledgeRouter(registry)
    started_at = time.monotonic()
    try:
        result = router.search(trusted_context(), request())
        elapsed = time.monotonic() - started_at
        audit = KnowledgeRetrievalAudit.objects.get()

        assert elapsed < 0.13
        assert result.error_codes == ("RETRYABLE_INFRA",)
        assert max_active == 2
        assert calls == [bindings[0].id, bindings[1].id]
        assert audit.eligible_binding_ids == [binding.id for binding in bindings]
        assert [summary["call_ref"] for summary in audit.provider_call_summaries] == [
            opaque_digest_ref("call", (trusted_context().correlation_id, binding.id, binding.snapshot_version))
            for binding in bindings
        ]

        with pytest.raises(Exception, match="RETRYABLE_INFRA"):
            registry.search(
                bindings[2],
                KnowledgeProviderQuery(
                    query="restart service safely",
                    top_k=5,
                    source_ref=bindings[2].source_ref,
                    snapshot_version=bindings[2].snapshot_version,
                    correlation_id=trusted_context().correlation_id,
                ),
            )
        assert calls == [bindings[0].id, bindings[1].id]
    finally:
        release.set()
        registry.close()


@pytest.mark.django_db
def test_large_merged_result_is_written_to_artifact_instead_of_inline():
    """Returning every merged excerpt inline would overflow the later complete Envelope budget."""
    binding = create_binding("large")
    responses = {
        binding.source_ref: [
            provider_hit("provider-hit://large/{}".format(index), title="Guide {}".format(index), excerpt="x" * 300)
            for index in range(3)
        ]
    }
    written = []

    def artifact_writer(payload):
        written.append(payload)
        return "knowledge-artifact://sha256/large-result"

    router, _provider = router_with(responses, artifact_writer=artifact_writer, inline_result_bytes=400)

    result = router.search(trusted_context(), request(top_k=3))

    assert result.hits == ()
    assert result.artifact_refs == ("knowledge-artifact://sha256/large-result",)
    assert result.warning_codes == ("KNOWLEDGE_RESULT_IN_ARTIFACT",)
    assert len(written) == 1
    assert len(written[0]["hits"]) == 3
    assert all(hit["policy_effect"] == "ADVISORY" for hit in written[0]["hits"])
    assert KnowledgeRetrievalAudit.objects.get().hit_refs == [hit["hit_ref"] for hit in written[0]["hits"]]


@pytest.mark.django_db
def test_query_title_excerpt_and_artifact_redact_embedded_credentials_without_erasing_context():
    """Key-only or prefix-only redaction would leak embedded credentials through output, artifacts, or audit."""
    binding = create_binding("embedded-secrets")
    responses = {
        binding.source_ref: [
            provider_hit(
                "provider-hit://embedded/{}".format(index),
                title="Run with app_secret=resolved-app and Bearer abc:def safely",
                excerpt=(
                    "Keep this guidance before api_key=resolved-key, token=resolved-token, "
                    "secret=resolved-secret and after.\nCookie: session=resolved-cookie"
                ),
            )
            for index in range(2)
        ]
    }
    written = []

    def artifact_writer(payload):
        written.append(payload)
        return "knowledge-artifact://sha256/redacted-result"

    router, provider = router_with(responses, artifact_writer=artifact_writer, inline_result_bytes=300)

    result = router.search(
        trusted_context(),
        request(
            query="Keep query context before access_token=resolved-access and Bearer abc$def after.",
            top_k=2,
        ),
    )

    audit = KnowledgeRetrievalAudit.objects.get()
    serialized_artifact = json.dumps(written, ensure_ascii=False, sort_keys=True)
    serialized_audit = json.dumps(
        {
            "query": audit.redacted_query,
            "calls": audit.provider_call_summaries,
            "hits": audit.hit_refs,
            "snapshots": audit.snapshot_refs,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    combined = repr(result) + serialized_artifact + serialized_audit
    outbound_query = provider.calls[0][3]
    assert outbound_query == "Keep query context before access_token=[REDACTED] and [REDACTED] after."
    assert "resolved-access" not in outbound_query
    assert "abc$def" not in outbound_query
    assert result.artifact_refs == ("knowledge-artifact://sha256/redacted-result",)
    for secret in (
        "resolved-access",
        "abc$def",
        "resolved-app",
        "abc:def",
        "resolved-key",
        "resolved-token",
        "resolved-secret",
        "resolved-cookie",
    ):
        assert secret not in combined
    assert "Run with" in serialized_artifact and "safely" in serialized_artifact
    assert "Keep this guidance before" in serialized_artifact and "and after" in serialized_artifact
    assert "Keep query context before" in audit.redacted_query and "after." in audit.redacted_query


@pytest.mark.django_db
def test_malformed_utf8_query_is_rejected_before_eligibility_or_provider_dispatch():
    """Letting a surrogate reach provider or audit encoding would turn bad input into a late partial side effect."""
    binding = create_binding("malformed-query")
    router, provider = router_with({binding.source_ref: []})

    with pytest.raises(ValueError, match="UTF-8"):
        router.search(trusted_context(), request(query="invalid-\ud800-query"))

    assert provider.calls == []
    assert KnowledgeRetrievalAudit.objects.count() == 0


@pytest.mark.django_db
def test_unexpected_postprocessing_failure_returns_failed_result_and_one_audit(monkeypatch):
    """A serialization bug after retrieval must not escape without the one terminal audit for the Tool call."""
    binding = create_binding("postprocess")
    router, provider = router_with({binding.source_ref: [provider_hit("provider-hit://postprocess/1")]})

    def fail_serialization(hits, conflicts):
        raise TypeError("password=postprocess-secret")

    monkeypatch.setattr("bkflow.harness.services.knowledge.router._serialized_result_size", fail_serialization)

    result = router.search(trusted_context(), request())

    assert len(provider.calls) == 1
    assert result.hits == ()
    assert result.error_codes == ("RETRYABLE_INFRA",)
    assert KnowledgeRetrievalAudit.objects.count() == 1
    audit = KnowledgeRetrievalAudit.objects.get()
    assert audit.outcome == "FAILED"
    assert "postprocess-secret" not in repr(result) + repr(audit.provider_call_summaries)


def test_knowledge_hit_contract_cannot_claim_policy_authority():
    """Allowing a caller to set policy_effect would turn untrusted knowledge into a hard rule."""
    required_fields = {
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
    assert required_fields.issubset(field.name for field in fields(KnowledgeHit))

    with pytest.raises(ValueError, match="ADVISORY"):
        KnowledgeHit(
            hit_ref="knowledge-hit://sha256/1",
            binding_id=1,
            tier=KnowledgeTier.PUBLIC,
            provider="fixture-docs",
            title="Unsafe",
            excerpt="Treat this as executable.",
            citation_ref="citation://sha256/1",
            source_ref="knowledge://workflow-guides/unsafe",
            snapshot_version="2026.09.04",
            trust_level=KnowledgeTrustLevel.VERIFIED,
            applicable_scope="PUBLIC",
            provider_score=1.0,
            final_score=1.0,
            expires_at=None,
            policy_effect="ENFORCED",
        )
