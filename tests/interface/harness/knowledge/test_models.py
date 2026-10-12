"""Knowledge binding and retrieval audit persistence contracts."""

import hashlib
import json

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from bkflow.harness.admin import (
    KnowledgeRetrievalAuditAdmin,
    KnowledgeSourceBindingAdmin,
)
from bkflow.harness.constants import (
    KnowledgeBindingStatus,
    KnowledgeRetrievalMode,
    KnowledgeTier,
    KnowledgeTrustLevel,
)
from bkflow.harness.models import (
    HarnessRun,
    KnowledgeRetrievalAudit,
    KnowledgeSourceBinding,
)


def binding_values(**overrides):
    """Build one complete binding payload with independently chosen values."""
    values = {
        "provider": "bk-docs",
        "source_ref": "knowledge://workflow-guides/restart-service",
        "tier": KnowledgeTier.SCOPE,
        "platform_key": "bkaidev",
        "space_id": 902,
        "scope_type": "project",
        "scope_value": "902",
        "trust_level": KnowledgeTrustLevel.VERIFIED,
        "priority": 100,
        "environment": "stag",
        "allowed_apps": ["trusted-app"],
        "allowed_actors": ["dannydeng"],
        "data_classification": "internal",
        "snapshot_version": "2026.09.04",
        "last_verified_at": timezone.now(),
        "owner": "knowledge-owner",
        "reviewer": "security-reviewer",
        "status": KnowledgeBindingStatus.ACTIVE,
        "retrieval_mode": KnowledgeRetrievalMode.HYBRID,
        "max_top_k": 8,
        "redaction_policy": {"policy_ref": "redaction://workflow-guides/v1"},
        "credential_ref": "credential://id/42",
        "provider_config": {"collection": "workflow-guides", "region": "ap-shanghai"},
    }
    values.update(overrides)
    return values


