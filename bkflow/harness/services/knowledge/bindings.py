"""Versioned, apply-gated governance for knowledge source bindings."""

import copy
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Optional, Protocol

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connections, router, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from bkflow.harness.constants import (
    KnowledgeBindingStatus,
    KnowledgeTier,
    KnowledgeTrustLevel,
)
from bkflow.harness.models import KnowledgeSourceBinding
from bkflow.space.models import Credential

MANIFEST_VERSION = 1
MAX_MANIFEST_BINDINGS = 1000
MYSQL_SYNC_LOCK_NAME = "bkflow:harness:knowledge-binding-sync:v1"
MYSQL_SYNC_LOCK_TIMEOUT_SECONDS = 10
POSTGRES_SYNC_LOCK_ID = 0x424B464C4F575031
_CREDENTIAL_REF = re.compile(r"^credential://id/([1-9][0-9]{0,18})$")
_SQLITE_SYNC_LOCK = Lock()
_BINDING_FIELDS = (
    "provider",
    "source_ref",
    "tier",
    "platform_key",
    "space_id",
    "scope_type",
    "scope_value",
    "trust_level",
    "priority",
    "environment",
    "allowed_apps",
    "allowed_actors",
    "data_classification",
    "snapshot_version",
    "expires_at",
    "last_verified_at",
    "owner",
    "reviewer",
    "status",
    "retrieval_mode",
    "max_top_k",
    "redaction_policy",
    "credential_ref",
    "provider_config",
)
_ENTRY_FIELDS = set(_BINDING_FIELDS) | {"id"}
_DATETIME_FIELDS = {"expires_at", "last_verified_at"}


class KnowledgeBindingManifestError(ValueError):
    """Represent a non-reflective failure in an untrusted binding manifest."""

    code = "KNOWLEDGE_BINDING_MANIFEST_INVALID"

    def __init__(self):
        super().__init__(self.code)


class KnowledgeBindingSyncLockError(RuntimeError):
    """Represent inability to serialize complete desired-state synchronization."""

    code = "KNOWLEDGE_BINDING_SYNC_UNAVAILABLE"

    def __init__(self):
        super().__init__(self.code)


@dataclass(frozen=True)
class KnowledgeBindingGovernanceFacts:
    """Bounded, non-secret facts that an external governance evidence source may inspect."""

    owner: str
    reviewer: str
    tier: str
    platform_key: Optional[str]
    space_id: Optional[int]
    scope_type: Optional[str]
    scope_value: Optional[str]
    provider: str
    source_ref: str
    snapshot_version: str


class KnowledgeBindingGovernanceEvidence(Protocol):
    """Evidence boundary for tier ownership and immutable provider snapshot existence."""

    def owner_reviewer_authorized(self, facts: KnowledgeBindingGovernanceFacts) -> bool:
        """Return whether this reviewed owner assignment governs the exact tier dimensions."""

    def source_snapshot_exists(self, facts: KnowledgeBindingGovernanceFacts) -> bool:
        """Return whether provider/source/snapshot identifies an existing immutable source version."""


class DenyAllKnowledgeBindingGovernanceEvidence:
    """Production-safe default while provider SPI has no authenticated evidence integration."""

    def owner_reviewer_authorized(self, facts):
        """Reject manifest self-asserted ownership."""
        return False

    def source_snapshot_exists(self, facts):
        """Reject manifest self-asserted source snapshots."""
        return False


@dataclass(frozen=True)
class BindingSyncPlan:
    """A fully validated desired-state diff containing no resolved credential data."""

    creates: tuple
    updates: tuple
    retires: tuple


@dataclass(frozen=True)
class BindingSyncResult:
    """Safe counts and database identifiers emitted by the management command."""

    created_ids: tuple
    updated_ids: tuple
    retired_ids: tuple


def _invalid():
    raise KnowledgeBindingManifestError()


@contextmanager
def _mysql_named_lock(database):
    """Hold one MySQL server advisory lock across the complete synchronization transaction."""
    acquired = False
    try:
        try:
            with database.cursor() as cursor:
                cursor.execute(
                    "SELECT GET_LOCK(%s, %s)",
                    [MYSQL_SYNC_LOCK_NAME, MYSQL_SYNC_LOCK_TIMEOUT_SECONDS],
                )
                acquired = cursor.fetchone() == (1,)
        except DatabaseError:
            raise KnowledgeBindingSyncLockError()
        if not acquired:
            raise KnowledgeBindingSyncLockError()
        yield
    finally:
        if acquired:
            try:
                with database.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", [MYSQL_SYNC_LOCK_NAME])
                    released = cursor.fetchone() == (1,)
                if not released:
                    database.close()
            except DatabaseError:
                # Closing a MySQL connection releases all of its named locks.
                try:
                    database.close()
                except Exception:
                    pass


