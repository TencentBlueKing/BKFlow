"""Token test fixtures backed by the normalized grant tables."""

from django.db import transaction
from django.utils import timezone

from bkflow.permission.grants import Grant, canonical_grants, grant_hash, grant_set_hash
from bkflow.permission.models import Token, TokenGrant


def create_token(
    *,
    space_id,
    user,
    resource_type=None,
    resource_id=None,
    permission_type=None,
    grants=None,
    token=None,
    expired_time=None,
):
    """Create a complete test token without invoking issuance behavior."""
    if grants is None:
        grants = (Grant(resource_type, str(resource_id), permission_type),)
    else:
        grants = tuple(Grant(**grant) if isinstance(grant, dict) else grant for grant in grants)
    grants = canonical_grants(grants)
    with transaction.atomic():
        token_obj = Token.objects.create(
            token=token or Token.generate_token(),
            space_id=space_id,
            user=user,
            expired_time=expired_time or timezone.now() + timezone.timedelta(hours=1),
            grant_set_hash=grant_set_hash(grants),
        )
        TokenGrant.objects.bulk_create(
            [TokenGrant(token=token_obj, grant_hash=grant_hash(grant), **grant.as_dict()) for grant in grants]
        )
    return token_obj
