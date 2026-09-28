import copy
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

import pytest
from django.db import connection
from django.utils import timezone

from bkflow.harness.constants import HarnessAction, HarnessRunStatus, RiskLevel
from bkflow.harness.models import (
    ApprovalRequest,
    EvidenceEvent,
    ExecutionRun,
    HarnessIdempotencyRecord,
)
from bkflow.harness.services.approval import (
    ApprovalVerifier,
    InMemoryApprovalReplayGuard,
)
from bkflow.harness.services.execution.adapter import (
    ApplicationTaskAdapter,
    BoundCredentialResolver,
    CreateDispatchRejected,
    CreateDispatchUncertain,
    StartDispatchRejected,
    StartDispatchUncertain,
)
from bkflow.harness.services.execution.contracts import RUNTIME_AUTHORIZATION_MODE
from bkflow.harness.services.execution.saga import start_workflow_execution_with_context
from bkflow.harness.services.release.policy import ReleasePolicy
from bkflow.harness.services.resolver import ResolvedCapability
from bkflow.space.configs import HarnessExecutionEnabledConfig, SpaceConfigValueType
from bkflow.space.models import (
    Credential,
    CredentialScopeLevel,
    CredentialType,
    SpaceConfig,
)
from bkflow.task.services.task_creator import TaskCreationReceipt, TaskCreator
from tests.interface.harness.release import test_prepare_release as prepare_cases
from tests.interface.harness.release import test_publish_workflow as publish_cases


class RecordingAdapter:
    def __init__(self, *, create_error=None, start_error=None, read_state="RUNNING"):
        self.create_error = create_error
        self.start_error = start_error
        self._read_state = read_state
        self.calls = []
        self.transaction_states = []

    def create(self, *, publication, request, credentials):
        self.calls.append(("create", publication.published_snapshot_id, copy.deepcopy(credentials)))
        self.transaction_states.append(connection.in_atomic_block)
        if self.create_error:
            raise self.create_error
        return "8101"

    def start(self, task_ref):
        self.calls.append(("start", task_ref))
        self.transaction_states.append(connection.in_atomic_block)
        if self.start_error:
            raise self.start_error
        return None

    def read_state(self, task_ref):
        self.calls.append(("read", task_ref))
        self.transaction_states.append(connection.in_atomic_block)
        if isinstance(self._read_state, BaseException):
            raise self._read_state
        return self._read_state


class RecordingCredentialResolver:
    def __init__(self, values=None):
        self.values = values or {}
        self.calls = []
        self.transaction_states = []

    def resolve(self, bindings, *, space_id, scope_type, scope_value):
        credential_refs = tuple(
            (item["binding"] if isinstance(item, dict) else item).credential_ref for item in bindings
        )
        self.calls.append((credential_refs, space_id, scope_type, scope_value))
        self.transaction_states.append(connection.in_atomic_block)
        return copy.deepcopy(self.values)


class TransactionTrackingResolver:
    def __init__(self, delegate):
        self.delegate = delegate
        self.transaction_states = []

    def resolve(self, *args, **kwargs):
        self.transaction_states.append(connection.in_atomic_block)
        return self.delegate.resolve(*args, **kwargs)


@pytest.fixture
def execution_case(db):
    builder = prepare_cases.release_case.__wrapped__(db)
    case = publish_cases.publish_case.__wrapped__(builder)
    first = publish_cases.publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    backend = publish_cases.ReceiptBackend(publish_cases.expected_claims(case, approval))
    verifier = ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard())
    published = publish_cases.publish(
        case,
        {
            **case.publish_request,
            "approval_request_id": str(approval.id),
            "approval_receipt_ref": publish_cases.RECEIPT_REF,
        },
        approval_verifier=verifier,
    )
    assert published["ok"] is True
    case.run.refresh_from_db()
    case.publication = case.manifest.publication
    SpaceConfig.objects.update_or_create(
        space_id=case.context.space_id,
        name=HarnessExecutionEnabledConfig.name,
        defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": "true"},
    )
    case.start_request = {
        "run_id": str(case.run.run_id),
        "manifest_id": str(case.manifest.id),
        "publication_id": str(case.publication.id),
        "expected_plan_hash": case.manifest.plan_hash,
        "name": "Harness execution",
        "constants": {"${region}": "ap-guangzhou"},
        "idempotency_key": "start-workflow-1",
    }
    case.release_policy = ReleasePolicy(profiles={case.context.policy_version: prepare_cases.POSTCONDITION_SPEC})
    return case


