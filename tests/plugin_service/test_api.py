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
from unittest import mock

from rest_framework.test import APIRequestFactory

from plugin_service import api
from plugin_service.exceptions import PluginServiceException


class TestGetPluginList:
    """Test get_plugin_list view"""

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    def test_get_plugin_list_without_tag_id(self, mock_get_list):
        """Test get_plugin_list without tag_id parameter"""
        mock_get_list.return_value = {
            "result": True,
            "message": None,
            "data": {
                "plugins": [
                    {"code": "plugin1", "name": "Plugin 1", "logo_url": "http://example.com/logo1.png"},
                    {"code": "plugin2", "name": "Plugin 2", "logo_url": "http://example.com/logo2.png"},
                ],
                "count": 2,
            },
        }

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/list/", {"search_term": "test", "limit": "10", "offset": "0"})

        response = api.get_plugin_list(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert len(data["data"]["plugins"]) == 2
        mock_get_list.assert_called_once_with(
            search_term="test",
            limit=10,
            offset=0,
            distributor_code_name="test_distributor",
        )

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    def test_get_plugin_list_with_tag_id(self, mock_get_list):
        """Test get_plugin_list with tag_id parameter"""
        mock_get_list.return_value = {
            "result": True,
            "message": None,
            "data": {"plugins": [], "count": 0},
        }

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/list/", {"limit": "20", "offset": "5", "tag_id": "3"})

        response = api.get_plugin_list(request)

        assert response.status_code == 200
        mock_get_list.assert_called_once_with(
            search_term=None,
            limit=20,
            offset=5,
            distributor_code_name="test_distributor",
            tag_id=3,
        )


class TestGetPluginTags:
    """Test get_plugin_tags view"""

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_tags_list")
    def test_get_plugin_tags_without_unknown_tag(self, mock_get_tags):
        """Test get_plugin_tags without with_unknown_tag parameter"""
        mock_get_tags.return_value = {
            "result": True,
            "message": None,
            "data": [
                {"code_name": "TAG1", "name": "标签1", "id": 1},
                {"code_name": "TAG2", "name": "标签2", "id": 2},
            ],
        }

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/tags/")

        response = api.get_plugin_tags(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert len(data["data"]) == 2
        mock_get_tags.assert_called_once()

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_tags_list")
    def test_get_plugin_tags_with_unknown_tag(self, mock_get_tags):
        """Test get_plugin_tags with with_unknown_tag parameter"""
        mock_get_tags.return_value = {
            "result": True,
            "message": None,
            "data": [
                {"code_name": "TAG1", "name": "标签1", "id": 1},
            ],
        }

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/tags/", {"with_unknown_tag": "true"})

        response = api.get_plugin_tags(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert len(data["data"]) == 2
        assert data["data"][-1]["code_name"] == "OTHER"
        assert data["data"][-1]["name"] == "未分类"
        assert data["data"][-1]["id"] == -1

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_tags_list")
    def test_get_plugin_tags_with_failed_result(self, mock_get_tags):
        """Test get_plugin_tags when result is False"""
        mock_get_tags.return_value = {
            "result": False,
            "message": "Error occurred",
            "data": None,
        }

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/tags/", {"with_unknown_tag": "true"})

        response = api.get_plugin_tags(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is False
        assert data["data"] is None


class TestGetPluginDetailList:
    """Test get_plugin_detail_list view"""

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_detail_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    @mock.patch("plugin_service.api.env.APIGW_ENVIRONMENT", "prod")
    def test_get_plugin_detail_list_basic(self, mock_get_detail_list):
        """Test get_plugin_detail_list with basic parameters and exclude_not_deployed=False"""
        mock_get_detail_list.return_value = {
            "result": True,
            "message": None,
            "data": {
                "plugins": [
                    {
                        "plugin": {"code": "plugin1", "name": "Plugin 1", "logo_url": "http://example.com/logo1.png"},
                        "deployed_statuses": {"prod": {"deployed": True}, "stag": {"deployed": False}},
                        "profile": {"contact": "admin", "introduction": "Test plugin"},
                    }
                ],
                "count": 1,
            },
        }

        factory = APIRequestFactory()
        request = factory.get(
            "/api/plugin/detail_list/", {"limit": "10", "offset": "0", "exclude_not_deployed": "false"}
        )

        response = api.get_plugin_detail_list(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["return_plugin_count"] == 1
        assert data["data"]["next_offset"] == 10

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_detail_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    @mock.patch("plugin_service.api.env.APIGW_ENVIRONMENT", "prod")
    def test_get_plugin_detail_list_with_fetch_all(self, mock_get_detail_list):
        """Test get_plugin_detail_list with fetch_all=True"""
        mock_get_detail_list.return_value = {
            "result": True,
            "message": None,
            "data": {
                "plugins": [
                    {
                        "plugin": {"code": "plugin1", "name": "Plugin 1", "logo_url": "http://example.com/logo1.png"},
                        "deployed_statuses": {"prod": {"deployed": True}, "stag": {"deployed": False}},
                        "profile": {"contact": "admin", "introduction": "Test plugin"},
                    }
                ],
                "count": 1,
            },
        }

        factory = APIRequestFactory()
        request = factory.get(
            "/api/plugin/detail_list/", {"fetch_all": "true", "search_term": "test", "exclude_not_deployed": "false"}
        )

        response = api.get_plugin_detail_list(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["next_offset"] == -1

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_detail_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    @mock.patch("plugin_service.api.env.APIGW_ENVIRONMENT", "prod")
    def test_get_plugin_detail_list_exclude_not_deployed(self, mock_get_detail_list):
        """Test get_plugin_detail_list with exclude_not_deployed=True"""
        mock_get_detail_list.return_value = {
            "result": True,
            "message": None,
            "data": {
                "plugins": [
                    {
                        "plugin": {"code": "plugin1", "name": "Plugin 1", "logo_url": "http://example.com/logo1.png"},
                        "deployed_statuses": {"prod": {"deployed": True}, "stag": {"deployed": False}},
                        "profile": {"contact": "admin", "introduction": "Test plugin 1"},
                    },
                    {
                        "plugin": {"code": "plugin2", "name": "Plugin 2", "logo_url": "http://example.com/logo2.png"},
                        "deployed_statuses": {"prod": {"deployed": False}, "stag": {"deployed": True}},
                        "profile": {"contact": "admin", "introduction": "Test plugin 2"},
                    },
                ],
                "count": 2,
            },
        }

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/detail_list/", {"limit": "10", "offset": "0"})

        response = api.get_plugin_detail_list(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["return_plugin_count"] == 1

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_detail_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    def test_get_plugin_detail_list_api_failure(self, mock_get_detail_list):
        """Test get_plugin_detail_list when API returns failure"""
        mock_get_detail_list.return_value = {
            "result": False,
            "message": "API Error",
            "data": None,
        }

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/detail_list/", {"limit": "10", "offset": "0"})

        response = api.get_plugin_detail_list(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is False
        assert data["message"] == "API Error"

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_detail_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    def test_get_plugin_detail_list_fetch_all_with_failure(self, mock_get_detail_list):
        """Test get_plugin_detail_list with fetch_all when API fails"""
        mock_get_detail_list.return_value = {
            "result": False,
            "message": "API Error",
            "data": None,
        }

        factory = APIRequestFactory()
        request = factory.get(
            "/api/plugin/detail_list/", {"fetch_all": "true", "search_term": "test", "exclude_not_deployed": "false"}
        )

        response = api.get_plugin_detail_list(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is False
        assert data["message"] == "API Error"

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_detail_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    @mock.patch("plugin_service.api.env.APIGW_ENVIRONMENT", "prod")
    def test_get_plugin_detail_list_scrolling_with_tag(self, mock_get_detail_list):
        """Test get_plugin_detail_list in scrolling mode with tag_id"""
        mock_get_detail_list.side_effect = [
            {
                "result": True,
                "message": None,
                "data": {
                    "plugins": [
                        {
                            "plugin": {
                                "code": "plugin1",
                                "name": "Plugin 1",
                                "logo_url": "http://example.com/logo1.png",
                            },
                            "deployed_statuses": {"prod": {"deployed": True}, "stag": {"deployed": False}},
                            "profile": {"contact": "admin", "introduction": "Test plugin 1"},
                        },
                        {
                            "plugin": {
                                "code": "plugin2",
                                "name": "Plugin 2",
                                "logo_url": "http://example.com/logo2.png",
                            },
                            "deployed_statuses": {"prod": {"deployed": True}, "stag": {"deployed": False}},
                            "profile": {"contact": "admin", "introduction": "Test plugin 2"},
                        },
                    ],
                    "count": 2,
                },
            }
        ]

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/detail_list/", {"limit": "2", "offset": "0", "tag_id": "5"})

        response = api.get_plugin_detail_list(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["return_plugin_count"] == 2
        # Verify tag_id was passed
        call_args = mock_get_detail_list.call_args
        assert call_args[1]["tag_id"] == 5

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_detail_list")
    @mock.patch("plugin_service.api.PLUGIN_DISTRIBUTOR_NAME", "test_distributor")
    @mock.patch("plugin_service.api.env.APIGW_ENVIRONMENT", "prod")
    def test_get_plugin_detail_list_scrolling_multiple_calls(self, mock_get_detail_list):
        """Test get_plugin_detail_list in scrolling mode with multiple API calls"""
        # First call returns 2 plugins, only 1 deployed
        # Second call returns 2 more plugins, both deployed - triggers break
        mock_get_detail_list.side_effect = [
            {
                "result": True,
                "message": None,
                "data": {
                    "plugins": [
                        {
                            "plugin": {
                                "code": "plugin1",
                                "name": "Plugin 1",
                                "logo_url": "http://example.com/logo1.png",
                            },
                            "deployed_statuses": {"prod": {"deployed": True}, "stag": {"deployed": False}},
                            "profile": {"contact": "admin", "introduction": "Test plugin 1"},
                        },
                        {
                            "plugin": {
                                "code": "plugin2",
                                "name": "Plugin 2",
                                "logo_url": "http://example.com/logo2.png",
                            },
                            "deployed_statuses": {"prod": {"deployed": False}, "stag": {"deployed": True}},
                            "profile": {"contact": "admin", "introduction": "Test plugin 2"},
                        },
                    ],
                    "count": 100,  # Large count to prevent count-based break
                },
            },
            {
                "result": True,
                "message": None,
                "data": {
                    "plugins": [
                        {
                            "plugin": {
                                "code": "plugin3",
                                "name": "Plugin 3",
                                "logo_url": "http://example.com/logo3.png",
                            },
                            "deployed_statuses": {"prod": {"deployed": True}, "stag": {"deployed": False}},
                            "profile": {"contact": "admin", "introduction": "Test plugin 3"},
                        },
                        {
                            "plugin": {
                                "code": "plugin4",
                                "name": "Plugin 4",
                                "logo_url": "http://example.com/logo4.png",
                            },
                            "deployed_statuses": {"prod": {"deployed": True}, "stag": {"deployed": False}},
                            "profile": {"contact": "admin", "introduction": "Test plugin 4"},
                        },
                    ],
                    "count": 100,
                },
            },
        ]

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/detail_list/", {"limit": "2", "offset": "0"})

        response = api.get_plugin_detail_list(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        # Should return exactly 2 plugins (limit reached, triggering break)
        assert data["data"]["return_plugin_count"] == 2
        # Verify API was called twice
        assert mock_get_detail_list.call_count == 2


class TestGetPluginDetail:
    """Test get_plugin_detail view"""

    @mock.patch("plugin_service.api_decorators.PluginServiceApiClient")
    @mock.patch("plugin_service.api.env.USE_PLUGIN_SERVICE", "1")
    def test_get_plugin_detail_without_app_detail(self, mock_client_class):
        """Test get_plugin_detail without app detail"""
        mock_client_instance = mock.Mock()
        mock_client_instance.get_detail.return_value = {
            "result": True,
            "message": None,
            "data": {"version": "1.0.0", "inputs": {}, "context_inputs": {}, "outputs": {}, "forms": {}},
        }
        mock_client_class.return_value = mock_client_instance

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/detail/", {"plugin_code": "test_plugin", "plugin_version": "1.0.0"})

        response = api.get_plugin_detail(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["version"] == "1.0.0"
        mock_client_instance.get_detail.assert_called_once_with("1.0.0")

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_app_detail")
    @mock.patch("plugin_service.api_decorators.PluginServiceApiClient")
    @mock.patch("plugin_service.api.env.USE_PLUGIN_SERVICE", "1")
    def test_get_plugin_detail_with_app_detail(self, mock_client_class, mock_get_app_detail):
        """Test get_plugin_detail with app detail"""
        mock_client_instance = mock.Mock()
        mock_client_instance.get_detail.return_value = {
            "result": True,
            "message": None,
            "data": {"version": "1.0.0", "inputs": {}, "context_inputs": {}, "outputs": {}, "forms": {}},
        }
        mock_client_class.return_value = mock_client_instance

        mock_get_app_detail.return_value = {
            "result": True,
            "message": None,
            "data": {
                "code": "test_app",
                "name": "Test App",
                "updated": "2024-01-01T00:00:00",
                "url": "http://example.com",
                "urls": ["http://example.com"],
            },
        }

        factory = APIRequestFactory()
        request = factory.get(
            "/api/plugin/detail/",
            {"plugin_code": "test_plugin", "plugin_version": "1.0.0", "with_app_detail": "true"},
        )

        response = api.get_plugin_detail(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert "app" in data["data"]

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_app_detail")
    @mock.patch("plugin_service.api_decorators.PluginServiceApiClient")
    @mock.patch("plugin_service.api.env.USE_PLUGIN_SERVICE", "1")
    def test_get_plugin_detail_with_app_detail_failure(self, mock_client_class, mock_get_app_detail):
        """Test get_plugin_detail when app_detail request fails"""
        mock_client_instance = mock.Mock()
        mock_client_instance.get_detail.return_value = {
            "result": True,
            "message": None,
            "data": {"version": "1.0.0", "inputs": {}, "context_inputs": {}, "outputs": {}, "forms": {}},
        }
        mock_client_class.return_value = mock_client_instance

        mock_get_app_detail.return_value = {
            "result": False,
            "message": "App detail not found",
            "data": None,
        }

        factory = APIRequestFactory()
        request = factory.get(
            "/api/plugin/detail/",
            {"plugin_code": "test_plugin", "plugin_version": "1.0.0", "with_app_detail": "true"},
        )

        response = api.get_plugin_detail(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is False
        assert data["message"] == "App detail not found"

    @mock.patch("plugin_service.api_decorators.PluginServiceApiClient")
    @mock.patch("plugin_service.api.env.USE_PLUGIN_SERVICE", "1")
    def test_get_plugin_detail_failure(self, mock_client_class):
        """Test get_plugin_detail when detail request fails"""
        mock_client_instance = mock.Mock()
        mock_client_instance.get_detail.return_value = {
            "result": False,
            "message": "Detail not found",
            "data": None,
        }
        mock_client_class.return_value = mock_client_instance

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/detail/", {"plugin_code": "test_plugin", "plugin_version": "1.0.0"})

        response = api.get_plugin_detail(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is False


class TestGetMeta:
    """Test get_meta view"""

    @mock.patch("plugin_service.api_decorators.PluginServiceApiClient")
    @mock.patch("plugin_service.api.env.USE_PLUGIN_SERVICE", "1")
    def test_get_meta_success(self, mock_client_class):
        """Test get_meta successful response"""
        mock_client_instance = mock.Mock()
        mock_client_instance.get_meta.return_value = {
            "result": True,
            "message": None,
            "data": {
                "code": "test_plugin",
                "description": "Test Plugin Description",
                "versions": ["1.0.0", "1.0.1"],
                "language": "python",
                "framework_version": "1.0.0",
                "runtime_version": "3.8",
            },
        }
        mock_client_class.return_value = mock_client_instance

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/meta/", {"plugin_code": "test_plugin"})

        response = api.get_meta(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["code"] == "test_plugin"
        assert len(data["data"]["versions"]) == 2
        mock_client_instance.get_meta.assert_called_once()


class TestGetLogs:
    """Test get_logs view"""

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_logs")
    def test_get_logs_success(self, mock_get_logs):
        """Test get_logs successful response"""
        mock_get_logs.return_value = {
            "result": True,
            "message": None,
            "data": {
                "logs": [
                    {
                        "ts": "2024-01-01 00:00:00",
                        "detail": {
                            "json.levelname": "INFO",
                            "json.funcName": "test_func",
                            "json.message": "Test log message 1",
                        },
                    },
                    {
                        "ts": "2024-01-01 00:00:01",
                        "detail": {
                            "json.levelname": "ERROR",
                            "json.funcName": "error_func",
                            "json.message": "Test error message",
                        },
                    },
                ],
                "scroll_id": "scroll123",
                "total": 2,
            },
        }

        factory = APIRequestFactory()
        request = factory.post(
            "/api/plugin/logs/",
            data=json.dumps({"plugin_code": "test_plugin", "trace_id": "trace123", "scroll_id": "scroll456"}),
            content_type="application/json",
        )

        response = api.get_logs(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert "logs" in data["data"]
        assert isinstance(data["data"]["logs"], str)
        assert "[2024-01-01 00:00:00]INFO-test_func: Test log message 1" in data["data"]["logs"]
        mock_get_logs.assert_called_once_with("test_plugin", "trace123", "scroll456")

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_logs")
    def test_get_logs_failure(self, mock_get_logs):
        """Test get_logs when API returns failure"""
        mock_get_logs.return_value = {
            "result": False,
            "message": "Logs not found",
            "data": None,
        }

        factory = APIRequestFactory()
        request = factory.post(
            "/api/plugin/logs/",
            data=json.dumps({"plugin_code": "test_plugin", "trace_id": "trace123"}),
            content_type="application/json",
        )

        response = api.get_logs(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is False


class TestGetPluginAppDetail:
    """Test get_plugin_app_detail view"""

    @mock.patch("plugin_service.api.PluginServiceApiClient.get_plugin_app_detail")
    def test_get_plugin_app_detail_success(self, mock_get_app_detail):
        """Test get_plugin_app_detail successful response"""
        mock_get_app_detail.return_value = {
            "result": True,
            "message": None,
            "data": {
                "code": "test_app",
                "name": "Test App",
                "updated": "2024-01-01T00:00:00",
                "url": "http://example.com",
                "urls": ["http://example.com"],
            },
        }

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/app_detail/", {"plugin_code": "test_plugin"})

        response = api.get_plugin_app_detail(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["code"] == "test_app"
        mock_get_app_detail.assert_called_once_with("test_plugin")


class TestGetPluginApiData:
    """Test get_plugin_api_data view"""

    @mock.patch("plugin_service.api.PluginServiceApiClient")
    @mock.patch("plugin_service.api.env.USE_PLUGIN_SERVICE", "1")
    @mock.patch("plugin_service.api.env.APIGW_USER_AUTH_KEY_NAME", "bk_token")
    def test_get_plugin_api_data_get_request(self, mock_client_class):
        """Test get_plugin_api_data with GET request"""
        mock_client_instance = mock.Mock()
        mock_client_instance.dispatch_plugin_api_request.return_value = {
            "result": True,
            "message": None,
            "data": {"key": "value"},
        }
        mock_client_class.return_value = mock_client_instance

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/test_plugin/data/users/", {"page": "1", "size": "10"})
        request.user = mock.Mock(username="testuser")
        request.COOKIES = {}

        response = api.get_plugin_api_data(request, "test_plugin", "data/users")

        assert response.status_code == 200
        assert response.data == {"key": "value"}

    @mock.patch("plugin_service.api.PluginServiceApiClient")
    @mock.patch("plugin_service.api.env.USE_PLUGIN_SERVICE", "1")
    def test_get_plugin_api_data_failure_response(self, mock_client_class):
        """Test get_plugin_api_data when plugin returns failure"""
        mock_client_instance = mock.Mock()
        mock_client_instance.dispatch_plugin_api_request.return_value = {
            "result": False,
            "message": "Plugin error",
            "data": None,
        }
        mock_client_class.return_value = mock_client_instance

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/test_plugin/data/users/")
        request.user = mock.Mock(username="testuser")
        request.COOKIES = {}

        response = api.get_plugin_api_data(request, "test_plugin", "data/users")

        assert response.status_code == 200
        assert response.data["result"] is False
        assert response.data["message"] == "Plugin error"

    @mock.patch("plugin_service.api.PluginServiceApiClient")
    @mock.patch("plugin_service.api.env.USE_PLUGIN_SERVICE", "1")
    def test_get_plugin_api_data_client_exception(self, mock_client_class):
        """Test get_plugin_api_data when client initialization fails"""
        mock_client_class.side_effect = PluginServiceException("Client init failed")

        factory = APIRequestFactory()
        request = factory.get("/api/plugin/test_plugin/data/users/")
        request.user = mock.Mock(username="testuser")
        request.COOKIES = {}

        response = api.get_plugin_api_data(request, "test_plugin", "data/users")

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["result"] is False
        assert "Client init failed" in data["message"]
