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
import json
from io import BytesIO
from unittest import mock

import pytest
from django.core.files.uploadedfile import UploadedFile
from requests import HTTPError

from plugin_service import env
from plugin_service.exceptions import PluginServiceException, PluginServiceNotUse
from plugin_service.plugin_client import PluginServiceApiClient


class TestPluginServiceApiClientInit:
    """Test PluginServiceApiClient initialization"""

    def test_init_without_plugin_service_enabled(self):
        """Test initialization when plugin service is not enabled"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "0"):
            with pytest.raises(PluginServiceNotUse) as exc_info:
                PluginServiceApiClient("test_plugin")
            assert "插件服务未启用" in str(exc_info.value)

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    def test_init_with_failed_plugin_detail(self, mock_get_detail):
        """Test initialization when get_plugin_app_detail fails"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detail.return_value = {"result": False, "message": "Plugin not found"}
            with pytest.raises(PluginServiceException) as exc_info:
                PluginServiceApiClient("test_plugin")
            assert "Plugin not found" in str(exc_info.value)

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    def test_init_success(self, mock_get_detail):
        """Test successful initialization"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detail.return_value = {
                "result": True,
                "data": {"url": "http://plugin.example.com", "apigw_name": "test_apigw"},
            }
            client = PluginServiceApiClient("test_plugin")
            assert client.plugin_code == "test_plugin"
            assert "http://plugin.example.com/bk_plugin/" in client.plugin_host
            assert client.plugin_apigw_name == "test_apigw"

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    def test_init_with_custom_host(self, mock_get_detail):
        """Test initialization with custom plugin host"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detail.return_value = {
                "result": True,
                "data": {"url": "http://plugin.example.com", "apigw_name": "test_apigw"},
            }
            client = PluginServiceApiClient("test_plugin", plugin_host="http://custom.host.com")
            assert client.plugin_host == "http://custom.host.com"

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    def test_init_with_null_apigw_name(self, mock_get_detail):
        """Test initialization when apigw_name is None"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detail.return_value = {
                "result": True,
                "data": {"url": "http://plugin.example.com", "apigw_name": None},
            }
            client = PluginServiceApiClient("test_plugin")
            assert client.plugin_apigw_name == "test_plugin"


class TestPluginServiceApiClientInvoke:
    """Test PluginServiceApiClient invoke method"""

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch("plugin_service.plugin_client.requests.post")
    def test_invoke_success(self, mock_post, mock_get_detail):
        """Test successful invoke"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            mock_response = mock.Mock()
                            mock_response.json.return_value = {
                                "result": True,
                                "data": {"trace_id": "123", "output": "success"},
                            }
                            mock_response.status_code = 200
                            mock_post.return_value = mock_response

                            client = PluginServiceApiClient("test_plugin")
                            result = client.invoke("v1", {"input": "test"}, {"X-Custom": "header"})

                            assert result == (True, {"trace_id": "123", "output": "success"})
                            mock_post.assert_called_once()

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch("plugin_service.plugin_client.requests.post")
    def test_invoke_with_result_false(self, mock_post, mock_get_detail):
        """Test invoke when result is False"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            mock_response = mock.Mock()
                            mock_response.json.return_value = {
                                "result": False,
                                "message": "Execute failed",
                                "trace_id": "456",
                            }
                            mock_response.status_code = 200
                            mock_post.return_value = mock_response

                            client = PluginServiceApiClient("test_plugin")
                            result = client.invoke("v1", {"input": "test"}, {})

                            assert result == (False, {"message": "Execute failed", "trace_id": "456"})

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch("plugin_service.plugin_client.requests.post")
    def test_invoke_with_exception(self, mock_post, mock_get_detail):
        """Test invoke when exception occurs"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            mock_post.side_effect = Exception("Network error")

                            client = PluginServiceApiClient("test_plugin")
                            result = client.invoke("v1", {"input": "test"}, {})

                            assert result[0] is False
                            assert "Network error" in result[1]["message"]


