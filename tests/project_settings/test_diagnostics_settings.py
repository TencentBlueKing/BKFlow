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

import json
import os
import subprocess
import sys

DIAGNOSTICS_SCHEDULES = {
    "scan_stuck_diagnostics": "bkflow.contrib.diagnostics.tasks.scan_stuck_diagnostics",
    "scan_stuck_signatures": "bkflow.contrib.diagnostics.tasks.scan_stuck_signatures",
    "scan_stuck_callbacks": "bkflow.contrib.diagnostics.tasks.scan_stuck_callbacks",
    "run_stuck_recovery": "bkflow.contrib.diagnostics.tasks.run_stuck_recovery",
    "cleanup_diagnostics": "bkflow.contrib.diagnostics.tasks.cleanup_diagnostics",
}


def _load_module_settings(module_type, extra_env=None):
    process_env = os.environ.copy()
    process_env.update(
        {
            "DJANGO_SETTINGS_MODULE": "module_settings",
            "BKFLOW_MODULE_TYPE": module_type,
            "BKFLOW_MODULE_CODE": "default",
            "BKFLOW_RESOURCE_ISOLATION_LEVEL": "only_calculation",
            "BKFLOW_DATABASE_NAME": "test",
            "BKFLOW_DATABASE_USER": "test",
            "BKFLOW_DATABASE_HOST": "127.0.0.1",
            "BKFLOW_DATABASE_PORT": "3306",
        }
    )
    process_env.update(extra_env or {})
    script = """
import json
from bamboo_engine.config import Settings as BambooSettings
from blueapps.core.celery.celery import app
from django.conf import settings

schedule_names = {
    "scan_stuck_diagnostics",
    "scan_stuck_signatures",
    "scan_stuck_callbacks",
    "run_stuck_recovery",
    "cleanup_diagnostics",
}
task_paths = {
    "bkflow.contrib.diagnostics.tasks.scan_stuck_diagnostics",
    "bkflow.contrib.diagnostics.tasks.scan_stuck_signatures",
    "bkflow.contrib.diagnostics.tasks.scan_stuck_callbacks",
    "bkflow.contrib.diagnostics.tasks.run_stuck_recovery",
    "bkflow.contrib.diagnostics.tasks.cleanup_diagnostics",
}
print(json.dumps({
    "pipeline_app": "pipeline.contrib.diagnostics" in settings.INSTALLED_APPS,
    "bkflow_app": "bkflow.contrib.diagnostics" in settings.INSTALLED_APPS,
    "schedules": {
        name: app.conf.beat_schedule[name]["task"]
        for name in schedule_names
        if name in app.conf.beat_schedule
    },
    "routes": {
        task_path: settings.CELERY_ROUTES[task_path]
        for task_path in task_paths
        if task_path in getattr(settings, "CELERY_ROUTES", {})
    },
    "event_enabled": getattr(settings, "PIPELINE_DIAGNOSTICS_EVENT_ENABLED", None),
    "scan_enabled": getattr(settings, "PIPELINE_DIAGNOSTICS_SCAN_ENABLED", None),
    "window_enabled": getattr(settings, "PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED", None),
    "signature_enabled": getattr(settings, "PIPELINE_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED", None),
    "callback_enabled": getattr(settings, "PIPELINE_DIAGNOSTICS_CALLBACK_SCAN_ENABLED", None),
    "recovery_enabled": getattr(settings, "PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED", None),
    "apply_enabled": getattr(settings, "PIPELINE_DIAGNOSTICS_APPLY_ENABLED", None),
    "cleanup_enabled": getattr(settings, "DIAGNOSTICS_CLEANUP_ENABLED", None),
    "fence_emit": getattr(BambooSettings, "FENCE_EMIT_ENABLED", False),
    "fence_enforce": getattr(BambooSettings, "FENCE_ENFORCE", False),
    "window_tiers": getattr(settings, "PIPELINE_DIAGNOSTICS_WINDOW_TIERS", None),
    "poll_excludes": getattr(settings, "PIPELINE_DIAGNOSTICS_POLL_EXCLUDE_CODES", None),
    "recovery_mode": getattr(settings, "PIPELINE_DIAGNOSTICS_RECOVERY_MODE", None),
    "auto_replay_types": getattr(settings, "PIPELINE_DIAGNOSTICS_AUTO_REPLAY_TYPES", None),
    "recovery_scopes": getattr(settings, "DIAGNOSTICS_RECOVERY_SCOPES", None),
    "scope_resolver": getattr(settings, "PIPELINE_DIAGNOSTICS_RECOVERY_SCOPE_RESOLVER", None),
}))
"""
    completed_process = subprocess.run(
        [sys.executable, "-c", script],
        env=process_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed_process.returncode == 0, completed_process.stderr
    return json.loads(completed_process.stdout.splitlines()[-1])


def test_engine_registers_diagnostics_with_safe_defaults():
    """engine 模块注册诊断能力和周期任务，但所有执行开关默认关闭。"""
    result = _load_module_settings("engine")

    assert result["pipeline_app"] is True
    assert result["bkflow_app"] is True
    assert result["schedules"] == DIAGNOSTICS_SCHEDULES
    assert result["routes"] == {
        task_path: {
            "queue": "clean_task_default",
            "routing_key": "clean_task_default",
        }
        for task_path in DIAGNOSTICS_SCHEDULES.values()
    }
    assert result["scope_resolver"] == "bkflow.contrib.diagnostics.recovery_scope.in_recovery_scope"
    assert all(
        result[name] is False
        for name in [
            "event_enabled",
            "scan_enabled",
            "window_enabled",
            "signature_enabled",
            "callback_enabled",
            "recovery_enabled",
            "apply_enabled",
            "cleanup_enabled",
            "fence_emit",
            "fence_enforce",
        ]
    )


def test_engine_loads_diagnostics_environment_values():
    """诊断开关、列表及恢复范围应从部署环境正确解析。"""
    result = _load_module_settings(
        "engine",
        {
            "BKAPP_DIAGNOSTICS_EVENT_ENABLED": "yes",
            "BKAPP_DIAGNOSTICS_SCAN_ENABLED": "1",
            "BKAPP_DIAGNOSTICS_WINDOW_SCAN_ENABLED": "true",
            "BKAPP_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED": "on",
            "BKAPP_DIAGNOSTICS_CALLBACK_SCAN_ENABLED": "TRUE",
            "BKAPP_DIAGNOSTICS_RECOVERY_ENABLED": "1",
            "BKAPP_DIAGNOSTICS_APPLY_ENABLED": "1",
            "BKAPP_DIAGNOSTICS_CLEANUP_ENABLED": "1",
            "BKAPP_PIPELINE_FENCE_EMIT_ENABLED": "1",
            "BKAPP_PIPELINE_FENCE_ENFORCE": "true",
            "BKAPP_DIAGNOSTICS_WINDOW_TIERS": "60, 120",
            "BKAPP_DIAGNOSTICS_POLL_EXCLUDE_CODES": "sleep_timer, long_poll",
            "BKAPP_DIAGNOSTICS_RECOVERY_MODE": "apply",
            "BKAPP_DIAGNOSTICS_AUTO_REPLAY_TYPES": "execute_dispatch_lost, poll_dispatch_lost",
            "BKAPP_DIAGNOSTICS_RECOVERY_SCOPES": "1, tenant-a:2",
        },
    )

    assert all(
        result[name] is True
        for name in [
            "event_enabled",
            "scan_enabled",
            "window_enabled",
            "signature_enabled",
            "callback_enabled",
            "recovery_enabled",
            "apply_enabled",
            "cleanup_enabled",
            "fence_emit",
            "fence_enforce",
        ]
    )
    assert result["window_tiers"] == [60, 120]
    assert result["poll_excludes"] == ["sleep_timer", "long_poll"]
    assert result["recovery_mode"] == "apply"
    assert result["auto_replay_types"] == ["execute_dispatch_lost", "poll_dispatch_lost"]
    assert result["recovery_scopes"] == ["1", "tenant-a:2"]


def test_interface_module_does_not_register_engine_diagnostics():
    """interface 模块不加载诊断数据表和周期任务。"""
    result = _load_module_settings("interface")

    assert result["pipeline_app"] is False
    assert result["bkflow_app"] is False
    assert result["schedules"] == {}
    assert result["routes"] == {}
