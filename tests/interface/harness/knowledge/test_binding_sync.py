"""Apply-gated and atomic knowledge binding manifest synchronization."""

import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import yaml
from django.core.management import CommandError, call_command
from django.db import close_old_connections, connections, transaction
from django.utils import timezone

from bkflow.harness.constants import KnowledgeBindingStatus, KnowledgeTier
from bkflow.harness.models import KnowledgeSourceBinding
from bkflow.harness.services.knowledge.bindings import (
    DenyAllKnowledgeBindingGovernanceEvidence,
    KnowledgeBindingGovernanceFacts,
    KnowledgeBindingSynchronizer,
    KnowledgeBindingSyncLockError,
    _mysql_named_lock,
)
from bkflow.harness.services.knowledge.providers import (
    FakeKnowledgeProvider,
    KnowledgeProviderRegistry,
)
from bkflow.space.models import Credential, CredentialScopeLevel, CredentialType


class NoSearchKnowledgeProvider:
    """Expose the SPI shape while proving governance never performs provider retrieval."""

    def search(self, binding, query):
        """Fail a test immediately if manifest validation tries to retrieve knowledge."""
        raise AssertionError("governance evidence must not call provider.search")


def manifest_binding(**overrides):
    """Build one non-secret manifest entry for the registered test provider."""
    values = {
        "provider": "fixture-docs",
        "source_ref": "knowledge://workflow-guides/restart-service",
        "tier": "SPACE",
        "platform_key": "bkaidev",
        "space_id": 902,
        "scope_type": None,
        "scope_value": None,
        "trust_level": "VERIFIED",
        "priority": 100,
        "environment": "stag",
        "allowed_apps": ["trusted-app"],
        "allowed_actors": ["trusted-user"],
        "data_classification": "internal",
        "snapshot_version": "2026.09.04",
        "expires_at": None,
        "last_verified_at": "2026-09-01T08:00:00Z",
        "owner": "knowledge-owner",
        "reviewer": "security-reviewer",
        "status": "ACTIVE",
        "retrieval_mode": "HYBRID",
        "max_top_k": 5,
        "redaction_policy": {"policy_ref": "redaction://workflow-guides/v1"},
        "credential_ref": None,
        "provider_config": {"collection": "workflow-guides", "region": "ap-shanghai"},
    }
    values.update(overrides)
    return values


def write_manifest(tmp_path, bindings, version=1, filename="knowledge-bindings.yaml"):
    """Write a small versioned YAML document for the management command."""
    path = tmp_path / filename
    path.write_text(yaml.safe_dump({"version": version, "bindings": bindings}), encoding="utf-8")
    return path


class FakeGovernanceEvidence:
    """Allow only reviewed tier assignments and immutable source snapshots declared by the test."""

    def __init__(self):
        self.authorized_assignments = {
            (
                "knowledge-owner",
                "security-reviewer",
                "SPACE",
                "bkaidev",
                902,
                None,
                None,
            )
        }
        self.existing_snapshots = {
            ("fixture-docs", "knowledge://workflow-guides/restart-service", "2026.09.04"),
            ("fixture-docs", "knowledge://workflow-guides/first", "2026.09.04"),
            ("fixture-docs", "knowledge://workflow-guides/second", "2026.09.04"),
        }
        self.seen_facts = []

    def owner_reviewer_authorized(self, facts):
        """Authorize only the fixture's exact owner/reviewer and trusted tier dimensions."""
        assert isinstance(facts, KnowledgeBindingGovernanceFacts)
        self.seen_facts.append(facts)
        return (
            facts.owner,
            facts.reviewer,
            facts.tier,
            facts.platform_key,
            facts.space_id,
            facts.scope_type,
            facts.scope_value,
        ) in self.authorized_assignments

    def source_snapshot_exists(self, facts):
        """Confirm an immutable provider/source/snapshot tuple without provider retrieval."""
        return (facts.provider, facts.source_ref, facts.snapshot_version) in self.existing_snapshots


@pytest.fixture
def governance_setup(monkeypatch):
    """Inject explicit provider and governance evidence without enabling a production adapter."""
    registry = KnowledgeProviderRegistry({"fixture-docs": NoSearchKnowledgeProvider()})
    evidence = FakeGovernanceEvidence()
    monkeypatch.setattr(
        "bkflow.harness.management.commands.sync_knowledge_bindings.production_provider_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "bkflow.harness.management.commands.sync_knowledge_bindings.production_governance_evidence",
        lambda: evidence,
    )
    yield registry, evidence
    registry.close()


