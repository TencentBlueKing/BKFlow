"""Persistence contracts for P2 debug sessions, token leases, and evidence."""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from bkflow.harness.constants import (
    DebugMode,
    DebugSessionStatus,
    HarnessRunStatus,
    ValidationCheckpoint,
)
from bkflow.harness.models import (
    DebugSession,
    EvidenceEvent,
    HarnessRun,
    TokenLease,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.evidence import EVIDENCE_REDACTION_VERSION


def run_values(**overrides):
    """Build one complete Harness run payload."""
    values = {
        "platform": "bkaidev",
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": 902,
        "scope": canonical_scope("project", "902"),
        "environment": "stag",
        "status": HarnessRunStatus.DRAFT_READY,
        "policy_version": "risk-2026.09",
        "mcp_contract_version": "1.2.0",
    }
    values.update(overrides)
    return values


def trusted_context_snapshot(**overrides):
    """Build the exact positive trusted-context snapshot persisted by a session."""
    values = {
        "platform_key": "bkaidev",
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": 902,
        "scope_type": "project",
        "scope_value": "902",
        "target_environment": "stag",
        "policy_version": "risk-2026.09",
        "mcp_contract_version": "1.2.0",
        "correlation_id": "p2-model-test",
    }
    values.update(overrides)
    return values


def tree_fingerprint(**overrides):
    """Mirror the complete DebugService tree-fingerprint structure."""
    value = {
        "nodes": {"node-1": "a" * 32},
        "flows": "b" * 32,
        "gateways": "c" * 32,
        "constants": "d" * 32,
    }
    value.update(overrides)
    return value


@pytest.fixture
def run_and_revision(db):
    """Persist one trusted run and immutable revision."""
    run = HarnessRun.objects.create(**run_values())
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={"goal": "restart service"},
        canonical_a2flow={"version": "2.0", "nodes": []},
        plan_hash="a" * 64,
    )
    return run, revision


def debug_session_values(run, revision, **overrides):
    """Build a valid active DebugSession payload."""
    now = timezone.now()
    values = {
        "run": run,
        "revision": revision,
        "template_id": 42,
        "debug_context_id": 84,
        "mode": DebugMode.STEP,
        "status": DebugSessionStatus.ACTIVE,
        "plan_hash": "a" * 64,
        "tree_fingerprint": tree_fingerprint(),
        "actor": "dannydeng",
        "policy_version": "risk-2026.09",
        "trusted_context_snapshot": trusted_context_snapshot(),
        "expires_at": now + timezone.timedelta(minutes=10),
        "last_heartbeat_at": now,
    }
    values.update(overrides)
    return values


def evidence_values(run, revision, session=None, **overrides):
    """Build one valid bounded EvidenceEvent payload."""
    values = {
        "run": run,
        "revision": revision,
        "debug_session": session,
        "event_type": "DEBUG_SESSION_STARTED",
        "action": "start_debug_session",
        "redacted_payload": {"mode": "step"},
        "artifact_refs": [],
        "actor": "dannydeng",
        "correlation_id": "p2-model-test",
        "redaction_version": EVIDENCE_REDACTION_VERSION,
        "occurred_at": timezone.now(),
    }
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_debug_session_derives_mysql_compatible_single_active_template_key(run_and_revision):
    """A normal create derives one nullable unique key per active template."""
    run, revision = run_and_revision
    first = DebugSession.objects.create(**debug_session_values(run, revision, active_template_key="forged"))

    assert first.active_template_key == "template:42"
    assert first.is_active is True
    assert first.is_terminal is False
    with pytest.raises(IntegrityError), transaction.atomic():
        DebugSession.objects.create(**debug_session_values(run, revision, debug_context_id=85))

    first.status = DebugSessionStatus.COMPLETED
    first.terminal_reason = "mock debug completed"
    first.save(update_fields=["status", "terminal_reason"])
    second = DebugSession.objects.create(**debug_session_values(run, revision, debug_context_id=85))

    first.refresh_from_db()
    assert first.active_template_key is None
    assert first.is_terminal is True
    assert second.active_template_key == "template:42"


