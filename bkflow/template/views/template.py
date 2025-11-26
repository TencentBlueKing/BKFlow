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
from copy import deepcopy

from blueapps.account.decorators import login_exempt
from django.db import transaction
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from webhook.signals import event_broadcast_signal

from bkflow.apigw.serializers.task import (
    CreateMockTaskWithPipelineTreeSerializer,
    CreateTaskSerializer,
)
from bkflow.apigw.serializers.template import CreateTemplateSerializer
from bkflow.constants import (
    RecordType,
    TaskTriggerMethod,
    TemplateOperationSource,
    TemplateOperationType,
    WebhookEventType,
    WebhookScopeType,
)
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.exceptions import APIResponseError, ValidationError
from bkflow.pipeline_web.drawing_new.constants import CANVAS_WIDTH, POSITION
from bkflow.pipeline_web.drawing_new.drawing import draw_pipeline as draw_pipeline_tree
from bkflow.pipeline_web.preview import preview_template_tree
from bkflow.pipeline_web.preview_base import PipelineTemplateWebPreviewer
from bkflow.space.configs import (
    GatewayExpressionConfig,
    UniformApiConfig,
    UniformAPIConfigHandler,
)
from bkflow.space.exceptions import SpaceConfigDefaultValueNotExists
from bkflow.space.models import SpaceConfig
from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.space.utils import build_default_pipeline_tree_with_space_id
from bkflow.template.exceptions import AnalysisConstantsRefException
from bkflow.template.models import (
    Template,
    TemplateMockData,
    TemplateMockScheme,
    TemplateOperationRecord,
    TemplateReference,
    TemplateSnapshot,
    Trigger,
)
from bkflow.template.permissions import (
    TemplateMockPermission,
    TemplatePermission,
    TemplateRelatedResourcePermission,
)
from bkflow.template.serializers.template import (
    AdminTemplateSerializer,
    DrawPipelineSerializer,
    PreviewTaskTreeSerializer,
    TemplateBatchDeleteSerializer,
    TemplateCopySerializer,
    TemplateMockDataBatchCreateSerializer,
    TemplateMockDataListSerializer,
    TemplateMockDataQuerySerializer,
    TemplateMockDataSerializer,
    TemplateMockSchemeSerializer,
    TemplateOperationRecordSerializer,
    TemplateRelatedResourceSerializer,
    TemplateSerializer,
)
from bkflow.template.utils import analysis_pipeline_constants_ref
from bkflow.utils.mixins import BKFLOWCommonMixin, BKFLOWNoMaxLimitPagination
from bkflow.utils.permissions import AdminPermission, AppInternalPermission
from bkflow.utils.views import AdminModelViewSet, SimpleGenericViewSet, UserModelViewSet

logger = logging.getLogger("root")


class TemplateFilterSet(FilterSet):
    class Meta:
        model = Template
        fields = {
            "id": ["exact"],
            "space_id": ["exact"],
            "name": ["icontains"],
            "creator": ["exact"],
            "updated_by": ["exact"],
            "scope_value": ["exact"],
            "scope_type": ["exact"],
            "is_enabled": ["exact"],
            "create_at": ["gte", "lte"],
            "update_at": ["gte", "lte"],
        }


