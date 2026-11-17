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
import importlib
import json
import os
import subprocess
import sys

import pytest

import env
from module_settings import BKFLOWDatabaseConfig, BKFLOWModule


@pytest.mark.parametrize(
    "env_insert_fixture, original_value_fixture",
    [
        (
            {
                "BKFLOW_MODULE_CODE": "engine_module",
                "BKFLOW_MODULE_TYPE": "engine",
                "BKFLOW_RESOURCE_ISOLATION_LEVEL": "only_calculation",
            },
            BKFLOWModule(broker_url="", code="engine_module", type="engine", isolation_level="only_calculation"),
        ),
        (
            {
                "BKFLOW_MODULE_CODE": "engine_module1",
                "BKFLOW_MODULE_TYPE": "engine",
                "BKFLOW_RESOURCE_ISOLATION_LEVEL": "all_resource",
            },
            BKFLOWModule(broker_url="", code="engine_module1", type="engine", isolation_level="all_resource"),
        ),
    ],
    indirect=True,
)
def test_bkflow_module(env_insert_fixture, original_value_fixture):
    importlib.reload(env)
    bkflow_module = BKFLOWModule.get_module()
    assert bkflow_module == original_value_fixture


@pytest.mark.parametrize(
    "env_insert_fixture, original_value_fixture",
    [
        (
            {
                "BKFLOW_DATABASE_ENGINE": "django.db.backends.mysql",
                "BKFLOW_DATABASE_NAME": "db_name",
                "BKFLOW_DATABASE_USER": "db_user",
                "BKFLOW_DATABASE_HOST": "db_host",
                "BKFLOW_DATABASE_PORT": "db_port",
            },
            BKFLOWDatabaseConfig(
                engine="django.db.backends.mysql",
                name="db_name",
                user="db_user",
                password="",
                host="db_host",
                port="db_port",
            ),
        )
    ],
    indirect=True,
)
def test_bkflow_database_config(env_insert_fixture, original_value_fixture):
    importlib.reload(env)
    bkflow_module = BKFLOWDatabaseConfig.get_database_config()
    assert bkflow_module == original_value_fixture


PYTHON_CODE_SWITCH_ENV_NAMES = (
    "PYTHON_CODE_PLUGIN_ENABLED",
    "PYTHON_CODE_PLUGIN_ALLOWED_MODULES",
    "SPACE_PLUGIN_LIST_STR",
)
SECURITY_SWITCH_ENV_NAMES = ("APP_INTERNAL_VALIDATION_SKIP", "SKIP_APIGW_CHECK")


def _load_settings_in_subprocess(overrides, script):
    """在独立进程加载引擎模块配置，避免影响当前测试进程的 settings。"""
    process_env = os.environ.copy()
    for name in PYTHON_CODE_SWITCH_ENV_NAMES + SECURITY_SWITCH_ENV_NAMES:
        process_env.pop(name, None)
    process_env.update(
        {
            "DJANGO_SETTINGS_MODULE": "module_settings",
            "BKFLOW_MODULE_TYPE": "engine",
            "BKFLOW_DATABASE_NAME": "test",
            "BKFLOW_DATABASE_USER": "test",
            "BKFLOW_DATABASE_HOST": "127.0.0.1",
            "BKFLOW_DATABASE_PORT": "3306",
            **overrides,
        }
    )
    completed_process = subprocess.run(
        [sys.executable, "-c", script], env=process_env, text=True, capture_output=True, check=False
    )

    assert completed_process.returncode == 0, completed_process.stderr
    return json.loads(completed_process.stdout.splitlines()[-1])


