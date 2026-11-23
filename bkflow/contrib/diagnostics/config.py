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

"""流程卡住治理统一开关。

把若干散落在 ``env.py`` 的旧布尔开关收敛成 5 个统一入口，统一入口未设置时
逐项沿用旧环境变量，保持升级前后行为一致。新旧同时设置但含义冲突时启动时报错，
避免部署时把能力误开或误关。解析只依赖标准库，可在 blueapps/Django 加载前调用。
"""

TRUE_VALUES = ("1", "true", "yes", "on")
FALSE_VALUES = ("0", "false", "no", "off")

# bkflow 当前接入的扫描器：窗口、丢失类型、回调。不含标准运维的补充检测（supplement）。
SCANNERS = ("window", "signature", "callback")
SCAN_FLAGS = {
    "window": "DIAGNOSTICS_WINDOW_SCAN_ENABLED",
    "signature": "DIAGNOSTICS_SIGNATURE_SCAN_ENABLED",
    "callback": "DIAGNOSTICS_CALLBACK_SCAN_ENABLED",
}

BOOL_PREFIX = "BKAPP_"


def _legacy_bool(environ, name):
    """按旧规则解析布尔环境变量，``"0"`` 等不会被当成真值。"""
    return environ.get(BOOL_PREFIX + name, "0").strip().lower() in TRUE_VALUES


def _choice(environ, key, choices):
    """读取并校验模式类入口，非法值直接抛错而不是静默降级。"""
    value = environ[key].strip().lower()
    if value not in choices:
        raise ValueError("{} must be one of: {}".format(key, ", ".join(choices)))
    return value


def _check_legacy(environ, key, expected, control, boolean=True):
    """旧变量与新入口同时存在且含义不一致时报错，并点名冲突的旧变量。"""
    if key not in environ:
        return
    raw = environ[key].strip().lower()
    actual = raw in TRUE_VALUES if boolean else raw
    if actual != expected:
        raise ValueError("{} conflicts with {}; remove the old setting or make it consistent".format(key, control))


def _detection(environ, result):
    """检测总开关 + 扫描范围 -> 三个扫描器开关（含旧取样开关的兼容）。"""
    control = "BKAPP_DIAGNOSTICS_DETECTION_ENABLED"
    selection = "BKAPP_DIAGNOSTICS_SCANNERS"
    result["DIAGNOSTICS_DETECTION_ENABLED"] = None
    result["DIAGNOSTICS_SCANNERS"] = None
    legacy_scan = result["DIAGNOSTICS_SCAN_ENABLED"]
    if control not in environ:
        if selection in environ:
            raise ValueError("{} requires {}".format(selection, control))
        # 未设置统一入口：bkflow 仍保留旧取样扫描路径，四种检测开关完全沿用旧值，
        # 不做 bk-sops 那种「折叠取样到窗口」的迁移，保证升级前后行为一致。
        return
    # 统一入口生效后以窗口扫描替代旧取样扫描，旧 SCAN 开关等价为窗口检测别名。
    result["DIAGNOSTICS_SCAN_ENABLED"] = False
    enabled = _choice(environ, control, TRUE_VALUES + FALSE_VALUES) in TRUE_VALUES
    selected = tuple(
        dict.fromkeys(item.strip() for item in environ.get(selection, ",".join(SCANNERS)).split(",") if item.strip())
    )
    if set(selected) - set(SCANNERS):
        raise ValueError("{} only accepts: {}".format(selection, ", ".join(SCANNERS)))
    result["DIAGNOSTICS_DETECTION_ENABLED"] = enabled
    result["DIAGNOSTICS_SCANNERS"] = selected
    # 旧取样扫描开关开启时，等价于选中窗口扫描；未开启时不否决 WINDOW=1。
    if legacy_scan:
        _check_legacy(environ, "BKAPP_DIAGNOSTICS_SCAN_ENABLED", enabled and "window" in selected, control)
    for scanner, name in SCAN_FLAGS.items():
        value = enabled and scanner in selected
        _check_legacy(environ, "BKAPP_" + name, value, control)
        result[name] = value


