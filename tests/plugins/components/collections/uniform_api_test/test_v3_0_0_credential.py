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
from unittest.mock import MagicMock, patch

from bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0 import (
    UniformAPIService,
)


class TestUniformAPIServiceGetCredential:
    """测试 UniformAPIService 的 _get_credential 方法"""

    def setup_method(self):
        self.service = UniformAPIService()
        self.service.logger = MagicMock()
        self.scope_type = "project"
        self.scope_id = "project-1"
        self.parent_data = MagicMock()
        self.space_configs = {}

    def test_get_credential_with_credential_key_in_user_credentials(self):
        """测试 credential_key 在用户 credentials 中时，优先使用用户凭证"""
        self.parent_data.inputs = {
            "credentials": {
                "custom_credential": {
                    "bk_app_code": "user_app",
                    "bk_app_secret": "user_secret",
                }
            }
        }
        app_code, app_secret = self.service._get_credential(
            self.scope_type, self.scope_id, self.parent_data, self.space_configs, "custom_credential"
        )
        assert app_code == "user_app"
        assert app_secret == "user_secret"

    def test_get_credential_with_credential_key_matching_space_config(self):
        """测试 credential_key 匹配空间配置的 api_gateway_credential_name 时，使用空间配置凭证"""
        self.space_configs = {
            "api_gateway_credential_name": "custom_credential",
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
        app_code, app_secret = self.service._get_credential(
            self.scope_type, self.scope_id, self.parent_data, self.space_configs, "custom_credential"
        )
        assert app_code == "space_app"
        assert app_secret == "space_secret"

    def test_get_credential_without_credential_key_but_api_gateway_name_in_credentials(self):
        """测试没有 credential_key，但 api_gateway_credential_name 在用户 credentials 中"""
        self.space_configs = {
            "api_gateway_credential_name": "default_credential",
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
        self.parent_data.inputs = {
            "credentials": {
                "default_credential": {
                    "bk_app_code": "user_app",
                    "bk_app_secret": "user_secret",
                }
            }
        }
        app_code, app_secret = self.service._get_credential(
            self.scope_type, self.scope_id, self.parent_data, self.space_configs, None
        )
        assert app_code == "user_app"
        assert app_secret == "user_secret"

    def test_get_credential_fallback_to_space_credential(self):
        """测试回退到使用空间配置的 credential"""
        self.space_configs = {
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
        app_code, app_secret = self.service._get_credential(
            self.scope_type, self.scope_id, self.parent_data, self.space_configs, None
        )
        assert app_code == "space_app"
        assert app_secret == "space_secret"

    @patch("bkflow.pipeline_plugins.components.collections.uniform_api.credential_handlers.settings")
    @patch("bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.settings")
    def test_get_credential_fallback_to_default_credential(self, mock_v3_settings, mock_handlers_settings):
        """测试回退到使用默认凭证"""
        mock_handlers_settings.USE_BKFLOW_CREDENTIAL = True
        mock_handlers_settings.APP_CODE = "default_app"
        mock_handlers_settings.SECRET_KEY = "default_secret"
        mock_v3_settings.USE_BKFLOW_CREDENTIAL = True
        mock_v3_settings.APP_CODE = "default_app"
        mock_v3_settings.SECRET_KEY = "default_secret"
        app_code, app_secret = self.service._get_credential(
            self.scope_type, self.scope_id, self.parent_data, self.space_configs, None
        )
        assert app_code == "default_app"
        assert app_secret == "default_secret"

    def test_get_credential_credential_key_not_found(self):
        """测试 credential_key 不存在时返回 None"""
        self.space_configs = {}
        app_code, app_secret = self.service._get_credential(
            self.scope_type, self.scope_id, self.parent_data, self.space_configs, "non_existent_key"
        )
        assert app_code is None
        assert app_secret is None
        # 应该记录警告日志
        assert self.service.logger.warning.called

    def test_get_credential_with_scope_specific_api_gateway_credential_name(self):
        """测试使用 scope 特定的 api_gateway_credential_name"""
        self.space_configs = {
            "api_gateway_credential_name": {
                "project_project-1": "scope_credential",
                "default": "default_credential",
            },
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
        self.parent_data.inputs = {
            "credentials": {
                "scope_credential": {
                    "bk_app_code": "scope_app",
                    "bk_app_secret": "scope_secret",
                }
            }
        }
        app_code, app_secret = self.service._get_credential(
            self.scope_type, self.scope_id, self.parent_data, self.space_configs, None
        )
        assert app_code == "scope_app"
        assert app_secret == "scope_secret"

    def test_get_credential_with_default_api_gateway_credential_name(self):
        """测试使用 default 的 api_gateway_credential_name"""
        self.space_configs = {
            "api_gateway_credential_name": {
                "default": "default_credential",
            },
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
        self.parent_data.inputs = {
            "credentials": {
                "default_credential": {
                    "bk_app_code": "default_app",
                    "bk_app_secret": "default_secret",
                }
            }
        }
        # 使用不存在的 scope
        app_code, app_secret = self.service._get_credential(
            "unknown", "unknown-1", self.parent_data, self.space_configs, None
        )
        assert app_code == "default_app"
        assert app_secret == "default_secret"

    def test_get_credential_handler_exception_handling(self):
        """测试处理器抛出异常时的处理"""
        # 创建一个会抛出异常的 mock
        self.parent_data.inputs = {
            "credentials": {
                "custom_credential": None,  # 这会导致 KeyError 或其他异常
            }
        }
        # 应该能够处理异常并继续尝试下一个处理器
        app_code, app_secret = self.service._get_credential(
            self.scope_type, self.scope_id, self.parent_data, self.space_configs, "custom_credential"
        )
        # 由于异常，应该尝试下一个处理器或返回 None
        # 这里主要测试不会因为异常而崩溃
        assert isinstance(app_code, (str, type(None)))
        assert isinstance(app_secret, (str, type(None)))
