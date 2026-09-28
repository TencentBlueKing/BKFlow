"""Trusted resource-token issuance shared by APIGW and the Harness Broker."""

import datetime
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from pytimeparse import parse

from bkflow.apigw.serializers.token import TokenResourceValidator
from bkflow.permission.models import Token
from bkflow.space.configs import TokenAutoRenewalConfig, TokenExpirationConfig
from bkflow.space.models import Space, SpaceConfig


@dataclass(frozen=True)
class TokenIssueContext:
    """Authority supplied by an already-authenticated platform request."""

    platform_app: str
    actor: str
    space_id: int


@dataclass(frozen=True)
class TokenRevokeContext:
    """Application-only authority used by the legacy revoke operation."""

    platform_app: str
    space_id: int


@dataclass(frozen=True)
class TokenResource:
    """One concrete BKFlow permission resource."""

    resource_type: str
    resource_id: str


class IssuedResourceToken:
    """A deliberately non-picklable server-side result with a redacted repr."""

    __slots__ = (
        "_secret",
        "space_id",
        "actor",
        "resource_type",
        "resource_id",
        "permission",
        "expires_at",
        "reused",
    )

    def __init__(
        self,
        *,
        secret,
        space_id,
        actor,
        resource_type,
        resource_id,
        permission,
        expires_at,
        reused,
    ):
        self._secret = secret
        self.space_id = space_id
        self.actor = actor
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.permission = permission
        self.expires_at = expires_at
        self.reused = reused

    @property
    def secret(self):
        """Expose plaintext only to the immediate server-side caller."""
        return self._secret

    def __repr__(self):
        return (
            "IssuedResourceToken(space_id={!r}, actor={!r}, resource_type={!r}, "
            "resource_id={!r}, permission={!r}, expires_at={!r}, reused={!r}, secret=[REDACTED])"
        ).format(
            self.space_id,
            self.actor,
            self.resource_type,
            self.resource_id,
            self.permission,
            self.expires_at,
            self.reused,
        )

    def __reduce_ex__(self, protocol):
        raise TypeError("Issued resource tokens cannot be serialized")

    def __getstate__(self):
        raise TypeError("Issued resource tokens cannot be serialized")


def _validate_context(context):
    if not isinstance(context, TokenIssueContext):
        raise ValidationError("Token issuer context is invalid")
    if (
        not isinstance(context.platform_app, str)
        or not context.platform_app
        or len(context.platform_app) > 32
        or not isinstance(context.actor, str)
        or not context.actor
        or len(context.actor) > 32
        or isinstance(context.space_id, bool)
        or not isinstance(context.space_id, int)
        or context.space_id <= 0
    ):
        raise ValidationError("Token issuer context is invalid")
    if not Space.objects.filter(id=context.space_id, app_code=context.platform_app, is_deleted=False).exists():
        raise ValidationError("Token issuer context is invalid")


def _validate_revoke_context(context):
    if (
        not isinstance(context, TokenRevokeContext)
        or not isinstance(context.platform_app, str)
        or not context.platform_app
        or len(context.platform_app) > 32
        or isinstance(context.space_id, bool)
        or not isinstance(context.space_id, int)
        or context.space_id <= 0
        or not Space.objects.filter(id=context.space_id, app_code=context.platform_app, is_deleted=False).exists()
    ):
        raise ValidationError("Token revocation authority is invalid")


def _validate_resource(resource, permission):
    resource_choices = {value for value, _label in Token.RESOURCE_TYPE}
    permission_choices = {value for value, _label in Token.PERMISSION_TYPE}
    if (
        not isinstance(resource, TokenResource)
        or resource.resource_type not in resource_choices
        or not isinstance(resource.resource_id, str)
        or not resource.resource_id
        or len(resource.resource_id) > 32
        or permission not in permission_choices
    ):
        raise ValidationError("Token resource request is invalid")


def _configured_expiry(space_id, now):
    try:
        seconds = parse(SpaceConfig.get_config(space_id, config_name=TokenExpirationConfig.name))
    except Exception:
        raise ValidationError("Token expiration policy is invalid") from None
    if seconds is None or seconds <= 0:
        raise ValidationError("Token expiration policy is invalid")
    return now + datetime.timedelta(seconds=seconds)


def _result(token, reused):
    return IssuedResourceToken(
        secret=token.token,
        space_id=token.space_id,
        actor=token.user,
        resource_type=token.resource_type,
        resource_id=token.resource_id,
        permission=token.permission_type,
        expires_at=token.expired_time,
        reused=reused,
    )


def issue_resource_token(context, resource, permission, *, expires_at=None, reuse_existing=True):
    """Validate authority/resource, then issue or reuse one BKFlow Token.

    ``expires_at`` is reserved for bounded server-side leases. Legacy APIGW
    callers omit it and retain the configured expiry/auto-renew behavior.
    """
    _validate_context(context)
    _validate_resource(resource, permission)
    now = timezone.now()
    requested_expiry = _configured_expiry(context.space_id, now) if expires_at is None else expires_at
    if requested_expiry is None or timezone.is_naive(requested_expiry) or requested_expiry <= now:
        raise ValidationError("Token expiration policy is invalid")

    # Resource existence is deliberately checked before any Token query/write.
    TokenResourceValidator(context.space_id, resource.resource_type, resource.resource_id).validate()
    identity = {
        "space_id": context.space_id,
        "user": context.actor,
        "resource_type": resource.resource_type,
        "resource_id": resource.resource_id,
        "permission_type": permission,
    }
    with transaction.atomic():
        token = None
        if reuse_existing:
            token = (
                Token.objects.select_for_update()
                .filter(**identity, expired_time__gte=now)
                .order_by("-expired_time")
                .first()
            )
        if token is not None:
            if expires_at is not None:
                # Explicit server-side bounds must never be widened by a stale token.
                if token.expired_time > requested_expiry:
                    token.expired_time = requested_expiry
                    token.save(update_fields=["expired_time"])
            elif SpaceConfig.get_config(context.space_id, TokenAutoRenewalConfig.name) == "true":
                token.expired_time = requested_expiry
                token.save(update_fields=["expired_time"])
            return _result(token, reused=True)

        token = Token.objects.create(
            **identity,
            expired_time=requested_expiry,
            token=Token.generate_token(),
        )
        return _result(token, reused=False)


def revoke_resource_token(secret, *, revoked_at=None):
    """Expire exactly one legacy token without logging or returning plaintext."""
    if not isinstance(secret, str) or not secret or len(secret) > 32:
        raise ValidationError("Token revocation request is invalid")
    when = revoked_at or timezone.now()
    if timezone.is_naive(when):
        raise ValidationError("Token revocation request is invalid")
    return Token.objects.filter(token=secret).update(expired_time=when)


def revoke_resource_tokens(context, filters, *, revoked_at=None):
    """Expire a trusted space-scoped token set without echoing filter values."""
    _validate_revoke_context(context)
    allowed = {"token", "user", "resource_type", "resource_id", "permission_type"}
    if not isinstance(filters, dict) or set(filters) - allowed:
        raise ValidationError("Token revocation request is invalid")
    when = revoked_at or timezone.now()
    if timezone.is_naive(when):
        raise ValidationError("Token revocation request is invalid")
    return Token.objects.filter(space_id=context.space_id, **filters).update(expired_time=when)
