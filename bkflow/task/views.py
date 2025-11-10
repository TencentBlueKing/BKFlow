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
from functools import wraps

from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.utils.decorators import method_decorator
from django_filters import FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.constants import (
    RecordType,
    TaskOperationSource,
    TaskOperationType,
    TaskTriggerMethod,
)
from bkflow.contrib.openapi.serializers import (
    EmptyBodySerializer,
    GetNodeDetailQuerySerializer,
    GetNodeLogDetailSerializer,
    GetTasksStatesBodySerializer,
    TaskBatchDeleteSerializer,
)
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.exceptions import ValidationError
from bkflow.task.models import (
    EngineSpaceConfig,
    EngineSpaceConfigValueType,
    PeriodicTask,
    TaskInstance,
    TaskMockData,
    TaskOperationRecord,
)
from bkflow.task.node_log import NodeLogDataSourceFactory
from bkflow.task.operations import TaskNodeOperation, TaskOperation
from bkflow.task.serializers import (
    BatchDeletePeriodicTaskSerializer,
    CreatePeriodicTaskSerializer,
    CreateTaskInstanceSerializer,
    EngineSpaceConfigSerializer,
    GetEngineSpaceConfigSerializer,
    GetTaskOperationRecordSerializer,
    NodeSnapshotQuerySerializer,
    NodeSnapshotResponseSerializer,
    PeriodicTaskSerializer,
    RetrieveTaskInstanceSerializer,
    TaskInstanceSerializer,
    TaskOperationRecordSerializer,
    UpdatePeriodicTaskSerializer,
)
from bkflow.utils.handlers import handle_plain_log
from bkflow.utils.mixins import BKFLOWCommonMixin
from bkflow.utils.permissions import AdminPermission, AppInternalPermission
from bkflow.utils.trace import start_trace
from bkflow.utils.views import SimpleGenericViewSet


class TaskInstanceFilterSet(FilterSet):
    class Meta:
        model = TaskInstance
        fields = {
            "id": ["exact"],
            "space_id": ["exact"],
            "name": ["exact", "icontains"],
            "creator": ["exact"],
            "executor": ["exact"],
            "template_id": ["exact"],
            "scope_type": ["exact"],
            "scope_value": ["exact"],
            "create_time": ["gte", "lte"],
            "start_time": ["gte", "lte"],
            "finish_time": ["gte", "lte"],
            "create_method": ["exact"],
            "trigger_method": ["exact"],
            "is_started": ["exact"],
            "is_finished": ["exact"],
        }


def validate_task_info(func):
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        space_id, from_superuser = request.headers.get(settings.APP_INTERNAL_SPACE_ID_HEADER_KEY), request.headers.get(
            settings.APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY, "0"
        )
        from_superuser = True if from_superuser == "1" else False
        task_instance = self.get_object()
        if not from_superuser and not (space_id and str(space_id) == str(task_instance.space_id)):
            return Response({"result": False, "data": None, "message": "space_id is invalid"}, status=403)

        node_id = kwargs.get("node_id") or request.data.get("node_id") or request.query_params.get("node_id")
        if node_id and not task_instance.has_node(node_id):
            return Response({"result": False, "data": None, "message": "node_id should be in task"}, status=403)
        return func(self, request, *args, **kwargs)

    return wrapper