@pytest.mark.django_db
def test_debug_session_bulk_create_derives_key_and_rejects_all_bulk_mutation(run_and_revision):
    """Validated inserts work while set-based lifecycle and deletion bypasses remain closed."""
    run, revision = run_and_revision
    session = DebugSession(**debug_session_values(run, revision, active_template_key="forged"))

    DebugSession.objects.bulk_create([session])

    assert session.active_template_key == "template:42"
    with pytest.raises(ValidationError):
        DebugSession.objects.filter(pk=session.pk).update(status=DebugSessionStatus.FAILED)
    with pytest.raises(ValidationError):
        DebugSession.objects.bulk_update([session], ["status"])
    with pytest.raises(ValidationError):
        DebugSession._base_manager.filter(pk=session.pk).delete()
    with pytest.raises(ValidationError):
        session.delete()
    with pytest.raises(ValidationError):
        session.hard_delete()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"template_id": 0},
        {"debug_context_id": -1},
        {"plan_hash": "not-a-sha256"},
        {"tree_fingerprint": tree_fingerprint(nodes={"node-1": "token=raw-secret"})},
        {"tree_fingerprint": {"nodes": {}, "flows": "b" * 32}},
        {"actor": "another-user"},
        {"policy_version": "another-policy"},
        {"trusted_context_snapshot": trusted_context_snapshot(space_id=903)},
        {"trusted_context_snapshot": trusted_context_snapshot(resolved_credentials={"token": "raw-secret"})},
        {"expires_at": timezone.now() - timezone.timedelta(seconds=1)},
        {"last_heartbeat_at": timezone.now() + timezone.timedelta(minutes=20)},
        {"terminal_reason": "token=raw-secret"},
    ],
)
def test_debug_session_direct_create_cannot_bypass_identity_hash_time_or_secret_invariants(run_and_revision, overrides):
    """Every ordinary ORM create enforces immutable trusted session facts."""
    run, revision = run_and_revision

    with pytest.raises(ValidationError):
        DebugSession.objects.create(**debug_session_values(run, revision, **overrides))

    assert DebugSession.objects.count() == 0


@pytest.mark.django_db
def test_debug_session_rejects_foreign_revision_and_persisted_identity_mutation(run_and_revision):
    """A session stays bound to its original run, revision, plan, actor, and trusted context."""
    run, revision = run_and_revision
    foreign_run = HarnessRun.objects.create(
        **run_values(actor="other-user", space_id=903, scope=canonical_scope("project", "903"))
    )
    foreign_revision = WorkflowPlanRevision.objects.create(
        run=foreign_run,
        sequence=1,
        intent_spec={},
        canonical_a2flow={},
        plan_hash="c" * 64,
    )
    with pytest.raises(ValidationError):
        DebugSession.objects.create(**debug_session_values(run, foreign_revision))

    session = DebugSession.objects.create(**debug_session_values(run, revision))
    session.actor = "other-user"
    with pytest.raises(ValidationError):
        session.save(update_fields=["actor"])


@pytest.mark.django_db
def test_models_report_missing_required_relations_as_validation_errors(run_and_revision):
    """Incomplete direct model construction fails closed without leaking RelatedObjectDoesNotExist."""
    run, revision = run_and_revision
    session = DebugSession(**debug_session_values(run, revision))
    session.revision = None
    with pytest.raises(ValidationError):
        session.full_clean()

    valid_session = DebugSession.objects.create(**debug_session_values(run, revision))
    lease = TokenLease(
        session=None,
        platform_app="trusted-app",
        actor="dannydeng",
        space_id=902,
        resource_type="TEMPLATE",
        resource_id="42",
        permission="MOCK",
        issuer_ref="issuer://bkflow/platform-app",
        token_fingerprint="c" * 64,
        issued_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(minutes=5),
        status=TokenLease.Status.ACTIVE,
    )
    with pytest.raises(ValidationError):
        lease.full_clean()

    event = EvidenceEvent(**evidence_values(run, revision, valid_session))
    event.run = None
    with pytest.raises(ValidationError):
        event.full_clean()


@pytest.mark.django_db
def test_terminal_session_clears_active_key_and_validates_expired_semantics(run_and_revision):
    """Every terminal state releases the MySQL unique key; EXPIRED means its deadline passed."""
    run, revision = run_and_revision
    for index, status in enumerate(
        (
            DebugSessionStatus.COMPLETED,
            DebugSessionStatus.FAILED,
            DebugSessionStatus.TERMINATED,
        ),
        start=1,
    ):
        session = DebugSession.objects.create(
            **debug_session_values(
                run,
                revision,
                template_id=100 + index,
                debug_context_id=200 + index,
                status=status,
                terminal_reason="terminal state",
                active_template_key="forged",
            )
        )
        assert session.active_template_key is None

    expired = DebugSession.objects.create(
        **debug_session_values(
            run,
            revision,
            template_id=200,
            debug_context_id=300,
            status=DebugSessionStatus.EXPIRED,
            expires_at=timezone.now() - timezone.timedelta(seconds=1),
            last_heartbeat_at=timezone.now() - timezone.timedelta(seconds=2),
            terminal_reason="lease expired",
        )
    )
    assert expired.active_template_key is None


