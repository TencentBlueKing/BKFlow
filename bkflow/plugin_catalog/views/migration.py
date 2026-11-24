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
from rest_framework.response import Response

from bkflow.plugin.permissions import PluginSpaceSuperuserPermission, PluginTokenPermissions
from bkflow.plugin_catalog.serializers.catalog import SpaceIdQuerySerializer
from bkflow.plugin_catalog.services.migration_service import PluginCatalogMigrationService
from bkflow.space.tenant import TenantScopeMixin
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import SimpleGenericViewSet


class PluginCatalogMigrationViewSet(TenantScopeMixin, SimpleGenericViewSet):
    """画布侧只读查询空间是否已启用插件目录。

    与空间配置页的 4.1 `plugin_catalog_migration`（管理员/空间管理员权限）不同，
    本接口面向画布前端的普通编排用户，权限沿用画布侧 picker/node 的组合：
    `AdminPermission | PluginSpaceSuperuserPermission | PluginTokenPermissions`，
    即持有效 BKFLOW_TOKEN 即可读取。

    仅提供只读状态查询，不提供任何触发迁移的入口（迁移仍只有运维命令一条通道）。
    """

    permission_classes = [AdminPermission | PluginSpaceSuperuserPermission | PluginTokenPermissions]
    basename = None

    def status(self, request, *args, **kwargs):
        ser = SpaceIdQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        space_id = ser.validated_data["space_id"]
        # 与 4.1 空间配置接口返回完全一致的内容（ready/migrated_at/migrated_by/legacy_snapshot）
        return Response({"space_id": space_id, **PluginCatalogMigrationService.get_status_view(space_id)})
