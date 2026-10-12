"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from bkflow.harness.exceptions import IdempotencyConflict, IdempotencyRecordImmutable
from bkflow.harness.models import HarnessIdempotencyRecord, HarnessRun
from bkflow.harness.services.idempotency import (
    IdempotencyOutcome,
    IdempotencyScope,
    acquire_idempotency,
    complete_idempotency,
    execute_idempotent,
)


@pytest.fixture
def pre_run_scope():
    """Create a stable first-write namespace from trusted caller context."""
    return IdempotencyScope(
        platform_app="bkfara_app",
        actor="dannydeng",
        space_id=100,
        tool_name="validate_workflow",
        run_scope="pre-run",
        idempotency_key="retry-key-1",
    )


@pytest.fixture
def harness_run(db):
    """Create a run for post-validation idempotency namespaces."""
    return HarnessRun.objects.create(
        platform="bkfara",
        platform_app="bkfara_app",
        actor="dannydeng",
        space_id=100,
        scope="project:100",
        environment="stag",
        status="VALIDATING",
        policy_version="2026.09",
        mcp_contract_version="p0",
    )


@pytest.mark.django_db
def test_same_request_replays_completed_snapshot_without_a_second_side_effect(pre_run_scope):
    """Catch retries that repeat a completed domain write instead of replaying it."""
    side_effects = []

    def create_validation():
        side_effects.append("created")
        return {"ok": True, "artifact_refs": ["artifact://validation/1"]}

    first = execute_idempotent(pre_run_scope, "a" * 64, create_validation)
    second = execute_idempotent(pre_run_scope, "a" * 64, create_validation)

    assert first.replayed is False
    assert second.replayed is True
    assert second.response_snapshot == {"ok": True, "artifact_refs": ["artifact://validation/1"]}
    assert side_effects == ["created"]


@pytest.mark.django_db
def test_same_scope_and_key_with_a_different_request_hash_conflicts(pre_run_scope):
    """Catch a caller reusing a key for a semantically different write."""
    execute_idempotent(pre_run_scope, "a" * 64, lambda: {"ok": True})

    with pytest.raises(IdempotencyConflict):
        execute_idempotent(pre_run_scope, "b" * 64, lambda: {"ok": False})


@pytest.mark.django_db
def test_different_actor_or_space_owns_an_independent_idempotency_namespace(pre_run_scope):
    """Catch cross-actor or cross-space replay of a write response."""
    execute_idempotent(pre_run_scope, "a" * 64, lambda: {"owner": "dannydeng"})
    another_actor = IdempotencyScope(**{**pre_run_scope.as_dict(), "actor": "other_actor"})
    another_space = IdempotencyScope(**{**pre_run_scope.as_dict(), "space_id": 101})

    actor_result = execute_idempotent(another_actor, "a" * 64, lambda: {"owner": "other_actor"})
    space_result = execute_idempotent(another_space, "a" * 64, lambda: {"space": 101})

    assert actor_result.replayed is False
    assert space_result.replayed is False
    assert HarnessIdempotencyRecord.objects.count() == 3


@pytest.mark.django_db
def test_first_write_uses_literal_pre_run_and_completed_record_keeps_created_run(pre_run_scope, harness_run):
    """Catch first-write retries that cannot find the run created by validation."""
    result = execute_idempotent(
        pre_run_scope,
        "a" * 64,
        lambda: IdempotencyOutcome(response_snapshot={"run_id": str(harness_run.run_id)}, run=harness_run),
    )
    record = HarnessIdempotencyRecord.objects.get(pk=result.record.pk)
    post_run_scope = IdempotencyScope.for_run(
        platform_app="bkfara_app",
        actor="dannydeng",
        space_id=100,
        tool_name="create_workflow_draft",
        run=harness_run,
        idempotency_key="draft-key-1",
    )

    assert record.run_scope == "pre-run"
    assert record.run_id == harness_run.id
    assert post_run_scope.run_scope == "run:{}".format(harness_run.run_id)


@pytest.mark.django_db
def test_failed_in_flight_record_is_explicit_and_retries_with_the_same_hash(pre_run_scope):
    """Catch failure handling that loses retryability or overwrites completion."""
    with pytest.raises(RuntimeError, match="temporary failure"):
        execute_idempotent(pre_run_scope, "a" * 64, lambda: (_ for _ in ()).throw(RuntimeError("temporary failure")))

    failed_record = HarnessIdempotencyRecord.objects.get()
    assert failed_record.status == "FAILED"
    assert failed_record.response_snapshot == {}

    retried = execute_idempotent(pre_run_scope, "a" * 64, lambda: {"ok": True})
    completed_record = HarnessIdempotencyRecord.objects.get(pk=failed_record.pk)

    assert retried.replayed is False
    assert completed_record.status == "COMPLETED"
    assert completed_record.response_snapshot == {"ok": True}


