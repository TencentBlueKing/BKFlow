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
from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    UniformApiConfig,
    UniformAPIConfigHandler,
)
from bkflow.utils.api_client import HttpRequestResult

from .utils import check_resource_token


class UniformAPIBaseSerializer(serializers.Serializer):
    template_id = serializers.IntegerField(required=False)
    task_id = serializers.CharField(required=False)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("template_id") and not attrs.get("task_id"):
            raise ValidationError("template_id 和 task_id 至少有一个")
        return super().validate(attrs)


class UniformAPICategorySerializer(UniformAPIBaseSerializer):
    scope_type = serializers.CharField(required=False)
    scope_value = serializers.CharField(required=False)
    key = serializers.CharField(required=False)
    api_name = serializers.CharField(required=False)


class UniformAPIListSerializer(UniformAPIBaseSerializer):
    limit = serializers.IntegerField(required=False, default=50)
    offset = serializers.IntegerField(required=False, default=0)
    scope_type = serializers.CharField(required=False)
    scope_value = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    key = serializers.CharField(required=False)
    api_name = serializers.CharField(required=False)


class UniformAPIMetaSerializer(UniformAPIBaseSerializer):
    scope_type = serializers.CharField(required=False)
    scope_value = serializers.CharField(required=False)
    meta_url = serializers.CharField(required=True)


def _get_api_credential(space_id: int, template_id: int = None, task_id: int = None) -> dict:
    """获取API凭证.

    :param space_id: 空间ID
    :param template_id: 模板ID
    :param task_id: 任务ID
    :return: API凭证
    """
    from bkflow.space.models import Credential, SpaceConfig
    from bkflow.task.models import TaskInstance
    from bkflow.template.models import Template

    # 校验 space_id template_id task_id 的正确性
    if template_id:
        template = Template.objects.filter(id=template_id, space_id=space_id).first()
        if not template:
            raise ValidationError(f"对应 space_id: {space_id} template_id: {template_id} 不存在")

        scope_type, scope_value = template.scope_type, template.scope_value
    else:
        task = TaskInstance.objects.filter(id=task_id, space_id=space_id).first()
        if not task:
            raise ValidationError(f"对应 space_id: {space_id} task_id: {task_id} 不存在")
        scope_type, scope_value = task.scope_type, task.scope_value

    scope = f"{scope_type}_{scope_value}" if scope_type and scope_value else None

    api_credential_config = SpaceConfig.get_config(
        space_id=space_id, config_name=ApiGatewayCredentialConfig.name, scope=scope
    )

    if not api_credential_config:
        raise ValidationError("不存在凭证配置")

    credential = Credential.objects.filter(space_id=space_id, name=api_credential_config)
    if not credential.exists():
        raise ValidationError(f"对应凭证 {api_credential_config} 不存在")

    return credential.first().content


def _get_space_uniform_api_list_info(
    space_id: int, request_data: dict, config_key: str, username: str, template_id: int = None, task_id: int = None
):
    from bkflow.space.models import SpaceConfig

    uniform_api_config = SpaceConfig.get_config(space_id=space_id, config_name=UniformApiConfig.name)
    if not uniform_api_config:
        raise ValidationError("接入平台未注册统一API, 请联系对应接入平台管理员")
    client = UniformAPIClient()
    uniform_api_config = UniformAPIConfigHandler(uniform_api_config).handle()
    # 弹出此参数避免透传
    api_name = request_data.pop("api_name", UniformApiConfig.Keys.DEFAULT_API_KEY.value)
    url = uniform_api_config.api.get(api_name, {}).get(config_key)
    if not url:
        raise ValidationError("对应API未配置, 请联系对应接入平台管理员")
    # 根据凭证注入请求头
    credential_content = _get_api_credential(space_id=space_id, template_id=template_id, task_id=task_id)
    headers = client.gen_default_apigw_header(
        app_code=credential_content["bk_app_code"], app_secret=credential_content["bk_app_secret"], username=username
    )
    request_result: HttpRequestResult = client.request(
        url=url, method="GET", data=request_data, headers=headers, username=username
    )
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
@check_resource_token
def get_space_uniform_api_category_list(request, space_id):
    """
    获取统一API列表
    """
    serializer = UniformAPICategorySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    api_category_key = UniformApiConfig.Keys.API_CATEGORIES.value
    username = request.user.username
    return _get_space_uniform_api_list_info(
        space_id,
        data,
        api_category_key,
        username,
        template_id=data.get("template_id"),
        task_id=data.get("task_id"),
    )


@swagger_auto_schema(methods=["GET"], query_serializer=UniformAPIListSerializer)
@api_view(["GET"])
@query_response_handler
@check_resource_token
def get_space_uniform_api_list(request, space_id):
    """
    获取统一API列表
    """
    serializer = UniformAPIListSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    meta_apis_key = UniformApiConfig.Keys.META_APIS.value
    username = request.user.username
    return _get_space_uniform_api_list_info(
        space_id,
        data,
        meta_apis_key,
        username,
        template_id=data.get("template_id"),
        task_id=data.get("task_id"),
    )


@swagger_auto_schema(methods=["GET"], query_serializer=UniformAPIMetaSerializer)
@api_view(["GET"])
@query_response_handler
@check_resource_token
def get_space_uniform_api_meta(requests, space_id):
    """
    获取统一API元数据
    """
    serializer = UniformAPIMetaSerializer(data=requests.query_params)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    meta_url = data.pop("meta_url")
    username = requests.user.username

    client = UniformAPIClient()
    credential_content = _get_api_credential(
        space_id=space_id,
        template_id=data.get("template_id"),
        task_id=data.get("task_id"),
    )
    headers = client.gen_default_apigw_header(
        app_code=credential_content["bk_app_code"], app_secret=credential_content["bk_app_secret"], username=username
    )
    request_result: HttpRequestResult = client.request(
        url=meta_url, method="GET", data=data, headers=headers, username=username
    )
    if request_result.result is False:
        raise APIResponseError(f"请求统一API元数据失败: {request_result.message}")
    client.validate_response_data(
        request_result.json_resp.get("data", {}), client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA
    )
    return request_result.json_resp["data"]
