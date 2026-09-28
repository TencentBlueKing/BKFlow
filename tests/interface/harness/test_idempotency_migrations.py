"""已有幂等记录升级的回填、可重入和失败封闭验证。"""

import importlib
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader

from bkflow.harness.services.idempotency import IdempotencyScope, execute_idempotent

SCHEMA = ("harness", "0001_idempotency_safe_initial")
BACKFILL = ("harness", "0009_backfill_idempotency_scope_hash")

pytestmark = pytest.mark.django_db(transaction=True)


def migrate_to(target):
    """使用真实迁移执行器，而非通过运行时模型模拟升级。"""
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return executor.loader.project_state([target]).apps


@pytest.fixture
def legacy_records():
    """回到可空摘要阶段，在退出前恢复最新结构。"""
    latest = MigrationExecutor(connection).loader.graph.leaf_nodes("harness")
    old_apps = migrate_to(SCHEMA)
    Record = old_apps.get_model("harness", "HarnessIdempotencyRecord")
    yield Record, old_apps
    Record.objects.all().delete()
    MigrationExecutor(connection).migrate(latest)


def identity(**overrides):
    """提供冻结迁移与当前协议共同接受的六维身份。"""
    return {
        "platform_app": "legacy",
        "actor": "alice",
        "space_id": 42,
        "tool_name": "validate_workflow",
        "run_scope": "pre-run",
        "idempotency_key": "before-upgrade",
        **overrides,
    }


def test_replacement_preserves_the_entire_incremental_schema_state():
    """移除互相抵消的操作后，所有模型的最终状态必须与原增量链一致。"""
    replacement = MigrationLoader(connection).project_state([SCHEMA])
    incremental = MigrationLoader(connection, replace_migrations=False).project_state(
        [("harness", "0008_idempotency_scope_hash")]
    )
    assert replacement.models == incremental.models


def test_mysql_utf8mb4_uses_a_full_digest_unique_index():
    """检查真实落库的字符集与唯一索引，防止配置错误让测试误通过。"""
    if connection.vendor != "mysql" or connection.settings_dict.get("OPTIONS", {}).get("charset") != "utf8mb4":
        pytest.skip("仅用于真实 MySQL utf8mb4 建库验收")
    table = "harness_harnessidempotencyrecord"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT CHARACTER_SET_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
            [table, "idempotency_key"],
        )
        assert cursor.fetchone() == ("utf8mb4",)
        constraints = connection.introspection.get_constraints(cursor, table)
    assert "uniq_harness_idempotency_scope" not in constraints
    assert any(item["unique"] and item["columns"] == ["scope_hash"] for item in constraints.values())


def test_backfill_preserves_snapshot_and_replays_existing_record(legacy_records):
    """升级后同一请求必须回放旧响应，不能创建第二条记录或重做副作用。"""
    Record, _ = legacy_records
    old = Record.objects.create(
        **identity(), request_hash="a" * 64, status="COMPLETED", response_snapshot={"old": True}
    )
    apps = migrate_to(BACKFILL)
    row = apps.get_model("harness", "HarnessIdempotencyRecord").objects.get(pk=old.pk)
    assert row.scope_hash is not None
    assert row.create_at == old.create_at
    assert row.update_at == old.update_at
    effects = []
    result = execute_idempotent(IdempotencyScope(**identity()), "a" * 64, lambda: effects.append("unsafe"))
    assert result.replayed is True
    assert result.record.pk == old.pk
    assert result.response_snapshot == {"old": True}
    assert effects == []


def test_backfill_duplicate_identity_fails_without_losing_records(legacy_records):
    """迁移窗口里的重复记录不能静默去重或覆盖，且回填需事务回滚。"""
    Record, apps = legacy_records
    Record.objects.create(**identity(), request_hash="a" * 64)
    Record.objects.create(**identity(), request_hash="b" * 64)
    migration = importlib.import_module("bkflow.harness.migrations.0009_backfill_idempotency_scope_hash")
    with pytest.raises(RuntimeError, match="idempotency"):
        migration.backfill_scope_hash(apps, SimpleNamespace(connection=connection))
    assert Record.objects.count() == 2
    assert Record.objects.filter(scope_hash__isnull=True).count() == 2


def test_backfill_reentry_validates_preexisting_digest(legacy_records):
    """重跑回填保留正确摘要，但遇到损坏摘要不得标记升级成功。"""
    Record, apps = legacy_records
    record = Record.objects.create(**identity(), request_hash="a" * 64)
    migration = importlib.import_module("bkflow.harness.migrations.0009_backfill_idempotency_scope_hash")
    editor = SimpleNamespace(connection=connection)
    migration.backfill_scope_hash(apps, editor)
    record.refresh_from_db()
    digest = record.scope_hash
    migration.backfill_scope_hash(apps, editor)
    record.refresh_from_db()
    assert record.scope_hash == digest
    Record.objects.filter(pk=record.pk).update(scope_hash="f" * 64)
    with pytest.raises(RuntimeError, match="idempotency"):
        migration.backfill_scope_hash(apps, editor)


def test_final_schema_disallows_missing_or_duplicate_digest():
    """绕过模型保存也不能在最终数据库结构中留下空摘要或重复身份。"""
    apps = MigrationExecutor(connection).loader.project_state().apps
    Record = apps.get_model("harness", "HarnessIdempotencyRecord")
    with pytest.raises(IntegrityError), transaction.atomic():
        Record.objects.create(**identity(), request_hash="a" * 64, scope_hash=None)
    Record.objects.create(**identity(), request_hash="a" * 64, scope_hash="a" * 64)
    with pytest.raises(IntegrityError), transaction.atomic():
        Record.objects.create(**identity(actor="bob"), request_hash="a" * 64, scope_hash="a" * 64)


def test_original_p4_history_upgrades_without_recreating_tables(legacy_records):
    """从真实 0007 结构和迁移记录升级，验证 Django 选择增量而不是重新建表。"""
    if connection.vendor == "mysql" and connection.settings_dict.get("OPTIONS", {}).get("charset") == "utf8mb4":
        pytest.skip("旧 P4 索引无法在 utf8mb4 创建；此路径在 SQLite 和真实 MySQL utf8 上验证")
    _, _ = legacy_records
    old_target = ("harness", "0007_p4_feedback_evalops")
    loader = MigrationLoader(connection, replace_migrations=False)
    old_state = loader.project_state([old_target])
    incremental = loader.disk_migrations[("harness", "0008_idempotency_scope_hash")]
    # 使用原增量迁移的真实反向 DDL 构造旧版本夹具，不手写或 fake 表结构。
    with connection.schema_editor() as editor:
        incremental.unapply(old_state, editor)
    executor = MigrationExecutor(connection)
    executor.recorder.record_unapplied(*SCHEMA)
    executor.recorder.record_unapplied("harness", "0008_idempotency_scope_hash")
    OldRecord = old_state.apps.get_model("harness", "HarnessIdempotencyRecord")
    old = OldRecord.objects.create(
        **identity(), request_hash="a" * 64, status="COMPLETED", response_snapshot={"p4": True}
    )
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes("harness")
    assert [migration.name for migration, _ in executor.migration_plan(latest)] == [
        "0008_idempotency_scope_hash",
        "0009_backfill_idempotency_scope_hash",
        "0010_require_idempotency_scope_hash",
    ]
    executor.migrate(latest)
    result = execute_idempotent(IdempotencyScope(**identity()), "a" * 64, lambda: {"unsafe": True})
    assert result.record.pk == old.pk
    assert result.replayed is True
    assert result.response_snapshot == {"p4": True}
