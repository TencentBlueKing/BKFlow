"""验证独立统计库在 Django 初始化前完成配置，不访问外部数据库。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATISTICS_ENV = {
    "STATISTICS_DB_HOST": "statistics.example.invalid",
    "STATISTICS_DB_NAME": "statistics_fixture",
    "STATISTICS_DB_USER": "fixture_user",
    "STATISTICS_DB_PASSWORD": "fixture_password",
    "STATISTICS_DB_PORT": "3307",
}


def load_database_settings(environment="stag", module="interface", overrides=None, databases=None):
    """隔离平台配置，执行真实 settings、数据库默认值初始化和统计应用 ready。"""
    process_env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(ROOT),
        "DJANGO_SETTINGS_MODULE": "settings",
        "BKPAAS_ENVIRONMENT": environment,
        "BKFLOW_MODULE_TYPE": module,
        "STATISTICS_ENABLED": "false",
    }
    process_env.update(overrides or {})
    if databases is None:
        databases = {
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": f"{module}_fixture",
                "OPTIONS": {"charset": "utf8mb4"},
                "ATOMIC_REQUESTS": True,
            },
            "replica": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        }
    script = """
import json
import os
import sys
from copy import deepcopy
from types import ModuleType
from unittest.mock import Mock, patch

import django
from django.db.backends.base.base import BaseDatabaseWrapper

patch.object(BaseDatabaseWrapper, "connect", side_effect=AssertionError("禁止连接数据库")).start()
config = ModuleType("config")
config.__path__ = []
config_name = "config." + os.environ["BKPAAS_ENVIRONMENT"]
platform_settings = ModuleType(config_name)
platform_settings.DATABASES = json.loads(sys.argv[1])
platform_settings.INSTALLED_APPS = ["bkflow.statistics"]
platform_settings.SECRET_KEY = "fixture_secret"
sys.modules["config"] = config
sys.modules[config_name] = platform_settings

# 统计信号的业务依赖与数据库初始化无关，只验证 ready 仍遵守统计开关。
handlers = ModuleType("bkflow.statistics.signals.handlers")
handlers.register_statistics_signals = Mock()
sys.modules[handlers.__name__] = handlers

from django.conf import settings
from django.core.handlers.base import BaseHandler
from django.db import connections

# 模拟模型加载阶段已经读取并缓存连接配置，再执行真正的 AppConfig.ready。
before_ready = deepcopy(connections.settings)
django.setup()
BaseHandler().make_view_atomic(lambda request: None)

from bkflow.statistics.conf import StatisticsSettings

print(json.dumps({
    "databases": connections.settings,
    "before_ready": before_ready,
    "db_alias": StatisticsSettings.get_db_alias(),
    "signals_registered": handlers.register_statistics_signals.call_count,
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, json.dumps(databases)],
        cwd=ROOT,
        env=process_env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.parametrize("environment", ["dev", "stag", "prod"])
@pytest.mark.parametrize("module", ["interface", "engine"])
def test_statistics_database_is_normalized_before_ready(environment, module):
    """所有环境和模块都提前注册统计库，保留主库配置并继续注册统计信号。"""
    result = load_database_settings(environment, module, {**STATISTICS_ENV, "STATISTICS_ENABLED": "true"})
    assert result["before_ready"] == result["databases"]
    assert result["db_alias"] == "statistics"
    assert result["signals_registered"] == 1
    databases = result["databases"]
    assert databases["default"]["NAME"] == f"{module}_fixture"
    assert databases["default"]["OPTIONS"] == {"charset": "utf8mb4"}
    assert databases["default"]["ATOMIC_REQUESTS"] is True
    assert databases["replica"]["ENGINE"] == "django.db.backends.sqlite3"
    statistics = databases["statistics"]
    assert statistics["ENGINE"] == "bkflow.db.mysql57"
    for setting in ("HOST", "NAME", "USER", "PASSWORD", "PORT"):
        assert statistics[setting] == STATISTICS_ENV[f"STATISTICS_DB_{setting}"]
    assert statistics["ATOMIC_REQUESTS"] is False
    assert statistics["AUTOCOMMIT"] is True
    assert statistics["CONN_MAX_AGE"] == 0
    assert statistics["CONN_HEALTH_CHECKS"] is False
    assert statistics["OPTIONS"] == {}
    assert statistics["TIME_ZONE"] is None
    assert statistics["TEST"]["MIGRATE"] is True


@pytest.mark.parametrize("host,name", [("", ""), ("statistics.example.invalid", ""), ("", "statistics_fixture")])
def test_incomplete_statistics_configuration_falls_back_to_default(host, name):
    """未配置独立统计库或仅提供部分连接信息时，仍使用主库且不注册信号。"""
    result = load_database_settings(overrides={"STATISTICS_DB_HOST": host, "STATISTICS_DB_NAME": name})
    assert "statistics" not in result["databases"]
    assert result["db_alias"] == "default"
    assert result["signals_registered"] == 0


def test_existing_statistics_database_is_preserved_without_environment_override():
    """未提供环境变量时，保留平台或模块已经声明的自定义统计库。"""
    databases = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        "statistics": {"ENGINE": "django.db.backends.sqlite3", "NAME": "custom_fixture", "ATOMIC_REQUESTS": True},
    }
    result = load_database_settings(databases=databases)
    assert result["before_ready"] == result["databases"]
    assert result["databases"]["statistics"]["ENGINE"] == "django.db.backends.sqlite3"
    assert result["databases"]["statistics"]["NAME"] == "custom_fixture"
    assert result["databases"]["statistics"]["ATOMIC_REQUESTS"] is True
    assert result["db_alias"] == "statistics"


def test_statistics_environment_keeps_precedence_over_existing_configuration():
    """显式统计库环境变量继续覆盖已有别名，且在 ready 前完成后端适配。"""
    databases = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        "statistics": {"ENGINE": "django.db.backends.sqlite3", "NAME": "custom_fixture"},
    }
    result = load_database_settings(overrides=STATISTICS_ENV, databases=databases)
    assert result["before_ready"] == result["databases"]
    assert result["databases"]["statistics"]["ENGINE"] == "bkflow.db.mysql57"
    assert result["databases"]["statistics"]["NAME"] == STATISTICS_ENV["STATISTICS_DB_NAME"]