@pytest.mark.django_db
def test_completed_record_is_immutable_after_its_response_is_stored(pre_run_scope):
    """Catch a second completion call that overwrites a completed response snapshot."""
    acquired = acquire_idempotency(pre_run_scope, "a" * 64)
    complete_idempotency(acquired.record, {"ok": True})

    with pytest.raises(IdempotencyRecordImmutable):
        complete_idempotency(acquired.record, {"ok": False})


@pytest.mark.django_db
def test_repeated_acquisition_has_one_owner_and_one_replay(pre_run_scope):
    """Catch duplicate side effects when the same write is acquired twice."""
    first = acquire_idempotency(pre_run_scope, "a" * 64)
    complete_idempotency(first.record, {"ok": True})
    second = acquire_idempotency(pre_run_scope, "a" * 64)

    assert first.owner is True
    assert second.owner is False
    assert second.replayed is True
    assert HarnessIdempotencyRecord.objects.count() == 1


@pytest.mark.skipif(
    not connection.features.has_select_for_update,
    reason="SQLite does not provide production row-lock semantics for this two-connection proof",
)
class TestIdempotencyRowLockConcurrency(TransactionTestCase):
    """Exercise idempotency races only where the database enforces row locks."""

    def _scope(self):
        """Build a stable namespace shared by the two independent connections."""
        return IdempotencyScope(
            platform_app="bkfara_app",
            actor="dannydeng",
            space_id=100,
            tool_name="validate_workflow",
            run_scope="pre-run",
            idempotency_key="concurrent-retry-key",
        )

    def _execute_in_connection(self, scope, request_hash, operation):
        """Run one write from a separate thread-local Django database connection."""
        close_old_connections()
        try:
            return execute_idempotent(scope, request_hash, operation)
        finally:
            close_old_connections()

    def test_two_connections_produce_one_owner_and_one_replay(self):
        """Catch a competing request executing its callback instead of replaying."""
        owner_started = threading.Event()
        release_owner = threading.Event()
        competitor_started = threading.Event()
        side_effects = []

        def owner_operation():
            side_effects.append("owner")
            owner_started.set()
            assert release_owner.wait(5)
            return {"owner": True}

        def competitor_operation():
            side_effects.append("competitor")
            return {"competitor": True}

        with ThreadPoolExecutor(max_workers=2) as executor:
            owner = executor.submit(self._execute_in_connection, self._scope(), "a" * 64, owner_operation)
            assert owner_started.wait(5)

            def competing_request():
                competitor_started.set()
                return self._execute_in_connection(self._scope(), "a" * 64, competitor_operation)

            replay = executor.submit(competing_request)
            assert competitor_started.wait(5)
            time.sleep(0.1)
            assert replay.done() is False
            release_owner.set()

            assert owner.result(timeout=5).replayed is False
            assert replay.result(timeout=5).replayed is True

        assert side_effects == ["owner"]
        assert HarnessIdempotencyRecord.objects.count() == 1

    def test_two_connections_retry_once_after_the_first_owner_fails(self):
        """Catch a failed in-flight record that cannot transfer ownership to one retry."""
        owner_started = threading.Event()
        release_owner = threading.Event()
        retry_started = threading.Event()
        side_effects = []

        def failing_operation():
            side_effects.append("failed-owner")
            owner_started.set()
            assert release_owner.wait(5)
            raise RuntimeError("temporary failure")

        def retry_operation():
            side_effects.append("retry-owner")
            return {"retried": True}

        with ThreadPoolExecutor(max_workers=2) as executor:
            failed_owner = executor.submit(self._execute_in_connection, self._scope(), "a" * 64, failing_operation)
            assert owner_started.wait(5)

            def retry_request():
                retry_started.set()
                return self._execute_in_connection(self._scope(), "a" * 64, retry_operation)

            retry = executor.submit(retry_request)
            assert retry_started.wait(5)
            time.sleep(0.1)
            assert retry.done() is False
            release_owner.set()

            with pytest.raises(RuntimeError, match="temporary failure"):
                failed_owner.result(timeout=5)
            assert retry.result(timeout=5).replayed is False

        record = HarnessIdempotencyRecord.objects.get()
        assert side_effects == ["failed-owner", "retry-owner"]
        assert record.status == "COMPLETED"
        assert record.response_snapshot == {"retried": True}
