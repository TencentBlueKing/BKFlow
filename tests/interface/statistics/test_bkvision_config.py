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
from pathlib import Path
from unittest.mock import MagicMock, patch

import env as real_env

BKVISION_ENV_KEYS = [
    "BKAPP_BKVISION_APIGW_URL",
    "BKAPP_BKVISION_BASE_URL",
    "BKAPP_BKVISION_SYSTEM_DASHBOARD_UID",
    "BKAPP_BKVISION_SPACE_DASHBOARD_UID",
    "BKAPP_BKVISION_MAIN_JS_SRC_URL",
]


class TestBKVisionEnvConfig:
    """BK-Vision 环境变量配置测试"""

    @patch.dict(
        "os.environ",
        {k: "" for k in BKVISION_ENV_KEYS},
        clear=False,
    )
    def test_bkvision_env_defaults_are_empty(self):
        """未设置环境变量时，BK-Vision 配置应为空字符串"""
        env_module = importlib.reload(real_env)
        for key in BKVISION_ENV_KEYS:
            assert getattr(env_module, key) == "", f"env.{key} should default to empty string"

    @patch.dict(
        "os.environ",
        {
            "BKAPP_BKVISION_APIGW_URL": "https://gw.example.com",
            "BKAPP_BKVISION_BASE_URL": "https://bkvision.example.com",
            "BKAPP_BKVISION_SYSTEM_DASHBOARD_UID": "sys-uid-123",
            "BKAPP_BKVISION_SPACE_DASHBOARD_UID": "space-uid-456",
            "BKAPP_BKVISION_MAIN_JS_SRC_URL": "https://bkvision.example.com/main.js",
        },
    )
    def test_bkvision_env_reads_from_environ(self):
        """设置环境变量后，env 模块应读取到对应值"""
        env_module = importlib.reload(real_env)
        assert env_module.BKAPP_BKVISION_APIGW_URL == "https://gw.example.com"
        assert env_module.BKAPP_BKVISION_BASE_URL == "https://bkvision.example.com"
        assert env_module.BKAPP_BKVISION_SYSTEM_DASHBOARD_UID == "sys-uid-123"
        assert env_module.BKAPP_BKVISION_SPACE_DASHBOARD_UID == "space-uid-456"
        assert env_module.BKAPP_BKVISION_MAIN_JS_SRC_URL == "https://bkvision.example.com/main.js"


def _make_mock_env(**overrides):
    """构造带 spec 约束的 env mock，拼错属性名会 AttributeError"""
    mock = MagicMock(spec=real_env)
    defaults = {
        "BK_DOC_CENTER_HOST": "https://docs.example.com",
        "BKPAAS_SHARED_RES_URL": "",
        "BKFLOW_LOGIN_URL": "",
        "MESSAGE_HELPER_URL": "",
        "BKPAAS_BK_DOMAIN": "",
        "BK_PAAS_ESB_HOST": "",
        "BKAPP_BKVISION_SYSTEM_DASHBOARD_UID": "",
        "BKAPP_BKVISION_SPACE_DASHBOARD_UID": "",
        "BKAPP_BKVISION_BASE_URL": "",
        "BKAPP_BKVISION_MAIN_JS_SRC_URL": "",
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_mock_request():
    request = MagicMock()
    request.user.username = "admin"
    request.COOKIES = {"blueking_language": "zh-cn"}
    return request


class TestBKVisionContextProcessor:
    """BK-Vision context processor 配置注入测试"""

    @patch("bkflow.interface.context_processors.env", _make_mock_env())
    @patch("bkflow.interface.context_processors.EnvironmentVariables")
    @patch("bkflow.interface.context_processors.settings")
    def test_bkvision_keys_in_context(self, mock_settings, mock_env_vars):
        """bkflow_settings 返回的上下文应包含 BK-Vision 配置键"""
        mock_settings.STATIC_URL = "/static/"
        mock_settings.RUN_VER = "open"
        mock_settings.MAX_NODE_EXECUTE_TIMEOUT = 3600
        mock_settings.MEMBER_SELECTOR_DATA_HOST = ""
        mock_settings.APP_CODE = "bkflow"
        mock_settings.APP_NAME = "BKFlow"
        mock_settings.RUN_VER_NAME = "BKFlow"
        mock_env_vars.objects.get_var = MagicMock(return_value=0)

        from bkflow.interface.context_processors import bkflow_settings

        ctx = bkflow_settings(_make_mock_request())

        assert "BKVISION_SYSTEM_DASHBOARD_UID" in ctx
        assert "BKVISION_SPACE_DASHBOARD_UID" in ctx
        assert "BKVISION_BASE_URL" in ctx
        assert "BKVISION_MAIN_JS_SRC_URL" in ctx

    @patch(
        "bkflow.interface.context_processors.env",
        _make_mock_env(
            BKAPP_BKVISION_SYSTEM_DASHBOARD_UID="test-system-uid",
            BKAPP_BKVISION_SPACE_DASHBOARD_UID="test-space-uid",
            BKAPP_BKVISION_BASE_URL="https://bkvision.example.com",
            BKAPP_BKVISION_MAIN_JS_SRC_URL="https://bkvision.example.com/main.js",
        ),
    )
    @patch("bkflow.interface.context_processors.EnvironmentVariables")
    @patch("bkflow.interface.context_processors.settings")
    def test_bkvision_values_from_env(self, mock_settings, mock_env_vars):
        """BK-Vision 配置值应来自 env 模块"""
        mock_settings.STATIC_URL = "/static/"
        mock_settings.RUN_VER = "open"
        mock_settings.MAX_NODE_EXECUTE_TIMEOUT = 3600
        mock_settings.MEMBER_SELECTOR_DATA_HOST = ""
        mock_settings.APP_CODE = "bkflow"
        mock_settings.APP_NAME = "BKFlow"
        mock_settings.RUN_VER_NAME = "BKFlow"
        mock_env_vars.objects.get_var = MagicMock(return_value=0)

        from bkflow.interface.context_processors import bkflow_settings

        ctx = bkflow_settings(_make_mock_request())

        assert ctx["BKVISION_SYSTEM_DASHBOARD_UID"] == "test-system-uid"
        assert ctx["BKVISION_SPACE_DASHBOARD_UID"] == "test-space-uid"
        assert ctx["BKVISION_BASE_URL"] == "https://bkvision.example.com"
        assert ctx["BKVISION_MAIN_JS_SRC_URL"] == "https://bkvision.example.com/main.js"


class TestBKVisionFrontendTemplates:
    """BK-Vision 前端模板变量注入测试"""

    def test_bkvision_main_js_src_url_exists_in_frontend_templates(self):
        """前端模板应暴露 BKVISION_MAIN_JS_SRC_URL 全局变量"""
        for template in ("frontend/index.html", "frontend/index-dev.html"):
            content = Path(template).read_text()
            assert "var BKVISION_MAIN_JS_SRC_URL" in content