def start(case, payload=None, **kwargs):
    values = {
        "resolver": case.resolver,
        "release_policy": case.release_policy,
        "converter_class": prepare_cases.ReleaseConverter,
        "credential_resolver": RecordingCredentialResolver(),
        "adapter": RecordingAdapter(),
    }
    values.update(kwargs)
    return start_workflow_execution_with_context(case.context, payload or case.start_request, **values)


def start_claims(case, approval):
    return {
        "actor": case.context.actor,
        "platform_app": case.context.platform_app,
        "space_id": case.context.space_id,
        "scope": case.run.scope,
        "environment": case.context.target_environment,
        "plan_hash": case.manifest.plan_hash,
        "action": HarnessAction.START_WORKFLOW_EXECUTION,
        "action_digest": approval.action_digest,
    }


def approved_payload(case, first):
    return {
        **case.start_request,
        "approval_request_id": first["approval_request_id"],
        "approval_receipt_ref": "approval://bkaidev/start-receipt",
    }


def approved_verifier(case, first):
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    backend = publish_cases.ReceiptBackend(start_claims(case, approval))
    return ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()), backend


@pytest.mark.django_db
def test_first_call_creates_start_specific_pending_approval_without_runtime_side_effects(execution_case):
    case = execution_case
    adapter = RecordingAdapter()
    credentials = RecordingCredentialResolver({"A": {"value": "SECRET_SENTINEL"}})

    response = start(case, adapter=adapter, credential_resolver=credentials)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_REQUIRED"
    approval = ApprovalRequest.objects.get(pk=response["approval_request_id"])
    assert approval.action == HarnessAction.START_WORKFLOW_EXECUTION
    assert approval.status == ApprovalRequest.Status.PENDING
    assert ExecutionRun.objects.count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name=HarnessAction.START_WORKFLOW_EXECUTION).count() == 0
    assert adapter.calls == []
    assert credentials.calls == []
    assert ApprovalRequest.objects.filter(action=HarnessAction.PUBLISH_WORKFLOW).count() == 1


@pytest.mark.django_db
def test_closed_request_rejects_plaintext_credentials_and_sdk_mode_fails_closed(execution_case):
    case = execution_case
    adapter = RecordingAdapter()
    response = start(case, {**case.start_request, "credentials": {"password": "raw"}}, adapter=adapter)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert adapter.calls == []
    assert RUNTIME_AUTHORIZATION_MODE == "harness_domain_service"
    with pytest.raises(ValueError, match="runtime authorization mode is unavailable"):
        ApplicationTaskAdapter(runtime_authorization_mode="brokered_sdk_token")


