"""Harness get_debug_session projection and convergence contracts."""

import copy
import datetime
import json
from dataclasses import replace

import pytest
from django.db import connection
from django.utils import timezone

from bkflow.harness.constants import DebugMode, DebugSessionStatus, HarnessRunStatus
from bkflow.harness.models import (
    DebugSession,
    EvidenceEvent,
    TokenLease,
    WorkflowPlanRevision,
)
from bkflow.harness.services.debug.adapter import DebugAdapter
from bkflow.harness.services.debug.facade import (
    get_debug_session_with_context,
    start_debug_session_with_context,
)
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.resolver import ProviderInfrastructureError
from bkflow.harness.services.token_broker import TokenBroker
from bkflow.space.configs import HarnessDebugEnabledConfig, SpaceConfigValueType
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, TemplateSnapshot

pytest_plugins = ("tests.interface.harness.debug.test_start_session",)


def _started(start_case, *, mode=None):
    context, _run, _revision, _template, request, resolver = start_case
    SpaceConfig.objects.create(
        space_id=context.space_id,
        name=HarnessDebugEnabledConfig.name,
        value_type=SpaceConfigValueType.TEXT.value,
        text_value="true",
    )
    if mode is not None:
        request = {**request, "mode": mode}
    assert start_debug_session_with_context(context, request, resolver=resolver)["ok"] is True
    return context, DebugSession.objects.get(), resolver


def _get_request(session, **overrides):
    values = {"session_id": str(session.id), "limit": 2}
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_get_projects_only_owned_session_context_and_evidence_cursor(start_case, monkeypatch):
    """A read must use session Evidence, not template-wide Engine history."""
    context, session, resolver = _started(start_case)
    occurred_at = timezone.now()
    for index in range(3):
        record_evidence(
            run=session.run,
            revision=session.revision,
            debug_session=session,
            event_type="DEBUG_READ_FIXTURE",
            action="fixture",
            payload={"index": index},
            actor=session.actor,
            correlation_id=session.trusted_context_snapshot["correlation_id"],
            occurred_at=occurred_at,
        )
    monkeypatch.setattr(DebugService, "history", lambda _self: (_ for _ in ()).throw(AssertionError("leak")))

    first = get_debug_session_with_context(context, _get_request(session), resolver=resolver)
    cursor = first["artifact_refs"][0]["history"]["next_cursor"]
    second = get_debug_session_with_context(context, _get_request(session, cursor=cursor), resolver=resolver)

    assert first["ok"] is True
    assert first["artifact_refs"][0]["type"] == "debug_session_status"
    assert first["artifact_refs"][0]["session"]["status"] == DebugSessionStatus.ACTIVE
    first_ids = [item["event_id"] for item in first["artifact_refs"][0]["history"]["items"]]
    second_ids = [item["event_id"] for item in second["artifact_refs"][0]["history"]["items"]]
    assert len(first_ids) == 2
    assert set(first_ids).isdisjoint(second_ids)
    assert first_ids + second_ids == [
        str(event_id)
        for event_id in EvidenceEvent.objects.filter(debug_session=session)
        .order_by("occurred_at", "id")
        .values_list("id", flat=True)
    ]
    assert first["next_actions"] == ["run_debug", "control_debug_session", "get_debug_session"]

    invalid = get_debug_session_with_context(
        context,
        _get_request(session, cursor="not_base64"),
        resolver=resolver,
    )
    assert invalid["ok"] is False
    assert invalid["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"


@pytest.mark.django_db
def test_get_redacts_context_and_externalizes_oversized_values(start_case):
    """A large or credential-bearing SDK context cannot become inline response data."""
    context, session, resolver = _started(start_case)
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    debug_context.global_vars = {"password": "raw-secret", "large": "x" * 10000}
    debug_context.save(update_fields=["global_vars"])
    written = []

    response = get_debug_session_with_context(
        context,
        _get_request(session),
        resolver=resolver,
        artifact_writer=lambda value: written.append(value) or "artifact://debug/session-context-1",
    )

    assert response["ok"] is True
    projection = response["artifact_refs"][0]["context"]
    assert projection == {"externalized": True, "artifact_ref": "artifact://debug/session-context-1"}
    assert written[0]["global_vars"]["password"] == "[REDACTED]"
    assert "raw-secret" not in str(response) + str(written)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "unsafe_context",
    [
        {"large": "x" * 20000},
        {"many": {"key_{:03d}".format(index): "value" for index in range(101)}},
    ],
)
def test_get_does_not_send_work_budget_overflow_to_artifact_writer(
    start_case,
    monkeypatch,
    unsafe_context,
):
    """Unbounded SDK residue is omitted before credential regex or external writes."""
    context, session, resolver = _started(start_case)
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    debug_context.global_vars = unsafe_context
    debug_context.save(update_fields=["global_vars"])
    written = []

    def forbidden_regex(_value):
        raise AssertionError("work-budget overflow reached credential regex")

    monkeypatch.setattr(
        "bkflow.harness.services.evidence.contains_secret_shaped_text",
        forbidden_regex,
    )
    response = get_debug_session_with_context(
        context,
        _get_request(session),
        resolver=resolver,
        artifact_writer=lambda value: written.append(value) or "artifact://debug/forbidden",
    )

    assert response["ok"] is True
    assert response["artifact_refs"][0]["context"] == {
        "omitted": True,
        "reason": "projection_budget_exceeded",
        "redaction_version": "builtin-credential-v1",
    }
    assert written == []


