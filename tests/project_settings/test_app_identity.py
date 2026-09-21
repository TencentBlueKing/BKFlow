"""验证标准 Smart 包、上云存量身份以及跨模块地址的配置兼容性。"""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def process_environment(module="interface"):
    """只使用仓库测试变量，避免继承开发机的真实服务配置。"""
    environment = {"PATH": os.environ["PATH"], "PYTHONPATH": str(ROOT)}
    for line in (ROOT / "tests" / f"{module}.env").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            key, value = line.split("=", 1)
            environment[key] = value
    environment["DJANGO_SETTINGS_MODULE"] = "module_settings"
    return environment


def load_runtime_settings(module, app_code, overrides=None):
    """在独立进程加载真实配置，不启动 Django 应用或连接外部服务。"""
    environment = process_environment(module)
    environment["BKPAAS_APP_ID"] = app_code
    addresses = [
        {
            "key": {"bk_app_code": app_code, "module_name": name},
            "value": {"prod": f"https://legacy.example.com/{name}/"},
        }
        for name in ("default", "default-engine")
    ]
    environment["BKPAAS_SERVICE_ADDRESSES_BKSAAS"] = base64.b64encode(json.dumps(addresses).encode()).decode()
    environment.update(overrides or {})
    script = """
import json
import config
import env
from django.conf import settings

settings.BKFLOW_MODULE
import config.default as defaults

result = {key: getattr(defaults, key) for key in ["BKAPP_INNER_CALLBACK_ENTRY", "BKAPP_DEFAULT_ENGINE_MODULE_ENTRY"]}
if env.BKFLOW_MODULE_TYPE == "engine":
    keys = ["INTERFACE_APP_URL"]
else:
    keys = ["BK_APIGW_NAME", "BK_APIGW_API_SERVER_HOST", "BK_APIGW_API_SERVER_SUB_PATH"]
result.update({key: getattr(settings, key) for key in keys})
result["APP_CODE"] = config.APP_CODE
assert config.BK_APP_CODE == config.APP_CODE
print(json.dumps(result))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=environment, text=True, capture_output=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.splitlines()[-1])


@pytest.mark.parametrize("app_code", ["bk_flow", "bk_flow_engine", "legacy-bkflow"])
@pytest.mark.parametrize("module", ["interface", "engine"])
def test_runtime_keeps_platform_identity_and_self_discovery(module, app_code):
    """新旧部署均按平台实际身份查找模块，默认网关保留下划线转中划线规则。"""
    settings = load_runtime_settings(module, app_code)
    assert settings["APP_CODE"] == app_code
    assert settings["BKAPP_INNER_CALLBACK_ENTRY"] == "https://legacy.example.com/default/"
    assert settings["BKAPP_DEFAULT_ENGINE_MODULE_ENTRY"] == "https://legacy.example.com/default-engine/"
    if module == "interface":
        assert settings["BK_APIGW_NAME"] == app_code.replace("_", "-")
        assert settings["BK_APIGW_API_SERVER_HOST"] == "legacy.example.com"
        assert settings["BK_APIGW_API_SERVER_SUB_PATH"] == "default/"
    else:
        assert settings["INTERFACE_APP_URL"] == "https://legacy.example.com/default"


@pytest.mark.parametrize("module", ["interface", "engine"])
def test_explicit_legacy_endpoints_override_service_discovery(module):
    """独立网关和拆分部署地址覆盖自动发现，不改变应用的认证身份。"""
    settings = load_runtime_settings(
        module,
        "bk_flow_engine",
        {
            "BK_APIGW_NAME": "legacy-gateway",
            "BKAPP_APIGW_API_HOST": "https://gateway-backend.example.com/bkflow/",
            "BKAPP_INNER_CALLBACK_ENTRY": "https://callback.example.com/flow/",
            "BKAPP_DEFAULT_ENGINE_MODULE_ENTRY": "https://engine.example.com/flow/",
            "INTERFACE_APP_URL": "https://interface.example.com/flow/",
        },
    )
    assert settings["APP_CODE"] == "bk_flow_engine"
    assert settings["BKAPP_INNER_CALLBACK_ENTRY"] == "https://callback.example.com/flow/"
    assert settings["BKAPP_DEFAULT_ENGINE_MODULE_ENTRY"] == "https://engine.example.com/flow/"
    if module == "interface":
        assert settings["BK_APIGW_NAME"] == "legacy-gateway"
        assert settings["BK_APIGW_API_SERVER_HOST"] == "gateway-backend.example.com"
        assert settings["BK_APIGW_API_SERVER_SUB_PATH"] == "bkflow/"
    else:
        assert settings["INTERFACE_APP_URL"] == "https://interface.example.com/flow"


@pytest.mark.parametrize("configured_name", ["", "custom_gateway", "legacy-gateway"])
def test_gateway_configuration_precedence(configured_name):
    """空配置回落平台身份，显式配置保持历史网关命名规则。"""
    settings = load_runtime_settings("interface", "bk_flow_engine", {"BK_APIGW_NAME": configured_name})
    assert settings["BK_APIGW_NAME"] == (configured_name or "bk_flow_engine").replace("_", "-")


@pytest.mark.parametrize("app_code,gateway", [(None, None), ("bk_flow_engine", "legacy-gateway")])
def test_render_smart_description_keeps_application_and_module_references_consistent(tmp_path, app_code, gateway):
    """生成的包同时更新自身服务发现，外部用户服务和仓库源文件保持原值。"""
    source_path = ROOT / "app_desc.yaml"
    source = source_path.read_bytes()
    output = tmp_path / "package" / "app_desc.yaml"
    environment = process_environment()
    if app_code:
        environment["BKFLOW_PACKAGE_APP_CODE"] = app_code
    if gateway:
        environment["BKFLOW_PACKAGE_APIGW_NAME"] = gateway
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_app_desc.py"), "--output", str(output)],
        env=environment,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    description = yaml.safe_load(output.read_text())
    expected_code = app_code or "bk_flow_engine"
    assert description["app"]["bk_app_code"] == expected_code
    assert source_path.read_bytes() == source
    interface = description["modules"]["default"]
    engine = description["modules"]["default-engine"]
    assert interface["svc_discovery"]["bk_saas"] == [
        {"bk_app_code": "bk-user"},
        {"bk_app_code": expected_code},
        {"bk_app_code": expected_code, "module_name": "default-engine"},
    ]
    assert engine["svc_discovery"]["bk_saas"] == [{"bk_app_code": expected_code}]
    gateway_variables = [item["value"] for item in interface["env_variables"] if item["key"] == "BK_APIGW_NAME"]
    assert gateway_variables == ([gateway] if gateway else [])


def test_render_rejects_overwriting_source():
    """打包操作不能改写仓库中的标准应用描述。"""
    source = ROOT / "app_desc.yaml"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_app_desc.py"), "--output", str(source)],
        env=process_environment(),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "输出路径不能覆盖源应用描述" in result.stderr


@pytest.mark.parametrize("key", ["BKFLOW_PACKAGE_APP_CODE", "BKFLOW_PACKAGE_APIGW_NAME"])
def test_render_rejects_invalid_identity_without_creating_output(tmp_path, key):
    """错误的标识配置应在写入制品前失败。"""
    output = tmp_path / "app_desc.yaml"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_app_desc.py"), "--output", str(output)],
        env={**process_environment(), key: "invalid code"},
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert key in result.stderr
    assert not output.exists()
