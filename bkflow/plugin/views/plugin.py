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
import logging

from django.conf import settings
from django_filters import FilterSet
from drf_yasg.utils import swagger_auto_schema
from pipeline.component_framework.models import ComponentModel
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from bkflow.bk_plugin.models import BKPlugin
from bkflow.exceptions import APIResponseError
from bkflow.pipeline_plugins.query.uniform_api.uniform_api import _get_api_credential
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.plugin.models import SpacePluginConfig as SpacePluginConfigModel
from bkflow.plugin.permissions import (
    PluginSpaceSuperuserPermission,
    PluginTokenPermissions,
)
from bkflow.plugin.serializers.comonent import (
    ComponentDetailQuerySerializer,
    ComponentListQuerySerializer,
    ComponentModelDetailSerializer,
    ComponentModelListSerializer,
    PluginType,
    UniformPluginSerializer,
)
from bkflow.plugin.space_plugin_config_parser import SpacePluginConfigParser
from bkflow.space.configs import SpacePluginConfig
from bkflow.space.models import SpaceConfig
from bkflow.utils.mixins import BKFLOWCommonMixin
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import ReadOnlyViewSet

logger = logging.getLogger("root")


class ComponentModelFilter(FilterSet):
    class Meta:
        model = ComponentModel
        fields = ["version"]


class ComponentModelSetViewSet(BKFLOWCommonMixin, ReadOnlyViewSet):
    queryset = ComponentModel.objects.filter(status=True).exclude(code__in=["remote_plugin", "uniform_api"])
    retrieve_queryset = ComponentModel.objects.filter(status=True).order_by("name")
    serializer_class = ComponentModelListSerializer
    retrieve_serializer_class = ComponentModelDetailSerializer
    filterset_class = ComponentModelFilter
    pagination_class = None
    lookup_field = "code"
    permission_classes = [AdminPermission | PluginSpaceSuperuserPermission | PluginTokenPermissions]

    def get_queryset(self):
        queryset = super().get_queryset()

        # 过滤系统配置插件
        space_id = self.request.query_params.get("space_id")
        system_allow_list = SpacePluginConfigModel.objects.get_space_allow_list(space_id)
        space_plugins = set(settings.SPACE_PLUGIN_LIST) - set(system_allow_list)
        if space_plugins:
            queryset = queryset.exclude(code__in=list(space_plugins))

        # 过滤空间配置插件
        scope_type = self.request.query_params.get("scope_type")
        scope_id = self.request.query_params.get("scope_id")
        scope_code = f"{scope_type}_{scope_id}"
        space_plugin_config = SpaceConfig.get_config(space_id=space_id, config_name=SpacePluginConfig.name)
        if space_plugin_config:
            parser = SpacePluginConfigParser(space_plugin_config)
            queryset = parser.get_filtered_plugin_qs(scope_code, queryset)
        return queryset

    @swagger_auto_schema(query_serializer=ComponentListQuerySerializer)
    def list(self, request, *args, **kwargs):
        query_ser = ComponentListQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(query_serializer=ComponentDetailQuerySerializer)
    def retrieve(self, request, *args, **kwargs):
        query_ser = ComponentDetailQuerySerializer(
            data=request.query_params, context={"plugin_code": kwargs[self.lookup_field]}
        )
        query_ser.is_valid(raise_exception=True)
        return super().retrieve(request, *args, **kwargs)


class UniformPluginViewSet(ViewSet):
    @action(detail=False, methods=["get"])
    def get_plugin_detail(self, request, *args, **kwargs):
        serializer = UniformPluginSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        logo_url = ""
        plugin_type = serializer.validated_data.get("plugin_type")
        space_id = serializer.validated_data.get("space_id")
        plugin_code = serializer.validated_data.get("plugin_code")
        if plugin_type == PluginType.COMPONENT.value:
            # 内置插件 需要校验可见性 目前前端直接根据插件code来获取logo
            component_detail_query_serializer = ComponentDetailQuerySerializer(
                data=request.query_params, context={"plugin_code": plugin_code}
            )
            component_detail_query_serializer.is_valid(raise_exception=True)
            plugin = ComponentModel.objects.filter(code=plugin_code)
            if not plugin.exists():
                err_msg = f"Plugin {plugin_code} does not exist"
                return Response(exception=True, data={"detail": err_msg})
        elif plugin_type == PluginType.BLUEKING.value:
            # 蓝鲸插件
            plugin = BKPlugin.objects.filter(code=plugin_code)
            if not plugin.exists():
                err_msg = f"Plugin {plugin_code} does not exist"
                return Response(exception=True, data={"detail": err_msg})
            logo_url = plugin.first().logo_url
        elif plugin_type == PluginType.UNIFORM_API.value:
            # API 插件 需要获取对应的凭证 请求 meta_url
            meta_url = serializer.validated_data.get("meta_url")
            template_id = serializer.validated_data.get("template_id")
            credential = _get_api_credential(space_id=space_id, template_id=template_id)
            client = UniformAPIClient()
            header = client.gen_default_apigw_header(
                app_code=credential["bk_app_code"], app_secret=credential["bk_app_secret"]
            )
            resp = client.request(
                url=meta_url,
                method="GET",
                headers=header,
            )
            if resp.result is False:
                raise APIResponseError(f"请求统一API元数据失败: {resp.message}")
            client.validate_response_data(resp.json_resp.get("data", {}), client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)
            api_data = resp.json_resp["data"]
            logo_url = api_data.get("logo_url", "")
        return Response({"logo_url": logo_url})
