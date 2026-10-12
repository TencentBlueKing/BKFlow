"""Server-only broker for short-lived debug Token leases."""

import datetime
import hashlib

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import DebugSession, ExecutionRun, TokenLease
from bkflow.harness.services.canonical import canonical_scope
from bkflow.permission.grants import Grant, grant_set_hash
from bkflow.permission.models import Token
from bkflow.permission.token_issuer import (
    TokenIssueContext,
    TokenResource,
    issue_resource_token,
    revoke_resource_token,
)
from bkflow.template.models import Template

MAX_DEBUG_TOKEN_TTL_SECONDS = 5 * 60


class ActiveTokenHandle:
    """Non-serializable in-memory handle consumed only beside DebugService."""

    __slots__ = (
        "lease_id",
        "issuer_ref",
        "expires_at",
        "resource_type",
        "resource_id",
        "permission",
        "_secret",
    )

    def __init__(
        self,
        *,
        lease_id,
        issuer_ref,
        expires_at,
        resource_type,
        resource_id,
        permission,
        secret,
    ):
        self.lease_id = lease_id
        self.issuer_ref = issuer_ref
        self.expires_at = expires_at
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.permission = permission
        self._secret = secret

    @property
    def secret(self):
        """Return plaintext only to the immediate DebugService adapter call."""
        return self._secret

    def __repr__(self):
        return (
            "ActiveTokenHandle(lease_id={!r}, issuer_ref={!r}, expires_at={!r}, "
            "resource_type={!r}, resource_id={!r}, permission={!r}, secret=[REDACTED])"
        ).format(
            self.lease_id,
            self.issuer_ref,
            self.expires_at,
            self.resource_type,
            self.resource_id,
            self.permission,
        )

    def __reduce_ex__(self, protocol):
        raise TypeError("Active token handles cannot be serialized")

    def __getstate__(self):
        raise TypeError("Active token handles cannot be serialized")


def _fingerprint(secret):
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _issuer_context(context):
    return TokenIssueContext(
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
    )


def _validate_authority(context, session, *, require_active=True):
    if not isinstance(context, TrustedHarnessContext):
        raise ValidationError("Debug token authority is invalid")
    run = session.run
    snapshot = session.trusted_context_snapshot
    context_fields = (
        "platform_key",
        "platform_app",
        "actor",
        "space_id",
        "scope_type",
        "scope_value",
        "target_environment",
        "policy_version",
        "mcp_contract_version",
    )
    if not isinstance(snapshot, dict) or any(snapshot.get(key) != getattr(context, key) for key in context_fields):
        raise ValidationError("Debug token authority is invalid")
    run_expected = {
        "platform": snapshot["platform_key"],
        "platform_app": snapshot["platform_app"],
        "actor": snapshot["actor"],
        "space_id": snapshot["space_id"],
        "environment": snapshot["target_environment"],
        "policy_version": snapshot["policy_version"],
        "mcp_contract_version": snapshot["mcp_contract_version"],
    }
    if any(getattr(run, key) != value for key, value in run_expected.items()):
        raise ValidationError("Debug token authority is invalid")
    if run.scope != canonical_scope(snapshot["scope_type"], snapshot["scope_value"]):
        raise ValidationError("Debug token authority is invalid")
    if run.status != HarnessRunStatus.DEBUGGING:
        raise ValidationError("Debug token authority is invalid")
    if session.actor != snapshot["actor"] or session.policy_version != snapshot["policy_version"]:
        raise ValidationError("Debug token authority is invalid")
    if require_active and (not session.is_active or session.expires_at <= timezone.now()):
        raise ValidationError("Debug token session is inactive")


