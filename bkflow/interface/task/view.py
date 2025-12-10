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

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.contrib.openapi.serializers import (
    GetTasksStatesBodySerializer,
    RenderConstantsBodySerializer,
    TaskBatchDeleteSerializer,
    TaskEngineAdminSerializer,
)
from bkflow.exceptions import APIRequestError
from bkflow.interface.task.permissions import (
    ScopePermission,
    TaskMockTokenPermission,
    TaskTokenPermission,
)
from bkflow.interface.task.utils import StageConstantHandler, StageJobStateHandler
from bkflow.permission.models import TASK_PERMISSION_TYPE, Token
from bkflow.space.configs import SuperusersConfig
from bkflow.space.models import SpaceConfig
from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.trace import CallFrom, append_attributes, start_trace

logger = logging.getLogger("root")


class TaskInterfaceAdminViewSet(GenericViewSet):
    permission_classes = [AdminPermission | SpaceSuperuserPermission]

    @action(methods=["GET"], detail=False, url_path="get_task_list/(?P<space_id>\\d+)")
    def get_task_list(self, request, space_id):
        client = TaskComponentClient(space_id=space_id)
        result = client.task_list(data={**request.query_params, "space_id": space_id})
        return Response(result)

    @swagger_auto_schema(methods=["post"], operation_description="任务状态查询", request_body=GetTasksStatesBodySerializer)
    @action(methods=["POST"], detail=False, url_path="get_tasks_states")
    def get_tasks_states(self, request, *args, **kwargs):
        ser = GetTasksStatesBodySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        space_id, task_ids = ser.validated_data["space_id"], ser.validated_data["task_ids"]
        client = TaskComponentClient(space_id=space_id)
        result = client.get_tasks_states(data={"task_ids": task_ids, "space_id": space_id})
        return Response(result)

    @swagger_auto_schema(methods=["post"], operation_description="批量删除任务", request_body=TaskBatchDeleteSerializer)
    @action(methods=["POST"], detail=False, url_path="batch_delete_tasks")
    def batch_delete_tasks(self, request, *args, **kwargs):
        ser = TaskBatchDeleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        space_id = ser.validated_data["space_id"]
        client = TaskComponentClient(space_id=space_id)
        data = {
            "task_ids": ser.validated_data["task_ids"],
            "is_full": ser.validated_data["is_full"],
            "space_id": space_id,
        }
        if ser.validated_data["is_full"]:
            data["is_mock"] = ser.validated_data["is_mock"]
        result = client.batch_delete_tasks(data=data)
        return Response(result)


class TaskInterfaceSystemSuperuserViewSet(GenericViewSet):
    permission_classes = [AdminPermission]

    @swagger_auto_schema(methods=["post"], operation_description="触发引擎管理操作", request_body=TaskEngineAdminSerializer)
    @action(methods=["POST"], detail=False, url_path="trigger_engine_admin_action")
    def trigger_engine_admin_action(self, request, *args, **kwargs):
        ser = TaskEngineAdminSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        space_id, instance_id, action, data = (
            ser.validated_data["space_id"],
            ser.validated_data["instance_id"],
            ser.validated_data["action"],
            ser.validated_data["data"],
        )
        client = TaskComponentClient(space_id=space_id)
        result = client.trigger_engine_admin_action(instance_id, action, data=data)
        return Response(result)