@pytest.mark.django_db
def test_get_converges_finished_step_back_to_active_without_releasing_run(start_case, monkeypatch):
    """A successful async step is not the global assertion completion gate."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    debug_context.status = "running"
    debug_context.active_task_id = 7001
    debug_context.last_task_id = 7001
    debug_context.last_run_type = "step"
    debug_context.last_run_status = "running"
    debug_context.save(update_fields=["status", "active_task_id", "last_task_id", "last_run_type", "last_run_status"])

    def settle(_service, context_row):
        context_row.status = "idle"
        context_row.active_task_id = None
        context_row.last_task_id = 7001
        context_row.last_run_type = "step"
        context_row.last_run_status = "finished"
        context_row.save(update_fields=["status", "active_task_id", "last_task_id", "last_run_type", "last_run_status"])

    monkeypatch.setattr(DebugService, "sync_from_debug_task", settle)
    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is True
    assert session.status == DebugSessionStatus.ACTIVE
    assert session.current_task_id is None
    assert session.run.status == HarnessRunStatus.DEBUGGING
    assert EvidenceEvent.objects.filter(event_type="DEBUG_RUN_COMPLETED", debug_session=session).count() == 1
    assert not EvidenceEvent.objects.filter(event_type="DEBUG_SESSION_COMPLETED", debug_session=session).exists()


@pytest.mark.django_db
def test_get_converges_finished_global_to_release_ready(start_case, monkeypatch):
    """Only a successful global run satisfies the P2 required assertion gate."""
    context, session, resolver = _started(start_case, mode=DebugMode.GLOBAL)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=7001,
        last_task_id=7001,
        last_run_type="global",
        last_run_status="running",
    )

    def settle(_service, context_row):
        context_row.status = "idle"
        context_row.active_task_id = None
        context_row.last_task_id = 7001
        context_row.last_run_type = "global"
        context_row.last_run_status = "finished"
        context_row.save(update_fields=["status", "active_task_id", "last_task_id", "last_run_type", "last_run_status"])

    monkeypatch.setattr(DebugService, "sync_from_debug_task", settle)
    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is True
    assert session.status == DebugSessionStatus.COMPLETED
    assert session.current_task_id is None
    assert session.run.status == HarnessRunStatus.RELEASE_READY
    assert EvidenceEvent.objects.filter(event_type="DEBUG_SESSION_COMPLETED", debug_session=session).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "last_status,terminal_status",
    [
        ("failed", DebugSessionStatus.FAILED),
        ("revoked", DebugSessionStatus.TERMINATED),
    ],
)
def test_get_converges_failed_or_revoked_step_to_draft(
    start_case,
    monkeypatch,
    last_status,
    terminal_status,
):
    """A failed or revoked step closes the assertion attempt into a repairable draft."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=7001,
        last_task_id=7001,
        last_run_type="step",
        last_run_status="running",
    )

    def settle(_service, context_row):
        context_row.status = "idle"
        context_row.active_task_id = None
        context_row.last_task_id = 7001
        context_row.last_run_type = "step"
        context_row.last_run_status = last_status
        context_row.save(update_fields=["status", "active_task_id", "last_task_id", "last_run_type", "last_run_status"])

    monkeypatch.setattr(DebugService, "sync_from_debug_task", settle)
    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is True
    assert session.status == terminal_status
    assert session.run.status == HarnessRunStatus.DRAFT_READY


