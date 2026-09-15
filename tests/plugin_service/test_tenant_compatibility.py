"""旧 PaaS 认证和多租户网关认证互不串用。"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings

from plugin_service.api import _get_request_tenant_id
from plugin_service.plugin_client import PluginServiceApiClient


@pytest.mark.parametrize("enabled", [False, True])
def test_request_tenant_is_absent_when_switch_is_off(enabled):
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        request = SimpleNamespace(user=SimpleNamespace(tenant_id="tenant-a"))
        assert _get_request_tenant_id(request) == ("tenant-a" if enabled else None)


@pytest.mark.parametrize("enabled", [False, True])
def test_paas_auth_switch(enabled):
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled), patch.multiple(
        "plugin_service.plugin_client.env",
        PAASV3_APIGW_API_TOKEN="legacy-token",
        PLUGIN_SERVICE_APIGW_APP_CODE="app",
        PLUGIN_SERVICE_APIGW_APP_SECRET="secret",
    ):
        _, params, headers = PluginServiceApiClient._prepare_paas_request(
            ["system", "bk_plugins"], tenant_id="tenant-a"
        )
        if enabled:
            assert params == {}
            assert headers["X-Bk-Tenant-Id"] == "tenant-a"
            assert json.loads(headers["X-Bkapi-Authorization"])["bk_app_code"] == "app"
        else:
            assert params == {"private_token": "legacy-token"}
            assert headers == {}
