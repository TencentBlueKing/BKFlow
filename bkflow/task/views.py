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
from django.db.models import Count, Subquery
from django.utils.decorators import method_decorator
from django_filters import CharFilter, FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.constants import (
    OPERATE_EVENT_MAP,
    RecordType,
    TaskOperationSource,
    TaskOperationType,
    TaskTriggerMethod,
)
from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.contrib.openapi.serializers import (
    EmptyBodySerializer,
    GetNodeDetailQuerySerializer,
    GetNodeLogDetailSerializer,
    GetNodeOutputsSerializer,
    GetTasksStatesBodySerializer,
    TaskBatchDeleteSerializer,
)
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.exceptions import ValidationError
from bkflow.task.models import (
    EngineSpaceConfig,
    EngineSpaceConfigValueType,
    PeriodicTask,
    TaskExecutionSnapshot,
    TaskFlowRelation,
    TaskInstance,
    TaskLabelRelation,
    TaskMockData,
    TaskOperationRecord,
)
from bkflow.task.node_log import NodeLogDataSourceFactory
from bkflow.task.operations import TaskNodeOperation, TaskOperation
from bkflow.task.serializers import (
    BatchDeletePeriodicTaskSerializer,
    CreatePeriodicTaskSerializer,
    CreateTaskInstanceSerializer,
    DeleteTaskLabelRelationSerializer,
    EngineSpaceConfigSerializer,
    GetEngineSpaceConfigSerializer,
    GetTaskOperationRecordSerializer,
    LabelRefSerializer,
    NodeSnapshotQuerySerializer,
    NodeSnapshotResponseSerializer,
    PeriodicTaskSerializer,
    RetrieveTaskInstanceSerializer,
    TaskInstanceSerializer,
    TaskOperationRecordSerializer,
    TaskUpdateLabelSerializer,
    UpdatePeriodicTaskSerializer,
)
from bkflow.utils.handlers import handle_plain_log
from bkflow.utils.mixins import BKFLOWCommonMixin
from bkflow.utils.permissions import AdminPermission, AppInternalPermission
from bkflow.utils.trace import start_trace
from bkflow.utils.views import SimpleGenericViewSet


