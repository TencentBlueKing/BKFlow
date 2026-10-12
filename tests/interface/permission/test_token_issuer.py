"""Service-level contracts for issuing and revoking BKFlow resource tokens."""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from bkflow.permission.grants import Grant
from bkflow.permission.models import Token
from bkflow.permission.token_issuer import (
    TokenIssueContext,
    TokenResource,
    TokenRevokeContext,
    issue_resource_token,
    revoke_resource_token,
    revoke_resource_tokens,
)
from bkflow.space.models import Space, SpaceConfig
from tests.utils.token import create_token


@pytest.fixture
def token_context(db):
    space = Space.objects.create(app_code="trusted-app", platform_url="http://example.test", name="token-space")
    SpaceConfig.objects.create(
        space_id=space.id,
        name="token_expiration",
        text_value="1h",
        value_type="TEXT",
    )
    return TokenIssueContext(platform_app="trusted-app", actor="dannydeng", space_id=space.id)


@pytest.fixture(autouse=True)
def valid_resource(monkeypatch):
    calls = []

    def validate(instance):
        calls.append((instance.space_id, instance.resource_type, instance.resource_id))

    monkeypatch.setattr("bkflow.permission.token_issuer.TokenResourceValidator.validate", validate)
    return calls


@pytest.mark.django_db
def test_issue_binds_trusted_context_validates_resource_before_create_and_returns_safe_result(
    token_context, valid_resource
):
    issued = issue_resource_token(
        token_context,
        TokenResource(resource_type="TEMPLATE", resource_id="42"),
        "MOCK",
    )

    assert valid_resource == [(token_context.space_id, "TEMPLATE", "42")]
    assert Token.objects.filter(
        token=issued.secret,
        user="dannydeng",
        space_id=token_context.space_id,
        grants__resource_type="TEMPLATE",
        grants__resource_id="42",
        grants__permission_type="MOCK",
    ).exists()
    assert Token.objects.get(pk=issued.secret).get_grants() == (Grant("TEMPLATE", "42", "MOCK"),)
    assert issued.reused is False
    assert issued.secret not in repr(issued)
    with pytest.raises(TypeError):
        import pickle

        pickle.dumps(issued)


@pytest.mark.django_db
def test_issue_reuses_and_only_configuration_renews_legacy_token(token_context):
    resource = TokenResource(resource_type="TEMPLATE", resource_id="42")
    SpaceConfig.objects.create(
        space_id=token_context.space_id,
        name="token_auto_renewal",
        text_value="false",
        value_type="TEXT",
    )
    first = issue_resource_token(token_context, resource, "MOCK")
    token = Token.objects.get(token=first.secret)
    fixed_expiry = timezone.now() + datetime.timedelta(minutes=20)
    token.expired_time = fixed_expiry
    token.save(update_fields=["expired_time"])

    second = issue_resource_token(token_context, resource, "MOCK")
    token.refresh_from_db()
    assert second.secret == first.secret
    assert second.reused is True
    assert abs((token.expired_time - fixed_expiry).total_seconds()) < 1

    renewal = SpaceConfig.objects.get(space_id=token_context.space_id, name="token_auto_renewal")
    renewal.text_value = "true"
    renewal.save(update_fields=["text_value"])
    third = issue_resource_token(token_context, resource, "MOCK")
    token.refresh_from_db()
    assert third.secret == first.secret
    assert token.expired_time > fixed_expiry


@pytest.mark.django_db
def test_explicit_expiry_and_no_reuse_create_session_private_tokens(token_context):
    resource = TokenResource(resource_type="SCOPE", resource_id="project_902")
    expiry = timezone.now() + datetime.timedelta(minutes=5)

    first = issue_resource_token(token_context, resource, "MOCK", expires_at=expiry, reuse_existing=False)
    second = issue_resource_token(token_context, resource, "MOCK", expires_at=expiry, reuse_existing=False)

    assert first.secret != second.secret
    assert first.expires_at == expiry
    assert (
        Token.objects.filter(
            user=token_context.actor,
            space_id=token_context.space_id,
            grants__resource_type="SCOPE",
            grants__resource_id="project_902",
            grants__permission_type="MOCK",
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_issuer_preserves_legacy_character_length_semantics(valid_resource):
    actor = "用" * 20
    space = Space.objects.create(app_code="trusted-app", platform_url="http://example.test", name="unicode-space")
    SpaceConfig.objects.create(
        space_id=space.id,
        name="token_expiration",
        text_value="1h",
        value_type="TEXT",
    )

    issued = issue_resource_token(
        TokenIssueContext(platform_app="trusted-app", actor=actor, space_id=space.id),
        TokenResource(resource_type="TEMPLATE", resource_id="模" * 20),
        "MOCK",
    )

    assert issued.actor == actor
    assert issued.resource_id == "模" * 20


@pytest.mark.django_db
def test_issue_rejects_untrusted_app_user_space_and_bad_expiry_before_token_write(token_context):
    resource = TokenResource(resource_type="TEMPLATE", resource_id="42")
    invalid_contexts = [
        TokenIssueContext(platform_app="foreign-app", actor=token_context.actor, space_id=token_context.space_id),
        TokenIssueContext(platform_app=token_context.platform_app, actor="", space_id=token_context.space_id),
        TokenIssueContext(platform_app=token_context.platform_app, actor=token_context.actor, space_id=0),
    ]
    for context in invalid_contexts:
        with pytest.raises(ValidationError):
            issue_resource_token(context, resource, "MOCK")
    with pytest.raises(ValidationError):
        issue_resource_token(
            token_context,
            resource,
            "MOCK",
            expires_at=timezone.now() - datetime.timedelta(seconds=1),
            reuse_existing=False,
        )
    assert Token.objects.count() == 0


@pytest.mark.django_db
def test_revoke_exact_token_and_filtered_tokens_without_returning_secret(token_context):
    resource = TokenResource(resource_type="TEMPLATE", resource_id="42")
    first = issue_resource_token(token_context, resource, "MOCK", reuse_existing=False)
    second = issue_resource_token(token_context, resource, "MOCK", reuse_existing=False)

    assert revoke_resource_token(first.secret) == 1
    assert Token.objects.get(token=first.secret).has_expired()
    assert not Token.objects.get(token=second.secret).has_expired()

    count = revoke_resource_tokens(
        TokenRevokeContext(platform_app=token_context.platform_app, space_id=token_context.space_id),
        {"resource_type": "TEMPLATE", "resource_id": "42", "permission_type": "MOCK"},
    )
    assert count == 2
    assert Token.objects.get(token=second.secret).has_expired()


@pytest.mark.django_db
@pytest.mark.parametrize("broken", [False, True])
def test_issuer_never_reuses_broader_or_incomplete_grant_set(token_context, broken):
    grants = [Grant("TEMPLATE", "42", "MOCK"), Grant("TEMPLATE", "42", "EDIT")]
    existing = create_token(space_id=token_context.space_id, user=token_context.actor, grants=grants)
    if broken:
        existing.grants.filter(permission_type="EDIT").delete()
    issued = issue_resource_token(token_context, TokenResource("TEMPLATE", "42"), "MOCK")
    assert issued.secret != existing.pk
    assert Token.objects.get(pk=issued.secret).get_grants() == (grants[0],)