def expected_active_identity(**overrides):
    """Calculate the persisted active identity from literal contract fields."""
    values = binding_values(**overrides)
    payload = json.dumps(
        [
            values["provider"],
            values["source_ref"],
            values["platform_key"],
            int(values["space_id"]) if values["space_id"] is not None else None,
            values["scope_type"],
            values["scope_value"],
            values["environment"],
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


VALID_TIER_DIMENSIONS = [
    (KnowledgeTier.GLOBAL, None, None, None, None),
    (KnowledgeTier.PUBLIC, None, None, None, None),
    (KnowledgeTier.PLATFORM, "bkaidev", None, None, None),
    (KnowledgeTier.SPACE, "bkaidev", 902, None, None),
    (KnowledgeTier.SCOPE, "bkaidev", 902, "project", "902"),
]


INVALID_TIER_DIMENSIONS = [
    (KnowledgeTier.GLOBAL, "bkaidev", None, None, None),
    (KnowledgeTier.PUBLIC, None, 902, None, None),
    (KnowledgeTier.PLATFORM, None, None, None, None),
    (KnowledgeTier.PLATFORM, "bkaidev", 902, None, None),
    (KnowledgeTier.SPACE, "bkaidev", None, None, None),
    (KnowledgeTier.SPACE, "bkaidev", 902, "project", None),
    (KnowledgeTier.SCOPE, "bkaidev", 902, "project", None),
]


@pytest.mark.django_db
@pytest.mark.parametrize("tier,platform_key,space_id,scope_type,scope_value", VALID_TIER_DIMENSIONS)
def test_binding_accepts_only_complete_dimensions_for_each_tier(tier, platform_key, space_id, scope_type, scope_value):
    """Accept each tier when exactly its trusted identity dimensions are present."""
    binding = KnowledgeSourceBinding(
        **binding_values(
            tier=tier,
            platform_key=platform_key,
            space_id=space_id,
            scope_type=scope_type,
            scope_value=scope_value,
        )
    )

    binding.full_clean()
    binding.save()

    assert KnowledgeSourceBinding.objects.get(pk=binding.pk).tier == tier


@pytest.mark.django_db
@pytest.mark.parametrize("tier,platform_key,space_id,scope_type,scope_value", INVALID_TIER_DIMENSIONS)
def test_binding_clean_rejects_missing_or_excess_tier_dimensions(tier, platform_key, space_id, scope_type, scope_value):
    """Reject a binding whose dimensions do not exactly match its tier."""
    binding = KnowledgeSourceBinding(
        **binding_values(
            tier=tier,
            platform_key=platform_key,
            space_id=space_id,
            scope_type=scope_type,
            scope_value=scope_value,
        )
    )

    with pytest.raises(ValidationError):
        binding.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize("tier,platform_key,space_id,scope_type,scope_value", INVALID_TIER_DIMENSIONS)
def test_database_rejects_missing_or_excess_tier_dimensions(tier, platform_key, space_id, scope_type, scope_value):
    """Keep the tier matrix enforced when model validation is bypassed."""
    binding = KnowledgeSourceBinding(
        **binding_values(
            tier=tier,
            platform_key=platform_key,
            space_id=space_id,
            scope_type=scope_type,
            scope_value=scope_value,
        )
    )
    binding.active_identity = binding._derive_active_identity()
    with pytest.raises(IntegrityError), transaction.atomic():
        super(KnowledgeSourceBinding, binding).save(force_insert=True)


@pytest.mark.django_db
def test_active_binding_identity_is_unique_but_inactive_history_is_retained():
    """Reject duplicate active identities while allowing repeated inactive history."""
    KnowledgeSourceBinding.objects.create(**binding_values())

    with pytest.raises(IntegrityError), transaction.atomic():
        KnowledgeSourceBinding.objects.create(**binding_values(owner="another-owner"))

    first_inactive = KnowledgeSourceBinding.objects.create(**binding_values(status=KnowledgeBindingStatus.DISABLED))
    second_inactive = KnowledgeSourceBinding.objects.create(
        **binding_values(status=KnowledgeBindingStatus.DISABLED, owner="another-owner")
    )

    assert first_inactive.active_identity is None
    assert second_inactive.active_identity is None


def test_binding_lifecycle_and_trust_choices_cover_retrieval_governance():
    """Expose explicit disabled/deprecation states and trusted eligibility levels."""
    assert {
        KnowledgeBindingStatus.ACTIVE,
        KnowledgeBindingStatus.DISABLED,
        KnowledgeBindingStatus.DEPRECATED,
        KnowledgeBindingStatus.RETIRED,
    } == set(KnowledgeBindingStatus.values)
    assert {
        KnowledgeTrustLevel.UNVERIFIED,
        KnowledgeTrustLevel.VERIFIED,
        KnowledgeTrustLevel.TRUSTED,
    } == set(KnowledgeTrustLevel.values)


@pytest.mark.django_db
def test_database_requires_derived_identity_for_active_bindings():
    """Derive active identities for validated bulk inserts and reject duplicates."""
    binding = KnowledgeSourceBinding(**binding_values(active_identity="0" * 64))

    KnowledgeSourceBinding.objects.bulk_create([binding])

    assert binding.active_identity
    assert binding.active_identity != "0" * 64
    assert KnowledgeSourceBinding.objects.get(source_ref=binding.source_ref).active_identity == binding.active_identity

    with pytest.raises(IntegrityError), transaction.atomic():
        KnowledgeSourceBinding.objects.bulk_create([KnowledgeSourceBinding(**binding_values(owner="other-owner"))])


@pytest.mark.django_db
def test_provider_config_rejects_resolved_secret_material():
    """Keep provider configuration limited to non-secret routing metadata."""
    binding = KnowledgeSourceBinding(
        **binding_values(provider_config={"collection": "workflow-guides", "api_token": "resolved-secret"})
    )

    with pytest.raises(ValidationError) as error:
        binding.full_clean()

    assert "provider_config" in error.value.message_dict


@pytest.mark.django_db
def test_direct_binding_save_rejects_resolved_secret_material():
    """Keep direct ORM writes from persisting provider secrets without model forms."""
    with pytest.raises(ValidationError):
        KnowledgeSourceBinding.objects.create(
            **binding_values(provider_config={"collection": "workflow-guides", "password": "resolved-secret"})
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "provider_config",
    [
        {"clientSecret": "resolved-secret"},
        {"authorization": "Bearer resolved-secret"},
        {"collection": {"api_token": "nested-secret"}},
        {"unknown_metadata": "unbounded"},
        {"collection": "x" * 129},
    ],
)
def test_provider_config_uses_a_bounded_positive_schema(provider_config):
    """Reject secret-shaped, nested, unknown, or oversized provider metadata."""
    binding = KnowledgeSourceBinding(**binding_values(provider_config=provider_config))

    with pytest.raises(ValidationError) as error:
        binding.full_clean()

    assert "provider_config" in error.value.message_dict


@pytest.mark.django_db
def test_binding_bulk_create_rejects_unsafe_provider_config():
    """Prevent bulk inserts from bypassing provider metadata validation."""
    binding = KnowledgeSourceBinding(**binding_values(provider_config={"clientSecret": "resolved-secret"}))

    with pytest.raises(ValidationError):
        KnowledgeSourceBinding.objects.bulk_create([binding])

    assert KnowledgeSourceBinding.objects.count() == 0


UNSAFE_NON_SECRET_BINDING_FIELDS = [
    {"provider": "Bearer resolved-provider-secret"},
    {"platform_key": "token=resolved-platform-secret"},
    {"scope_type": "api_token=resolved-scope-type-secret"},
    {"scope_value": "password=resolved-scope-value-secret"},
    {"environment": "Bearer resolved-environment-secret"},
    {"allowed_apps": ["token=resolved-app-secret"]},
    {"allowed_actors": ["Bearer resolved-actor-secret"]},
    {"data_classification": "api_key=resolved-classification-secret"},
    {"source_ref": "https://workflow-guides/restart-service"},
    {"source_ref": "knowledge://user:password@workflow-guides/restart-service"},
    {"source_ref": "knowledge://workflow-guides/restart-service?token=resolved"},
    {"source_ref": "knowledge://workflow-guides/restart-service?"},
    {"source_ref": "knowledge://workflow-guides/restart-service#fragment"},
    {"source_ref": "knowledge://workflow-guides/restart-service#"},
    {"source_ref": "credential://id/42"},
    {"source_ref": "knowledge://workflow-guides/token=resolved-source-secret"},
    {"snapshot_version": "Bearer resolved-snapshot-secret"},
    {"snapshot_version": "invalid-\ud800-snapshot"},
    {"snapshot_version": "界" * 43},
    {"redaction_policy": {"policy_ref": "https://workflow-guides/redaction/v1"}},
    {"redaction_policy": {"policy_ref": "redaction://user:password@workflow-guides/v1"}},
    {"redaction_policy": {"policy_ref": "redaction://workflow-guides/v1?"}},
    {"redaction_policy": {"policy_ref": "redaction://workflow-guides/v1#"}},
    {"provider_config": {"collection": "Bearer resolved-collection-secret"}},
    {"provider_config": {"region": "token=resolved-region-secret"}},
    {"provider_config": {"endpoint_ref": "credential://id/42"}},
    {"provider_config": {"endpoint_ref": "endpoint://user:password@knowledge-service/v1"}},
    {"provider_config": {"endpoint_ref": "https://knowledge-service/v1"}},
]


@pytest.mark.django_db
@pytest.mark.parametrize("overrides", UNSAFE_NON_SECRET_BINDING_FIELDS)
def test_binding_full_clean_rejects_secret_or_unsafe_non_secret_metadata(overrides):
    """Unsafe references and secret-shaped metadata must fail before governance can activate a binding."""
    binding = KnowledgeSourceBinding(**binding_values(**overrides))

    with pytest.raises(ValidationError):
        binding.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize("overrides", UNSAFE_NON_SECRET_BINDING_FIELDS)
def test_binding_direct_save_rejects_secret_or_unsafe_non_secret_metadata(overrides):
    """Direct ORM writes must apply the same non-secret boundary as model validation."""
    with pytest.raises(ValidationError):
        KnowledgeSourceBinding.objects.create(**binding_values(**overrides))

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("overrides", UNSAFE_NON_SECRET_BINDING_FIELDS)
def test_binding_bulk_create_rejects_secret_or_unsafe_non_secret_metadata(overrides):
    """Bulk inserts must not bypass URI, UTF-8 byte, or secret-shape validation."""
    binding = KnowledgeSourceBinding(**binding_values(**overrides))

    with pytest.raises(ValidationError):
        KnowledgeSourceBinding.objects.bulk_create([binding])

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db
def test_binding_accepts_explicit_safe_endpoint_reference_scheme():
    """The endpoint field remains usable only through its non-secret opaque reference namespace."""
    binding = KnowledgeSourceBinding(
        **binding_values(provider_config={"endpoint_ref": "endpoint://knowledge-service/retrieval-v1"})
    )

    binding.full_clean()
    binding.save()

    assert KnowledgeSourceBinding.objects.get(pk=binding.pk).provider_config["endpoint_ref"].startswith("endpoint://")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"owner": ""},
        {"reviewer": None},
        {"reviewer": ""},
        {"reviewer": "knowledge-owner"},
        {"owner": "Bearer resolved-owner-secret"},
        {"reviewer": "token=resolved-reviewer-secret"},
        {"trust_level": KnowledgeTrustLevel.VERIFIED, "last_verified_at": None},
        {"trust_level": KnowledgeTrustLevel.TRUSTED, "last_verified_at": None},
    ],
)
def test_binding_clean_and_direct_save_enforce_local_governance_invariants(overrides):
    """Direct model writes must not bypass dual review, trust evidence timestamps, or non-secret identities."""
    for operation in ("full_clean", "save"):
        binding = KnowledgeSourceBinding(**binding_values(**overrides))
        with pytest.raises(ValidationError):
            getattr(binding, operation)()

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db
def test_binding_deletion_paths_are_blocked_in_favor_of_controlled_retirement():
    """Soft or hard deletion would erase governance history instead of transitioning the binding to retired."""
    binding = KnowledgeSourceBinding.objects.create(**binding_values())

    with pytest.raises(ValidationError, match="retire"):
        binding.delete()
    with pytest.raises(ValidationError, match="retire"):
        binding.hard_delete()
    with pytest.raises(ValidationError, match="retire"):
        KnowledgeSourceBinding.objects.filter(pk=binding.pk).delete()

    persisted = KnowledgeSourceBinding.objects.get(pk=binding.pk)
    assert persisted.status == KnowledgeBindingStatus.ACTIVE
    assert persisted.is_deleted is False


