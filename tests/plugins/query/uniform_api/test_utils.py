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
from unittest.mock import patch

import pytest
from django.conf import settings

from bkflow.exceptions import APIRequestError, ValidationError
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient


class TestUniformAPIClientMethods:
    """测试 UniformAPIClient 的方法"""

    def setup_method(self, method):
        self.client = UniformAPIClient(from_apigw_check=False)

    def test_request_with_get_method(self):
        """测试 GET 请求"""
        response = self.client.request(url="http://www.example.com", method="GET", data={"key": "value"})
        assert response is not None

    def test_request_with_post_method(self):
        """测试 POST 请求"""
        response = self.client.request(url="http://www.example.com", method="POST", data={"key": "value"})
        assert response is not None

    def test_request_with_lowercase_method(self):
        """测试小写方法名会被转换为大写"""
        response = self.client.request(url="http://www.example.com", method="get", data={"key": "value"})
        assert response is not None

    def test_request_with_custom_headers(self):
        """测试自定义headers"""
        custom_headers = {"X-Custom-Header": "test_value"}
        response = self.client.request(
            url="http://www.example.com",
            method="GET",
            data={},
            headers=custom_headers,
        )
        assert response is not None

    def test_request_with_custom_timeout(self):
        """测试自定义timeout"""
        response = self.client.request(url="http://www.example.com", method="GET", data={}, timeout=60)
        assert response is not None

    @patch.object(UniformAPIClient, "check_url_from_apigw")
    def test_request_url_apigw_check_fail(self, mock_check):
        """测试URL API网关检查失败"""
        mock_check.return_value = False
        client = UniformAPIClient(from_apigw_check=True)

        with pytest.raises(APIRequestError) as exc_info:
            client.request(url="http://invalid.com", method="GET", data={})
        assert "check url from apigw fail" in str(exc_info.value)

    def test_category_list_response_schema_validation(self):
        """测试分类列表响应Schema验证"""
        # 有效数据
        valid_data = [{"id": "cat1", "name": "Category 1"}, {"id": "cat2", "name": "Category 2"}]
        self.client.validate_response_data(valid_data, self.client.UNIFORM_API_CATEGORY_LIST_RESPONSE_DATA_SCHEMA)

        # 无效数据（缺少必需字段）
        with pytest.raises(ValidationError):
            invalid_data = [{"id": "cat1"}]  # 缺少 name
            self.client.validate_response_data(invalid_data, self.client.UNIFORM_API_CATEGORY_LIST_RESPONSE_DATA_SCHEMA)

    @patch.object(settings, "BK_APP_CODE", "default_app")
    @patch.object(settings, "BK_APP_SECRET", "default_secret")
    def test_request_with_default_headers(self):
        """测试使用默认headers"""
        client = UniformAPIClient(from_apigw_check=False)
        response = client.request(
            url="http://www.example.com",
            method="GET",
            data={},
            headers=None,  # 使用默认headers
            username="test_user",
        )
        assert response is not None

    def test_gen_default_apigw_header(self):
        """测试生成默认API网关请求头"""
        headers = self.client.gen_default_apigw_header(
            app_code="test_app", app_secret="test_secret", username="test_user"
        )
        assert "X-Bkapi-Authorization" in headers

    def test_method_not_supported(self):
        """测试不支持的方法"""
        with pytest.raises(APIRequestError) as exc_info:
            self.client.request(url="http://www.example.com", method="DELETE", data={})
        assert "method not supported" in str(exc_info.value)

    def test_list_response_schema_validation_missing_apis(self):
        """测试列表响应Schema验证 - 缺少apis字段"""
        with pytest.raises(ValidationError):
            invalid_data = {"total": 10}  # 缺少 apis
            self.client.validate_response_data(invalid_data, self.client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)

    def test_list_response_schema_validation_valid(self):
        """测试列表响应Schema验证 - 有效数据"""
        valid_data = {
            "total": 1,
            "apis": [{"id": "api1", "name": "API 1", "meta_url": "http://example.com/meta"}],
        }
        self.client.validate_response_data(valid_data, self.client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)

    def test_meta_response_schema_validation_valid(self):
        """测试元数据响应Schema验证 - 有效数据"""
        valid_data = {
            "id": "api1",
            "name": "API 1",
            "url": "http://example.com/api",
            "methods": ["GET", "POST"],
            "inputs": [{"name": "param1", "key": "param1"}],
        }
        self.client.validate_response_data(valid_data, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    def test_meta_response_schema_validation_invalid_method(self):
        """测试元数据响应Schema验证 - 无效方法"""
        with pytest.raises(ValidationError):
            invalid_data = {
                "id": "api1",
                "name": "API 1",
                "url": "http://example.com/api",
                "methods": ["DELETE"],  # 不支持的方法
                "inputs": [{"name": "param1", "key": "param1"}],
            }
            self.client.validate_response_data(invalid_data, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    def test_support_methods(self):
        """测试支持的方法常量"""
        assert "GET" in self.client.SUPPORT_METHODS
        assert "POST" in self.client.SUPPORT_METHODS
        assert "DELETE" not in self.client.SUPPORT_METHODS

    def test_timeout_constant(self):
        """测试超时常量"""
        assert self.client.TIMEOUT == 30
