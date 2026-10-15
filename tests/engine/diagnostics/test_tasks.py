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

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.test import override_settings

from bkflow.contrib.diagnostics import tasks
from bkflow.contrib.diagnostics.constants import (
    CALLBACK_SCAN_LOCK,
    CLEANUP_LOCK,
    RECOVERY_LOCK,
    ROOT_SCAN_LOCK,
    SIGNATURE_SCAN_LOCK,
)


@pytest.fixture
def singleflight(mocker):
    """让周期任务直接进入执行分支，并记录锁释放。"""
    acquire = mocker.patch.object(tasks, "_acquire_singleflight", return_value="lock-token")
    release = mocker.patch.object(tasks, "_release_singleflight")
    return acquire, release


@override_settings(
    PIPELINE_DIAGNOSTICS_SCAN_ENABLED=True,
    PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED=True,
)
def test_root_scan_prefers_window_scanner(mocker, singleflight):
    """窗口扫描开启时不再重复执行基础静默扫描。"""
    mock_window = mocker.patch.object(tasks, "scan_silence_windows", return_value=["window-report"])
    mock_basic = mocker.patch.object(tasks, "scan_stalled_roots")

    assert tasks.scan_stuck_diagnostics() == ["window-report"]
    mock_window.assert_called_once_with()
    mock_basic.assert_not_called()
    singleflight[1].assert_called_once_with(ROOT_SCAN_LOCK, "lock-token")


@override_settings(
    PIPELINE_DIAGNOSTICS_SCAN_ENABLED=True,
    PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED=False,
)
def test_root_scan_falls_back_to_basic_scanner(mocker, singleflight):
    """窗口扫描关闭时执行基础静默扫描。"""
    mock_basic = mocker.patch.object(tasks, "scan_stalled_roots", return_value=["case"])

    assert tasks.scan_stuck_diagnostics() == ["case"]
    mock_basic.assert_called_once_with()


@override_settings(
    PIPELINE_DIAGNOSTICS_SCAN_ENABLED=False,
    PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED=False,
)
def test_disabled_root_scan_does_not_touch_lock(mocker):
    """扫描开关全关时不访问 Redis 或数据库。"""
    mock_acquire = mocker.patch.object(tasks, "_acquire_singleflight")
    mock_scan = mocker.patch.object(tasks, "scan_stalled_roots")

    assert tasks.scan_stuck_diagnostics() is None
    mock_acquire.assert_not_called()
    mock_scan.assert_not_called()


@pytest.mark.parametrize(
    "task_name, setting_name, runner_name, lock_name",
    [
        (
            "scan_stuck_signatures",
            "PIPELINE_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED",
            "scan_signatures",
            SIGNATURE_SCAN_LOCK,
        ),
        (
            "scan_stuck_callbacks",
            "PIPELINE_DIAGNOSTICS_CALLBACK_SCAN_ENABLED",
            "scan_callbacks",
            CALLBACK_SCAN_LOCK,
        ),
        (
            "run_stuck_recovery",
            "PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED",
            "run_recovery",
            RECOVERY_LOCK,
        ),
    ],
)
def test_enabled_periodic_task_calls_library_runner(
    mocker,
    singleflight,
    task_name,
    setting_name,
    runner_name,
    lock_name,
):
    """三个周期任务打开后调用 bamboo-pipeline 提供的执行器。"""
    runner = mocker.patch.object(tasks, runner_name, return_value="report")

    with override_settings(**{setting_name: True}):
        assert getattr(tasks, task_name)() == "report"

    runner.assert_called_once_with()
    singleflight[0].assert_called_once()
    singleflight[1].assert_called_once_with(lock_name, "lock-token")


@override_settings(DIAGNOSTICS_CLEANUP_ENABLED=True)
def test_cleanup_task_calls_management_command(mocker, singleflight):
    """清理开关打开后复用依赖包的清理命令。"""
    mock_call_command = mocker.patch.object(tasks, "call_command")

    tasks.cleanup_diagnostics()

    mock_call_command.assert_called_once_with("cleanup_diagnostics")
    singleflight[1].assert_called_once_with(CLEANUP_LOCK, "lock-token")


def test_singleflight_skips_when_lock_is_held(mocker):
    """上一轮未结束时跳过本轮，避免扫描水位并发推进。"""
    runner = MagicMock()
    mocker.patch.object(tasks, "_acquire_singleflight", return_value=None)

    assert tasks._run_singleflight("test", True, runner) is None
    runner.assert_not_called()


@override_settings(
    BKFLOW_MODULE=SimpleNamespace(code="engine-a"),
    redis_inst=MagicMock(),
)
def test_lock_isolated_by_engine_module_and_owned_token():
    """不同 engine 模块使用独立锁，且只能释放自己的锁。"""
    redis_inst = tasks.settings.redis_inst
    redis_inst.set.return_value = True
    redis_inst.get.return_value = b"other-token"

    token = tasks._acquire_singleflight(ROOT_SCAN_LOCK, 60)
    tasks._release_singleflight(ROOT_SCAN_LOCK, token)

    redis_inst.set.assert_called_once_with(
        name="bkflow:engine-a:diagnostics:root_scan",
        value=token,
        nx=True,
        ex=60,
    )
    redis_inst.delete.assert_not_called()
