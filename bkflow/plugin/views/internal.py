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
from rest_framework import serializers
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

    @action(methods=["POST"], detail=False)
    def build_open_plugin_snapshots(self, request):
        """为 Engine 创建/回填任务构建开放插件引用快照和 schema 快照。"""
        data = request.data or {}
        if data.get("space_id") is None:
            return Response(exception=True, data={"detail": "space_id is required"})
        space_id = int(data["space_id"])
        pipeline_tree = data.get("pipeline_tree") or {}
        snapshot_extra = {
            OpenPluginSnapshotService.REFERENCE_SNAPSHOT_KEY: data.get("plugin_reference_snapshot") or [],
            OpenPluginSnapshotService.SCHEMA_SNAPSHOT_KEY: data.get("plugin_schema_snapshot") or {},
        }
        username = data.get("username")
        scope_type = data.get("scope_type")
        scope_id = data.get("scope_value")
        mode = data.get("mode") or "prepare"
        if mode not in ("prepare", "backfill"):
            return Response(exception=True, data={"detail": "mode must be prepare or backfill"})

        try:
            if mode == "backfill":
                existing_ref = OpenPluginSnapshotService.get_reference_snapshot(snapshot_extra)
                existing_schema = OpenPluginSnapshotService.get_schema_snapshot(snapshot_extra)
                if existing_ref and existing_schema:
                    return Response(
                        {
                            "reference_snapshot": existing_ref,
                            "schema_snapshot": existing_schema,
                            "changed": False,
                        }
                    )
                merged, changed = OpenPluginSnapshotService.backfill_extra_info(
                    space_id=space_id,
                    pipeline_tree=pipeline_tree,
                    extra_info=snapshot_extra,
                    username=username,
                    scope_type=scope_type,
                    scope_id=scope_id,
                )
            else:
                merged = OpenPluginSnapshotService.prepare_task_extra_info(
                    space_id=space_id,
                    pipeline_tree=pipeline_tree,
                    extra_info=snapshot_extra,
                    username=username,
                    scope_type=scope_type,
                    scope_id=scope_id,
                )
                changed = merged != dict(snapshot_extra)
        except ValueError as e:
            return Response(exception=True, data={"detail": str(e)})
        except serializers.ValidationError as e:
            return Response(exception=True, data={"detail": _validation_error_message(e)})

        return Response(
            {
                "reference_snapshot": OpenPluginSnapshotService.get_reference_snapshot(merged),
                "schema_snapshot": OpenPluginSnapshotService.get_schema_snapshot(merged),
                "changed": changed,
            }
        )


def _validation_error_message(exc):
    """把 DRF ValidationError 压成前端/Engine 可读的单行 message。"""
    detail = getattr(exc, "detail", None)
    if isinstance(detail, list) and detail:
        return str(detail[0])
    if isinstance(detail, dict) and detail:
        first = next(iter(detail.values()))
        if isinstance(first, list) and first:
            return str(first[0])
        return str(first)
    if detail is not None:
        return str(detail)
    return str(exc)
