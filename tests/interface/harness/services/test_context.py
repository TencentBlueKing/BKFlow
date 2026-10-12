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

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory

from bkflow.harness.contracts import HarnessContextError, TrustedHarnessContext
from bkflow.harness.models import HarnessRun
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.context import authenticated_app_code, correlation_id
from bkflow.space.configs import (
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
    SpaceConfigValueType,
)
from bkflow.space.models import Space, SpaceConfig


@pytest.fixture
def trusted_space(db):
    """Create one configured space whose server-side binding is authoritative."""
    space = Space.objects.create(
        name="Harness trusted context space",
        app_code="trusted-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name=HarnessEnabledConfig.name,
        value_type=SpaceConfigValueType.TEXT.value,
        text_value="true",
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name=HarnessDeploymentConfig.name,
        value_type=SpaceConfigValueType.JSON.value,
        json_value={
            "platform_key": "bkaidev",
            "allowed_scope_types": ["biz", "project"],
            "scope_type": "biz",
            "scope_value": "42",
            "target_environment": "stag",
            "risk_policy_version": "risk-2026.09",
            "mcp_contract_version": "1.0.0",
        },
    )
    return space


def build_request(body, *, app_code="trusted-app", actor="real-actor", trace_id="trace-from-gateway", verified=True):
    """Build a gateway-authenticated request with deliberately untrusted body data."""
    request = APIRequestFactory().post("/api/harness/", body, format="json")
    request.app = SimpleNamespace(bk_app_code=app_code, verified=verified)
    request.user = SimpleNamespace(username=actor, is_authenticated=True)
    request.trace_id = trace_id
    return request


@pytest.mark.django_db
def test_trusted_context_ignores_forged_identity_and_authority_fields(trusted_space):
    """Catch any body field that could replace gateway or server-side authority."""
    request = build_request(
        {
            "platform_key": "forged-platform",
            "platform_app": "forged-app",
            "actor": "forged-actor",
            "space_id": 999999,
            "scope_type": "forged-scope",
            "scope_value": "forged-value",
            "target_environment": "prod",
            "risk_policy_version": "forged-policy",
            "mcp_contract_version": "9.9.9",
            "intent": "restart the declared service",
        }
    )

    context = TrustedHarnessContext.from_request(request, space_id=trusted_space.id)

    assert context == TrustedHarnessContext(
        platform_key="bkaidev",
        platform_app="trusted-app",
        actor="real-actor",
        space_id=trusted_space.id,
        scope_type="biz",
        scope_value="42",
        target_environment="stag",
        policy_version="risk-2026.09",
        mcp_contract_version="1.0.0",
        correlation_id="trace-from-gateway",
    )


@pytest.mark.django_db
def test_trusted_context_is_frozen_and_uses_a_generated_correlation_id_when_missing(trusted_space):
    """Catch mutable trusted fields or a missing audit correlation identifier."""
    context = TrustedHarnessContext.from_request(
        build_request({"actor": "forged"}, trace_id=""),
        space_id=trusted_space.id,
    )

    assert len(context.correlation_id) == 32
    int(context.correlation_id, 16)
    with pytest.raises(FrozenInstanceError):
        context.actor = "forged-actor"


@pytest.mark.django_db
@pytest.mark.parametrize("source", ["trace", "header"])
def test_trusted_context_replaces_secret_shaped_correlation_before_domain_use(trusted_space, source):
    """A raw tracing value must never become the identifier persisted by domain services."""
    raw_correlation = "Bearer C2-CORRELATION-SENTINEL"
    request = build_request({}, trace_id=raw_correlation if source == "trace" else "")
    if source == "header":
        request.META["HTTP_X_REQUEST_ID"] = raw_correlation

    normalized = correlation_id(request)
    context = TrustedHarnessContext.from_request(request, space_id=trusted_space.id)

    assert normalized != raw_correlation
    assert len(normalized) == 32
    int(normalized, 16)
    assert context.correlation_id != raw_correlation
    assert len(context.correlation_id) == 32
    int(context.correlation_id, 16)


def test_direct_trusted_context_replaces_an_unsafe_correlation_identifier():
    """Direct service construction gets the same safe correlation contract as HTTP construction."""
    context = TrustedHarnessContext(
        platform_key="bkfara",
        platform_app="app",
        actor="actor",
        space_id=1,
        scope_type=None,
        scope_value=None,
        target_environment="stag",
        policy_version="p0",
        mcp_contract_version="1.0.0",
        correlation_id="x-bkapi-authorization=C2-SENTINEL",
    )

    assert len(context.correlation_id) == 32
    int(context.correlation_id, 16)


@pytest.mark.django_db
def test_trusted_context_rejects_a_present_but_unverified_gateway_app(trusted_space):
    """Catch an app claim that has a code but was not authenticated by gateway middleware."""
    request = build_request({"intent": "restart"}, verified=False)

    with pytest.raises(HarnessContextError, match="Harness context is unavailable.") as direct_error:
        authenticated_app_code(request)
    with pytest.raises(HarnessContextError, match="Harness context is unavailable.") as context_error:
        TrustedHarnessContext.from_request(request, space_id=trusted_space.id)

    assert direct_error.value.code == "HARNESS_APP_UNAUTHENTICATED"
    assert context_error.value.code == "HARNESS_APP_UNAUTHENTICATED"


@pytest.mark.django_db
def test_maximum_unicode_deployment_binding_builds_context_and_persists_run():
    """Every accepted maximum is writable to the strictest downstream Harness/Template contract."""
    scope_type = "类" * 64
    scope_value = "😀" * 128
    deployment = {
        "platform_key": "平" * 64,
        "allowed_scope_types": [scope_type] + ["类型{}".format(index) for index in range(19)],
        "scope_type": scope_type,
        "scope_value": scope_value,
        "target_environment": "环" * 64,
        "risk_policy_version": "策" * 64,
        "mcp_contract_version": "1.0.0",
    }
    assert HarnessDeploymentConfig.validate(deployment) is True
    space = Space.objects.create(
        name="Harness maximum binding",
        app_code="maximum-binding-app",
        platform_url="https://bkflow.example.com",
        creator="owner",
        updated_by="owner",
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name=HarnessDeploymentConfig.name,
        value_type=SpaceConfigValueType.JSON.value,
        json_value=deployment,
    )
    context = TrustedHarnessContext.from_request(
        build_request({}, app_code=space.app_code),
        space_id=space.id,
    )

    run = HarnessRun.objects.create(
        platform=context.platform_key,
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        scope=canonical_scope(context.scope_type, context.scope_value),
        environment=context.target_environment,
        status="INTENT_CAPTURED",
        policy_version=context.policy_version,
        mcp_contract_version=context.mcp_contract_version,
    )

    run.refresh_from_db()
    assert run.platform == "平" * 64
    assert run.scope == '["{}","{}"]'.format(scope_type, scope_value)
    assert len(run.scope) == 199
    assert len(run.scope.encode("utf-8")) > 255
