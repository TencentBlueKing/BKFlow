"""Database-first eligibility for governed knowledge source bindings."""

import json
import re

from django.db import connection, models
from django.db.models.expressions import RawSQL
from django.utils import timezone

from bkflow.harness.constants import (
    KnowledgeBindingStatus,
    KnowledgeTier,
    KnowledgeTrustLevel,
)
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import KnowledgeSourceBinding

_CLASSIFICATION = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_TIER_ORDER = {
    KnowledgeTier.GLOBAL: 0,
    KnowledgeTier.PUBLIC: 1,
    KnowledgeTier.PLATFORM: 2,
    KnowledgeTier.SPACE: 3,
    KnowledgeTier.SCOPE: 4,
}


def _json_array_member_sql(field_name, value):
    """Build a parameterized JSON-array membership expression for supported databases."""
    table = connection.ops.quote_name(KnowledgeSourceBinding._meta.db_table)
    column = connection.ops.quote_name(field_name)
    qualified = "{}.{}".format(table, column)
    if connection.vendor == "sqlite":
        sql = "EXISTS (SELECT 1 FROM json_each({}) WHERE json_each.value = %s)".format(qualified)
        params = [value]
    elif connection.vendor == "mysql":
        sql = "JSON_CONTAINS({}, JSON_QUOTE(%s))".format(qualified)
        params = [value]
    elif connection.vendor == "postgresql":
        sql = "{} @> %s::jsonb".format(qualified)
        params = [json.dumps([value], ensure_ascii=True)]
    else:
        # Eligibility is security-sensitive: unknown database engines get no allowlist match.
        sql = "1 = 0"
        params = []
    return RawSQL(sql, params, output_field=models.BooleanField())


def _tier_predicate(context):
    """Select only tiers whose complete authority dimensions match the trusted context."""
    return (
        models.Q(tier__in=[KnowledgeTier.GLOBAL, KnowledgeTier.PUBLIC])
        | models.Q(tier=KnowledgeTier.PLATFORM, platform_key=context.platform_key)
        | models.Q(
            tier=KnowledgeTier.SPACE,
            platform_key=context.platform_key,
            space_id=context.space_id,
        )
        | models.Q(
            tier=KnowledgeTier.SCOPE,
            platform_key=context.platform_key,
            space_id=context.space_id,
            scope_type=context.scope_type,
            scope_value=context.scope_value,
        )
    )


def eligible_bindings(context, classification):
    """Return a deterministic tuple after all ACL predicates have executed in the database."""
    if not isinstance(context, TrustedHarnessContext):
        return ()
    if not isinstance(classification, str) or not _CLASSIFICATION.fullmatch(classification):
        return ()

    tier_order = models.Case(
        *[models.When(tier=tier, then=models.Value(order)) for tier, order in _TIER_ORDER.items()],
        default=models.Value(len(_TIER_ORDER)),
        output_field=models.IntegerField(),
    )
    queryset = (
        KnowledgeSourceBinding.objects.filter(
            _tier_predicate(context),
            is_deleted=False,
            status=KnowledgeBindingStatus.ACTIVE,
            trust_level__in=[KnowledgeTrustLevel.VERIFIED, KnowledgeTrustLevel.TRUSTED],
            last_verified_at__isnull=False,
            environment=context.target_environment,
            data_classification=classification,
        )
        .exclude(snapshot_version="")
        .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now()))
        .annotate(
            _allowed_app=_json_array_member_sql("allowed_apps", context.platform_app),
            _allowed_actor=_json_array_member_sql("allowed_actors", context.actor),
            _tier_order=tier_order,
        )
        .filter(models.Q(allowed_apps=[]) | models.Q(_allowed_app=True))
        .filter(models.Q(allowed_actors=[]) | models.Q(_allowed_actor=True))
        .order_by("_tier_order", "-priority", "id")
    )
    return tuple(queryset)
