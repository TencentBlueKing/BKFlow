"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

import datetime
import json
import os
import runpy
from pathlib import Path
from unittest.mock import patch

import pytest
from django.db import IntegrityError, connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from bkflow.permission.grants import Grant
from bkflow.permission.models import Token, TokenGrant
from bkflow.permission.services import issue_token
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot


@pytest.fixture
def token_api(db, client):
    """使用真实空间和模板，仅替换网关身份与引擎 API 边界。"""
    space = Space.objects.create(app_code="test", platform_url="http://test.com", name="token_space")
    snapshot = TemplateSnapshot.objects.create(data={"activities": {}}, md5sum="test")
    # 测试数据直接入库，避免触发与授权无关的异步统计信号。
    Template.objects.bulk_create(
        [
            Template(
                id=100,
                space_id=space.id,
                snapshot_id=snapshot.id,
                name="token_template",
                scope_type="biz",
                scope_value="001",
            )
        ]
    )
    template = Template.objects.get(pk=100)
    SpaceConfig.objects.create(space_id=space.id, name="token_expiration", text_value="1h", value_type="TEXT")
    SpaceConfig.objects.create(space_id=space.id, name="token_auto_renewal", text_value="false", value_type="TEXT")
    with override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True,
        TOKEN_COMPOSITE_ENABLED=True,
        MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",),
    ):
        yield client, space, template


def post(token_api, payload, action="apply_token"):
    """通过实际 Django 路由调用并保留原 HTTP 状态约定。"""
    client, space, _ = token_api
    response = client.post(
        f"/apigw/space/{space.id}/{action}/", data=json.dumps(payload), content_type="application/json"
    )
    assert response.status_code == 200
    return response.json()


def template_grant(token_api, permission="MOCK"):
    """构造真实模板的显式授权。"""
    return {"resource_type": "TEMPLATE", "resource_id": str(token_api[2].id), "permission_type": permission}


def assert_error(response, code):
    """旧错误包装始终带 message、空 data 和业务错误码。"""
    assert set(response) == {"result", "message", "code", "data"}
    assert response["result"] is False
    assert response["data"] is None
    assert response["code"] == code


def test_legacy_numeric_id_extras_mixed_and_date(token_api):
    """旧字段优先，忽略额外身份和 grants，保持响应字段和时间编码。"""
    grant = template_grant(token_api)
    payload = dict(
        grant, resource_id=token_api[2].id, user="intruder", space_id=999, grants=[{"bad": "ignored"}], other="ignored"
    )
    with override_settings(TOKEN_COMPOSITE_ENABLED=False):
        response = post(token_api, payload)
    assert set(response) == {"result", "data", "code"}
    assert response["result"] is True and response["code"] == 0
    data = response["data"]
    assert set(data) == {"token", "space_id", "user", "resource_type", "resource_id", "expired_time"}
    assert data["resource_id"] == str(token_api[2].id)
    assert data["user"] == "username" and data["space_id"] == token_api[1].id
    token = Token.objects.get(pk=data["token"])
    assert data["expired_time"] == token.expired_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    assert token.get_grants() == (Grant("TEMPLATE", str(token_api[2].id), "MOCK"),)
    assert token.grant_set_hash and TokenGrant.objects.count() == 1


@pytest.mark.parametrize("key", [None, "resource_type", "resource_id", "permission_type"])
def test_legacy_missing_fields_keep_errors_even_with_grants(token_api, key):
    """任何旧字段都触发原必填规则，全部缺失也沿用旧错误。"""
    payload = {} if key is None else {key: template_grant(token_api)[key], "grants": [template_grant(token_api)]}
    response = post(token_api, payload)
    assert_error(response, 400)
    assert set(json.loads(response["message"])) == ({"resource_type", "resource_id", "permission_type"} - {key})
    assert not Token.objects.exists()