@pytest.mark.django_db
def test_binding_base_manager_cannot_bypass_bulk_safety():
    """Apply the same batch validation through Django's base manager."""
    binding = KnowledgeSourceBinding(
        **binding_values(
            status=KnowledgeBindingStatus.DISABLED,
            provider_config={"clientSecret": "resolved-secret"},
        )
    )

    with pytest.raises(ValidationError):
        KnowledgeSourceBinding._base_manager.bulk_create([binding])

    assert KnowledgeSourceBinding.objects.count() == 0


@pytest.mark.django_db
def test_binding_bulk_update_and_queryset_update_are_explicitly_blocked():
    """Block set-based mutations that cannot safely maintain validation and derived identity."""
    binding = KnowledgeSourceBinding.objects.create(**binding_values())
    original_identity = binding.active_identity
    binding.provider_config = {"clientSecret": "resolved-secret"}

    with pytest.raises(ValidationError):
        KnowledgeSourceBinding.objects.bulk_update([binding], ["provider_config"])
    with pytest.raises(ValidationError):
        KnowledgeSourceBinding.objects.filter(pk=binding.pk).update(provider="other-provider")
    with pytest.raises(ValidationError):
        KnowledgeSourceBinding.objects.filter(pk=binding.pk).update(
            provider_config={"authorization": "Bearer resolved-secret"}
        )
    with pytest.raises(ValidationError):
        KnowledgeSourceBinding.objects.filter(pk=binding.pk).update(active_identity="0" * 64)

    persisted = KnowledgeSourceBinding.objects.get(pk=binding.pk)
    assert persisted.provider == "bk-docs"
    assert persisted.provider_config == {"collection": "workflow-guides", "region": "ap-shanghai"}
    assert persisted.active_identity == original_identity


