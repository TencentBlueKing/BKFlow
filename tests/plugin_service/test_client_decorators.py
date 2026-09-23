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

from plugin_service import env
from plugin_service.client_decorators import (
    check_use_plugin_service,
    data_parser,
    json_response_decoder,
)


class TestDataParser:
    """Test data_parser decorator"""

    def test_data_parser_success_with_trace_id(self):
        """Test data_parser with successful result and trace_id"""

        @data_parser
        def mock_func():
            return {"result": True, "data": {"key": "value"}, "trace_id": "trace123"}

        result, data = mock_func()
        assert result is True
        assert data["key"] == "value"
        assert data["trace_id"] == "trace123"

    def test_data_parser_success_without_trace_id(self):
        """Test data_parser with successful result without trace_id"""

        @data_parser
        def mock_func():
            return {"result": True, "data": {"key": "value"}}

        result, data = mock_func()
        assert result is True
        assert data["key"] == "value"
        assert "trace_id" not in data

    def test_data_parser_success_with_trace_id_non_dict_data(self):
        """Test data_parser with trace_id but data is not dict"""

        @data_parser
        def mock_func():
            return {"result": True, "data": ["item1", "item2"], "trace_id": "trace123"}

        result, data = mock_func()
        assert result is True
        assert data == ["item1", "item2"]
        # trace_id should not be added to non-dict data

    def test_data_parser_failure_with_trace_id(self):
        """Test data_parser with failed result and trace_id"""

        @data_parser
        def mock_func():
            return {"result": False, "message": "Error occurred", "trace_id": "trace456"}

        result, data = mock_func()
        assert result is False
        assert data["message"] == "Error occurred"
        assert data["trace_id"] == "trace456"

    def test_data_parser_failure_without_trace_id(self):
        """Test data_parser with failed result without trace_id"""

        @data_parser
        def mock_func():
            return {"result": False, "message": "Error occurred"}

        result, data = mock_func()
        assert result is False
        assert data["message"] == "Error occurred"
        assert "trace_id" not in data

    def test_data_parser_exception(self):
        """Test data_parser when function raises exception"""

        @data_parser
        def mock_func(arg1, arg2, kwarg1=None):
            raise ValueError("Test exception")

        result, data = mock_func("test1", "test2", kwarg1="test3")
        assert result is False
        assert "mock_func" in data["message"]
        assert "Test exception" in data["message"]


class TestJsonResponseDecoder:
    """Test json_response_decoder decorator"""

    def test_json_response_decoder_success(self):
        """Test json_response_decoder with successful response"""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": True, "data": "success"}

        @json_response_decoder
        def mock_func():
            return mock_response

        result = mock_func()
        assert result["result"] is True
        assert result["data"] == "success"

    def test_json_response_decoder_error_status_code(self):
        """Test json_response_decoder with error status code"""
        with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                mock_response = mock.Mock()
                mock_response.status_code = 500
                mock_response.content = b"Internal Server Error"

                @json_response_decoder
                def mock_func():
                    return mock_response

                result = mock_func()
                assert result["result"] is False
                assert result["data"] is None
                assert "500" in result["message"]

    def test_json_response_decoder_error_with_inject_authorization(self):
        """Test json_response_decoder with error and inject_authorization"""
        with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                mock_response = mock.Mock()
                mock_response.status_code = 403
                mock_response.content = b"Forbidden"

                @json_response_decoder
                def mock_func(inject_authorization=None):
                    return mock_response

                result = mock_func(inject_authorization={"bk_token": "secret_token"})
                assert result["result"] is False
                assert "403" in result["message"]

    def test_json_response_decoder_exception(self):
        """Test json_response_decoder when function raises exception"""

        @json_response_decoder
        def mock_func():
            raise ConnectionError("Network error")

        result = mock_func()
        assert result["result"] is False
        assert result["data"] is None
        assert "Network error" in result["message"]

    def test_json_response_decoder_exception_with_args(self):
        """Test json_response_decoder exception with function arguments"""

        @json_response_decoder
        def mock_func(arg1, kwarg1=None):
            raise RuntimeError("Runtime error occurred")

        result = mock_func("test_arg", kwarg1="test_kwarg")
        assert result["result"] is False
        assert "Runtime error occurred" in result["message"]


class TestCheckUsePluginService:
    """Test check_use_plugin_service decorator"""

    def test_check_use_plugin_service_enabled(self):
        """Test check_use_plugin_service when plugin service is enabled"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):

            @check_use_plugin_service
            def mock_func():
                return {"result": True, "data": "success"}

            result = mock_func()
            assert result["result"] is True
            assert result["data"] == "success"

    def test_check_use_plugin_service_disabled(self):
        """Test check_use_plugin_service when plugin service is disabled"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "0"):

            @check_use_plugin_service
            def mock_func():
                return {"result": True, "data": "success"}

            result = mock_func()
            assert result["result"] is False
            assert "插件服务未启用" in result["message"]
            assert result["data"] is None

    def test_check_use_plugin_service_with_args(self):
        """Test check_use_plugin_service with function arguments"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):

            @check_use_plugin_service
            def mock_func(arg1, arg2, kwarg1=None):
                return {"result": True, "data": f"{arg1}-{arg2}-{kwarg1}"}

            result = mock_func("test1", "test2", kwarg1="test3")
            assert result["result"] is True
            assert result["data"] == "test1-test2-test3"

    def test_check_use_plugin_service_disabled_with_args(self):
        """Test check_use_plugin_service disabled with function arguments"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", ""):

            @check_use_plugin_service
            def mock_func(*args, **kwargs):
                return {"result": True, "data": "should not reach here"}

            result = mock_func("arg1", "arg2", key="value")
            assert result["result"] is False
            assert "插件服务未启用" in result["message"]
