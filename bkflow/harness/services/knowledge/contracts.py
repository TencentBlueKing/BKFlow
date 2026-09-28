"""Frozen provider-facing DTOs for advisory knowledge retrieval."""

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol, Sequence, TypeVar

from bkflow.harness.services.knowledge.security import (
    is_bounded_non_secret_text,
    is_safe_opaque_uri,
)

PROVIDER_MODE = "provider_spi_only"
PROVIDER_IDENTITY_MODE = "platform_service_identity"
PROVIDER_SNAPSHOT_MODE = "content_digest_snapshot"
PROVIDER_CONTENT_TRUST = "ADVISORY"
KNOWLEDGE_REDACTION_BASELINE = "builtin_credential_redaction_v1"

DEFAULT_BINDING_TOP_K = 5
MAX_TOP_K = 20
MAX_EXCERPT_BYTES = 4096
# This bounds normalized provider hits only; the later Task 7 Envelope boundary must recheck its complete payload.
MAX_PROVIDER_RESPONSE_BYTES = 65536
PROVIDER_TIMEOUT_SECONDS = 3
MAX_PROVIDER_QUERY_BYTES = 2000
MAX_SOURCE_REF_BYTES = 2048
MAX_SNAPSHOT_VERSION_BYTES = 128
MAX_CORRELATION_ID_BYTES = 128


@dataclass(frozen=True)
class KnowledgeProviderQuery:
    """Trusted, non-secret query passed to a registered provider."""

    query: str
    top_k: int
    source_ref: str
    snapshot_version: str
    correlation_id: str

    def __post_init__(self):
        """Reject unsafe outbound text and counts outside the provider budget."""
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int) or not 1 <= self.top_k <= MAX_TOP_K:
            raise ValueError("top_k must be between 1 and {}".format(MAX_TOP_K))
        if not (
            is_bounded_non_secret_text(self.query, MAX_PROVIDER_QUERY_BYTES)
            and is_safe_opaque_uri(self.source_ref, "knowledge", MAX_SOURCE_REF_BYTES)
            and is_bounded_non_secret_text(self.snapshot_version, MAX_SNAPSHOT_VERSION_BYTES)
            and is_bounded_non_secret_text(self.correlation_id, MAX_CORRELATION_ID_BYTES)
        ):
            raise ValueError("provider query must contain only bounded non-secret UTF-8 strings")


@dataclass(frozen=True)
class ProviderKnowledgeHit:
    """One advisory provider hit; registry normalization makes it safe to expose."""

    provider_hit_ref: str
    title: str
    excerpt: str
    citation_ref: str
    source_snapshot: str
    provider_score: float


class KnowledgeProvider(Protocol):
    """Passive provider SPI; implementations must not invoke an LLM."""

    def search(self, binding: object, query: KnowledgeProviderQuery) -> Sequence[ProviderKnowledgeHit]:
        """Search one already-authorized binding using deterministic provider behavior."""


ProviderCallResult = TypeVar("ProviderCallResult")


class ProviderCredentialDispatcher(Protocol):
    """Adapter injection boundary that never returns a resolved credential to the router."""

    def invoke(
        self,
        credential_ref: str,
        call: Callable[[Mapping[str, object]], ProviderCallResult],
    ) -> ProviderCallResult:
        """Resolve a reference for one adapter call and discard its secret material afterward."""
