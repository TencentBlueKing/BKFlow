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

import logging
from urllib.parse import parse_qs, urlsplit

from django.core.cache import cache
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers
from rest_framework.decorators import api_view

from bkflow.exceptions import APIResponseError, ValidationError
from bkflow.pipeline_plugins.query.uniform_api.utils import (
    UniformAPIClient,
    resolve_meta_url,
)
from bkflow.pipeline_plugins.query.utils import query_response_handler
from bkflow.plugin.models import OpenPluginCatalogIndex
from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService
from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    UniformAPICatalogMode,
    UniformApiConfig,
    UniformAPIConfigHandler,
)
from bkflow.utils.api_client import HttpRequestResult

from .utils import check_resource_token

logger = logging.getLogger(__name__)
CATALOG_SYNC_DEDUP_SECONDS = 60


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
    meta_url = serializers.CharField(required=False, allow_blank=True)
    meta_url_template = serializers.CharField(required=False, allow_blank=True)
    version = serializers.CharField(required=False, allow_blank=True)
    source_key = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        if not attrs.get("meta_url") and not attrs.get("meta_url_template"):
            raise serializers.ValidationError("meta_url 和 meta_url_template 至少有一个")
        if attrs.get("meta_url_template") and not attrs.get("version"):
            raise serializers.ValidationError("meta_url_template 存在时 version 不能为空")
        if attrs.get("meta_url_template") and not attrs.get("source_key"):
            raise serializers.ValidationError({"source_key": "开放插件详情请求必须指定来源"})
        return attrs


def _get_request_scope(space_id: int, template_id: int = None, task_id: int = None):
    from bkflow.contrib.api.collections.task import TaskComponentClient
    from bkflow.template.models import Template

    if template_id:
        template = Template.objects.filter(id=template_id, space_id=space_id).first()
        if not template:
            raise ValidationError(f"对应 space_id: {space_id} template_id: {template_id} 不存在")

        scope_type, scope_value = template.scope_type, template.scope_value
    else:
        client = TaskComponentClient(space_id=space_id)
        result = client.get_task_detail(task_id=task_id)
        if not result.get("result", False):
            raise ValidationError(f"对应 space_id: {space_id} task_id: {task_id} 不存在")
        scope_type, scope_value = result["data"]["scope_type"], result["data"]["scope_value"]

    return scope_type, scope_value


def _get_api_credential(
    space_id: int,
    template_id: int = None,
    task_id: int = None,
    request_scope=None,
) -> dict:
    """获取API凭证.

    :param space_id: 空间ID
    :param template_id: 模板ID
    :param task_id: 任务ID
    :param request_scope: 已校验的 (scope_type, scope_value)
    :return: API凭证
    """
    from bkflow.space.models import Credential, SpaceConfig

    scope_type, scope_value = request_scope or _get_request_scope(
        space_id=space_id,
        template_id=template_id,
        task_id=task_id,
    )
    scope = f"{scope_type}_{scope_value}" if scope_type and scope_value else "default"

    api_credential_config = SpaceConfig.get_config(
        space_id=space_id, config_name=ApiGatewayCredentialConfig.name, scope=scope
    )

    if not api_credential_config:
        raise ValidationError("不存在凭证配置")

    credential = Credential.objects.filter(space_id=space_id, name=api_credential_config)
    if not credential.exists():
        raise ValidationError(f"对应凭证 {api_credential_config} 不存在")

    return credential.first().content


def _extract_plugin_source(url):
    plugin_sources = parse_qs(urlsplit(url).query).get("plugin_source", [])
    return plugin_sources[-1] if plugin_sources else None


def _attach_source_key(response_data, config_key, source_key):
    if config_key != UniformApiConfig.Keys.META_APIS.value or not isinstance(response_data, dict):
        return response_data

    return {
        **response_data,
        "apis": [
            {**api, "source_key": source_key} if isinstance(api, dict) else api for api in response_data.get("apis", [])
        ],
    }


def _build_cached_catalog_data(plugins, request_data, config_key, plugin_source=None):
    visible_plugins = [
        plugin
        for plugin in plugins
        if plugin.get("status") == OpenPluginCatalogIndex.Status.AVAILABLE
        and plugin.get("enabled") is True
        and (not plugin_source or plugin.get("plugin_source") == plugin_source)
    ]

    if config_key == UniformApiConfig.Keys.API_CATEGORIES.value:
        categories = {
            plugin["group_name"]: plugin.get("group_display_name") or plugin["group_name"]
            for plugin in visible_plugins
            if plugin.get("group_name")
        }
        return [{"id": "all", "name": "全部"}] + [
            {"id": category, "name": categories[category]} for category in sorted(categories)
        ]

    category = request_data.get("category")
    if category and category != "all":
        visible_plugins = [plugin for plugin in visible_plugins if plugin.get("group_name") == category]

    keyword = str(request_data.get("key") or "").strip().casefold()
    if keyword:
        visible_plugins = [
            plugin
            for plugin in visible_plugins
            if any(
                keyword in str(plugin.get(field) or "").casefold()
                for field in ("plugin_id", "plugin_name", "plugin_code")
            )
        ]

    api_list = [
        {
            "id": plugin["plugin_id"],
            "name": plugin["plugin_name"],
            "plugin_source": plugin["plugin_source"],
            "plugin_code": plugin["plugin_code"],
            "wrapper_version": plugin["wrapper_version"],
            "default_version": plugin["default_version"],
            "latest_version": plugin["latest_version"],
            "versions": plugin["versions"],
            "meta_url_template": plugin["meta_url_template"],
            "source_key": plugin["source_key"],
            "category": plugin.get("group_name", ""),
            "category_name": plugin.get("group_display_name") or plugin.get("group_name", ""),
            "description": plugin.get("description", ""),
        }
        for plugin in visible_plugins
    ]
    total = len(api_list)
    offset = max(request_data.get("offset", 0), 0)
    limit = max(request_data.get("limit", 50), 0)
    return {"total": total, "apis": api_list[offset : offset + limit]}