@pytest.mark.django_db(transaction=True)
def test_default_mode_prints_diff_and_performs_no_writes(tmp_path, governance_setup):
    """Make a manifest invocation a safe dry run unless --apply is explicit."""
    path = write_manifest(tmp_path, [manifest_binding(provider_config={"collection": "do-not-print"})])
    stdout = io.StringIO()

    call_command("sync_knowledge_bindings", str(path), stdout=stdout)

    output = stdout.getvalue()
    assert KnowledgeSourceBinding.objects.count() == 0
    assert "mode=dry-run" in output
    assert "create=1" in output
    assert "update=0" in output
    assert "retire=0" in output
    assert "do-not-print" not in output
    assert "restart-service" not in output


@pytest.mark.django_db(transaction=True)
def test_apply_creates_updates_and_retires_without_deleting_history(tmp_path, governance_setup):
    """Apply complete desired state and retain an omitted binding as retired evidence."""
    create_path = write_manifest(tmp_path, [manifest_binding()])
    create_stdout = io.StringIO()
    call_command("sync_knowledge_bindings", str(create_path), "--apply", stdout=create_stdout)
    binding = KnowledgeSourceBinding.objects.get()
    assert "mode=apply" in create_stdout.getvalue()
    assert "create=1" in create_stdout.getvalue()
    assert "created_ids={}".format(binding.id) in create_stdout.getvalue()

    update_path = write_manifest(tmp_path, [manifest_binding(id=binding.id, priority=250)])
    update_stdout = io.StringIO()
    call_command("sync_knowledge_bindings", str(update_path), "--apply", stdout=update_stdout)
    binding.refresh_from_db()
    assert binding.priority == 250
    assert "update=1" in update_stdout.getvalue()
    assert "updated_ids={}".format(binding.id) in update_stdout.getvalue()

    retire_path = write_manifest(tmp_path, [])
    retire_stdout = io.StringIO()
    call_command("sync_knowledge_bindings", str(retire_path), "--apply", stdout=retire_stdout)
    binding.refresh_from_db()
    assert binding.status == KnowledgeBindingStatus.RETIRED
    assert KnowledgeSourceBinding.objects.filter(pk=binding.pk).exists()
    assert "retire=1" in retire_stdout.getvalue()
    assert "retired_ids={}".format(binding.id) in retire_stdout.getvalue()


