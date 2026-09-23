"""
TencentBlueKing is pleased to support the open source community by making
BlueKing Flow Engine Service available.
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

from copy import deepcopy

import pytest

import env
from config.default import logging_addition_settings

BASE_LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(levelname)s %(message)s"},
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "root": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "component": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        "root": {"handlers": ["root"], "level": "INFO", "propagate": True},
    },
}


def count_handler_calls(logging_config, logger_name, handler_name):
    count = 0
    current_name = logger_name

    while current_name:
        logger_config = logging_config["loggers"].get(current_name)
        if logger_config:
            count += logger_config["handlers"].count(handler_name)
            if not logger_config.get("propagate", True):
                break

        current_name = current_name.rpartition(".")[0] or ("root" if current_name != "root" else "")

    return count


@pytest.mark.parametrize("data_source", ["DATABASE", "PaaS3"])
@pytest.mark.parametrize(
    "logger_name",
    ["bamboo_engine", "pipeline_engine", "pipeline.logging", "pipeline.eri.log"],
)
def test_engine_log_is_written_to_root_handler_once(monkeypatch, data_source, logger_name):
    monkeypatch.setattr(env, "NODE_LOG_DATA_SOURCE", data_source)
    logging_config = deepcopy(BASE_LOGGING)

    logging_addition_settings(logging_config)

    assert count_handler_calls(logging_config, logger_name, "root") == 1


def test_database_node_log_handlers_are_preserved(monkeypatch):
    monkeypatch.setattr(env, "NODE_LOG_DATA_SOURCE", "DATABASE")
    logging_config = deepcopy(BASE_LOGGING)

    logging_addition_settings(logging_config)

    assert count_handler_calls(logging_config, "bamboo_engine", "bamboo_engine_context") == 1
    assert count_handler_calls(logging_config, "pipeline_engine", "pipeline_engine_context") == 1
    assert count_handler_calls(logging_config, "pipeline.eri.log", "pipeline_eri") == 1


@pytest.mark.parametrize(
    "logger_name,handler_name",
    [
        ("bamboo_engine", "bamboo_engine_context"),
        ("pipeline_engine", "pipeline_engine_context"),
        ("pipeline.eri.log", "pipeline_eri"),
    ],
)
def test_database_node_log_handlers_are_disabled_for_paas3(monkeypatch, logger_name, handler_name):
    monkeypatch.setattr(env, "NODE_LOG_DATA_SOURCE", "PaaS3")
    logging_config = deepcopy(BASE_LOGGING)

    logging_addition_settings(logging_config)

    assert count_handler_calls(logging_config, logger_name, handler_name) == 0
