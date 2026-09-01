"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils.translation import ugettext_lazy as _

from bkflow.harness.constants import IdempotencyStatus
from bkflow.harness.exceptions import IdempotencyConflict
from bkflow.harness.models import HarnessIdempotencyRecord, HarnessRun

PRE_RUN_SCOPE = "pre-run"
_IN_FLIGHT_WAIT_SECONDS = 5
_IN_FLIGHT_POLL_INTERVAL = 0.05


def run_scope_for(run_id: Optional[UUID]) -> str:
    """首次写操作为 pre-run，已有 run 后绑定到该 run。"""
    if run_id is None:
        return PRE_RUN_SCOPE
    return f"run:{run_id}"


@dataclass(frozen=True)
class IdempotencyAcquireResult:
    """幂等获取结果：要么成为唯一 owner，要么回放已完成响应。"""

    owned: bool
    replay: bool
    record: HarnessIdempotencyRecord
    response_snapshot: Optional[Dict[str, Any]] = None


def _lookup(**kwargs):
    return {
        "platform_app": kwargs["platform_app"],
        "actor": kwargs["actor"],
        "space_id": kwargs["space_id"],
        "tool_name": kwargs["tool_name"],
        "run_scope": kwargs["run_scope"],
        "idempotency_key": kwargs["idempotency_key"],
    }


def acquire_idempotency(
    *,
    platform_app: str,
    actor: str,
    space_id: int,
    tool_name: str,
    run_scope: str,
    idempotency_key: str,
    request_hash: str,
) -> IdempotencyAcquireResult:
    """
    获取幂等所有权或回放已完成响应。

    已完成记录的不同请求哈希会冲突；失败记录可按相同哈希重试。
    """
    lookup = _lookup(
        platform_app=platform_app,
        actor=actor,
        space_id=space_id,
        tool_name=tool_name,
        run_scope=run_scope,
        idempotency_key=idempotency_key,
    )
    try:
        with transaction.atomic():
            record = HarnessIdempotencyRecord.objects.create(
                **lookup,
                request_hash=request_hash,
                status=IdempotencyStatus.IN_FLIGHT.value,
            )
        return IdempotencyAcquireResult(owned=True, replay=False, record=record)
    except IntegrityError:
        return _acquire_existing(lookup, request_hash)


def _acquire_existing(lookup: Dict[str, Any], request_hash: str) -> IdempotencyAcquireResult:
    deadline = time.monotonic() + _IN_FLIGHT_WAIT_SECONDS
    while True:
        record = HarnessIdempotencyRecord.objects.filter(**lookup).first()
        if record is None:
            if time.monotonic() > deadline:
                raise IdempotencyConflict(_("幂等记录在并发创建后丢失"))
            time.sleep(_IN_FLIGHT_POLL_INTERVAL)
            continue
        if record.status == IdempotencyStatus.COMPLETED.value:
            if record.request_hash != request_hash:
                raise IdempotencyConflict(_("相同幂等键对应了不同的请求"))
            return IdempotencyAcquireResult(
                owned=False,
                replay=True,
                record=record,
                response_snapshot=record.response_snapshot,
            )
        if record.status == IdempotencyStatus.FAILED.value:
            return _reclaim_failed(record, request_hash)
        if record.status == IdempotencyStatus.IN_FLIGHT.value:
            if time.monotonic() > deadline:
                raise IdempotencyConflict(_("幂等记录仍在处理中"))
            time.sleep(_IN_FLIGHT_POLL_INTERVAL)
            continue
        raise IdempotencyConflict(_("未知的幂等状态"))


def _reclaim_failed(record: HarnessIdempotencyRecord, request_hash: str) -> IdempotencyAcquireResult:
    with transaction.atomic():
        locked = HarnessIdempotencyRecord.objects.select_for_update().get(pk=record.pk)
        if locked.request_hash != request_hash:
            raise IdempotencyConflict(_("相同幂等键对应了不同的请求"))
        if locked.status == IdempotencyStatus.COMPLETED.value:
            return IdempotencyAcquireResult(
                owned=False,
                replay=True,
                record=locked,
                response_snapshot=locked.response_snapshot,
            )
        if locked.status != IdempotencyStatus.FAILED.value:
            raise IdempotencyConflict(_("幂等记录仍在处理中"))
        locked.status = IdempotencyStatus.IN_FLIGHT.value
        locked.response_snapshot = {}
        locked.save(update_fields=["status", "response_snapshot", "update_at"])
        return IdempotencyAcquireResult(owned=True, replay=False, record=locked)


def complete_idempotency(
    record: HarnessIdempotencyRecord,
    response_snapshot: Dict[str, Any],
    resource_ref: Optional[Dict[str, Any]] = None,
    run: Optional[HarnessRun] = None,
) -> HarnessIdempotencyRecord:
    """领域操作成功后写入响应快照。"""
    with transaction.atomic():
        locked = HarnessIdempotencyRecord.objects.select_for_update().get(pk=record.pk)
        if locked.status == IdempotencyStatus.COMPLETED.value:
            if locked.request_hash != record.request_hash:
                raise IdempotencyConflict(_("不能覆盖已完成的幂等记录"))
            return locked
        locked.status = IdempotencyStatus.COMPLETED.value
        locked.response_snapshot = response_snapshot
        update_fields = ["status", "response_snapshot", "update_at"]
        if resource_ref is not None:
            locked.resource_ref = resource_ref
            update_fields.append("resource_ref")
        if run is not None:
            locked.run = run
            update_fields.append("run")
        locked.save(update_fields=update_fields)
        record.status = locked.status
        record.response_snapshot = locked.response_snapshot
        record.resource_ref = locked.resource_ref
        record.run = locked.run
        return locked


def fail_idempotency(record: HarnessIdempotencyRecord) -> HarnessIdempotencyRecord:
    """将进行中记录标记为失败，供相同请求重试。"""
    with transaction.atomic():
        locked = HarnessIdempotencyRecord.objects.select_for_update().get(pk=record.pk)
        if locked.status == IdempotencyStatus.COMPLETED.value:
            raise IdempotencyConflict(_("不能覆盖已完成的幂等记录"))
        locked.status = IdempotencyStatus.FAILED.value
        locked.save(update_fields=["status", "update_at"])
        record.status = locked.status
        return locked
