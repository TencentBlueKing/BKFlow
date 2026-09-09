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

统一授权明细的真实 MySQL 数据迁移、回滚与结构清理回归。
"""

import importlib
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone

LATEST = ("permission", "0007_auto_20260909_1521")
BACKFILL = ("permission", "0006_backfill_token_grants")
HYBRID = ("permission", "0005_auto_20260909_1147")
LEGACY = ("permission", "0004_alter_token_expired_time")

pytestmark = pytest.mark.django_db(transaction=True)


def migrate_to(target):
    """迁移到指定历史状态，并返回该状态对应的历史应用注册表。"""
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return executor.loader.project_state([target]).apps


@pytest.fixture(autouse=True)
def restore_latest_schema():
    """每个用例后清除历史数据并恢复最新结构，避免影响后续测试。"""
    yield
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        if "permission_tokengrant" in tables:
            cursor.execute("DELETE FROM permission_tokengrant")
        if "permission_token" in tables:
            cursor.execute("DELETE FROM permission_token")
    migrate_to(LATEST)


def create_hybrid_token(Token, token_id, fields, expired_time, grant_set_digest=None, *, space_id=17, user="alice"):
    """使用 0005 历史模型创建单项或组合主记录。"""
    return Token.objects.create(
        token=token_id,
        space_id=space_id,
        user=user,
        resource_type=fields[0],
        resource_id=fields[1],
        permission_type=fields[2],
        grant_set_hash=grant_set_digest,
        expired_time=expired_time,
    )


def test_forward_preserves_raw_legacy_triples_and_runtime_rejects_them():
    """未知枚举和部分空字段旧三元组应原样回填，但不能因此获得授权。"""
    old_apps = migrate_to(HYBRID)
    OldToken = old_apps.get_model("permission", "Token")
    records = {
        "raw-unknown": ("ARCHIVED", "001", "CUSTOM"),
        "raw-partial": ("", "001", "CUSTOM"),
    }
    for token_id, fields in records.items():
        create_hybrid_token(OldToken, token_id, fields, timezone.now() + timedelta(hours=1))

    backfill_apps = migrate_to(BACKFILL)
    BackfilledToken = backfill_apps.get_model("permission", "Token")
    BackfilledGrant = backfill_apps.get_model("permission", "TokenGrant")
    for token_id, fields in records.items():
        token = BackfilledToken.objects.get(pk=token_id)
        detail = BackfilledGrant.objects.get(token_id=token_id)
        assert (detail.resource_type, detail.resource_id, detail.permission_type) == fields
        assert token.grant_set_hash

    migrate_to(LATEST)
    from bkflow.permission.services import get_valid_token

    for token_id in records:
        assert get_valid_token(token_id, "alice", 17) is None


def test_migrate_0004_to_latest_preserves_identity_time_and_exact_grants():
    """0004 的活跃、过期和失效资源单项应原样进入唯一明细，并删除旧列。"""
    # 0005 的唯一约束恰好被 MySQL 选作外键索引；测试降级准备需先给旧迁移补一个临时外键索引。
    with connection.cursor() as cursor:
        cursor.execute("CREATE INDEX perm_grant_unapply_fk_idx ON permission_tokengrant (token_id)")
    old_apps = migrate_to(LEGACY)
    OldToken = old_apps.get_model("permission", "Token")
    now = timezone.now()
    records = {
        "legacy-leading-zero": (17, "Alice", ("TEMPLATE", "001", "MOCK"), now + timedelta(hours=1)),
        "legacy-unicode": (18, "alice", ("SCOPE", "biz_中文", "VIEW"), now - timedelta(hours=1)),
        "legacy-deleted": (19, "ALICE", ("TASK", "Deleted-Case", "OPERATE"), now + timedelta(days=1)),
    }
    expected_digests = {
        "legacy-leading-zero": (
            "8085619d6b64b06d4ce5569c9be08f04911470d1f3cf62c32f633a4b54f2219d",
            "b5da9badf7648f66fff17fd066452c4ab581d6449c17a03eae2561d4d178921e",
        ),
        "legacy-unicode": (
            "c111cf2b09a71ae2a08058e0ab84ab797bba457e65bbeaf6eb7be6c4e0ef0cc4",
            "81e2368e247e33be5cc4c076d5a4bed44773982c90be943a5887f6e03dc28f5a",
        ),
        "legacy-deleted": (
            "c7bbef701aaed72710e085345c1727c7e42957168e38505b1208e64e548921c6",
            "97c5c83a50196a08369084daa4080e869a69d42d79245a05f740aa3da7494919",
        ),
    }
    for token_id, (space_id, user, fields, expired_time) in records.items():
        OldToken.objects.create(
            token=token_id,
            space_id=space_id,
            user=user,
            resource_type=fields[0],
            resource_id=fields[1],
            permission_type=fields[2],
            expired_time=expired_time,
        )

    new_apps = migrate_to(LATEST)
    NewToken = new_apps.get_model("permission", "Token")
    NewGrant = new_apps.get_model("permission", "TokenGrant")
    with connection.cursor() as cursor:
        columns = {column.name for column in connection.introspection.get_table_description(cursor, "permission_token")}
    assert not {"resource_type", "resource_id", "permission_type"} & columns
    for token_id, (space_id, user, fields, expired_time) in records.items():
        token = NewToken.objects.get(pk=token_id)
        detail = NewGrant.objects.get(token_id=token_id)
        assert (token.space_id, token.user, token.expired_time) == (space_id, user, expired_time)
        assert (detail.resource_type, detail.resource_id, detail.permission_type) == fields
        assert (detail.grant_hash, token.grant_set_hash) == expected_digests[token_id]


def test_legacy_http_request_reuses_genuinely_migrated_token(client):
    """旧申请经当前路由重复调用时应复用真实迁移票据并保持响应。"""
    from bkflow.space.models import Space, SpaceConfig

    space = Space.objects.create(app_code="test", platform_url="http://test.com", name="migration_token_space")
    SpaceConfig.objects.create(space_id=space.id, name="token_expiration", text_value="1h", value_type="TEXT")
    SpaceConfig.objects.create(space_id=space.id, name="token_auto_renewal", text_value="false", value_type="TEXT")
    expires = timezone.now() + timedelta(hours=1)
    old_apps = migrate_to(HYBRID)
    OldToken = old_apps.get_model("permission", "Token")
    create_hybrid_token(
        OldToken,
        "migrated-http-token",
        ("TASK", "123", "VIEW"),
        expires,
        space_id=space.id,
        user="username",
    )
    current_apps = migrate_to(LATEST)
    CurrentToken = current_apps.get_model("permission", "Token")
    CurrentGrant = current_apps.get_model("permission", "TokenGrant")
    migrated = CurrentToken.objects.get(pk="migrated-http-token")

    payload = {"resource_type": "TASK", "resource_id": "123", "permission_type": "VIEW"}
    url = f"/apigw/space/{space.id}/apply_token/"
    with override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True,
        MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",),
    ), patch("bkflow.apigw.serializers.token.TokenResourceValidator.validate", return_value=True):
        first = client.post(url, data=json.dumps(payload), content_type="application/json")
        second = client.post(url, data=json.dumps(payload), content_type="application/json")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json() == {
        "result": True,
        "data": {
            "token": "migrated-http-token",
            "space_id": space.id,
            "user": "username",
            "resource_type": "TASK",
            "resource_id": "123",
            "expired_time": migrated.expired_time.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        },
        "code": 0,
    }

    assert CurrentToken.objects.count() == 1
    assert CurrentGrant.objects.filter(token_id="migrated-http-token").count() == 1


def test_mixed_0005_forward_is_idempotent_and_preserves_composite():
    """0005 混合数据应清除单项意外明细，保留组合，并允许重复执行回填。"""
    old_apps = migrate_to(HYBRID)
    OldToken = old_apps.get_model("permission", "Token")
    OldGrant = old_apps.get_model("permission", "TokenGrant")
    expires = timezone.now() + timedelta(hours=1)
    legacy = create_hybrid_token(OldToken, "legacy-single", ("TEMPLATE", "001", "MOCK"), expires)
    OldGrant.objects.create(
        token=legacy,
        resource_type="TASK",
        resource_id="stray",
        permission_type="VIEW",
        grant_hash="0" * 64,
    )
    composite = create_hybrid_token(
        OldToken,
        "native-composite",
        ("", "", ""),
        expires,
        "674c67ab6b387192a174d0759a513e77a492854603e49084e949c50adb86f6ca",
    )
    composite_details = [
        ("TASK", "200", "OPERATE", "9d0b89387edf09ba53d8cf8f93bd729b5aa553b24a8900fc16847ee5d655c11e"),
        ("TEMPLATE", "100", "MOCK", "6b7dc78ab5ddef71a0f0ab2ceddefef47d5adc27469b9e4fe162969e5c749176"),
    ]
    for resource_type, resource_id, permission_type, digest in composite_details:
        OldGrant.objects.create(
            token=composite,
            resource_type=resource_type,
            resource_id=resource_id,
            permission_type=permission_type,
            grant_hash=digest,
        )
    backfilled = create_hybrid_token(
        OldToken,
        "already-backfilled",
        ("TEMPLATE", "001", "MOCK"),
        expires,
        "b5da9badf7648f66fff17fd066452c4ab581d6449c17a03eae2561d4d178921e",
    )
    OldGrant.objects.create(
        token=backfilled,
        resource_type="TEMPLATE",
        resource_id="001",
        permission_type="MOCK",
        grant_hash="8085619d6b64b06d4ce5569c9be08f04911470d1f3cf62c32f633a4b54f2219d",
    )

    backfill_apps = migrate_to(BACKFILL)
    BackfilledGrant = backfill_apps.get_model("permission", "TokenGrant")
    before = list(
        BackfilledGrant.objects.order_by("token_id", "resource_type", "resource_id").values_list(
            "token_id", "resource_type", "resource_id", "permission_type", "grant_hash"
        )
    )
    migration = importlib.import_module("bkflow.permission.migrations.0006_backfill_token_grants")
    with transaction.atomic():
        migration.forwards(backfill_apps, SimpleNamespace(connection=connection))
    after = list(
        BackfilledGrant.objects.order_by("token_id", "resource_type", "resource_id").values_list(
            "token_id", "resource_type", "resource_id", "permission_type", "grant_hash"
        )
    )
    assert after == before
    assert BackfilledGrant.objects.filter(token_id="legacy-single").count() == 1
    assert BackfilledGrant.objects.filter(token_id="native-composite").count() == 2

    latest_apps = migrate_to(LATEST)
    LatestToken = latest_apps.get_model("permission", "Token")
    assert LatestToken.objects.get(pk="legacy-single").expired_time == expires
    assert LatestToken.objects.get(pk="native-composite").grant_set_hash == composite.grant_set_hash


@pytest.mark.parametrize("corruption", ["empty_legacy", "singleton_composite", "wrong_composite_digest"])
def test_forward_corruption_aborts_and_rolls_back_every_write(corruption):
    """全空旧单项或损坏原组合必须中止，且不能留下前序单项回填写入。"""
    old_apps = migrate_to(HYBRID)
    OldToken = old_apps.get_model("permission", "Token")
    OldGrant = old_apps.get_model("permission", "TokenGrant")
    expires = timezone.now() + timedelta(hours=1)
    create_hybrid_token(OldToken, "aaa-valid-single", ("TEMPLATE", "001", "MOCK"), expires)
    corrupt = create_hybrid_token(
        OldToken,
        "zzz-corrupt",
        ("", "", ""),
        expires,
        (
            None
            if corruption == "empty_legacy"
            else (
                "b5da9badf7648f66fff17fd066452c4ab581d6449c17a03eae2561d4d178921e"
                if corruption == "singleton_composite"
                else "0" * 64
            )
        ),
    )
    if corruption == "singleton_composite":
        OldGrant.objects.create(
            token=corrupt,
            resource_type="TEMPLATE",
            resource_id="001",
            permission_type="MOCK",
            grant_hash="8085619d6b64b06d4ce5569c9be08f04911470d1f3cf62c32f633a4b54f2219d",
        )
    elif corruption == "wrong_composite_digest":
        for resource_type, resource_id, permission_type, digest in [
            ("TASK", "200", "OPERATE", "9d0b89387edf09ba53d8cf8f93bd729b5aa553b24a8900fc16847ee5d655c11e"),
            ("TEMPLATE", "100", "MOCK", "6b7dc78ab5ddef71a0f0ab2ceddefef47d5adc27469b9e4fe162969e5c749176"),
        ]:
            OldGrant.objects.create(
                token=corrupt,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                grant_hash=digest,
            )
    corrupt_hash = corrupt.grant_set_hash
    corrupt_details = list(
        OldGrant.objects.filter(token=corrupt)
        .order_by("pk")
        .values_list("resource_type", "resource_id", "permission_type", "grant_hash")
    )

    with pytest.raises(RuntimeError):
        migrate_to(LATEST)

    failed_apps = MigrationExecutor(connection).loader.project_state([HYBRID]).apps
    FailedToken = failed_apps.get_model("permission", "Token")
    FailedGrant = failed_apps.get_model("permission", "TokenGrant")
    assert FailedToken.objects.get(pk="aaa-valid-single").grant_set_hash is None
    assert not FailedGrant.objects.filter(token_id="aaa-valid-single").exists()
    assert FailedToken.objects.get(pk="zzz-corrupt").grant_set_hash == corrupt_hash
    assert (
        list(
            FailedGrant.objects.filter(token_id="zzz-corrupt")
            .order_by("pk")
            .values_list("resource_type", "resource_id", "permission_type", "grant_hash")
        )
        == corrupt_details
    )
    with connection.cursor() as cursor:
        columns = {column.name for column in connection.introspection.get_table_description(cursor, "permission_token")}
    assert {"resource_type", "resource_id", "permission_type"} <= columns


def test_latest_to_0005_and_forward_again_preserves_single_and_composite():
    """最新结构回退到 0005 再升级时应还原单项旧列并保持全部身份与时间。"""
    migrate_to(LATEST)
    from bkflow.permission.grants import Grant
    from bkflow.permission.services import issue_token

    single = issue_token(17, "alice", (Grant("TEMPLATE", "001", "MOCK"),), 3600, False)
    composite = issue_token(
        17,
        "alice",
        (Grant("TASK", "200", "OPERATE"), Grant("TEMPLATE", "100", "MOCK")),
        7200,
        False,
    )
    identity = {
        single.pk: (single.space_id, single.user, single.expired_time),
        composite.pk: (composite.space_id, composite.user, composite.expired_time),
    }

    old_apps = migrate_to(HYBRID)
    OldToken = old_apps.get_model("permission", "Token")
    OldGrant = old_apps.get_model("permission", "TokenGrant")
    old_single = OldToken.objects.get(pk=single.pk)
    old_composite = OldToken.objects.get(pk=composite.pk)
    assert (old_single.resource_type, old_single.resource_id, old_single.permission_type) == (
        "TEMPLATE",
        "001",
        "MOCK",
    )
    assert old_single.grant_set_hash is None
    assert not OldGrant.objects.filter(token_id=single.pk).exists()
    assert (old_composite.resource_type, old_composite.resource_id, old_composite.permission_type) == ("", "", "")
    assert OldGrant.objects.filter(token_id=composite.pk).count() == 2

    latest_apps = migrate_to(LATEST)
    LatestToken = latest_apps.get_model("permission", "Token")
    LatestGrant = latest_apps.get_model("permission", "TokenGrant")
    for token_id, expected_identity in identity.items():
        token = LatestToken.objects.get(pk=token_id)
        assert (token.space_id, token.user, token.expired_time) == expected_identity
    assert LatestGrant.objects.filter(token_id=single.pk).count() == 1
    assert LatestGrant.objects.filter(token_id=composite.pk).count() == 2


def test_reverse_explicitly_clears_legacy_fields_for_composite():
    """反向函数应显式清空组合票据旧列，不依赖结构迁移添加列时的默认值。"""
    old_apps = migrate_to(HYBRID)
    OldToken = old_apps.get_model("permission", "Token")
    OldGrant = old_apps.get_model("permission", "TokenGrant")
    token = create_hybrid_token(
        OldToken,
        "native-composite",
        ("", "", ""),
        timezone.now() + timedelta(hours=1),
        "674c67ab6b387192a174d0759a513e77a492854603e49084e949c50adb86f6ca",
    )
    for resource_type, resource_id, permission_type, digest in [
        ("TASK", "200", "OPERATE", "9d0b89387edf09ba53d8cf8f93bd729b5aa553b24a8900fc16847ee5d655c11e"),
        ("TEMPLATE", "100", "MOCK", "6b7dc78ab5ddef71a0f0ab2ceddefef47d5adc27469b9e4fe162969e5c749176"),
    ]:
        OldGrant.objects.create(
            token=token,
            resource_type=resource_type,
            resource_id=resource_id,
            permission_type=permission_type,
            grant_hash=digest,
        )
    backfill_apps = migrate_to(BACKFILL)
    BackfilledToken = backfill_apps.get_model("permission", "Token")
    BackfilledToken.objects.filter(pk=token.pk).update(
        resource_type="DIRTY", resource_id="DIRTY", permission_type="EDIT"
    )

    migration = importlib.import_module("bkflow.permission.migrations.0006_backfill_token_grants")
    with transaction.atomic():
        migration.backwards(backfill_apps, SimpleNamespace(connection=connection))

    restored = BackfilledToken.objects.get(pk=token.pk)
    assert (restored.resource_type, restored.resource_id, restored.permission_type) == ("", "", "")