@pytest.mark.django_db(transaction=True)
def test_approved_call_creates_starts_reads_back_and_persists_only_safe_runtime_facts(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, backend = approved_verifier(case, first)
    adapter = RecordingAdapter(read_state="RUNNING")
    credentials = RecordingCredentialResolver({"A": {"value": "ENGINE_SECRET_SENTINEL"}})

    response = start(
        case,
        payload,
        approval_verifier=verifier,
        adapter=adapter,
        credential_resolver=credentials,
    )
    replay = start(
        case,
        payload,
        approval_verifier=verifier,
        adapter=adapter,
        credential_resolver=credentials,
    )

    assert replay == response
    assert response["ok"] is True
    assert response["status"] == HarnessRunStatus.EXECUTING
    assert response["artifact_refs"][0]["task_ref"] == "8101"
    execution = ExecutionRun.objects.get()
    assert execution.status == ExecutionRun.Status.EXECUTING
    assert execution.task_ref == "8101"
    assert adapter.calls == [
        ("create", case.publication.published_snapshot_id, credentials.values),
        ("start", "8101"),
        ("read", "8101"),
    ]
    assert adapter.transaction_states == [False, False, False]
    # Replay repeats freshness and current credential-scope authorization, but
    # never repeats an Engine mutation.
    assert credentials.transaction_states == [False, False]
    assert backend.transaction_states == [False]
    serialized = repr(response) + repr(list(EvidenceEvent.objects.filter(execution=execution).values()))
    serialized += repr(
        HarnessIdempotencyRecord.objects.get(tool_name=HarnessAction.START_WORKFLOW_EXECUTION).response_snapshot
    )
    assert "ENGINE_SECRET_SENTINEL" not in serialized
    assert payload["approval_receipt_ref"] not in serialized


@pytest.mark.django_db(transaction=True)
def test_create_without_task_ref_becomes_uncertain_and_retry_never_redispatches(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter(create_error=CreateDispatchUncertain())

    response = start(case, payload, approval_verifier=verifier, adapter=adapter)
    retry = start(case, payload, approval_verifier=verifier, adapter=adapter)

    assert response == retry
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["next_actions"] == ["manual_reconcile_execution"]
    assert ExecutionRun.objects.get().status == ExecutionRun.Status.CREATE_UNCERTAIN
    assert [call[0] for call in adapter.calls] == ["create"]


class CrashAfterTaskPersist(BaseException):
    pass


class CrashAfterCreateBarrier(BaseException):
    pass


@pytest.mark.django_db(transaction=True)
def test_retry_after_task_ref_persisted_resumes_start_without_duplicate_create(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter()

    with pytest.raises(CrashAfterTaskPersist):
        start(
            case,
            payload,
            approval_verifier=verifier,
            adapter=adapter,
            test_after_task_persist_hook=lambda execution: (_ for _ in ()).throw(CrashAfterTaskPersist()),
        )
    assert ExecutionRun.objects.get().status == ExecutionRun.Status.CREATED

    response = start(case, payload, approval_verifier=verifier, adapter=adapter)

    assert response["ok"] is True
    assert [call[0] for call in adapter.calls] == ["create", "start", "read"]


@pytest.mark.django_db(transaction=True)
def test_ambiguous_start_recovers_only_from_readback_and_otherwise_stays_uncertain(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    recovered = RecordingAdapter(start_error=StartDispatchUncertain(), read_state="RUNNING")

    response = start(case, payload, approval_verifier=verifier, adapter=recovered)

    assert response["ok"] is True
    assert ExecutionRun.objects.get().status == ExecutionRun.Status.EXECUTING
    assert [call[0] for call in recovered.calls] == ["create", "start", "read"]


@pytest.mark.django_db(transaction=True)
def test_unreadable_ambiguous_start_is_not_blindly_retried(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter(start_error=StartDispatchUncertain(), read_state=RuntimeError("engine secret"))

    response = start(case, payload, approval_verifier=verifier, adapter=adapter)
    retry = start(case, payload, approval_verifier=verifier, adapter=adapter)

    assert response == retry
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["next_actions"] == ["manual_reconcile_execution"]
    assert ExecutionRun.objects.get().status == ExecutionRun.Status.START_UNCERTAIN
    assert [call[0] for call in adapter.calls] == ["create", "start", "read", "read"]


@pytest.mark.django_db
def test_disabled_execution_flag_stops_before_approval_or_runtime(execution_case):
    case = execution_case
    SpaceConfig.objects.filter(space_id=case.context.space_id, name=HarnessExecutionEnabledConfig.name).update(
        text_value="false"
    )
    adapter = RecordingAdapter()

    response = start(case, adapter=adapter)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    assert ApprovalRequest.objects.filter(action=HarnessAction.START_WORKFLOW_EXECUTION).count() == 0
    assert adapter.calls == []


@pytest.mark.django_db(transaction=True)
def test_provider_and_open_plugin_preparation_are_both_outside_atomic(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    resolver = TransactionTrackingResolver(case.resolver)
    preparation_states = []
    engine_states = []
    client = mock.Mock()

    def prepare_snapshot(**kwargs):
        preparation_states.append(connection.in_atomic_block)
        return kwargs["extra_info"]

    def create_task(data):
        engine_states.append(connection.in_atomic_block)
        return {
            "result": True,
            "data": {
                "id": 8301,
                "name": data["name"],
                "template_id": data["template_id"],
                "parameters": {},
            },
        }

    def operate_task(*args, **kwargs):
        engine_states.append(connection.in_atomic_block)
        return {"result": True}

    def get_task_states(*args, **kwargs):
        engine_states.append(connection.in_atomic_block)
        return {"result": True, "data": {"state": "RUNNING"}}

    client.create_task.side_effect = create_task
    client.operate_task.side_effect = operate_task
    client.get_task_states.side_effect = get_task_states
    creator = TaskCreator(client_factory=lambda **kwargs: client, snapshot_preparer=prepare_snapshot)
    adapter = ApplicationTaskAdapter(
        space_id=case.context.space_id,
        actor=case.context.actor,
        task_creator=creator,
        client_factory=lambda **kwargs: client,
    )

    with mock.patch("bkflow.task.services.task_creator.event_broadcast_signal.send"):
        response = start(
            case,
            payload,
            approval_verifier=verifier,
            resolver=resolver,
            adapter=adapter,
        )

    assert response["ok"] is True
    assert resolver.transaction_states and set(resolver.transaction_states) == {False}
    assert preparation_states == [False]
    assert engine_states == [False, False, False]


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_key_observes_dispatch_barrier_without_duplicate_create(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter()
    nested = []

    def interleave(_execution):
        nested.append(start(case, payload, approval_verifier=verifier, adapter=adapter))

    outer = start(
        case,
        payload,
        approval_verifier=verifier,
        adapter=adapter,
        test_after_create_barrier_hook=interleave,
    )

    assert outer["ok"] is True
    assert nested[0]["ok"] is False
    assert nested[0]["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert nested[0]["next_actions"] != ["manual_reconcile_execution"]
    assert [call[0] for call in adapter.calls].count("create") == 1


@pytest.mark.django_db(transaction=True)
def test_stale_create_dispatch_barrier_becomes_manual_uncertain_without_redispatch(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter()

    with pytest.raises(CrashAfterCreateBarrier):
        start(
            case,
            payload,
            approval_verifier=verifier,
            adapter=adapter,
            test_after_create_barrier_hook=lambda execution: (_ for _ in ()).throw(CrashAfterCreateBarrier()),
        )
    execution = ExecutionRun.objects.get()
    stale_at = timezone.now() - timezone.timedelta(minutes=5)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE {} SET update_at = %s WHERE id = %s".format(ExecutionRun._meta.db_table),
            [stale_at, execution.id.hex],
        )

    response = start(case, payload, approval_verifier=verifier, adapter=adapter)

    execution.refresh_from_db()
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["next_actions"] == ["manual_reconcile_execution"]
    assert execution.status == ExecutionRun.Status.CREATE_UNCERTAIN
    assert adapter.calls == []


@pytest.mark.django_db(transaction=True)
def test_only_original_create_dispatch_may_recover_a_stale_uncertain_barrier_with_late_receipt(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter()
    nested = []

    def expire_and_retry(execution):
        stale_at = timezone.now() - timezone.timedelta(minutes=5)
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE {} SET update_at = %s WHERE id = %s".format(ExecutionRun._meta.db_table),
                [stale_at, execution.id.hex],
            )
        nested.append(start(case, payload, approval_verifier=verifier, adapter=adapter))

    response = start(
        case,
        payload,
        approval_verifier=verifier,
        adapter=adapter,
        test_after_create_barrier_hook=expire_and_retry,
    )

    execution = ExecutionRun.objects.get()
    assert nested[0]["next_actions"] == ["manual_reconcile_execution"]
    assert response["ok"] is True
    assert execution.task_ref == "8101"
    assert execution.status == ExecutionRun.Status.EXECUTING
    assert [call[0] for call in adapter.calls] == ["create", "start", "read"]


@pytest.mark.django_db
def test_publish_approval_cannot_authorize_start_and_missing_verifier_fails_closed(execution_case):
    case = execution_case
    publish_approval = ApprovalRequest.objects.get(action=HarnessAction.PUBLISH_WORKFLOW)
    forged = {
        **case.start_request,
        "approval_request_id": str(publish_approval.id),
        "approval_receipt_ref": publish_cases.RECEIPT_REF,
    }
    adapter = RecordingAdapter()

    wrong_action = start(case, forged, adapter=adapter)
    first = start(case, adapter=adapter)
    without_verifier = start(case, approved_payload(case, first), adapter=adapter)

    assert wrong_action["errors"][0]["code"] == "APPROVAL_INVALID"
    assert without_verifier["errors"][0]["code"] == "APPROVAL_REQUIRED"
    assert adapter.calls == []


@pytest.mark.django_db
def test_injected_no_approval_policy_cannot_downgrade_production_start(execution_case):
    case = execution_case
    adapter = RecordingAdapter()

    response = start(case, action_policy=publish_cases.NoApprovalActionPolicy(), adapter=adapter)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ApprovalRequest.objects.filter(action=HarnessAction.START_WORKFLOW_EXECUTION).count() == 0
    assert adapter.calls == []


@pytest.mark.django_db(transaction=True)
def test_schema_drift_and_trusted_actor_mismatch_stop_before_runtime(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter()

    drift = start(
        case,
        payload,
        approval_verifier=verifier,
        resolver=prepare_cases.ReleaseResolver(schema_hash="d" * 64),
        adapter=adapter,
    )
    foreign_context = replace(case.context, actor="other-user")
    foreign = start_workflow_execution_with_context(
        foreign_context,
        payload,
        resolver=case.resolver,
        release_policy=case.release_policy,
        converter_class=prepare_cases.ReleaseConverter,
        credential_resolver=RecordingCredentialResolver(),
        adapter=adapter,
    )

    assert drift["errors"][0]["code"] == "VALIDATION_STALE"
    assert foreign["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert adapter.calls == []


@pytest.mark.django_db(transaction=True)
def test_provider_outage_does_not_consume_receipt_but_schema_drift_revokes_start_approval(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, backend = approved_verifier(case, first)
    adapter = RecordingAdapter()

    outage = start(
        case,
        payload,
        approval_verifier=verifier,
        resolver=prepare_cases.UnavailableResolver(),
        adapter=adapter,
    )
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    assert outage["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert approval.status == ApprovalRequest.Status.PENDING
    assert backend.transaction_states == []

    drift = start(
        case,
        payload,
        approval_verifier=verifier,
        resolver=prepare_cases.ReleaseResolver(schema_hash="d" * 64),
        adapter=adapter,
    )
    approval.refresh_from_db()
    case.run.refresh_from_db()
    assert drift["errors"][0]["code"] == "VALIDATION_STALE"
    assert approval.status == ApprovalRequest.Status.REVOKED
    assert case.run.status == HarnessRunStatus.PUBLISHED
    assert case.manifest.publication.pk == case.publication.pk
    assert adapter.calls == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("barrier", ["create", "start"])
def test_each_runtime_side_effect_barrier_rechecks_live_verified_approval(execution_case, barrier):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter()

    def revoke(_execution):
        approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
        approval.status = ApprovalRequest.Status.REVOKED
        approval.save(update_fields=["status", "active_approval_key", "update_at"])

    hooks = {
        "test_before_create_barrier_hook": revoke if barrier == "create" else None,
        "test_before_start_barrier_hook": revoke if barrier == "start" else None,
    }
    response = start(case, payload, approval_verifier=verifier, adapter=adapter, **hooks)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_INVALID"
    assert [call[0] for call in adapter.calls] == ([] if barrier == "create" else ["create"])
    execution = ExecutionRun.objects.first()
    if barrier == "start":
        assert execution.task_ref == "8101"
        assert execution.status == ExecutionRun.Status.CREATED
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.PUBLISHED


@pytest.mark.django_db(transaction=True)
def test_same_key_with_different_approved_action_payload_conflicts_before_dispatch(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    original_adapter = RecordingAdapter()
    assert start(case, payload, approval_verifier=verifier, adapter=original_adapter)["ok"] is True

    changed_request = {**case.start_request, "name": "different task"}
    second_first = start(case, changed_request)
    second_payload = approved_payload(case, second_first)
    second_payload["name"] = "different task"
    second_verifier, _ = approved_verifier(case, second_first)
    second_adapter = RecordingAdapter()

    conflict = start(case, second_payload, approval_verifier=second_verifier, adapter=second_adapter)

    assert conflict["ok"] is False
    assert conflict["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"
    assert second_adapter.calls == []
    assert ExecutionRun.objects.count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "create_error,start_error,reason,expected_calls",
    [
        (CreateDispatchRejected(), None, "create_rejected", ["create"]),
        (None, StartDispatchRejected(), "start_rejected", ["create", "start"]),
    ],
)
def test_explicit_dispatch_rejection_is_terminal_safe_and_idempotently_replayed(
    execution_case, create_error, start_error, reason, expected_calls
):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter(create_error=create_error, start_error=start_error)

    response = start(case, payload, approval_verifier=verifier, adapter=adapter)
    replay = start(case, payload, approval_verifier=verifier, adapter=adapter)

    assert replay == response
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "EXECUTION_REJECTED"
    assert "manual_reconcile_execution" not in response.get("next_actions", [])
    execution = ExecutionRun.objects.get()
    assert execution.status == ExecutionRun.Status.FAILED
    assert execution.postcondition_status == ExecutionRun.PostconditionStatus.UNAVAILABLE
    assert execution.postcondition_report == {"reason": reason}
    assert execution.terminal_at is not None
    assert [call[0] for call in adapter.calls] == expected_calls
    assert HarnessIdempotencyRecord.objects.get(tool_name=HarnessAction.START_WORKFLOW_EXECUTION).status == "COMPLETED"
    assert EvidenceEvent.objects.filter(execution=execution, event_type="EXECUTION_REJECTED").count() == 1
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.PUBLISHED


@pytest.mark.django_db(transaction=True)
def test_publication_snapshot_remains_execution_anchor_after_template_pointer_advances(execution_case):
    case = execution_case
    later = case.snapshot.__class__.objects.create(
        template_id=case.template.id,
        draft=False,
        version="2.0.0",
        md5sum="1" * 32,
        data={**copy.deepcopy(case.snapshot.data), "later": True},
    )
    case.template.snapshot_id = later.id
    case.template.save(update_fields=["snapshot_id"])
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)
    adapter = RecordingAdapter()

    response = start(case, payload, approval_verifier=verifier, adapter=adapter)

    assert response["ok"] is True
    assert adapter.calls[0][1] == case.publication.published_snapshot_id


@pytest.mark.django_db(transaction=True)
def test_safe_post_create_warning_keeps_task_ref_and_continues_saga(execution_case):
    case = execution_case
    first = start(case)
    payload = approved_payload(case, first)
    verifier, _ = approved_verifier(case, first)

    class WarningAdapter(RecordingAdapter):
        def create(self, *, publication, request, credentials):
            self.calls.append(("create", publication.published_snapshot_id, copy.deepcopy(credentials)))
            return TaskCreationReceipt(task_ref="8101", warnings=("TASK_CREATE_NOTIFICATION_FAILED",))

    adapter = WarningAdapter()
    response = start(case, payload, approval_verifier=verifier, adapter=adapter)

    assert response["ok"] is True
    execution = ExecutionRun.objects.get()
    assert execution.task_ref == "8101"
    event = EvidenceEvent.objects.get(execution=execution, event_type="TASK_CREATED")
    assert event.redacted_payload["warning_codes"] == ["TASK_CREATE_NOTIFICATION_FAILED"]


@pytest.mark.django_db
def test_bound_credential_resolver_requires_current_space_and_scope(execution_case):
    case = execution_case
    credential = Credential.objects.create(
        space_id=case.context.space_id,
        name="runtime",
        type=CredentialType.CUSTOM.value,
        scope_level=CredentialScopeLevel.ALL.value,
        content={"api_key": "ENGINE_ONLY_SECRET"},
        creator="owner",
    )
    binding = SimpleNamespace(
        node_id="A",
        capability_ref="capability://uniform_api/source/demo@1.0.0",
        resolved_version="1.0.0",
        schema_hash="b" * 64,
        conversion_fingerprint="c" * 64,
        credential_ref="credential://id/{}".format(credential.id),
        risk="L1",
    )
    capability = ResolvedCapability(
        capability_ref=binding.capability_ref,
        plugin_type="uniform_api",
        code="demo",
        source_key="source",
        resolved_version=binding.resolved_version,
        schema_hash=binding.schema_hash,
        schema={},
        risk_level=binding.risk,
        conversion_metadata={"kind": "uniform_api", "credential_key": "custom_app_credential"},
        conversion_fingerprint=binding.conversion_fingerprint,
    )
    resolved_binding = {"binding": binding, "capability": capability}

    values = BoundCredentialResolver().resolve(
        [resolved_binding],
        space_id=case.context.space_id,
        scope_type=case.context.scope_type,
        scope_value=case.context.scope_value,
    )
    assert values == {"custom_app_credential": {"api_key": "ENGINE_ONLY_SECRET"}}

    credential.scope_level = CredentialScopeLevel.NONE.value
    credential.save(update_fields=["scope_level", "update_at"])
    with pytest.raises(ValueError, match="bound credential is unavailable"):
        BoundCredentialResolver().resolve(
            [resolved_binding],
            space_id=case.context.space_id,
            scope_type=case.context.scope_type,
            scope_value=case.context.scope_value,
        )


@pytest.mark.django_db
def test_bound_credentials_require_exact_uniform_capability_and_safe_unique_engine_key(execution_case):
    case = execution_case
    first = Credential.objects.create(
        space_id=case.context.space_id,
        name="first",
        type=CredentialType.CUSTOM.value,
        scope_level=CredentialScopeLevel.ALL.value,
        content={"bk_app_code": "app-one", "bk_app_secret": "SECRET_ONE"},
        creator="owner",
    )
    second = Credential.objects.create(
        space_id=case.context.space_id,
        name="second",
        type=CredentialType.CUSTOM.value,
        scope_level=CredentialScopeLevel.ALL.value,
        content={"bk_app_code": "app-two", "bk_app_secret": "SECRET_TWO"},
        creator="owner",
    )

    def item(node_id, credential, *, plugin_type="uniform_api", key="shared", capability_ref=None):
        binding = SimpleNamespace(
            node_id=node_id,
            capability_ref=capability_ref or "capability://uniform_api/source/{}@1.0.0".format(node_id),
            resolved_version="1.0.0",
            schema_hash="b" * 64,
            conversion_fingerprint="c" * 64,
            credential_ref="credential://id/{}".format(credential.id),
            risk=RiskLevel.L1,
        )
        capability = ResolvedCapability(
            capability_ref=binding.capability_ref,
            plugin_type=plugin_type,
            code=node_id,
            source_key="source",
            resolved_version=binding.resolved_version,
            schema_hash=binding.schema_hash,
            schema={},
            risk_level=binding.risk,
            conversion_metadata={"kind": plugin_type, "credential_key": key},
            conversion_fingerprint=binding.conversion_fingerprint,
        )
        return {"binding": binding, "capability": capability}

    resolver = BoundCredentialResolver()
    kwargs = {
        "space_id": case.context.space_id,
        "scope_type": case.context.scope_type,
        "scope_value": case.context.scope_value,
    }
    same_ref = resolver.resolve([item("A", first), item("B", first)], **kwargs)
    assert same_ref == {"shared": first.value}
    with pytest.raises(ValueError, match="conflicting credential bindings"):
        resolver.resolve([item("A", first), item("B", second)], **kwargs)
    with pytest.raises(ValueError, match="uniform API"):
        resolver.resolve([item("A", first, plugin_type="component")], **kwargs)
    with pytest.raises(ValueError, match="credential key"):
        resolver.resolve([item("A", first, key="../unsafe")], **kwargs)
    drifted = item("A", first)
    drifted["capability"] = replace(drifted["capability"], schema_hash="d" * 64)
    with pytest.raises(ValueError, match="capability binding is stale"):
        resolver.resolve([drifted], **kwargs)


@pytest.mark.django_db
def test_application_adapter_maps_transport_false_to_uncertain_and_passes_trusted_operator(execution_case):
    case = execution_case
    client = mock.Mock()
    client.operate_task.return_value = {"result": False, "message": "opaque transport failure"}
    adapter = ApplicationTaskAdapter(
        space_id=case.context.space_id,
        actor=case.context.actor,
        client_factory=lambda **kwargs: client,
        task_creator=mock.Mock(),
    )

    with pytest.raises(StartDispatchUncertain):
        adapter.start("8101")

    client.operate_task.assert_called_once_with("8101", "start", {"operator": case.context.actor})
