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

from pathlib import Path

import yaml

APP_DESC_PATH = Path(__file__).resolve().parents[2] / "app_desc.yaml"
# 旧版本曾随源码公开的默认值（只记录前缀），部署描述中不得再出现。
PUBLIC_DEFAULT_SECRET_PREFIXES = {"df1da1fc5b13", "a35230d7a282", "jbSH1_3PFsM8"}


def _module_env(app_desc, module_name):
    """返回指定模块展开 YAML 锚点后的环境变量。"""
    return {item["key"]: item.get("value", "") for item in app_desc["modules"][module_name]["env_variables"]}


def test_app_desc_requires_injected_security_values():
    """内部 token、回调密钥和网关主机规则不能使用公开默认值。"""
    content = APP_DESC_PATH.read_text(encoding="utf-8")
    app_desc = yaml.safe_load(content)
    interface_env = _module_env(app_desc, "default")
    engine_env = _module_env(app_desc, "default-engine")

    assert interface_env["APP_INTERNAL_TOKEN"] == ""
    assert interface_env["DEFAULT_ENGINE_APP_INTERNAL_TOKEN"] == ""
    assert interface_env["BKFLOW_DEFAULT_CALLBACK_KEY"] == ""
    assert interface_env["BK_APIGW_NETLOC_PATTERN"] == r"^bkapi\.{hostname}$"
    assert engine_env["APP_INTERNAL_TOKEN"] == ""
    assert engine_env["INTERFACE_APP_INTERNAL_TOKEN"] == ""
    assert engine_env["BKFLOW_DEFAULT_CALLBACK_KEY"] == ""
    assert engine_env["BK_APIGW_NETLOC_PATTERN"] == r"^bkapi\.{hostname}$"
    assert not any(prefix in content for prefix in PUBLIC_DEFAULT_SECRET_PREFIXES)