class TaskInterfaceViewSet(GenericViewSet):
    OPERATE_ABOVE_ACTIONS = ["operate_node", "operate_task"]
    MOCK_ABOVE_ACTIONS = ["get_task_mock_data"]
    permission_classes = [
        AdminPermission | SpaceSuperuserPermission | TaskTokenPermission | TaskMockTokenPermission | ScopePermission
    ]

    @staticmethod
    def _inject_user_task_auth(request, data):
        if data.get("result", False):
            task_detail = data["data"]
            if request.user.is_superuser or getattr(request, "is_space_superuser", False):
                task_detail["auth"] = TASK_PERMISSION_TYPE
                return

            permissions = Token.objects.filter(
                Q(resource_id=f"{task_detail['scope_type']}_{task_detail['scope_value']}", resource_type="SCOPE")
                | Q(resource_id=task_detail["id"], resource_type="TASK"),
                space_id=task_detail["space_id"],
                user=request.user.username,
                expired_time__gte=timezone.now(),
            ).values_list("permission_type", flat=True)
            task_detail["auth"] = list(set(permissions))

    def get_space_id(self, request):
        request_space_id = request.query_params.get("space_id", None) or request.data.get("space_id", None)
        if request.user.is_superuser or request.user.username in SpaceConfig.get_config(
            request_space_id, SuperusersConfig.name
        ):
            return request_space_id

        try:
            return Token.objects.get(
                token=request.token, expired_time__gte=timezone.now(), user=request.user.username
            ).space_id
        except Token.DoesNotExist:
            logger.exception("find token is not exist")
            raise APIRequestError(
                _("当前token已过期或不存在，token={token}, user={username}").format(
                    token=request.token, username=request.user.username
                )
            )

    @action(methods=["GET"], detail=False, url_path="get_task_detail/(?P<task_id>\\d+)")
    def get_task_detail(self, request, task_id, *args, **kwargs):
        space_id = self.get_space_id(request)
        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        result = client.get_task_detail(task_id)
        self._inject_user_task_auth(request, result)
        return Response(result)

    @action(methods=["GET"], detail=False, url_path="get_task_states/(?P<task_id>\\d+)")
    def get_task_states(self, request, task_id, *args, **kwargs):
        space_id = self.get_space_id(request)
        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        data = {"space_id": space_id}
        result = client.get_task_states(task_id, data=data)
        return Response(result)

    @action(methods=["GET"], detail=False, url_path="get_task_mock_data/(?P<task_id>\\d+)")
    def get_task_mock_data(self, request, task_id, *args, **kwargs):
        space_id = self.get_space_id(request)
        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        result = client.get_task_mock_data(task_id)
        return Response(result)

    @action(methods=["POST"], detail=False, url_path="operate_task/(?P<task_id>\\d+)/(?P<operation>\\w+)")
    def operate_task(self, request, task_id, operation, *args, **kwargs):
        space_id = self.get_space_id(request)

        with start_trace(
            "operate_task_interface", True, space_id=space_id, task_id=task_id, call_from=CallFrom.WEB.value
        ):
            append_attributes({"operation": operation})
            client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
            request.data["operator"] = request.user.username
            result = client.operate_task(task_id, operation, request.data)
            return Response(result)

    @action(methods=["GET"], detail=False, url_path="get_task_node_detail/(?P<task_id>\\w+)/node/(?P<node_id>\\w+)")
    def get_task_node_detail(self, request, task_id, node_id, *args, **kwargs):
        space_id = self.get_space_id(request)
        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        result = client.get_task_node_detail(task_id, node_id, username=request.user.username, data=request.GET)
        return Response(result)

    @action(
        methods=["POST"],
        detail=False,
        url_path="operate_node/(?P<task_id>\\d+)/node/(?P<node_id>\\w+)/(?P<operation>\\w+)",
    )
    def operate_node(self, request, task_id, node_id, operation, *args, **kwargs):
        space_id = self.get_space_id(request)

        with start_trace(
            "operate_task_node_interface",
            True,
            space_id=space_id,
            task_id=task_id,
            node_id=node_id,
            call_from=CallFrom.WEB.value,
        ):
            append_attributes({"operation": operation})
            client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
            request.data["operator"] = request.user.username
            result = client.node_operate(task_id, node_id, operation, request.data)
            return Response(result)

    @action(
        methods=["GET"],
        detail=False,
        url_path="get_task_node_log/(?P<task_id>\\d+)/(?P<node_id>\\w+)/(?P<version>\\w+)",
    )
    def get_task_node_log(self, request, task_id, node_id, version, *args, **kwargs):
        space_id = self.get_space_id(request)
        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        result = client.get_task_node_log(task_id, node_id, version, data=request.query_params)
        return Response(result)

    @action(methods=["GET"], detail=False, url_path="render_current_constants/(?P<task_id>\\d+)")
    def render_current_constants(self, request, task_id, *args, **kwargs):
        space_id = self.get_space_id(request)
        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        result = client.render_current_constants(task_id)
        return Response(result)

    @action(methods=["GET"], detail=False, url_path="get_task_operation_record/(?P<task_id>\\d+)")
    def get_task_operation_record(self, request, task_id, *args, **kwargs):
        space_id = self.get_space_id(request)
        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        result = client.get_task_operation_record(task_id, data=request.query_params)
        return Response(result)

    @action(methods=["GET"], detail=False, url_path="get_node_snapshot_config/(?P<task_id>\\d+)/(?P<node_id>\\w+)")
    def get_node_snapshot_config(self, request, task_id, node_id, *args, **kwargs):
        space_id = self.get_space_id(request)
        client = TaskComponentClient(space_id=space_id, from_superuser=request.user.is_superuser)
        data = {"node_id": node_id}
        result = client.get_node_snapshot_config(task_id, data)
        return Response(result)

    @action(methods=["GET"], detail=False, url_path="get_stage_job_states/(?P<task_id>\\d+)")
    def get_stage_and_job_states(self, request, task_id, *args, **kwargs):
        """获取stage和job状态的视图函数"""
        space_id = self.get_space_id(request)
        handler = StageJobStateHandler(space_id, request.user.is_superuser)
        result = handler.process(task_id)
        return Response(result)

    @action(methods=["POST"], detail=False, url_path="rendered_stage_constants/(?P<task_id>\\d+)")
    @swagger_auto_schema(operation_description="渲染stage画布变量", request_body=RenderConstantsBodySerializer)
    def render_stage_constants(self, request, task_id, *args, **kwargs):
        """渲染stage画布变量"""
        space_id = self.get_space_id(request)
        serializer = RenderConstantsBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        node_ids = serializer.validated_data.get("node_ids", [])
        stage_constants = serializer.validated_data.get("to_render_constants", {})
        handler = StageConstantHandler(space_id, request.user.is_superuser)
        result = handler.process(task_id, node_ids, stage_constants)
        return Response(result)
