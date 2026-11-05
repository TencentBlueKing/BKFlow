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

from bkflow.plugin.permissions import (
    PluginSpaceSuperuserPermission,
    PluginTokenPermissions,
)
from bkflow.plugin_catalog.serializers.node import (
    PluginStatusesSerializer,
    PluginVersionsQuerySerializer,
    VersionDiffSerializer,
)
from bkflow.plugin_catalog.services.guard_service import PluginCatalogGuardService
from bkflow.plugin_catalog.services.version_diff_service import PluginVersionDiffService
from bkflow.space.tenant import TenantScopeMixin
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import SimpleGenericViewSet

logger = logging.getLogger("root")


class PluginNodeViewSet(TenantScopeMixin, SimpleGenericViewSet):
    """
    节点配置面板相关接口：批量查询插件当前状态（渲染「已停用」提示条）、
    查询插件可选版本列表、计算版本切换/换插件时的参数差异。

    节点配置面板本身属于画布编辑态，权限沿用 10 的画布组合。
    """

    permission_classes = [AdminPermission | PluginSpaceSuperuserPermission | PluginTokenPermissions]

    def statuses(self, request, *args, **kwargs):
        """12 · 批量查询插件当前状态（画布内全部节点引用的插件身份一次性查）。"""
        ser = PluginStatusesSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        results = PluginCatalogGuardService.batch_get_status(
            space_id=data["space_id"], identities=data["items"]
        )
        return Response({"results": results})

    def versions(self, request, *args, **kwargs):
        """13 · 该插件可选版本列表。"""
        ser = PluginVersionsQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = PluginVersionDiffService.list_versions(
            space_id=data["space_id"],
            plugin_type=data["plugin_type"],
            source_key=data.get("source_key"),
            plugin_code=data["plugin_code"],
        )
        return Response(result)

    def version_diff(self, request, *args, **kwargs):
        """13 · 版本切换/换插件的参数差异计算（12 场景③的入参映射复用同一套逻辑）。"""
        ser = VersionDiffSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = PluginVersionDiffService.diff(
            space_id=data["space_id"],
            from_identity=data["from_plugin"],
            to_identity=data["to_plugin"],
            current_inputs=data.get("current_inputs"),
        )
        return Response(result)
