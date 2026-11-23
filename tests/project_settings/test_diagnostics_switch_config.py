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

import itertools
import json
import os
import subprocess
import sys

import pytest

from bkflow.contrib.diagnostics.config import resolve_switches


def load_module_settings(environ):
    """按真实部署方式在子进程加载 module_settings，读取归一后的开关值。"""
    process_env = os.environ.copy()
    process_env.update(
        {
            "DJANGO_SETTINGS_MODULE": "module_settings",
            "BKFLOW_MODULE_TYPE": "engine",
            "BKFLOW_MODULE_CODE": "default",
            "BKFLOW_RESOURCE_ISOLATION_LEVEL": "only_calculation",
            "BKFLOW_DATABASE_NAME": "test",
            "BKFLOW_DATABASE_USER": "test",
            "BKFLOW_DATABASE_HOST": "127.0.0.1",
            "BKFLOW_DATABASE_PORT": "3306",
        }
    )
    for key in list(process_env):
        if key.startswith("BKAPP_DIAGNOSTICS") or key.startswith("BKAPP_PIPELINE_FENCE"):
            process_env.pop(key, None)
    process_env.update(environ)
    script = """
import json
from bamboo_engine.config import Settings as BambooSettings
from django.conf import settings
names = (
    "DIAGNOSTICS_DETECTION_ENABLED", "DIAGNOSTICS_SCANNERS", "PIPELINE_FENCE_MODE",
    "DIAGNOSTICS_RECOVERY_POLICY", "DIAGNOSTICS_MANUAL_APPLY_ENABLED",
    "DIAGNOSTICS_OBSERVABILITY_MODE", "PIPELINE_DIAGNOSTICS_SCAN_ENABLED",
    "PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED", "PIPELINE_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED",
    "PIPELINE_DIAGNOSTICS_CALLBACK_SCAN_ENABLED", "PIPELINE_DIAGNOSTICS_EVENT_ENABLED",
    "PIPELINE_DIAGNOSTICS_ALERT_ENABLED", "PIPELINE_DIAGNOSTICS_APPLY_ENABLED",
    "PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED", "PIPELINE_DIAGNOSTICS_RECOVERY_MODE",
    "DIAGNOSTICS_CLEANUP_ENABLED", "DIAGNOSTICS_RECOVERY_SCOPES",
)
result = {name: getattr(settings, name, None) for name in names}
result["FENCE_EMIT_ENABLED"] = BambooSettings.FENCE_EMIT_ENABLED
result["FENCE_ENFORCE"] = BambooSettings.FENCE_ENFORCE
print(json.dumps(result))
"""
    completed_process = subprocess.run(
        [sys.executable, "-c", script], env=process_env, text=True, capture_output=True, check=False
    )
    assert completed_process.returncode == 0, completed_process.stderr
    return json.loads(completed_process.stdout.splitlines()[-1])


