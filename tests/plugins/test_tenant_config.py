"""部署开关在业务代码和 blueapps 登录策略之间保持一致。"""

import json
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "platform,legacy,expected",
    [(None, "true", True), ("false", "true", False), ("true", "false", True), (None, None, False)],
)
def test_tenant_switch_normalized_before_login(platform, legacy, expected):
    """平台变量优先，历史别名会补为 blueapps 能读取的平台变量。"""
    environment = dict(os.environ)
    for key, value in (("BKPAAS_MULTI_TENANT_MODE", platform), ("ENABLE_MULTI_TENANT_MODE", legacy)):
        environment.pop(key, None)
        if value is not None:
            environment[key] = value
    code = (
        "import env, os, json; "
        "print(json.dumps([env.ENABLE_MULTI_TENANT_MODE, os.environ['BKPAAS_MULTI_TENANT_MODE'].lower() == 'true']))"
    )
    result = subprocess.run([sys.executable, "-c", code], env=environment, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [expected, expected]


@pytest.mark.parametrize(
    "value,expected",
    [(None, ["system"]), ("", ["system"]), (" , ", ["system"]), ("system, a, a,,b ", ["system", "a", "b"])],
)
def test_plugin_sync_tenants_have_no_blank_ids(value, expected):
    """未配置使用 system；显式配置去重并清除空项。"""
    environment = dict(os.environ)
    environment.pop("BK_PLUGIN_SYNC_TENANTS", None)
    if value is not None:
        environment["BK_PLUGIN_SYNC_TENANTS"] = value
    result = subprocess.run(
        [sys.executable, "-c", "import env,json; print(json.dumps(env.BK_PLUGIN_SYNC_TENANTS))"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == expected
