"""Deterministic ACL-first federation and advisory knowledge conflict merge."""

import json
import math
import re
import time
from dataclasses import asdict, dataclass

from bkflow.harness.constants import KnowledgeTier, KnowledgeTrustLevel
from bkflow.harness.contracts import (
    KnowledgeConflictAnnotation,
    KnowledgeHit,
    KnowledgeQuery,
    KnowledgeSearchResult,
)
from bkflow.harness.services.knowledge.audit import (
    fingerprint_query,
    opaque_digest_ref,
    record_knowledge_retrieval,
)
from bkflow.harness.services.knowledge.contracts import (
    MAX_PROVIDER_QUERY_BYTES,
    MAX_PROVIDER_RESPONSE_BYTES,
    KnowledgeProviderQuery,
)
from bkflow.harness.services.knowledge.eligibility import eligible_bindings
from bkflow.harness.services.knowledge.providers import KnowledgeProviderSearchResult
from bkflow.harness.services.knowledge.redaction import redact_knowledge_payload

MAX_ROUTED_BINDINGS = 50
MAX_CONFLICT_ANNOTATIONS = 20
MAX_CONFLICT_ALTERNATIVES = 20
_OPAQUE_REF = re.compile(r"^[a-z][a-z0-9+.-]*://\S+$")
_TIER_RANK = {
    KnowledgeTier.PUBLIC: 1,
    KnowledgeTier.PLATFORM: 2,
    KnowledgeTier.SPACE: 3,
    KnowledgeTier.SCOPE: 4,
    KnowledgeTier.GLOBAL: 5,
}
_TRUST_RANK = {
    KnowledgeTrustLevel.VERIFIED: 1,
    KnowledgeTrustLevel.TRUSTED: 2,
}


@dataclass(frozen=True)
class _Candidate:
    """Internal hit facts required for deterministic merge but not Tool output."""

    hit: KnowledgeHit
    provider_hit_ref: str
    topic_key: str

    @property
    def deduplication_key(self):
        return (self.hit.source_ref, self.hit.snapshot_version, self.provider_hit_ref)


def _clamp_score(value):
    """Normalize arbitrary finite provider scores to the documented zero-to-one range."""
    return min(1.0, max(0.0, float(value)))


def _applicable_scope(binding):
    """Return a compact trusted scope label without provider-controlled content."""
    if binding.tier in {KnowledgeTier.GLOBAL, KnowledgeTier.PUBLIC}:
        return binding.tier
    if binding.tier == KnowledgeTier.PLATFORM:
        return "PLATFORM:{}".format(binding.platform_key)
    if binding.tier == KnowledgeTier.SPACE:
        return "SPACE:{}:{}".format(binding.platform_key, binding.space_id)
    return "SCOPE:{}:{}:{}:{}".format(
        binding.platform_key,
        binding.space_id,
        binding.scope_type,
        binding.scope_value,
    )


def _final_score(binding, provider_score):
    """Expose a stable display score while sort precedence remains an explicit tuple."""
    tier_score = _TIER_RANK[binding.tier] / max(_TIER_RANK.values())
    trust_score = _TRUST_RANK[binding.trust_level] / max(_TRUST_RANK.values())
    priority_score = (math.tanh(binding.priority / 100.0) + 1.0) / 2.0
    return round(0.55 * tier_score + 0.2 * trust_score + 0.05 * priority_score + 0.2 * provider_score, 6)


def _candidate_sort_key(candidate):
    """Sort hard precedence first and use stable identities for every remaining tie."""
    hit = candidate.hit
    return (
        -_TIER_RANK[hit.tier],
        -_TRUST_RANK[hit.trust_level],
        -hit.final_score,
        hit.binding_id,
        hit.source_ref,
        candidate.provider_hit_ref,
    )


def _normalize_candidate(binding, provider_hit, context):
    """Redact provider strings and attach only governed binding metadata."""
    policy_version = binding.redaction_policy.get("policy_ref") or context.policy_version
    safe = redact_knowledge_payload(
        {
            "title": provider_hit.title,
            "excerpt": provider_hit.excerpt,
            "citation_ref": provider_hit.citation_ref,
        },
        policy_version,
    )
    provider_score = _clamp_score(provider_hit.provider_score)
    hit_ref = opaque_digest_ref(
        "hit",
        (
            binding.source_ref,
            provider_hit.source_snapshot,
            provider_hit.provider_hit_ref,
            safe["title"],
            safe["excerpt"],
        ),
    )
    hit = KnowledgeHit(
        hit_ref=hit_ref,
        binding_id=binding.id,
        tier=binding.tier,
        provider=binding.provider,
        title=safe["title"],
        excerpt=safe["excerpt"],
        citation_ref=safe["citation_ref"],
        source_ref=binding.source_ref,
        snapshot_version=provider_hit.source_snapshot,
        trust_level=binding.trust_level,
        applicable_scope=_applicable_scope(binding),
        provider_score=provider_score,
        final_score=_final_score(binding, provider_score),
        expires_at=binding.expires_at.isoformat() if binding.expires_at else None,
    )
    topic_key = " ".join(hit.title.casefold().split())
    return _Candidate(hit=hit, provider_hit_ref=provider_hit.provider_hit_ref, topic_key=topic_key)


