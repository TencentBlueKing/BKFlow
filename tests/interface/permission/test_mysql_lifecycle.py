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

MySQL 两连接的真实行锁竞争与原子签发回归。
"""

from datetime import timedelta
from functools import partial
from threading import Event, Thread
from time import monotonic

import pytest
from django.db import connection, connections, transaction

from bkflow.permission.grants import Grant, grant_hash
from bkflow.permission.models import Token, TokenGrant
from bkflow.permission.services import issue_token, renew_token, revoke_tokens

pytestmark = [pytest.mark.django_db(transaction=True)]
GRANTS = (Grant("TASK", "200", "OPERATE"), Grant("TEMPLATE", "100", "MOCK"))


def issue(grants=GRANTS):
    """签发可自动续期的完整组合票据。"""
    return issue_token(1, "alice", grants, 3600, True)


class DatabaseWorker:
    """在独立连接执行真实服务，回传结果和异常并保证关闭连接。"""

    def __init__(self, operation):
        self.ready = Event()
        self.done = Event()
        self.result = None
        self.error = None
        self.connection_id = None
        self.thread = Thread(target=self.run, args=(operation,), daemon=True)
        self.thread.start()

    def run(self, operation):
        """线程局部 Django 连接不与主线程共享。"""
        try:
            connections.close_all()
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 10")
                cursor.execute("SELECT CONNECTION_ID()")
                self.connection_id = cursor.fetchone()[0]
            self.ready.set()
            self.result = operation()
        except BaseException as error:
            self.error = error
        finally:
            connections.close_all()
            self.done.set()

    def finish(self):
        """有限等待并在测试线程重新抛出 worker 错误。"""
        self.thread.join(12)
        assert not self.thread.is_alive(), "数据库 worker 未在有限超时内结束"
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture(autouse=True)
def mysql_only():
    """SQLite 跳过真实 MySQL 锁测试，不将跳过当成验证通过。"""
    if connection.vendor != "mysql":
        pytest.skip("requires real MySQL 8.0 row locks")


def wait_for_row_lock(worker, first_pk):
    """从 MySQL 等待图证明 worker 正被本连接阻塞，无需 PROCESS 权限。"""
    assert worker.ready.wait(5), "worker 未建立连接"
    with connection.cursor() as cursor:
        cursor.execute("SELECT CONNECTION_ID()")
        owner_id = cursor.fetchone()[0]
        assert owner_id != worker.connection_id
        deadline = monotonic() + 5
        while monotonic() < deadline:
            cursor.execute(
                "SELECT waiting.INDEX_NAME, waiting.LOCK_DATA FROM performance_schema.data_lock_waits AS waits "
                "JOIN performance_schema.data_locks AS waiting "
                "ON waiting.ENGINE_LOCK_ID = waits.REQUESTING_ENGINE_LOCK_ID "
                "JOIN performance_schema.threads AS requester "
                "ON requester.THREAD_ID = waits.REQUESTING_THREAD_ID "
                "JOIN performance_schema.threads AS blocker "
                "ON blocker.THREAD_ID = waits.BLOCKING_THREAD_ID "
                "WHERE requester.PROCESSLIST_ID = %s AND blocker.PROCESSLIST_ID = %s",
                [worker.connection_id, owner_id],
            )
            waiting = cursor.fetchone()
            if waiting:
                assert waiting[0] == "PRIMARY"
                assert first_pk in waiting[1]
                cursor.execute(
                    "SELECT COUNT(*) FROM performance_schema.data_locks AS locks "
                    "JOIN performance_schema.threads AS threads ON threads.THREAD_ID = locks.THREAD_ID "
                    "WHERE threads.PROCESSLIST_ID = %s AND locks.OBJECT_NAME = %s "
                    "AND locks.INDEX_NAME IS NOT NULL AND locks.LOCK_STATUS = 'GRANTED'",
                    [worker.connection_id, Token._meta.db_table],
                )
                assert cursor.fetchone()[0] == 0, "等待首个主键前不应持有其他记录或二级索引锁"
                assert not worker.done.is_set()
                return
            if worker.done.wait(0.01):
                worker.finish()
                pytest.fail("worker 未等待主票据锁就已完成")
    pytest.fail("未观察到两个真实连接之间的 MySQL 行锁等待")


@pytest.mark.parametrize("first", ["revoke", "renew"])
def test_revoke_and_renew_are_serialized_on_parent(first):
    """撤销先提交阻止续活；续期先提交时后续撤销覆盖它。"""
    token = issue()
    renew = partial(renew_token, token.pk, "alice")
    revoke = partial(revoke_tokens, 1, {"token": token.pk})
    first_operation, second_operation = (revoke, renew) if first == "revoke" else (renew, revoke)
    worker = None
    try:
        with transaction.atomic():
            Token.objects.select_for_update().get(pk=token.pk)
            worker = DatabaseWorker(second_operation)
            wait_for_row_lock(worker, token.pk)
            initial_result = first_operation()
    finally:
        if worker is not None:
            later_result = worker.finish()
    assert initial_result == 1 if first == "revoke" else initial_result[0] is True
    assert later_result[0] is False if first == "revoke" else later_result == 1
    token.refresh_from_db()
    assert token.has_expired()
    assert token.get_grants() == GRANTS


@pytest.mark.parametrize("first", ["revoke", "reuse"])
@pytest.mark.parametrize("composite", [False, True])
@pytest.mark.parametrize("multiple", [False, True])
def test_apply_reuse_and_revoke_are_serialized_on_parent(first, composite, multiple):
    """旧/组合、多候选与资源过滤均按主键取锁，并保留最晚过期复用。"""
    grants = GRANTS if composite else (GRANTS[1],)
    apply = partial(issue, grants)
    token = apply()
    token.expired_time += timedelta(hours=1)
    token.save(update_fields=["expired_time"])
    token_ids = [token.pk]
    if multiple:
        duplicate = Token.objects.create(
            token="0" * 32,
            **{
                field: getattr(token, field)
                for field in ("space_id", "user", "resource_type", "resource_id", "permission_type", "grant_set_hash")
            },
            expired_time=token.expired_time - timedelta(minutes=30),
        )
        TokenGrant.objects.bulk_create(
            [TokenGrant(token=duplicate, **grant.as_dict(), grant_hash=grant_hash(grant)) for grant in grants]
            if composite
            else []
        )
        token_ids.append(duplicate.pk)
    filters = {"user": "alice", "resource_id": grants[0].resource_id} if multiple else {"token": token.pk}
    revoke = partial(revoke_tokens, 1, filters)
    first_operation, second_operation = (revoke, apply) if first == "revoke" else (apply, revoke)
    worker = None
    try:
        with transaction.atomic():
            for token_id in sorted(token_ids):
                Token.objects.select_for_update().get(pk=token_id)
            worker = DatabaseWorker(second_operation)
            wait_for_row_lock(worker, min(token_ids))
            initial_result = first_operation()
    finally:
        if worker is not None:
            later_result = worker.finish()
    for original in Token.objects.filter(pk__in=token_ids):
        assert original.has_expired()
    if first == "revoke":
        assert initial_result == len(token_ids)
        assert later_result.pk not in token_ids
        assert not later_result.has_expired()
        assert later_result.get_grants() == grants
        assert later_result.grants.count() == (2 if composite else 0)
    else:
        assert initial_result.pk == token.pk
        assert later_result == len(token_ids)
        assert Token.objects.count() == len(token_ids)


def test_concurrent_same_set_issuance_keeps_every_ticket_complete():
    """两连接均查无候选后并发签发，两张等价票据都必须原子保存全部明细。"""
    main_read = Event()
    worker_read = Event()
    parent_table = connection.ops.quote_name(Token._meta.db_table)

    def after_candidate_read(own_read, other_read):
        """只在真实候选 SELECT 完成后设置屏障，不替换 SQL 或锁。"""

        def wrapper(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.startswith("SELECT") and f"FROM {parent_table}" in sql and "FOR UPDATE" not in sql:
                own_read.set()
                assert other_read.wait(5), "另一连接没有完成真实候选查询"
            return result

        return wrapper

    def worker_issue():
        """独立连接完成同集合申请。"""
        with connection.execute_wrapper(after_candidate_read(worker_read, main_read)):
            return issue()

    worker = DatabaseWorker(worker_issue)
    try:
        assert worker.ready.wait(5)
        with connection.execute_wrapper(after_candidate_read(main_read, worker_read)):
            main_token = issue()
    finally:
        worker_token = worker.finish()
    assert main_read.is_set() and worker_read.is_set()
    assert main_token.pk != worker_token.pk
    assert Token.objects.count() == 2
    assert TokenGrant.objects.count() == 4
    for token in Token.objects.all():
        assert not token.has_expired()
        assert token.get_grants() == GRANTS
        assert token.grants.count() == 2


def test_mysql_case_distinct_grants_keep_unique_hashes_and_identity():
    """默认不区分大小写的MySQL排序规则仍可保存两个不同大小写授权。"""
    grants = (Grant("SCOPE", "biz_A", "VIEW"), Grant("SCOPE", "biz_a", "VIEW"))
    token = issue(grants)
    assert token.get_grants() == grants
    assert token.grants.count() == 2
    assert token.grants.values("grant_hash").distinct().count() == 2
    assert issue(tuple(reversed(grants))).pk == token.pk