@pytest.mark.django_db
def test_binding_save_update_fields_persists_recomputed_identity_and_overwrites_forgery():
    """Keep the stored active identity synchronized when a partial model save changes its inputs."""
    binding = KnowledgeSourceBinding.objects.create(**binding_values(active_identity="0" * 64))
    original_identity = binding.active_identity

    assert original_identity != "0" * 64

    binding.provider = "other-provider"
    binding.active_identity = "1" * 64
    binding.save(update_fields=["provider"])
    persisted = KnowledgeSourceBinding.objects.get(pk=binding.pk)

    assert persisted.provider == "other-provider"
    assert persisted.active_identity == binding.active_identity
    assert persisted.active_identity not in {original_identity, "1" * 64}


@pytest.mark.django_db
def test_partial_save_rejects_omitted_changed_identity_when_saving_owner_only():
    """Reject an owner-only save when an unsaved space change would drift the persisted hash."""
    binding = KnowledgeSourceBinding.objects.create(**binding_values())
    original_identity = binding.active_identity
    binding.space_id = 903
    binding.owner = "new-owner"

    with pytest.raises(ValidationError):
        binding.save(update_fields=["owner"])

    persisted = KnowledgeSourceBinding.objects.get(pk=binding.pk)
    assert persisted.space_id == 902
    assert persisted.owner == "knowledge-owner"
    assert persisted.active_identity == original_identity
    assert persisted.active_identity == expected_active_identity()