class TestResolveDefaults:
    def test_unset_preserves_all_legacy_defaults(self):
        """未配置统一入口时，所有旧开关保持默认关闭，模式值保持 preview。"""
        result = resolve_switches({})
        for name in (
            "DIAGNOSTICS_SCAN_ENABLED",
            "DIAGNOSTICS_WINDOW_SCAN_ENABLED",
            "DIAGNOSTICS_SIGNATURE_SCAN_ENABLED",
            "DIAGNOSTICS_CALLBACK_SCAN_ENABLED",
            "DIAGNOSTICS_EVENT_ENABLED",
            "DIAGNOSTICS_ALERT_ENABLED",
            "DIAGNOSTICS_APPLY_ENABLED",
            "DIAGNOSTICS_RECOVERY_ENABLED",
            "PIPELINE_FENCE_EMIT_ENABLED",
            "PIPELINE_FENCE_ENFORCE",
        ):
            assert result[name] is False
        assert result["DIAGNOSTICS_RECOVERY_MODE"] == "preview"
        for name in (
            "DIAGNOSTICS_DETECTION_ENABLED",
            "DIAGNOSTICS_SCANNERS",
            "PIPELINE_FENCE_MODE",
            "DIAGNOSTICS_RECOVERY_POLICY",
            "DIAGNOSTICS_OBSERVABILITY_MODE",
        ):
            assert result[name] is None

    def test_legacy_boolean_parsing_is_unchanged(self):
        """旧布尔解析保持 yes/on/true/1 为真、其余为假。"""
        for value in ("1", "TRUE", "yes", "on", " true ", "0", "false", "", "typo"):
            result = resolve_switches({"BKAPP_DIAGNOSTICS_SCAN_ENABLED": value})
            assert result["DIAGNOSTICS_SCAN_ENABLED"] is (value.strip().lower() in ("1", "true", "yes", "on"))

    def test_every_legacy_scan_combination_is_preserved(self):
        """未设置统一入口时四种检测开关各自独立，不折叠取样到窗口。"""
        names = [
            "DIAGNOSTICS_{}_ENABLED".format(name) for name in ("SCAN", "WINDOW_SCAN", "SIGNATURE_SCAN", "CALLBACK_SCAN")
        ]
        for values in itertools.product(("0", "1"), repeat=4):
            result = resolve_switches(dict(zip(["BKAPP_" + name for name in names], values)))
            assert [result[name] for name in names] == [value == "1" for value in values]

    def test_all_legacy_fence_combinations_are_preserved(self):
        """旧 EMIT/ENFORCE 任意组合保持独立。"""
        for emit, enforce in itertools.product(("0", "1"), repeat=2):
            result = resolve_switches(
                {"BKAPP_PIPELINE_FENCE_EMIT_ENABLED": emit, "BKAPP_PIPELINE_FENCE_ENFORCE": enforce}
            )
            assert result["PIPELINE_FENCE_EMIT_ENABLED"] is (emit == "1")
            assert result["PIPELINE_FENCE_ENFORCE"] is (enforce == "1")

    def test_legacy_recovery_mode_is_not_reinterpreted(self):
        """统一入口未设置时不重新解释旧 RECOVERY_ENABLED/MODE 组合。"""
        for enabled, mode in itertools.product((None, "0", "1"), (None, "preview", "apply")):
            environ = {}
            if enabled is not None:
                environ["BKAPP_DIAGNOSTICS_RECOVERY_ENABLED"] = enabled
            if mode is not None:
                environ["BKAPP_DIAGNOSTICS_RECOVERY_MODE"] = mode
            result = resolve_switches(environ)
            assert result["DIAGNOSTICS_RECOVERY_ENABLED"] is (enabled == "1")
            assert result["DIAGNOSTICS_RECOVERY_MODE"] == (mode or "preview")
            assert result["DIAGNOSTICS_RECOVERY_POLICY"] is None