class AdminTemplateViewSet(AdminModelViewSet):
    queryset = Template.objects.filter(is_deleted=False).order_by("-id")
    serializer_class = AdminTemplateSerializer
    filter_backends = [DjangoFilterBackend]
    filter_class = TemplateFilterSet
    pagination_class = BKFLOWNoMaxLimitPagination
    permission_classes = [AdminPermission | SpaceSuperuserPermission]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        scope_value = request.query_params.get("scope_value")
        scope_type = request.query_params.get("scope_type")
        empty_scope = request.query_params.get("empty_scope")
        if scope_type is None and scope_value is None and empty_scope:
            queryset = queryset.filter(scope_type__isnull=True, scope_value__isnull=True)

        page = self.paginate_queryset(queryset)

        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        data = []
        has_trigger_template_ids = set(Trigger.objects.all().values_list("template_id", flat=True))
        for template in serializer.data:
            if template["id"] in has_trigger_template_ids:
                template["has_interval_trigger"] = True
            else:
                template["has_interval_trigger"] = False
            data.append(template)
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

    @swagger_auto_schema(method="POST", operation_description="创建流程", request_body=CreateTemplateSerializer)
    @action(methods=["POST"], detail=False, url_path="create_default_template/(?P<space_id>\\d+)")
    def create_template(self, request, space_id, *args, **kwargs):
        ser = CreateTemplateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)

        pipeline_tree = build_default_pipeline_tree_with_space_id(space_id)
        # 涉及到两张表的创建，需要那个开启事物，确保两张表全部都创建成功
        with transaction.atomic():
            username = request.user.username
            snapshot = TemplateSnapshot.create_snapshot(pipeline_tree)
            template = Template.objects.create(
                **ser.data, snapshot_id=snapshot.id, space_id=space_id, updated_by=username, creator=username
            )
            snapshot.template_id = template.id
            snapshot.save(update_fields=["template_id"])
        return Response({"result": True, "data": template.to_json()})

    @swagger_auto_schema(method="POST", operation_description="创建任务", request_body=CreateTaskSerializer)
    @action(methods=["POST"], detail=False, url_path="create_task/(?P<space_id>\\d+)")
    def create_task(self, request, space_id, *args, **kwargs):
        ser = CreateTaskSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            template = Template.objects.get(id=ser.data["template_id"], space_id=space_id)
        except Template.DoesNotExist:
            raise ValidationError(
                _("模版不存在，space_id={space_id}, template_id={template_id}").format(
                    space_id=space_id, template_id=ser.data["template_id"]
                )
            )
        create_task_data = dict(ser.data)
        create_task_data["scope_type"] = template.scope_type
        create_task_data["scope_value"] = template.scope_value
        create_task_data["space_id"] = space_id

        pre_pipeline_tree = deepcopy(template.pipeline_tree)
        PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(pre_pipeline_tree)
        create_task_data["pipeline_tree"] = pre_pipeline_tree
        create_task_data["trigger_method"] = TaskTriggerMethod.manual.name
        DEFAULT_NOTIFY_CONFIG = {
            "notify_type": {"fail": [], "success": []},
            "notify_receivers": {"more_receiver": "", "receiver_group": []},
        }
        create_task_data.setdefault("extra_info", {}).update(
            {"notify_config": template.notify_config or DEFAULT_NOTIFY_CONFIG}
        )
        client = TaskComponentClient(space_id=space_id)
        result = client.create_task(create_task_data)
        if not result["result"]:
            raise APIResponseError(result["message"])

        task_data = result["data"]
        event_broadcast_signal.send(
            sender=WebhookEventType.TASK_CREATE.value,
            scopes=[(WebhookScopeType.SPACE.value, str(space_id))],
            extra_info={
                "task_id": task_data["id"],
                "task_name": task_data["name"],
                "template_id": task_data["template_id"],
                "parameters": task_data["parameters"],
                "trigger_source": TaskTriggerMethod.manual.name,
            },
        )

        return Response(task_data)

    @swagger_auto_schema(method="POST", operation_description="流程批量删除", request_body=TemplateBatchDeleteSerializer)
    @action(methods=["POST"], detail=False, url_path="batch_delete")
    def batch_delete(self, request, *args, **kwargs):
        ser = TemplateBatchDeleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        space_id = ser.validated_data["space_id"]
        is_full = ser.validated_data["is_full"]
        template_ids = ser.validated_data["template_ids"]

        template_references = TemplateReference.objects.filter(subprocess_template_id__in=template_ids)
        root_template_ids = list(template_references.values_list("root_template_id", flat=True))
        if root_template_ids:
            all_needed_template_ids = set(template_ids) | set(root_template_ids)
            templates = Template.objects.filter(id__in=all_needed_template_ids, is_deleted=False)
            templates_map = {str(t.id): t.name for t in templates}

            sub_root_map = {}
            for ref in template_references:
                template_key = str(ref.subprocess_template_id)
                root_id = ref.root_template_id
                if (int(root_id) in template_ids) or (root_id not in templates_map):
                    continue
                sub_template_name = templates_map.get(template_key)
                if template_key not in sub_root_map:
                    sub_root_map[template_key] = {"sub_template_name": sub_template_name, "referenced": []}

                sub_root_map[template_key]["referenced"].append(
                    {"root_template_id": root_id, "root_template_name": templates_map.get(str(root_id))}
                )
            if sub_root_map:
                return Response(exception=True, data={"sub_root_map": dict(sub_root_map)})

        if is_full:
            update_num = Template.objects.filter(space_id=space_id, is_deleted=False).update(is_deleted=True)
        else:

            update_num = Template.objects.filter(space_id=space_id, id__in=template_ids, is_deleted=False).update(
                is_deleted=True
            )
        trigger_ids = Trigger.objects.filter(template_id__in=ser.validated_data["template_ids"]).values_list(
            "id", flat=True
        )
        Trigger.objects.batch_delete_by_ids(space_id=space_id, trigger_ids=list(trigger_ids), is_full=is_full)
        return Response({"delete_num": update_num})

    @swagger_auto_schema(method="POST", operation_description="流程模版复制", request_body=TemplateCopySerializer)
    @action(methods=["POST"], detail=False, url_path="template_copy")
    def copy_template(self, request, *args, **kwargs):
        ser = TemplateCopySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        space_id = ser.validated_data["space_id"]
        template_id = ser.validated_data["template_id"]
        copy_subprocess = ser.validated_data.get("copy_subprocess", False)
        name = ser.validated_data.get("name")
        desc = ser.validated_data.get("desc")
        try:
            template = Template.objects.copy_template(
                template_id,
                space_id,
                request.user.username,
                name,
                desc,
                copy_subprocess,
            )
        except Template.DoesNotExist:
            err_msg = f"模版不存在, space_id={space_id}, template_id={template_id}"
            logger.error(str(err_msg))
            return Response(exception=True, data={"detail": err_msg})
        except ValidationError as e:
            logger.error(str(e))
            return Response(exception=True, data={"detail": str(e)})
        return Response(data={"template_id": template.id, "template_name": template.name})


