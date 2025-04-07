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

import django_filters
from django_filters.filterset import FilterSet
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response

import env
from bkflow.bk_plugin.models import BKPlugin, BKPluginAuthorization
from bkflow.bk_plugin.permissions import BKPluginManagerPermission
from bkflow.bk_plugin.serializer import (
    AuthListQuerySerializer,
    AuthListSerializer,
    BKPluginAuthSerializer,
    BKPluginQuerySerializer,
    BKPluginSerializer,
)
from bkflow.exceptions import ValidationError
from bkflow.utils.mixins import BKFLOWCommonMixin, BKFLOWDefaultPagination
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import SimpleGenericViewSet

logger = logging.getLogger("root")


class BKPluginFilterSet(FilterSet):
    manager = django_filters.CharFilter(field_name="managers", method="filter_by_manager")

    class Meta:
        model = BKPlugin
        fields = {
            "code": ["exact"],
            "name": ["exact", "icontains"],
        }

    @staticmethod
    def filter_by_manager(queryset, name, value):
        return queryset.filter(managers__contains=value)


class BKPluginAuthFilterSet(FilterSet):
    class Meta:
        model = BKPluginAuthorization
        fields = {
            "status": ["exact"],
            "status_updator": ["exact"],
        }


class BKPluginManagerViewSet(BKFLOWCommonMixin, mixins.ListModelMixin, mixins.UpdateModelMixin):
    queryset = BKPlugin.objects.all()
    serializer_class = BKPluginSerializer
    filterset_class = BKPluginFilterSet
    permission_classes = [AdminPermission | BKPluginManagerPermission]
    lookup_field = "code"

    @swagger_auto_schema(query_serializer=AuthListQuerySerializer)
    def list(self, request, *args, **kwargs):
        query_serializer = AuthListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        plugins = self.filter_queryset(self.get_queryset())
        filtered_plugins = plugins.filter(managers__contains=request.user.username)
        filtered_authorization = BKPluginAuthFilterSet(
            query_serializer.validated_data, queryset=BKPluginAuthorization.objects.all()
        ).qs
        authorization_dict = {auth.code: auth for auth in filtered_authorization}
        result_data = []
        for plugin in filtered_plugins:
            status_param = query_serializer.validated_data.get("status")
            updator_param = query_serializer.validated_data.get("status_updator")
            authorization = (
                authorization_dict.get(plugin.code) if authorization_dict.get(plugin.code) else BKPluginAuthorization()
            )
            # 二次过滤，处理没有授权记录的情况
            if (status_param is not None and status_param != authorization.status) or (
                updator_param and updator_param != authorization.status_updator
            ):
                continue
            data = {
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
                ),
            }
            result_data.append(data)

        serializer = AuthListSerializer(data=result_data, many=True)
        serializer.is_valid(raise_exception=True)
        paged_data = self.pagination_class().paginate_queryset(serializer.validated_data, request)
        return Response(
            {"result": True, "message": None, "data": {"count": len(serializer.validated_data), "plugins": paged_data}}
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