@pytest.mark.django_db
def test_partial_save_rejects_a_second_changed_identity_field_omitted_from_update_fields():
    """Reject a provider save when another changed identity dimension is omitted."""
    binding = KnowledgeSourceBinding.objects.create(**binding_values())
    original_identity = binding.active_identity
    binding.provider = "other-provider"
    binding.space_id = 903

    with pytest.raises(ValidationError):
        binding.save(update_fields=["provider"])

    persisted = KnowledgeSourceBinding.objects.get(pk=binding.pk)
    assert persisted.provider == "bk-docs"
    assert persisted.space_id == 902
    assert persisted.active_identity == original_identity
    assert persisted.active_identity == expected_active_identity()


@pytest.mark.django_db
def test_partial_save_of_selected_identity_and_status_fields_keeps_hash_consistent():
    """Persist explicitly selected identity and status changes with the matching derived hash."""
    binding = KnowledgeSourceBinding.objects.create(**binding_values())
    binding.provider = "other-provider"

    binding.save(update_fields=["provider"])

    persisted = KnowledgeSourceBinding.objects.get(pk=binding.pk)
    assert persisted.provider == "other-provider"
    assert persisted.active_identity == expected_active_identity(provider="other-provider")

    persisted.status = KnowledgeBindingStatus.DISABLED
    persisted.save(update_fields=["status"])
    disabled = KnowledgeSourceBinding.objects.get(pk=binding.pk)
    assert disabled.status == KnowledgeBindingStatus.DISABLED
    assert disabled.active_identity is None


@pytest.mark.django_db
def test_partial_save_from_adding_instance_with_existing_pk_cannot_drift_identity():
    """Reject a forced partial UPDATE whose new instance has no persisted-state baseline."""
    persisted = KnowledgeSourceBinding.objects.create(**binding_values())
    original_identity = persisted.active_identity
    replacement = KnowledgeSourceBinding(pk=persisted.pk, **binding_values(provider="other-provider"))

    assert replacement._state.adding is True

    with pytest.raises(ValidationError):
        replacement.save(update_fields=["provider"])

    persisted.refresh_from_db()
    assert persisted.provider == "bk-docs"
    assert persisted.active_identity == original_identity
    assert persisted.active_identity == expected_active_identity()


