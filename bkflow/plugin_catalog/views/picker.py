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
from bkflow.plugin_catalog.serializers.picker import PluginPickerQuerySerializer
from bkflow.plugin_catalog.services.picker_service import PluginPickerService
from bkflow.space.tenant import TenantScopeMixin
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import SimpleGenericViewSet

logger = logging.getLogger("root")


class PluginPickerViewSet(TenantScopeMixin, SimpleGenericViewSet):
    """
    画布统一选择列表：供流程画布的「选择插件」面板使用。

    权限沿用 bkflow/plugin 模块既有组合（画布编辑态常见是 token 鉴权），
    不为新 app 单独发明权限类，直接复用既有权限类的组合。
    """

    permission_classes = [AdminPermission | PluginSpaceSuperuserPermission | PluginTokenPermissions]

    def list(self, request, *args, **kwargs):
        ser = PluginPickerQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        result = PluginPickerService.list_pickable_plugins(
            space_id=data["space_id"],
            directory_id=data["directory_id"],
            plugin_type=data["plugin_type"],
            keyword=data.get("keyword"),
            ordering=data["ordering"],
            page=data["page"],
            page_size=data["page_size"],
        )
        return Response(result)