class TaskInstanceFilterSet(FilterSet):
    label = CharFilter(method="filter_by_labels")
    is_child_taskflow = CharFilter(method="filter_by_child_taskflow")

    class Meta:
        model = TaskInstance
        fields = {
            "id": ["exact", "in"],
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

    def filter_by_labels(self, queryset, name, value):
        """
        根据逗号分隔的 label_id 字符串过滤任务。
        URL Query Param 示例: ?label=1,2,3
        """
        try:
            label_ids = [int(lid) for lid in value.split(",")]
        except ValueError:
            return queryset.none()

        if not label_ids:
            return queryset

        task_ids_subquery = TaskLabelRelation.objects.filter(label_id__in=label_ids).values("task_id")

        return queryset.filter(id__in=Subquery(task_ids_subquery))

    def filter_by_child_taskflow(self, queryset, name, value):
        """
        过滤子任务流（子流程和子画布）
        """
        filter_task_trigger_method = [TaskTriggerMethod.subprocess.name, TaskTriggerMethod.sub_canvas.name]
        if value == "false":
            return queryset.exclude(trigger_method__in=filter_task_trigger_method)
        return queryset


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

    def _should_keep_debug_tasks(self):
        """列表默认隐藏 DEBUG；显式按 create_method 或按主键查询时保留。

        apply_token / get_task_list?id= 都走 list + id 精确过滤，必须先应用 FilterSet
        再决定是否隐藏，避免只在 get_queryset 里看 query_params 漏掉 DEBUG。
        """
        if self.action != "list":
            return True

        params = self.request.query_params
        if "create_method" in params:
            return True

        for key in ("id", "id__in", "pk"):
            if hasattr(params, "getlist"):
                values = params.getlist(key)
            else:
                value = params.get(key)
                values = [value] if value is not None else []
            if any(str(value) for value in values if value is not None):
                return True
        return False

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if self.action == "list" and not self._should_keep_debug_tasks():
            queryset = queryset.exclude(create_method="DEBUG")
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)

        serializer = self.get_serializer(page, many=True)
        task_ids = [task["id"] for task in serializer.data]
        tasks_labels = TaskLabelRelation.objects.fetch_tasks_labels(task_ids)
        for task in serializer.data:
            task["labels"] = tasks_labels.get(task["id"], [])

        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"], url_path="update_labels")
    def update_labels(self, request, *args, **kwargs):
        task_instance = self.get_object()
        ser = TaskUpdateLabelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        label_ids = ser.validated_data["label_ids"]
        TaskLabelRelation.objects.set_labels(task_instance.id, label_ids)
        return Response(label_ids)

    @action(detail=False, methods=["get"], serializer_class=LabelRefSerializer)
    def get_task_label_ref_count(self, request, *args, **kwargs):
        """获取标签引用数量"""
        ser = LabelRefSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        validated_params = ser.validated_data
        label_ids = validated_params["label_ids"].split(",")
        queryset = (
            TaskLabelRelation.objects.filter(label_id__in=label_ids).values("label_id").annotate(count=Count("id"))
        )
        label_template_count_map = {item["label_id"]: item["count"] for item in queryset}
        result = {}
        for label_id in label_ids:
            result[label_id] = label_template_count_map.get(int(label_id), 0)

        return Response(result)

    @action(detail=False, methods=["post"], serializer_class=DeleteTaskLabelRelationSerializer)
    def delete_task_label_relation(self, request, *args, **kwargs):
        """删除任务标签关联"""
        ser = DeleteTaskLabelRelationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        validated_params = ser.validated_data
        label_ids = validated_params["label_ids"]
        TaskLabelRelation.objects.filter(label_id__in=label_ids).delete()
        return Response({"label_ids": label_ids})

    @record_operation(RecordType.task.name, TaskOperationType.create.name, TaskOperationSource.api.name)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        label_ids = serializer.validated_data.pop("label_ids", [])
        instance = TaskInstance.objects.create_instance(**serializer.validated_data)
        TaskLabelRelation.objects.set_labels(instance.id, label_ids)
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
            TaskLabelRelation.objects.filter(task_id__in=task_ids).delete()
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

            if operation in ["pause", "resume", "revoke"]:
                interface_client = InterfaceModuleClient()
                interface_client.broadcast_task_events(
                    data={
                        "space_id": task_instance.space_id,
                        "event": OPERATE_EVENT_MAP[operation],
                        "extra_info": {
                            "task_id": task_instance.id,
                            "operation": operation,
                            "username": request.user.username,
                        },
                    }
                )
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
            if task_instance.trigger_method in [
                TaskTriggerMethod.subprocess.name,
                TaskTriggerMethod.sub_canvas.name,
            ] and operation in ["skip", "retry"]:
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
        truthy = {"1", "true", "yes"}
        states = task_operation.get_task_states(
            with_ex_data=str(request.query_params.get("with_ex_data", "")).lower() in truthy,
            include_schedule=str(request.query_params.get("include_schedule", "")).lower() in truthy,
        )
        return Response(dict(states))

    @action(detail=False, methods=["get"], url_path="batch_get_task_states")
    def batch_get_task_states(self, request, *args, **kwargs):
        task_ids_str = request.query_params.get("task_ids", "")
        space_id = request.query_params.get("space_id", "")
        if not task_ids_str or not space_id:
            return Response({"result": False, "message": "缺少必要参数task_ids或space_id", "data": {}}, status=400)

        task_id_list = task_ids_str.split(",")
        if not task_id_list:
            return Response({"result": False, "message": "无合法的任务ID", "data": {}}, status=400)

        tasks = TaskInstance.objects.filter(id__in=task_id_list, space_id=space_id)
        states_result = {}
        for task in tasks:
            task_operation = TaskOperation(task_instance=task, queue=settings.BKFLOW_MODULE.code)
            task_states = task_operation.get_task_states()
            states_result[str(task.id)] = task_states.data if task_states else {}

        return Response(states_result)

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

    @swagger_auto_schema(methods=["get"], operation_description="获取任务模板节点 id 到运行时节点 id 的映射")
    @action(detail=True, methods=["get"], url_path="get_node_id_map")
    @validate_task_info
    def get_node_id_map(self, request, *args, **kwargs):
        task_instance = self.get_object()
        execution_data = task_instance.execution_data or {}
        mapping = {}
        for node_type in ("activities", "gateways"):
            for node_id, node in execution_data.get(node_type, {}).items():
                mapping[node.get("template_node_id", node_id)] = node_id
        return Response(mapping)

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

    @action(methods=["GET"], detail=False, url_path="list_children_taskflow")
    def list_children_taskflow(self, request, *args, **kwargs):
        """获取根任务下的所有子任务列表"""
        root_task_id = request.query_params.get("task_id")
        if not root_task_id:
            return Response({"tasks": [], "relations": {}}, status=status.HTTP_200_OK)

        children_task_info = TaskFlowRelation.objects.filter(root_task_id=root_task_id).values(
            "task_id", "parent_task_id"
        )
        children_task_ids = [info["task_id"] for info in children_task_info]
        if not children_task_ids:
            return Response({"tasks": [], "relations": {}}, status=status.HTTP_200_OK)
        queryset = TaskInstance.objects.filter(
            id__in=children_task_ids, is_deleted=False, trigger_method=TaskTriggerMethod.subprocess.name
        )
        queryset = self.filter_queryset(queryset)
        serializer = self.get_serializer(queryset, many=True)
        task_ids = [task["id"] for task in serializer.data]
        tasks_labels = TaskLabelRelation.objects.fetch_tasks_labels(task_ids)
        for task in serializer.data:
            task["labels"] = tasks_labels.get(task["id"], [])

        # 仅保留实际返回给前端的子流程任务关系，排除子画布等非子流程记录
        task_id_set = set(task_ids)
        relations = {
            info["task_id"]: info["parent_task_id"] for info in children_task_info if info["task_id"] in task_id_set
        }
        return Response({"tasks": serializer.data, "relations": relations}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="root_task_info")
    def root_task_info(self, request, *args, **kwargs):
        """批量查询任务是否包含子任务"""
        task_ids_param = request.query_params.get("task_ids", "")
        if not task_ids_param:
            return Response({"has_children_taskflow": {}})

        try:
            task_ids = [int(task_id) for task_id in task_ids_param.split(",") if task_id]
        except ValueError:
            return Response(
                {"result": False, "code": "400", "message": "task_ids参数格式错误，应为逗号分隔的数字"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tasks_with_children = set(
            TaskFlowRelation.objects.filter(root_task_id__in=task_ids)
            .exclude(extra_info__trigger_method=TaskTriggerMethod.sub_canvas.name)
            .values_list("root_task_id", flat=True)
            .distinct()
        )
        root_task_info = {task_id: task_id in tasks_with_children for task_id in task_ids}
        return Response({"has_children_taskflow": root_task_info})

    @action(methods=["GET"], detail=False)
    def get_tasks_pipeline(self, request, *args, **kwargs):
        task_ids = request.query_params.get("task_ids", "")
        space_id = request.query_params["space_id"]
        if not task_ids:
            return Response({})
        task_id_list = task_ids.split(",")
        tasks = TaskInstance.objects.filter(id__in=task_id_list, space_id=space_id).values(
            "id", "execution_snapshot_id"
        )
        snapshot_ids = [task["execution_snapshot_id"] for task in tasks if task["execution_snapshot_id"]]

        snapshot_map = (
            {snap.id: snap for snap in TaskExecutionSnapshot.objects.filter(id__in=snapshot_ids)}
            if snapshot_ids
            else {}
        )

        result = {}
        for task in tasks:
            task_id = str(task["id"])
            pipeline_tree = None
            snap_id = task["execution_snapshot_id"]

            if snap_id and snap_id in snapshot_map:
                snap = snapshot_map[snap_id]
                pipeline_tree = snap.data

            result[task_id] = pipeline_tree

        return Response(result)

    @action(methods=["POST"], detail=False)
    def get_node_outputs(self, request, *args, **kwargs):
        ser = GetNodeOutputsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task_id = ser.validated_data["task_id"]
        space_id = ser.validated_data["space_id"]
        node_ids = ser.validated_data["node_ids"]
        try:
            task_instance = TaskInstance.objects.get(id=task_id, space_id=space_id)
        except TaskInstance.DoesNotExist:
            return Response({"result": False, "data": None, "message": "task not found"})

        for node_id in node_ids:
            if not task_instance.has_node(node_id):
                return Response({"result": False, "data": None, "message": "node_id should be in task"})
        node_outputs = [
            {node_id: TaskNodeOperation(task_instance=task_instance, node_id=node_id).get_node_outputs().data}
            for node_id in node_ids
        ]
        return Response(node_outputs)

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
                include_loop_outputs=query_ser.validated_data["include_loop_outputs"],
            )
            if not node_data_result.result:
                return Response(dict(node_data_result))
            node_data = node_data_result.data

        node_detail_result = node_operation.get_node_detail(
            subprocess_stack=query_ser.validated_data.get("subprocess_stack"),
            component_code=query_ser.validated_data.get("component_code"),
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
