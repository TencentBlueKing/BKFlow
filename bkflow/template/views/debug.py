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

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.template.debug.serializers import (
    ContextVarSerializer,
    GlobalRunSerializer,
    NodeMockSerializer,
    ResetSerializer,
    StepRunSerializer,
    TemplateIdQuerySerializer,
    TerminateSerializer,
)
from bkflow.template.debug.service import (
    DebugConflictError,
    DebugService,
    DebugStateError,
)
from bkflow.template.permissions import TemplateRelatedResourcePermission
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import SimpleGenericViewSet


def _err(exc, code):
    return Response(exception=True, data={"detail": str(exc)}, status=code)


class DebugViewSet(SimpleGenericViewSet):
    permission_classes = [AdminPermission | SpaceSuperuserPermission | TemplateRelatedResourcePermission]
    # 只读操作既是查看能力，也是调试链路的一部分；写操作需 mock 权限，
    # 因为它们会创建/启动/撤销真实的引擎 TaskInstance。
    DEFAULT_PERMISSION = (
        TemplateRelatedResourcePermission.VIEW_PERMISSION,
        TemplateRelatedResourcePermission.MOCK_PERMISSION,
    )
    PERM_MAPPINGS = {
        "global_run": TemplateRelatedResourcePermission.MOCK_PERMISSION,
        "reset": TemplateRelatedResourcePermission.MOCK_PERMISSION,
        "terminate": TemplateRelatedResourcePermission.MOCK_PERMISSION,
        # step_run/node_mock/context_var 均会变更共享调试态或创建/启动真实引擎任务，需 mock 及以上权限
        "step_run": TemplateRelatedResourcePermission.MOCK_PERMISSION,
        "node_mock": TemplateRelatedResourcePermission.MOCK_PERMISSION,
        "context_var": TemplateRelatedResourcePermission.MOCK_PERMISSION,
    }

    @action(methods=["GET"], detail=False)
    def context(self, request, *args, **kwargs):
        query = TemplateIdQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        svc = DebugService(template_id=query.validated_data["template_id"])
        return Response(svc.build_context_view())

    @action(methods=["GET"], detail=False)
    def input_schema(self, request, *args, **kwargs):
        query = TemplateIdQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        svc = DebugService(template_id=query.validated_data["template_id"])
        return Response({"fields": svc.input_schema()})

    @action(methods=["POST"], detail=False)
    def global_run(self, request, *args, **kwargs):
        ser = GlobalRunSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        svc = DebugService(template_id=ser.validated_data["template_id"])
        try:
            data = svc.global_run(inputs=ser.validated_data["inputs"], operator=request.user.username)
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        except DebugStateError as e:
            return _err(e, status.HTTP_400_BAD_REQUEST)
        return Response(data)

    @action(methods=["POST"], detail=False)
    def reset(self, request, *args, **kwargs):
        ser = ResetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        svc = DebugService(template_id=ser.validated_data["template_id"])
        try:
            reset_ids = svc.reset(node_ids=ser.validated_data.get("node_ids"))
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        return Response({"reset_node_ids": reset_ids})

    @action(methods=["POST"], detail=False)
    def terminate(self, request, *args, **kwargs):
        ser = TerminateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        svc = DebugService(template_id=ser.validated_data["template_id"])
        try:
            data = svc.terminate(node_id=ser.validated_data.get("node_id"), operator=request.user.username)
        except DebugStateError as e:
            return _err(e, status.HTTP_400_BAD_REQUEST)
        return Response(data)

    @action(methods=["GET"], detail=False)
    def history(self, request, *args, **kwargs):
        query = TemplateIdQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        svc = DebugService(template_id=query.validated_data["template_id"])
        return Response(svc.history())

    @action(methods=["POST"], detail=False)
    def reset_impact(self, request, *args, **kwargs):
        query = TemplateIdQuerySerializer(data=request.data)
        query.is_valid(raise_exception=True)
        svc = DebugService(template_id=query.validated_data["template_id"])
        return Response(svc.reset_impact())

    @action(methods=["POST"], detail=False)
    def step_run(self, request, *args, **kwargs):
        ser = StepRunSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        svc = DebugService(template_id=vd["template_id"])
        try:
            data = svc.step_run(
                node_id=vd["node_id"],
                operator=request.user.username,
                mode=vd.get("mode"),
                input_overrides=vd.get("input_overrides"),
                mock_result=vd["mock_result"],
                mock_outputs=vd["mock_outputs"],
                mock_error=vd["mock_error"],
            )
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        except DebugStateError as e:
            detail = e.args[0] if e.args else str(e)
            return Response(exception=True, data={"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)

    @action(methods=["POST"], detail=False)
    def node_mock(self, request, *args, **kwargs):
        ser = NodeMockSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        svc = DebugService(template_id=vd["template_id"])
        try:
            data = svc.node_mock(
                node_id=vd["node_id"],
                enable=vd["enable"],
                mock_result=vd["mock_result"],
                mock_outputs=vd["mock_outputs"],
                mock_error=vd["mock_error"],
            )
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        except DebugStateError as e:
            return _err(e, status.HTTP_400_BAD_REQUEST)
        return Response(data)

    @action(methods=["POST"], detail=False)
    def context_var(self, request, *args, **kwargs):
        ser = ContextVarSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        svc = DebugService(template_id=vd["template_id"])
        try:
            data = svc.set_context_var(key=vd["key"], value=vd["value"])
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        return Response(data)