class TemplateViewSet(UserModelViewSet):
    queryset = Template.objects.filter(is_deleted=False)
    serializer_class = TemplateSerializer
    EDIT_ABOVE_ACTIONS = ["update"]
    MOCK_ABOVE_ACTIONS = ["preview_task_tree", "create_mock_task"]
    permission_classes = [AdminPermission | SpaceSuperuserPermission | TemplatePermission | TemplateMockPermission]

    @record_operation(RecordType.template.name, TemplateOperationType.update.name, TemplateOperationSource.app.name)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def analysis_constants_ref(self, request, *args, **kwargs):
        """
        @summary：计算模板中的变量引用
        @param request:
        @return:
        """
        tree = request.data
        try:
            result = analysis_pipeline_constants_ref(tree)
        except Exception:
            logger.exception("[analysis_constants_ref] error")
            raise AnalysisConstantsRefException()

        data = {"defined": {}, "nodefined": {}}
        defined_keys = tree.get("constants", {}).keys()
        if result:
            for k, v in result.items():
                if k in defined_keys:
                    data["defined"][k] = v
                else:
                    data["nodefined"][k] = v

        return Response(data)

    @swagger_auto_schema(methods=["post"], operation_description="画布排版", request_body=DrawPipelineSerializer)
    @action(methods=["POST"], detail=False)
    def draw_pipeline(self, request, *args, **kwargs):

        pipeline_tree = request.data["pipeline_tree"]
        canvas_width = int(request.data.get("canvas_width", CANVAS_WIDTH))

        kwargs = {"canvas_width": canvas_width}

        for kw in list(POSITION.keys()):
            if kw in request.data:
                kwargs[kw] = request.data[kw]
        try:
            draw_pipeline_tree(pipeline_tree, **kwargs)
        except Exception as e:
            message = _(f"流程自动排版失败: 流程排版发生异常: {e}, 请检查流程 | draw_pipeline")
            logger.exception(message)
            raise e

        return Response({"pipeline_tree": pipeline_tree})

    @swagger_auto_schema(methods=["get"], operation_description="流程操作记录")
    @action(detail=True, methods=["get"], url_path="get_template_operation_record")
    def get_task_operation_record(self, request, *args, **kwargs):
        instance_id = kwargs["pk"]
        queryset = TemplateOperationRecord.objects.filter(instance_id=instance_id)
        model_ser = TemplateOperationRecordSerializer(queryset, many=True)
        return Response(
            {
                "result": True,
                "message": "success",
                "data": model_ser.data,
            }
        )

    @action(detail=True, methods=["get"], url_path="get_space_related_configs")
    def get_space_related_configs(self, request, *args, **kwargs):
        template = self.get_object()
        try:
            data = {
                GatewayExpressionConfig.name: SpaceConfig.get_config(template.space_id, GatewayExpressionConfig.name)
            }
        except SpaceConfigDefaultValueNotExists as e:
            logger.error(f"space_id={template.space_id}, config_name={GatewayExpressionConfig.name}, error={e}")
            raise
        # 增加 uniform api 的配置项返回
        uniform_api_config = SpaceConfig.get_config(space_id=template.space_id, config_name=UniformApiConfig.name)
        if uniform_api_config:
            uniform_api_config = UniformAPIConfigHandler(uniform_api_config).handle().dict()
        data.update({UniformApiConfig.name: uniform_api_config})
        return Response(data)

    @swagger_auto_schema(methods=["post"], operation_description="流程树预览", request_body=PreviewTaskTreeSerializer)
    @action(detail=True, methods=["post"], url_path="preview_task_tree")
    def preview_task_tree(self, request, *args, **kwargs):
        template = self.get_object()
        serializer = PreviewTaskTreeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appoint_node_ids = serializer.validated_data["appoint_node_ids"]
            version = serializer.validated_data.get("version")
            pipeline_tree = template.get_pipeline_tree_by_version(version)
            if not serializer.validated_data["is_all_nodes"]:
                exclude_task_nodes_id = PipelineTemplateWebPreviewer.get_template_exclude_task_nodes_with_appoint_nodes(
                    pipeline_tree, appoint_node_ids
                )
            else:
                exclude_task_nodes_id = None
            data = preview_template_tree(pipeline_tree, exclude_task_nodes_id)
        except Exception as e:
            message = f"[preview task tree] error: {e}"
            logger.exception(message)
            raise

        mock_data_instances = TemplateMockData.objects.filter(
            template_id=template.id, space_id=template.space_id, node_id__in=appoint_node_ids
        )
        mock_data = TemplateMockDataSerializer(instance=mock_data_instances, many=True)
        data["mock_data"] = mock_data.data
        data["version"] = template.version
        data["outputs"] = template.outputs(version)
        return Response(data)

    @swagger_auto_schema(
        method="POST", operation_description="创建Mock任务", request_body=CreateMockTaskWithPipelineTreeSerializer
    )
    @action(methods=["POST"], detail=True, url_path="create_mock_task")
    def create_mock_task(self, request, *args, **kwargs):
        template = self.get_object()
        ser = CreateMockTaskWithPipelineTreeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        include_node_ids = ser.validated_data.get("include_node_ids", [])
        pipeline_tree = ser.validated_data["pipeline_tree"]

        if include_node_ids:
            exclude_task_nodes_id = PipelineTemplateWebPreviewer.get_template_exclude_task_nodes_with_appoint_nodes(
                pipeline_tree, include_node_ids
            )
            PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(
                pipeline_tree=pipeline_tree, exclude_task_nodes_id=exclude_task_nodes_id
            )

        create_task_data = dict(ser.data)
        create_task_data.update(
            {
                "template_id": template.id,
                "space_id": template.space_id,
                "scope_type": template.scope_type,
                "scope_value": template.scope_value,
                "pipeline_tree": pipeline_tree,
                "mock_data": ser.validated_data["mock_data"],
                "create_method": "MOCK",
                "trigger_method": TaskTriggerMethod.manual.name,
            }
        )
        DEFAULT_NOTIFY_CONFIG = {
            "notify_type": {"fail": [], "success": []},
            "notify_receivers": {"more_receiver": "", "receiver_group": []},
        }
        create_task_data.setdefault("extra_info", {}).update(
            {"notify_config": template.notify_config or DEFAULT_NOTIFY_CONFIG}
        )

        client = TaskComponentClient(space_id=template.space_id)
        result = client.create_task(create_task_data)
        if not result["result"]:
            raise APIResponseError(result["message"])
        return Response(result["data"])