def _fence(environ, result):
    """执行保护模式 -> FENCE_EMIT / FENCE_ENFORCE。bkflow 未接入检查点/同步推进开关。"""
    control = "BKAPP_PIPELINE_FENCE_MODE"
    result["PIPELINE_FENCE_MODE"] = None
    if control not in environ:
        return
    mode = _choice(environ, control, ("off", "observe", "enforce"))
    result["PIPELINE_FENCE_MODE"] = mode
    for name, value in (
        ("PIPELINE_FENCE_EMIT_ENABLED", mode != "off"),
        ("PIPELINE_FENCE_ENFORCE", mode == "enforce"),
    ):
        _check_legacy(environ, "BKAPP_" + name, value, control)
        result[name] = value


def _recovery(environ, result):
    """周期恢复策略 -> RECOVERY_ENABLED / RECOVERY_MODE，不重新解释旧 MODE 值。"""
    control = "BKAPP_DIAGNOSTICS_RECOVERY_POLICY"
    result["DIAGNOSTICS_RECOVERY_POLICY"] = None
    if control not in environ:
        return
    policy = _choice(environ, control, ("off", "preview", "auto"))
    enabled, mode = policy != "off", "apply" if policy == "auto" else "preview"
    _check_legacy(environ, "BKAPP_DIAGNOSTICS_RECOVERY_ENABLED", enabled, control)
    _check_legacy(environ, "BKAPP_DIAGNOSTICS_RECOVERY_MODE", mode, control, boolean=False)
    result["DIAGNOSTICS_RECOVERY_POLICY"] = policy
    result["DIAGNOSTICS_RECOVERY_ENABLED"] = enabled
    result["DIAGNOSTICS_RECOVERY_MODE"] = mode


def _manual_apply(environ, result):
    """控制台人工写操作开关，新旧名一致才允许同时存在。"""
    control = "BKAPP_DIAGNOSTICS_MANUAL_APPLY_ENABLED"
    enabled = result["DIAGNOSTICS_APPLY_ENABLED"]
    if control in environ:
        enabled = _choice(environ, control, TRUE_VALUES + FALSE_VALUES) in TRUE_VALUES
        _check_legacy(environ, "BKAPP_DIAGNOSTICS_APPLY_ENABLED", enabled, control)
    result["DIAGNOSTICS_MANUAL_APPLY_ENABLED"] = enabled
    # 运行时与控制台仍消费旧设置名，两者保持同值。
    result["DIAGNOSTICS_APPLY_ENABLED"] = enabled


def _observability(environ, result):
    """事件与告警统一模式 -> EVENT_ENABLED / ALERT_ENABLED。"""
    control = "BKAPP_DIAGNOSTICS_OBSERVABILITY_MODE"
    result["DIAGNOSTICS_OBSERVABILITY_MODE"] = None
    if control not in environ:
        return
    mode = _choice(environ, control, ("off", "alerts", "full"))
    result["DIAGNOSTICS_OBSERVABILITY_MODE"] = mode
    for name, enabled in (("DIAGNOSTICS_EVENT_ENABLED", mode == "full"), ("DIAGNOSTICS_ALERT_ENABLED", mode != "off")):
        _check_legacy(environ, "BKAPP_" + name, enabled, control)
        result[name] = enabled


def resolve_switches(environ):
    """把统一入口与旧环境变量归一为 ``env.py`` 使用的设置值。

    :param environ: 环境变量映射，通常为 ``os.environ``
    :return: 设置名到解析值的字典；未设置的统一入口值为 ``None``
    :raises ValueError: 非法模式值、扫描器列表或新旧配置冲突
    """
    names = (
        "DIAGNOSTICS_SCAN_ENABLED",
        "DIAGNOSTICS_WINDOW_SCAN_ENABLED",
        "DIAGNOSTICS_SIGNATURE_SCAN_ENABLED",
        "DIAGNOSTICS_CALLBACK_SCAN_ENABLED",
        "PIPELINE_FENCE_EMIT_ENABLED",
        "PIPELINE_FENCE_ENFORCE",
        "DIAGNOSTICS_RECOVERY_ENABLED",
        "DIAGNOSTICS_APPLY_ENABLED",
        "DIAGNOSTICS_EVENT_ENABLED",
        "DIAGNOSTICS_ALERT_ENABLED",
    )
    result = {name: _legacy_bool(environ, name) for name in names}
    result["DIAGNOSTICS_RECOVERY_MODE"] = environ.get("BKAPP_DIAGNOSTICS_RECOVERY_MODE", "preview").strip().lower()
    _detection(environ, result)
    _fence(environ, result)
    _recovery(environ, result)
    _manual_apply(environ, result)
    _observability(environ, result)
    return result
