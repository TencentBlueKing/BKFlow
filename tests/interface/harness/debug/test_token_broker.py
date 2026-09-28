"""Security and lifecycle contracts for the server-side debug Token Broker."""

import datetime
import json
import pickle

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from bkflow.harness.constants import DebugMode, DebugSessionStatus, HarnessRunStatus
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    DebugSession,
    HarnessRun,
    TokenLease,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.token_broker import (
    MAX_DEBUG_TOKEN_TTL_SECONDS,
    TokenBroker,
)
from bkflow.permission.models import Token
from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot


def trusted_context(space_id, **overrides):
    values = {
        "platform_key": "bkaidev",
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": space_id,
        "scope_type": "project",
        "scope_value": "902",
        "target_environment": "stag",
        "policy_version": "risk-2026.09",
        "mcp_contract_version": "1.2.0",
        "correlation_id": "p2-broker-call",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


@pytest.fixture
def broker_session(db, monkeypatch):
    space = Space.objects.create(app_code="trusted-app", platform_url="http://example.test", name="broker-space")
    context = trusted_context(space.id)
    run = HarnessRun.objects.create(
        platform=context.platform_key,
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        scope=canonical_scope(context.scope_type, context.scope_value),
        environment=context.target_environment,
        status=HarnessRunStatus.DEBUGGING,
        policy_version=context.policy_version,
        mcp_contract_version=context.mcp_contract_version,
    )
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={},
        canonical_a2flow={},
        plan_hash="a" * 64,
    )
    snapshot = TemplateSnapshot.objects.create(md5sum="0" * 32, data={"activities": {}})
    Template.objects.create(
        id=42,
        space_id=space.id,
        snapshot_id=snapshot.id,
        name="broker-template",
        scope_type=context.scope_type,
        scope_value=context.scope_value,
        bk_app_code=context.platform_app,
    )
    session = DebugSession.objects.create(
        run=run,
        revision=revision,
        template_id=42,
        debug_context_id=84,
        mode=DebugMode.STEP,
        status=DebugSessionStatus.ACTIVE,
        plan_hash=revision.plan_hash,
        tree_fingerprint={
            "nodes": {"node-1": "b" * 32},
            "flows": "c" * 32,
            "gateways": "d" * 32,
            "constants": "e" * 32,
        },
        actor=context.actor,
        policy_version=context.policy_version,
        trusted_context_snapshot={
            "platform_key": context.platform_key,
            "platform_app": context.platform_app,
            "actor": context.actor,
            "space_id": context.space_id,
            "scope_type": context.scope_type,
            "scope_value": context.scope_value,
            "target_environment": context.target_environment,
            "policy_version": context.policy_version,
            "mcp_contract_version": context.mcp_contract_version,
            "correlation_id": "p2-session",
        },
        expires_at=timezone.now() + datetime.timedelta(minutes=10),
        last_heartbeat_at=timezone.now(),
    )
    monkeypatch.setattr("bkflow.permission.services.token_issuer.TokenResourceValidator.validate", lambda _self: None)
    return context, session


@pytest.mark.django_db
def test_acquire_issues_private_capped_template_mock_lease_and_safe_handle(broker_session):
    context, session = broker_session
    before = timezone.now()

    handle = TokenBroker().acquire_debug_lease(context, session)

    lease = TokenLease.objects.get(pk=handle.lease_id)
    assert lease.resource_type == TokenLease.Resource.TEMPLATE
    assert lease.resource_id == "42"
    assert lease.permission == TokenLease.Permission.MOCK
    assert lease.expires_at <= before + datetime.timedelta(seconds=MAX_DEBUG_TOKEN_TTL_SECONDS + 1)
    assert lease.token_fingerprint not in {"", handle.secret}
    assert handle.secret not in repr(handle)
    assert not hasattr(handle, "to_dict")
    with pytest.raises((TypeError, pickle.PicklingError)):
        pickle.dumps(handle)
    with pytest.raises(TypeError):
        json.dumps(handle)
    assert handle.secret not in repr(TokenLease.objects.values().get(pk=lease.pk))


@pytest.mark.django_db
def test_repeated_acquire_reuses_own_live_lease_but_sessions_never_share_scope_token(broker_session):
    context, first_session = broker_session
    broker = TokenBroker()
    first = broker.acquire_debug_lease(context, first_session)
    replay = broker.acquire_debug_lease(context, first_session)
    assert replay.lease_id == first.lease_id
    assert replay.secret == first.secret

    run = first_session.run
    second_revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=2,
        parent_revision=first_session.revision,
        intent_spec={},
        canonical_a2flow={},
        plan_hash="f" * 64,
    )
    second_session = DebugSession.objects.create(
        run=run,
        revision=second_revision,
        template_id=43,
        debug_context_id=85,
        mode=DebugMode.STEP,
        status=DebugSessionStatus.ACTIVE,
        plan_hash=second_revision.plan_hash,
        tree_fingerprint=first_session.tree_fingerprint,
        actor=first_session.actor,
        policy_version=first_session.policy_version,
        trusted_context_snapshot=first_session.trusted_context_snapshot,
        expires_at=first_session.expires_at,
        last_heartbeat_at=timezone.now(),
    )
    second_snapshot = TemplateSnapshot.objects.create(md5sum="1" * 32, data={"activities": {}})
    Template.objects.create(
        id=43,
        space_id=context.space_id,
        snapshot_id=second_snapshot.id,
        name="second-broker-template",
        scope_type=context.scope_type,
        scope_value=context.scope_value,
        bk_app_code=context.platform_app,
    )
    scope_first = broker.acquire_debug_lease(
        context, first_session, resource_type=TokenLease.Resource.SCOPE, resource_id="project_902"
    )
    scope_second = broker.acquire_debug_lease(
        context, second_session, resource_type=TokenLease.Resource.SCOPE, resource_id="project_902"
    )
    assert scope_first.secret != scope_second.secret
    assert scope_first.lease_id != scope_second.lease_id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "context_overrides",
    [
        {"platform_app": "foreign-app"},
        {"actor": "foreign-user"},
        {"space_id": 999},
        {"policy_version": "foreign-policy"},
    ],
)
def test_acquire_rejects_context_mismatch_without_issuing_token(broker_session, context_overrides):
    context, session = broker_session
    overrides = dict(context_overrides)
    forged_space_id = overrides.pop("space_id", context.space_id)
    forged = trusted_context(forged_space_id, **overrides)

    with pytest.raises(ValidationError):
        TokenBroker().acquire_debug_lease(forged, session)

    assert TokenLease.objects.count() == 0
    assert Token.objects.count() == 0


