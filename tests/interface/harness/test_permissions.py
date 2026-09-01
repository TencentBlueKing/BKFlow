"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from types import SimpleNamespace

import pytest

from bkflow.harness.exceptions import HarnessAuthorizationError
from bkflow.harness.permissions import HarnessPermission, authorize_harness_request
from bkflow.space.configs import SpaceConfigValueType
from bkflow.space.models import Space, SpaceConfig

VALID_DEPLOYMENT = {
    "platform_key": "bkaidev",
    "allowed_scope_types": ["biz"],
    "scope_type": None,
    "scope_value": None,
    "target_environment": "stage",
    "risk_policy_version": "p0-v1",
    "mcp_contract_version": "1.0.0",
}


def _enable_harness(space, enabled="true", deployment=None, users=None):
    SpaceConfig.objects.create(
        space_id=space.id,
        name="harness_enabled",
        value_type=SpaceConfigValueType.TEXT.value,
        text_value=enabled,
    )
    if deployment is not None:
        SpaceConfig.objects.create(
            space_id=space.id,
            name="harness_deployment",
            value_type=SpaceConfigValueType.JSON.value,
            json_value=deployment,
        )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="superusers",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=users if users is not None else ["alice"],
    )


def _request(app_code="bkflow_harness", username="alice", authenticated=True, app=True, data=None):
    request = SimpleNamespace(
        user=SimpleNamespace(username=username, is_authenticated=authenticated),
        data=data or {},
        trace_id="corr-1",
    )
    if app:
        request.app = SimpleNamespace(bk_app_code=app_code)
    else:
        request.app = None
    return request


def _view(space_id):
    return SimpleNamespace(kwargs={"space_id": space_id})


@pytest.mark.django_db
def test_permission_requires_all_predicates(space):
    """五个谓词同时成立才放行。"""
    _enable_harness(space, deployment=VALID_DEPLOYMENT)
    request = _request()
    authorize_harness_request(request, space.id)
    assert HarnessPermission().has_permission(request, _view(space.id)) is True


@pytest.mark.django_db
def test_missing_authenticated_app(space):
    """缺少认证应用时拒绝。"""
    _enable_harness(space, deployment=VALID_DEPLOYMENT)
    request = _request(app=False)
    with pytest.raises(HarnessAuthorizationError) as exc:
        authorize_harness_request(request, space.id)
    assert exc.value.code == "HARNESS_APP_UNAUTHENTICATED"
    assert HarnessPermission().has_permission(request, _view(space.id)) is False


@pytest.mark.django_db
def test_missing_authenticated_user(space):
    """缺少认证用户时拒绝。"""
    _enable_harness(space, deployment=VALID_DEPLOYMENT)
    request = _request(authenticated=False, username="")
    with pytest.raises(HarnessAuthorizationError) as exc:
        authorize_harness_request(request, space.id)
    assert exc.value.code == "HARNESS_USER_UNAUTHENTICATED"


@pytest.mark.django_db
def test_missing_app_to_space_authorization(space):
    """应用与空间绑定不一致时拒绝。"""
    _enable_harness(space, deployment=VALID_DEPLOYMENT)
    request = _request(app_code="other_app")
    with pytest.raises(HarnessAuthorizationError) as exc:
        authorize_harness_request(request, space.id)
    assert exc.value.code == "HARNESS_APP_FORBIDDEN"
    assert "secret" not in str(exc.value).lower()


@pytest.mark.django_db
def test_missing_user_to_space_authorization(space):
    """用户不在空间授权范围内时拒绝。"""
    _enable_harness(space, deployment=VALID_DEPLOYMENT, users=["bob"])
    request = _request(username="alice")
    with pytest.raises(HarnessAuthorizationError) as exc:
        authorize_harness_request(request, space.id)
    assert exc.value.code == "HARNESS_USER_FORBIDDEN"


@pytest.mark.django_db
def test_missing_harness_enabled_defaults_false(space):
    """未配置开关时默认关闭。"""
    SpaceConfig.objects.create(
        space_id=space.id,
        name="superusers",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=["alice"],
    )
    request = _request()
    with pytest.raises(HarnessAuthorizationError) as exc:
        authorize_harness_request(request, space.id)
    assert exc.value.code == "HARNESS_DISABLED"


@pytest.mark.django_db
def test_explicit_harness_enabled_false(space):
    """显式关闭开关时拒绝。"""
    _enable_harness(space, enabled="false", deployment=VALID_DEPLOYMENT)
    request = _request()
    with pytest.raises(HarnessAuthorizationError) as exc:
        authorize_harness_request(request, space.id)
    assert exc.value.code == "HARNESS_DISABLED"


@pytest.mark.django_db
def test_unknown_space_is_forbidden(space):
    """不存在的空间不能成为授权依据。"""
    request = _request()
    with pytest.raises(HarnessAuthorizationError) as exc:
        authorize_harness_request(request, space.id + 1000)
    assert exc.value.code == "HARNESS_APP_FORBIDDEN"


@pytest.mark.django_db
def test_forged_body_identity_cannot_authorize_another_space(space):
    """body 中的空间/身份不能覆盖路由空间。"""
    _enable_harness(space, deployment=VALID_DEPLOYMENT)
    other = Space.objects.create(name="other-space", app_code="other_app", platform_url="http://example.com")
    request = _request(data={"space_id": other.id, "platform_app": "other_app", "actor": "mallory"})
    authorize_harness_request(request, space.id)
    with pytest.raises(HarnessAuthorizationError):
        authorize_harness_request(request, other.id)
