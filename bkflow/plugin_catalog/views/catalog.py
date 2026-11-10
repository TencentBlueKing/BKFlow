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

from rest_framework.response import Response

from bkflow.plugin_catalog.models import SpacePluginCatalogEntry
from bkflow.plugin_catalog.permissions import PLUGIN_CATALOG_ADMIN_PERMISSIONS
from bkflow.plugin_catalog.serializers.catalog import (
    BatchCategorySerializer,
    BatchCleanSerializer,
    BatchStatusSerializer,
    DisableConfigSerializer,
    EntryListQuerySerializer,
    EntryStatusSerializer,
    EntryUpdateSerializer,
    PluginDetailQuerySerializer,
    ReferenceListQuerySerializer,
    SpaceIdQuerySerializer,
    SuggestDirectoryQuerySerializer,
)
from bkflow.plugin_catalog.services.catalog_service import PluginCatalogService
from bkflow.plugin_catalog.services.query_service import PluginCatalogQueryService
from bkflow.plugin_catalog.services.reference_service import PluginReferenceService
from bkflow.space.tenant import TenantScopeMixin
from bkflow.utils.views import SimpleGenericViewSet

logger = logging.getLogger("root")


def _request_id(request):
    """取请求链路 ID，便于变更记录与网关/前端日志对齐；未启用时返回空串。"""
    return getattr(request, "request_id", "") or ""


class PluginCatalogAdminViewSet(TenantScopeMixin, SimpleGenericViewSet):
    """
    插件列表管理：状态 Tab 查询与计数、单条编辑、状态流转、批量操作、空间推荐位维护。

    不经过 DRF router 自动注册（需要 `POST plugins/<id>/` 这种无子路径的 detail 写接口，
    router 默认只给 PUT/PATCH），改为在 urls.py 手工映射 method -> action，详见该文件注释。
    手工映射时 DRF 不会自动注入 `basename`，这里显式声明为类属性，避免
    `SpaceSuperuserPermission.has_permission` 访问 `view.basename` 时报 AttributeError。
    """

    permission_classes = PLUGIN_CATALOG_ADMIN_PERMISSIONS
    queryset = SpacePluginCatalogEntry.objects.all()
    basename = None

    # --------------------------------------------------------- 列表 / summary ----

    def list(self, request, *args, **kwargs):
        ser = EntryListQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        common_filters = {
            "space_id": data["space_id"],
            "directory_id": data["directory_id"],
            "plugin_type": data["plugin_type"],
            "source_key": data["source_key"],
            "keyword": data["keyword"],
        }
        result = PluginCatalogQueryService.list_entries(
            status=data["status"], ordering=data["ordering"], page=data["page"], page_size=data["page_size"], **common_filters
        )
        result["status_counts"] = PluginCatalogQueryService.get_status_counts(**common_filters)
        return Response(result)

    def summary(self, request, *args, **kwargs):
        ser = SpaceIdQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        return Response(PluginCatalogQueryService.get_summary(space_id=ser.validated_data["space_id"]))

    # --------------------------------------------------- 单条编辑 / 状态流转(01/02/03) ----

    def update_entry(self, request, pk=None):
        ser = EntryUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        extra = {}
        if "directory_id" in request.data:
            extra["directory_id"] = data.get("directory_id")
        if "recommended" in data:
            extra["recommended"] = data["recommended"]
        entry = PluginCatalogService.update_entry(
            space_id=data["space_id"],
            entry_id=pk,
            operator=request.user.username,
            request_id=_request_id(request),
            **extra,
        )
        return Response(PluginCatalogQueryService.serialize_entries(data["space_id"], [entry])[0])

    def status(self, request, pk=None):
        ser = EntryStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        extra = {}
        if "target_directory_id" in request.data:
            extra["target_directory_id"] = data.get("target_directory_id")
        entry = PluginCatalogService.transition_status(
            space_id=data["space_id"],
            entry_id=pk,
            target_status=data["status"],
            operator=request.user.username,
            disable_config=data.get("disable_config"),
            offline_reason=data.get("offline_reason", ""),
            replace_plugin_id=data.get("replace_plugin_id"),
            request_id=_request_id(request),
            **extra,
        )
        return Response(PluginCatalogQueryService.serialize_entries(data["space_id"], [entry])[0])

    def suggest_directory(self, request, pk=None):
        ser = SuggestDirectoryQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        return Response(
            PluginCatalogService.suggest_restore_directory(space_id=ser.validated_data["space_id"], entry_id=pk)
        )

    def plugin_detail(self, request, pk=None):
        """07 · 基本信息 + 引用统计 + 首页引用列表（一次性返回，避免详情侧滑二次请求）。"""
        ser = PluginDetailQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        return Response(PluginReferenceService.get_plugin_detail(space_id=ser.validated_data["space_id"], entry_id=pk))

    def references(self, request, pk=None):
        """07 · 当前引用流程列表（供 Tab 2 的筛选/翻页）。"""
        ser = ReferenceListQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = PluginReferenceService.list_references(
            space_id=data["space_id"],
            entry_id=pk,
            scope=data["scope"],
            keyword=data.get("keyword"),
            page=data["page"],
            page_size=data["page_size"],
        )
        return Response(result)

    def disable_config(self, request, pk=None):
        ser = DisableConfigSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        entry = PluginCatalogService.update_disable_config(
            space_id=data["space_id"],
            entry_id=pk,
            disable_config=data["disable_config"],
            operator=request.user.username,
            request_id=_request_id(request),
        )
        return Response(PluginCatalogQueryService.serialize_entries(data["space_id"], [entry])[0])

    # ------------------------------------------------------------------- 批量操作 ----

    def batch_category(self, request, *args, **kwargs):
        ser = BatchCategorySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = PluginCatalogService.batch_category(
            space_id=data["space_id"],
            ids=data["ids"],
            directory_id=data.get("directory_id"),
            operator=request.user.username,
            request_id=_request_id(request),
        )
        return Response(result)

    def batch_status(self, request, *args, **kwargs):
        ser = BatchStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = PluginCatalogService.batch_status(
            space_id=data["space_id"],
            ids=data["ids"],
            status=data["status"],
            target_directory_id=data.get("target_directory_id"),
            items=data.get("items"),
            operator=request.user.username,
            request_id=_request_id(request),
        )
        return Response(result)

    def batch_clean(self, request, *args, **kwargs):
        ser = BatchCleanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = PluginCatalogService.batch_clean(
            space_id=data["space_id"],
            ids=data["ids"],
            operator=request.user.username,
            request_id=_request_id(request),
        )
        return Response(result)

    # ----------------------------------------------------------------------- 推荐(05) ----

    def recommend_list(self, request, *args, **kwargs):
        ser = SpaceIdQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        return Response(PluginCatalogService.list_recommend(space_id=ser.validated_data["space_id"]))

    def recommend_cancel(self, request, pk=None):
        ser = SpaceIdQuerySerializer(data=request.data or request.query_params)
        ser.is_valid(raise_exception=True)
        space_id = ser.validated_data["space_id"]
        entry = PluginCatalogService.cancel_recommend(
            space_id=space_id,
            entry_id=pk,
            operator=request.user.username,
            request_id=_request_id(request),
        )
        return Response(PluginCatalogQueryService.serialize_entries(space_id, [entry])[0])