class TestUnifiedDetection:
    def test_detection_on_enables_all_three_scanners_and_retires_sampling(self):
        result = resolve_switches({"BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1"})
        assert result["DIAGNOSTICS_SCAN_ENABLED"] is False
        for name in ("WINDOW_SCAN", "SIGNATURE_SCAN", "CALLBACK_SCAN"):
            assert result["DIAGNOSTICS_{}_ENABLED".format(name)] is True

    def test_detection_off_disables_all_scanners(self):
        result = resolve_switches({"BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "0"})
        for name in ("SCAN", "WINDOW_SCAN", "SIGNATURE_SCAN", "CALLBACK_SCAN"):
            assert result["DIAGNOSTICS_{}_ENABLED".format(name)] is False

    def test_scanner_selection_can_isolate_callback(self):
        result = resolve_switches(
            {"BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1", "BKAPP_DIAGNOSTICS_SCANNERS": " callback "}
        )
        assert result["DIAGNOSTICS_CALLBACK_SCAN_ENABLED"] is True
        for name in ("SCAN", "WINDOW_SCAN", "SIGNATURE_SCAN"):
            assert result["DIAGNOSTICS_{}_ENABLED".format(name)] is False

    def test_empty_scanner_list_disables_all(self):
        result = resolve_switches({"BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1", "BKAPP_DIAGNOSTICS_SCANNERS": ""})
        assert result["DIAGNOSTICS_SCANNERS"] == ()
        for name in ("WINDOW_SCAN", "SIGNATURE_SCAN", "CALLBACK_SCAN"):
            assert result["DIAGNOSTICS_{}_ENABLED".format(name)] is False

    def test_scanner_list_requires_explicit_master(self):
        with pytest.raises(ValueError, match="BKAPP_DIAGNOSTICS_DETECTION_ENABLED"):
            resolve_switches({"BKAPP_DIAGNOSTICS_SCANNERS": "callback"})

    def test_enabled_legacy_scan_alias_is_accepted_with_unified_window(self):
        result = resolve_switches(
            {
                "BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1",
                "BKAPP_DIAGNOSTICS_SCANNERS": "window",
                "BKAPP_DIAGNOSTICS_SCAN_ENABLED": "1",
            }
        )
        assert result["DIAGNOSTICS_WINDOW_SCAN_ENABLED"] is True
        assert result["DIAGNOSTICS_SCAN_ENABLED"] is False

    def test_legacy_scan_alias_conflicts_when_window_excluded(self):
        with pytest.raises(ValueError, match="BKAPP_DIAGNOSTICS_SCAN_ENABLED"):
            resolve_switches(
                {
                    "BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1",
                    "BKAPP_DIAGNOSTICS_SCANNERS": "callback",
                    "BKAPP_DIAGNOSTICS_SCAN_ENABLED": "1",
                }
            )


class TestUnifiedFenceRecoveryApplyObservability:
    @pytest.mark.parametrize(
        "mode,emit,enforce",
        (("off", False, False), ("observe", True, False), ("enforce", True, True)),
    )
    def test_fence_mode_maps_to_engine_flags(self, mode, emit, enforce):
        result = resolve_switches({"BKAPP_PIPELINE_FENCE_MODE": mode})
        assert result["PIPELINE_FENCE_MODE"] == mode
        assert result["PIPELINE_FENCE_EMIT_ENABLED"] is emit
        assert result["PIPELINE_FENCE_ENFORCE"] is enforce

    @pytest.mark.parametrize(
        "policy,enabled,mode",
        (("off", False, "preview"), ("preview", True, "preview"), ("auto", True, "apply")),
    )
    def test_recovery_policy_maps_to_existing_runtime_contract(self, policy, enabled, mode):
        result = resolve_switches({"BKAPP_DIAGNOSTICS_RECOVERY_POLICY": policy})
        assert result["DIAGNOSTICS_RECOVERY_POLICY"] == policy
        assert result["DIAGNOSTICS_RECOVERY_ENABLED"] is enabled
        assert result["DIAGNOSTICS_RECOVERY_MODE"] == mode

    @pytest.mark.parametrize("value,expected", (("0", False), ("1", True), ("TRUE", True), ("off", False)))
    def test_manual_apply_alias_preserves_legacy_boolean_parsing(self, value, expected):
        result = resolve_switches({"BKAPP_DIAGNOSTICS_APPLY_ENABLED": value})
        assert result["DIAGNOSTICS_MANUAL_APPLY_ENABLED"] is expected
        assert result["DIAGNOSTICS_APPLY_ENABLED"] is expected

    @pytest.mark.parametrize(
        "mode,event,alert",
        (("off", False, False), ("alerts", False, True), ("full", True, True)),
    )
    def test_observability_mode_maps_to_event_and_alert(self, mode, event, alert):
        result = resolve_switches({"BKAPP_DIAGNOSTICS_OBSERVABILITY_MODE": mode})
        assert result["DIAGNOSTICS_OBSERVABILITY_MODE"] == mode
        assert result["DIAGNOSTICS_EVENT_ENABLED"] is event
        assert result["DIAGNOSTICS_ALERT_ENABLED"] is alert


class TestConflictAndValidation:
    @pytest.mark.parametrize(
        "new,key,value",
        (
            ({"BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "0"}, "BKAPP_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED", "1"),
            ({"BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1"}, "BKAPP_DIAGNOSTICS_WINDOW_SCAN_ENABLED", "0"),
            ({"BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "0"}, "BKAPP_DIAGNOSTICS_SCAN_ENABLED", "1"),
            ({"BKAPP_PIPELINE_FENCE_MODE": "enforce"}, "BKAPP_PIPELINE_FENCE_EMIT_ENABLED", "0"),
            ({"BKAPP_PIPELINE_FENCE_MODE": "observe"}, "BKAPP_PIPELINE_FENCE_ENFORCE", "1"),
            ({"BKAPP_DIAGNOSTICS_RECOVERY_POLICY": "preview"}, "BKAPP_DIAGNOSTICS_RECOVERY_ENABLED", "0"),
            ({"BKAPP_DIAGNOSTICS_RECOVERY_POLICY": "preview"}, "BKAPP_DIAGNOSTICS_RECOVERY_MODE", "apply"),
            ({"BKAPP_DIAGNOSTICS_RECOVERY_POLICY": "auto"}, "BKAPP_DIAGNOSTICS_RECOVERY_MODE", "preview"),
            ({"BKAPP_DIAGNOSTICS_MANUAL_APPLY_ENABLED": "0"}, "BKAPP_DIAGNOSTICS_APPLY_ENABLED", "1"),
            ({"BKAPP_DIAGNOSTICS_OBSERVABILITY_MODE": "off"}, "BKAPP_DIAGNOSTICS_EVENT_ENABLED", "1"),
        ),
    )
    def test_conflicts_report_the_offending_old_setting(self, new, key, value):
        with pytest.raises(ValueError, match=key):
            resolve_switches(dict(new, **{key: value}))

    @pytest.mark.parametrize(
        "key,values",
        (
            ("BKAPP_DIAGNOSTICS_DETECTION_ENABLED", ("", "maybe", "2")),
            ("BKAPP_PIPELINE_FENCE_MODE", ("", "true", "enforced")),
            ("BKAPP_DIAGNOSTICS_RECOVERY_POLICY", ("", "apply", "automatic")),
            ("BKAPP_DIAGNOSTICS_MANUAL_APPLY_ENABLED", ("", "manual", "2")),
            ("BKAPP_DIAGNOSTICS_OBSERVABILITY_MODE", ("", "1", "events", "ful")),
        ),
    )
    def test_invalid_new_values_fail_instead_of_silent_fallback(self, key, values):
        for value in values:
            with pytest.raises(ValueError, match=key):
                resolve_switches({key: value})

    def test_invalid_scanner_value_fails(self):
        with pytest.raises(ValueError, match="BKAPP_DIAGNOSTICS_SCANNERS"):
            resolve_switches({"BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1", "BKAPP_DIAGNOSTICS_SCANNERS": "calback"})

    def test_new_modes_do_not_enable_unrelated_features(self):
        """检测/门禁/恢复统一入口互不越界开启人工操作、事件告警或数据清理。"""
        result = resolve_switches(
            {
                "BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1",
                "BKAPP_PIPELINE_FENCE_MODE": "enforce",
                "BKAPP_DIAGNOSTICS_RECOVERY_POLICY": "auto",
            }
        )
        assert result["DIAGNOSTICS_APPLY_ENABLED"] is False
        assert result["DIAGNOSTICS_MANUAL_APPLY_ENABLED"] is False
        assert result["DIAGNOSTICS_EVENT_ENABLED"] is False
        assert result["DIAGNOSTICS_ALERT_ENABLED"] is False

    def test_matching_legacy_settings_are_accepted(self):
        environ = {
            "BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1",
            "BKAPP_DIAGNOSTICS_SCAN_ENABLED": "0",
            "BKAPP_DIAGNOSTICS_WINDOW_SCAN_ENABLED": "1",
            "BKAPP_PIPELINE_FENCE_MODE": "observe",
            "BKAPP_PIPELINE_FENCE_EMIT_ENABLED": "1",
            "BKAPP_PIPELINE_FENCE_ENFORCE": "0",
            "BKAPP_DIAGNOSTICS_RECOVERY_POLICY": "auto",
            "BKAPP_DIAGNOSTICS_RECOVERY_ENABLED": "1",
            "BKAPP_DIAGNOSTICS_RECOVERY_MODE": "apply",
        }
        result = resolve_switches(environ)
        assert result["DIAGNOSTICS_RECOVERY_MODE"] == "apply"
        assert result["PIPELINE_FENCE_ENFORCE"] is False

    def test_matching_legacy_value_with_whitespace_is_accepted(self):
        """旧布尔值带空格时按旧规则解析，不应误判为与新入口冲突。"""
        environ = {
            "BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1",
            "BKAPP_DIAGNOSTICS_WINDOW_SCAN_ENABLED": " true ",
            "BKAPP_DIAGNOSTICS_SCAN_ENABLED": "0",
        }
        assert resolve_switches(environ)["DIAGNOSTICS_WINDOW_SCAN_ENABLED"] is True


class TestSettingsWiring:
    def test_unified_controls_reach_django_and_bamboo_settings(self):
        """统一入口通过 env.py -> module_settings 派生到运行时设置与引擎配置。"""
        settings = load_module_settings(
            {
                "BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1",
                "BKAPP_PIPELINE_FENCE_MODE": "enforce",
                "BKAPP_DIAGNOSTICS_RECOVERY_POLICY": "auto",
                "BKAPP_DIAGNOSTICS_OBSERVABILITY_MODE": "full",
                "BKAPP_DIAGNOSTICS_MANUAL_APPLY_ENABLED": "1",
            }
        )
        assert settings["DIAGNOSTICS_DETECTION_ENABLED"] is True
        assert settings["PIPELINE_FENCE_MODE"] == "enforce"
        assert settings["DIAGNOSTICS_RECOVERY_POLICY"] == "auto"
        assert settings["DIAGNOSTICS_OBSERVABILITY_MODE"] == "full"
        assert settings["DIAGNOSTICS_MANUAL_APPLY_ENABLED"] is True
        assert settings["FENCE_EMIT_ENABLED"] is True
        assert settings["FENCE_ENFORCE"] is True
        for name in ("WINDOW_SCAN", "SIGNATURE_SCAN", "CALLBACK_SCAN"):
            assert settings["PIPELINE_DIAGNOSTICS_{}_ENABLED".format(name)] is True
        assert settings["PIPELINE_DIAGNOSTICS_SCAN_ENABLED"] is False
        assert settings["PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED"] is True
        assert settings["PIPELINE_DIAGNOSTICS_RECOVERY_MODE"] == "apply"
        assert settings["PIPELINE_DIAGNOSTICS_EVENT_ENABLED"] is True
        assert settings["PIPELINE_DIAGNOSTICS_ALERT_ENABLED"] is True
        assert settings["PIPELINE_DIAGNOSTICS_APPLY_ENABLED"] is True

    def test_unset_keeps_defaults_and_bkflow_only_settings(self):
        """未配置统一入口时默认值不变，bkflow 独有清理/范围设置保持可用。"""
        settings = load_module_settings(
            {
                "BKAPP_DIAGNOSTICS_CLEANUP_ENABLED": "1",
                "BKAPP_DIAGNOSTICS_RECOVERY_SCOPES": "1, tenant-a:2",
            }
        )
        assert settings["DIAGNOSTICS_DETECTION_ENABLED"] is None
        assert settings["PIPELINE_FENCE_MODE"] is None
        assert settings["PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED"] is False
        assert settings["PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED"] is False
        assert settings["DIAGNOSTICS_CLEANUP_ENABLED"] is True
        assert settings["DIAGNOSTICS_RECOVERY_SCOPES"] == ["1", "tenant-a:2"]

    def test_scanner_selection_and_fence_reach_runtime(self):
        settings = load_module_settings(
            {
                "BKAPP_DIAGNOSTICS_DETECTION_ENABLED": "1",
                "BKAPP_DIAGNOSTICS_SCANNERS": "callback",
                "BKAPP_PIPELINE_FENCE_MODE": "observe",
                "BKAPP_DIAGNOSTICS_RECOVERY_POLICY": "off",
            }
        )
        assert settings["DIAGNOSTICS_SCANNERS"] == ["callback"]
        assert settings["PIPELINE_DIAGNOSTICS_CALLBACK_SCAN_ENABLED"] is True
        assert settings["PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED"] is False
        assert settings["PIPELINE_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED"] is False
        assert settings["FENCE_EMIT_ENABLED"] is True
        assert settings["FENCE_ENFORCE"] is False
        assert settings["PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED"] is False