def _request_remote_uniform_api_data(
    space_id,
    request_data,
    config_key,
    username,
    url,
    template_id=None,
    task_id=None,
    request_scope=None,
):
    client = UniformAPIClient()
    credential_kwargs = {
        "space_id": space_id,
        "template_id": template_id,
        "task_id": task_id,
    }
    if request_scope is not None:
        credential_kwargs["request_scope"] = request_scope
    credential_content = _get_api_credential(**credential_kwargs)
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
    response_data = request_result.json_resp.get("data", {})
    client.validate_response_data(response_data, response_schema)
    return response_data


def _dispatch_catalog_sync(space_id, source_key):
    lock_key = "open_plugin_catalog_sync_trigger:{}:{}".format(space_id, source_key)
    try:
        lock_acquired = cache.add(lock_key, True, timeout=CATALOG_SYNC_DEDUP_SECONDS)
    except Exception:
        logger.exception("开放插件目录同步去重锁获取失败: space_id=%s, source_key=%s", space_id, source_key)
        return

    if not lock_acquired:
        return

    try:
        from bkflow.plugin.tasks import sync_open_plugin_catalog_source

        sync_open_plugin_catalog_source.delay(space_id=space_id, source_key=source_key)
    except Exception:
        try:
            cache.delete(lock_key)
        except Exception:
            logger.exception("开放插件目录同步去重锁清理失败: space_id=%s, source_key=%s", space_id, source_key)
        logger.exception("开放插件目录同步任务投递失败: space_id=%s, source_key=%s", space_id, source_key)


def _get_space_uniform_api_list_info(
    space_id: int, request_data: dict, config_key: str, username: str, template_id: int = None, task_id: int = None
):
    from bkflow.space.models import SpaceConfig

    uniform_api_config = SpaceConfig.get_config(space_id=space_id, config_name=UniformApiConfig.name)
    if not uniform_api_config:
        raise ValidationError("接入平台未注册统一API, 请联系对应接入平台管理员")
    uniform_api_config = UniformAPIConfigHandler(uniform_api_config).handle()
    request_data = dict(request_data)
    # 弹出此参数避免透传
    api_name = request_data.pop("api_name", UniformApiConfig.Keys.DEFAULT_API_KEY.value)
    api_entry = uniform_api_config.api.get(api_name)
    url = api_entry.get(config_key) if api_entry else None
    if not url:
        raise ValidationError("对应API未配置, 请联系对应接入平台管理员")

    source_key = api_entry.source_key or api_name

    if api_entry.catalog_mode == UniformAPICatalogMode.REMOTE:
        response_data = _request_remote_uniform_api_data(
            space_id=space_id,
            request_data=request_data,
            config_key=config_key,
            username=username,
            url=url,
            template_id=template_id,
            task_id=task_id,
        )
        return _attach_source_key(response_data, config_key, source_key)

    request_scope = _get_request_scope(space_id=space_id, template_id=template_id, task_id=task_id)
    plugin_source = _extract_plugin_source(url)

    if OpenPluginCatalogService.is_catalog_initialized(
        space_id=space_id,
        source_key=source_key,
        plugin_source=plugin_source,
    ):
        plugins = OpenPluginCatalogService.list_space_plugins(space_id=space_id, source_key=source_key)
        return _build_cached_catalog_data(
            plugins=plugins,
            request_data=request_data,
            config_key=config_key,
            plugin_source=plugin_source,
        )

    if api_entry.catalog_mode == UniformAPICatalogMode.CACHE_ONLY:
        raise ValidationError(
            "开放插件目录缓存未初始化: source_key={}, plugin_source={}".format(source_key, plugin_source or "all")
        )

    response_data = _request_remote_uniform_api_data(
        space_id=space_id,
        request_data=request_data,
        config_key=config_key,
        username=username,
        url=url,
        template_id=template_id,
        task_id=task_id,
        request_scope=request_scope,
    )
    _dispatch_catalog_sync(space_id=space_id, source_key=source_key)
    return _attach_source_key(response_data, config_key, source_key)


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
    meta_url_template = data.pop("meta_url_template", "")
    data.pop("source_key", "")
    meta_url = resolve_meta_url(
        meta_url=data.pop("meta_url", ""),
        meta_url_template=meta_url_template,
        version=data.pop("version", ""),
    )
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