@pytest.mark.django_db
def test_partial_save_uses_one_routed_database_for_lock_and_write(monkeypatch):
    """Keep the lock read and real database write on the same resolved alias."""
    binding = KnowledgeSourceBinding.objects.create(**binding_values())
    route_calls = []

    def route_write(model, **hints):
        route_calls.append((model, hints))
        return "default" if len(route_calls) == 1 else "unexpected-second-route"

    monkeypatch.setattr("bkflow.harness.models.router.db_for_write", route_write)
    binding.provider = "other-provider"

    binding.save(update_fields=["provider"])

    persisted = KnowledgeSourceBinding.objects.using("default").get(pk=binding.pk)
    assert len(route_calls) == 1
    assert persisted.provider == "other-provider"
    assert persisted.active_identity == expected_active_identity(provider="other-provider")


@pytest.mark.django_db
def test_active_identity_canonicalizes_space_id_to_database_integer_type():
    """Hash equivalent integer inputs identically before they reach the database."""
    string_space_binding = KnowledgeSourceBinding(**binding_values(space_id="902"))
    integer_space_binding = KnowledgeSourceBinding(**binding_values(space_id=902))

    string_space_binding.save()
    integer_space_binding.full_clean(validate_unique=False)
    persisted = KnowledgeSourceBinding.objects.get(pk=string_space_binding.pk)

    assert persisted.space_id == 902
    assert isinstance(persisted.space_id, int)
    assert persisted.active_identity == integer_space_binding.active_identity


@pytest.mark.django_db
@pytest.mark.parametrize("max_top_k", [0, 21])
def test_binding_clean_rejects_max_top_k_outside_one_to_twenty(max_top_k):
    """Reject ineffective or unbounded retrieval limits during Python validation."""
    binding = KnowledgeSourceBinding(**binding_values(max_top_k=max_top_k))

    with pytest.raises(ValidationError) as error:
        binding.full_clean()

    assert "max_top_k" in error.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("max_top_k", [0, 21])
def test_database_rejects_max_top_k_outside_one_to_twenty(max_top_k):
    """Keep retrieval limits bounded when Python validation is bypassed."""
    with pytest.raises(IntegrityError), transaction.atomic():
        KnowledgeSourceBinding.objects.create(**binding_values(max_top_k=max_top_k))


@pytest.mark.django_db
def test_retrieval_audit_persists_only_bounded_retrieval_evidence():
    """Persist trusted context, fingerprints, and references without secret or document fields."""
    audit = KnowledgeRetrievalAudit.objects.create(
        trusted_context_snapshot={
            "platform_key": "bkaidev",
            "platform_app": "trusted-app",
            "actor": "dannydeng",
            "space_id": 902,
            "scope_type": "project",
            "scope_value": "902",
            "target_environment": "stag",
            "policy_version": "risk-2026.09",
            "mcp_contract_version": "1.1.0",
            "correlation_id": "knowledge-audit-1",
        },
        query_fingerprint="f" * 64,
        redacted_query="how to restart [REDACTED] safely",
        eligible_binding_ids=[1, 2],
        provider_call_summaries=[{"provider": "bk-docs", "duration_ms": 12, "outcome": "SUCCESS"}],
        hit_refs=["knowledge-hit://bk-docs/abc"],
        snapshot_refs=["knowledge-snapshot://bk-docs/2026.09.04"],
        correlation_id="knowledge-audit-1",
        duration_ms=18,
        outcome="SUCCESS",
    )

    persisted = KnowledgeRetrievalAudit.objects.get(pk=audit.pk)
    field_names = {field.name for field in KnowledgeRetrievalAudit._meta.get_fields()}

    assert persisted.run is None
    assert persisted.query_fingerprint == "f" * 64
    assert "resolved_credentials" not in field_names
    assert "document_content" not in field_names
    assert "documents" not in field_names


@pytest.mark.django_db
def test_retrieval_audit_rejects_untrusted_context_and_sensitive_payload_keys():
    """Reject forged context fields, resolved credentials, and full document payloads."""
    audit = KnowledgeRetrievalAudit(
        trusted_context_snapshot={"space_id": 902, "resolved_credentials": {"token": "secret"}},
        query_fingerprint="f" * 64,
        redacted_query="restart service",
        provider_call_summaries=[{"provider": "bk-docs", "document_content": "full document"}],
        correlation_id="knowledge-audit-unsafe",
        duration_ms=1,
        outcome="SUCCESS",
    )

    with pytest.raises(ValidationError) as error:
        audit.full_clean()

    assert "trusted_context_snapshot" in error.value.message_dict
    assert "provider_call_summaries" in error.value.message_dict


