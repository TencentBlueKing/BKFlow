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

from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    BaseSpaceConfig,
    CanvasModeConfig,
    FlowVersioning,
    GatewayExpressionConfig,
    SpacePluginConfig,
    SpaceEngineConfig,
    SuperusersConfig,
    SpaceConfigVerifyNotSupported,
    TemplateTriggerConfig,
    TokenAutoRenewalConfig,
    TokenExpirationConfig,
    UniformApiConfig,
)


class TestBaseSpaceConfigMetadata:
    def test_to_dict_contains_new_metadata_keys(self):
        """to_dict 应包含 group/help/ui/verifiable 四个新键"""
        data = CanvasModeConfig.to_dict()
        for key in ("group", "help", "ui", "verifiable"):
            assert key in data, f"Missing key: {key}"

    def test_base_defaults_are_none_or_false(self):
        """基类默认值：group/help/ui 为 None，verifiable 为 False"""
        assert BaseSpaceConfig.group is None
        assert BaseSpaceConfig.help is None
        assert BaseSpaceConfig.ui is None
        assert BaseSpaceConfig.verifiable is False

    def test_verify_default_raises_not_supported(self):
        """未实现 verify 的配置调用 verify 抛 SpaceConfigVerifyNotSupported"""
        with pytest.raises(SpaceConfigVerifyNotSupported):
            CanvasModeConfig.verify(space_id=1, value="horizontal")


class TestP1ConfigDeclarations:
    def test_switch_configs(self):
        """开关型配置：control=switch，声明 group"""
        for cfg in (TokenAutoRenewalConfig, TemplateTriggerConfig, FlowVersioning):
            data = cfg.to_dict()
            assert data["ui"]["control"] == "switch"
            assert data["group"] in ("access_security", "flow_canvas")

    def test_radio_configs_options_have_desc(self):
        """单选型配置：control=radio，每个选项含 value/label/desc"""
        for cfg in (GatewayExpressionConfig, CanvasModeConfig):
            options = cfg.to_dict()["ui"]["options"]
            assert len(options) == len(cfg.choices)
            for opt in options:
                assert set(("value", "label", "desc")) <= set(opt.keys())
            assert {o["value"] for o in options} == set(cfg.choices)

    def test_token_expiration_is_input(self):
        """token_expiration 应该是 input 类型"""
        data = TokenExpirationConfig.to_dict()
        assert data["ui"]["control"] == "input"

    def test_superusers_is_member_selector(self):
        """superusers 应该是 member_selector 类型"""
        data = SuperusersConfig.to_dict()
        assert data["ui"]["control"] == "member_selector"
        assert data["group"] == "access_security"


class TestComplexConfigDeclarations:
    def test_uniform_api_is_api_plugin_config_and_verifiable(self):
        """uniform_api：control=api_plugin_config，group=api_integration，可验证"""
        data = UniformApiConfig.to_dict()
        assert data["ui"]["control"] == "api_plugin_config"
        assert data["group"] == "api_integration"
        assert data["verifiable"] is True
        assert data["help"]["summary"]

    def test_api_gateway_credential_is_credential_map(self):
        """api_gateway_credential_name：control=credential_map，data_source 指向 BK_APP 凭证"""
        data = ApiGatewayCredentialConfig.to_dict()
        assert data["ui"]["control"] == "credential_map"
        assert data["group"] == "access_security"
        assert data["ui"]["data_source"] == {"type": "credential", "credential_type": "BK_APP"}
        assert data["is_mix_type"] is True

    def test_space_plugin_config_is_plugin_scope(self):
        """space_plugin_config：control=plugin_scope，group=api_integration"""
        data = SpacePluginConfig.to_dict()
        assert data["ui"]["control"] == "plugin_scope"
        assert data["group"] == "api_integration"

    def test_engine_space_config_is_engine_kv(self):
        """engine_space_config：control=engine_kv，group=api_integration"""
        data = SpaceEngineConfig.to_dict()
        assert data["ui"]["control"] == "engine_kv"
        assert data["group"] == "api_integration"
