"""Data-minimal, append-only audit persistence for one knowledge Tool call."""

import hashlib

from django.core.exceptions import ValidationError

from bkflow.harness.contracts import KnowledgeQuery
from bkflow.harness.models import HarnessRun, KnowledgeRetrievalAudit
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.knowledge.redaction import redact_knowledge_payload


def fingerprint_query(query):
    """Hash raw search text so audits can correlate calls without exposing content."""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def opaque_digest_ref(kind, parts):
    """Build a bounded reference from trusted or already-redacted scalar facts."""
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return "knowledge-{}://sha256/{}".format(kind, digest)


def _trusted_context_snapshot(context):
    """Retain only the model-defined positive audit schema."""
    return {
        "platform_key": context.platform_key,
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope_type": context.scope_type,
        "scope_value": context.scope_value,
        "target_environment": context.target_environment,
        "policy_version": context.policy_version,
        "mcp_contract_version": context.mcp_contract_version,
        "correlation_id": context.correlation_id,
    }


def _matching_run(context, run_id):
    """Resolve an optional run reference only inside the complete trusted authority scope."""
    if run_id is None:
        return None
    try:
        scope = canonical_scope(context.scope_type, context.scope_value)
        return HarnessRun.objects.filter(
            run_id=run_id,
            platform=context.platform_key,
            platform_app=context.platform_app,
            actor=context.actor,
            space_id=context.space_id,
            scope=scope,
            environment=context.target_environment,
            policy_version=context.policy_version,
            mcp_contract_version=context.mcp_contract_version,
        ).first()
    except (TypeError, ValueError, ValidationError):
        return None


def record_knowledge_retrieval(
    *,
    context,
    query,
    bindings,
    provider_call_summaries,
    hits,
    duration_ms,
    outcome,
):
    """Append exactly one bounded evidence row for a completed Router invocation."""
    redacted_query = redact_knowledge_payload({"query": query.query}, context.policy_version)["query"]
    redacted_query = redacted_query[:2000]
    snapshot_refs = list(
        dict.fromkeys(opaque_digest_ref("snapshot", (hit.source_ref, hit.snapshot_version)) for hit in hits)
    )
    return KnowledgeRetrievalAudit.objects.create(
        run=_matching_run(context, query.run_id),
        trusted_context_snapshot=_trusted_context_snapshot(context),
        query_fingerprint=fingerprint_query(query.query),
        redacted_query=redacted_query,
        eligible_binding_ids=[binding.id for binding in bindings],
        provider_call_summaries=list(provider_call_summaries),
        hit_refs=[hit.hit_ref for hit in hits],
        snapshot_refs=snapshot_refs,
        correlation_id=context.correlation_id,
        duration_ms=max(0, min(int(duration_ms), 3_600_000)),
        outcome=outcome,
    )


def record_denied_knowledge_retrieval(context, request):
    """Append one data-minimal denial before a forbidden run reference returns to transport."""
    query = request if isinstance(request, KnowledgeQuery) else KnowledgeQuery.from_request(request)
    return record_knowledge_retrieval(
        context=context,
        query=query,
        bindings=(),
        provider_call_summaries=(),
        hits=(),
        duration_ms=0,
        outcome="DENIED",
    )
