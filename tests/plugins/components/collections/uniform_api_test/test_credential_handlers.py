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

from bkflow.pipeline_plugins.components.collections.uniform_api.credential_handlers import (
    ApiGatewayCredentialNameUserProvidedHandler,
    CredentialKeySpaceConfigHandler,
    CredentialKeyUserProvidedHandler,
    DefaultCredentialHandler,
    SpaceCredentialHandler,
    UniformAPICredentialHandler,
)


class TestUniformAPICredentialHandler:
    """测试凭证处理器基类"""

    def setup_method(self):
        self.logger = MagicMock()
        self.scope_type = "project"
        self.scope_id = "project-1"
        self.parent_data = MagicMock()
        self.space_configs = {}

    def test_get_name(self):
        """测试获取处理器名称"""
        handler = UniformAPICredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler.get_name() == "UniformAPICredentialHandler"

    def test_get_api_gateway_credential_name_string(self):
        """测试从字符串配置中获取 api_gateway_credential_name"""
        handler = UniformAPICredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"api_gateway_credential_name": "test_credential"}
        assert handler._get_api_gateway_credential_name() == "test_credential"

    def test_get_api_gateway_credential_name_dict_with_scope(self):
        """测试从字典配置中根据scope获取 api_gateway_credential_name"""
        handler = UniformAPICredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {
            "api_gateway_credential_name": {
                "project_project-1": "scope_credential",
                "default": "default_credential",
            }
        }
        assert handler._get_api_gateway_credential_name() == "scope_credential"

    def test_get_api_gateway_credential_name_dict_with_default(self):
        """测试从字典配置中使用default获取 api_gateway_credential_name"""
        handler = UniformAPICredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"api_gateway_credential_name": {"default": "default_credential"}}
        assert handler._get_api_gateway_credential_name() == "default_credential"

    def test_get_api_gateway_credential_name_none(self):
        """测试配置不存在时返回None"""
        handler = UniformAPICredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler._get_api_gateway_credential_name() is None

    def test_get_api_gateway_credential_name_no_scope(self):
        """测试没有scope时使用default"""
        handler = UniformAPICredentialHandler(self.logger, None, None, self.parent_data, self.space_configs)
        handler.space_configs = {"api_gateway_credential_name": {"default": "default_credential"}}
        assert handler._get_api_gateway_credential_name() == "default_credential"


class TestCredentialKeyUserProvidedHandler:
    """测试从用户传入的 credentials 中获取 credential_key 对应的凭证"""

    def setup_method(self):
        self.logger = MagicMock()
        self.scope_type = "project"
        self.scope_id = "project-1"
        self.parent_data = MagicMock()
        self.space_configs = {}

    def test_can_handle_with_credential_key_in_credentials(self):
        """测试当 credential_key 在 credentials 中时返回 True"""
        handler = CredentialKeyUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        self.parent_data.inputs = {"credentials": {"test_key": {"bk_app_code": "app", "bk_app_secret": "secret"}}}
        assert handler.can_handle("test_key") is True

    def test_can_handle_without_credential_key(self):
        """测试没有 credential_key 时返回 False"""
        handler = CredentialKeyUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler.can_handle(None) is False

    def test_can_handle_credential_key_not_in_credentials(self):
        """测试 credential_key 不在 credentials 中时返回 False"""
        handler = CredentialKeyUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        self.parent_data.inputs = {"credentials": {}}
        assert handler.can_handle("test_key") is False

    def test_get_credential_success(self):
        """测试成功获取凭证"""
        handler = CredentialKeyUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        self.parent_data.inputs = {
            "credentials": {"test_key": {"bk_app_code": "app_code", "bk_app_secret": "app_secret"}}
        }
        app_code, app_secret = handler.get_credential("test_key")
        assert app_code == "app_code"
        assert app_secret == "app_secret"
        self.logger.info.assert_called_once()

    def test_get_credential_invalid_dict(self):
        """测试凭证不是有效字典时返回 None"""
        handler = CredentialKeyUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        self.parent_data.inputs = {"credentials": {"test_key": "invalid"}}
        app_code, app_secret = handler.get_credential("test_key")
        assert app_code is None
        assert app_secret is None
        self.logger.warning.assert_called_once()


class TestCredentialKeySpaceConfigHandler:
    """测试当 credential_key 匹配空间配置的 api_gateway_credential_name 时，使用空间配置的凭证"""

    def setup_method(self):
        self.logger = MagicMock()
        self.scope_type = "project"
        self.scope_id = "project-1"
        self.parent_data = MagicMock()
        self.space_configs = {}

    def test_can_handle_credential_key_matches(self):
        """测试 credential_key 匹配 api_gateway_credential_name 时返回 True"""
        handler = CredentialKeySpaceConfigHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"api_gateway_credential_name": "test_key"}
        assert handler.can_handle("test_key") is True

    def test_can_handle_credential_key_not_matches(self):
        """测试 credential_key 不匹配时返回 False"""
        handler = CredentialKeySpaceConfigHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"api_gateway_credential_name": "other_key"}
        assert handler.can_handle("test_key") is False

    def test_can_handle_without_credential_key(self):
        """测试没有 credential_key 时返回 False"""
        handler = CredentialKeySpaceConfigHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler.can_handle(None) is False

    def test_get_credential_success(self):
        """测试成功获取空间配置的凭证"""
        handler = CredentialKeySpaceConfigHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {
            "api_gateway_credential_name": "test_key",
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
        app_code, app_secret = handler.get_credential("test_key")
        assert app_code == "space_app"
        assert app_secret == "space_secret"
        self.logger.info.assert_called_once()

    def test_get_credential_no_credential_data(self):
        """测试空间配置中没有 credential 时返回 None"""
        handler = CredentialKeySpaceConfigHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"api_gateway_credential_name": "test_key"}
        app_code, app_secret = handler.get_credential("test_key")
        assert app_code is None
        assert app_secret is None


