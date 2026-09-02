"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
    10|CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import json

import pytest
from django.test import override_settings

from bkflow.apigw.serializers.harness.common import (
    ENVELOPE_FIELDS,
    HarnessEnvelopeSerializer,
)
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


def _enable_harness(space, users=None):
    SpaceConfig.objects.create(
        space_id=space.id, name="harness_enabled", value_type=SpaceConfigValueType.TEXT.value, text_value="true"
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="harness_deployment",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=VALID_DEPLOYMENT,
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="superusers",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=users or ["username"],
    )


@pytest.fixture
def space(db):
    return Space.objects.create(name="harness-api", app_code="test", platform_url="http://example.com")


def _post(client, space, path, payload):
    return client.post(
        "/apigw/space/{}/harness/{}/".format(space.id, path),
        data=json.dumps(payload),
        content_type="application/json",
    )


@override_settings(BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",))
@pytest.mark.django_db
def test_search_valid_request_calls_facade(client, space, monkeypatch):
    """合法检索只做传输校验并调用 Facade。"""
    _enable_harness(space)
    monkeypatch.setattr(
        "bkflow.apigw.views.harness.dispatch.HarnessFacade.search_workflow_capabilities",
        lambda self, context, request: {
            "ok": True,
            "run_id": None,
            "revision_id": None,
            "plan_hash": None,
            "status": None,
            "summary": "found 1 capabilities",
            "artifact_refs": [],
            "errors": [],
            "next_actions": [],
            "correlation_id": context.correlation_id,
        },
    )
    resp = _post(client, space, "search_workflow_capabilities", {"query": "重启", "platform_app": "evil"})
    body = resp.json()
    assert resp.status_code == 200
    assert body["result"] is True
    assert set(body["data"]) == set(ENVELOPE_FIELDS)
    assert HarnessEnvelopeSerializer(data=body["data"]).is_valid()


@override_settings(BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",))
@pytest.mark.django_db
def test_malformed_and_auth_failures(client, space):
    """非法输入、未启用、应用/用户无权限都不得进入 Facade 领域逻辑。"""
    resp = _post(client, space, "search_workflow_capabilities", {})
    assert resp.json()["result"] is False
    assert resp.json()["data"]["errors"][0]["category"] == "PERMISSION"

    _enable_harness(space, users=["alice"])
    forbidden_user = _post(client, space, "get_plugin_schema", {"capability_ref": "cap_v1_x"})
    assert forbidden_user.json()["data"]["errors"][0]["category"] == "PERMISSION"

    other = Space.objects.create(name="other", app_code="other_app", platform_url="http://example.com")
    _enable_harness(other)
    forbidden_app = _post(client, other, "validate_workflow", {"a2flow": {}, "bindings": [], "idempotency_key": "k"})
    assert forbidden_app.json()["data"]["errors"][0]["category"] == "PERMISSION"


@override_settings(BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",))
@pytest.mark.django_db
def test_write_endpoints_require_transport_fields(client, space, monkeypatch):
    """草稿和校验接口校验传输字段后才调用 Facade。"""
    _enable_harness(space)
    called = {"validate": 0, "draft": 0}

    def fake_validate(self, context, request):
        called["validate"] += 1
        return {
            "ok": True,
            "run_id": "r1",
            "revision_id": "rev1",
            "plan_hash": "a" * 64,
            "status": "VALIDATING",
            "summary": "ok",
            "artifact_refs": [],
            "errors": [],
            "next_actions": [],
            "correlation_id": context.correlation_id,
        }

    def fake_draft(self, context, request):
        called["draft"] += 1
        return {
            "ok": True,
            "run_id": request["run_id"],
            "revision_id": request["revision_id"],
            "plan_hash": request.get("plan_hash"),
            "status": "DRAFT_READY",
            "summary": "draft",
            "artifact_refs": [],
            "errors": [],
            "next_actions": [],
            "correlation_id": context.correlation_id,
        }

    monkeypatch.setattr("bkflow.apigw.views.harness.dispatch.HarnessFacade.validate_workflow", fake_validate)
    monkeypatch.setattr("bkflow.apigw.views.harness.dispatch.HarnessFacade.create_workflow_draft", fake_draft)

    missing = _post(client, space, "validate_workflow", {"idempotency_key": "k"})
    assert missing.json()["result"] is False
    assert called["validate"] == 0

    ok = _post(
        client,
        space,
        "validate_workflow",
        {"a2flow": {"version": "2.0", "name": "x", "nodes": []}, "bindings": [], "idempotency_key": "k"},
    )
    assert ok.json()["result"] is True
    assert called["validate"] == 1

    draft_missing = _post(client, space, "create_workflow_draft", {"idempotency_key": "d"})
    assert draft_missing.json()["result"] is False
    draft_ok = _post(
        client,
        space,
        "create_workflow_draft",
        {
            "run_id": "r1",
            "revision_id": "rev1",
            "expected_plan_hash": "a" * 64,
            "idempotency_key": "d1",
        },
    )
    assert draft_ok.json()["data"]["status"] == "DRAFT_READY"
    assert called["draft"] == 1
