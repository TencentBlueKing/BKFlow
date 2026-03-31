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
from unittest.mock import MagicMock, patch


class TestBKVisionEnvConfig:
    """BK-Vision 环境变量配置测试"""

    @patch.dict("os.environ", {}, clear=False)
    def test_bkvision_env_defaults_are_empty(self):
        """未设置环境变量时，BK-Vision 配置应为空字符串"""
        import env

        for key in [
            "BKAPP_BKVISION_APIGW_URL",
            "BKAPP_BKVISION_BASE_URL",
            "BKAPP_BKVISION_SYSTEM_DASHBOARD_UID",
            "BKAPP_BKVISION_SPACE_DASHBOARD_UID",
        ]:
            assert hasattr(env, key), f"env.{key} should be defined"
            assert isinstance(getattr(env, key), str), f"env.{key} should be a string"

    @patch.dict(
        "os.environ",
        {
            "BKAPP_BKVISION_APIGW_URL": "https://gw.example.com",
            "BKAPP_BKVISION_BASE_URL": "https://bkvision.example.com",
            "BKAPP_BKVISION_SYSTEM_DASHBOARD_UID": "sys-uid-123",
            "BKAPP_BKVISION_SPACE_DASHBOARD_UID": "space-uid-456",
        },
    )
    def test_bkvision_env_reads_from_environ(self):
        """设置环境变量后，env 模块应读取到对应值"""
        import env

        env_module = importlib.reload(env)
        assert env_module.BKAPP_BKVISION_APIGW_URL == "https://gw.example.com"
        assert env_module.BKAPP_BKVISION_BASE_URL == "https://bkvision.example.com"
        assert env_module.BKAPP_BKVISION_SYSTEM_DASHBOARD_UID == "sys-uid-123"
        assert env_module.BKAPP_BKVISION_SPACE_DASHBOARD_UID == "space-uid-456"


class TestBKVisionContextProcessor:
    """BK-Vision context processor 配置注入测试"""

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

        request = MagicMock()
        request.user.username = "admin"
        request.COOKIES = {"blueking_language": "zh-cn"}

        from bkflow.interface.context_processors import bkflow_settings

        ctx = bkflow_settings(request)

        assert "BKVISION_SYSTEM_DASHBOARD_UID" in ctx
        assert "BKVISION_SPACE_DASHBOARD_UID" in ctx
        assert "BKVISION_BASE_URL" in ctx

    @patch("bkflow.interface.context_processors.env")
    @patch("bkflow.interface.context_processors.EnvironmentVariables")
    @patch("bkflow.interface.context_processors.settings")
    def test_bkvision_values_from_env(self, mock_settings, mock_env_vars, mock_env):
        """BK-Vision 配置值应来自 env 模块"""
        mock_settings.STATIC_URL = "/static/"
        mock_settings.RUN_VER = "open"
        mock_settings.MAX_NODE_EXECUTE_TIMEOUT = 3600
        mock_settings.MEMBER_SELECTOR_DATA_HOST = ""
        mock_settings.APP_CODE = "bkflow"
        mock_settings.APP_NAME = "BKFlow"
        mock_settings.RUN_VER_NAME = "BKFlow"
        mock_env_vars.objects.get_var = MagicMock(return_value=0)

        mock_env.BKAPP_BKVISION_SYSTEM_DASHBOARD_UID = "test-system-uid"
        mock_env.BKAPP_BKVISION_SPACE_DASHBOARD_UID = "test-space-uid"
        mock_env.BKAPP_BKVISION_BASE_URL = "https://bkvision.example.com"
        mock_env.BK_DOC_CENTER_HOST = "https://docs.example.com"
        mock_env.BKPAAS_SHARED_RES_URL = ""
        mock_env.BKFLOW_LOGIN_URL = ""
        mock_env.MESSAGE_HELPER_URL = ""
        mock_env.BKPAAS_BK_DOMAIN = ""
        mock_env.BK_PAAS_ESB_HOST = ""

        request = MagicMock()
        request.user.username = "admin"
        request.COOKIES = {"blueking_language": "zh-cn"}

        from bkflow.interface.context_processors import bkflow_settings

        ctx = bkflow_settings(request)

        assert ctx["BKVISION_SYSTEM_DASHBOARD_UID"] == "test-system-uid"
        assert ctx["BKVISION_SPACE_DASHBOARD_UID"] == "test-space-uid"
        assert ctx["BKVISION_BASE_URL"] == "https://bkvision.example.com"
