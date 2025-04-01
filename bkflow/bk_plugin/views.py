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

from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response

import env
from bkflow.bk_plugin.models import AuthStatus, BKPlugin, BKPluginAuthorization
from bkflow.bk_plugin.permissions import BKPluginManagerPermission
from bkflow.bk_plugin.serializer import (
    AuthListSerializer,
    BKPluginAuthSerializer,
    BKPluginQuerySerializer,
    BKPluginSerializer,
)
from bkflow.constants import ALL_SPACE, WHITE_LIST
from bkflow.exceptions import ValidationError
from bkflow.utils.mixins import BKFLOWDefaultPagination
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import ReadOnlyViewSet, SimpleGenericViewSet

logger = logging.getLogger("root")


class BKPluginManagerViewSet(ReadOnlyViewSet, mixins.UpdateModelMixin):
    queryset = BKPluginAuthorization.objects.all()
    serializer_class = BKPluginAuthSerializer
    pagination_class = BKFLOWDefaultPagination
    permission_classes = [AdminPermission | BKPluginManagerPermission]
    lookup_field = "code"

    def list(self, request, *args, **kwargs):
        plugins = BKPlugin.objects.get_plugin_by_manager(request.user.username)
        paged_plugins = self.pagination_class().paginate_queryset(plugins, request)
        authorizations = self.get_queryset().filter(code__in=[p.code for p in paged_plugins])
        authorization_dict = {auth.code: auth for auth in authorizations}
        paged_data = [
            {
                "code": plugin.code,
                "name": plugin.name,
                "managers": plugin.managers,
                **(
                    {
                        "status": authorization.status,
                        "config": authorization.config,
                        "operator": authorization.operator,
                        "authorized_time": authorization.authorized_time,
                    }
                    if (authorization := authorization_dict.get(plugin.code))
                    else {
                        "status": AuthStatus.unauthorized,
                        "config": {WHITE_LIST: [ALL_SPACE]},
                        "operator": "",
                        "authorized_time": "",
                    }
                ),
            }
            for plugin in paged_plugins
        ]
        serializer = AuthListSerializer(data=paged_data, many=True)
        serializer.is_valid()
        return Response({"result": True, "message": None, "data": {"count": len(plugins), "plugins": serializer.data}})

    def update(self, request, *args, **kwargs):
        code = kwargs["code"]
        authorization, _ = self.get_queryset().get_or_create(code=code)
        ser = self.get_serializer(authorization, data=request.data, partial=True)
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
        tag = ser.validated_data["tag"]
        space_id = ser.validated_data["space_id"]
        plugins_queryset = self.get_queryset().filter(tag=int(tag))
        if env.USE_BK_PLUGIN_AUTHORIZATION:
            authorized_codes = BKPluginAuthorization.objects.get_codes_by_space_id(int(space_id))
            plugins_queryset = plugins_queryset.filter(code__in=authorized_codes)
        paged_data = self.pagination_class().paginate_queryset(plugins_queryset, request)
        serializer = self.get_serializer(paged_data, many=True)
        return Response(
            {"result": True, "message": None, "data": {"count": len(plugins_queryset), "plugins": serializer.data}}
        )

    @action(detail=False, methods=["GET"], url_path="is_manager", pagination_class=None)
    def is_manager(self, request):
        return Response(self.get_queryset().filter(managers__contains=request.user.username).exists())