@pytest.mark.django_db(transaction=True)
def test_invalid_manifest_is_fully_validated_before_any_write(tmp_path, governance_setup):
    """Do not partially create or retire rows when any desired entry is invalid."""
    current = KnowledgeSourceBinding.objects.create(
        **{
            key: value
            for key, value in manifest_binding().items()
            if key not in {"id", "expires_at", "last_verified_at"}
        },
        last_verified_at=timezone.now(),
    )
    path = write_manifest(
        tmp_path,
        [
            manifest_binding(id=current.id, priority=200),
            manifest_binding(
                source_ref="knowledge://workflow-guides/invalid",
                provider="unregistered-provider",
            ),
        ],
    )

    with pytest.raises(CommandError, match="KNOWLEDGE_BINDING_MANIFEST_INVALID"):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    current.refresh_from_db()
    assert current.priority == 100
    assert current.status == KnowledgeBindingStatus.ACTIVE
    assert KnowledgeSourceBinding.objects.count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "overrides",
    [
        {"owner": ""},
        {"reviewer": ""},
        {"reviewer": "knowledge-owner"},
        {"owner": "arbitrary-owner", "reviewer": "arbitrary-reviewer"},
        {"snapshot_version": ""},
        {"snapshot_version": "does-not-exist"},
        {"last_verified_at": None},
        {"tier": KnowledgeTier.GLOBAL.value, "platform_key": "bkaidev", "space_id": None},
        {"provider": "unregistered-provider"},
        {"credential_ref": "credential://id/999999"},
    ],
)
def test_governance_validation_rejects_unreviewed_or_unresolvable_entries(tmp_path, governance_setup, overrides):
    """Reject missing governance, invalid dimensions, providers, snapshots or credentials."""
    path = write_manifest(tmp_path, [manifest_binding(**overrides)])

    with pytest.raises(CommandError, match="KNOWLEDGE_BINDING_MANIFEST_INVALID"):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "overrides",
    [
        {"source_ref": "knowledge://workflow-guides/restart?token=manifest-secret"},
        {"snapshot_version": "Bearer manifest-snapshot-secret"},
        {"redaction_policy": {"policy_ref": "credential://id/42"}},
        {"provider_config": {"collection": "api_token=manifest-provider-secret"}},
    ],
)
def test_manifest_rejects_secret_shaped_binding_metadata_before_writes(tmp_path, governance_setup, overrides):
    """The controlled synchronizer must not become a bypass around model non-secret validation."""
    path = write_manifest(tmp_path, [manifest_binding(**overrides)])

    with pytest.raises(CommandError, match="KNOWLEDGE_BINDING_MANIFEST_INVALID"):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_unknown_fields_and_secret_shaped_provider_config_are_rejected_without_echo(tmp_path, governance_setup):
    """Keep the manifest schema positive and avoid reflecting sensitive values in errors."""
    path = write_manifest(
        tmp_path,
        [manifest_binding(provider_config={"api_token": "very-secret"}, unexpected="must-not-appear")],
    )
    stderr = io.StringIO()

    with pytest.raises(CommandError) as error:
        call_command("sync_knowledge_bindings", str(path), "--apply", stderr=stderr)

    assert str(error.value) == "KNOWLEDGE_BINDING_MANIFEST_INVALID"
    assert "very-secret" not in stderr.getvalue()
    assert "must-not-appear" not in stderr.getvalue()
    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_unsupported_manifest_version_fails_closed(tmp_path, governance_setup):
    """Reject undeclared future schemas instead of guessing their meaning."""
    path = write_manifest(tmp_path, [manifest_binding()], version=2)

    with pytest.raises(CommandError, match="KNOWLEDGE_BINDING_MANIFEST_INVALID"):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_existing_space_credential_reference_is_validated_without_resolving_secret(tmp_path, governance_setup):
    """Accept an existing governed credential reference while keeping its content outside the manifest path."""
    credential = Credential.objects.create(
        space_id=902,
        name="knowledge-reader",
        type=CredentialType.CUSTOM.value,
        scope_level=CredentialScopeLevel.ALL.value,
        content=None,
    )
    path = write_manifest(tmp_path, [manifest_binding(credential_ref="credential://id/{}".format(credential.id))])

    call_command("sync_knowledge_bindings", str(path), "--apply")

    binding = KnowledgeSourceBinding.objects.get()
    assert binding.credential_ref == "credential://id/{}".format(credential.id)


@pytest.mark.django_db(transaction=True)
def test_duplicate_active_identity_is_rejected_before_any_manifest_write(tmp_path, governance_setup):
    """Reject two desired active rows for one source identity with a generic safe error."""
    duplicate = manifest_binding()
    path = write_manifest(tmp_path, [manifest_binding(), duplicate])

    with pytest.raises(CommandError, match="KNOWLEDGE_BINDING_MANIFEST_INVALID"):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_reapplying_the_same_manifest_is_idempotent(tmp_path, governance_setup):
    """Report no update when the stored row already equals the complete desired entry."""
    create_path = write_manifest(tmp_path, [manifest_binding()])
    call_command("sync_knowledge_bindings", str(create_path), "--apply")
    binding = KnowledgeSourceBinding.objects.get()
    same_path = write_manifest(tmp_path, [manifest_binding(id=binding.id)])
    stdout = io.StringIO()

    call_command("sync_knowledge_bindings", str(same_path), "--apply", stdout=stdout)

    assert "create=0" in stdout.getvalue()
    assert "update=0" in stdout.getvalue()
    assert "retire=0" in stdout.getvalue()