class TestApiGatewayCredentialNameUserProvidedHandler:
    """测试当没有 credential_key 时，从用户传入的 credentials 中获取 api_gateway_credential_name 对应的凭证"""

    def setup_method(self):
        self.logger = MagicMock()
        self.scope_type = "project"
        self.scope_id = "project-1"
        self.parent_data = MagicMock()
        self.space_configs = {}

    def test_can_handle_without_credential_key_and_match(self):
        """测试没有 credential_key 且 api_gateway_credential_name 在 credentials 中时返回 True"""
        handler = ApiGatewayCredentialNameUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"api_gateway_credential_name": "test_key"}
        self.parent_data.inputs = {"credentials": {"test_key": {"bk_app_code": "app", "bk_app_secret": "secret"}}}
        assert handler.can_handle(None) is True

    def test_can_handle_with_credential_key(self):
        """测试有 credential_key 时返回 False"""
        handler = ApiGatewayCredentialNameUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler.can_handle("test_key") is False

    def test_can_handle_no_api_gateway_credential_name(self):
        """测试没有 api_gateway_credential_name 时返回 False"""
        handler = ApiGatewayCredentialNameUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler.can_handle(None) is False

    def test_get_credential_success(self):
        """测试成功获取凭证"""
        handler = ApiGatewayCredentialNameUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"api_gateway_credential_name": "test_key"}
        self.parent_data.inputs = {
            "credentials": {"test_key": {"bk_app_code": "app_code", "bk_app_secret": "app_secret"}}
        }
        app_code, app_secret = handler.get_credential(None)
        assert app_code == "app_code"
        assert app_secret == "app_secret"
        self.logger.info.assert_called_once()

    def test_get_credential_invalid_dict(self):
        """测试凭证不是有效字典时返回 None"""
        handler = ApiGatewayCredentialNameUserProvidedHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"api_gateway_credential_name": "test_key"}
        self.parent_data.inputs = {"credentials": {"test_key": "invalid"}}
        app_code, app_secret = handler.get_credential(None)
        assert app_code is None
        assert app_secret is None
        self.logger.warning.assert_called_once()


class TestSpaceCredentialHandler:
    """测试从空间配置的 credential 中获取凭证"""

    def setup_method(self):
        self.logger = MagicMock()
        self.scope_type = "project"
        self.scope_id = "project-1"
        self.parent_data = MagicMock()
        self.space_configs = {}

    def test_can_handle_with_credential(self):
        """测试空间配置中有 credential 时返回 True"""
        handler = SpaceCredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"credential": {"bk_app_code": "app", "bk_app_secret": "secret"}}
        assert handler.can_handle() is True

    def test_can_handle_without_credential(self):
        """测试空间配置中没有 credential 时返回 False"""
        handler = SpaceCredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler.can_handle() is False

    def test_get_credential_success(self):
        """测试成功获取空间配置的凭证"""
        handler = SpaceCredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        handler.space_configs = {"credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"}}
        app_code, app_secret = handler.get_credential()
        assert app_code == "space_app"
        assert app_secret == "space_secret"
        self.logger.info.assert_called_once()


class TestDefaultCredentialHandler:
    """测试使用默认凭证（settings）"""

    def setup_method(self):
        self.logger = MagicMock()
        self.scope_type = "project"
        self.scope_id = "project-1"
        self.parent_data = MagicMock()
        self.space_configs = {}

    @patch("bkflow.pipeline_plugins.components.collections.uniform_api.credential_handlers.settings")
    def test_can_handle_with_use_bkflow_credential(self, mock_settings):
        """测试 USE_BKFLOW_CREDENTIAL 为 True 时返回 True"""
        mock_settings.USE_BKFLOW_CREDENTIAL = True
        handler = DefaultCredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler.can_handle() is True

    @patch("bkflow.pipeline_plugins.components.collections.uniform_api.credential_handlers.settings")
    def test_can_handle_without_use_bkflow_credential(self, mock_settings):
        """测试 USE_BKFLOW_CREDENTIAL 为 False 时返回 False"""
        mock_settings.USE_BKFLOW_CREDENTIAL = False
        handler = DefaultCredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        assert handler.can_handle() is False

    @patch("bkflow.pipeline_plugins.components.collections.uniform_api.credential_handlers.settings")
    def test_get_credential_success(self, mock_settings):
        """测试成功获取默认凭证"""
        mock_settings.USE_BKFLOW_CREDENTIAL = True
        mock_settings.APP_CODE = "default_app"
        mock_settings.SECRET_KEY = "default_secret"
        handler = DefaultCredentialHandler(
            self.logger, self.scope_type, self.scope_id, self.parent_data, self.space_configs
        )
        app_code, app_secret = handler.get_credential()
        assert app_code == "default_app"
        assert app_secret == "default_secret"
        self.logger.info.assert_called_once()