@contextmanager
def _synchronized_atomic(using):
    """Serialize one complete manifest using the active database's supported primitive."""
    database = connections[using]
    if database.vendor in {"mysql", "sqlite"} and database.in_atomic_block:
        # These locks are not transaction-scoped. Releasing them at this nested block's exit would precede
        # the caller's real commit/rollback and reopen the complete-manifest lost-update race.
        raise KnowledgeBindingSyncLockError()
    if database.vendor == "mysql":
        with _mysql_named_lock(database):
            with transaction.atomic(using=using):
                yield
        return
    if database.vendor == "postgresql":
        with transaction.atomic(using=using):
            try:
                with database.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [POSTGRES_SYNC_LOCK_ID])
            except DatabaseError:
                raise KnowledgeBindingSyncLockError()
            yield
        return
    if database.vendor == "sqlite":
        acquired = _SQLITE_SYNC_LOCK.acquire(timeout=MYSQL_SYNC_LOCK_TIMEOUT_SECONDS)
        if not acquired:
            raise KnowledgeBindingSyncLockError()
        try:
            with transaction.atomic(using=using):
                yield
        finally:
            _SQLITE_SYNC_LOCK.release()
        return
    raise KnowledgeBindingSyncLockError()


def _normalize_datetime(value):
    """Parse an ISO-8601 timestamp and normalize it to an aware datetime."""
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else parse_datetime(value) if isinstance(value, str) else None
    if parsed is None:
        _invalid()
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.utc)
    return parsed


def normalize_manifest(document):
    """Validate the positive versioned document shape before any database lookup or write."""
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "bindings"}
        or isinstance(document.get("version"), bool)
        or document.get("version") != MANIFEST_VERSION
        or not isinstance(document.get("bindings"), list)
        or len(document["bindings"]) > MAX_MANIFEST_BINDINGS
    ):
        _invalid()

    normalized = []
    seen_ids = set()
    for raw_entry in document["bindings"]:
        if (
            not isinstance(raw_entry, dict)
            or set(raw_entry) - _ENTRY_FIELDS
            or not set(_BINDING_FIELDS).issubset(raw_entry)
        ):
            _invalid()
        entry = dict(raw_entry)
        binding_id = entry.pop("id", None)
        if binding_id is not None:
            if (
                isinstance(binding_id, bool)
                or not isinstance(binding_id, int)
                or binding_id <= 0
                or binding_id in seen_ids
            ):
                _invalid()
            seen_ids.add(binding_id)
        for field_name in _DATETIME_FIELDS:
            entry[field_name] = _normalize_datetime(entry[field_name])
        normalized.append((binding_id, entry))
    return tuple(normalized)


def _candidate(existing, values):
    """Clone an existing row or build a new row without mutating database-backed instances."""
    candidate = copy.copy(existing) if existing is not None else KnowledgeSourceBinding()
    for field_name, value in values.items():
        setattr(candidate, field_name, value)
    if existing is not None:
        candidate._state.adding = False
    return candidate


def _credential_exists_for_binding(binding, using):
    """Verify a canonical reference against the binding's governed space and scope."""
    if binding.credential_ref is None:
        return True
    match = _CREDENTIAL_REF.fullmatch(binding.credential_ref) if isinstance(binding.credential_ref, str) else None
    if match is None or binding.space_id is None:
        return False
    credential = (
        Credential.objects.using(using)
        .filter(
            id=int(match.group(1)),
            space_id=binding.space_id,
            is_deleted=False,
        )
        .first()
    )
    if credential is None:
        return False
    if binding.tier == KnowledgeTier.SCOPE:
        return credential.can_use_in_scope(binding.scope_type, binding.scope_value)
    return credential.can_use_in_scope(None, None)


def _governance_facts(binding):
    """Project a validated binding into the minimal evidence lookup contract."""
    return KnowledgeBindingGovernanceFacts(
        owner=binding.owner,
        reviewer=binding.reviewer,
        tier=binding.tier,
        platform_key=binding.platform_key,
        space_id=binding.space_id,
        scope_type=binding.scope_type,
        scope_value=binding.scope_value,
        provider=binding.provider,
        source_ref=binding.source_ref,
        snapshot_version=binding.snapshot_version,
    )


def _governance_evidence_exists(binding, governance_evidence):
    """Fail closed on missing, negative or exceptional external governance evidence."""
    facts = _governance_facts(binding)
    try:
        owner_authorized = governance_evidence.owner_reviewer_authorized(facts)
        snapshot_exists = governance_evidence.source_snapshot_exists(facts)
    except Exception:
        return False
    return owner_authorized is True and snapshot_exists is True