@pytest.mark.django_db
def test_terminal_debug_session_cannot_be_resurrected(run_and_revision):
    """No terminal session can reacquire a template's active key."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(
        **debug_session_values(
            run,
            revision,
            status=DebugSessionStatus.TERMINATED,
            terminal_reason="operator terminated",
        )
    )
    session.status = DebugSessionStatus.ACTIVE
    session.terminal_reason = None

    with pytest.raises(ValidationError):
        session.full_clean()
    with pytest.raises(ValidationError):
        session.save(update_fields=["status", "terminal_reason"])


@pytest.mark.django_db
def test_debug_session_partial_save_rejects_omitted_changed_lifecycle_field(run_and_revision):
    """A partial lifecycle save cannot validate one state but persist another state and active key."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    session.status = DebugSessionStatus.FAILED
    session.terminal_reason = "debug failed"

    with pytest.raises(ValidationError):
        session.save(update_fields=["terminal_reason"])

    session.refresh_from_db()
    assert session.status == DebugSessionStatus.ACTIVE
    assert session.active_template_key == "template:42"


@pytest.mark.django_db
def test_token_lease_persists_metadata_only_and_separates_resource_from_mock_permission(run_and_revision):
    """A lease stores a fingerprint/reference and can represent future resource types without plaintext."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    now = timezone.now()
    lease = TokenLease.objects.create(
        session=session,
        platform_app="trusted-app",
        actor="dannydeng",
        space_id=902,
        resource_type="TEMPLATE",
        resource_id="42",
        permission="MOCK",
        issuer_ref="issuer://bkflow/platform-app",
        token_fingerprint="c" * 64,
        issued_at=now,
        expires_at=now + timezone.timedelta(minutes=5),
        status=TokenLease.Status.ACTIVE,
    )

    field_names = {field.name for field in TokenLease._meta.get_fields()}
    assert lease.resource_type == "TEMPLATE"
    assert lease.permission == "MOCK"
    assert "token" not in field_names
    assert "secret" not in field_names
    assert "plaintext" not in field_names
    assert isinstance(lease.id, uuid.UUID)

    scope_session = DebugSession.objects.create(
        **debug_session_values(run, revision, template_id=43, debug_context_id=85)
    )
    scope_lease = TokenLease.objects.create(
        session=scope_session,
        platform_app="trusted-app",
        actor="dannydeng",
        space_id=902,
        resource_type="SCOPE",
        resource_id="project_902",
        permission="MOCK",
        issuer_ref="issuer://bkflow/platform-app",
        token_fingerprint="d" * 64,
        issued_at=now,
        expires_at=now + timezone.timedelta(minutes=5),
        status=TokenLease.Status.ACTIVE,
    )
    assert scope_lease.resource_type == "SCOPE"
    assert scope_lease.resource_id == "project_902"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"platform_app": "foreign-app"},
        {"actor": "foreign-user"},
        {"space_id": 0},
        {"space_id": 903},
        {"resource_type": "UNKNOWN"},
        {"resource_type": "TASK"},
        {"resource_id": "0"},
        {"resource_type": "SCOPE", "resource_id": "project_903"},
        {"resource_type": "SCOPE", "resource_id": "token=raw-secret"},
        {"permission": "VIEW"},
        {"issuer_ref": "https://user:password@example.com/token"},
        {"token_fingerprint": "not-a-sha256"},
    ],
)
def test_token_lease_direct_create_rejects_untrusted_identity_or_unsafe_metadata(run_and_revision, overrides):
    """A normal create cannot persist a forged identity, authority, issuer, or token representation."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    now = timezone.now()
    values = {
        "session": session,
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": 902,
        "resource_type": "TEMPLATE",
        "resource_id": "42",
        "permission": "MOCK",
        "issuer_ref": "issuer://bkflow/platform-app",
        "token_fingerprint": "c" * 64,
        "issued_at": now,
        "expires_at": now + timezone.timedelta(minutes=5),
        "status": TokenLease.Status.ACTIVE,
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        TokenLease.objects.create(**values)

    assert TokenLease.objects.count() == 0


@pytest.mark.django_db
def test_token_lease_enforces_status_times_and_governed_mutation(run_and_revision):
    """ACTIVE, REVOKED, and EXPIRED leases have coherent timestamps and no bulk bypass."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    now = timezone.now()
    common = {
        "session": session,
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": 902,
        "resource_type": "TEMPLATE",
        "resource_id": "42",
        "permission": "MOCK",
        "issuer_ref": "issuer://bkflow/platform-app",
        "token_fingerprint": "c" * 64,
        "issued_at": now,
        "expires_at": now + timezone.timedelta(minutes=5),
        "status": TokenLease.Status.ACTIVE,
    }
    lease = TokenLease.objects.create(**common)
    lease.status = TokenLease.Status.REVOKED
    lease.revoked_at = timezone.now()
    lease.save(update_fields=["status", "revoked_at"])
    assert lease.status == TokenLease.Status.REVOKED

    with pytest.raises(ValidationError):
        TokenLease.objects.create(**{**common, "token_fingerprint": "d" * 64, "revoked_at": now})
    with pytest.raises(ValidationError):
        TokenLease.objects.create(
            **{
                **common,
                "token_fingerprint": "e" * 64,
                "status": TokenLease.Status.REVOKED,
                "revoked_at": None,
            }
        )
    with pytest.raises(ValidationError):
        TokenLease.objects.create(
            **{
                **common,
                "token_fingerprint": "f" * 64,
                "status": TokenLease.Status.EXPIRED,
                "expires_at": now + timezone.timedelta(minutes=1),
            }
        )
    with pytest.raises(ValidationError):
        TokenLease.objects.filter(pk=lease.pk).update(status=TokenLease.Status.EXPIRED)
    with pytest.raises(ValidationError):
        TokenLease.objects.bulk_update([lease], ["status"])
    with pytest.raises(ValidationError):
        TokenLease._base_manager.filter(pk=lease.pk).delete()
    with pytest.raises(ValidationError):
        lease.delete()
    with pytest.raises(ValidationError):
        lease.hard_delete()


@pytest.mark.django_db
def test_token_lease_cannot_be_active_on_terminal_session_or_resurrected(run_and_revision):
    """Terminal debug authority cannot own a live lease, and terminal leases never become ACTIVE."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    now = timezone.now()
    values = {
        "session": session,
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": 902,
        "resource_type": "TEMPLATE",
        "resource_id": "42",
        "permission": "MOCK",
        "issuer_ref": "issuer://bkflow/platform-app",
        "token_fingerprint": "c" * 64,
        "issued_at": now,
        "expires_at": now + timezone.timedelta(minutes=5),
        "status": TokenLease.Status.ACTIVE,
    }
    lease = TokenLease.objects.create(**values)
    lease.status = TokenLease.Status.REVOKED
    lease.revoked_at = now
    lease.save(update_fields=["status", "revoked_at"])
    lease.status = TokenLease.Status.ACTIVE
    lease.revoked_at = None
    with pytest.raises(ValidationError):
        lease.full_clean()
    with pytest.raises(ValidationError):
        lease.save(update_fields=["status", "revoked_at"])

    session.status = DebugSessionStatus.TERMINATED
    session.terminal_reason = "operator terminated"
    session.save(update_fields=["status", "terminal_reason"])
    with pytest.raises(ValidationError):
        TokenLease.objects.create(**{**values, "token_fingerprint": "d" * 64})


@pytest.mark.django_db
def test_debug_session_requires_active_leases_to_end_before_terminal_transition(run_and_revision):
    """A session cannot release its active key while a live lease still grants debug authority."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    now = timezone.now()
    lease = TokenLease.objects.create(
        session=session,
        platform_app="trusted-app",
        actor="dannydeng",
        space_id=902,
        resource_type="TEMPLATE",
        resource_id="42",
        permission="MOCK",
        issuer_ref="issuer://bkflow/platform-app",
        token_fingerprint="c" * 64,
        issued_at=now,
        expires_at=now + timezone.timedelta(minutes=5),
        status=TokenLease.Status.ACTIVE,
    )
    session.status = DebugSessionStatus.TERMINATED
    session.terminal_reason = "operator terminated"

    with pytest.raises(ValidationError):
        session.save(update_fields=["status", "terminal_reason"])

    lease.status = TokenLease.Status.REVOKED
    lease.revoked_at = timezone.now()
    lease.save(update_fields=["status", "revoked_at"])
    session.save(update_fields=["status", "terminal_reason"])
    assert session.active_template_key is None


@pytest.mark.django_db
def test_active_lease_create_rereads_locked_session_and_bulk_insert_is_closed(run_and_revision):
    """Stale session objects and bulk inserts cannot race a terminal session transition."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    stale_session = DebugSession.objects.get(pk=session.pk)
    session.status = DebugSessionStatus.COMPLETED
    session.terminal_reason = "mock completed"
    session.save(update_fields=["status", "terminal_reason"])
    now = timezone.now()
    values = {
        "session": stale_session,
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": 902,
        "resource_type": "TEMPLATE",
        "resource_id": "42",
        "permission": "MOCK",
        "issuer_ref": "issuer://bkflow/platform-app",
        "token_fingerprint": "c" * 64,
        "issued_at": now,
        "expires_at": now + timezone.timedelta(minutes=5),
        "status": TokenLease.Status.ACTIVE,
    }

    with pytest.raises(ValidationError):
        TokenLease.objects.create(**values)

    active_session = DebugSession.objects.create(
        **debug_session_values(run, revision, template_id=43, debug_context_id=85)
    )
    with pytest.raises(ValidationError):
        TokenLease.objects.bulk_create(
            [TokenLease(**{**values, "session": active_session, "resource_id": "43", "token_fingerprint": "d" * 64})]
        )


@pytest.mark.django_db
def test_scope_lease_requires_exact_trusted_scope_and_rejects_space_wide_session():
    """SCOPE authority is exact and unavailable when the trusted deployment has no scope."""
    run = HarnessRun.objects.create(**run_values(scope=""))
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={},
        canonical_a2flow={},
        plan_hash="a" * 64,
    )
    session = DebugSession.objects.create(
        **debug_session_values(
            run,
            revision,
            trusted_context_snapshot=trusted_context_snapshot(scope_type=None, scope_value=None),
        )
    )
    now = timezone.now()

    with pytest.raises(ValidationError):
        TokenLease.objects.create(
            session=session,
            platform_app="trusted-app",
            actor="dannydeng",
            space_id=902,
            resource_type="SCOPE",
            resource_id="project_902",
            permission="MOCK",
            issuer_ref="issuer://bkflow/platform-app",
            token_fingerprint="c" * 64,
            issued_at=now,
            expires_at=now + timezone.timedelta(minutes=5),
            status=TokenLease.Status.ACTIVE,
        )


