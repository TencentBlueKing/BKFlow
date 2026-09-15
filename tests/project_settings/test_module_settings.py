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


def test_python_code_plugin_settings_are_loaded_from_environment():
    """Python 代码节点的运行参数应能通过部署环境变量调整。"""
    process_env = os.environ.copy()
    process_env.update(
        {
            "DJANGO_SETTINGS_MODULE": "module_settings",
            "BKFLOW_MODULE_TYPE": "engine",
            "BKFLOW_DATABASE_NAME": "test",
            "BKFLOW_DATABASE_USER": "test",
            "BKFLOW_DATABASE_HOST": "127.0.0.1",
            "BKFLOW_DATABASE_PORT": "3306",
            "PYTHON_CODE_PLUGIN_TIMEOUT": "9",
            "PYTHON_CODE_PLUGIN_QUEUE_TIMEOUT": "3",
            "PYTHON_CODE_PLUGIN_MAX_LENGTH": "12345",
            "PYTHON_CODE_PLUGIN_MEMORY_LIMIT_MB": "384",
            "PYTHON_CODE_PLUGIN_MAX_CONCURRENT_PROCESSES": "7",
            "PYTHON_CODE_PLUGIN_MAX_RESPONSE_SIZE_BYTES": "654321",
        }
    )
    script = """
import json
from django.conf import settings

print(json.dumps([
    settings.PYTHON_CODE_PLUGIN_TIMEOUT,
    settings.PYTHON_CODE_PLUGIN_QUEUE_TIMEOUT,
    settings.PYTHON_CODE_PLUGIN_MAX_LENGTH,
    settings.PYTHON_CODE_PLUGIN_MEMORY_LIMIT_MB,
    settings.PYTHON_CODE_PLUGIN_MAX_CONCURRENT_PROCESSES,
    settings.PYTHON_CODE_PLUGIN_MAX_RESPONSE_SIZE_BYTES,
]))
"""

    completed_process = subprocess.run(
        [sys.executable, "-c", script], env=process_env, text=True, capture_output=True, check=False
    )

    assert completed_process.returncode == 0, completed_process.stderr
    assert json.loads(completed_process.stdout.splitlines()[-1]) == [9, 3, 12345, 384, 7, 654321]
