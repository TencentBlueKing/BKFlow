"""幂等索引的长度、身份隔离和摘要碰撞回归。"""

import pytest
from django.db import IntegrityError, models, transaction

from bkflow.harness.exceptions import IdempotencyConflict
from bkflow.harness.models import HarnessIdempotencyRecord
from bkflow.harness.services.idempotency import IdempotencyScope, execute_idempotent

pytestmark = pytest.mark.django_db


def scope(**overrides):
    """构建无需外部服务的完整幂等身份。"""
    return IdempotencyScope(
        **{
            "platform_app": "app",
            "actor": "alice",
            "space_id": 100,
            "tool_name": "validate_workflow",
            "run_scope": "pre-run",
            "idempotency_key": "key",
            **overrides,
        }
    )


def test_idempotency_unique_index_fits_mysql_utf8mb4():
    """防止模型重新引入超过 InnoDB 3072 字节上限的唯一约束。"""
    meta = HarnessIdempotencyRecord._meta
    constraints = [item.fields for item in meta.constraints if isinstance(item, models.UniqueConstraint)]
    constraints += [(field.name,) for field in meta.fields if field.unique]
    for fields in constraints:
        size = sum(
            meta.get_field(name).max_length * 4 if isinstance(meta.get_field(name), models.CharField) else 8
            for name in fields
        )
        assert size <= 3072, (fields, size)


def test_maximum_length_four_byte_unicode_replays_without_truncation():
    """不能通过截短字段或降字符集修复索引。"""
    identity = scope(
        platform_app="😀" * 128,
        actor="🐧" * 128,
        tool_name="🚀" * 128,
        run_scope="🌍" * 255,
        idempotency_key="🔑" * 255,
    )
    effects = []
    first = execute_idempotent(identity, "a" * 64, lambda: effects.append(1) or {"ok": True})
    second = execute_idempotent(identity, "a" * 64, lambda: effects.append(2))
    first.record.refresh_from_db()
    assert second.replayed is True
    assert effects == [1]
    assert {key: getattr(first.record, key) for key in identity.as_dict()} == identity.as_dict()


@pytest.mark.parametrize(
    "overrides",
    [
        {"platform_app": "app:alice", "actor": ""},
        {"platform_app": "APP"},
        {"actor": "Alice"},
        {"space_id": 101},
        {"tool_name": "other"},
        {"run_scope": "other"},
        {"idempotency_key": "KEY"},
        {"idempotency_key": "key "},
        {"idempotency_key": "kéy"},
    ],
)
def test_each_exact_scope_has_its_own_owner(overrides):
    """摘要须包含六个维度且不受数据库大小写、重音和尾空格排序规则影响。"""
    first = execute_idempotent(scope(), "a" * 64, lambda: {"owner": 1})
    other = execute_idempotent(scope(**overrides), "a" * 64, lambda: {"owner": 2})
    assert other.replayed is False
    assert other.response_snapshot == {"owner": 2}
    assert other.record.pk != first.record.pk


def test_digest_collision_never_replays_foreign_response():
    """模拟摘要命中但六维身份不同，必须在回放或副作用之前拒绝。"""
    victim = execute_idempotent(scope(), "a" * 64, lambda: {"private": True})
    other = execute_idempotent(scope(actor="bob"), "a" * 64, lambda: {"other": True})
    other_digest = other.record.scope_hash
    other.record.hard_delete()
    HarnessIdempotencyRecord._base_manager.filter(pk=victim.record.pk).update(scope_hash=other_digest)
    effects = []
    with pytest.raises(IdempotencyConflict):
        execute_idempotent(scope(actor="bob"), "a" * 64, lambda: effects.append("unsafe"))
    assert effects == []
    victim.record.refresh_from_db()
    assert victim.record.response_snapshot == {"private": True}


def test_bulk_create_derives_the_same_identity_as_normal_create():
    """批量插入不得留下空摘要，也不能绕过数据库去重。"""
    first = HarnessIdempotencyRecord(**scope().as_dict(), request_hash="a" * 64)
    HarnessIdempotencyRecord.objects.bulk_create([first])
    stored = HarnessIdempotencyRecord.objects.get()
    assert len(stored.scope_hash) == 64
    with pytest.raises(IntegrityError), transaction.atomic():
        HarnessIdempotencyRecord.objects.create(**scope().as_dict(), request_hash="a" * 64)


def test_string_space_id_replays_integer_space_id():
    """ORM 支持的整数字符串必须在摘要之前归一，避免同一空间重复写入。"""
    first = execute_idempotent(scope(space_id="100"), "a" * 64, lambda: {"ok": True})
    second = execute_idempotent(scope(space_id=100), "a" * 64, lambda: {"unsafe": True})
    assert second.replayed is True
    assert second.record.pk == first.record.pk


def test_set_based_identity_updates_cannot_leave_a_stale_digest():
    """集合更新无法逐行重新派生摘要，必须拒绝修改身份字段。"""
    result = execute_idempotent(scope(), "a" * 64, lambda: {"ok": True})
    with pytest.raises(ValueError):
        HarnessIdempotencyRecord.objects.filter(pk=result.record.pk).update(actor="bob")
    result.record.refresh_from_db()
    assert result.record.actor == "alice"


def test_partial_save_recomputes_digest_when_identity_changes():
    """save(update_fields=...) 修改身份时不能丢掉派生摘要。"""
    result = execute_idempotent(scope(), "a" * 64, lambda: {"ok": True})
    old_hash = result.record.scope_hash
    result.record.actor = "bob"
    result.record.save(update_fields=["actor"])
    result.record.refresh_from_db()
    assert result.record.scope_hash != old_hash
    assert execute_idempotent(scope(actor="bob"), "a" * 64, lambda: {"unsafe": True}).replayed is True