@pytest.mark.django_db
def test_evidence_event_is_relation_bound_non_secret_and_truly_append_only(run_and_revision):
    """Evidence allows one safe insert and rejects every instance, queryset, and base-manager mutation."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    event = EvidenceEvent.objects.create(**evidence_values(run, revision, session))

    event.action = "run_debug"
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        EvidenceEvent.objects.filter(pk=event.pk).update(action="run_debug")
    with pytest.raises(ValidationError):
        EvidenceEvent.objects.bulk_update([event], ["action"])
    with pytest.raises(ValidationError):
        EvidenceEvent._base_manager.filter(pk=event.pk).delete()
    with pytest.raises(ValidationError):
        event.delete()
    with pytest.raises(ValidationError):
        event.hard_delete()

    with pytest.raises(ValidationError):
        EvidenceEvent.objects.create(
            **evidence_values(run, revision, session, redacted_payload={"authorization": "Bearer raw-secret"})
        )
    with pytest.raises(ValidationError):
        EvidenceEvent.objects.create(**evidence_values(run, revision, session, redacted_payload={"externalized": True}))


@pytest.mark.django_db
def test_evidence_event_bulk_create_validates_relations_and_safe_payload(run_and_revision):
    """Safe append batching cannot bypass run/revision/session ownership or payload checks."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))
    safe = EvidenceEvent(**evidence_values(run, revision, session))
    EvidenceEvent.objects.bulk_create([safe])
    assert EvidenceEvent.objects.filter(pk=safe.pk).exists()

    foreign_run = HarnessRun.objects.create(
        **run_values(actor="other-user", space_id=903, scope=canonical_scope("project", "903"))
    )
    unsafe = EvidenceEvent(**evidence_values(foreign_run, revision, session, actor="other-user"))
    with pytest.raises(ValidationError):
        EvidenceEvent.objects.bulk_create([unsafe])


@pytest.mark.django_db
def test_session_evidence_correlation_must_match_trusted_snapshot(run_and_revision):
    """Session-bound evidence cannot be attached to a different correlation stream."""
    run, revision = run_and_revision
    session = DebugSession.objects.create(**debug_session_values(run, revision))

    with pytest.raises(ValidationError):
        EvidenceEvent.objects.create(**evidence_values(run, revision, session, correlation_id="another-correlation"))


def test_task2_field_changes_fit_p2_states_and_generated_migration_contract():
    """The schema can persist long P2 checkpoints and the Task2 Harness run status choices."""
    from bkflow.harness.models import ValidationReport

    checkpoint = ValidationReport._meta.get_field("checkpoint")
    run_status = HarnessRun._meta.get_field("status")

    assert checkpoint.max_length >= len(ValidationCheckpoint.START_DEBUG_SESSION)
    assert {value for value, _label in run_status.choices} == set(HarnessRunStatus.values)
