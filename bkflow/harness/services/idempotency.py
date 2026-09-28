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
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.models import HarnessIdempotencyRecord


@dataclass(frozen=True)
class IdempotencyScope:
    """Trusted dimensions of the unique Harness write namespace."""

    platform_app: str
    actor: str
    space_id: int
    tool_name: str
    run_scope: str
    idempotency_key: str

    @classmethod
    def for_run(cls, platform_app, actor, space_id, tool_name, run, idempotency_key):
        """Build the exact post-creation namespace for one Harness run."""
        return cls(
            platform_app=platform_app,
            actor=actor,
            space_id=space_id,
            tool_name=tool_name,
            run_scope="run:{}".format(run.run_id),
            idempotency_key=idempotency_key,
        )

    def as_dict(self):
        """Return the namespace fields accepted by the persistence model."""
        return {
            "platform_app": self.platform_app,
            "actor": self.actor,
            "space_id": self.space_id,
            "tool_name": self.tool_name,
            "run_scope": self.run_scope,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class IdempotencyOutcome:
    """Successful domain-write values to persist before a retry can replay."""

    response_snapshot: dict
    run: object = None
    resource_reference: str = None


@dataclass(frozen=True)
class IdempotencyAcquisition:
    """A row-lock protected idempotency acquisition result."""

    record: HarnessIdempotencyRecord
    owner: bool
    replayed: bool
    response_snapshot: dict = None


@dataclass(frozen=True)
class IdempotencyResult:
    """The response returned from a new or replayed idempotent write."""

    record: HarnessIdempotencyRecord
    replayed: bool
    response_snapshot: dict


def _record_query(scope):
    """Return the exact unique lookup for an idempotency namespace."""
    return HarnessIdempotencyRecord.objects.select_for_update().filter(**scope.as_dict())


def _check_request_hash(record, request_hash):
    """Reject a namespace collision before a stale response can be replayed."""
    if record.request_hash != request_hash:
        raise IdempotencyConflict("idempotency key was already used for a different request")


def acquire_idempotency(scope, request_hash):
    """Acquire a new or failed write record, or replay a completed response.

    The caller must invoke this inside an outer ``transaction.atomic`` block
    when it will perform a domain write, so the lock spans write and snapshot.
    """
    with transaction.atomic():
        record = _record_query(scope).first()
        created = False
        if record is None:
            try:
                with transaction.atomic():
                    record = HarnessIdempotencyRecord.objects.create(
                        **scope.as_dict(), request_hash=request_hash, status="IN_FLIGHT"
                    )
                    created = True
            except IntegrityError:
                record = _record_query(scope).get()

        _check_request_hash(record, request_hash)
        if created:
            return IdempotencyAcquisition(record, owner=True, replayed=False)
        if record.status == "COMPLETED":
            return IdempotencyAcquisition(
                record, owner=False, replayed=True, response_snapshot=record.response_snapshot
            )
        if record.status == "FAILED":
            record.status = "IN_FLIGHT"
            record.save(update_fields=["status", "update_at"])
            return IdempotencyAcquisition(record, owner=True, replayed=False)
        if record.status == "IN_FLIGHT":
            if record.response_snapshot:
                raise IdempotencyRecordImmutable("an in-flight record must not have a response snapshot")
            raise IdempotencyInFlight("the same idempotency key is currently being processed")
        raise IdempotencyRecordImmutable("unknown idempotency record status: {}".format(record.status))


def complete_idempotency(record, response_snapshot, run=None, resource_reference=None):
    """Store a response only after its domain write has succeeded."""
    with transaction.atomic():
        locked_record = HarnessIdempotencyRecord.objects.select_for_update().get(pk=record.pk)
        if locked_record.status != "IN_FLIGHT":
            raise IdempotencyRecordImmutable("only an in-flight record can be completed")
        locked_record.status = "COMPLETED"
        locked_record.response_snapshot = response_snapshot
        if run is not None:
            locked_record.run = run
        if resource_reference is not None:
            locked_record.resource_reference = resource_reference
        locked_record.save(update_fields=["status", "response_snapshot", "run", "resource_reference", "update_at"])
        return locked_record


def bind_inflight_idempotency(record, *, run, resource_reference):
    """Commit a durable resource claim before its non-transactional side effect."""
    with transaction.atomic():
        locked_record = HarnessIdempotencyRecord.objects.select_for_update().get(pk=record.pk)
        if locked_record.status != "IN_FLIGHT" or locked_record.response_snapshot:
            raise IdempotencyRecordImmutable("only an empty in-flight record can become a dispatch barrier")
        if locked_record.run_id not in {None, run.pk}:
            raise IdempotencyRecordImmutable("an in-flight record cannot change its run")
        if locked_record.resource_reference not in {None, "", resource_reference}:
            raise IdempotencyRecordImmutable("an in-flight record cannot change its resource")
        locked_record.run = run
        locked_record.resource_reference = resource_reference
        locked_record.save(update_fields=["run", "resource_reference", "update_at"])
        return locked_record


def acquire_debug_session_barrier(scope, request_hash, session, *, blocking_tool_names):
    """Atomically acquire idempotency, serialize the session, and bind its claim."""
    from bkflow.harness.models import DebugSession

    resource_reference = str(session.id)
    with transaction.atomic():
        acquisition = acquire_idempotency(scope, request_hash)
        if acquisition.replayed:
            return acquisition
        locked_session = DebugSession._base_manager.select_for_update().select_related("run").get(pk=session.pk)
        blocked = (
            HarnessIdempotencyRecord.objects.select_for_update()
            .filter(
                platform_app=acquisition.record.platform_app,
                actor=acquisition.record.actor,
                space_id=acquisition.record.space_id,
                tool_name__in=blocking_tool_names,
                run=locked_session.run,
                resource_reference=resource_reference,
                status="IN_FLIGHT",
            )
            .exclude(pk=acquisition.record.pk)
            .exists()
        )
        if blocked:
            raise IdempotencyInFlight("this debug session already has an uncertain mutation")
        bind_inflight_idempotency(
            acquisition.record,
            run=locked_session.run,
            resource_reference=resource_reference,
        )
        return acquisition


def acquire_execution_barrier(scope, request_hash, *, run, execution_id, blocking_tool_names):
    """Acquire and bind one execution mutation before any external dispatch.

    The caller owns the surrounding transaction.  This helper locks only the
    idempotency namespace, so callers can subsequently take the shared
    Template -> Run -> ... -> Execution graph locks in the canonical order.
    """
    resource_reference = str(execution_id)
    with transaction.atomic():
        acquisition = acquire_idempotency(scope, request_hash)
        if acquisition.replayed:
            return acquisition
        blocked = (
            HarnessIdempotencyRecord.objects.select_for_update()
            .filter(
                platform_app=acquisition.record.platform_app,
                actor=acquisition.record.actor,
                space_id=acquisition.record.space_id,
                tool_name__in=blocking_tool_names,
                run=run,
                resource_reference=resource_reference,
                status="IN_FLIGHT",
            )
            .exclude(pk=acquisition.record.pk)
            .exists()
        )
        if blocked:
            raise IdempotencyInFlight("this execution already has an uncertain mutation")
        bind_inflight_idempotency(
            acquisition.record,
            run=run,
            resource_reference=resource_reference,
        )
        return acquisition


def fail_idempotency(record):
    """Persist an explicit retryable failure without replacing a completion."""
    with transaction.atomic():
        locked_record = HarnessIdempotencyRecord.objects.select_for_update().get(pk=record.pk)
        if locked_record.status != "IN_FLIGHT":
            raise IdempotencyRecordImmutable("only an in-flight record can be failed")
        locked_record.status = "FAILED"
        locked_record.response_snapshot = {}
        locked_record.save(update_fields=["status", "response_snapshot", "update_at"])
        return locked_record


def _outcome(value):
    """Normalize a domain callback result while keeping response data explicit."""
    if isinstance(value, IdempotencyOutcome):
        return value
    return IdempotencyOutcome(response_snapshot=value)


def execute_idempotent(scope, request_hash, operation):
    """Run one database-backed write once and replay its completed response.

    The callback runs while the unique record remains locked. Failures are
    committed as ``FAILED`` before being re-raised, allowing a later retry with
    the same request hash to become the next owner.
    """
    failure = None
    with transaction.atomic():
        acquisition = acquire_idempotency(scope, request_hash)
        if acquisition.replayed:
            return IdempotencyResult(
                record=acquisition.record, replayed=True, response_snapshot=acquisition.response_snapshot
            )
        try:
            with transaction.atomic():
                outcome = _outcome(operation())
        except Exception as error:
            fail_idempotency(acquisition.record)
            failure = error
        else:
            record = complete_idempotency(
                acquisition.record,
                outcome.response_snapshot,
                run=outcome.run,
                resource_reference=outcome.resource_reference,
            )
            return IdempotencyResult(record=record, replayed=False, response_snapshot=record.response_snapshot)
    if failure is not None:
        raise failure