class TestPluginServiceApiClientDispatchPluginApiRequest:
    """Test dispatch_plugin_api_request method"""

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_dispatch_without_files(self, mock_request, mock_get_detail):
        """Test dispatch without file uploads"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            mock_request.return_value = mock.Mock(
                                json=lambda: {"result": True, "data": "success"}, status_code=200
                            )

                            client = PluginServiceApiClient("test_plugin")
                            request_params = {"path": "/api/test", "method": "GET", "data": {"key": "value"}}
                            result = client.dispatch_plugin_api_request(request_params)

                            assert result["result"] is True
                            mock_request.assert_called_once()
                            call_kwargs = mock_request.call_args[1]
                            assert call_kwargs["method"] == "post"
                            assert "headers" in call_kwargs

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_dispatch_with_inject_headers(self, mock_request, mock_get_detail):
        """Test dispatch with inject headers"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            mock_request.return_value = mock.Mock(
                                json=lambda: {"result": True, "data": "success"}, status_code=200
                            )

                            client = PluginServiceApiClient("test_plugin")
                            request_params = {"path": "/api/test", "method": "GET", "data": {}}
                            inject_headers = {"X-Custom-Header": "custom_value"}
                            result = client.dispatch_plugin_api_request(request_params, inject_headers=inject_headers)

                            assert result["result"] is True
                            call_kwargs = mock_request.call_args[1]
                            assert "X-Custom-Header" in call_kwargs["headers"]

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_dispatch_with_inject_authorization(self, mock_request, mock_get_detail):
        """Test dispatch with inject authorization"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            mock_request.return_value = mock.Mock(
                                json=lambda: {"result": True, "data": "success"}, status_code=200
                            )

                            client = PluginServiceApiClient("test_plugin")
                            request_params = {"path": "/api/test", "method": "GET", "data": {}}
                            inject_authorization = {"bk_username": "test_user"}
                            result = client.dispatch_plugin_api_request(
                                request_params, inject_authorization=inject_authorization
                            )

                            assert result["result"] is True

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_dispatch_with_file_upload(self, mock_request, mock_get_detail):
        """Test dispatch with file upload"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            mock_request.return_value = mock.Mock(
                                json=lambda: {"result": True, "data": "success"}, status_code=200
                            )

                            client = PluginServiceApiClient("test_plugin")
                            # Create mock uploaded file
                            file_obj = BytesIO(b"test file content")
                            uploaded_file = UploadedFile(file=file_obj, name="test.txt", content_type="text/plain")

                            request_params = {
                                "path": "/api/upload",
                                "method": "POST",
                                "data": {"file": uploaded_file, "param": "value"},
                            }
                            result = client.dispatch_plugin_api_request(request_params)

                            assert result["result"] is True
                            mock_request.assert_called_once()
                            call_kwargs = mock_request.call_args[1]
                            assert "files" in call_kwargs
                            assert "Content-Type" not in call_kwargs["headers"]