def _deduplicate(candidates):
    """Keep the strongest deterministic candidate for each exact provider evidence key."""
    chosen = {}
    for candidate in sorted(candidates, key=_candidate_sort_key):
        chosen.setdefault(candidate.deduplication_key, candidate)
    return tuple(sorted(chosen.values(), key=_candidate_sort_key))


def _conflicts(selected):
    """Annotate same-topic contradictory excerpts using only non-executable references."""
    by_topic = {}
    for candidate in selected:
        by_topic.setdefault(candidate.topic_key, []).append(candidate)
    annotations = []
    for topic_key in sorted(by_topic):
        group = tuple(sorted(by_topic[topic_key], key=_candidate_sort_key))
        if len(group) < 2 or len({candidate.hit.excerpt for candidate in group}) < 2:
            continue
        global_candidates = tuple(candidate for candidate in group if candidate.hit.tier == KnowledgeTier.GLOBAL)
        preferred = global_candidates[0] if global_candidates else group[0]
        alternatives = tuple(candidate.hit.hit_ref for candidate in group if candidate is not preferred)[
            :MAX_CONFLICT_ALTERNATIVES
        ]
        annotations.append(
            KnowledgeConflictAnnotation(
                topic_ref=opaque_digest_ref("topic", (topic_key,)),
                resolution=("GLOBAL_POLICY_VALIDATION_REQUIRED" if global_candidates else "BUSINESS_SPECIFICITY"),
                preferred_hit_ref=preferred.hit.hit_ref,
                alternative_hit_refs=alternatives,
            )
        )
    return tuple(annotations)


def _conflicts_for_hits(conflicts, hits):
    """Retain only annotations whose preferred evidence remains part of the selected result."""
    selected_refs = {hit.hit_ref for hit in hits}
    return tuple(conflict for conflict in conflicts if conflict.preferred_hit_ref in selected_refs)[
        :MAX_CONFLICT_ANNOTATIONS
    ]