@method_decorator(login_exempt, name="dispatch")
class TaskInstanceViewSet(
    BKFLOWCommonMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    SimpleGenericViewSet,
):
    queryset = TaskInstance.objects.filter(is_deleted=False, is_expired=False)
    serializer_class = TaskInstanceSerializer
    permission_classes = [AdminPermission | AppInternalPermission]
    VALID_TASK_OPERATIONS = ["start", "pause", "resume", "revoke"]
    VALID_NODE_OPERATIONS = ["retry", "skip", "callback", "forced_fail", "skip_exg", "skip_cpg"]
    filter_backends = [DjangoFilterBackend]
    filter_class = TaskInstanceFilterSet

    def task_response_wrapper(self, data):
        if all([key in data for key in ["result", "data", "message"]]):
            return data
        else:
            return self.default_response_wrapper(data)

    RESPONSE_WRAPPER = task_response_wrapper

    def get_serializer_class(self):
        if self.action == "create":
            return CreateTaskInstanceSerializer
        elif self.action == "retrieve":
            return RetrieveTaskInstanceSerializer
        return super().get_serializer_class()

    @record_operation(RecordType.task.name, TaskOperationType.create.name, TaskOperationSource.api.name)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = TaskInstance.objects.create_instance(**serializer.validated_data)
        new_serializer = TaskInstanceSerializer(instance)
        headers = self.get_success_headers(new_serializer.data)
        response_data = new_serializer.data
        constants = instance.pipeline_tree["constants"]
        parameters = {key: value["value"] for key, value in constants.items()}
        response_data["parameters"] = parameters
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @swagger_auto_schema(methods=["post"], operation_description="批量删除任务", request_body=TaskBatchDeleteSerializer)
    @action(detail=False, methods=["post"], url_path="batch_delete_tasks")
    def batch_delete(self, request, *args, **kwargs):
        serializer = TaskBatchDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        space_id = serializer.validated_data["space_id"]
        is_full = serializer.validated_data["is_full"]
        if is_full:
            qs = TaskInstance.objects.filter(space_id=space_id, is_deleted=False)
            if serializer.validated_data["is_mock"]:
                qs = qs.filter(create_method="MOCK")
            qs.update(is_deleted=True)
        else:
            task_ids = serializer.validated_data["task_ids"]
            TaskInstance.objects.filter(space_id=space_id, id__in=task_ids, is_deleted=False).update(is_deleted=True)
        return Response({"result": True, "data": None, "message": "success"})

    @swagger_auto_schema(methods=["post"], operation_description="任务操作", request_body=EmptyBodySerializer)
    @action(detail=True, methods=["post"], url_path="operate/(?P<operation>\\w+)")
    @validate_task_info
    def operate(self, request, operation, *args, **kwargs):
        if operation not in self.VALID_TASK_OPERATIONS:
            raise ValidationError("task operation not allowed")
        task_instance = self.get_object()

        with start_trace(
            "operate_task_engine",
            propagate=True,
            space_id=task_instance.space_id,
            task_id=task_instance.id,
            template_id=task_instance.template_id,
            executor=task_instance.executor,
        ):
            task_operation = TaskOperation(task_instance=task_instance, queue=settings.BKFLOW_MODULE.code)
            operation_method = getattr(task_operation, operation, None)
            if operation_method is None:
                raise ValidationError("task operation not found")
            data = request.data
            operator = data.pop("operator", request.user.username)
            operation_result = operation_method(operator=operator, **data)
            return Response(dict(operation_result))

    @swagger_auto_schema(methods=["post"], operation_description="节点操作", request_body=EmptyBodySerializer)
    @action(detail=True, methods=["post"], url_path="node_operate/(?P<node_id>\\w+)/(?P<operation>\\w+)")
    @validate_task_info
    def node_operate(self, request, node_id, operation, *args, **kwargs):
        if operation not in self.VALID_NODE_OPERATIONS:
            raise ValidationError("node operation not allowed")
        task_instance = self.get_object()

        with start_trace(
            "operate_task_node_engine",
            propagate=True,
            space_id=task_instance.space_id,
            task_id=task_instance.id,
            node_id=node_id,
            template_id=task_instance.template_id,
            executor=task_instance.executor,
        ):
            if task_instance.trigger_method == TaskTriggerMethod.subprocess.name and operation in ["skip", "retry"]:
                task_instance.change_parent_task_node_state_to_running()
            node_operation = TaskNodeOperation(task_instance=task_instance, node_id=node_id)
            operation_method = getattr(node_operation, operation, None)
            if operation_method is None:
                raise ValidationError("node operation not found")
            data = request.data
            operator = data.pop("operator", request.user.username)
            operation_result = operation_method(operator=operator, **data)
            return Response(dict(operation_result))

    @swagger_auto_schema(methods=["get"], operation_description="任务状态查询")
    @action(detail=True, methods=["get"], url_path="get_states")
    @validate_task_info
    def get_states(self, request, *args, **kwargs):
        task_instance = self.get_object()
        task_operation = TaskOperation(task_instance=task_instance, queue=settings.BKFLOW_MODULE.code)
        states = task_operation.get_task_states()
        return Response(dict(states))

    @swagger_auto_schema(methods=["post"], operation_description="任务状态查询", request_body=GetTasksStatesBodySerializer)
    @action(detail=False, methods=["post"], url_path="get_tasks_states")
    def get_tasks_states(self, request, *args, **kwargs):
        """批量获取任务状态，仅支持管理员调用"""
        ser = GetTasksStatesBodySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task_ids = ser.validated_data["task_ids"]
        space_id = ser.validated_data["space_id"]
        task_instances = TaskInstance.objects.filter(id__in=task_ids, space_id=space_id)
        task_operations = [
            {"task_id": task_instance.id, "operation": TaskOperation(task_instance=task_instance).get_task_states()}
            for task_instance in task_instances
        ]
        task_states = {
            task_operation["task_id"]: {
                "state": (
                    task_operation["operation"].data.get("state")
                    if task_operation["operation"].result is True
                    else None
                )
            }
            for task_operation in task_operations
        }
        return Response(task_states)

    @swagger_auto_schema(methods=["get"], operation_description="获取任务 mock 数据")
    @action(detail=True, methods=["get"], url_path="get_task_mock_data")
    def get_task_mock_data(self, request, *args, **kwargs):
        task_instance = self.get_object()
        task_mock_data = TaskMockData.objects.filter(taskflow_id=task_instance.id).first()
        return Response(task_mock_data.to_json() if task_mock_data else {})

    @swagger_auto_schema(methods=["get"], operation_description="任务全局变量查询")
    @action(detail=True, methods=["get"], url_path="render_current_constants")
    @validate_task_info
    def render_current_constants(self, request, *args, **kwargs):
        task_instance = self.get_object()
        task_operation = TaskOperation(task_instance=task_instance, queue=settings.BKFLOW_MODULE.code)
        states = task_operation.render_current_constants()
        return Response(dict(states))

    @action(detail=True, methods=["post"], url_path="render_context_with_node_outputs")
    @validate_task_info
    def render_context_with_node_outputs(self, request, *args, **kwargs):
        task_instance = self.get_object()
        task_operation = TaskOperation(task_instance=task_instance, queue=settings.BKFLOW_MODULE.code)
        node_ids = request.data.get("node_ids", [])
        to_render_constants = request.data.get("to_render_constants", [])
        to_render_constants_dict = {item: item for item in to_render_constants}
        constants = task_operation.render_context_with_node_outputs(node_ids, to_render_constants_dict)
        return Response(dict(constants))

    @swagger_auto_schema(
        methods=["get"], operation_description="任务节点详情查询", query_serializer=GetNodeDetailQuerySerializer
    )
    @action(detail=True, methods=["get"], url_path="get_task_node_detail/(?P<node_id>\\w+)")
    @validate_task_info
    def get_node_detail(self, request, node_id, *args, **kwargs):
        query_ser = GetNodeDetailQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        task_instance = self.get_object()
        if not task_instance.has_node(node_id):
            raise ValidationError(f"node {node_id} not found")

        node_data = {}
        node_operation = TaskNodeOperation(task_instance=task_instance, node_id=node_id)
        if query_ser.validated_data["include_data"]:
            node_data_result = node_operation.get_node_data(
                username=query_ser.validated_data["username"],
                subprocess_stack=query_ser.validated_data.get("subprocess_stack"),
                component_code=query_ser.validated_data.get("component_code"),
                loop=query_ser.validated_data.get("loop"),
            )
            if not node_data_result.result:
                return Response(dict(node_data_result))
            node_data = node_data_result.data

        node_detail_result = node_operation.get_node_detail(
            subprocess_stack=query_ser.validated_data.get("subprocess_stack"),
            loop=query_ser.validated_data.get("loop"),
        )
        if not node_detail_result.result:
            return Response(dict(node_detail_result))

        node_detail_result.data.update(node_data)

        return Response(dict(node_detail_result))

    @swagger_auto_schema(methods=["get"], operation_description="任务节点执行日志", query_serializer=GetNodeLogDetailSerializer)
    @action(detail=True, methods=["get"], url_path="get_task_node_log/(?P<node_id>\\w+)/(?P<version>\\w+)")
    @validate_task_info
    def get_node_log(self, request, node_id, version, *args, **kwargs):
        query_ser = GetNodeLogDetailSerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        page, page_size = query_ser.validated_data["page"], query_ser.validated_data["page_size"]
        data_source = NodeLogDataSourceFactory(settings.NODE_LOG_DATA_SOURCE).data_source
        result = data_source.fetch_node_logs(node_id, version, page=page, page_size=page_size)
        if not result["result"]:
            return Response({"result": False, "message": result["message"], "data": None})
        logs, page_info = result["data"]["logs"], result["data"]["page_info"]

        return Response(
            {
                "result": True,
                "message": "success",
                "data": handle_plain_log(logs),
                "page": page_info if page_info else {},
            }
        )

    @swagger_auto_schema(
        methods=["get"], operation_description="任务操作记录", query_serializer=GetTaskOperationRecordSerializer
    )
    @action(detail=True, methods=["get"], url_path="get_task_operation_record")
    @validate_task_info
    def get_task_operation_record(self, request, *args, **kwargs):
        query_ser = GetTaskOperationRecordSerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        instance_id = kwargs["pk"]
        queryset = TaskOperationRecord.objects.filter(instance_id=instance_id)
        if query_ser.validated_data.get("node_id"):
            queryset = queryset.filter(node_id=query_ser.validated_data["node_id"])

        model_ser = TaskOperationRecordSerializer(queryset, many=True)
        return Response(
            {
                "result": True,
                "message": "success",
                "data": model_ser.data,
            }
        )

    @swagger_auto_schema(
        method="GET",
        operation_summary="获取某个节点的节点配置快照",
        query_serializer=NodeSnapshotQuerySerializer,
        responses={200: NodeSnapshotResponseSerializer},
    )
    @action(methods=["GET"], detail=True)
    @validate_task_info
    def get_node_snapshot_config(self, request, *args, **kwargs):
        ser = NodeSnapshotQuerySerializer(data=request.GET)
        ser.is_valid(raise_exception=True)

        node_id = ser.data["node_id"]
        task = self.get_object()

        # 不存在子流程，则直接查找
        template_node_id = task.execution_data["activities"].get(node_id, {}).get("template_node_id")
        if not template_node_id:
            return Response(
                {
                    "result": False,
                    "message": "template_node_id 未找到",
                    "data": None,
                }
            )
        node_snapshot_config = task.snapshot.data["activities"].get(template_node_id)

        return Response(
            {
                "result": True,
                "message": "success",
                "data": node_snapshot_config,
            }
        )

    @action(detail=False, methods=["get"], url_path="get_engine_config")
    def get_engine_config(self, request, *args, **kwargs):
        serializer = GetEngineSpaceConfigSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        instance_ids = serializer.validated_data["interface_config_ids"]
        simplified = serializer.validated_data["simplified"]
        try:
            instances = EngineSpaceConfig.objects.filter(interface_config_id__in=instance_ids)
        except EngineSpaceConfig.DoesNotExist as e:
            return Response(exception=True, data={"result": False, "message": str(e)})
        if simplified:
            res = [
                {
                    "key": instance.name,
                    "value": (
                        instance.json_value
                        if instance.value_type == EngineSpaceConfigValueType.JSON.value
                        else instance.text_value
                    ),
                }
                for instance in instances
            ]
        else:
            res = [instance.to_json() for instance in instances]
        return Response({"result": True, "message": "success", "data": res})

    @action(detail=False, methods=["post"], url_path="upsert_engine_config")
    def upsert_engine_config(self, request, *args, **kwargs):
        serializer = EngineSpaceConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance_id = serializer.validated_data.get("interface_config_id", -1)

        try:
            # 如果有 interface_config_id，则更新，否则创建新的配置
            config_instance = EngineSpaceConfig.objects.get(interface_config_id=instance_id)
            for attr, value in serializer.validated_data.items():
                setattr(config_instance, attr, value)
            config_instance.save()
        except EngineSpaceConfig.DoesNotExist:
            EngineSpaceConfig.objects.create(**serializer.validated_data)
        return Response({"result": True, "message": "success", "data": serializer.data})

    @action(detail=False, methods=["delete"], url_path="delete_engine_config")
    def delete_engine_config(self, request, *args, **kwargs):
        serializer = GetEngineSpaceConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance_id = serializer.validated_data["interface_config_ids"]

        try:
            instances = EngineSpaceConfig.objects.filter(interface_config_id__in=instance_id)
            instances.delete()
        except EngineSpaceConfig.DoesNotExist:
            return Response(
                exception=True, data={"result": False, "message": f"config with id {instance_id} not exist"}
            )
        return Response({"result": True, "message": "success", "data": serializer.data})


@method_decorator(login_exempt, name="dispatch")
class PeriodicTaskViewSet(
    BKFLOWCommonMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    SimpleGenericViewSet,
):
    queryset = PeriodicTask.objects.all()
    serializer_class = PeriodicTaskSerializer

    def create(self, request, *args, **kwargs):
        serializer = CreatePeriodicTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = PeriodicTask.objects.create_task(**serializer.validated_data)
        return Response(instance, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="update")
    def update_task(self, request, *args, **kwargs):
        serializer = UpdatePeriodicTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trigger_id = serializer.validated_data["trigger_id"]
        instance = self.get_queryset().filter(trigger_id=trigger_id).first()
        if not instance:
            return Response(
                status=status.HTTP_404_NOT_FOUND,
                data={"result": False, "message": f"periodic_task instance with trigger id {trigger_id} not exist"},
            )
        serializer.update(instance, serializer.validated_data)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="batch_delete")
    def batch_delete(self, request, *args, **kwargs):
        serializer = BatchDeletePeriodicTaskSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        trigger_ids = serializer.validated_data["trigger_ids"]
        for instance in self.get_queryset().filter(trigger_id__in=trigger_ids).select_related("celery_task"):
            instance.delete()
        return Response(status=status.HTTP_200_OK)