def _validate_execution_authority(context, execution):
    """Require the execution and its run to match every trusted dimension."""
    if not isinstance(context, TrustedHarnessContext) or not isinstance(execution, ExecutionRun):
        raise ValidationError("Execution token authority is invalid")
    run = execution.run
    if (
        run.platform != context.platform_key
        or run.platform_app != context.platform_app
        or run.actor != context.actor
        or run.space_id != context.space_id
        or run.scope != canonical_scope(context.scope_type, context.scope_value)
        or run.environment != context.target_environment
        or run.policy_version != context.policy_version
        or run.mcp_contract_version != context.mcp_contract_version
        or execution.platform != run.platform
        or execution.platform_app != run.platform_app
        or execution.actor != run.actor
        or execution.space_id != run.space_id
        or execution.scope != run.scope
        or execution.target_environment != run.environment
        or execution.policy_version != run.policy_version
    ):
        raise ValidationError("Execution token authority is invalid")


def _resource(session, resource_type, resource_id):
    if resource_type == TokenLease.Resource.TEMPLATE:
        expected = str(session.template_id)
    elif resource_type == TokenLease.Resource.SCOPE:
        scope_type = session.trusted_context_snapshot.get("scope_type")
        scope_value = session.trusted_context_snapshot.get("scope_value")
        expected = "{}_{}".format(scope_type, scope_value) if scope_type and scope_value else None
    else:
        raise ValidationError("Debug token resource is invalid")
    resolved = expected if resource_id is None else str(resource_id)
    if expected is None or resolved != expected:
        raise ValidationError("Debug token resource is invalid")
    return TokenResource(resource_type=resource_type, resource_id=resolved)


def _validate_template_boundary(session, template):
    """Prove that the concrete template belongs to every trusted boundary."""
    snapshot = session.trusted_context_snapshot
    if (
        template.id != session.template_id
        or template.space_id != session.run.space_id
        or template.scope_type != snapshot["scope_type"]
        or template.scope_value != snapshot["scope_value"]
        or template.bk_app_code != snapshot["platform_app"]
        or template.is_deleted
    ):
        raise ValidationError("Debug token template boundary is invalid")


def _matching_token(lease, now):
    grants = (Grant(lease.resource_type, lease.resource_id, lease.permission),)
    candidates = Token.objects.filter(
        space_id=lease.space_id,
        user=lease.actor,
        grant_set_hash=grant_set_hash(grants),
        expired_time__gt=now,
    ).order_by("-expired_time")
    for token in candidates:
        if (
            token.user == lease.actor
            and token.get_grants() == grants
            and not token.has_expired()
            and _fingerprint(token.token) == lease.token_fingerprint
        ):
            return token
    return None


def _handle(lease, secret):
    return ActiveTokenHandle(
        lease_id=lease.pk,
        issuer_ref=lease.issuer_ref,
        expires_at=lease.expires_at,
        resource_type=lease.resource_type,
        resource_id=lease.resource_id,
        permission=lease.permission,
        secret=secret,
    )


