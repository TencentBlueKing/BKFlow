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
from uuid import UUID

import pytest

from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.space.configs import SpaceConfigValueType
from bkflow.space.models import SpaceConfig

VALID_DEPLOYMENT = {
    "platform_key": "bkaidev",
    "allowed_scope_types": ["biz"],
    "scope_type": None,
    "scope_value": None,
    "target_environment": "stage",
    "risk_policy_version": "p0-v1",
    "mcp_contract_version": "1.0.0",
}


def _enable_harness(space, deployment=None, users=None):
    SpaceConfig.objects.create(
        space_id=space.id,
        name="harness_enabled",
        value_type=SpaceConfigValueType.TEXT.value,
        text_value="true",
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="harness_deployment",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=deployment or VALID_DEPLOYMENT,
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="superusers",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=users or ["alice"],
    )


def _request(app_code="bkflow_harness", username="alice", data=None, trace_id="corr-1"):
    return SimpleNamespace(
        app=SimpleNamespace(bk_app_code=app_code),
        user=SimpleNamespace(username=username, is_authenticated=True),
        data=data or {},
        trace_id=trace_id,
    )


@pytest.mark.django_db
def test_from_request_uses_trusted_sources_and_ignores_forged_body(space):
    """可信上下文字段来自网关身份和部署绑定，忽略 body 伪造值。"""
    _enable_harness(space)
    request = _request(
        data={
            "platform_key": "forged-platform",
            "platform_app": "evil_app",
            "actor": "mallory",
            "space_id": 99999,
            "scope_type": "biz",
            "scope_value": "hacked",
            "target_environment": "prod",
            "policy_version": "forged",
            "mcp_contract_version": "9.9.9",
        }
    )

    context = TrustedHarnessContext.from_request(request, space_id=space.id)

    assert context.platform_key == "bkaidev"
    assert context.platform_app == "bkflow_harness"
    assert context.actor == "alice"
    assert context.space_id == space.id
    assert context.scope_type is None
    assert context.scope_value is None
    assert context.target_environment == "stage"
    assert context.policy_version == "p0-v1"
    assert context.mcp_contract_version == "1.0.0"
    assert context.correlation_id == "corr-1"


@pytest.mark.django_db
def test_from_request_generates_correlation_id_when_missing(space):
    """没有 request.trace_id 时生成 UUID。"""
    _enable_harness(space)
    request = _request()
    del request.trace_id

    context = TrustedHarnessContext.from_request(request, space_id=space.id)

    UUID(context.correlation_id)