@pytest.mark.django_db
def test_get_rejects_engine_run_type_mismatch_without_releasing_session(start_case, monkeypatch):
    """The template-scoped context cannot relabel a global task as this step session."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=7001,
        last_task_id=7001,
        last_run_type="global",
        last_run_status="running",
    )

    def settle(_service, context_row):
        context_row.status = "idle"
        context_row.active_task_id = None
        context_row.last_run_status = "finished"
        context_row.save(update_fields=["status", "active_task_id", "last_run_status"])

    monkeypatch.setattr(DebugService, "sync_from_debug_task", settle)
    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    session.refresh_from_db()
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_EXECUTION_FAILED"
    assert session.status == DebugSessionStatus.RUNNING
    assert session.current_task_id == 7001


@pytest.mark.django_db
def test_get_does_not_adopt_another_task_or_release_failed_expiry(start_case, monkeypatch):
    """Mismatched tasks and failed expiry termination leave ownership locked."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    debug_context.status = "running"
    debug_context.active_task_id = 9009
    debug_context.last_task_id = 9009
    debug_context.last_run_status = "finished"
    debug_context.save(update_fields=["status", "active_task_id", "last_task_id", "last_run_status"])
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="running-expiry-space",
    )
    monkeypatch.setattr(
        "bkflow.permission.token_issuer.TokenResourceValidator.validate",
        lambda *_args, **_kwargs: None,
    )
    TokenBroker().acquire_debug_lease(context, session)
    monkeypatch.setattr(
        "bkflow.harness.services.debug.read.timezone.now",
        lambda: session.expires_at + datetime.timedelta(seconds=1),
    )

    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_EXECUTION_FAILED"
    assert session.status == DebugSessionStatus.RUNNING
    assert session.current_task_id == 7001
    assert session.run.status == HarnessRunStatus.DEBUGGING
    assert not TokenLease.objects.filter(session=session, status=TokenLease.Status.ACTIVE).exists()
    assert TokenLease.objects.filter(session=session, status=TokenLease.Status.REVOKED).count() == 1