@pytest.mark.django_db
def test_acquire_rejects_run_identity_drift_from_immutable_session_snapshot(broker_session):
    context, session = broker_session
    run = session.run
    space = Space.objects.get(pk=context.space_id)
    run.platform_app = "replacement-app"
    run.save(update_fields=["platform_app"])
    space.app_code = "replacement-app"
    space.save(update_fields=["app_code"])
    forged = trusted_context(context.space_id, platform_app="replacement-app")

    with pytest.raises(ValidationError):
        TokenBroker().acquire_debug_lease(forged, session)

    assert Token.objects.count() == 0
    assert TokenLease.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("field,value", [("scope", ""), ("status", HarnessRunStatus.DRAFT_READY)])
def test_acquire_rejects_run_scope_or_state_drift(broker_session, field, value):
    context, session = broker_session
    run = session.run
    setattr(run, field, value)
    run.save(update_fields=[field])

    with pytest.raises(ValidationError):
        TokenBroker().acquire_debug_lease(context, session)

    assert Token.objects.count() == 0
    assert TokenLease.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [("space_id", 999), ("scope_value", "foreign"), ("bk_app_code", "foreign-app"), ("is_deleted", True)],
)
def test_acquire_proves_concrete_template_boundary_before_issuance(broker_session, field, value):
    context, session = broker_session
    template = Template.objects.get(pk=session.template_id)
    setattr(template, field, value)
    template.save(update_fields=[field])

    with pytest.raises(ValidationError):
        TokenBroker().acquire_debug_lease(context, session)

    assert Token.objects.count() == 0
    assert TokenLease.objects.count() == 0


@pytest.mark.django_db
def test_acquire_rejects_bad_permission_resource_terminal_and_expired_session(broker_session):
    context, session = broker_session
    broker = TokenBroker()
    with pytest.raises(ValidationError):
        broker.acquire_debug_lease(context, session, permission="VIEW")
    with pytest.raises(ValidationError):
        broker.acquire_debug_lease(context, session, resource_type="TASK", resource_id="1")
    with pytest.raises(ValidationError):
        broker.acquire_debug_lease(context, session, resource_type=TokenLease.Resource.SCOPE, resource_id="project_903")

    session.status = DebugSessionStatus.TERMINATED
    session.terminal_reason = "operator terminated"
    session.save(update_fields=["status", "terminal_reason"])
    with pytest.raises(ValidationError):
        broker.acquire_debug_lease(context, session)
    assert Token.objects.count() == 0


@pytest.mark.django_db
def test_stale_lease_renews_and_revoke_active_leases_revokes_secret_without_leaking(
    broker_session, caplog, monkeypatch
):
    context, session = broker_session
    broker = TokenBroker()
    first = broker.acquire_debug_lease(context, session)
    lease = TokenLease.objects.get(pk=first.lease_id)
    past = timezone.now() - datetime.timedelta(seconds=1)
    Token.objects.filter(token=first.secret).update(expired_time=past)

    second = broker.acquire_debug_lease(context, session)
    lease.refresh_from_db()
    assert lease.status == TokenLease.Status.EXPIRED
    assert second.secret != first.secret
    assert second.lease_id != first.lease_id

    # Cleanup remains available after the session deadline so expiry cannot
    # strand an otherwise-live underlying credential.
    future = session.expires_at + datetime.timedelta(seconds=1)
    monkeypatch.setattr("bkflow.harness.services.token_broker.timezone.now", lambda: future)
    assert broker.revoke_active_leases(context, session) == 1
    renewed = TokenLease.objects.get(pk=second.lease_id)
    assert renewed.status == TokenLease.Status.REVOKED
    assert Token.objects.get(token=second.secret).has_expired()
    assert second.secret not in caplog.text


@pytest.mark.django_db
def test_expired_lease_revokes_an_underlying_token_renewed_by_legacy_api(broker_session, monkeypatch):
    context, session = broker_session
    broker = TokenBroker()
    first = broker.acquire_debug_lease(context, session)
    lease = TokenLease.objects.get(pk=first.lease_id)
    future = lease.expires_at + datetime.timedelta(seconds=1)
    Token.objects.filter(token=first.secret).update(expired_time=session.expires_at)
    monkeypatch.setattr("bkflow.harness.services.token_broker.timezone.now", lambda: future)

    second = broker.acquire_debug_lease(context, session)

    lease.refresh_from_db()
    assert lease.status == TokenLease.Status.EXPIRED
    assert Token.objects.get(token=first.secret).expired_time == future
    assert second.secret != first.secret