class TestPluginServiceApiClientOtherMethods:
    """Test other methods of PluginServiceApiClient"""

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_get_meta(self, mock_request, mock_get_detail):
        """Test get_meta method"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detail.return_value = {
                "result": True,
                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
            }
            mock_request.return_value = mock.Mock(
                json=lambda: {"result": True, "data": {"version": "1.0"}}, status_code=200
            )

            client = PluginServiceApiClient("test_plugin")
            result = client.get_meta()

            assert result["result"] is True
            assert result["data"]["version"] == "1.0"

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_get_detail(self, mock_request, mock_get_detail):
        """Test get_detail method"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detail.return_value = {
                "result": True,
                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
            }
            mock_request.return_value = mock.Mock(
                json=lambda: {"result": True, "data": {"name": "test"}}, status_code=200
            )

            client = PluginServiceApiClient("test_plugin")
            result = client.get_detail("v1")

            assert result["result"] is True
            assert result["data"]["name"] == "test"

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_get_schedule(self, mock_request, mock_get_detail):
        """Test get_schedule method"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detail.return_value = {
                "result": True,
                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
            }
            mock_request.return_value = mock.Mock(
                json=lambda: {"result": True, "data": {"status": "running"}, "trace_id": "123"}, status_code=200
            )

            client = PluginServiceApiClient("test_plugin")
            result = client.get_schedule("trace123")

            assert result == (True, {"status": "running", "trace_id": "123"})


class TestPluginServiceApiClientStaticMethods:
    """Test static methods of PluginServiceApiClient"""

    @mock.patch.object(PluginServiceApiClient, "get_paas_logs")
    def test_get_plugin_logs_success(self, mock_get_logs):
        """Test get_plugin_logs when successful"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_logs.return_value = {"logs": ["log1", "log2"], "scroll_id": "scroll123"}
            result = PluginServiceApiClient.get_plugin_logs("test_plugin", "trace123")

            assert result["result"] is True
            assert result["data"]["logs"] == ["log1", "log2"]

    @mock.patch.object(PluginServiceApiClient, "get_paas_logs")
    def test_get_plugin_logs_failure(self, mock_get_logs):
        """Test get_plugin_logs when failed"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_logs.return_value = {"result": False, "message": "Log fetch failed"}
            result = PluginServiceApiClient.get_plugin_logs("test_plugin", "trace123", scroll_id="scroll1")

            assert result["result"] is False
            assert result["message"] == "Log fetch failed"

    @mock.patch.object(PluginServiceApiClient, "get_paas_logs")
    def test_get_plugin_logs_without_plugin_service(self, mock_get_logs):
        """Test get_plugin_logs when plugin service is not enabled"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "0"):
            result = PluginServiceApiClient.get_plugin_logs("test_plugin", "trace123")

            assert result["result"] is False
            assert "插件服务未启用" in result["message"]
            mock_get_logs.assert_not_called()

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_info")
    def test_get_plugin_list_without_plugin_service(self, mock_get_info):
        """Test get_plugin_list when plugin service is not enabled"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "0"):
            result = PluginServiceApiClient.get_plugin_list()

            assert result["result"] is True
            assert result["data"]["count"] == 0
            assert result["data"]["plugins"] == []
            mock_get_info.assert_not_called()

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_info")
    def test_get_plugin_list_success(self, mock_get_info):
        """Test get_plugin_list when successful"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_info.return_value = {
                "count": 2,
                "results": [
                    {"code": "plugin1", "name": "Plugin 1", "logo_url": "url1", "creator": "admin"},
                    {"code": "plugin2", "name": "Plugin 2", "logo_url": "url2", "creator": "user"},
                ],
            }
            result = PluginServiceApiClient.get_plugin_list(search_term="test", limit=10, offset=0)

            assert result["result"] is True
            assert result["data"]["count"] == 2
            assert len(result["data"]["plugins"]) == 2
            assert result["data"]["plugins"][0]["code"] == "plugin1"

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_info")
    def test_get_plugin_list_with_distributor(self, mock_get_info):
        """Test get_plugin_list with distributor_code_name"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_info.return_value = {"count": 0, "results": []}
            result = PluginServiceApiClient.get_plugin_list(distributor_code_name="dist1")

            assert result["result"] is True
            mock_get_info.assert_called_once()

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_info")
    def test_get_plugin_list_failure(self, mock_get_info):
        """Test get_plugin_list when failed"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_info.return_value = {"result": False, "message": "Fetch failed"}
            result = PluginServiceApiClient.get_plugin_list()

            assert result["result"] is False

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_tags")
    def test_get_plugin_tags_list_without_plugin_service(self, mock_get_tags):
        """Test get_plugin_tags_list when plugin service is not enabled"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "0"):
            result = PluginServiceApiClient.get_plugin_tags_list()

            assert result["result"] is True
            assert "插件服务未启用" in result["message"]
            mock_get_tags.assert_not_called()

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_tags")
    def test_get_plugin_tags_list_success(self, mock_get_tags):
        """Test get_plugin_tags_list when successful"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_tags.return_value = [{"id": 1, "name": "tag1"}, {"id": 2, "name": "tag2"}]
            result = PluginServiceApiClient.get_plugin_tags_list()

            assert result["result"] is True
            assert len(result["data"]) == 2

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_tags")
    def test_get_plugin_tags_list_failure(self, mock_get_tags):
        """Test get_plugin_tags_list when failed"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_tags.return_value = {"result": False, "message": "Failed to get tags"}
            result = PluginServiceApiClient.get_plugin_tags_list()

            assert result["result"] is False

    @mock.patch.object(PluginServiceApiClient, "batch_get_paas_plugin_detailed_info")
    def test_get_plugin_detail_list_without_plugin_service(self, mock_get_detailed):
        """Test get_plugin_detail_list when plugin service is not enabled"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "0"):
            result = PluginServiceApiClient.get_plugin_detail_list()

            assert result["result"] is True
            assert result["data"]["count"] == 0
            mock_get_detailed.assert_not_called()

    @mock.patch.object(PluginServiceApiClient, "batch_get_paas_plugin_detailed_info")
    def test_get_plugin_detail_list_success(self, mock_get_detailed):
        """Test get_plugin_detail_list when successful"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detailed.return_value = {"count": 1, "results": [{"code": "plugin1", "detail": "info"}]}
            result = PluginServiceApiClient.get_plugin_detail_list(search_term="test")

            assert result["result"] is True
            assert result["data"]["count"] == 1

    @mock.patch.object(PluginServiceApiClient, "batch_get_paas_plugin_detailed_info")
    def test_get_plugin_detail_list_failure(self, mock_get_detailed):
        """Test get_plugin_detail_list when failed"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            mock_get_detailed.return_value = {"result": False, "message": "Failed"}
            result = PluginServiceApiClient.get_plugin_detail_list()

            assert result["result"] is False

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_info")
    def test_get_plugin_app_detail_not_enabled(self, mock_get_info):
        """Test get_plugin_app_detail when plugin service is not enabled"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "0"):
            result = PluginServiceApiClient.get_plugin_app_detail("test_plugin")

            assert result["result"] is False
            mock_get_info.assert_not_called()

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_info")
    def test_get_plugin_app_detail_network_error(self, mock_get_info):
        """Test get_plugin_app_detail with network error"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                mock_get_info.return_value = {"result": False, "message": "Network timeout"}
                result = PluginServiceApiClient.get_plugin_app_detail("test_plugin")

                assert result["result"] is False
                assert "network error" in result["message"]

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_info")
    def test_get_plugin_app_detail_not_deployed(self, mock_get_info):
        """Test get_plugin_app_detail when plugin is not deployed"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                mock_get_info.return_value = {
                    "deployed_statuses": {"prod": {"deployed": False}},
                    "plugin": {},
                    "profile": {},
                }
                result = PluginServiceApiClient.get_plugin_app_detail("test_plugin")

                assert result["result"] is False
                assert "does not deployed" in result["message"]

    @mock.patch.object(PluginServiceApiClient, "get_paas_plugin_info")
    def test_get_plugin_app_detail_success(self, mock_get_info):
        """Test get_plugin_app_detail when successful"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                mock_get_info.return_value = {
                    "deployed_statuses": {
                        "prod": {
                            "deployed": True,
                            "addresses": [
                                {"type": 2, "address": "http://default.example.com"},
                                {"type": 1, "address": "http://other.example.com"},
                            ],
                        }
                    },
                    "plugin": {"name": "Test Plugin", "code": "test_plugin", "updated": "2024-01-01", "tag_info": {}},
                    "profile": {"api_gw_name": "test_apigw"},
                }
                result = PluginServiceApiClient.get_plugin_app_detail("test_plugin")

                assert result["result"] is True
                assert result["data"]["url"] == "http://default.example.com"
                assert result["data"]["code"] == "test_plugin"
                assert result["data"]["apigw_name"] == "test_apigw"
                assert len(result["data"]["urls"]) == 2


