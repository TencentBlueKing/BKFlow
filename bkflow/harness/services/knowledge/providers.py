"""Fail-closed knowledge provider registry and deterministic test provider."""

import hashlib
import json
import math
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from threading import BoundedSemaphore, Condition, Lock
from typing import Mapping, Sequence

from bkflow.harness.services.knowledge.contracts import (
    MAX_EXCERPT_BYTES,
    MAX_PROVIDER_RESPONSE_BYTES,
    PROVIDER_TIMEOUT_SECONDS,
    KnowledgeProvider,
    KnowledgeProviderQuery,
    ProviderKnowledgeHit,
)

MAX_PROVIDER_NAME_BYTES = 64
MAX_PROVIDER_HIT_REF_BYTES = 2048
MAX_PROVIDER_TITLE_BYTES = 4096
DEFAULT_PROVIDER_WORKERS = 4
DEFAULT_PROVIDER_MAX_IN_FLIGHT = 4


class KnowledgeProviderError(ValueError):
    """Safe provider failure containing only a normalized public code."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class KnowledgeProviderSearchResult:
    """One ordered, non-reflective result from a bounded provider fan-out."""

    hits: tuple
    succeeded: bool
    duration_ms: int


def _utf8_size(value):
    """Return the encoded size used by all provider byte budgets."""
    return len(value.encode("utf-8"))


def _bounded_string(value, max_bytes):
    """Validate a non-empty string controlled by an external provider."""
    return isinstance(value, str) and value and _utf8_size(value) <= max_bytes


def _truncate_utf8(value, max_bytes):
    """Truncate at a UTF-8 character boundary."""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", "ignore")


def _digest(parts):
    """Hash canonical provider facts into a stable bounded reference."""
    serialized = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class KnowledgeProviderRegistry:
    """Explicit registry that bounds, normalizes, and distrusts every provider response."""

    def __init__(
        self,
        providers: Mapping[str, KnowledgeProvider] = None,
        timeout_seconds=PROVIDER_TIMEOUT_SECONDS,
        max_workers=DEFAULT_PROVIDER_WORKERS,
        max_in_flight=DEFAULT_PROVIDER_MAX_IN_FLIGHT,
    ):
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
            or timeout_seconds > PROVIDER_TIMEOUT_SECONDS
        ):
            raise ValueError("timeout_seconds must be within the provider budget")
        if (
            isinstance(max_workers, bool)
            or not isinstance(max_workers, int)
            or isinstance(max_in_flight, bool)
            or not isinstance(max_in_flight, int)
            or max_workers < 1
            or max_in_flight < 1
            or max_workers > max_in_flight
        ):
            raise ValueError("provider concurrency limits must be positive and bounded")
        self._providers = {}
        self.timeout_seconds = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="knowledge-provider")
        self._in_flight_slots = BoundedSemaphore(max_in_flight)
        self._slot_condition = Condition()
        self._slot_waiters = deque()
        self._slot_generation = 0
        self._lifecycle_lock = Lock()
        self._closed = False
        for provider_name, provider in (providers or {}).items():
            self.register(provider_name, provider)

    @property
    def is_ready(self):
        """Production readiness requires at least one explicit provider registration."""
        return bool(self._providers)

    def require_ready(self):
        """Fail closed when deployment has no authenticated provider adapter."""
        if not self.is_ready:
            raise KnowledgeProviderError("KNOWLEDGE_PROVIDER_UNAVAILABLE")

    def is_registered(self, provider_name):
        """Return whether governance may bind a source to this explicit provider name."""
        return isinstance(provider_name, str) and provider_name in self._providers

    def register(self, provider_name, provider):
        """Register one provider explicitly; test fakes are never installed implicitly."""
        if not _bounded_string(provider_name, MAX_PROVIDER_NAME_BYTES) or not callable(
            getattr(provider, "search", None)
        ):
            raise ValueError("invalid knowledge provider registration")
        if provider_name in self._providers:
            raise ValueError("knowledge provider already registered")
        self._providers[provider_name] = provider

    def close(self, wait=True):
        """Close the registry-owned worker pool during the registry lifecycle shutdown."""
        with self._lifecycle_lock:
            if self._closed:
                return
            with self._slot_condition:
                self._closed = True
                self._slot_generation += 1
                self._slot_condition.notify_all()
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

    def _validate_query(self, binding, query):
        """Bind provider input to the eligible trusted source row and its lower budget."""
        if not isinstance(query, KnowledgeProviderQuery):
            raise KnowledgeProviderError("KNOWLEDGE_QUERY_INVALID")
        if (
            query.source_ref != getattr(binding, "source_ref", None)
            or query.snapshot_version != getattr(binding, "snapshot_version", None)
            or isinstance(getattr(binding, "max_top_k", None), bool)
            or not isinstance(getattr(binding, "max_top_k", None), int)
            or query.top_k > binding.max_top_k
        ):
            raise KnowledgeProviderError("KNOWLEDGE_QUERY_INVALID")

    def _acquire_slot(self, deadline, wait_for_slot):
        """Acquire a shared slot without barging ahead of requests already waiting for a turn."""
        with self._slot_condition:
            if self._closed:
                return False, self._slot_generation
            if not wait_for_slot:
                if self._slot_waiters:
                    return False, self._slot_generation
                return self._in_flight_slots.acquire(blocking=False), self._slot_generation

            waiter = object()
            self._slot_waiters.append(waiter)
            acquired = False
            try:
                while not self._closed:
                    if self._slot_waiters[0] is waiter and self._in_flight_slots.acquire(blocking=False):
                        self._slot_waiters.popleft()
                        acquired = True
                        self._slot_condition.notify_all()
                        return True, self._slot_generation
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False, self._slot_generation
                    self._slot_condition.wait(timeout=remaining)
                return False, self._slot_generation
            finally:
                if not acquired:
                    self._slot_waiters.remove(waiter)
                    self._slot_condition.notify_all()

    def _release_slot(self):
        """Release a slot only from a truly completed or cancelled shared future."""
        with self._slot_condition:
            self._in_flight_slots.release()
            self._slot_generation += 1
            self._slot_condition.notify_all()
            return self._slot_generation

    def _slot_generation_snapshot(self):
        """Read the wakeup generation under the same condition used by every slot transition."""
        with self._slot_condition:
            return self._slot_generation

    def _wait_for_progress(self, pending, deadline, observed_generation):
        """Wake on a local completion, any global slot release, close, or the absolute deadline."""
        with self._slot_condition:
            while True:
                completed = {future for future in pending if future.done()}
                if completed or self._closed or self._slot_generation != observed_generation:
                    return completed
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return set()
                self._slot_condition.wait(timeout=remaining)

    def _is_closed(self):
        """Read lifecycle state without taking locks in the reverse close/submit order."""
        with self._lifecycle_lock:
            return self._closed

    def _submit(self, provider, binding, query, deadline, wait_for_slot):
        """Submit only after fair acquisition of a shared bounded in-flight slot."""
        acquired, observed_generation = self._acquire_slot(deadline, wait_for_slot)
        if not acquired:
            return None, observed_generation
        with self._lifecycle_lock:
            if self._closed:
                return None, self._release_slot()
            try:
                future = self._executor.submit(provider.search, binding, query)
            except Exception:
                return None, self._release_slot()
        future.add_done_callback(lambda completed: self._release_slot())
        return future, observed_generation

    def _normalize_hit(self, provider_name, binding, query, hit):
        """Replace provider-controlled citations with content-addressed safe references."""
        if not isinstance(hit, ProviderKnowledgeHit):
            raise KnowledgeProviderError("RETRYABLE_INFRA")
        if not _bounded_string(hit.provider_hit_ref, MAX_PROVIDER_HIT_REF_BYTES):
            raise KnowledgeProviderError("RETRYABLE_INFRA")
        if not _bounded_string(hit.title, MAX_PROVIDER_TITLE_BYTES) or not isinstance(hit.excerpt, str):
            raise KnowledgeProviderError("RETRYABLE_INFRA")
        if (
            isinstance(hit.provider_score, bool)
            or not isinstance(hit.provider_score, (int, float))
            or not math.isfinite(hit.provider_score)
        ):
            raise KnowledgeProviderError("RETRYABLE_INFRA")

        excerpt = _truncate_utf8(hit.excerpt, MAX_EXCERPT_BYTES)
        snapshot_digest = _digest(
            [
                provider_name,
                binding.source_ref,
                query.snapshot_version,
                hit.provider_hit_ref,
                hit.title,
                excerpt,
            ]
        )
        source_snapshot = "sha256:{}".format(snapshot_digest)
        citation_digest = _digest([provider_name, binding.source_ref, source_snapshot, hit.provider_hit_ref])
        return replace(
            hit,
            excerpt=excerpt,
            citation_ref="citation://sha256/{}".format(citation_digest),
            source_snapshot=source_snapshot,
            provider_score=float(hit.provider_score),
        )

    def search_many(self, searches, deadline_seconds=None):
        """Search an ordered batch with shared workers and one total provider-phase deadline."""
        searches = tuple(searches)
        budget = self.timeout_seconds if deadline_seconds is None else deadline_seconds
        if (
            isinstance(budget, bool)
            or not isinstance(budget, (int, float))
            or budget <= 0
            or budget > self.timeout_seconds
        ):
            raise ValueError("deadline_seconds must be within the provider budget")

        started_at = time.monotonic()
        deadline = started_at + budget
        results = [None] * len(searches)
        pending = {}
        next_index = 0

        def failed_result(call_started_at=None):
            started = call_started_at if call_started_at is not None else started_at
            return KnowledgeProviderSearchResult((), False, max(0, int((time.monotonic() - started) * 1000)))

        while next_index < len(searches) or pending:
            stalled_generation = None
            while next_index < len(searches) and time.monotonic() < deadline:
                binding, query = searches[next_index]
                provider_name = getattr(binding, "provider", None)
                provider = self._providers.get(provider_name)
                try:
                    if provider is None:
                        raise KnowledgeProviderError("RETRYABLE_INFRA")
                    self._validate_query(binding, query)
                except Exception:
                    results[next_index] = failed_result()
                    next_index += 1
                    continue

                call_started_at = time.monotonic()
                future, observed_generation = self._submit(
                    provider,
                    binding,
                    query,
                    deadline,
                    wait_for_slot=not pending,
                )
                if future is None:
                    stalled_generation = observed_generation
                    break
                pending[future] = (next_index, provider_name, provider, binding, query, call_started_at)
                next_index += 1

            if not pending:
                break
            if stalled_generation is None:
                stalled_generation = self._slot_generation_snapshot()
            completed = self._wait_for_progress(pending, deadline, stalled_generation)
            if not completed:
                if time.monotonic() >= deadline or self._is_closed():
                    break
                continue
            for future in completed:
                index, provider_name, _provider, binding, query, call_started_at = pending.pop(future)
                try:
                    raw_hits = future.result()
                    if isinstance(raw_hits, (str, bytes)) or not isinstance(raw_hits, Sequence):
                        raise KnowledgeProviderError("RETRYABLE_INFRA")
                    normalized = tuple(
                        self._normalize_hit(provider_name, binding, query, hit) for hit in raw_hits[: query.top_k]
                    )
                    serialized = json.dumps(
                        [asdict(hit) for hit in normalized],
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                    if len(serialized) > MAX_PROVIDER_RESPONSE_BYTES:
                        raise KnowledgeProviderError("RETRYABLE_INFRA")
                    results[index] = KnowledgeProviderSearchResult(
                        normalized,
                        True,
                        max(0, int((time.monotonic() - call_started_at) * 1000)),
                    )
                except Exception:
                    results[index] = failed_result(call_started_at)

        for future, (index, _provider_name, _provider, _binding, _query, call_started_at) in pending.items():
            future.cancel()
            results[index] = failed_result(call_started_at)
        for index in range(next_index, len(searches)):
            results[index] = failed_result()
        return tuple(result if result is not None else failed_result() for result in results)

    def search(self, binding, query):
        """Search one explicit provider and return only normalized advisory hits."""
        if self._providers.get(getattr(binding, "provider", None)) is None:
            raise KnowledgeProviderError("RETRYABLE_INFRA")
        self._validate_query(binding, query)
        result = self.search_many(((binding, query),))[0]
        if not result.succeeded:
            raise KnowledgeProviderError("RETRYABLE_INFRA")
        return result.hits


class FakeKnowledgeProvider:
    """Deterministic test-only provider; callers must register it explicitly."""

    def __init__(self, hits: Sequence[ProviderKnowledgeHit]):
        self._hits = tuple(hits)

    def search(self, binding, query):
        """Return fixed test data without network, credentials, state changes, or LLM calls."""
        return self._hits[: query.top_k]
