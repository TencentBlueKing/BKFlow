"""校验兼容后端的版本边界、SQL 生成以及配置隔离。"""

from copy import deepcopy

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import NotSupportedError
from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper

from bkflow.db.mysql57.base import DatabaseWrapper
from bkflow.utils.mysql57_compat import configure_mysql57_compat


def make_connection(version, mariadb=False, backend=DatabaseWrapper):
    """无需连接数据库即可验证版本门槛和 SQL 生成能力。"""
    connection = backend({"ENGINE": "django.db.backends.mysql", "OPTIONS": {}})
    connection.mysql_version = version
    connection.mysql_is_mariadb = mariadb
    return connection


def test_standard_backend_still_rejects_mysql57():
    """兼容后端不能修改 Django 原生后端的版本检查。"""
    connection = make_connection((5, 7, 20), backend=MySQLDatabaseWrapper)
    with pytest.raises(NotSupportedError, match="MySQL 8 or later"):
        connection.check_database_version_supported()


@pytest.mark.parametrize("version", [(5, 7, 20), (5, 7, 44), (8, 0, 46)])
def test_compat_backend_accepts_supported_versions(version):
    """兼容后端允许已有的 MySQL 5.7.20+ 部署继续使用。"""
    make_connection(version).check_database_version_supported()


@pytest.mark.parametrize("version,mariadb", [((5, 6, 51), False), ((5, 7, 19), False), ((10, 3, 39), True)])
def test_older_database_versions_remain_rejected(version, mariadb):
    """不通过关闭全局检查来放行所有数据库版本。"""
    with pytest.raises(NotSupportedError):
        make_connection(version, mariadb).check_database_version_supported()


def test_mysql57_queries_keep_legacy_sql():
    """恢复 5.7 能执行的正则和无表查询语法。"""
    connection = make_connection((5, 7, 20))
    assert connection.ops.regex_lookup("regex") % ("name", "%s") == "name REGEXP BINARY %s"
    assert connection.ops.regex_lookup("iregex") % ("name", "%s") == "name REGEXP %s"
    assert "SELECT 1" + connection.features.bare_select_suffix + " WHERE 1 = 1" == "SELECT 1 FROM DUAL WHERE 1 = 1"
    assert not connection.features.supports_over_clause
    assert not connection.features.has_select_for_update_skip_locked
    assert not connection.features.has_select_for_update_nowait
    assert not connection.features.supports_column_check_constraints


@pytest.mark.parametrize("version,mariadb", [((8, 0, 46), False), ((10, 4, 34), True)])
def test_supported_database_sql_is_unchanged(version, mariadb):
    """MySQL 8 和 MariaDB 继续使用 Django 原有 SQL。"""
    adapted = make_connection(version, mariadb)
    original = make_connection(version, mariadb, MySQLDatabaseWrapper)
    adapted.check_database_version_supported()
    for lookup in ("regex", "iregex"):
        assert adapted.ops.regex_lookup(lookup) == original.ops.regex_lookup(lookup)
    assert adapted.features.bare_select_suffix == original.features.bare_select_suffix


def test_non_mysql_databases_keep_original_config(monkeypatch):
    """其他后端不受 MySQL 兼容处理及其 Django 版本约束影响。"""
    databases = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    monkeypatch.setattr("bkflow.utils.mysql57_compat.VERSION", (5, 0, 0, "final", 0))
    assert configure_mysql57_compat(databases) is databases


def test_default_compat_preserves_connection_options():
    """无需开关即可覆盖多数据库配置，同时保留 SQLite 和自定义后端。"""
    databases = {
        "default": {"ENGINE": "django.db.backends.mysql", "NAME": "fixture", "OPTIONS": {"charset": "utf8mb4"}},
        "engine": {"ENGINE": "django.db.backends.mysql", "NAME": "engine"},
        "sqlite": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        "custom": {"ENGINE": "custom.mysql", "NAME": "custom"},
    }
    before = deepcopy(databases)
    adapted = configure_mysql57_compat(databases)
    assert databases == before
    for alias in ("default", "engine"):
        assert adapted[alias] == {**before[alias], "ENGINE": "bkflow.db.mysql57"}
    for alias in ("sqlite", "custom"):
        assert adapted[alias] == before[alias]


@pytest.mark.parametrize("version", [(4, 1, 13, "final", 0), (5, 0, 0, "final", 0)])
def test_other_django_versions_require_revalidation(monkeypatch, version):
    """切换 Django 系列后必须重新评估兼容后端，不能静默沿用补丁。"""
    monkeypatch.setattr("bkflow.utils.mysql57_compat.VERSION", version)
    with pytest.raises(ImproperlyConfigured, match="requires Django 4.2"):
        configure_mysql57_compat({"default": {"ENGINE": "django.db.backends.mysql"}})