@method_decorator(login_exempt, name="dispatch")
class TemplateInternalViewSet(BKFLOWCommonMixin, mixins.RetrieveModelMixin, SimpleGenericViewSet):
    queryset = Template.objects.filter()
    serializer_class = TemplateSerializer
    permission_classes = [AdminPermission | AppInternalPermission]

    @action(methods=["GET"], detail=True)
    def get_subproc_data(self, request, *args, **kwargs):
        version = request.query_params.get("version")
        template = self.get_object()
        subproc_data = self.get_serializer(template).data
        # 去除子流程中未被引用的变量
        pipeline_tree = template.get_pipeline_tree_by_version(version)
        pre_pipeline_tree = deepcopy(pipeline_tree)
        PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(pre_pipeline_tree)
        subproc_data["pipeline_tree"] = pre_pipeline_tree
        return Response(subproc_data)


class TemplateMockDataViewSet(
    BKFLOWCommonMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    SimpleGenericViewSet,
):
    DEFAULT_PERMISSION = TemplateRelatedResourcePermission.MOCK_PERMISSION

    queryset = TemplateMockData.objects.filter()
    filter_backends = [DjangoFilterBackend]
    serializer_class = TemplateMockDataSerializer
    permission_classes = [AdminPermission | SpaceSuperuserPermission | TemplateRelatedResourcePermission]

    @swagger_auto_schema(
        query_serializer=TemplateMockDataQuerySerializer,
        responses={200: TemplateMockDataListSerializer},
    )
    def list(self, request, *args, **kwargs):
        ser = TemplateMockDataQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        mock_data = TemplateMockData.objects.filter(**ser.validated_data).all()
        response_ser = TemplateMockDataSerializer(mock_data, many=True)
        return Response(response_ser.data)

    @swagger_auto_schema(
        methods=["post"],
        request_body=TemplateMockDataBatchCreateSerializer,
        responses={200: TemplateMockDataListSerializer},
    )
    @action(methods=["post"], detail=False)
    def batch_create(self, request, *args, **kwargs):
        ser = TemplateMockDataBatchCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        operator = request.user.username
        space_id = ser.validated_data["space_id"]
        template_id = ser.validated_data["template_id"]
        mock_data = ser.validated_data["data"]
        objs = TemplateMockData.objects.batch_create(operator, space_id, template_id, mock_data)
        response_ser = TemplateMockDataSerializer(objs, many=True)
        return Response(response_ser.data)

    @swagger_auto_schema(
        methods=["post"],
        request_body=TemplateMockDataBatchCreateSerializer,
        responses={200: TemplateMockDataListSerializer},
    )
    @action(methods=["post"], detail=False)
    def batch_update(self, request, *args, **kwargs):
        ser = TemplateMockDataBatchCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        operator = request.user.username
        space_id = ser.validated_data["space_id"]
        template_id = ser.validated_data["template_id"]
        mock_data = ser.validated_data["data"]
        objs = TemplateMockData.objects.batch_update(operator, space_id, template_id, mock_data)
        response_ser = TemplateMockDataSerializer(objs, many=True)
        return Response(response_ser.data)