@pytest.mark.django_db(transaction=True)
def test_apply_rolls_back_all_rows_when_a_write_fails(tmp_path, governance_setup, monkeypatch):
    """Keep apply atomic even if a database write fails after an earlier create."""
    first = manifest_binding(source_ref="knowledge://workflow-guides/first")
    second = manifest_binding(source_ref="knowledge://workflow-guides/second")
    path = write_manifest(tmp_path, [first, second])
    original_save = KnowledgeSourceBinding.save

    def fail_second_save(binding, *args, **kwargs):
        if binding.source_ref.endswith("/second"):
            raise RuntimeError("synthetic write failure")
        return original_save(binding, *args, **kwargs)

    monkeypatch.setattr(KnowledgeSourceBinding, "save", fail_second_save)

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_governance_evidence_receives_only_bounded_non_secret_reference_facts(tmp_path, governance_setup):
    """Do not pass provider configuration or credentials into the governance evidence boundary."""
    _registry, evidence = governance_setup
    path = write_manifest(tmp_path, [manifest_binding()])

    call_command("sync_knowledge_bindings", str(path))

    assert len(evidence.seen_facts) == 1
    facts = evidence.seen_facts[0]
    assert not hasattr(facts, "provider_config")
    assert not hasattr(facts, "credential_ref")


@pytest.mark.django_db(transaction=True)
def test_governance_evidence_failure_is_non_reflective_and_writes_nothing(tmp_path, governance_setup, monkeypatch):
    """Normalize an evidence backend exception without exposing its payload or partially applying state."""
    registry, _evidence = governance_setup

    class FailedEvidence:
        def owner_reviewer_authorized(self, facts):
            raise RuntimeError("external-secret-marker")

        def source_snapshot_exists(self, facts):
            raise RuntimeError("external-secret-marker")

    monkeypatch.setattr(
        "bkflow.harness.management.commands.sync_knowledge_bindings.production_provider_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "bkflow.harness.management.commands.sync_knowledge_bindings.production_governance_evidence",
        FailedEvidence,
    )
    path = write_manifest(tmp_path, [manifest_binding()])

    with pytest.raises(CommandError) as error:
        call_command("sync_knowledge_bindings", str(path), "--apply")

    assert str(error.value) == "KNOWLEDGE_BINDING_MANIFEST_INVALID"
    assert "external-secret-marker" not in str(error.value)
    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_provider_spi_only_production_governance_defaults_to_deny_all(tmp_path, monkeypatch):
    """Never promote manifest assertions to verified evidence without an injected governance source."""
    assert not DenyAllKnowledgeBindingGovernanceEvidence().owner_reviewer_authorized(
        KnowledgeBindingGovernanceFacts(
            owner="knowledge-owner",
            reviewer="security-reviewer",
            tier="SPACE",
            platform_key="bkaidev",
            space_id=902,
            scope_type=None,
            scope_value=None,
            provider="fixture-docs",
            source_ref="knowledge://workflow-guides/restart-service",
            snapshot_version="2026.09.04",
        )
    )
    registry = KnowledgeProviderRegistry({"fixture-docs": FakeKnowledgeProvider([])})
    monkeypatch.setattr(
        "bkflow.harness.management.commands.sync_knowledge_bindings.production_provider_registry",
        lambda: registry,
    )
    path = write_manifest(tmp_path, [manifest_binding()])

    with pytest.raises(CommandError, match="KNOWLEDGE_BINDING_MANIFEST_INVALID"):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    assert KnowledgeSourceBinding.objects.count() == 0
    registry.close()


@pytest.mark.django_db(transaction=True)
def test_deny_all_production_governance_cannot_retire_existing_binding(tmp_path, monkeypatch):
    """Treat omission as a governed mutation instead of allowing an unsigned empty manifest to retire all rows."""
    existing = KnowledgeSourceBinding.objects.create(**manifest_binding())
    registry = KnowledgeProviderRegistry({"fixture-docs": FakeKnowledgeProvider([])})
    monkeypatch.setattr(
        "bkflow.harness.management.commands.sync_knowledge_bindings.production_provider_registry",
        lambda: registry,
    )
    path = write_manifest(tmp_path, [])

    with pytest.raises(CommandError, match="KNOWLEDGE_BINDING_MANIFEST_INVALID"):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    existing.refresh_from_db()
    assert existing.status == KnowledgeBindingStatus.ACTIVE
    registry.close()


