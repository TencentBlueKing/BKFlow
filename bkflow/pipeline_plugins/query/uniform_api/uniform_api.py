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
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers
from rest_framework.decorators import api_view

from bkflow.exceptions import APIResponseError, ValidationError
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.pipeline_plugins.query.utils import query_response_handler
from bkflow.space.configs import UniformApiConfig
from bkflow.space.models import SpaceConfig
from bkflow.utils.api_client import HttpRequestResult


class UniformAPICategorySerializer(serializers.Serializer):
    scope_type = serializers.CharField(required=False)
    scope_value = serializers.CharField(required=False)
    key = serializers.CharField(required=True)


class UniformAPIListSerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, default=50)
    offset = serializers.IntegerField(required=False, default=0)
    scope_type = serializers.CharField(required=False)
    scope_value = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    key = serializers.CharField(required=True)


class UniformAPIMetaSerializer(serializers.Serializer):
    scope_type = serializers.CharField(required=False)
    scope_value = serializers.CharField(required=False)
    meta_url = serializers.CharField(required=True)


def _get_space_uniform_api_list_info(space_id, request_data, config_key):
    uniform_api_configs = SpaceConfig.get_config(space_id=space_id, config_name=UniformApiConfig.name)
    if not uniform_api_configs:
        raise ValidationError("接入平台未注册统一API, 请联系对应接入平台管理员")
    client = UniformAPIClient()
    if uniform_api_configs.get("api"):
        # 新协议多一层 api
        api_config = uniform_api_configs.get("api").get(request_data.get("key"), None)
        if not api_config:
            raise ValidationError("对应统一API未配置")
        url = api_config[config_key]
    else:
        url = uniform_api_configs[config_key]
        # 旧协议直接获取
    request_result: HttpRequestResult = client.request(url=url, method="GET", data=request_data)
    if not request_result.result:
        raise APIResponseError(f"请求统一API列表失败: {request_result.message}")
    response_schema = (
        client.UNIFORM_API_CATEGORY_LIST_RESPONSE_DATA_SCHEMA
        if config_key == UniformApiConfig.Keys.API_CATEGORIES.value
        else client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA
    )
    client.validate_response_data(request_result.json_resp.get("data", {}), response_schema)
    return request_result.json_resp["data"]


@swagger_auto_schema(methods=["GET"], query_serializer=UniformAPICategorySerializer)
@api_view(["GET"])
@query_response_handler
def get_space_uniform_api_category_list(request, space_id):
    """
    获取统一API列表
    """
    serializer = UniformAPICategorySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    api_category_key = UniformApiConfig.Keys.API_CATEGORIES.value
    return _get_space_uniform_api_list_info(space_id, data, api_category_key)


@swagger_auto_schema(methods=["GET"], query_serializer=UniformAPIListSerializer)
@api_view(["GET"])
@query_response_handler
def get_space_uniform_api_list(request, space_id):
    """
    获取统一API列表
    """
    serializer = UniformAPIListSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    meta_apis_key = UniformApiConfig.Keys.META_APIS.value
    return _get_space_uniform_api_list_info(space_id, data, meta_apis_key)


@swagger_auto_schema(methods=["GET"], query_serializer=UniformAPIMetaSerializer)
@api_view(["GET"])
@query_response_handler
def get_space_uniform_api_meta(requests, space_id):
    """
    获取统一API元数据
    """
    serializer = UniformAPIMetaSerializer(data=requests.query_params)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    meta_url = data.pop("meta_url")
    client = UniformAPIClient()
    request_result: HttpRequestResult = client.request(url=meta_url, method="GET", data=data)
    if request_result.result is False:
        raise APIResponseError(f"请求统一API元数据失败: {request_result.message}")
    client.validate_response_data(
        request_result.json_resp.get("data", {}), client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA
    )
    return request_result.json_resp["data"]