@pytest.mark.django_db
def test_repeated_running_expiry_termination_is_transactional_and_idempotent(start_case, mocker, monkeypatch):
    """Repeated expiry reads revoke once and never dispatch Engine termination twice."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=7001,
        active_run_type="global",
        last_task_id=7001,
        last_run_type="global",
        last_run_status="running",
    )
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="repeated-expiry-space",
    )
    mocker.patch("bkflow.permission.token_issuer.TokenResourceValidator.validate", return_value=None)
    TokenBroker().acquire_debug_lease(context, session)
    effective_now = session.expires_at + datetime.timedelta(seconds=1)
    monkeypatch.setattr("bkflow.harness.services.debug.read.timezone.now", lambda: effective_now)
    monkeypatch.setattr("bkflow.harness.models.timezone.now", lambda: effective_now)
    client = mocker.MagicMock()
    client.operate_task.return_value = {"result": True}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=client)
    terminate_in_atomic = []
    baseline_savepoint_depth = len(connection.savepoint_ids)
    original_terminate = DebugAdapter.terminate

    def observe_terminate(adapter, *args, **kwargs):
        terminate_in_atomic.append(len(connection.savepoint_ids) > baseline_savepoint_depth)
        return original_terminate(adapter, *args, **kwargs)

    monkeypatch.setattr(DebugAdapter, "terminate", observe_terminate)

    first = get_debug_session_with_context(context, _get_request(session), resolver=resolver)
    second = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    session.refresh_from_db()
    assert first["ok"] is True
    assert second["ok"] is True
    assert terminate_in_atomic == [True, True]
    assert client.operate_task.call_count == 1
    assert session.status == DebugSessionStatus.RUNNING
    assert session.current_task_id == 7001
    assert not TokenLease.objects.filter(session=session, status=TokenLease.Status.ACTIVE).exists()
    assert first["artifact_refs"][0]["context"]["termination_status"] == "terminating"
    assert second["artifact_refs"][0]["context"]["termination_status"] == "terminating"


@pytest.mark.django_db
@pytest.mark.parametrize("failure", ["task_states", "id_map"])
def test_get_engine_or_id_map_failure_keeps_owned_session_running(start_case, mocker, failure):
    """An incomplete Engine observation cannot release the session or its run."""
    context, session, resolver = _started(start_case)
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=7001,
        last_task_id=7001,
        last_run_status="running",
    )
    client = mocker.MagicMock()
    client.get_task_states.return_value = (
        {"result": False}
        if failure == "task_states"
        else {"result": True, "data": {"state": "FINISHED", "children": {}}}
    )
    client.get_node_id_map.return_value = {"result": False}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=client)

    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is True
    assert session.status == DebugSessionStatus.RUNNING
    assert session.current_task_id == 7001
    assert session.run.status == HarnessRunStatus.DEBUGGING


@pytest.mark.django_db
def test_get_rejects_foreign_owner_and_current_task_mismatch_before_engine(start_case, mocker):
    """Neither forged authority nor another task can be adopted by a read Tool."""
    context, session, resolver = _started(start_case)
    foreign = get_debug_session_with_context(
        replace(context, actor="foreign-user"),
        _get_request(session),
        resolver=resolver,
    )
    assert foreign["ok"] is False
    assert foreign["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"

    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = 7001
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(status="running", active_task_id=9009)
    engine = mocker.patch("bkflow.template.debug.service.DebugService.sync_from_debug_task")
    mismatch = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    assert mismatch["ok"] is False
    assert mismatch["errors"][0]["code"] == "DEBUG_EXECUTION_FAILED"
    engine.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,run_status",
    [
        (DebugSessionStatus.COMPLETED, HarnessRunStatus.RELEASE_READY),
        (DebugSessionStatus.FAILED, HarnessRunStatus.DRAFT_READY),
        (DebugSessionStatus.TERMINATED, HarnessRunStatus.DRAFT_READY),
    ],
)
def test_get_terminal_session_reads_only_persisted_evidence(start_case, mocker, status, run_status):
    """Old terminal sessions never expose a newer template-scoped DebugContext."""
    context, session, resolver = _started(start_case)
    session.status = status
    session.terminal_reason = "terminal_fixture"
    session.save(update_fields=["status", "terminal_reason"])
    session.run.status = run_status
    session.run.save(update_fields=["status"])
    engine = mocker.patch("bkflow.template.debug.service.DebugService.build_context_view")

    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    assert response["ok"] is True
    assert response["artifact_refs"][0]["session"]["status"] == status
    assert response["artifact_refs"][0]["context"] == {
        "available": False,
        "reason": "session_terminal",
    }
    engine.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("mutation", ["tree_drift", "provider_outage"])
def test_get_expires_idle_session_before_draft_or_provider_revalidation(
    start_case,
    mocker,
    monkeypatch,
    mutation,
):
    """Expiry deauthorization cannot be blocked by mutable draft or provider state."""
    context, session, resolver = _started(start_case)
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="expiry-space",
    )
    mocker.patch("bkflow.permission.token_issuer.TokenResourceValidator.validate", return_value=None)
    TokenBroker().acquire_debug_lease(context, session)
    if mutation == "tree_drift":
        snapshot = TemplateSnapshot.objects.get(template_id=session.template_id, draft=True, is_deleted=False)
        changed = dict(snapshot.data)
        changed["constants"] = {"${drift}": {"value": "changed"}}
        snapshot.data = changed
        snapshot.save(update_fields=["data"])
    else:

        class UnavailableResolver:
            def resolve(self, *_args, **_kwargs):
                raise ProviderInfrastructureError()

        resolver = UnavailableResolver()
    effective_now = session.expires_at + datetime.timedelta(seconds=1)
    monkeypatch.setattr("bkflow.harness.services.debug.read.timezone.now", lambda: effective_now)
    monkeypatch.setattr("bkflow.harness.models.timezone.now", lambda: effective_now)

    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is True
    assert session.status == DebugSessionStatus.EXPIRED
    assert session.run.status == HarnessRunStatus.DRAFT_READY
    assert not TokenLease.objects.filter(session=session, status=TokenLease.Status.ACTIVE).exists()


@pytest.mark.django_db
def test_get_with_debug_disabled_is_persisted_only_and_has_zero_side_effects(start_case, mocker, monkeypatch):
    """The read survives rollout disable without touching mutable runtime dependencies."""
    context, session, _resolver = _started(start_case)
    SpaceConfig.objects.filter(
        space_id=context.space_id,
        name=HarnessDebugEnabledConfig.name,
    ).update(text_value="false")
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    debug_context.global_vars = {"password": "shared-canvas-secret"}
    debug_context.save(update_fields=["global_vars"])
    effective_now = session.expires_at + datetime.timedelta(seconds=1)
    monkeypatch.setattr("bkflow.harness.services.debug.read.timezone.now", lambda: effective_now)
    monkeypatch.setattr("bkflow.harness.models.timezone.now", lambda: effective_now)
    evidence_before = list(EvidenceEvent.objects.values_list("id", flat=True))

    class ForbiddenResolver:
        def resolve(self, *_args, **_kwargs):
            raise AssertionError("resolver must not run")

    class ForbiddenAdapter:
        def __init__(self, **_kwargs):
            raise AssertionError("DebugService must not run")

    broker = mocker.MagicMock()
    broker.revoke_active_leases.side_effect = AssertionError("TokenBroker must not run")
    response = get_debug_session_with_context(
        context,
        _get_request(session),
        resolver=ForbiddenResolver(),
        adapter_class=ForbiddenAdapter,
        token_broker=broker,
        artifact_writer=lambda _value: (_ for _ in ()).throw(AssertionError("writer must not run")),
    )

    session.refresh_from_db()
    session.run.refresh_from_db()
    assert response["ok"] is True
    assert response["artifact_refs"][0]["context"] == {
        "available": False,
        "reason": "debug_disabled",
    }
    assert response["next_actions"] == ["get_debug_session"]
    assert session.status == DebugSessionStatus.ACTIVE
    assert session.run.status == HarnessRunStatus.DEBUGGING
    assert list(EvidenceEvent.objects.values_list("id", flat=True)) == evidence_before
    broker.revoke_active_leases.assert_not_called()
    assert "shared-canvas-secret" not in str(response)


@pytest.mark.django_db
@pytest.mark.parametrize("mutation", ["artifact_template", "superseded_revision"])
def test_get_rejects_managed_artifact_or_latest_revision_drift_before_engine(
    start_case,
    mocker,
    mutation,
):
    """An unchanged tree cannot hide a different template or superseded plan."""
    context, session, resolver = _started(start_case)
    if mutation == "artifact_template":
        artifacts = copy.deepcopy(session.run.artifact_references)
        artifacts[0]["template_id"] = session.template_id + 1
        session.run.artifact_references = artifacts
        session.run.save(update_fields=["artifact_references"])
    else:
        WorkflowPlanRevision.objects.create(
            run=session.run,
            sequence=session.revision.sequence + 1,
            parent_revision=session.revision,
            intent_spec={"goal": "superseding revision"},
            canonical_a2flow={"version": "2.0", "nodes": []},
            plan_hash="f" * 64,
        )
    engine = mocker.patch("bkflow.template.debug.service.DebugService.build_context_view")
    evidence_before = EvidenceEvent.objects.count()

    response = get_debug_session_with_context(context, _get_request(session), resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert EvidenceEvent.objects.count() == evidence_before
    engine.assert_not_called()


@pytest.mark.django_db
def test_get_history_uses_a_total_utf8_budget_without_duplicate_or_missing_events(start_case):
    """One large Evidence stream is paged below the real Envelope renderer budget."""
    context, session, resolver = _started(start_case)
    SpaceConfig.objects.filter(
        space_id=context.space_id,
        name=HarnessDebugEnabledConfig.name,
    ).update(text_value="false")
    occurred_at = timezone.now()
    for index in range(100):
        record_evidence(
            run=session.run,
            revision=session.revision,
            debug_session=session,
            event_type="DEBUG_LARGE_HISTORY_FIXTURE",
            action="fixture",
            payload={"index": index, "blob": "x" * 7000},
            actor=session.actor,
            correlation_id=session.trusted_context_snapshot["correlation_id"],
            occurred_at=occurred_at,
        )
    expected_ids = [
        str(event_id)
        for event_id in EvidenceEvent.objects.filter(debug_session=session)
        .order_by("occurred_at", "id")
        .values_list("id", flat=True)
    ]
    observed_ids = []
    cursor = None
    pages = 0
    while True:
        response = get_debug_session_with_context(
            context,
            _get_request(session, limit=100, **({"cursor": cursor} if cursor else {})),
            resolver=resolver,
        )
        assert response["ok"] is True
        assert len(json.dumps(response, ensure_ascii=False).encode("utf-8")) < 64 * 1024
        history = response["artifact_refs"][0]["history"]
        observed_ids.extend(item["event_id"] for item in history["items"])
        pages += 1
        cursor = history["next_cursor"]
        if cursor is None:
            break
    assert pages > 1
    assert observed_ids == expected_ids
