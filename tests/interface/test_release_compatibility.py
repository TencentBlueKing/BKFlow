"""发布规范回归：平台协议、用户时区、存量凭证与管理员授权。"""

import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from bkflow.space.models import Space, SpaceConfig
from bkflow.utils.crypt import BaseCrypt, CredentialCrypt
from bkflow.utils.message import send_message
from bkflow.utils.models import SecretSingleJsonField
from bkflow.utils.platform import use_apigw
from bkflow.utils.time_zone import get_user_timezone


@pytest.mark.parametrize(
    "multi,mode,expected", [(False, "legacy", False), (False, "apigw", True), (True, "legacy", True)]
)
def test_platform_mode_is_independent_from_single_tenant(multi, mode, expected):
    """单租户新平台走 APIGW，多租户不能回退旧 ESB。"""
    with override_settings(ENABLE_MULTI_TENANT_MODE=multi, BKFLOW_PLATFORM_API_MODE=mode):
        assert use_apigw() is expected


@override_settings(ENABLE_MULTI_TENANT_MODE=False, BKFLOW_PLATFORM_API_MODE="apigw")
def test_single_tenant_notification_uses_apigw():
    """新平台单租户发送通知也带 default 租户，不访问旧客户端。"""
    with patch("bkflow.utils.message.get_client_by_username"), patch(
        "bkflow.utils.message.send_cmsi_message", return_value=("v1_send_mail", {}, {"result": True})
    ) as sender, patch("bkflow.utils.message.get_client_by_user") as legacy:
        assert send_message("u", ["mail"], "r", "title", "body") == (False, "")
        assert sender.call_args.kwargs["tenant_id"] == "default"
        legacy.assert_not_called()


@pytest.mark.parametrize("multi", [False, True])
@pytest.mark.parametrize("source", ["standard", "internal", "cookie", "session"])
def test_timezone_preferences_work_in_both_modes(multi, source):
    """有效显式偏好在两种租户模式生效，不请求登录平台。"""
    request = SimpleNamespace(headers={}, COOKIES={}, session={}, user=SimpleNamespace(username="u", tenant_id="t"))
    mapping, key = {
        "standard": (request.headers, "blueking-timezone"),
        "internal": (request.headers, settings.APP_INTERNAL_TIME_ZONE_HEADER_KEY),
        "cookie": (request.COOKIES, "blueking_timezone"),
        "session": (request.session, "blueking_timezone"),
    }[source]
    mapping[key] = "Europe/Paris"
    with override_settings(ENABLE_MULTI_TENANT_MODE=multi), patch(
        "bkflow.utils.time_zone.get_client_by_request"
    ) as api:
        assert get_user_timezone(request) == "Europe/Paris"
        api.assert_not_called()


@override_settings(ENABLE_MULTI_TENANT_MODE=False, BKFLOW_PLATFORM_API_MODE="apigw")
def test_single_tenant_timezone_fetches_default_tenant_and_validates_response():
    """新单租户从平台取时区，非法结果回落到部署默认值。"""
    request = SimpleNamespace(headers={"blueking-timezone": "bad"}, COOKIES={}, user=SimpleNamespace(username="u"))
    with patch("bkflow.utils.time_zone.get_client_by_request") as client:
        api = client.return_value.api.get_bk_token_userinfo
        api.return_value = {"data": {"time_zone": "Europe/Paris"}}
        assert get_user_timezone(request, use_cache=False) == "Europe/Paris"
        assert api.call_args.kwargs["headers"] == {"X-Bk-Tenant-Id": "default"}
        api.return_value = {"data": {"time_zone": "not-a-zone"}}
        assert get_user_timezone(request, use_cache=False) == settings.TIME_ZONE


def test_sm4_roundtrip_random_nonce_and_legacy_ciphertext():
    """SM4 采用随机 nonce；切换配置不影响新旧密文读取，AES 格式与旧版本一致。"""
    key = "test-private-key-for-credentials-32"
    old = BaseCrypt(key)
    crypt = CredentialCrypt(key)
    legacy = old.encrypt("secret-中文")
    with override_settings(BKFLOW_CREDENTIAL_CIPHER="SM4"):
        first, second = crypt.encrypt("secret-中文"), crypt.encrypt("secret-中文")
        assert first != second
        assert first.startswith(CredentialCrypt.SM4_PREFIX)
        assert crypt.decrypt(first) == "secret-中文"
        assert crypt.decrypt(legacy) == "secret-中文"
    with override_settings(BKFLOW_CREDENTIAL_CIPHER="AES"):
        assert crypt.encrypt("secret-中文") == legacy
        assert crypt.decrypt(second) == "secret-中文"