@pytest.mark.django_db
def test_direct_audit_save_rejects_document_payloads():
    """Keep direct ORM writes from persisting unrestricted document content."""
    with pytest.raises(ValidationError):
        KnowledgeRetrievalAudit.objects.create(
            trusted_context_snapshot={"space_id": 902},
            query_fingerprint="f" * 64,
            redacted_query="restart service",
            provider_call_summaries=[{"provider": "bk-docs", "full_content": "full document"}],
            correlation_id="knowledge-audit-unsafe-save",
            duration_ms=1,
            outcome="SUCCESS",
        )


@pytest.mark.django_db
def test_audit_bulk_create_validates_each_record_and_rejects_sensitive_content():
    """Prevent bulk audit insertion from bypassing the bounded evidence schema."""
    safe = KnowledgeRetrievalAudit(
        trusted_context_snapshot={"space_id": 902},
        query_fingerprint="a" * 64,
        redacted_query="restart service",
        provider_call_summaries=[{"provider": "bk-docs", "outcome": "SUCCESS", "duration_ms": 1}],
        hit_refs=["knowledge-hit://bk-docs/abc"],
        snapshot_refs=["knowledge-snapshot://bk-docs/v1"],
        correlation_id="knowledge-audit-bulk-safe",
        duration_ms=1,
        outcome="SUCCESS",
    )
    unsafe = KnowledgeRetrievalAudit(
        trusted_context_snapshot={"space_id": 902},
        query_fingerprint="b" * 64,
        redacted_query="restart service",
        provider_call_summaries=[{"provider": "bk-docs", "document_content": "full document"}],
        correlation_id="knowledge-audit-bulk-unsafe",
        duration_ms=1,
        outcome="SUCCESS",
    )

    with pytest.raises(ValidationError):
        KnowledgeRetrievalAudit.objects.bulk_create([safe, unsafe])

    assert KnowledgeRetrievalAudit.objects.count() == 0

    KnowledgeRetrievalAudit.objects.bulk_create([safe])

    assert KnowledgeRetrievalAudit.objects.get(correlation_id="knowledge-audit-bulk-safe").query_fingerprint == "a" * 64


@pytest.mark.django_db
def test_audit_base_manager_cannot_bypass_bulk_safety():
    """Apply bounded audit validation through Django's base manager."""
    unsafe = KnowledgeRetrievalAudit(
        trusted_context_snapshot={"space_id": 902},
        query_fingerprint="b" * 64,
        redacted_query="restart service",
        provider_call_summaries=[{"provider": "bk-docs", "document_content": "full document"}],
        correlation_id="knowledge-audit-base-manager-unsafe",
        duration_ms=1,
        outcome="SUCCESS",
    )

    with pytest.raises(ValidationError):
        KnowledgeRetrievalAudit._base_manager.bulk_create([unsafe])

    assert KnowledgeRetrievalAudit.objects.count() == 0


