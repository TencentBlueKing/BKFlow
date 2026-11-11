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
from bkflow.plugin_catalog.serializers.directory import (
    AiClassifySerializer,
    ExecuteDeleteSerializer,
    ManageSaveSerializer,
    PreviewDeleteSerializer,
    SpaceIdQuerySerializer,
)
from bkflow.plugin_catalog.services.directory_service import DirectoryService
from bkflow.space.tenant import TenantScopeMixin
from bkflow.utils.views import SimpleGenericViewSet

logger = logging.getLogger("root")


def _request_id(request):
    """取请求链路 ID，便于变更记录与网关/前端日志对齐；未启用时返回空串。"""
    return getattr(request, "request_id", "") or ""


class DirectoryManageViewSet(TenantScopeMixin, SimpleGenericViewSet):
    """目录批量管理：整页编辑副本模式下的目录树维护、删除预览与执行、AI 分类建议。"""

    permission_classes = PLUGIN_CATALOG_ADMIN_PERMISSIONS

    @swagger_auto_schema(method="get", operation_summary="整页目录数据", query_serializer=SpaceIdQuerySerializer)
    @action(detail=False, methods=["GET"], url_path="manage_data")
    def manage_data(self, request, *args, **kwargs):
        ser = SpaceIdQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        return Response(DirectoryService.get_manage_data(space_id=ser.validated_data["space_id"]))

    @swagger_auto_schema(method="post", operation_summary="整页保存目录", request_body=ManageSaveSerializer)
    @action(detail=False, methods=["POST"], url_path="manage_save")
    def manage_save(self, request, *args, **kwargs):
        ser = ManageSaveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = DirectoryService.save_manage_data(
            space_id=data["space_id"],
            directories=data["directories"],
            assignments=data["assignments"],
            deleted_plugin_ids=data["deleted_plugin_ids"],
            expected_revision=data["expected_revision"],
            operator=request.user.username,
            request_id=_request_id(request),
        )
        return Response(result)

    @swagger_auto_schema(method="post", operation_summary="删除目录前的影响预览", request_body=PreviewDeleteSerializer)
    @action(detail=False, methods=["POST"], url_path="preview_delete")
    def preview_delete(self, request, *args, **kwargs):
        ser = PreviewDeleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        return Response(
            DirectoryService.preview_delete(space_id=data["space_id"], directory_id=data["directory_id"])
        )

    @swagger_auto_schema(method="post", operation_summary="执行删除目录", request_body=ExecuteDeleteSerializer)
    @action(detail=False, methods=["POST"], url_path="execute_delete")
    def execute_delete(self, request, *args, **kwargs):
        ser = ExecuteDeleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = DirectoryService.execute_delete(
            space_id=data["space_id"],
            directory_id=data["directory_id"],
            strategy=data.get("strategy"),
            target_directory_id=data.get("target_directory_id"),
            operator=request.user.username,
            request_id=_request_id(request),
        )
        return Response(result)

    @swagger_auto_schema(method="post", operation_summary="AI 智能分类建议", request_body=AiClassifySerializer)
    @action(detail=False, methods=["POST"], url_path="ai_classify")
    def ai_classify(self, request, *args, **kwargs):
        ser = AiClassifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        return Response(
            DirectoryService.ai_classify(
                space_id=data["space_id"], scope=data["scope"], plugin_ids=data["plugin_ids"]
            )
        )