class TokenBroker:
    """Issue, reuse, expire, and revoke session-private debug credentials."""

    def acquire_debug_lease(
        self,
        context,
        session,
        *,
        resource_type=TokenLease.Resource.TEMPLATE,
        resource_id=None,
        permission=TokenLease.Permission.MOCK,
    ):
        if permission != TokenLease.Permission.MOCK:
            raise ValidationError("Debug token permission is invalid")
        if not isinstance(session, DebugSession) or not session.pk:
            raise ValidationError("Debug token session is invalid")
        now = timezone.now()
        with transaction.atomic():
            try:
                seed = DebugSession._base_manager.only("template_id").get(pk=session.pk)
                # Other Harness lifecycle paths lock Template before
                # DebugSession. Keep that order and close the template/session
                # time-of-check/time-of-use window.
                template = Template.objects.select_for_update().get(pk=seed.template_id)
                locked = (
                    DebugSession._base_manager.select_for_update().select_related("run", "revision").get(pk=session.pk)
                )
            except (DebugSession.DoesNotExist, Template.DoesNotExist):
                raise ValidationError("Debug token session is invalid") from None
            _validate_authority(context, locked)
            _validate_template_boundary(locked, template)
            requested_resource = _resource(locked, resource_type, resource_id)

            live_leases = list(
                TokenLease._base_manager.select_for_update()
                .filter(
                    session=locked,
                    resource_type=requested_resource.resource_type,
                    resource_id=requested_resource.resource_id,
                    permission=TokenLease.Permission.MOCK,
                    status=TokenLease.Status.ACTIVE,
                )
                .order_by("-issued_at")
            )
            for lease in live_leases:
                token = _matching_token(lease, now)
                if lease.expires_at > now and token is not None:
                    return _handle(lease, token.token)
                if token is not None:
                    # The legacy API can renew the underlying Token without
                    # extending this lease. Do not leave that credential live.
                    revoke_resource_token(token.token, revoked_at=now)
                lease.status = TokenLease.Status.EXPIRED
                lease.expires_at = min(lease.expires_at, now)
                lease.save(update_fields=["status", "expires_at"])

            expires_at = min(
                locked.expires_at,
                now + datetime.timedelta(seconds=MAX_DEBUG_TOKEN_TTL_SECONDS),
            )
            if expires_at <= now:
                raise ValidationError("Debug token session is inactive")
            issued = issue_resource_token(
                _issuer_context(context),
                requested_resource,
                TokenLease.Permission.MOCK,
                expires_at=expires_at,
                reuse_existing=False,
            )
            fingerprint = _fingerprint(issued.secret)
            lease = TokenLease.objects.create(
                session=locked,
                platform_app=context.platform_app,
                actor=context.actor,
                space_id=context.space_id,
                resource_type=requested_resource.resource_type,
                resource_id=requested_resource.resource_id,
                permission=TokenLease.Permission.MOCK,
                issuer_ref="issuer://bkflow/permission-token/{}".format(fingerprint),
                token_fingerprint=fingerprint,
                issued_at=now,
                expires_at=expires_at,
                status=TokenLease.Status.ACTIVE,
            )
            return _handle(lease, issued.secret)

    def revoke_active_leases(self, context, session):
        """Revoke all active credentials before the owning session becomes terminal."""
        if not isinstance(session, DebugSession) or not session.pk:
            raise ValidationError("Debug token session is invalid")
        now = timezone.now()
        with transaction.atomic():
            try:
                locked = DebugSession._base_manager.select_for_update().select_related("run").get(pk=session.pk)
            except DebugSession.DoesNotExist:
                raise ValidationError("Debug token session is invalid") from None
            _validate_authority(context, locked, require_active=False)
            leases = list(
                TokenLease._base_manager.select_for_update()
                .filter(session=locked, status=TokenLease.Status.ACTIVE)
                .order_by("issued_at", "id")
            )
            for lease in leases:
                token = _matching_token(lease, now)
                if token is not None:
                    revoke_resource_token(token.token, revoked_at=now)
                lease.status = TokenLease.Status.REVOKED
                lease.revoked_at = now
                lease.save(update_fields=["status", "revoked_at"])
            return len(leases)

    def revoke_execution_leases(self, context, execution):
        """Revoke execution-owned credentials before an execution becomes terminal."""
        if not isinstance(execution, ExecutionRun) or not execution.pk:
            raise ValidationError("Execution token authority is invalid")
        now = timezone.now()
        with transaction.atomic():
            try:
                locked = ExecutionRun._base_manager.select_for_update().select_related("run").get(pk=execution.pk)
            except ExecutionRun.DoesNotExist:
                raise ValidationError("Execution token authority is invalid") from None
            _validate_execution_authority(context, locked)
            leases = list(
                TokenLease._base_manager.select_for_update()
                .filter(execution=locked, status=TokenLease.Status.ACTIVE)
                .order_by("issued_at", "id")
            )
            for lease in leases:
                token = _matching_token(lease, now)
                if token is not None:
                    revoke_resource_token(token.token, revoked_at=now)
                lease.status = TokenLease.Status.REVOKED
                lease.revoked_at = now
                lease.save(update_fields=["status", "revoked_at"])
            return len(leases)
