"""Provider SPI, safe registry, and bounded result contracts."""

import threading
import time
from collections.abc import Sequence
from dataclasses import fields
from types import SimpleNamespace

import pytest

from bkflow.harness.services.knowledge.contracts import (
    DEFAULT_BINDING_TOP_K,
    MAX_EXCERPT_BYTES,
    MAX_PROVIDER_RESPONSE_BYTES,
    MAX_TOP_K,
    PROVIDER_CONTENT_TRUST,
    PROVIDER_IDENTITY_MODE,
    PROVIDER_MODE,
    PROVIDER_SNAPSHOT_MODE,
    PROVIDER_TIMEOUT_SECONDS,
    KnowledgeProviderQuery,
    ProviderKnowledgeHit,
)
from bkflow.harness.services.knowledge.providers import (
    FakeKnowledgeProvider,
    KnowledgeProviderError,
    KnowledgeProviderRegistry,
)


def binding(**overrides):
    """Build a provider-facing binding without involving database behavior."""
    values = {
        "provider": "fixture-docs",
        "source_ref": "knowledge://workflow-guides/restart-service",
        "snapshot_version": "sha256:binding-snapshot",
        "max_top_k": DEFAULT_BINDING_TOP_K,
        "credential_ref": "credential://knowledge/reader",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def provider_query(**overrides):
    """Build a complete provider query from literal trusted values."""
    values = {
        "query": "restart a service safely",
        "top_k": DEFAULT_BINDING_TOP_K,
        "source_ref": "knowledge://workflow-guides/restart-service",
        "snapshot_version": "sha256:binding-snapshot",
        "correlation_id": "correlation-provider-contract",
    }
    values.update(overrides)
    return KnowledgeProviderQuery(**values)


def provider_hit(**overrides):
    """Build one complete untrusted provider response."""
    values = {
        "provider_hit_ref": "provider-hit://restart/1",
        "title": "Restart a service",
        "excerpt": "Drain traffic, restart one instance, and verify health.",
        "citation_ref": "provider-controlled-citation",
        "source_snapshot": "provider-controlled-snapshot",
        "provider_score": 0.9,
    }
    values.update(overrides)
    return ProviderKnowledgeHit(**values)


def test_provider_contract_is_spi_only_platform_identity_and_advisory():
    """Changing the frozen authority boundary must not turn providers into an LLM or fact source."""
    assert PROVIDER_MODE == "provider_spi_only"
    assert PROVIDER_IDENTITY_MODE == "platform_service_identity"
    assert PROVIDER_SNAPSHOT_MODE == "content_digest_snapshot"
    assert PROVIDER_CONTENT_TRUST == "ADVISORY"
    assert PROVIDER_TIMEOUT_SECONDS == 3
    assert MAX_TOP_K == 20
    assert DEFAULT_BINDING_TOP_K == 5
    assert MAX_EXCERPT_BYTES == 4096
    assert MAX_PROVIDER_RESPONSE_BYTES == 65536


def test_query_and_hit_dataclasses_cannot_carry_credentials_or_secrets():
    """Adding credential-shaped DTO fields would let resolved secrets escape an adapter call."""
    forbidden = {"credential", "credential_ref", "credentials", "secret", "token", "password"}

    assert forbidden.isdisjoint(field.name for field in fields(KnowledgeProviderQuery))
    assert forbidden.isdisjoint(field.name for field in fields(ProviderKnowledgeHit))


@pytest.mark.parametrize("top_k", [0, True, 21])
def test_query_rejects_top_k_outside_the_frozen_budget(top_k):
    """Weakening query validation would let a caller exceed the provider retrieval budget."""
    with pytest.raises(ValueError, match="top_k"):
        provider_query(top_k=top_k)


@pytest.mark.parametrize(
    "overrides",
    [
        {"query": "Bearer resolved-query-secret"},
        {"query": "token=resolved-query-secret"},
        {"query": "invalid-\ud800-query"},
        {"query": "x" * 2001},
        {"source_ref": "knowledge://user:password@workflow-guides/restart"},
        {"snapshot_version": "api_token=resolved-snapshot-secret"},
        {"correlation_id": "Bearer resolved-correlation-secret"},
    ],
)
def test_provider_query_fails_closed_on_secret_malformed_or_oversized_strings(overrides):
    """A malformed or secret-shaped DTO would cross the last boundary before external provider execution."""
    with pytest.raises(ValueError, match="provider query"):
        provider_query(**overrides)


def test_empty_registry_and_unknown_provider_fail_closed_without_auto_registering_fake():
    """Automatically registering a test fake or accepting an unknown provider would open production retrieval."""
    registry = KnowledgeProviderRegistry()

    assert registry.is_ready is False
    with pytest.raises(KnowledgeProviderError, match="KNOWLEDGE_PROVIDER_UNAVAILABLE"):
        registry.require_ready()
    with pytest.raises(KnowledgeProviderError) as error:
        registry.search(binding(provider="secret-provider-name"), provider_query())

    assert error.value.code == "RETRYABLE_INFRA"
    assert str(error.value) == "RETRYABLE_INFRA"
    assert "secret-provider-name" not in repr(error.value)


def test_explicit_fake_registration_returns_deterministic_bounded_hits():
    """Removing explicit registration or result bounds would make the test provider leak into production behavior."""
    fake = FakeKnowledgeProvider([provider_hit()])
    registry = KnowledgeProviderRegistry({"fixture-docs": fake})

    first = registry.search(binding(), provider_query(top_k=1))
    second = registry.search(binding(), provider_query(top_k=1))

    assert first == second
    assert len(first) == 1
    assert first[0].provider_hit_ref == "provider-hit://restart/1"
    assert first[0].title == "Restart a service"
    assert first[0].excerpt == "Drain traffic, restart one instance, and verify health."
    assert first[0].provider_score == 0.9
    assert first[0].citation_ref.startswith("citation://sha256/")
    assert first[0].source_snapshot.startswith("sha256:")
    assert first[0].citation_ref != "provider-controlled-citation"
    assert first[0].source_snapshot != "provider-controlled-snapshot"
    assert len(first[0].citation_ref.encode("utf-8")) <= 128
    assert len(first[0].source_snapshot.encode("utf-8")) <= 128


def test_content_change_changes_digest_snapshot_and_citation():
    """Reusing references across changed content would make citations point at an unstable source snapshot."""
    original_registry = KnowledgeProviderRegistry({"fixture-docs": FakeKnowledgeProvider([provider_hit()])})
    changed_registry = KnowledgeProviderRegistry(
        {"fixture-docs": FakeKnowledgeProvider([provider_hit(excerpt="A changed verified procedure.")])}
    )

    original = original_registry.search(binding(), provider_query())[0]
    changed = changed_registry.search(binding(), provider_query())[0]

    assert original.source_snapshot != changed.source_snapshot
    assert original.citation_ref != changed.citation_ref


def test_registry_truncates_excerpt_without_splitting_utf8_and_respects_top_k():
    """Byte-based truncation must not emit invalid UTF-8 or more hits than requested."""
    long_excerpt = "流" * 2000
    hits = [
        provider_hit(provider_hit_ref="provider-hit://restart/{}".format(index), excerpt=long_excerpt)
        for index in range(3)
    ]
    registry = KnowledgeProviderRegistry({"fixture-docs": FakeKnowledgeProvider(hits)})

    result = registry.search(binding(max_top_k=2), provider_query(top_k=2))

    assert len(result) == 2
    assert all(len(hit.excerpt.encode("utf-8")) <= MAX_EXCERPT_BYTES for hit in result)
    assert all(hit.excerpt.encode("utf-8").decode("utf-8") == hit.excerpt for hit in result)


def test_registry_rejects_query_above_binding_budget():
    """Ignoring a binding's lower budget would bypass source-specific retrieval governance."""
    registry = KnowledgeProviderRegistry({"fixture-docs": FakeKnowledgeProvider([provider_hit()])})

    with pytest.raises(KnowledgeProviderError, match="KNOWLEDGE_QUERY_INVALID"):
        registry.search(binding(max_top_k=4), provider_query(top_k=5))


def test_timeout_is_normalized_without_provider_detail_or_secret_echo():
    """Propagating provider exceptions would expose infrastructure and credential material."""

    class TimeoutProvider:
        """Raise the same timeout shape an external adapter could raise."""

        def search(self, binding, query):
            raise TimeoutError("Authorization: Bearer resolved-provider-secret")

    registry = KnowledgeProviderRegistry({"fixture-docs": TimeoutProvider()})

    with pytest.raises(KnowledgeProviderError) as error:
        registry.search(binding(), provider_query())

    assert error.value.code == "RETRYABLE_INFRA"
    assert str(error.value) == "RETRYABLE_INFRA"
    assert "resolved-provider-secret" not in repr(error.value)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_consecutive_timeouts_keep_shared_threads_and_wait_for_their_own_slot_deadline():
    """A saturated request must wait for its own deadline without growing threads or releasing running slots."""
    release = threading.Event()
    started_lock = threading.Lock()
    started_threads = set()

    class BlockingProvider:
        """Block real worker calls until the assertion releases them."""

        def search(self, binding, query):
            with started_lock:
                started_threads.add(threading.get_ident())
            release.wait(timeout=1)
            return []

    registry = KnowledgeProviderRegistry(
        {"fixture-docs": BlockingProvider()}, timeout_seconds=0.03, max_workers=2, max_in_flight=2
    )
    try:
        started_at = time.monotonic()
        for _ in range(2):
            with pytest.raises(KnowledgeProviderError, match="RETRYABLE_INFRA"):
                registry.search(binding(), provider_query())

        saturated_at = time.monotonic()
        with pytest.raises(KnowledgeProviderError, match="RETRYABLE_INFRA"):
            registry.search(binding(), provider_query())
        saturated_elapsed = time.monotonic() - saturated_at

        timeout_elapsed = saturated_at - started_at
        assert 0.04 <= timeout_elapsed < 0.5
        assert 0.02 <= saturated_elapsed < 0.2
        assert len(started_threads) == 2
    finally:
        release.set()
        registry.close()


def test_concurrent_large_batch_yields_the_next_slot_to_an_already_waiting_request():
    """A first batch must not barge ahead of a second request when the sole shared slot rotates."""
    first_started = threading.Event()
    release_first = threading.Event()
    second_done = threading.Event()
    calls = []
    result_box = {}

    def search_pair(name):
        source_ref = "knowledge://workflow-guides/{}".format(name)
        snapshot_version = "sha256:{}-snapshot".format(name)
        return (
            binding(source_ref=source_ref, snapshot_version=snapshot_version),
            provider_query(source_ref=source_ref, snapshot_version=snapshot_version),
        )

    first, first_query = search_pair("batch-first")
    second, second_query = search_pair("batch-second")
    urgent, urgent_query = search_pair("waiting-request")

    class OrderedBlockingProvider:
        """Block only the first batch call so the next shared-slot owner is observable."""

        def search(self, provider_binding, query):
            name = provider_binding.source_ref.rsplit("/", 1)[-1]
            calls.append(name)
            if name == "batch-first":
                first_started.set()
                release_first.wait(timeout=1)
            return [provider_hit(provider_hit_ref="provider-hit://{}/1".format(name))]

    registry = KnowledgeProviderRegistry(
        {"fixture-docs": OrderedBlockingProvider()},
        timeout_seconds=0.3,
        max_workers=1,
        max_in_flight=1,
    )

    def run_batch():
        result_box["batch"] = registry.search_many(((first, first_query), (second, second_query)))

    def run_waiting_request():
        started_at = time.monotonic()
        try:
            result_box["waiting"] = registry.search(urgent, urgent_query)
        except Exception as error:
            result_box["waiting_error"] = error
        finally:
            result_box["waiting_elapsed"] = time.monotonic() - started_at
            second_done.set()

    batch_thread = threading.Thread(target=run_batch)
    waiting_thread = threading.Thread(target=run_waiting_request)
    try:
        batch_thread.start()
        assert first_started.wait(timeout=0.2)
        waiting_thread.start()

        assert second_done.wait(timeout=0.03) is False
        assert calls == ["batch-first"]
        release_first.set()
        waiting_thread.join(timeout=0.5)
        batch_thread.join(timeout=0.5)

        assert waiting_thread.is_alive() is False
        assert batch_thread.is_alive() is False
        assert "waiting_error" not in result_box
        assert 0.03 <= result_box["waiting_elapsed"] < 0.3
        assert calls == ["batch-first", "waiting-request", "batch-second"]
        assert [item.succeeded for item in result_box["batch"]] == [True, True]
        assert [item.hits[0].provider_hit_ref for item in result_box["batch"]] == [
            "provider-hit://batch-first/1",
            "provider-hit://batch-second/1",
        ]
        assert result_box["waiting"][0].provider_hit_ref == "provider-hit://waiting-request/1"
    finally:
        release_first.set()
        waiting_thread.join(timeout=1)
        batch_thread.join(timeout=1)
        registry.close()


def test_batch_resumes_after_the_fair_request_releases_its_slot_while_an_original_call_is_still_running():
    """After yielding to B, batch A must observe B's release and submit A2 without waiting for blocked A1."""
    release_a0 = threading.Event()
    release_a1 = threading.Event()
    a0_started = threading.Event()
    a1_started = threading.Event()
    b_done = threading.Event()
    a2_started = threading.Event()
    calls = []
    calls_lock = threading.Lock()
    result_box = {}

    def search_pair(name):
        source_ref = "knowledge://workflow-guides/{}".format(name)
        snapshot_version = "sha256:{}-snapshot".format(name)
        return (
            binding(source_ref=source_ref, snapshot_version=snapshot_version),
            provider_query(source_ref=source_ref, snapshot_version=snapshot_version),
        )

    a0, a0_query = search_pair("a0")
    a1, a1_query = search_pair("a1")
    a2, a2_query = search_pair("a2")
    b, b_query = search_pair("b")

    class ReturningProvider:
        """Expose A/B completion order while returning one distinct normalized hit per source."""

        def search(self, provider_binding, query):
            name = provider_binding.source_ref.rsplit("/", 1)[-1]
            with calls_lock:
                calls.append(name)
            if name == "a0":
                a0_started.set()
                release_a0.wait(timeout=1)
            elif name == "a1":
                a1_started.set()
                release_a1.wait(timeout=1)
            elif name == "a2":
                a2_started.set()
            return [provider_hit(provider_hit_ref="provider-hit://{}/1".format(name))]

    registry = KnowledgeProviderRegistry(
        {"fixture-docs": ReturningProvider()},
        timeout_seconds=0.25,
        max_workers=2,
        max_in_flight=2,
    )

    def run_a_batch():
        result_box["a"] = registry.search_many(((a0, a0_query), (a1, a1_query), (a2, a2_query)))

    def run_b_request():
        try:
            result_box["b"] = registry.search(b, b_query)
        finally:
            b_done.set()

    a_thread = threading.Thread(target=run_a_batch)
    b_thread = threading.Thread(target=run_b_request)
    try:
        a_thread.start()
        assert a0_started.wait(timeout=0.2)
        assert a1_started.wait(timeout=0.2)
        b_thread.start()
        with registry._slot_condition:
            waiter_deadline = time.monotonic() + 0.1
            while not registry._slot_waiters and time.monotonic() < waiter_deadline:
                registry._slot_condition.wait(timeout=waiter_deadline - time.monotonic())
            assert len(registry._slot_waiters) == 1

        release_a0.set()
        assert b_done.wait(timeout=0.1)
        assert result_box["b"][0].provider_hit_ref == "provider-hit://b/1"
        assert a1_started.is_set() and not release_a1.is_set()

        assert a2_started.wait(timeout=0.1)
        release_a1.set()
        a_thread.join(timeout=0.3)

        assert a_thread.is_alive() is False
        assert [item.succeeded for item in result_box["a"]] == [True, True, True]
        assert [item.hits[0].provider_hit_ref for item in result_box["a"]] == [
            "provider-hit://a0/1",
            "provider-hit://a1/1",
            "provider-hit://a2/1",
        ]
        assert set(calls[:2]) == {"a0", "a1"}
        assert calls[2:] == ["b", "a2"]
    finally:
        release_a0.set()
        release_a1.set()
        a_thread.join(timeout=1)
        b_thread.join(timeout=1)
        registry.close()


def test_close_wakes_a_waiting_request_without_submitting_it_after_shutdown():
    """A close racing with a fair slot wait must fail safely instead of deadlocking or dispatching afterward."""
    first_started = threading.Event()
    first_done = threading.Event()
    release_first = threading.Event()
    waiting_done = threading.Event()
    calls = []
    result_box = {}

    class CloseRaceProvider:
        """Keep the only running slot occupied across registry shutdown."""

        def search(self, provider_binding, query):
            calls.append(provider_binding.source_ref)
            first_started.set()
            release_first.wait(timeout=1)
            return []

    registry = KnowledgeProviderRegistry(
        {"fixture-docs": CloseRaceProvider()},
        timeout_seconds=0.3,
        max_workers=1,
        max_in_flight=1,
    )

    def run_first():
        try:
            result_box["first"] = registry.search(binding(), provider_query())
        except Exception as error:
            result_box["first_error"] = error
        finally:
            first_done.set()

    waiting_binding = binding(source_ref="knowledge://workflow-guides/waiting-close")
    waiting_query = provider_query(source_ref=waiting_binding.source_ref)

    def run_waiting():
        try:
            registry.search(waiting_binding, waiting_query)
        except Exception as error:
            result_box["waiting_error"] = error
        finally:
            waiting_done.set()

    first_thread = threading.Thread(target=run_first)
    waiting_thread = threading.Thread(target=run_waiting)
    try:
        first_thread.start()
        assert first_started.wait(timeout=0.2)
        waiting_thread.start()
        assert waiting_done.wait(timeout=0.03) is False

        registry.close(wait=False)

        assert waiting_done.wait(timeout=0.2)
        assert first_done.wait(timeout=0.2)
        assert isinstance(result_box["waiting_error"], KnowledgeProviderError)
        assert result_box["waiting_error"].code == "RETRYABLE_INFRA"
        assert isinstance(result_box["first_error"], KnowledgeProviderError)
        assert result_box["first_error"].code == "RETRYABLE_INFRA"
        assert calls == ["knowledge://workflow-guides/restart-service"]
    finally:
        release_first.set()
        first_thread.join(timeout=1)
        waiting_thread.join(timeout=1)
        registry.close()


def test_shared_executor_threads_and_queue_have_a_hard_in_flight_upper_bound():
    """A large batch may occupy only max_in_flight running-plus-queued futures on the shared executor."""
    release = threading.Event()
    two_started = threading.Event()
    state_lock = threading.Lock()
    thread_ids = set()
    calls = []

    class QueueBoundProvider:
        """Hold both workers so the executor queue depth can be measured deterministically."""

        def search(self, provider_binding, query):
            with state_lock:
                thread_ids.add(threading.get_ident())
                calls.append(provider_binding.source_ref)
                if len(calls) == 2:
                    two_started.set()
            release.wait(timeout=1)
            return []

    searches = []
    for index in range(8):
        source_ref = "knowledge://workflow-guides/queue-{}".format(index)
        searches.append(
            (
                binding(source_ref=source_ref),
                provider_query(source_ref=source_ref),
            )
        )
    registry = KnowledgeProviderRegistry(
        {"fixture-docs": QueueBoundProvider()},
        timeout_seconds=0.2,
        max_workers=2,
        max_in_flight=3,
    )
    result_box = {}
    batch_thread = threading.Thread(target=lambda: result_box.setdefault("result", registry.search_many(searches)))
    try:
        batch_thread.start()
        assert two_started.wait(timeout=0.2)
        queue_deadline = time.monotonic() + 0.2
        while registry._executor._work_queue.qsize() < 1 and time.monotonic() < queue_deadline:
            time.sleep(0.001)

        assert len(thread_ids) == 2
        assert registry._executor._work_queue.qsize() == 1
        assert len(calls) == 2
    finally:
        release.set()
        batch_thread.join(timeout=1)
        registry.close()

    assert batch_thread.is_alive() is False
    assert len(result_box["result"]) == len(searches)


@pytest.mark.parametrize("failure_point", ["getitem", "iter"])
def test_malicious_sequence_processing_is_normalized_without_secret_exception(failure_point):
    """Provider-controlled slicing or iteration failures must stay inside the safe normalization boundary."""

    class HostileSequence(Sequence):
        """Raise secret-bearing errors from either slicing or later iteration."""

        def __len__(self):
            return 1

        def __getitem__(self, index):
            if failure_point == "getitem":
                raise RuntimeError("password=resolved-sequence-secret")
            if isinstance(index, slice):
                return self
            raise IndexError

        def __iter__(self):
            if failure_point == "iter":
                raise RuntimeError("password=resolved-sequence-secret")
            return super().__iter__()

    class HostileProvider:
        """Return the complete hostile response through the real provider SPI."""

        def search(self, binding, query):
            return HostileSequence()

    registry = KnowledgeProviderRegistry({"fixture-docs": HostileProvider()})
    try:
        with pytest.raises(KnowledgeProviderError) as error:
            registry.search(binding(), provider_query())
    finally:
        registry.close()

    assert error.value.code == "RETRYABLE_INFRA"
    assert str(error.value) == "RETRYABLE_INFRA"
    assert "resolved-sequence-secret" not in repr(error.value)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_normalized_provider_hits_larger_than_total_budget_fail_closed():
    """Task 4 bounds normalized hits; the later Task 7 Envelope boundary must apply its own final budget."""
    hits = [
        provider_hit(
            provider_hit_ref="provider-hit://oversized/{}".format(index),
            title="title-{}".format(index),
            excerpt="x" * MAX_EXCERPT_BYTES,
        )
        for index in range(20)
    ]
    registry = KnowledgeProviderRegistry({"fixture-docs": FakeKnowledgeProvider(hits)})

    with pytest.raises(KnowledgeProviderError, match="RETRYABLE_INFRA"):
        registry.search(binding(max_top_k=20), provider_query(top_k=20))