@pytest.mark.parametrize("payload,kind", [([], "list"), ("x", "str"), (1, "int"), (None, None)])
def test_legacy_nonobject_keeps_parameter_error(token_api, payload, kind):
    """非 object JSON 必须保留原 non_field_errors 和 HTTP 200/code 400。"""
    response = post(token_api, payload)
    assert_error(response, 400)
    expected = "No data provided" if kind is None else f"无效数据。期待为字典类型，得到的是 {kind} 。"
    assert json.loads(response["message"]) == {"non_field_errors": expected}


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("permission_type", "FLOW_EDIT", 400),
        ("resource_type", "INVALID", 400),
        ("resource_type", "LABEL", 500),
        ("resource_id", "", 400),
    ],
)
def test_legacy_choices_and_unsupported_resources(token_api, field, value, code):
    """旧 choices 与 LABEL 的资源校验失败类别不改变。"""
    response = post(token_api, dict(template_grant(token_api), **{field: value}))
    assert_error(response, code)
    assert not Token.objects.exists()


@pytest.mark.parametrize("composite", [False, True])
def test_unusual_operation_resource_pair_remains_accepted(token_api, composite):
    """本次不收紧旧版允许签发的 TEMPLATE/OPERATE 组合。"""
    grant = template_grant(token_api, "OPERATE")
    response = post(token_api, {"grants": [grant]} if composite else grant)
    assert response["result"] is True


def test_composite_disabled_only_blocks_grants_issuance(token_api):
    """关闭开关仍允许旧申请及撤销既有组合票据。"""
    grants = [template_grant(token_api), template_grant(token_api, "VIEW")]
    token = issue_token(token_api[1].id, "username", [Grant(**g) for g in grants], 3600, False)
    with override_settings(TOKEN_COMPOSITE_ENABLED=False):
        response = post(token_api, {"grants": grants})
        assert_error(response, 500)
        assert "未启用" in response["message"]
        assert post(token_api, grants[0])["result"] is True
        assert post(token_api, {"token": token.pk}, "revoke_token")["data"] == "1 tokens revoke success"
    token.refresh_from_db()
    assert token.has_expired()


@pytest.mark.parametrize(
    "value,expected", [(None, False), ("false", False), ("0", False), ("true", True), ("TRUE", True), ("1", False)]
)
def test_composite_environment_flag(value, expected):
    """只有不区分大小写的 true 启用组合申请；默认和显式 false 关闭。"""
    env_path = Path(__file__).resolve().parents[3] / "env.py"
    with patch.dict(os.environ):
        os.environ.pop("BKAPP_TOKEN_COMPOSITE_ENABLED", None)
        if value is not None:
            os.environ["BKAPP_TOKEN_COMPOSITE_ENABLED"] = value
        namespace = runpy.run_path(str(env_path))
    assert namespace.get("TOKEN_COMPOSITE_ENABLED") is expected


@pytest.mark.parametrize("grants", [[], None, {}, "invalid", [{}] * 33])
def test_composite_requires_raw_list_length_1_to_32(token_api, grants):
    """无效列表在逐项资源查询和任何写入前拒绝。"""
    response = post(token_api, {"grants": grants})
    assert_error(response, 400)
    message = json.loads(response["message"])
    assert "grants" in message
    if isinstance(grants, list) and len(grants) == 33:
        assert "32" in message["grants"]
    assert not Token.objects.exists()


def test_composite_duplicate_raw_limit_before_dedup(token_api):
    """32 条完全重复可签发单项，33 条即使重复也拒绝。"""
    grant = template_grant(token_api)
    assert post(token_api, {"grants": [grant] * 32})["result"] is True
    assert_error(post(token_api, {"grants": [grant] * 33}), 400)
    assert Token.objects.count() == 1


@pytest.mark.parametrize(
    "bad,code",
    [
        (None, 400),
        ({}, 400),
        ({"resource_type": "TEMPLATE", "resource_id": "1", "permission_type": "FLOW_VIEW"}, 400),
        ({"resource_type": "LABEL", "resource_id": "1", "permission_type": "VIEW"}, 500),
        ({"resource_type": "TEMPLATE", "resource_id": "999999", "permission_type": "VIEW"}, 500),
    ],
)
def test_composite_item_failures_identify_index_and_write_nothing(token_api, bad, code):
    """字段与资源失败均标注从零开始的授权索引，不创建部分票据。"""
    response = post(token_api, {"grants": [template_grant(token_api), bad]})
    assert_error(response, code)
    assert "grants[1]" in response["message"]
    assert not Token.objects.exists() and not TokenGrant.objects.exists()