def test_sm4_credentials_reject_corruption_and_wrong_key():
    """有标识的密文认证失败必须报错，不能伪装成历史明文。"""
    with override_settings(BKFLOW_CREDENTIAL_CIPHER="SM4"):
        encrypted = CredentialCrypt(settings.PRIVATE_SECRET).encrypt("secret")
    with pytest.raises(Exception):
        CredentialCrypt("different-key").decrypt(encrypted)
    with pytest.raises(Exception):
        SecretSingleJsonField().from_db_value(
            json.dumps({"password": CredentialCrypt.SM4_PREFIX + "broken"}), None, None
        )


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_superuser_authorization_is_atomic_and_system_only():
    """任何一个用户不属于 system 时整批拒绝，不创建未知用户。"""
    User = apps.get_model("account", "User")
    system = User.objects.create(username="system_operator", tenant_id="system")
    other = User.objects.create(username="tenant_operator", tenant_id="tenant-a")
    with pytest.raises(CommandError):
        call_command("sync_superuser", usernames=f"{system.username},{other.username}")
    system.refresh_from_db()
    assert not system.is_superuser
    with pytest.raises(CommandError):
        call_command("sync_superuser", usernames="unknown")
    assert not User.objects.filter(username="unknown").exists()
    call_command("sync_superuser", usernames=system.username)
    system.refresh_from_db()
    assert system.is_superuser and system.is_staff


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_single_tenant_superuser_initialization_is_preserved():
    """存量单租户仍可按原命令创建管理员。"""
    call_command("sync_superuser", usernames="legacy_admin")
    assert apps.get_model("account", "User").objects.get(username="legacy_admin").is_superuser


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_space_admin_grant_checks_tenant_and_is_idempotent():
    """空间管理员只获得本租户空间权限，重复授权不会产生重复成员。"""
    User = apps.get_model("account", "User")
    user = User.objects.create(username="tenant_admin", tenant_id="tenant-a")
    space = Space.objects.create(name="space", tenant_id="tenant-a")
    args = {"username": user.username, "tenant_id": "tenant-a", "space_id": space.id, "stdout": io.StringIO()}
    call_command("grant_space_admin", **args)
    call_command("grant_space_admin", **args)
    assert SpaceConfig.get_config(space.id, "superusers") == [user.username]
    user.refresh_from_db()
    assert not user.is_superuser and not user.is_staff
    with pytest.raises(CommandError):
        call_command("grant_space_admin", **{**args, "tenant_id": "tenant-b"})


@pytest.mark.django_db
def test_sm4_orm_storage_and_aes_rewrite():
    """真实字段存储不落明文，新代码可将 SM4 凭证重新保存为旧格式。"""
    from django.db import connection

    from bkflow.space.models import Credential, CredentialType

    space = Space.objects.create(name="crypto")
    with override_settings(BKFLOW_CREDENTIAL_CIPHER="SM4"):
        credential = Credential.create_credential(
            space_id=space.id,
            name="sm4",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app", "bk_app_secret": "secret"},
            creator="user",
        )
    with connection.cursor() as cursor:
        cursor.execute("SELECT content FROM space_credential WHERE id=%s", [credential.id])
        stored = cursor.fetchone()[0]
        if isinstance(stored, str):
            stored = json.loads(stored)
    assert stored["bk_app_secret"].startswith(CredentialCrypt.SM4_PREFIX)
    with override_settings(BKFLOW_CREDENTIAL_CIPHER="AES"):
        loaded = Credential.objects.get(pk=credential.pk)
        assert loaded.content == {"bk_app_code": "app", "bk_app_secret": "secret"}
        loaded.save()
    with connection.cursor() as cursor:
        cursor.execute("SELECT content FROM space_credential WHERE id=%s", [credential.id])
        stored = cursor.fetchone()[0]
        if isinstance(stored, str):
            stored = json.loads(stored)
    assert BaseCrypt(settings.PRIVATE_SECRET).decrypt(stored["bk_app_secret"]) == "secret"


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_tenant_denial_is_translated():
    from django.utils import translation
    from rest_framework.exceptions import PermissionDenied

    from bkflow.utils.tenant import get_request_tenant_id

    with translation.override("en"), pytest.raises(PermissionDenied) as error:
        get_request_tenant_id(SimpleNamespace(user=SimpleNamespace(username="u")))
    assert str(error.value.detail) == "The current user has no tenant identity"


@pytest.mark.parametrize(
    "mode,tenant,allowed", [("apigw", "default", True), ("apigw", "other", False), ("legacy", "default", False)]
)
@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_single_tenant_approval_initialization(mode, tenant, allowed):
    path = "bkflow.contrib.itsm_workflow.management.commands.migrate_itsm_workflow.get_client_by_username"
    with override_settings(BKFLOW_PLATFORM_API_MODE=mode), patch(path) as client:
        api = client.return_value.api
        api.system_create.return_value = api.system_migrate.return_value = {"result": True}
        if allowed:
            call_command("init_tenant", tenant_id=tenant, stdout=io.StringIO())
            assert api.system_create.call_args.kwargs["headers"] == {"X-Bk-Tenant-Id": "default"}
            api.system_migrate.assert_called_once()
        else:
            with pytest.raises(CommandError):
                call_command("init_tenant", tenant_id=tenant)
            client.assert_not_called()


