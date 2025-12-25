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

    def test_system_constants_to_mako_str(self):
        """Test converting _system. to _system点 in various structures"""
        assert _system_constants_to_mako_str("${_system.username}") == "${_system点username}"
        assert _system_constants_to_mako_str("${normal_var}") == "${normal_var}"
        assert _system_constants_to_mako_str(123) == 123
        assert _system_constants_to_mako_str(True) is True
        assert _system_constants_to_mako_str(None) is None

        # Test dict and list
        value = {"key1": "${_system.username}", "key2": "${normal_var}"}
        result = _system_constants_to_mako_str(value)
        assert result["key1"] == "${_system点username}"
        assert result["key2"] == "${normal_var}"

    def test_mako_str_to_system_constants(self):
        """Test converting _system点 back to _system."""
        assert _mako_str_to_system_constants("${_system点username}") == "${_system.username}"
        assert _mako_str_to_system_constants("${normal_var}") == "${normal_var}"
        assert _mako_str_to_system_constants(123) == 123


class TestAnalysisPipelineConstantsRef:
    """Test pipeline constants reference analysis"""

    def test_analysis_basic_cases(self):
        """Test with empty pipeline and constants only"""
        # Empty pipeline
        result = analysis_pipeline_constants_ref({})
        assert result == {}

        # Constants only
        pipeline_tree = {"constants": {"key1": {"value": "value1"}, "key2": {"value": "value2"}}}
        result = analysis_pipeline_constants_ref(pipeline_tree)
        assert "key1" in result
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

    def test_analysis_with_gateways(self):
        """Test with different gateway types"""
        # ExclusiveGateway
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

        # ConditionalParallelGateway
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

        # ParallelGateway (should be ignored)
        pipeline_tree = {
            "constants": {"const1": {"value": "value1"}},
            "gateways": {"gateway1": {"type": "ParallelGateway"}},
        }
        result = analysis_pipeline_constants_ref(pipeline_tree)
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

    @mock.patch("bkflow.template.utils.ApiGwClient")
    @mock.patch("bkflow.template.utils.SpaceConfig.get_config")
    def test_send_callback(self, mock_get_config, mock_client_class):
        """Test callback with various scenarios"""
        # Skipped cases
        mock_get_config.return_value = None
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})
        mock_get_config.return_value = {"callback_types": ["task_finished"], "url": "http://callback.example.com"}
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})
        mock_get_config.return_value = {"callback_types": ["task_created"], "url": ""}
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})
        mock_client_class.assert_not_called()

        # Success
        mock_get_config.return_value = {"callback_types": ["task_created"], "url": "http://callback.example.com"}
        mock_client = mock.Mock()
        mock_response = mock.Mock()
        mock_response.result = True
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client
        data = {"task_id": "123", "status": "created"}
        send_callback(space_id=1, callback_type="task_created", data=data)
        mock_client.request.assert_called_once()

        # API error
        mock_response.result = False
        mock_response.message = "API Error"
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})

        # Exception handling
        mock_get_config.side_effect = Exception("Database error")
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})

        # Request exception
        mock_get_config.return_value = {"callback_types": ["task_created"], "url": "http://callback.example.com"}
        mock_get_config.side_effect = None
        mock_client.request.side_effect = Exception("Network error")
        send_callback(space_id=1, callback_type="task_created", data={"task_id": "123"})
