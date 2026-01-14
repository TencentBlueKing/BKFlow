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

from unittest import mock

import pytest

from bkflow.exceptions import ValidationError
from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    ApiModel,
    BaseSpaceConfig,
    CallbackHooksConfig,
    CanvasModeConfig,
    FlowVersioning,
    GatewayExpressionConfig,
    SchemaV2Model,
    SpaceConfigHandler,
    SpaceConfigValueType,
    SpaceEngineConfig,
    SpacePluginConfig,
    SuperusersConfig,
    TemplateTriggerConfig,
    TokenAutoRenewalConfig,
    TokenExpirationConfig,
    UniformApiConfig,
    UniformAPIConfigHandler,
)


class TestSpaceConfigHandler:
    def test_get_all_configs(self):
        configs = SpaceConfigHandler.get_all_configs()
        assert len(configs) == 13
        configs = SpaceConfigHandler.get_all_configs(only_public=True)
        assert len(configs) == 12

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

    def test_template_trigger_config(self):
        config_cls = SpaceConfigHandler.get_config("allow_multiple_triggers")
        assert config_cls == TemplateTriggerConfig
        assert config_cls.default_value == "false"
        assert config_cls.value_type == SpaceConfigValueType.TEXT.value
        assert config_cls.choices == ["true", "false"]
        assert config_cls.control is True
        assert config_cls.validate("true")
        assert config_cls.validate("false")
        assert SpaceConfigHandler.validate(name="allow_multiple_triggers", value="true")
        with pytest.raises(ValidationError):
            config_cls.validate("invalid")

    def test_flow_versioning(self):
        config_cls = SpaceConfigHandler.get_config("flow_versioning")
        assert config_cls == FlowVersioning
        assert config_cls.default_value == "false"
        assert config_cls.value_type == SpaceConfigValueType.TEXT.value
        assert config_cls.choices == ["true", "false"]
        assert config_cls.control is True
        assert config_cls.validate("true")
        assert config_cls.validate("false")
        assert SpaceConfigHandler.validate(name="flow_versioning", value="false")
        with pytest.raises(ValidationError):
            config_cls.validate("invalid")

    def test_space_engine_config(self):
        config_cls = SpaceConfigHandler.get_config("engine_space_config")
        assert config_cls == SpaceEngineConfig
        assert config_cls.value_type == SpaceConfigValueType.REF.value
        assert config_cls.is_public is True

        # Valid cases
        valid_config = {
            "space": {"key1": "value1", "key2": 123, "key3": True},
            "scope": {
                "template_1": {"key1": "value1", "key2": 456},
                "template_2": {"key1": "value2", "key2": 789, "key3": False},
            },
        }
        assert config_cls.validate(valid_config)
        assert SpaceConfigHandler.validate(name="engine_space_config", value=valid_config)

        # Valid case - empty space and scope (both are optional)
        assert config_cls.validate({"space": {}})
        assert config_cls.validate({"scope": {}})
        assert config_cls.validate({"space": {}, "scope": {}})

        # Invalid cases - invalid value types
        with pytest.raises(ValidationError):
            config_cls.validate({"space": {"key1": []}, "scope": {}})

        # Invalid cases - additional properties
        with pytest.raises(ValidationError):
            config_cls.validate({"space": {}, "scope": {}, "invalid": "value"})

    def test_get_control_configs(self):
        control_configs = SpaceConfigHandler.get_control_configs()
        assert isinstance(control_configs, dict)
        assert len(control_configs) > 0
        for name, config_cls in control_configs.items():
            assert getattr(config_cls, "control", False) is True

        control_configs_public = SpaceConfigHandler.get_control_configs(only_public=True)
        assert isinstance(control_configs_public, dict)
        for name, config_cls in control_configs_public.items():
            assert getattr(config_cls, "control", False) is True
            assert config_cls.is_public is True

    def test_validate_configs(self):
        configs = {
            "token_expiration": "2h",
            "canvas_mode": "vertical",
            "gateway_expression": "FEEL",
            "superusers": ["user1", "user2"],
        }
        assert SpaceConfigHandler.validate_configs(configs) is True

        invalid_configs = {
            "token_expiration": "2h",
            "canvas_mode": "invalid",
        }
        with pytest.raises(ValidationError):
            SpaceConfigHandler.validate_configs(invalid_configs)

    def test_token_expiration_edge_cases(self):
        config_cls = TokenExpirationConfig
        # Test minimum valid value (1h)
        assert config_cls.validate("1h") is True
        # Test value less than 1h
        with pytest.raises(ValidationError):
            config_cls.validate("30m")
        # Test invalid format
        with pytest.raises(ValidationError):
            config_cls.validate("invalid")
        # Test None value
        with pytest.raises(ValidationError):
            config_cls.validate(None)

    @mock.patch("bkflow.space.configs.check_url_from_apigw")
    def test_callback_hooks_url_validation(self, mock_check_url):
        config_cls = CallbackHooksConfig
        mock_check_url.return_value = True

        # Valid case
        valid_config = {"url": "http://api.apigw.example.com", "callback_types": ["template"]}
        assert config_cls.validate(valid_config) is True

        # Invalid URL - not from apigw
        mock_check_url.return_value = False
        with pytest.raises(ValidationError):
            config_cls.validate({"url": "http://example.com", "callback_types": ["template"]})

        # Invalid callback_types
        mock_check_url.return_value = True
        with pytest.raises(ValidationError):
            config_cls.validate({"url": "http://api.apigw.example.com", "callback_types": ["invalid"]})

        # Missing required fields
        with pytest.raises(ValidationError):
            config_cls.validate({"url": "http://api.apigw.example.com"})

    @mock.patch("bkflow.space.configs.check_url_from_apigw")
    def test_uniform_api_url_validation(self, mock_check_url):
        config_cls = UniformApiConfig
        mock_check_url.return_value = True

        # Valid case
        valid_api = {
            "api": {
                "test_api": {
                    UniformApiConfig.Keys.META_APIS.value: "http://api.apigw.example.com",
                    UniformApiConfig.Keys.API_CATEGORIES.value: "http://api.apigw.example.com",
                    UniformApiConfig.Keys.DISPLAY_NAME.value: "test_api",
                }
            }
        }
        assert config_cls.validate(valid_api) is True

        # Invalid URL - not from apigw
        mock_check_url.return_value = False
        with pytest.raises(ValidationError):
            config_cls.validate(valid_api)

        # Missing required fields
        mock_check_url.return_value = True
        invalid_api = {
            "api": {
                "test_api": {
                    UniformApiConfig.Keys.META_APIS.value: "http://api.apigw.example.com",
                }
            }
        }
        with pytest.raises(ValidationError):
            config_cls.validate(invalid_api)

    def test_api_gateway_credential_dict_validation(self):
        config_cls = ApiGatewayCredentialConfig

        # Valid dict format
        valid_dict = {"default": "default_credential", "template_1": "credential1"}
        assert config_cls.validate(valid_dict) is True

        # Missing default
        with pytest.raises(ValidationError):
            config_cls.validate({"template_1": "credential1"})

        # Invalid pattern
        with pytest.raises(ValidationError):
            config_cls.validate({"default": "credential", "invalid": "value"})

        # Invalid type
        with pytest.raises(ValidationError):
            config_cls.validate(123)

    def test_api_gateway_credential_get_value(self):
        config_cls = ApiGatewayCredentialConfig

        # Mock config object with text_value
        class MockConfigText:
            value_type = SpaceConfigValueType.TEXT.value
            text_value = "default_credential"

        result = config_cls.get_value(MockConfigText())
        assert result == "default_credential"

        # Mock config object with json_value (string)
        class MockConfigJsonString:
            value_type = SpaceConfigValueType.JSON.value
            json_value = "default_credential"

        result = config_cls.get_value(MockConfigJsonString())
        assert result == "default_credential"

        # Mock config object with json_value (dict) - with scope
        class MockConfigJsonDict:
            value_type = SpaceConfigValueType.JSON.value
            json_value = {"default": "default_credential", "template_1": "credential1"}

        result = config_cls.get_value(MockConfigJsonDict(), scope="template_1")
        assert result == "credential1"

        # Mock config object with json_value (dict) - scope not found, return default
        result = config_cls.get_value(MockConfigJsonDict(), scope="template_2")
        assert result == "default_credential"

    def test_base_space_config_to_dict(self):
        config_cls = TokenExpirationConfig
        config_dict = config_cls.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict["name"] == "token_expiration"
        assert config_dict["desc"] is not None
        assert config_dict["is_public"] is True
        assert config_dict["value_type"] == SpaceConfigValueType.TEXT.value
        assert config_dict["default_value"] == "1h"
        assert "choices" in config_dict
        assert "example" in config_dict
        assert "is_mix_type" in config_dict

    def test_base_space_config_get_value(self):
        # Mock config object with TEXT value
        class MockConfigText:
            value_type = SpaceConfigValueType.TEXT.value
            text_value = "test_text"
            json_value = None

        result = BaseSpaceConfig.get_value(MockConfigText())
        assert result == "test_text"

        # Mock config object with JSON value
        class MockConfigJson:
            value_type = SpaceConfigValueType.JSON.value
            text_value = None
            json_value = {"key": "value"}

        result = BaseSpaceConfig.get_value(MockConfigJson())
        assert result == {"key": "value"}

    def test_space_plugin_config_invalid_cases(self):
        config_cls = SpacePluginConfig

        # Missing mode
        with pytest.raises(ValidationError):
            config_cls.validate({"default": {"plugin_codes": ["a"]}})

        # Missing plugin_codes
        with pytest.raises(ValidationError):
            config_cls.validate({"default": {"mode": "allow_list"}})

        # Invalid mode
        with pytest.raises(ValidationError):
            config_cls.validate({"default": {"mode": "invalid", "plugin_codes": ["a"]}})

        # Missing default
        with pytest.raises(ValidationError):
            config_cls.validate({"scope1": {"mode": "allow_list", "plugin_codes": ["a"]}})

    @mock.patch("bkflow.space.configs.check_url_from_apigw")
    def test_uniform_api_config_handler(self, mock_check_url):
        mock_check_url.return_value = True

        # Test V2 schema
        v2_config = {
            "api": {
                "test_api": {
                    "meta_apis": "http://api.apigw.example.com",
                    "api_categories": "http://api.apigw.example.com",
                    "display_name": "Test API",
                }
            }
        }
        handler = UniformAPIConfigHandler(v2_config)
        model = handler.handle()
        assert isinstance(model, SchemaV2Model)
        assert "test_api" in model.api
        assert model.api["test_api"].display_name == "Test API"

        # Test V1 schema (legacy)
        v1_config = {
            "meta_apis": "http://api.apigw.example.com",
            "api_categories": "http://api.apigw.example.com",
        }
        handler = UniformAPIConfigHandler(v1_config)
        model = handler.handle()
        assert isinstance(model, SchemaV2Model)
        assert UniformApiConfig.Keys.DEFAULT_API_KEY.value in model.api
        assert (
            model.api[UniformApiConfig.Keys.DEFAULT_API_KEY.value].display_name
            == UniformApiConfig.Keys.DEFAULT_DISPLAY_NAME.value
        )

        # Test invalid schema
        invalid_config = {"invalid": "value"}
        handler = UniformAPIConfigHandler(invalid_config)
        with pytest.raises(ValidationError):
            handler.handle()

    @mock.patch("bkflow.space.configs.check_url_from_apigw")
    def test_uniform_api_config_with_common(self, mock_check_url):
        mock_check_url.return_value = True
        config_cls = UniformApiConfig
        test_api = {
            "api": {
                "test_api": {
                    UniformApiConfig.Keys.META_APIS.value: "http://api.apigw.example.com",
                    UniformApiConfig.Keys.API_CATEGORIES.value: "http://api.apigw.example.com",
                    UniformApiConfig.Keys.DISPLAY_NAME.value: "test_api",
                }
            },
            "common": {
                "exclude_none_fields": "true",
                "enable_api_parameter_conversion": "false",
            },
        }
        assert config_cls.validate(test_api)

    def test_schema_v2_model_common_access(self):
        config = {
            "api": {
                "test_api": {
                    "meta_apis": "http://api.apigw.example.com",
                    "api_categories": "http://api.apigw.example.com",
                    "display_name": "Test API",
                }
            },
            "common": {
                "exclude_none_fields": "true",
                "enable_api_parameter_conversion": "false",
            },
        }
        model = SchemaV2Model(**config)
        assert model.exclude_none_fields == "true"
        assert model.enable_api_parameter_conversion == "false"
        assert model.common is not None

        # Test without common
        config_no_common = {
            "api": {
                "test_api": {
                    "meta_apis": "http://api.apigw.example.com",
                    "api_categories": "http://api.apigw.example.com",
                    "display_name": "Test API",
                }
            }
        }
        model_no_common = SchemaV2Model(**config_no_common)
        assert model_no_common.common is None
        assert model_no_common.exclude_none_fields is None

        # Test accessing non-existent attribute
        with pytest.raises(AttributeError):
            _ = model_no_common.non_existent_field

    def test_api_model_get_method(self):
        api_model = ApiModel(
            meta_apis="http://api.apigw.example.com",
            api_categories="http://api.apigw.example.com",
            display_name="Test API",
        )
        assert api_model.get("meta_apis") == "http://api.apigw.example.com"
        assert api_model.get("api_categories") == "http://api.apigw.example.com"
        assert api_model.get("display_name") == "Test API"
        assert api_model.get("non_existent", "default") == "default"