def test_composite_task_resource_validation_prevents_existing_token_renewal(token_api):
    """真实校验器读到引擎资源不存在时，已有同集合票据也不能续期。"""
    task = {"resource_type": "TASK", "resource_id": "200", "permission_type": "OPERATE"}
    grants = [template_grant(token_api), task]
    SpaceConfig.objects.filter(space_id=token_api[1].id, name="token_auto_renewal").update(text_value="true")
    token = issue_token(token_api[1].id, "username", [Grant(**g) for g in grants], 300, False)
    old_expiry = token.expired_time
    with patch("bkflow.apigw.serializers.token.TaskComponentClient") as engine:
        engine.return_value.task_list.return_value = {"result": True, "data": {"count": 0, "results": []}}
        response = post(token_api, {"grants": grants})
        assert_error(response, 500)
        assert "grants[1]" in response["message"]
        engine.return_value.task_list.assert_called_once_with(
            data={"id": "200", "space_id": str(token_api[1].id), "limit": 1, "offset": 0}
        )
    token.refresh_from_db()
    assert token.expired_time == old_expiry
    assert Token.objects.count() == 1 and TokenGrant.objects.count() == 2


def test_composite_order_duplicates_resource_cache_and_scope_identity(token_api):
    """相同集合复用一张票据；不同操作不压缩，相同资源仅查询一次。"""
    template = template_grant(token_api)
    task = {"resource_type": "TASK", "resource_id": "200", "permission_type": "OPERATE"}
    task_view = dict(task, permission_type="VIEW")
    scope = {"resource_type": "SCOPE", "resource_id": "biz_001", "permission_type": "EDIT"}
    with patch("bkflow.apigw.serializers.token.TaskComponentClient") as engine:
        engine.return_value.task_list.return_value = {"result": True, "data": {"count": 1}}
        with CaptureQueriesContext(connection) as queries:
            first = post(token_api, {"grants": [template, task, task_view, scope, template]})
        assert first["result"] is True
        engine.return_value.task_list.assert_called_once()
        template_table = connection.ops.quote_name(Template._meta.db_table)
        template_queries = [q["sql"] for q in queries if f"FROM {template_table}" in q["sql"]]
        assert len(template_queries) == 2  # 一次模板存在性，一次 scope 存在性。
        second = post(token_api, {"grants": [scope, task_view, task, template]})
    assert second["data"]["token"] == first["data"]["token"]
    assert set(first) == {"result", "data", "code"}
    assert set(first["data"]) == {"token", "space_id", "user", "expired_time", "grants"}
    assert first["data"]["grants"] == [scope, task, task_view, template]
    token = Token.objects.get()
    assert token.is_composite
    assert TokenGrant.objects.count() == 4


def test_new_single_grant_reuses_legacy_request_ticket_with_new_response(token_api):
    """grants 单项和旧请求复用同票据，但响应形式跟随请求。"""
    grant = template_grant(token_api)
    legacy = post(token_api, grant)
    response = post(token_api, {"grants": [dict(grant, resource_id=token_api[2].id), grant]})
    assert response["result"] is True
    assert response["data"]["token"] == legacy["data"]["token"]
    assert response["data"]["grants"] == [grant]
    assert set(response["data"]) == {"token", "space_id", "user", "expired_time", "grants"}
    assert response["data"]["expired_time"] == legacy["data"]["expired_time"]
    token = Token.objects.get()
    assert token.grant_set_hash and token.get_grants() == (Grant(**grant),)
    assert TokenGrant.objects.count() == 1


def test_composite_resource_must_be_in_url_space(token_api):
    """其他空间中实际存在的模板不能被组合申请授权。"""
    Template.objects.bulk_create([Template(id=101, space_id=999, snapshot_id=token_api[2].snapshot_id, name="other")])
    other = Template.objects.get(pk=101)
    response = post(
        token_api, {"grants": [template_grant(token_api), dict(template_grant(token_api), resource_id=str(other.id))]}
    )
    assert_error(response, 500)
    assert "grants[1]" in response["message"]
    assert not Token.objects.exists()


