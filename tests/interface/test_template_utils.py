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

from bkflow.template.utils import (
    _mako_str_to_system_constants,
    _system_constants_to_mako_str,
    analysis_pipeline_constants_ref,
    send_callback,
)


class TestSystemConstantsConversion:
    """Test system constants conversion functions"""

    def test_system_constants_to_mako_str_with_string(self):
        """Test converting string with _system. to _system点"""
        value = "${_system.username}"
        result = _system_constants_to_mako_str(value)
        assert result == "${_system点username}"

    def test_system_constants_to_mako_str_without_system(self):
        """Test string without _system. remains unchanged"""
        value = "${normal_var}"
        result = _system_constants_to_mako_str(value)
        assert result == "${normal_var}"

    def test_system_constants_to_mako_str_with_dict(self):
        """Test converting dictionary with nested _system references"""
        value = {"key1": "${_system.username}", "key2": "${normal_var}", "nested": {"key3": "${_system.operator}"}}
        result = _system_constants_to_mako_str(value)
        assert result["key1"] == "${_system点username}"
        assert result["key2"] == "${normal_var}"
        assert result["nested"]["key3"] == "${_system点operator}"

    def test_system_constants_to_mako_str_with_list(self):
        """Test converting list with _system references"""
        value = ["${_system.username}", "${normal_var}", "${_system.operator}"]
        result = _system_constants_to_mako_str(value)
        assert result[0] == "${_system点username}"
        assert result[1] == "${normal_var}"
        assert result[2] == "${_system点operator}"

    def test_system_constants_to_mako_str_with_nested_structures(self):
        """Test converting complex nested structures"""
        value = {"list": ["${_system.username}", {"inner": "${_system.operator}"}], "dict": {"key": "${_system.bizid}"}}
        result = _system_constants_to_mako_str(value)
        assert result["list"][0] == "${_system点username}"
        assert result["list"][1]["inner"] == "${_system点operator}"
        assert result["dict"]["key"] == "${_system点bizid}"

    def test_system_constants_to_mako_str_with_non_string(self):
        """Test with non-string types (int, bool, None)"""
        assert _system_constants_to_mako_str(123) == 123
        assert _system_constants_to_mako_str(True) is True
        assert _system_constants_to_mako_str(None) is None

    def test_mako_str_to_system_constants_with_string(self):
        """Test converting string with _system点 back to _system."""
        value = "${_system点username}"
        result = _mako_str_to_system_constants(value)
        assert result == "${_system.username}"

    def test_mako_str_to_system_constants_without_mako(self):
        """Test string without _system点 remains unchanged"""
        value = "${normal_var}"
        result = _mako_str_to_system_constants(value)
        assert result == "${normal_var}"

    def test_mako_str_to_system_constants_with_non_string(self):
        """Test with non-string types"""
        assert _mako_str_to_system_constants(123) == 123
        assert _mako_str_to_system_constants({"key": "value"}) == {"key": "value"}


class TestAnalysisPipelineConstantsRef:
    """Test pipeline constants reference analysis"""

    def test_analysis_empty_pipeline(self):
        """Test with empty pipeline tree"""
        pipeline_tree = {}
        result = analysis_pipeline_constants_ref(pipeline_tree)
        assert result == {}

    def test_analysis_with_constants_only(self):
        """Test with constants but no activities"""
        pipeline_tree = {"constants": {"key1": {"value": "value1"}, "key2": {"value": "value2"}}}
        result = analysis_pipeline_constants_ref(pipeline_tree)
        assert "key1" in result
        assert "key2" in result
        assert result["key1"] == {"activities": [], "conditions": [], "constants": []}

    def test_analysis_with_service_activity(self):
        """Test with ServiceActivity that references constants"""
        pipeline_tree = {
            "constants": {"const1": {"value": "test"}},
            "activities": {
                "act1": {
                    "type": "ServiceActivity",
                    "component": {"data": {"param1": {"value": "${const1}"}, "param2": {"value": "${const2}"}}},
                }
            },
        }
        result = analysis_pipeline_constants_ref(pipeline_tree)
        assert "act1" in result["${const1}"]["activities"]
        assert "act1" in result["${const2}"]["activities"]

    def test_analysis_with_subprocess(self):
        """Test with SubProcess that has constants"""
        pipeline_tree = {
            "constants": {"parent_const": {"value": "parent"}},
            "activities": {
                "subprocess1": {"type": "SubProcess", "constants": {"sub_const": {"value": "${parent_const}"}}}
            },
        }
        result = analysis_pipeline_constants_ref(pipeline_tree)
        assert "subprocess1" in result["${parent_const}"]["activities"]

    def test_analysis_with_exclusive_gateway(self):
        """Test with ExclusiveGateway conditions"""
        pipeline_tree = {
            "constants": {"const1": {"value": "value1"}},
            "gateways": {
                "gateway1": {
                    "type": "ExclusiveGateway",
                    "conditions": {"condition1": {"evaluate": "${const1} == 'test'"}},
                }
            },
        }
        result = analysis_pipeline_constants_ref(pipeline_tree)
        assert "condition1" in result["${const1}"]["conditions"]

    def test_analysis_with_conditional_parallel_gateway(self):
        """Test with ConditionalParallelGateway"""
        pipeline_tree = {
            "constants": {"const1": {"value": "value1"}},
            "gateways": {
                "gateway1": {
                    "type": "ConditionalParallelGateway",
                    "conditions": {"condition1": {"evaluate": "${const1} == 'test'"}},
                }
            },
        }
        result = analysis_pipeline_constants_ref(pipeline_tree)
        assert "condition1" in result["${const1}"]["conditions"]

    def test_analysis_with_parallel_gateway_no_conditions(self):
        """Test with ParallelGateway (should be ignored)"""
        pipeline_tree = {
            "constants": {"const1": {"value": "value1"}},
            "gateways": {"gateway1": {"type": "ParallelGateway"}},
        }
        result = analysis_pipeline_constants_ref(pipeline_tree)
        # ParallelGateway should be skipped
        assert result["const1"]["conditions"] == []

    def test_analysis_with_constant_references_constant(self):
        """Test when a constant references another constant"""
        pipeline_tree = {"constants": {"const1": {"value": "base_value"}, "const2": {"value": "${const1}_extended"}}}
        result = analysis_pipeline_constants_ref(pipeline_tree)
        assert "const2" in result["${const1}"]["constants"]

    def test_analysis_with_system_constants(self):
        """Test with _system constants that get converted"""
        pipeline_tree = {
            "constants": {"const1": {"value": "test"}},
            "activities": {
                "act1": {"type": "ServiceActivity", "component": {"data": {"param1": {"value": "${_system.username}"}}}}
            },
        }
        result = analysis_pipeline_constants_ref(pipeline_tree)
        # _system.username should be tracked
        assert "${_system.username}" in result

    def test_analysis_complex_pipeline(self):
        """Test with a complex pipeline tree"""
        pipeline_tree = {
            "constants": {
                "const1": {"value": "value1"},
                "const2": {"value": "${const1}_modified"},
                "const3": {"value": "value3"},
            },
            "activities": {
                "act1": {
                    "type": "ServiceActivity",
                    "component": {"data": {"param1": {"value": "${const1}"}, "param2": {"value": "${const2}"}}},
                },
                "subprocess1": {"type": "SubProcess", "constants": {"sub_const": {"value": "${const3}"}}},
            },
            "gateways": {
                "gateway1": {
                    "type": "ExclusiveGateway",
                    "conditions": {"condition1": {"evaluate": "${const1} == ${const3}"}},
                }
            },
        }
        result = analysis_pipeline_constants_ref(pipeline_tree)

        # Check const1 references
        assert "act1" in result["${const1}"]["activities"]
        assert "condition1" in result["${const1}"]["conditions"]
        assert "const2" in result["${const1}"]["constants"]

        # Check const2 references
        assert "act1" in result["${const2}"]["activities"]

        # Check const3 references
        assert "subprocess1" in result["${const3}"]["activities"]
        assert "condition1" in result["${const3}"]["conditions"]