def _retirement_governance_exists(binding, governance_evidence):
    """Require current owner/reviewer tier authority before retiring an omitted binding."""
    try:
        return governance_evidence.owner_reviewer_authorized(_governance_facts(binding)) is True
    except Exception:
        return False


def _validate_candidate(binding, provider_registry, governance_evidence, using):
    """Validate governance, dimensions and external references without resolving secrets."""
    if (
        not isinstance(binding.owner, str)
        or not binding.owner
        or not isinstance(binding.reviewer, str)
        or not binding.reviewer
        or binding.owner == binding.reviewer
        or not isinstance(binding.snapshot_version, str)
        or not binding.snapshot_version
        or (
            binding.trust_level in {KnowledgeTrustLevel.VERIFIED, KnowledgeTrustLevel.TRUSTED}
            and binding.last_verified_at is None
        )
    ):
        _invalid()
    try:
        binding.full_clean()
    except ValidationError:
        _invalid()
    if (
        not provider_registry.is_registered(binding.provider)
        or not _credential_exists_for_binding(binding, using)
        or not _governance_evidence_exists(binding, governance_evidence)
    ):
        _invalid()


def _changed(existing, candidate):
    """Compare only manifest-controlled fields after Django normalization."""
    return any(getattr(existing, field_name) != getattr(candidate, field_name) for field_name in _BINDING_FIELDS)


def _build_plan(entries, provider_registry, governance_evidence, existing_rows, using):
    """Validate every desired row before constructing the complete create/update/retire diff."""
    existing_by_id = {binding.id: binding for binding in existing_rows}
    included_ids = set()
    active_identities = set()
    creates = []
    updates = []
    for binding_id, values in entries:
        existing = existing_by_id.get(binding_id) if binding_id is not None else None
        if binding_id is not None and existing is None:
            _invalid()
        candidate = _candidate(existing, values)
        _validate_candidate(candidate, provider_registry, governance_evidence, using)
        if candidate.active_identity is not None:
            if candidate.active_identity in active_identities:
                _invalid()
            active_identities.add(candidate.active_identity)
        if existing is None:
            creates.append(candidate)
        else:
            included_ids.add(existing.id)
            if _changed(existing, candidate):
                updates.append((existing, candidate))

    retires = [
        binding
        for binding in existing_rows
        if binding.id not in included_ids and binding.status != KnowledgeBindingStatus.RETIRED
    ]
    if any(not _retirement_governance_exists(binding, governance_evidence) for binding in retires):
        _invalid()
    return BindingSyncPlan(tuple(creates), tuple(updates), tuple(retires))


class KnowledgeBindingSynchronizer:
    """Compute and atomically apply one complete binding desired state."""

    def __init__(self, provider_registry, governance_evidence, using=None):
        self.provider_registry = provider_registry
        self.governance_evidence = governance_evidence
        self.using = using or router.db_for_write(KnowledgeSourceBinding)

    def plan(self, document):
        """Return a validated dry-run diff without modifying bindings."""
        entries = normalize_manifest(document)
        existing_rows = tuple(KnowledgeSourceBinding.objects.using(self.using).filter(is_deleted=False).order_by("id"))
        return _build_plan(entries, self.provider_registry, self.governance_evidence, existing_rows, self.using)

    def apply(self, document):
        """Re-plan under a database lock and apply only after all candidates validate."""
        entries = normalize_manifest(document)
        with _synchronized_atomic(self.using):
            existing_rows = tuple(
                KnowledgeSourceBinding.objects.using(self.using)
                .select_for_update()
                .filter(is_deleted=False)
                .order_by("id")
            )
            plan = _build_plan(
                entries,
                self.provider_registry,
                self.governance_evidence,
                existing_rows,
                self.using,
            )

            created_ids = []
            for candidate in plan.creates:
                candidate.save(using=self.using)
                created_ids.append(candidate.id)

            updated_ids = []
            for existing, candidate in plan.updates:
                for field_name in _BINDING_FIELDS:
                    setattr(existing, field_name, getattr(candidate, field_name))
                existing.save(using=self.using)
                updated_ids.append(existing.id)

            retired_ids = []
            for binding in plan.retires:
                binding.status = KnowledgeBindingStatus.RETIRED
                binding.save(using=self.using, update_fields=["status"])
                retired_ids.append(binding.id)

        return BindingSyncResult(tuple(created_ids), tuple(updated_ids), tuple(retired_ids))