def test_python_code_plugin_settings_are_loaded_from_environment():
    """Python 代码节点的运行参数应能通过部署环境变量调整。"""
    overrides = {
        "PYTHON_CODE_PLUGIN_ENABLED": "1",
        "PYTHON_CODE_PLUGIN_ALLOWED_MODULES": "math, json",
        "PYTHON_CODE_PLUGIN_TIMEOUT": "9",
        "PYTHON_CODE_PLUGIN_QUEUE_TIMEOUT": "3",
        "PYTHON_CODE_PLUGIN_MAX_LENGTH": "12345",
        "PYTHON_CODE_PLUGIN_MEMORY_LIMIT_MB": "384",
        "PYTHON_CODE_PLUGIN_MAX_CONCURRENT_PROCESSES": "7",
        "PYTHON_CODE_PLUGIN_MAX_RESPONSE_SIZE_BYTES": "654321",
    }
    script = """
import json
from django.conf import settings

print(json.dumps([
    settings.PYTHON_CODE_PLUGIN_ENABLED,
    settings.PYTHON_CODE_PLUGIN_ALLOWED_MODULES,
    settings.PYTHON_CODE_PLUGIN_TIMEOUT,
    settings.PYTHON_CODE_PLUGIN_QUEUE_TIMEOUT,
    settings.PYTHON_CODE_PLUGIN_MAX_LENGTH,
    settings.PYTHON_CODE_PLUGIN_MEMORY_LIMIT_MB,
    settings.PYTHON_CODE_PLUGIN_MAX_CONCURRENT_PROCESSES,
    settings.PYTHON_CODE_PLUGIN_MAX_RESPONSE_SIZE_BYTES,
]))
"""

    assert _load_settings_in_subprocess(overrides, script) == [True, ["math", "json"], 9, 3, 12345, 384, 7, 654321]


def test_python_code_plugin_is_disabled_without_modules_by_default():
    """未配置时 Python 代码节点关闭，且不开放任何模块。"""
    script = """
import json
from django.conf import settings

print(json.dumps([settings.PYTHON_CODE_PLUGIN_ENABLED, settings.PYTHON_CODE_PLUGIN_ALLOWED_MODULES]))
"""

    assert _load_settings_in_subprocess({}, script) == [False, []]


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({}, ["python_code"]),
        ({"SPACE_PLUGIN_LIST_STR": "bk_display,python_code"}, ["bk_display", "python_code"]),
        ({"PYTHON_CODE_PLUGIN_ENABLED": "true"}, []),
        ({"PYTHON_CODE_PLUGIN_ENABLED": "true", "SPACE_PLUGIN_LIST_STR": "bk_display"}, ["bk_display"]),
    ],
)
def test_disabled_python_code_plugin_is_hidden_from_spaces(overrides, expected):
    """节点关闭时只对白名单空间可见，开启后按原有空间插件配置展示。"""
    script = """
import json
from django.conf import settings

# 先由 Django 完整加载模块配置，避免直接导入 config.default 时出现循环导入。
settings.BKFLOW_MODULE
from config import default

print(json.dumps(default.SPACE_PLUGIN_LIST))
"""

    assert _load_settings_in_subprocess(overrides, script) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", True),
        ("true", True),
        (" TRUE ", True),
        ("Yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("False", False),
        ("no", False),
        ("off", False),
        ("", False),
        ("enabled", False),
    ],
)
def test_env_bool_only_accepts_explicit_true_values(monkeypatch, raw, expected):
    """布尔环境变量只把明确的真值当作开启，"0"、"false" 和未知写法均为关闭。"""
    monkeypatch.setenv("BKFLOW_TEST_STRICT_BOOL", raw)

    assert env._env_bool("BKFLOW_TEST_STRICT_BOOL") is expected


def test_env_bool_uses_default_when_unset(monkeypatch):
    """未配置时返回调用方给定的默认值。"""
    monkeypatch.delenv("BKFLOW_TEST_STRICT_BOOL", raising=False)

    assert env._env_bool("BKFLOW_TEST_STRICT_BOOL") is False
    assert env._env_bool("BKFLOW_TEST_STRICT_BOOL", True) is True


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({}, [False, False]),
        ({"APP_INTERNAL_VALIDATION_SKIP": "0", "SKIP_APIGW_CHECK": "0"}, [False, False]),
        ({"APP_INTERNAL_VALIDATION_SKIP": "false", "SKIP_APIGW_CHECK": "False"}, [False, False]),
        ({"APP_INTERNAL_VALIDATION_SKIP": "1", "SKIP_APIGW_CHECK": "true"}, [True, True]),
    ],
)
def test_security_skip_switches_are_parsed_strictly(overrides, expected):
    """内部调用校验和 APIGW 来源校验的跳过开关配置为 "0"/"false" 时必须保持关闭。"""
    script = """
import json
from django.conf import settings

# 先由 Django 完整加载模块配置，避免直接导入 config.default 时出现循环导入。
settings.BKFLOW_MODULE
from config import default

print(json.dumps([default.APP_INTERNAL_VALIDATION_SKIP, default.SKIP_APIGW_CHECK]))
"""

    assert _load_settings_in_subprocess(overrides, script) == expected
