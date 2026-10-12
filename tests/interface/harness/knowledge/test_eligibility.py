"""Database-first ACL truth table for governed knowledge bindings."""

from unittest import mock

import pytest
from django.db import connection
from django.utils import timezone

from bkflow.harness.constants import (
    KnowledgeBindingStatus,
    KnowledgeRetrievalMode,
    KnowledgeTier,
    KnowledgeTrustLevel,
)
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import KnowledgeSourceBinding
from bkflow.harness.services.knowledge.contracts import KnowledgeProviderQuery
from bkflow.harness.services.knowledge.eligibility import eligible_bindings


def trusted_context(**overrides):
    """Build authority that would normally come only from the gateway request."""
    values = {
        "platform_key": "bkaidev",
        "platform_app": "trusted-app",
        "actor": "trusted-user",
        "space_id": 902,
        "scope_type": "project",
        "scope_value": "902",
        "target_environment": "stag",
        "policy_version": "risk-2026.09",
        "mcp_contract_version": "1.1.0",
        "correlation_id": "knowledge-eligibility-test",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


def binding_values(**overrides):
    """Return a valid active public binding unless a test overrides its ACL facts."""
    values = {
        "provider": "fixture-docs",
        "source_ref": "knowledge://workflow-guides/default",
        "tier": KnowledgeTier.PUBLIC,
        "platform_key": None,
        "space_id": None,
        "scope_type": None,
        "scope_value": None,
        "trust_level": KnowledgeTrustLevel.VERIFIED,
        "priority": 0,
        "environment": "stag",
        "allowed_apps": [],
        "allowed_actors": [],
        "data_classification": "internal",
        "snapshot_version": "2026.09.04",
        "last_verified_at": timezone.now(),
        "owner": "knowledge-owner",
        "reviewer": "security-reviewer",
        "status": KnowledgeBindingStatus.ACTIVE,
        "retrieval_mode": KnowledgeRetrievalMode.HYBRID,
        "max_top_k": 5,
        "redaction_policy": {"policy_ref": "redaction://workflow-guides/v1"},
        "credential_ref": None,
        "provider_config": {"collection": "workflow-guides"},
    }
    values.update(overrides)
    return values


def create_binding(source_suffix, **overrides):
    """Persist one binding with a unique opaque source reference."""
    values = binding_values(source_ref="knowledge://workflow-guides/{}".format(source_suffix), **overrides)
    binding = KnowledgeSourceBinding(**values)
    binding.full_clean()
    binding.save()
    return binding


@pytest.mark.django_db
def test_eligible_bindings_orders_global_public_platform_space_scope_before_dispatch():
    """Return only matching tier rows in the documented deterministic tier order."""
    scope = create_binding(
        "scope",
        tier=KnowledgeTier.SCOPE,
        platform_key="bkaidev",
        space_id=902,
        scope_type="project",
        scope_value="902",
        priority=500,
    )
    space = create_binding("space", tier=KnowledgeTier.SPACE, platform_key="bkaidev", space_id=902)
    public = create_binding("public", tier=KnowledgeTier.PUBLIC)
    global_binding = create_binding("global", tier=KnowledgeTier.GLOBAL)
    platform = create_binding("platform", tier=KnowledgeTier.PLATFORM, platform_key="bkaidev")

    result = eligible_bindings(trusted_context(), "internal")

    assert [binding.id for binding in result] == [
        global_binding.id,
        public.id,
        platform.id,
        space.id,
        scope.id,
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"tier": KnowledgeTier.PLATFORM, "platform_key": "other-platform"},
        {"tier": KnowledgeTier.SPACE, "platform_key": "bkaidev", "space_id": 903},
        {
            "tier": KnowledgeTier.SCOPE,
            "platform_key": "bkaidev",
            "space_id": 902,
            "scope_type": "project",
            "scope_value": "another-scope",
        },
        {"environment": "prod"},
        {"allowed_apps": ["other-app"]},
        {"allowed_actors": ["other-user"]},
        {"expires_at": timezone.now() - timezone.timedelta(seconds=1)},
        {"trust_level": KnowledgeTrustLevel.UNVERIFIED},
        {"last_verified_at": None},
        {"status": KnowledgeBindingStatus.DISABLED},
        {"status": KnowledgeBindingStatus.DEPRECATED},
        {"status": KnowledgeBindingStatus.RETIRED},
        {"is_deleted": True},
        {"data_classification": "restricted"},
    ],
)
def test_acl_truth_table_filters_forbidden_binding_before_provider_dispatch(overrides):
    """Never expose a forbidden row to the loop that can invoke a provider."""
    if overrides == {"last_verified_at": None}:
        forbidden = create_binding("forbidden")
        table = connection.ops.quote_name(KnowledgeSourceBinding._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE {} SET last_verified_at = NULL WHERE id = %s".format(table), [forbidden.id])
    else:
        forbidden = create_binding("forbidden", **overrides)
    provider = mock.Mock()

    for binding in eligible_bindings(trusted_context(), "internal"):
        provider.search(
            binding,
            KnowledgeProviderQuery(
                query="restart service",
                top_k=1,
                source_ref=binding.source_ref,
                snapshot_version=binding.snapshot_version,
                correlation_id="knowledge-eligibility-test",
            ),
        )

    provider.search.assert_not_called()
    assert forbidden.id not in [binding.id for binding in eligible_bindings(trusted_context(), "internal")]


@pytest.mark.django_db
def test_empty_allowlists_are_open_but_matching_nonempty_allowlists_are_allowed():
    """Treat an empty list as unrestricted and a nonempty list as an exact allowlist."""
    open_binding = create_binding("open")
    restricted_binding = create_binding(
        "allowed",
        allowed_apps=["trusted-app", "backup-app"],
        allowed_actors=["trusted-user"],
    )

    result = eligible_bindings(trusted_context(), "internal")

    assert {binding.id for binding in result} == {open_binding.id, restricted_binding.id}


@pytest.mark.django_db
def test_same_tier_order_uses_priority_then_primary_key_for_stability():
    """Make repeated routing deterministic without letting priority cross tier boundaries."""
    low = create_binding("low", priority=1)
    high_first = create_binding("high-first", priority=10)
    high_second = create_binding("high-second", priority=10)

    result = eligible_bindings(trusted_context(), "internal")

    assert [binding.id for binding in result] == [high_first.id, high_second.id, low.id]


@pytest.mark.django_db
@pytest.mark.parametrize("classification", [None, "", "internal\x00secret", "x" * 65])
def test_invalid_requested_classification_fails_closed(classification):
    """Reject malformed classification selectors instead of broadening the query."""
    create_binding("valid")

    assert eligible_bindings(trusted_context(), classification) == ()