class TestSendCallback:
    """Test callback sending functionality"""

    @mock.patch("bkflow.template.utils.SpaceConfig.get_config")
    def test_send_callback_no_hooks_config(self, mock_get_config):
        """Test when no callback hooks are configured"""
        mock_get_config.return_value = None

        # Should not raise exception
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})

        mock_get_config.assert_called_once_with(1, "callback_hooks")

    @mock.patch("bkflow.template.utils.ApiGwClient")
    @mock.patch("bkflow.template.utils.SpaceConfig.get_config")
    def test_send_callback_type_not_enabled(self, mock_get_config, mock_client):
        """Test when callback type is not in enabled list"""
        mock_get_config.return_value = {"callback_types": ["task_finished"], "url": "http://callback.example.com"}

        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})

        # ApiGwClient should not be called
        mock_client.assert_not_called()

    @mock.patch("bkflow.template.utils.ApiGwClient")
    @mock.patch("bkflow.template.utils.SpaceConfig.get_config")
    def test_send_callback_no_url(self, mock_get_config, mock_client):
        """Test when callback URL is not configured"""
        mock_get_config.return_value = {"callback_types": ["task_created"], "url": ""}

        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})

        # ApiGwClient should not be called when URL is empty
        mock_client.assert_not_called()

    @mock.patch("bkflow.template.utils.ApiGwClient")
    @mock.patch("bkflow.template.utils.SpaceConfig.get_config")
    def test_send_callback_success(self, mock_get_config, mock_client_class):
        """Test successful callback"""
        mock_get_config.return_value = {"callback_types": ["task_created"], "url": "http://callback.example.com"}

        mock_client = mock.Mock()
        mock_response = mock.Mock()
        mock_response.result = True
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        data = {"task_id": "123", "status": "created"}
        send_callback(space_id=1, callback_type="task_created", data=data)

        mock_client_class.assert_called_once_with(from_apigw_check=True)
        mock_client.request.assert_called_once_with(
            url="http://callback.example.com", method="POST", data=data, headers=None
        )

    @mock.patch("bkflow.template.utils.ApiGwClient")
    @mock.patch("bkflow.template.utils.SpaceConfig.get_config")
    def test_send_callback_api_error(self, mock_get_config, mock_client_class):
        """Test callback with API error response"""
        mock_get_config.return_value = {"callback_types": ["task_created"], "url": "http://callback.example.com"}

        mock_client = mock.Mock()
        mock_response = mock.Mock()
        mock_response.result = False
        mock_response.message = "API Error"
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Should not raise exception even when API returns error
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})

    @mock.patch("bkflow.template.utils.ApiGwClient")
    @mock.patch("bkflow.template.utils.SpaceConfig.get_config")
    def test_send_callback_exception_handling(self, mock_get_config, mock_client_class):
        """Test exception handling in callback"""
        mock_get_config.side_effect = Exception("Database error")

        # Should not raise exception
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})

    @mock.patch("bkflow.template.utils.ApiGwClient")
    @mock.patch("bkflow.template.utils.SpaceConfig.get_config")
    def test_send_callback_request_exception(self, mock_get_config, mock_client_class):
        """Test when request raises exception"""
        mock_get_config.return_value = {"callback_types": ["task_created"], "url": "http://callback.example.com"}

        mock_client = mock.Mock()
        mock_client.request.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client

        # Should not raise exception
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})