@override_settings(ENABLE_MULTI_TENANT_MODE=False, BKFLOW_PLATFORM_API_MODE="apigw")
def test_old_approval_requires_explicit_service_in_modern_mode():
    from django.core.exceptions import ImproperlyConfigured

    import env
    from bkflow.contrib.api.collections.itsm import _get_itsm_api

    with patch.object(env, "BK_ITSM_API_ENTRY", ""):
        with pytest.raises(ImproperlyConfigured):
            _get_itsm_api("get_ticket_info")
    with patch.object(env, "BK_ITSM_API_ENTRY", "https://old-itsm.example/api/"):
        assert _get_itsm_api("get_ticket_info") == "https://old-itsm.example/api/get_ticket_info/"


@pytest.mark.parametrize("language", ["en", "zh-cn"])
@override_settings(ENABLE_MULTI_TENANT_MODE=False, BKFLOW_PLATFORM_API_MODE="apigw")
def test_page_context_exposes_timezone_protocol_and_configurable_docs(language):
    import env
    from bkflow.interface.context_processors import bkflow_settings

    request = SimpleNamespace(
        headers={"blueking-timezone": "Europe/Paris"},
        COOKIES={"blueking_language": language},
        user=SimpleNamespace(username="u"),
    )
    with patch(
        "bkflow.interface.context_processors.EnvironmentVariables.objects.get_var", side_effect=lambda k, d: d
    ), patch.object(env, "BKFLOW_DOC_VERSION", ""), patch.object(env, "BKFLOW_DOC_URL_EN", ""), patch.object(
        env, "BKFLOW_DOC_URL_ZH", ""
    ):
        context = bkflow_settings(request)
        assert context["TIMEZONE"] == "Europe/Paris"
        assert context["USE_APIGW"] is True and context["TENANT_ID"] == "default"
        assert "/1.8/" not in context["BK_DOC_URL"]
        with patch.object(
            env, "BKFLOW_DOC_URL_EN" if language == "en" else "BKFLOW_DOC_URL_ZH", "https://docs.example/custom"
        ):
            assert bkflow_settings(request)["BK_DOC_URL"] == "https://docs.example/custom"
        with patch.object(env, "BKFLOW_DOC_VERSION", "1.11"):
            assert "/BKFlow/1.11/" in bkflow_settings(request)["BK_DOC_URL"]


@pytest.mark.parametrize("multi", [False, True])
def test_timezone_middleware_localizes_api_values(multi):
    from datetime import datetime
    from datetime import timezone as dt_timezone

    from django.utils import timezone
    from rest_framework import serializers

    from bkflow.utils.middlewares import TimezoneMiddleware

    request = SimpleNamespace(
        headers={"blueking-timezone": "Europe/Paris"},
        COOKIES={},
        session={},
        user=SimpleNamespace(username="u", tenant_id="t"),
    )
    try:
        with override_settings(ENABLE_MULTI_TENANT_MODE=multi):
            TimezoneMiddleware(lambda request: None).process_view(request, None, (), {})
        assert request.session["blueking_timezone"] == "Europe/Paris"
        assert (
            serializers.DateTimeField()
            .to_representation(datetime(2026, 7, 1, 0, 0, tzinfo=dt_timezone.utc))
            .endswith("02:00:00+02:00")
        )
    finally:
        timezone.deactivate()


@pytest.mark.django_db
def test_trigger_persists_creation_timezone_and_preserves_it_on_edit():
    from django.utils import timezone

    from bkflow.template.models import Trigger
    from bkflow.template.serializers.trigger import ConfigSerializer
    from bkflow.utils.pipeline import build_default_pipeline_tree

    space = Space.objects.create(name="trigger-space")
    template = SimpleNamespace(
        id=1,
        space_id=space.pk,
        name="trigger-template",
        pipeline_tree=build_default_pipeline_tree(),
        scope_type="",
        scope_value="",
        creator="u",
        notify_config={},
    )
    config = {
        "cron": {"minute": "0", "hour": "9", "day_of_month": "*", "month_of_year": "*", "day_of_week": "*"},
        "constants": {},
        "mode": "form",
    }
    with patch("bkflow.template.models.TaskComponentClient") as client:
        client.return_value.create_periodic_task.return_value = {"result": True}
        client.return_value.update_periodic_task.return_value = {"result": True}
        with timezone.override("Europe/Paris"):
            trigger = Trigger.objects.create_trigger({"name": "daily", "config": dict(config)}, template, "u")
        assert trigger.config["timezone"] == "Europe/Paris"
        assert client.return_value.create_periodic_task.call_args.kwargs["data"]["cron"]["timezone"] == "Europe/Paris"
        with timezone.override("Asia/Tokyo"):
            Trigger.objects.update_trigger(trigger, {"config": dict(config)}, template, "u")
        assert client.return_value.update_periodic_task.call_args.kwargs["data"]["cron"]["timezone"] == "Europe/Paris"
    serializer = ConfigSerializer(data={**config, "timezone": "invalid"})
    assert not serializer.is_valid()
