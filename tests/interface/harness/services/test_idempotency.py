"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connections

from bkflow.harness.constants import IdempotencyStatus
from bkflow.harness.exceptions import IdempotencyConflict
from bkflow.harness.models import HarnessIdempotencyRecord
from bkflow.harness.services.idempotency import (
    PRE_RUN_SCOPE,
    acquire_idempotency,
    complete_idempotency,
    fail_idempotency,
    run_scope_for,
)


def _scope(space_id, actor="alice"):
    return {
        "platform_app": "bkflow_harness",
        "actor": actor,
        "space_id": space_id,
        "tool_name": "validate_workflow",
        "run_scope": PRE_RUN_SCOPE,
        "idempotency_key": "key-1",
        "request_hash": "a" * 64,
    }


def test_run_scope_is_pre_run_then_run_id(harness_run):
    """首次写操作用 pre-run，已有 run 后用 run:<id>。"""
    assert run_scope_for(None) == "pre-run"
    assert run_scope_for(harness_run.id) == f"run:{harness_run.id}"


def test_same_key_and_hash_replays_stored_response(space):
    """相同 key 且相同请求哈希返回已存储响应。"""
    first = acquire_idempotency(**_scope(space.id))
    assert first.owned is True
    complete_idempotency(first.record, {"ok": True, "run_id": "r1"}, resource_ref={"run_id": "r1"})

    replay = acquire_idempotency(**_scope(space.id))
    assert replay.replay is True
    assert replay.owned is False
    assert replay.response_snapshot == {"ok": True, "run_id": "r1"}


def test_same_key_different_hash_raises_conflict(space):
    """相同 key 但请求哈希不同时冲突。"""
    first = acquire_idempotency(**_scope(space.id))
    complete_idempotency(first.record, {"ok": True})
    with pytest.raises(IdempotencyConflict):
        acquire_idempotency(**{**_scope(space.id), "request_hash": "b" * 64})


def test_same_key_is_independent_across_space_and_actor(space):
    """不同空间或不同 actor 的相同 key 互不影响。"""
    other_space = space.__class__.objects.create(
        name="harness-p0-space-2",
        app_code="bkflow_harness",
        platform_url="http://example.com",
    )
    first = acquire_idempotency(**_scope(space.id))
    complete_idempotency(first.record, {"space": 1})
    other_space_acquire = acquire_idempotency(**_scope(other_space.id))
    other_actor = acquire_idempotency(**_scope(space.id, actor="bob"))

    assert other_space_acquire.owned is True
    assert other_actor.owned is True


def test_failed_in_flight_can_be_retried_without_overwriting_completed(space):
    """失败的进行中记录可显式重试；已完成记录不能被静默覆盖。"""
    first = acquire_idempotency(**_scope(space.id))
    fail_idempotency(first.record)
    first.record.refresh_from_db()
    assert first.record.status == IdempotencyStatus.FAILED.value

    retry = acquire_idempotency(**_scope(space.id))
    assert retry.owned is True
    complete_idempotency(retry.record, {"ok": True})

    completed = HarnessIdempotencyRecord.objects.get(
        platform_app="bkflow_harness",
        actor="alice",
        space_id=space.id,
        tool_name="validate_workflow",
        run_scope=PRE_RUN_SCOPE,
        idempotency_key="key-1",
    )
    assert completed.status == IdempotencyStatus.COMPLETED.value
    with pytest.raises(IdempotencyConflict):
        acquire_idempotency(**{**_scope(space.id), "request_hash": "c" * 64})


@pytest.mark.django_db(transaction=True)
def test_concurrent_acquisition_one_owner_one_replay(space):
    """并发获取只产生一个 owner 和一个 replay。"""
    payload = _scope(space.id)

    def worker():
        outcome = acquire_idempotency(**payload)
        if outcome.owned:
            complete_idempotency(outcome.record, {"ok": True, "owner": True})
        connections.close_all()
        return outcome

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(lambda _: worker(), range(2))

    outcomes = [first, second]
    assert sum(1 for item in outcomes if item.owned) == 1
    assert sum(1 for item in outcomes if item.replay) == 1
    replay = next(item for item in outcomes if item.replay)
    assert replay.response_snapshot == {"ok": True, "owner": True}