class TemplateMockSchemeFilterSet(FilterSet):
    class Meta:
        model = TemplateMockScheme
        fields = {
            "space_id": ["exact"],
            "template_id": ["exact"],
            "operator": ["exact"],
        }


class TemplateMockSchemeViewSet(
    BKFLOWCommonMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    SimpleGenericViewSet,
):
    DEFAULT_PERMISSION = TemplateRelatedResourcePermission.MOCK_PERMISSION

    queryset = TemplateMockScheme.objects.filter()
    serializer_class = TemplateMockSchemeSerializer
    permission_classes = [AdminPermission | SpaceSuperuserPermission | TemplateRelatedResourcePermission]
    filter_class = TemplateMockSchemeFilterSet

    def perform_create(self, serializer):
        if TemplateMockScheme.objects.filter(
            space_id=serializer.validated_data["space_id"], template_id=serializer.validated_data["template_id"]
        ).exists():
            msg = (
                f"template mock scheme with space id {serializer.validated_data['space_id']} and "
                f"template id {serializer.validated_data['template_id']} has already existed."
            )
            logger.error(msg)
            raise ValidationError(msg)
        user = serializer.context.get("request").user
        serializer.save(operator=user.username)

    def perform_update(self, serializer):
        user = serializer.context.get("request").user
        serializer.save(operator=user.username)


class TemplateMockTaskViewSet(mixins.ListModelMixin, GenericViewSet):
    DEFAULT_PERMISSION = TemplateRelatedResourcePermission.MOCK_PERMISSION
    permission_classes = [AdminPermission | SpaceSuperuserPermission | TemplateRelatedResourcePermission]

    @swagger_auto_schema(query_serializer=TemplateRelatedResourceSerializer)
    def list(self, request, *args, **kwargs):
        ser = TemplateRelatedResourceSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        space_id, template_id = ser.validated_data["space_id"], ser.validated_data["template_id"]
        client = TaskComponentClient(space_id=space_id)
        result = client.task_list(data={"template_id": template_id, "space_id": space_id, "create_method": "MOCK"})
        return Response(result)
