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

from django_filters.rest_framework import FilterSet
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response

import env
from bkflow.bk_plugin.models import (
    AuthStatus,
    BKPlugin,
    BKPluginAuthorization,
    get_default_config,
)
from bkflow.bk_plugin.permissions import BKPluginManagerPermission
from bkflow.bk_plugin.serializer import (
    AuthListQuerySerializer,
    AuthListSerializer,
    BKPluginAuthSerializer,
    BKPluginQuerySerializer,
    BKPluginSerializer,
)
from bkflow.exceptions import ValidationError
from bkflow.utils.mixins import BKFLOWDefaultPagination
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import ReadOnlyViewSet, SimpleGenericViewSet

logger = logging.getLogger("root")


class BKPluginAuthFilterSet(FilterSet):
    @staticmethod
    def filter_plugins(plugins, query_data):
        filtered_plugins = plugins
        if "code" in query_data:
            filtered_plugins = filtered_plugins.filter(code=query_data["code"])
        if "name" in query_data:
            filtered_plugins = filtered_plugins.filter(name__icontains=query_data["name"])
        if "manager" in query_data:
            filtered_plugins = filtered_plugins.filter(managers__contains=query_data["manager"])
        return filtered_plugins

    @staticmethod
    def filter_authorization(validated_data, query_data):
        filtered_data = validated_data
        if "status" in query_data:
            status_value = query_data["status"]
            filtered_data = [item for item in validated_data if item["status"] == status_value]
        if "status_updator" in query_data:
            updator = query_data["status_updator"]
            # 模糊匹配 (包含查询)
            filtered_data = [item for item in filtered_data if item["status_updator"] == updator]
        return filtered_data


class BKPluginManagerViewSet(ReadOnlyViewSet, mixins.UpdateModelMixin):
    queryset = BKPluginAuthorization.objects.all()
    pagination_class = BKFLOWDefaultPagination
    permission_classes = [AdminPermission | BKPluginManagerPermission]
    lookup_field = "code"

    @swagger_auto_schema(query_serializer=AuthListQuerySerializer)
    def list(self, request, *args, **kwargs):
        query_serializer = AuthListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        plugins = BKPlugin.objects.get_plugin_by_manager(request.user.username)
        plugins = BKPluginAuthFilterSet.filter_plugins(plugins, query_serializer.validated_data)
        authorizations = self.get_queryset().filter(code__in=[p.code for p in plugins])
        authorization_dict = {auth.code: auth for auth in authorizations}
        result_data = [
            {
                "code": plugin.code,
                "name": plugin.name,
                "managers": plugin.managers,
                **(
                    {
                        "status": authorization.status,
                        "config": authorization.config,
                        "status_updator": authorization.status_updator,
                        "status_update_time": authorization.status_update_time,
                    }
                    if (authorization := authorization_dict.get(plugin.code))
                    else {
                        "status": AuthStatus.unauthorized.value,
                        "config": get_default_config(),
                        "status_updator": "",
                        "status_update_time": None,
                    }
                ),
            }
            for plugin in plugins
        ]
        serializer = AuthListSerializer(data=result_data, many=True)
        serializer.is_valid(raise_exception=True)
        if "status" in query_serializer.validated_data or "status_updator" in query_serializer.validated_data:
            result_data = BKPluginAuthFilterSet.filter_authorization(
                serializer.validated_data, query_serializer.validated_data
            )
        paged_plugins = self.pagination_class().paginate_queryset(result_data, request)
        return Response(
            {"result": True, "message": None, "data": {"count": len(result_data), "plugins": paged_plugins}}
        )

    def update(self, request, *args, **kwargs):
        code = kwargs["code"]
        authorization, _ = self.get_queryset().get_or_create(code=code)
        ser = BKPluginAuthSerializer(authorization, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        if "status" in ser.validated_data:
            ser.context.update({"username": request.user.username})
        try:
            ser.save()
        except ValidationError as e:
            return Response({"result": False, "data": None, "message": e.message})
        return Response({"result": True, "message": None, "data": ser.data})


class BKPluginViewSet(SimpleGenericViewSet):
    queryset = BKPlugin.objects.all()
    serializer_class = BKPluginSerializer
    pagination_class = BKFLOWDefaultPagination
    permission_classes = []

    @swagger_auto_schema(query_serializer=BKPluginQuerySerializer)
    def list(self, request):
        ser = BKPluginQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        plugins_queryset = self.get_queryset().filter(tag=ser.validated_data["tag"])
        if env.ENABLE_BK_PLUGIN_AUTHORIZATION:
            authorized_codes = BKPluginAuthorization.objects.get_codes_by_space_id(str(ser.validated_data["space_id"]))
            plugins_queryset = plugins_queryset.filter(code__in=authorized_codes)
        paged_data = self.pagination_class().paginate_queryset(plugins_queryset, request)
        serializer = self.get_serializer(paged_data, many=True)
        return Response(
            {"result": True, "message": None, "data": {"count": len(plugins_queryset), "plugins": serializer.data}}
        )

    @action(detail=False, methods=["GET"], url_path="is_manager", pagination_class=None)
    def is_manager(self, request):
        is_manager = self.get_queryset().filter(managers__contains=request.user.username).exists()
        return Response({"result": True, "message": None, "data": {"is_manager": is_manager}})