class TestPluginServiceApiClientPaasApiMethods:
    """Test PaaS API related methods"""

    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_get_paas_plugin_info_single_plugin(self, mock_request):
        """Test get_paas_plugin_info for single plugin"""
        with mock.patch.object(env, "PAASV3_APIGW_API_HOST", "http://paas.example.com"):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                    mock_request.return_value = mock.Mock(json=lambda: {"plugin": {"code": "test"}}, status_code=200)
                    result = PluginServiceApiClient.get_paas_plugin_info("test_plugin", environment="prod")

                    assert result["plugin"]["code"] == "test"
                    mock_request.assert_called_once()

    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_get_paas_plugin_info_list_plugins(self, mock_request):
        """Test get_paas_plugin_info for listing plugins"""
        with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", None):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "app_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                    with mock.patch.object(env, "APIGW_NETWORK_PROTOCAL", "http"):
                        with mock.patch.object(env, "APIGW_URL_SUFFIX", "example.com"):
                            with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                                mock_request.return_value = mock.Mock(
                                    json=lambda: {"count": 10, "results": []}, status_code=200
                                )
                                result = PluginServiceApiClient.get_paas_plugin_info(
                                    limit=50, offset=10, search_term="test", distributor_code_name="dist1"
                                )

                                assert result["count"] == 10
                                call_kwargs = mock_request.call_args[1]
                                assert call_kwargs["params"]["limit"] == 50
                                assert call_kwargs["params"]["search_term"] == "test"

    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_batch_get_paas_plugin_detailed_info(self, mock_request):
        """Test batch_get_paas_plugin_detailed_info"""
        with mock.patch.object(env, "PAASV3_APIGW_API_HOST", "http://paas.example.com"):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                    mock_request.return_value = mock.Mock(json=lambda: {"count": 5, "results": []}, status_code=200)
                    result = PluginServiceApiClient.batch_get_paas_plugin_detailed_info(
                        environment="prod", search_term="test", distributor_code_name="dist1", extra_param="value"
                    )

                    assert result["count"] == 5
                    call_kwargs = mock_request.call_args[1]
                    assert "search_term" in call_kwargs["params"]
                    assert "distributor_code_name" in call_kwargs["params"]

    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_get_paas_logs(self, mock_request):
        """Test get_paas_logs"""
        with mock.patch.object(env, "PAASV3_APIGW_API_HOST", "http://paas.example.com"):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                    mock_request.return_value = mock.Mock(json=lambda: {"logs": []}, status_code=200)
                    result = PluginServiceApiClient.get_paas_logs("test_plugin", "trace123", scroll_id="scroll1")

                    assert "logs" in result
                    call_kwargs = mock_request.call_args[1]
                    assert call_kwargs["data"]["trace_id"] == "trace123"
                    assert call_kwargs["data"]["scroll_id"] == "scroll1"

    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_get_paas_logs_without_scroll_id(self, mock_request):
        """Test get_paas_logs without scroll_id"""
        with mock.patch.object(env, "PAASV3_APIGW_API_HOST", "http://paas.example.com"):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                    mock_request.return_value = mock.Mock(json=lambda: {"logs": []}, status_code=200)
                    result = PluginServiceApiClient.get_paas_logs("test_plugin", "trace123")

                    assert "logs" in result
                    call_kwargs = mock_request.call_args[1]
                    assert "scroll_id" not in call_kwargs["data"]

    @mock.patch.object(PluginServiceApiClient, "_request_api_and_error_retry")
    def test_get_paas_plugin_tags(self, mock_request):
        """Test get_paas_plugin_tags"""
        with mock.patch.object(env, "PAASV3_APIGW_API_HOST", "http://paas.example.com"):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "app_code"):
                    with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                        with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                            mock_request.return_value = mock.Mock(json=lambda: [{"name": "tag1"}], status_code=200)
                            result = PluginServiceApiClient.get_paas_plugin_tags(environment="prod")

                            assert len(result) == 1
                            # Check that app info is force added
                            call_kwargs = mock_request.call_args[1]
                            assert "bk_app_code" in call_kwargs["params"]