@pytest.mark.django_db(transaction=True)
def test_concurrent_complete_manifests_from_empty_state_never_merge():
    """Serialize A-versus-B complete manifests so the final active state equals exactly one desired set."""
    registry = KnowledgeProviderRegistry({"fixture-docs": FakeKnowledgeProvider([])})
    evidence = FakeGovernanceEvidence()
    synchronizer = KnowledgeBindingSynchronizer(registry, evidence)
    barrier = Barrier(2)
    document_a = {"version": 1, "bindings": [manifest_binding(source_ref="knowledge://workflow-guides/first")]}
    document_b = {"version": 1, "bindings": [manifest_binding(source_ref="knowledge://workflow-guides/second")]}

    def apply(document):
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            return synchronizer.apply(document)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(apply, document_a), executor.submit(apply, document_b)]
        for future in futures:
            future.result(timeout=10)

    active_refs = frozenset(
        KnowledgeSourceBinding.objects.filter(status=KnowledgeBindingStatus.ACTIVE).values_list("source_ref", flat=True)
    )
    assert active_refs in {
        frozenset({"knowledge://workflow-guides/first"}),
        frozenset({"knowledge://workflow-guides/second"}),
    }
    assert KnowledgeSourceBinding.objects.filter(status=KnowledgeBindingStatus.RETIRED).count() == 1
    registry.close()


@pytest.mark.django_db(transaction=True)
def test_unknown_database_vendor_fails_closed_before_write(tmp_path, governance_setup, monkeypatch):
    """Refuse apply when no synchronization primitive is defined for the active database."""
    database = connections["default"]
    monkeypatch.setattr(database, "vendor", "unknown")
    path = write_manifest(tmp_path, [manifest_binding()])

    with pytest.raises(CommandError, match=KnowledgeBindingSyncLockError.code):
        call_command("sync_knowledge_bindings", str(path), "--apply")

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(connections["default"].vendor != "sqlite", reason="SQLite 专用的事务外锁范围验证")
def test_sqlite_apply_inside_outer_atomic_fails_before_lock_or_write(tmp_path, governance_setup):
    """Reject SQLite synchronization when its process lock cannot cover the caller's outer transaction."""
    assert connections["default"].vendor == "sqlite"
    path = write_manifest(tmp_path, [manifest_binding()])

    with transaction.atomic():
        assert connections["default"].in_atomic_block
        with pytest.raises(CommandError, match=KnowledgeBindingSyncLockError.code):
            call_command("sync_knowledge_bindings", str(path), "--apply")
        assert KnowledgeSourceBinding.objects.count() == 0

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_mysql_apply_inside_outer_atomic_fails_before_named_lock(tmp_path, governance_setup, monkeypatch):
    """Reject nested MySQL synchronization before GET_LOCK and before any desired-state write."""
    registry, evidence = governance_setup
    synchronizer = KnowledgeBindingSynchronizer(registry, evidence)
    document = {"version": 1, "bindings": [manifest_binding()]}
    database = connections["default"]

    class ForbiddenNamedLock:
        def __enter__(self):
            raise AssertionError("GET_LOCK must not run inside an outer transaction")

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(
        "bkflow.harness.services.knowledge.bindings._mysql_named_lock",
        lambda _database: ForbiddenNamedLock(),
    )

    with transaction.atomic():
        original_vendor = database.vendor
        database.vendor = "mysql"
        try:
            with pytest.raises(KnowledgeBindingSyncLockError):
                synchronizer.apply(document)
        finally:
            database.vendor = original_vendor
        assert KnowledgeSourceBinding.objects.count() == 0

    assert KnowledgeSourceBinding.objects.count() == 0


def test_mysql_named_lock_is_released_when_synchronization_body_fails():
    """Always issue RELEASE_LOCK after a successful MySQL GET_LOCK, including exceptional exits."""
    statements = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            statements.append((statement, params))

        def fetchone(self):
            return (1,)

    class Database:
        def cursor(self):
            return Cursor()

        def close(self):
            raise AssertionError("successful release must not close the connection")

    with pytest.raises(RuntimeError, match="body failed"):
        with _mysql_named_lock(Database()):
            raise RuntimeError("body failed")

    assert statements[0][0].startswith("SELECT GET_LOCK")
    assert statements[-1][0].startswith("SELECT RELEASE_LOCK")


def test_mysql_named_lock_fails_closed_when_get_lock_is_not_acquired():
    """Do not enter synchronization when MySQL reports a busy or unavailable advisory lock."""
    statements = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            statements.append((statement, params))

        def fetchone(self):
            return (0,)

    class Database:
        def cursor(self):
            return Cursor()

    with pytest.raises(KnowledgeBindingSyncLockError):
        with _mysql_named_lock(Database()):
            raise AssertionError("unacquired lock must not enter the body")

    assert len(statements) == 1
    assert statements[0][0].startswith("SELECT GET_LOCK")
