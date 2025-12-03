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

import pytest

from bkflow.exceptions import ValidationError
from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    BaseSpaceConfig,
    CallbackHooksConfig,
    CanvasModeConfig,
    GatewayExpressionConfig,
    SpaceConfigHandler,
    SpaceConfigValueType,
    SpacePluginConfig,
    SuperusersConfig,
    TokenAutoRenewalConfig,
    TokenExpirationConfig,
    UniformApiConfig,
)


class TestSpaceConfigHandler:
    def test_get_all_configs(self):
        configs = SpaceConfigHandler.get_all_configs()
        assert len(configs) == 12
        configs = SpaceConfigHandler.get_all_configs(only_public=True)
        assert len(configs) == 11

    def test_get_config(self):
        # valid cases
        valid_names = list(SpaceConfigHandler.get_all_configs().keys())
        for name in valid_names:
            config_cls = SpaceConfigHandler.get_config(name)
            assert issubclass(config_cls, BaseSpaceConfig)

        # invalid cases
        invalid_names = ["an_invalid_name"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                SpaceConfigHandler.get_config(name)

    def test_token_expiration_config(self):
        config_cls = SpaceConfigHandler.get_config("token_expiration")
        assert config_cls == TokenExpirationConfig
        assert config_cls.default_value == "1h"
        assert config_cls.value_type == SpaceConfigValueType.TEXT.value
        assert config_cls.validate("4h")
        assert SpaceConfigHandler.validate(name="token_expiration", value="2d")
        with pytest.raises(ValidationError):
            config_cls.validate("4abc")

    def test_token_auto_renewal(self):
        config_cls = SpaceConfigHandler.get_config("token_auto_renewal")
        assert config_cls == TokenAutoRenewalConfig
        assert config_cls.default_value == "true"
        assert config_cls.value_type == SpaceConfigValueType.TEXT.value

    def test_callback_hooks(self):
        config_cls = SpaceConfigHandler.get_config("callback_hooks")
        assert config_cls == CallbackHooksConfig
        assert config_cls.default_value is None
        assert config_cls.value_type == SpaceConfigValueType.JSON.value
        assert config_cls.is_public is False
        assert config_cls.validate({"url": "example.com", "callback_types": ["template"]})
        assert SpaceConfigHandler.validate(
            name="callback_hooks", value={"url": "example.com", "callback_types": ["template"]}
        )
        with pytest.raises(ValidationError):
            config_cls.validate([{"url": "example.com"}])

    def test_uniform_api(self):
        config_cls = SpaceConfigHandler.get_config("uniform_api")
        assert config_cls == UniformApiConfig
        assert config_cls.default_value == {}
        assert config_cls.value_type == SpaceConfigValueType.JSON.value
        test_api = {
            "api": {
                "test_api": {
                    UniformApiConfig.Keys.META_APIS.value: "example.com",
                    UniformApiConfig.Keys.API_CATEGORIES.value: "example.com",
                    UniformApiConfig.Keys.DISPLAY_NAME.value: "test_api",
                }
            }
        }
        assert config_cls.validate(test_api)
        assert SpaceConfigHandler.validate(name="uniform_api", value=test_api)
        with pytest.raises(ValidationError):
            config_cls.validate({UniformApiConfig.Keys.META_APIS.value: "example.com"})

    def test_superusers(self):
        config_cls = SpaceConfigHandler.get_config("superusers")
        assert config_cls == SuperusersConfig
        assert config_cls.default_value == []
        assert config_cls.value_type == SpaceConfigValueType.JSON.value
        assert config_cls.validate(["a"])
        assert SpaceConfigHandler.validate(name="superusers", value=["a"])
        with pytest.raises(ValidationError):
            config_cls.validate("a")

    def test_canvas_mode(self):
        config_cls = SpaceConfigHandler.get_config("canvas_mode")
        assert config_cls == CanvasModeConfig
        assert config_cls.default_value == "horizontal"
        assert config_cls.value_type == SpaceConfigValueType.TEXT.value
        assert config_cls.validate("horizontal")
        assert config_cls.validate("vertical")
        assert SpaceConfigHandler.validate(name="canvas_mode", value="vertical")
        with pytest.raises(ValidationError):
            config_cls.validate("a")

    def test_gateway_expression(self):
        config_cls = SpaceConfigHandler.get_config("gateway_expression")
        assert config_cls == GatewayExpressionConfig
        assert config_cls.default_value == "boolrule"
        assert config_cls.value_type == SpaceConfigValueType.TEXT.value
        assert config_cls.validate("boolrule")
        assert config_cls.validate("FEEL")
        assert SpaceConfigHandler.validate(name="gateway_expression", value="FEEL")
        with pytest.raises(ValidationError):
            config_cls.validate("a")

    def test_api_gateway_credential_name(self):
        config_cls = SpaceConfigHandler.get_config("api_gateway_credential_name")
        assert config_cls == ApiGatewayCredentialConfig
        assert config_cls.default_value is None
        assert config_cls.value_type == SpaceConfigValueType.TEXT.value

        credential_in_string = "Test credential name"
        credential_in_dict = {"default": "test credential name"}
        assert config_cls.validate(credential_in_string)
        assert config_cls.validate(credential_in_dict)

    def test_space_plugin_config(self):
        config_cls = SpaceConfigHandler.get_config("space_plugin_config")
        assert config_cls == SpacePluginConfig
        assert config_cls.default_value is None
        assert config_cls.value_type == SpaceConfigValueType.JSON.value
        assert config_cls.validate({"default": {"mode": "allow_list", "plugin_codes": ["a"]}})
        assert config_cls.validate({"default": {"mode": "deny_list", "plugin_codes": ["a"]}})
        assert SpaceConfigHandler.validate(
            name="space_plugin_config", value={"default": {"mode": "allow_list", "plugin_codes": ["a"]}}
        )

        with pytest.raises(ValidationError):
            config_cls.validate({"default": {"mode": "allow_list"}})
