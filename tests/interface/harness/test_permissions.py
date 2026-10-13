"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory

from bkflow.harness.permissions import HarnessPermission
from bkflow.space.configs import (
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
    SpaceConfigValueType,
    SuperusersConfig,
)
from bkflow.space.models import Space, SpaceConfig


@pytest.fixture
def harness_space(db):
    """Create one fully authorized Harness space."""
    space = Space.objects.create(
        name="Harness authorization space",
        app_code="trusted-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    configs = (
        (HarnessEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (SuperusersConfig.name, SpaceConfigValueType.JSON.value, "", ["trusted-user"]),
        (
            HarnessDeploymentConfig.name,
            SpaceConfigValueType.JSON.value,
            "",
            {
                "platform_key": "bkaidev",
                "allowed_scope_types": ["biz"],
                "scope_type": None,
                "scope_value": None,
                "target_environment": "stag",
                "risk_policy_version": "risk-2026.09",
                "mcp_contract_version": "1.0.0",
            },
        ),
    )
    for name, value_type, text_value, json_value in configs:
        SpaceConfig.objects.create(
            space_id=space.id,
            name=name,
            value_type=value_type,
            text_value=text_value,
            json_value=json_value,
        )
    return space


def request_for(
    space,
    *,
    app_code="trusted-app",
    username="trusted-user",
    authenticated=True,
    include_app=True,
    verified=True,
):
    """Build an authenticated gateway request addressed by a route space only."""
    request = APIRequestFactory().post("/api/harness/", {"space_id": 999999}, format="json")
    if include_app:
        request.app = SimpleNamespace(bk_app_code=app_code, verified=verified)
    request.user = SimpleNamespace(username=username, is_authenticated=authenticated)
    view = SimpleNamespace(kwargs={"space_id": str(space.id)})
    return request, view


def assert_denied(permission, request, view, code):
    """Assert a denial is stable and cannot disclose request-supplied secrets."""
    assert permission.has_permission(request, view) is False
    assert request.harness_authorization_error.code == code
    assert request.harness_authorization_error.message == "Harness access denied."
    assert "999999" not in request.harness_authorization_error.message


@pytest.mark.django_db
def test_harness_permission_requires_an_authenticated_app(harness_space):
    """Catch a Harness route that accepts a request without gateway app identity."""
    request, view = request_for(harness_space, include_app=False)

    assert_denied(HarnessPermission(), request, view, "HARNESS_APP_UNAUTHENTICATED")


@pytest.mark.django_db
def test_harness_permission_rejects_an_unverified_app_claim(harness_space):
    """Catch a present gateway app object whose verification bit is false."""
    request, view = request_for(harness_space, verified=False)

    assert_denied(HarnessPermission(), request, view, "HARNESS_APP_UNAUTHENTICATED")


@pytest.mark.django_db
def test_harness_permission_requires_an_authenticated_user(harness_space):
    """Catch a Harness route that accepts an unauthenticated gateway user."""
    request, view = request_for(harness_space, authenticated=False)

    assert_denied(HarnessPermission(), request, view, "HARNESS_USER_UNAUTHENTICATED")


@pytest.mark.django_db
def test_harness_permission_requires_the_app_to_own_the_route_space(harness_space):
    """Catch an app identity that tries to enter another app's space."""
    request, view = request_for(harness_space, app_code="other-app")

    assert_denied(HarnessPermission(), request, view, "HARNESS_APP_SPACE_FORBIDDEN")


@pytest.mark.django_db
def test_harness_permission_requires_the_user_to_administer_the_route_space(harness_space):
    """Catch a gateway user who is not authorized by the existing space policy."""
    request, view = request_for(harness_space, username="other-user")

    assert_denied(HarnessPermission(), request, view, "HARNESS_USER_SPACE_FORBIDDEN")


@pytest.mark.django_db
@pytest.mark.parametrize("enabled", [None, "false"])
def test_harness_permission_requires_the_feature_flag(harness_space, enabled):
    """Catch missing and explicit-off flags before any Harness request is accepted."""
    config = SpaceConfig.objects.get(space_id=harness_space.id, name=HarnessEnabledConfig.name)
    if enabled is None:
        config.delete()
    else:
        config.text_value = enabled
        config.save(update_fields=["text_value"])
    request, view = request_for(harness_space)

    assert_denied(HarnessPermission(), request, view, "HARNESS_DISABLED")


@pytest.mark.django_db
def test_harness_permission_allows_only_the_complete_authorization_conjunction(harness_space):
    """Catch an OR-composed permission that permits a partial authorization state."""
    request, view = request_for(harness_space)

    assert HarnessPermission().has_permission(request, view) is True
    assert request.harness_context.platform_app == "trusted-app"
    assert request.harness_context.space_id == harness_space.id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mode,app_tenant,header,user_tenant,allowed",
    [
        ("single", "tenant-a", None, "tenant-a", True),
        ("global", None, "tenant-a", "tenant-a", True),
        ("single", "tenant-b", None, "tenant-b", False),
        ("single", "tenant-a", "tenant-b", "tenant-a", False),
        ("global", None, None, "tenant-a", False),
        ("global", None, "tenant-b", "tenant-b", False),
        ("global", None, "tenant-a", "tenant-b", False),
        ("single", "tenant-a", None, None, False),
        (None, None, "tenant-a", "tenant-a", False),
    ],
)
def test_harness_keeps_master_tenant_boundary_even_with_admin_and_auth_exemption(
    harness_space, settings, mode, app_tenant, header, user_tenant, allowed
):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.BK_APIGW_REQUIRE_EXEMPT = True
    harness_space.tenant_id = "tenant-a"
    harness_space.save(update_fields=["tenant_id"])
    request, view = request_for(harness_space)
    request.app.tenant_mode = mode
    request.app.tenant_id = app_tenant
    request.user.tenant_id = user_tenant
    if header is not None:
        request.META["HTTP_X_BK_TENANT_ID"] = header
    assert HarnessPermission().has_permission(request, view) is allowed
    if not allowed:
        assert not hasattr(request, "harness_context")