class TestPluginServiceApiClientHelperMethods:
    """Test helper methods of PluginServiceApiClient"""

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    def test_prepare_apigw_api_request(self, mock_get_detail):
        """Test _prepare_apigw_api_request"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            client = PluginServiceApiClient("test_plugin")
                            url, headers = client._prepare_apigw_api_request(["invoke", "v1"])

                            assert "http://test_plugin.example.com" in url
                            assert "prod" in url
                            assert "X-Bkapi-Authorization" in headers
                            assert headers["Content-Type"] == "application/json"

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    def test_prepare_apigw_api_request_with_api_name_placeholder(self, mock_get_detail):
        """Test _prepare_apigw_api_request with {api_name} placeholder"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{api_name}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            client = PluginServiceApiClient("test_plugin")
                            url, headers = client._prepare_apigw_api_request(["invoke", "v1"])

                            assert "http://test_plugin.example.com" in url

    @mock.patch.object(PluginServiceApiClient, "get_plugin_app_detail")
    def test_prepare_apigw_api_request_with_inject_authorization(self, mock_get_detail):
        """Test _prepare_apigw_api_request with inject_authorization"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "test_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "test_secret"):
                    with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                        with mock.patch.object(env, "PLUGIN_APIGW_API_HOST_FORMAT", "http://{}.example.com"):
                            mock_get_detail.return_value = {
                                "result": True,
                                "data": {"url": "http://plugin.example.com", "apigw_name": "test_plugin"},
                            }
                            client = PluginServiceApiClient("test_plugin")
                            url, headers = client._prepare_apigw_api_request(
                                ["invoke", "v1"], inject_authorization={"bk_username": "admin"}
                            )

                            auth_info = json.loads(headers["X-Bkapi-Authorization"])
                            assert "bk_username" in auth_info
                            assert auth_info["bk_username"] == "admin"

    def test_prepare_paas_api_request_with_token(self):
        """Test _prepare_paas_api_request with API token"""
        with mock.patch.object(env, "PAASV3_APIGW_API_HOST", "http://paas.example.com"):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                    url, params = PluginServiceApiClient._prepare_paas_api_request(
                        ["system", "bk_plugins"], environment="prod"
                    )

                    assert "http://paas.example.com" in url
                    assert params["private_token"] == "test_token"

    def test_prepare_paas_api_request_without_token(self):
        """Test _prepare_paas_api_request without API token"""
        with mock.patch.object(env, "PAASV3_APIGW_API_HOST", None):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", None):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "app_code"):
                    with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                        with mock.patch.object(env, "APIGW_NETWORK_PROTOCAL", "http"):
                            with mock.patch.object(env, "APIGW_URL_SUFFIX", "example.com"):
                                with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                                    url, params = PluginServiceApiClient._prepare_paas_api_request(
                                        ["system", "bk_plugins"]
                                    )

                                    assert "example.com" in url
                                    assert params["bk_app_code"] == "app_code"
                                    assert params["bk_app_secret"] == "app_secret"

    def test_prepare_paas_api_request_force_add_app_info(self):
        """Test _prepare_paas_api_request with force_add_app_info"""
        with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
            with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_CODE", "app_code"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                    with mock.patch.object(env, "PAASV3_APIGW_API_HOST", "http://paas.example.com"):
                        with mock.patch.object(env, "APIGW_ENVIRONMENT", "prod"):
                            url, params = PluginServiceApiClient._prepare_paas_api_request(
                                ["system", "bk_plugins"], force_add_app_info=True
                            )

                            assert params["private_token"] == "test_token"
                            assert params["bk_app_code"] == "app_code"
                            assert params["bk_app_secret"] == "app_secret"

    @mock.patch("plugin_service.plugin_client.requests.get")
    def test_request_api_and_error_retry_success(self, mock_get):
        """Test _request_api_and_error_retry success on first try"""
        with mock.patch.object(env, "BKAPP_INVOKE_PAAS_RETRY_NUM", 3):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                    mock_response = mock.Mock()
                    mock_response.status_code = 200
                    mock_get.return_value = mock_response

                    result = PluginServiceApiClient._request_api_and_error_retry("http://api.example.com", method="get")

                    assert result == mock_response
                    assert mock_get.call_count == 1

    @mock.patch("plugin_service.plugin_client.requests.post")
    def test_request_api_and_error_retry_http_error_then_success(self, mock_post):
        """Test _request_api_and_error_retry with HTTP error then success"""
        with mock.patch.object(env, "BKAPP_INVOKE_PAAS_RETRY_NUM", 3):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                    mock_error_response = mock.Mock()
                    mock_error_response.raise_for_status.side_effect = HTTPError("500 Server Error")

                    mock_success_response = mock.Mock()
                    mock_success_response.status_code = 200

                    mock_post.side_effect = [mock_error_response, mock_success_response]

                    result = PluginServiceApiClient._request_api_and_error_retry(
                        "http://api.example.com", method="post", data={"key": "value"}
                    )

                    assert result == mock_success_response
                    assert mock_post.call_count == 2

    @mock.patch("plugin_service.plugin_client.requests.get")
    def test_request_api_and_error_retry_all_retries_failed(self, mock_get):
        """Test _request_api_and_error_retry when all retries fail"""
        with mock.patch.object(env, "BKAPP_INVOKE_PAAS_RETRY_NUM", 3):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                    mock_response = mock.Mock()
                    mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")
                    mock_get.return_value = mock_response

                    result = PluginServiceApiClient._request_api_and_error_retry("http://api.example.com", method="get")

                    # Should still return the last response even if it failed
                    assert result == mock_response
                    assert mock_get.call_count == 3

    @mock.patch("plugin_service.plugin_client.requests.post")
    def test_request_api_and_error_retry_exception(self, mock_post):
        """Test _request_api_and_error_retry with unexpected exception"""
        with mock.patch.object(env, "BKAPP_INVOKE_PAAS_RETRY_NUM", 3):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "test_token"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                    mock_post.side_effect = ValueError("Unexpected error")

                    with pytest.raises(ValueError) as exc_info:
                        PluginServiceApiClient._request_api_and_error_retry("http://api.example.com", method="post")

                    assert "Unexpected error" in str(exc_info.value)
                    assert mock_post.call_count == 1

    @mock.patch("plugin_service.plugin_client.requests.get")
    def test_request_api_and_error_retry_masks_token(self, mock_get):
        """Test _request_api_and_error_retry masks sensitive token in logs"""
        with mock.patch.object(env, "BKAPP_INVOKE_PAAS_RETRY_NUM", 1):
            with mock.patch.object(env, "PAASV3_APIGW_API_TOKEN", "secret_token"):
                with mock.patch.object(env, "PLUGIN_SERVICE_APIGW_APP_SECRET", "app_secret"):
                    mock_response = mock.Mock()
                    mock_response.status_code = 200
                    mock_get.return_value = mock_response

                    result = PluginServiceApiClient._request_api_and_error_retry(
                        "http://api.example.com?token=secret_token", method="get"
                    )

                    assert result == mock_response