def test_composite_detail_write_failure_rolls_back_main_token(token_api):
    """真实事务在明细写入出错时回滚主票据。"""
    with patch.object(TokenGrant.objects, "bulk_create", side_effect=IntegrityError("detail write failed")):
        response = post(token_api, {"grants": [template_grant(token_api), template_grant(token_api, "VIEW")]})
    assert_error(response, 500)
    assert "detail write failed" in response["message"]
    assert not Token.objects.exists() and not TokenGrant.objects.exists()


def test_revoke_by_grant_expires_whole_ticket_preserving_protocol(token_api):
    """授权条件撤销一张组合票据，保留计数文本及空 message。"""
    grants = [template_grant(token_api), template_grant(token_api, "VIEW")]
    token = issue_token(token_api[1].id, "username", [Grant(**g) for g in grants], 3600, False)
    response = post(token_api, dict(grants[0], token=token.pk, user="username", extra="ignored"), "revoke_token")
    assert response == {"result": True, "data": "1 tokens revoke success", "message": "", "code": 0}
    token.refresh_from_db()
    assert token.has_expired() and token.grants.count() == 2
    assert post(token_api, {"token": token.pk}, "revoke_token")["data"] == "1 tokens revoke success"


def test_empty_revoke_only_expires_url_space(token_api):
    """空过滤仍撤销当前空间所有票据，不能跨空间。"""
    grant = Grant(**template_grant(token_api))
    own = issue_token(token_api[1].id, "username", [grant], 3600, False)
    other = issue_token(token_api[1].id + 1, "username", [grant], 3600, False)
    response = post(token_api, {}, "revoke_token")
    assert response == {"result": True, "data": "1 tokens revoke success", "message": "", "code": 0}
    own.refresh_from_db()
    other.refresh_from_db()
    assert own.has_expired() and not other.has_expired()


def test_revoke_resource_conditions_must_match_one_grant(token_api):
    """撤销的资源三元组不能从不同明细拼接。"""
    grants = [Grant(**template_grant(token_api)), Grant("TASK", "200", "OPERATE")]
    token = issue_token(token_api[1].id, "username", grants, 3600, False)
    assert (
        post(token_api, dict(template_grant(token_api), permission_type="OPERATE"), "revoke_token")["data"]
        == "0 tokens revoke success"
    )
    token.refresh_from_db()
    assert token.expired_time > timezone.now() + datetime.timedelta(minutes=50)


@pytest.mark.parametrize("auto_renewal", ["false", "true"])
def test_composite_reuse_obeys_space_renewal_config(token_api, auto_renewal):
    """组合重复申请遵循自动续期配置，授权集合始终不变。"""
    grants = [template_grant(token_api), template_grant(token_api, "VIEW")]
    token = issue_token(token_api[1].id, "username", [Grant(**g) for g in grants], 300, False)
    original_expiry = token.expired_time
    SpaceConfig.objects.filter(space_id=token_api[1].id, name="token_auto_renewal").update(text_value=auto_renewal)
    response = post(token_api, {"grants": grants})
    assert response["result"] is True and response["data"]["token"] == token.pk
    token.refresh_from_db()
    if auto_renewal == "true":
        assert token.expired_time > original_expiry + datetime.timedelta(minutes=50)
    else:
        assert token.expired_time == original_expiry
    assert Token.objects.count() == 1 and token.grants.count() == 2


def test_composite_preserves_leading_zero_resource_identity(token_api):
    """模板可按数值查存在性，但存储和返回的资源 ID 保留原字符串。"""
    grant = dict(template_grant(token_api), resource_id="00100")
    response = post(token_api, {"grants": [grant]})
    assert response["result"] is True and response["data"]["grants"] == [grant]
    assert Token.objects.get().get_grants() == (Grant("TEMPLATE", "00100", "MOCK"),)


def test_composite_engine_failure_is_indexed_and_has_no_writes(token_api):
    """引擎 API 失败按资源失败处理，不留下任何票据。"""
    task = {"resource_type": "TASK", "resource_id": "200", "permission_type": "VIEW"}
    with patch("bkflow.apigw.serializers.token.TaskComponentClient") as engine:
        engine.return_value.task_list.return_value = {"result": False, "data": None, "message": "unavailable"}
        response = post(token_api, {"grants": [template_grant(token_api), task]})
    assert_error(response, 500)
    assert "grants[1]" in response["message"]
    assert not Token.objects.exists() and not TokenGrant.objects.exists()