def _serialized_result_size(hits, conflicts):
    """Measure only the Task 6 result body; Task 7 rechecks the complete Envelope."""
    return len(
        json.dumps(
            {
                "hits": [asdict(hit) for hit in hits],
                "conflict_annotations": [asdict(conflict) for conflict in conflicts],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


class KnowledgeRouter:
    """Federate eligible sources without becoming an Agent or policy engine."""

    def __init__(
        self,
        provider_registry,
        artifact_writer=None,
        inline_result_bytes=MAX_PROVIDER_RESPONSE_BYTES,
    ):
        if (
            isinstance(inline_result_bytes, bool)
            or not isinstance(inline_result_bytes, int)
            or not 1 <= inline_result_bytes <= MAX_PROVIDER_RESPONSE_BYTES
        ):
            raise ValueError("inline_result_bytes must be within the knowledge response budget")
        if artifact_writer is not None and not callable(artifact_writer):
            raise ValueError("artifact_writer must be callable")
        self.provider_registry = provider_registry
        self.artifact_writer = artifact_writer
        self.inline_result_bytes = inline_result_bytes

    def _provider_query(self, binding, query, context):
        """Build one provider request only after the binding passed database eligibility."""
        safe_query = redact_knowledge_payload({"query": query.query}, context.policy_version)["query"]
        safe_query = safe_query.encode("utf-8")[:MAX_PROVIDER_QUERY_BYTES].decode("utf-8", "ignore")
        return KnowledgeProviderQuery(
            query=safe_query,
            top_k=min(query.top_k, binding.max_top_k),
            source_ref=binding.source_ref,
            snapshot_version=binding.snapshot_version,
            correlation_id=context.correlation_id,
        )

    def _search_binding_result(self, binding, provider_result, context):
        """Convert one ordered batch result into candidates and a bounded audit summary."""
        call_ref = opaque_digest_ref("call", (context.correlation_id, binding.id, binding.snapshot_version))
        snapshot_ref = opaque_digest_ref("snapshot", (binding.source_ref, binding.snapshot_version))
        if provider_result.succeeded:
            candidates = tuple(_normalize_candidate(binding, hit, context) for hit in provider_result.hits)
            summary = {
                "provider": binding.provider,
                "call_ref": call_ref,
                "snapshot_ref": snapshot_ref,
                "duration_ms": provider_result.duration_ms,
                "hit_count": len(candidates),
                "outcome": "SUCCESS",
            }
            return candidates, summary, True
        summary = {
            "provider": binding.provider,
            "call_ref": call_ref,
            "snapshot_ref": snapshot_ref,
            "duration_ms": provider_result.duration_ms,
            "hit_count": 0,
            "outcome": "FAILED",
            "error_code": "RETRYABLE_INFRA",
        }
        return (), summary, False

    def _artifact_result(self, hits, conflicts):
        """Move large redacted results behind a trusted artifact writer when configured."""
        if _serialized_result_size(hits, conflicts) <= self.inline_result_bytes:
            return hits, conflicts, (), ()
        if self.artifact_writer is not None:
            payload = {
                "hits": [asdict(hit) for hit in hits],
                "conflict_annotations": [asdict(conflict) for conflict in conflicts],
            }
            try:
                artifact_ref = self.artifact_writer(payload)
            except Exception:
                artifact_ref = None
            if isinstance(artifact_ref, str) and len(artifact_ref) <= 255 and _OPAQUE_REF.fullmatch(artifact_ref):
                return (), (), (artifact_ref,), ("KNOWLEDGE_RESULT_IN_ARTIFACT",)

        bounded = list(hits)
        bounded_conflicts = _conflicts_for_hits(conflicts, bounded)
        while bounded and _serialized_result_size(tuple(bounded), bounded_conflicts) > self.inline_result_bytes:
            bounded.pop()
            bounded_conflicts = _conflicts_for_hits(conflicts, bounded)
        bounded_hits = tuple(bounded)
        return bounded_hits, bounded_conflicts, (), ("KNOWLEDGE_RESULT_TRUNCATED",)

    def search(self, context, request):
        """Run ACL-first retrieval, deterministic merge, safe fallback, and one audit append."""
        query = request if isinstance(request, KnowledgeQuery) else KnowledgeQuery.from_request(request)
        started_at = time.monotonic()
        try:
            bindings = tuple(eligible_bindings(context, query.data_classification)[:MAX_ROUTED_BINDINGS])
        except Exception:
            bindings = ()
            eligibility_failed = True
        else:
            eligibility_failed = False

        candidates = []
        summaries = []
        successful_sources = 0
        failed_sources = 0
        provider_results = [None] * len(bindings)
        provider_searches = []
        provider_search_indexes = []
        for index, binding in enumerate(bindings):
            try:
                provider_query = self._provider_query(binding, query, context)
            except Exception:
                provider_results[index] = KnowledgeProviderSearchResult((), False, 0)
            else:
                provider_searches.append((binding, provider_query))
                provider_search_indexes.append(index)
        for index, provider_result in zip(
            provider_search_indexes,
            self.provider_registry.search_many(provider_searches),
        ):
            provider_results[index] = provider_result
        for binding, provider_result in zip(bindings, provider_results):
            source_candidates, summary, succeeded = self._search_binding_result(binding, provider_result, context)
            candidates.extend(source_candidates)
            summaries.append(summary)
            successful_sources += int(succeeded)
            failed_sources += int(not succeeded)

        selected_hits = ()
        try:
            if eligibility_failed or (bindings and successful_sources == 0):
                outcome = "FAILED"
                errors = ("RETRYABLE_INFRA",)
                warnings = ()
                inline_hits, inline_conflicts, artifact_refs = (), (), ()
            else:
                merged = _deduplicate(candidates)
                selected = merged[: query.top_k]
                selected_hits = tuple(candidate.hit for candidate in selected)
                conflicts = _conflicts_for_hits(_conflicts(merged), selected_hits)
                outcome = "SUCCESS" if selected_hits else "ZERO_RESULTS"
                if failed_sources and selected_hits:
                    outcome = "PARTIAL_SUCCESS"
                inline_hits, inline_conflicts, artifact_refs, artifact_warnings = self._artifact_result(
                    selected_hits, conflicts
                )
                warnings = (("KNOWLEDGE_SOURCE_FAILED",) if failed_sources else ()) + artifact_warnings
                errors = ()
        except Exception:
            outcome = "FAILED"
            errors = ("RETRYABLE_INFRA",)
            warnings = ()
            inline_hits, inline_conflicts, artifact_refs = (), (), ()

        record_knowledge_retrieval(
            context=context,
            query=query,
            bindings=bindings,
            provider_call_summaries=summaries,
            hits=selected_hits,
            duration_ms=(time.monotonic() - started_at) * 1000,
            outcome=outcome,
        )
        return KnowledgeSearchResult(
            query_fingerprint=fingerprint_query(query.query),
            hits=inline_hits,
            conflict_annotations=inline_conflicts,
            artifact_refs=artifact_refs,
            warning_codes=tuple(dict.fromkeys(warnings)),
            error_codes=errors,
        )
