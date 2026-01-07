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
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from plugin_service import env
from plugin_service.api_decorators import inject_plugin_client, validate_params
from plugin_service.exceptions import PluginServiceException


class TestInjectPluginClient:
    """Test inject_plugin_client decorator"""

    @mock.patch("plugin_service.api_decorators.PluginServiceApiClient")
    def test_inject_plugin_client_success(self, mock_client_class):
        """Test successful plugin client injection"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            factory = APIRequestFactory()
            django_request = factory.get("/test/")
            request = Request(django_request)
            request.validated_data = {"plugin_code": "test_plugin"}

            mock_client_instance = mock.Mock()
            mock_client_class.return_value = mock_client_instance

            @inject_plugin_client
            def view_func(req):
                return {"plugin_client": req.plugin_client, "result": True}

            result = view_func(request)
            assert result["result"] is True
            assert result["plugin_client"] == mock_client_instance
            mock_client_class.assert_called_once_with("test_plugin")

    @mock.patch("plugin_service.api_decorators.PluginServiceApiClient")
    def test_inject_plugin_client_exception(self, mock_client_class):
        """Test plugin client injection when exception occurs"""
        with mock.patch.object(env, "USE_PLUGIN_SERVICE", "1"):
            factory = APIRequestFactory()
            django_request = factory.get("/test/")
            request = Request(django_request)
            request.validated_data = {"plugin_code": "test_plugin"}

            mock_client_class.side_effect = PluginServiceException("Plugin initialization failed")

            @inject_plugin_client
            def view_func(req):
                return {"result": True}

            response = view_func(request)
            # Should return JsonResponse
            assert response.status_code == 200
            _ = response.data if hasattr(response, "data") else response.content
            # JsonResponse returns rendered content, so we check the response type
            assert response["Content-Type"] == "application/json"


class TestValidateParams:
    """Test validate_params decorator"""

    def test_validate_params_get_request_success(self):
        """Test validate_params with valid GET request"""

        class TestSerializer(serializers.Serializer):
            param1 = serializers.CharField(required=True)
            param2 = serializers.IntegerField(required=False, default=10)

        factory = APIRequestFactory()
        django_request = factory.get("/test/", {"param1": "value1", "param2": "20"})
        request = Request(django_request)

        @validate_params(TestSerializer)
        def view_func(req):
            return {"data": req.validated_data, "result": True}

        result = view_func(request)
        assert result["result"] is True
        assert result["data"]["param1"] == "value1"
        assert result["data"]["param2"] == 20

    def test_validate_params_post_request_success(self):
        """Test validate_params with valid POST request"""

        class TestSerializer(serializers.Serializer):
            name = serializers.CharField(required=True)
            age = serializers.IntegerField(required=False)

        factory = APIRequestFactory()
        # Use GET method to set query_params, but test POST logic by mocking method
        django_request = factory.post("/test/", data={"name": "John", "age": "30"})
        request = Request(django_request)
        # Manually set data to avoid parser issues in test
        request._full_data = {"name": "John", "age": 30}

        @validate_params(TestSerializer)
        def view_func(req):
            return {"data": req.validated_data, "result": True}

        result = view_func(request)
        assert result["result"] is True
        assert result["data"]["name"] == "John"
        assert result["data"]["age"] == 30

    def test_validate_params_validation_error(self):
        """Test validate_params with validation error"""

        class TestSerializer(serializers.Serializer):
            required_field = serializers.CharField(required=True)
            number_field = serializers.IntegerField(required=True)

        factory = APIRequestFactory()
        # Missing required_field
        django_request = factory.get("/test/", {"number_field": "not_a_number"})
        request = Request(django_request)

        @validate_params(TestSerializer)
        def view_func(req):
            return {"result": True}

        with pytest.raises(Exception):  # ValidationError will be raised
            view_func(request)

    def test_validate_params_with_default_values(self):
        """Test validate_params with default values"""

        class TestSerializer(serializers.Serializer):
            limit = serializers.IntegerField(required=False, default=100)
            offset = serializers.IntegerField(required=False, default=0)

        factory = APIRequestFactory()
        django_request = factory.get("/test/", {})
        request = Request(django_request)

        @validate_params(TestSerializer)
        def view_func(req):
            return {"data": req.validated_data}

        result = view_func(request)
        assert result["data"]["limit"] == 100
        assert result["data"]["offset"] == 0

    def test_validate_params_put_request(self):
        """Test validate_params with PUT request"""

        class TestSerializer(serializers.Serializer):
            field1 = serializers.CharField()

        factory = APIRequestFactory()
        django_request = factory.put("/test/")
        request = Request(django_request)
        request._full_data = {"field1": "updated_value"}

        @validate_params(TestSerializer)
        def view_func(req):
            return {"data": req.validated_data}

        result = view_func(request)
        assert result["data"]["field1"] == "updated_value"

    def test_validate_params_preserves_function_metadata(self):
        """Test that validate_params preserves function metadata"""

        class TestSerializer(serializers.Serializer):
            param = serializers.CharField()

        @validate_params(TestSerializer)
        def my_view(request):
            """My view docstring"""
            return {"result": True}

        assert my_view.__name__ == "my_view"
        assert my_view.__doc__ == "My view docstring"
