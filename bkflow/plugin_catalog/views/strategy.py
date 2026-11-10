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
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.plugin_catalog.permissions import PLUGIN_CATALOG_ADMIN_PERMISSIONS
from bkflow.plugin_catalog.serializers.strategy import (
    SourceGroupQuerySerializer,
    StrategyQuerySerializer,
    StrategySaveSerializer,
)
from bkflow.plugin_catalog.services.source_group_service import SourceGroupService
from bkflow.plugin_catalog.services.strategy_service import PluginAdmissionStrategyService
from bkflow.space.tenant import TenantScopeMixin
from bkflow.utils.views import SimpleGenericViewSet

logger = logging.getLogger("root")


class StrategyViewSet(TenantScopeMixin, SimpleGenericViewSet):
    """新插件接入策略：查询与保存当前空间的插件接入策略配置。"""

    permission_classes = PLUGIN_CATALOG_ADMIN_PERMISSIONS

    @swagger_auto_schema(operation_summary="查询当前新插件策略", query_serializer=StrategyQuerySerializer)
    def list(self, request, *args, **kwargs):
        ser = StrategyQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        space_id = ser.validated_data["space_id"]
        strategy = PluginAdmissionStrategyService.get_strategy(space_id)
        return Response(strategy or dict(PluginAdmissionStrategyService.Config.default_value))

    @swagger_auto_schema(operation_summary="保存新插件策略", request_body=StrategySaveSerializer)
    def create(self, request, *args, **kwargs):
        ser = StrategySaveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = PluginAdmissionStrategyService.save_strategy(
            space_id=data["space_id"], data=data["strategy"], operator=request.user.username
        )
        return Response(result)

    @swagger_auto_schema(method="get", operation_summary="来源分组列表", query_serializer=SourceGroupQuerySerializer)
    @action(detail=False, methods=["GET"], url_path="sources")
    def sources(self, request, *args, **kwargs):
        ser = SourceGroupQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        groups = SourceGroupService.list_groups(
            space_id=data["space_id"], exclude_directory_id=data.get("exclude_directory_id")
        )
        return Response(groups)