@pytest.mark.django_db
def test_audit_bulk_update_and_queryset_update_are_explicitly_blocked():
    """Keep append-only audit evidence immutable through set-based ORM writes."""
    audit = KnowledgeRetrievalAudit.objects.create(
        trusted_context_snapshot={"space_id": 902},
        query_fingerprint="a" * 64,
        redacted_query="restart service",
        correlation_id="knowledge-audit-immutable",
        duration_ms=1,
        outcome="SUCCESS",
    )
    audit.provider_call_summaries = [{"provider": "bk-docs", "document_content": "full document"}]

    with pytest.raises(ValidationError):
        KnowledgeRetrievalAudit.objects.bulk_update([audit], ["provider_call_summaries"])
    with pytest.raises(ValidationError):
        KnowledgeRetrievalAudit.objects.filter(pk=audit.pk).update(
            provider_call_summaries=[{"resolved_credentials": {"token": "secret"}}]
        )

    assert KnowledgeRetrievalAudit.objects.get(pk=audit.pk).provider_call_summaries == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name,invalid_value",
    [
        ("trusted_context_snapshot", {"space_id": {"forged": 902}}),
        ("trusted_context_snapshot", {"space_id": True}),
        ("eligible_binding_ids", [0]),
        ("eligible_binding_ids", list(range(1, 102))),
        ("provider_call_summaries", [{"provider": "bk-docs", "arbitrary": "unbounded"}]),
        ("provider_call_summaries", [{"provider": "x" * 65, "outcome": "SUCCESS"}]),
        ("hit_refs", ["not-an-opaque-ref"]),
        ("snapshot_refs", ["knowledge-snapshot://" + "x" * 240]),
        ("query_fingerprint", "not-a-sha256"),
        ("redacted_query", "x" * 2001),
    ],
)
def test_audit_enforces_field_level_types_counts_lengths_and_formats(field_name, invalid_value):
    """Reject audit evidence outside explicit field shapes and bounded reference formats."""
    values = {
        "trusted_context_snapshot": {"space_id": 902},
        "query_fingerprint": "a" * 64,
        "redacted_query": "restart service",
        "eligible_binding_ids": [1],
        "provider_call_summaries": [{"provider": "bk-docs", "outcome": "SUCCESS", "duration_ms": 1}],
        "hit_refs": ["knowledge-hit://bk-docs/abc"],
        "snapshot_refs": ["knowledge-snapshot://bk-docs/v1"],
        "correlation_id": "knowledge-audit-bounded",
        "duration_ms": 1,
        "outcome": "SUCCESS",
    }
    values[field_name] = invalid_value
    audit = KnowledgeRetrievalAudit(**values)

    with pytest.raises(ValidationError) as error:
        audit.full_clean()

    assert field_name in error.value.message_dict


@pytest.mark.django_db
def test_retrieval_audit_can_reference_a_run_and_isolates_json_defaults():
    """Optionally correlate an audit to a run without sharing mutable JSON defaults."""
    run = HarnessRun.objects.create(
        platform="bkaidev",
        platform_app="trusted-app",
        actor="dannydeng",
        space_id=902,
        scope="project:902",
        environment="stag",
        status="INTENT_CAPTURED",
        policy_version="risk-2026.09",
        mcp_contract_version="1.1.0",
    )
    first = KnowledgeRetrievalAudit.objects.create(
        run=run,
        trusted_context_snapshot={"space_id": 902},
        query_fingerprint="a" * 64,
        redacted_query="restart service",
        correlation_id="knowledge-audit-2",
        duration_ms=1,
        outcome="NO_HITS",
    )
    second = KnowledgeRetrievalAudit.objects.create(
        trusted_context_snapshot={"space_id": 903},
        query_fingerprint="b" * 64,
        redacted_query="deploy service",
        correlation_id="knowledge-audit-3",
        duration_ms=2,
        outcome="SUCCESS",
    )

    assert first.run_id == run.id
    assert first.eligible_binding_ids == []
    assert second.eligible_binding_ids == []
    assert first.eligible_binding_ids is not second.eligible_binding_ids


def test_admin_makes_binding_and_audit_models_read_only():
    """Admin must not bypass the controlled binding synchronizer or append-only audit path."""
    binding_admin = admin.site._registry[KnowledgeSourceBinding]
    audit_admin = admin.site._registry[KnowledgeRetrievalAudit]

    assert isinstance(binding_admin, KnowledgeSourceBindingAdmin)
    assert {"tier", "status", "owner"}.issubset(set(binding_admin.list_filter))
    assert binding_admin.has_add_permission(None) is False
    assert binding_admin.has_change_permission(None) is False
    assert binding_admin.has_delete_permission(None) is False
    assert set(binding_admin.readonly_fields) == {field.name for field in KnowledgeSourceBinding._meta.get_fields()}
    assert isinstance(audit_admin, KnowledgeRetrievalAuditAdmin)
    assert audit_admin.has_add_permission(None) is False
    assert audit_admin.has_change_permission(None) is False
    assert audit_admin.has_delete_permission(None) is False
