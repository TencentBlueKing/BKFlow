"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.

票据签发、整票据撤销及持锁续期的数据库回归。
"""

import json
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.permission.grants import Grant
from bkflow.permission.models import Token, TokenGrant
from bkflow.space.models import SpaceConfig

pytestmark = pytest.mark.django_db

GRANTS = (Grant("TEMPLATE", "100", "MOCK"), Grant("TASK", "200", "OPERATE"))


def issue(grants=GRANTS, space_id=1, user="alice", expiration_seconds=3600, auto_renewal=False):
    """通过真实服务签发测试票据。"""
    from bkflow.permission.services import issue_token

    return issue_token(space_id, user, grants, expiration_seconds, auto_renewal)


def legacy(expired_time=None):
    """创建旧单项票据，允许覆盖到期时间。"""
    return Token.objects.create(
        token=Token.generate_token(),
        space_id=1,
        user="alice",
        resource_type="TEMPLATE",
        resource_id="100",
        permission_type="MOCK",
        expired_time=expired_time or timezone.now() + timedelta(hours=1),
    )


def test_issue_composite_normalizes_and_reuses():
    """顺序和重复条目不改变整张票据，主表不泄漏额外资源。"""
    token = issue()
    reused = issue([GRANTS[1], GRANTS[0], GRANTS[1]])
    assert reused.pk == token.pk
    assert token.get_grants() == (Grant("TASK", "200", "OPERATE"), Grant("TEMPLATE", "100", "MOCK"))
    assert (token.resource_type, token.resource_id, token.permission_type) == ("", "", "")
    assert Token.objects.count() == 1
    assert TokenGrant.objects.count() == 2


def test_single_reuses_latest_legacy_and_never_composite():
    """单项复用最晚过期的旧票据，不复用含该项的组合票据。"""
    composite = issue()
    older = legacy(timezone.now() + timedelta(minutes=5))
    latest = legacy()
    token = issue([GRANTS[0], GRANTS[0]])
    assert token.pk == latest.pk
    assert token.pk not in (older.pk, composite.pk)
    assert not token.is_composite
    assert token.grants.count() == 0


@pytest.mark.parametrize(
    "grants,space_id,user",
    [
        ([GRANTS[0]], 1, "alice"),
        ([*GRANTS, Grant("TASK", "300", "VIEW")], 1, "alice"),
        ([GRANTS[0], Grant("TASK", "200", "VIEW")], 1, "alice"),
        (GRANTS, 2, "alice"),
        (GRANTS, 1, "bob"),
    ],
)
def test_different_complete_sets_and_owners_do_not_reuse(grants, space_id, user):
    """子集、超集、不同操作或不同身份空间独立签发。"""
    original = issue()
    assert issue(grants, space_id, user).pk != original.pk


def test_hash_candidate_compares_complete_set():
    """即使摘要碰撞且两边完整性校验通过，也不得复用不同授权。"""
    with patch("bkflow.permission.services.grant_set_hash", return_value="a" * 64), patch(
        "bkflow.permission.models.grant_set_hash", return_value="a" * 64
    ):
        original = issue()
        other = issue([GRANTS[0], Grant("TASK", "300", "VIEW")])
    assert original.pk != other.pk


def test_issue_rolls_back_parent_and_partial_details():
    """真实唯一约束使批量明细失败，主票据和已写明细一起回滚。"""
    with patch("bkflow.permission.services.grant_hash", return_value="a" * 64):
        with pytest.raises(IntegrityError):
            issue()
    assert Token.objects.count() == 0
    assert TokenGrant.objects.count() == 0


def test_issue_expired_or_incomplete_candidate_creates_new():
    """到期和明细损坏的组合票据不能复用。"""
    original = issue()
    Token.objects.filter(pk=original.pk).update(expired_time=timezone.now())
    second = issue()
    second.grants.all().delete()
    third = issue()
    assert len({original.pk, second.pk, third.pk}) == 3


@pytest.mark.parametrize("auto_renewal", [False, True])
def test_issue_auto_renewal_setting(auto_renewal):
    """复用按传入空间开关决定是否补全有效周期。"""
    token = issue(expiration_seconds=60)
    reused = issue(expiration_seconds=3600, auto_renewal=auto_renewal)
    assert reused.pk == token.pk
    if auto_renewal:
        assert reused.expired_time > token.expired_time + timedelta(minutes=58)
    else:
        assert reused.expired_time == token.expired_time


@pytest.mark.parametrize(
    "filters,count",
    [
        ({"resource_type": "TEMPLATE", "resource_id": "100"}, 1),
        ({"resource_type": "TEMPLATE", "resource_id": "200"}, 0),
        ({"resource_type": "TEMPLATE", "permission_type": "OPERATE"}, 0),
        ({"resource_id": "200", "permission_type": "MOCK"}, 0),
        ({"resource_type": "TASK", "resource_id": "200", "permission_type": "OPERATE"}, 1),
    ],
)
def test_revoke_resource_conditions_match_same_grant(filters, count):
    """所有资源条件必须命中同一条明细，命中后整张票据失效。"""
    from bkflow.permission.services import revoke_tokens

    token = issue()
    assert revoke_tokens(1, filters) == count
    token.refresh_from_db()
    assert token.has_expired() == bool(count)
    assert token.grants.count() == 2


def test_revoke_counts_distinct_parents_including_expired():
    """多条匹配明细只计一张票据，已到期单项也纳入计数。"""
    from bkflow.permission.services import revoke_tokens

    token = issue([Grant("TEMPLATE", "100", "VIEW"), Grant("TEMPLATE", "100", "MOCK")])
    old = legacy(timezone.now() - timedelta(hours=1))
    assert revoke_tokens(1, {"resource_type": "TEMPLATE", "resource_id": "100"}) == 2
    for obj in (token, old):
        obj.refresh_from_db()
        assert obj.has_expired()


def test_revoke_main_conditions_and_space_are_all_required():
    """token、用户与 URL 空间均须匹配，不能相互覆盖。"""
    from bkflow.permission.services import revoke_tokens

    token = issue()
    assert revoke_tokens(2, {"token": token.pk, "user": "alice"}) == 0
    assert revoke_tokens(1, {"token": token.pk, "user": "bob"}) == 0
    assert revoke_tokens(1, {"token": token.pk, "user": "alice", "resource_id": "999"}) == 0
    assert revoke_tokens(1, {"token": token.pk, "user": "alice", "resource_id": "100"}) == 1


def test_revoke_empty_filters_includes_corrupt_but_only_current_space():
    """空间全撤销不依赖明细，损坏票据仍能清除。"""
    from bkflow.permission.services import revoke_tokens

    token = issue()
    token.grants.all().delete()
    legacy()
    other = issue(space_id=2)
    assert revoke_tokens(1, {}) == 2
    token.refresh_from_db()
    other.refresh_from_db()
    assert token.has_expired()
    assert not other.has_expired()


def test_legacy_revoke_ignores_stray_details_and_composite_old_fields():
    """两种存储形态均只按权威字段筛选撤销。"""
    from bkflow.permission.grants import grant_hash
    from bkflow.permission.services import revoke_tokens

    old = legacy()
    detail = Grant("TASK", "300", "VIEW")
    TokenGrant.objects.create(token=old, **detail.as_dict(), grant_hash=grant_hash(detail))
    composite = issue()
    Token.objects.filter(pk=composite.pk).update(resource_type="TASK", resource_id="300", permission_type="VIEW")
    assert revoke_tokens(1, {"resource_id": "300"}) == 0


def test_model_renewal_does_not_revive_expired_token():
    """旧模型接口不得恢复到期票据，仍返回二元组。"""
    token = legacy(timezone.now() - timedelta(seconds=1))
    result, message = token.renewal()
    assert result is False
    assert message
    token.refresh_from_db()
    assert token.has_expired()


def test_model_renewal_refetches_stale_instance_after_revoke():
    """撤销后即使模型实例仍持有旧到期时间也不能续活。"""
    from bkflow.permission.services import revoke_tokens

    token = issue()
    assert revoke_tokens(1, {"token": token.pk}) == 1
    assert token.renewal()[0] is False
    assert token.has_expired()


def test_revoke_after_renewal_wins():
    """续期先完成时，后续撤销覆盖新到期时间。"""
    from bkflow.permission.services import renew_token, revoke_tokens

    token = issue(expiration_seconds=60)
    result, message, renewed = renew_token(token.pk, "alice")
    assert result is True and message == ""
    assert renewed.expired_time > token.expired_time
    assert revoke_tokens(1, {"token": token.pk}) == 1
    renewed.refresh_from_db()
    assert renewed.has_expired()


@pytest.mark.parametrize("case", ["missing", "wrong_user", "incomplete", "disabled"])
def test_renewal_rejects_invalid_or_disabled_token(case):
    """缺失、身份不符、明细损坏或关闭开关均不可更新到期时间。"""
    from bkflow.permission.services import renew_token

    token = issue()
    if case == "incomplete":
        token.grants.all().delete()
    if case == "disabled":
        SpaceConfig.objects.create(space_id=1, name="token_auto_renewal", text_value="false", value_type="TEXT")
    result, message, _ = renew_token(
        "missing" if case == "missing" else token.pk, "bob" if case == "wrong_user" else "alice"
    )
    assert result is False and message
    stored = Token.objects.get(pk=token.pk)
    assert stored.expired_time == token.expired_time


def test_model_renewal_syncs_expiry_and_uses_space_duration():
    """模型保持二元组和实例同步，续期周期来自空间设置。"""
    SpaceConfig.objects.create(space_id=1, name="token_expiration", text_value="2h", value_type="TEXT")
    token = issue(expiration_seconds=60)
    before = timezone.now()
    assert token.renewal() == (True, "")
    assert token.expired_time >= before + timedelta(hours=2)
    assert Token.objects.get(pk=token.pk).expired_time == token.expired_time


def test_expiry_equality_is_expired():
    """等于当前时刻的票据已失效。"""
    now = timezone.now()
    token = legacy(now)
    with patch("bkflow.permission.models.timezone.now", return_value=now):
        assert token.has_expired()


def test_valid_token_checks_identity_space_expiry_and_integrity():
    """公共读取只返回当前身份空间内有效且完整的票据。"""
    from bkflow.permission.services import get_valid_token

    token = issue()
    assert get_valid_token(token.pk, "alice", "1").pk == token.pk
    assert get_valid_token(token.pk, "alice").pk == token.pk
    assert get_valid_token(token.pk, "bob", 1) is None
    assert get_valid_token(token.pk, "alice", 2) is None
    assert get_valid_token("missing", "alice", 1) is None
    token.grants.all().delete()
    assert get_valid_token(token.pk, "alice", 1) is None
    old = legacy(timezone.now() - timedelta(seconds=1))
    assert get_valid_token(old.pk, "alice", 1) is None


def test_request_cache_reuses_grants_but_rechecks_context_and_time(django_assert_num_queries):
    """请求内复用读取，跨身份、跨请求和到期边界均不误放行。"""
    from bkflow.permission.services import get_valid_token

    token = issue()
    request = SimpleNamespace()
    with django_assert_num_queries(2):
        first = get_valid_token(token.pk, "alice", 1, request)
        assert first.get_grants()
    with django_assert_num_queries(0):
        assert get_valid_token(token.pk, "alice", 1, request) is first
        assert first.get_grants()
    assert get_valid_token(token.pk, "bob", 1, request) is None
    assert get_valid_token(token.pk, "alice", 2, request) is None
    with patch("bkflow.permission.services.timezone.now", return_value=token.expired_time):
        assert get_valid_token(token.pk, "alice", 1, request) is None
    token.grants.all().delete()
    assert get_valid_token(token.pk, "alice", 1, SimpleNamespace()) is None


def test_cached_token_cannot_bypass_locked_renewal_check():
    """请求缓存不能使已撤销票据在模型续期时复活。"""
    from bkflow.permission.services import get_valid_token, revoke_tokens

    token = issue()
    cached = get_valid_token(token.pk, "alice", 1, SimpleNamespace())
    revoke_tokens(1, {"token": token.pk})
    assert cached.renewal()[0] is False


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_renewal_view_preserves_normal_response_wrapper(enabled):
    """正常续期的外层包装、内层开关结果与字段保持不变。"""
    from bkflow.permission.views import TokenViewSet

    SpaceConfig.objects.create(space_id=1, name="token_auto_renewal", text_value=enabled, value_type="TEXT")
    token = issue()
    request = APIRequestFactory().post(f"/api/permission/token/{token.pk}/renewal/")
    force_authenticate(request, user=SimpleNamespace(username="alice", is_authenticated=True))
    response = TokenViewSet.as_view({"post": "renewal"})(request, pk=token.pk)
    assert response.status_code == 200
    assert set(response.data) == {"result", "data", "code", "message"}
    assert response.data["result"] is True
    assert response.data["code"] == "0"
    assert set(response.data["data"]) == {"result", "message", "expired_time"}
    assert response.data["data"]["result"] is (enabled == "true")


def test_successful_renewal_renders_legacy_default_timezone_expiry():
    """成功续期按默认时区输出无偏移时间，不受当前活动时区影响。"""
    from bkflow.permission.views import TokenViewSet

    now = datetime(2030, 1, 1, 12, tzinfo=datetime_timezone.utc)
    SpaceConfig.objects.create(space_id=1, name="token_auto_renewal", text_value="true", value_type="TEXT")
    SpaceConfig.objects.create(space_id=1, name="token_expiration", text_value="1h", value_type="TEXT")
    token = legacy(now + timedelta(hours=2))
    request = APIRequestFactory().post(f"/api/permission/token/{token.pk}/renewal/")
    force_authenticate(request, user=SimpleNamespace(username="alice", is_authenticated=True))

    with timezone.override("Asia/Tokyo"), patch("bkflow.permission.services.timezone.now", return_value=now):
        response = TokenViewSet.as_view({"post": "renewal"})(request, pk=token.pk)
        rendered = json.loads(response.render().content)

    assert rendered == {
        "result": True,
        "data": {"result": True, "message": "", "expired_time": "2030-01-01T21:00:00"},
        "code": "0",
        "message": "",
    }
    stored = Token.objects.get(pk=token.pk)
    assert timezone.is_aware(stored.expired_time)
    assert stored.expired_time == now + timedelta(hours=1)


def test_disabled_renewal_renders_original_database_expiry():
    """关闭自动续期时保持数据库读取到的 aware 时间编码。"""
    from bkflow.permission.views import TokenViewSet

    now = datetime(2030, 1, 1, 12, tzinfo=datetime_timezone.utc)
    SpaceConfig.objects.create(space_id=1, name="token_auto_renewal", text_value="false", value_type="TEXT")
    token = legacy(now + timedelta(hours=2))
    request = APIRequestFactory().post(f"/api/permission/token/{token.pk}/renewal/")
    force_authenticate(request, user=SimpleNamespace(username="alice", is_authenticated=True))

    with timezone.override("Asia/Tokyo"), patch("bkflow.permission.services.timezone.now", return_value=now):
        response = TokenViewSet.as_view({"post": "renewal"})(request, pk=token.pk)
        rendered = json.loads(response.render().content)

    assert rendered == {
        "result": True,
        "data": {
            "result": False,
            "message": "续期失败，当前空间未开启token自动续期",
            "expired_time": "2030-01-01T14:00:00Z",
        },
        "code": "0",
        "message": "",
    }


def test_view_queryset_uses_current_time_on_every_call():
    """视图查询不能保留模块加载时的旧时间。"""
    from bkflow.permission.views import TokenViewSet

    now = timezone.now()
    token = legacy(now + timedelta(seconds=30))
    view = TokenViewSet()
    with patch("bkflow.permission.views.timezone.now", return_value=now):
        assert view.get_queryset().filter(pk=token.pk).exists()
    with patch("bkflow.permission.views.timezone.now", return_value=token.expired_time):
        assert not view.get_queryset().filter(pk=token.pk).exists()


@pytest.mark.parametrize("operation", ["renew", "issue"])
def test_lifecycle_rechecks_expiry_after_parent_read(operation):
    """模拟主行锁等待跨过到期边界，锁前时间不能用于续期或复用。"""
    from django.db import connection

    from bkflow.permission.services import renew_token

    token = issue()
    before = token.expired_time - timedelta(seconds=1)
    parent_reads = []
    parent_table = connection.ops.quote_name(Token._meta.db_table)
    with patch("bkflow.permission.services.timezone.now", return_value=before) as clock:

        def advance_after_parent_read(execute, sql, params, many, context):
            """真实主表查询完成时推进时钟，保留数据库执行。"""
            result = execute(sql, params, many, context)
            if sql.startswith("SELECT") and f"FROM {parent_table}" in sql:
                parent_reads.append(sql)
                clock.return_value = token.expired_time
            return result

        with connection.execute_wrapper(advance_after_parent_read):
            if operation == "renew":
                assert renew_token(token.pk, "alice")[0] is False
            else:
                assert issue(auto_renewal=True).pk != token.pk
    assert parent_reads
    token.refresh_from_db()
    assert token.expired_time == before + timedelta(seconds=1)


def test_single_creation_preserves_resource_id_and_authoritative_fields():
    """单项去重后只写旧字段，资源 ID 不做额外数值规范化。"""
    token = issue([Grant("TEMPLATE", "001", "MOCK")])
    assert not token.is_composite
    assert token.resource_id == "001"
    assert token.grants.count() == 0
    assert issue([Grant("TEMPLATE", "1", "MOCK")]).pk != token.pk


@pytest.mark.parametrize("composite", [False, True])
def test_space_id_integer_equivalence_preserves_access_and_request_cache(composite, django_assert_num_queries):
    """空间前导零与整数字段等价，缓存共用；资源前导零保持原样。"""
    from bkflow.permission.services import get_valid_token

    grants = [Grant("TEMPLATE", "001", "MOCK")]
    if composite:
        grants.append(Grant("TASK", "200", "OPERATE"))
    token = issue(grants, space_id=245)
    request = SimpleNamespace()
    current = get_valid_token(token.pk, "alice", "0245", request)
    assert current is not None and current.pk == token.pk
    with django_assert_num_queries(0):
        assert get_valid_token(token.pk, "alice", 245, request) is current
        assert get_valid_token(token.pk, "alice", "245", request) is current
    assert get_valid_token(token.pk, "alice", "0246", request) is None
    assert Grant("TEMPLATE", "001", "MOCK") in current.get_grants()
    assert Grant("TEMPLATE", "1", "MOCK") not in current.get_grants()


@pytest.mark.parametrize("composite", [False, True])
def test_space_id_integer_equivalence_reuses_existing_token(composite):
    """字符串空间前导零不能使相同单项或组合授权重复签发。"""
    grants = [Grant("TEMPLATE", "001", "MOCK")]
    if composite:
        grants.append(Grant("TASK", "200", "OPERATE"))
    token = issue(grants, space_id=245)
    reused = issue(grants, space_id="0245")
    assert reused.pk == token.pk
    assert Token.objects.count() == 1
    assert Grant("TEMPLATE", "001", "MOCK") in reused.get_grants()
    assert issue(grants, space_id="0246").pk != token.pk
