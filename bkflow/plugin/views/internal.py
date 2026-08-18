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

from blueapps.account.decorators import login_exempt
from django.utils.decorators import method_decorator
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.plugin.services.open_plugin_snapshot import OpenPluginSnapshotService
from bkflow.utils.permissions import AdminPermission, AppInternalPermission
from bkflow.utils.views import SimpleGenericViewSet


@method_decorator(login_exempt, name="dispatch")
class PluginInternalViewSet(SimpleGenericViewSet):
    """Engine 调用的开放插件内部接口。"""

    permission_classes = [AdminPermission | AppInternalPermission]

    @action(methods=["POST"], detail=False)
    def validate_open_plugins_for_start(self, request):
        """按快照或 pipeline_tree 做启动前准入预检。"""
        space_id = int(request.data["space_id"])
        OpenPluginSnapshotService.validate_for_start(
            space_id=space_id,
            snapshot=request.data.get("snapshot"),
            pipeline_tree=request.data.get("pipeline_tree"),
        )
        return Response({"validated": True})
