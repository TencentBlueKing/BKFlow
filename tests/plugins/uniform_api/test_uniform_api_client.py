# -*- coding: utf-8 -*-
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
from django.conf import settings

from bkflow.exceptions import APIRequestError, ValidationError
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.utils.api_client import HttpRequestResult


class TestUniformAPIClient:
    def setup_method(self, method):
        self.client = UniformAPIClient()

    def test_method_not_allowed(self):
        with pytest.raises(APIRequestError):
            self.client.request(method="PUT", url="http://www.example.com", data={})

    def test_request_check_url_from_apigw(self, monkeypatch):
        monkeypatch.setattr(settings, "SKIP_APIGW_CHECK", False)
        # 跳过配置检查
        client = UniformAPIClient(from_apigw_check=False)
        response = client.request(method="GET", url="http://www.example.com", data={})
        assert isinstance(response, HttpRequestResult)

        # 配置检查且未配置正则
        with pytest.raises(APIRequestError):
            self.client.request(method="GET", url="http://www.example.com", data={})

        # 配置检查且配置正则
        monkeypatch.setattr(settings, "BK_APIGW_NETLOC_PATTERN", "^(.*?)www.example.com")
        response = self.client.request(method="GET", url="http://www.example.com", data={})
        assert isinstance(response, HttpRequestResult)

    def test_list_response_schema_validation(self):
        # 不符合格式的响应
        with pytest.raises(ValidationError):
            # 缺少 total 字段
            invalid_instance = {
                "apis": [
                    {
                        "id": "api1",
                        "name": "test",
                        "meta_url": "http://www.example.com",
                    }
                ]
            }
            self.client.validate_response_data(invalid_instance, self.client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)

        # 符合格式的响应
        valid_instance = {
            "total": 1,
            "apis": [
                {
                    "id": "api1",
                    "name": "test",
                    "meta_url": "http://www.example.com",
                }
            ],
        }
        self.client.validate_response_data(valid_instance, self.client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)

    def test_meta_response_schema_validation(self):
        # 不符合格式的响应
        with pytest.raises(ValidationError):
            # method 不符合枚举类型
            invalid_instance = {
                "id": "api1",
                "name": "test",
                "url": "http://www.example.com",
                "methods": ["GET", "POST", "PUT"],
                "inputs": [{"name": "test", "key": "test", "required": True, "type": "string"}],
            }
            self.client.validate_response_data(invalid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

        # 符合格式的响应
        valid_instance = {
            "id": "api1",
            "name": "test",
            "url": "http://www.example.com",
            "methods": ["GET", "POST"],
            "inputs": [{"name": "test", "key": "test", "required": True, "type": "string"}],
        }
        self.client.validate_response_data(valid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)
