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

import django_filters
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.db import DatabaseError
from django.db.models import Q
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from webhook.base_models import Scope
from webhook.signals import event_broadcast_signal

from bkflow.apigw.serializers.credential import (
    CreateCredentialSerializer,
    UpdateCredentialSerializer,
)
from bkflow.apigw.serializers.space import CreateSpaceSerializer
from bkflow.constants import WebhookScopeType
from bkflow.exceptions import APIRequestError
from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    SpaceConfigHandler,
    SuperusersConfig,
)
from bkflow.space.exceptions import SpaceConfigDefaultValueNotExists
from bkflow.space.models import (
    Credential,
    CredentialType,
    Space,
    SpaceConfig,
    SpaceCreateType,
)
from bkflow.space.permissions import (
    SpaceConfigExemptionPermission,
    SpaceExemptionPermission,
    SpaceSuperuserPermission,
)
from bkflow.space.serializers import (
    CredentialBaseQuerySerializer,
    CredentialSerializer,
    SpaceConfigBaseQuerySerializer,
    SpaceConfigBatchApplySerializer,
    SpaceConfigSerializer,
    SpaceSerializer,
)
from bkflow.utils.api_client import ApiGwClient, HttpRequestResult
from bkflow.utils.mixins import BKFLOWDefaultPagination
from bkflow.utils.permissions import AdminPermission, AppInternalPermission
from bkflow.utils.views import AdminModelViewSet, SimpleGenericViewSet

logger = logging.getLogger("root")


class CredentialFilterSet(FilterSet):
    class Meta:
        model = Credential
        fields = {"space_id": ["exact"], "name": ["exact"], "type": ["exact"]}


@method_decorator(login_exempt, name="dispatch")
class CredentialViewSet(AdminModelViewSet):
    queryset = Credential.objects.filter(is_deleted=False)
    serializer_class = CredentialSerializer
    permission_classes = [AdminPermission | AppInternalPermission]
    filter_backends = [DjangoFilterBackend]
    filter_class = CredentialFilterSet

    @action(detail=False, methods=["GET"])
    def get_api_gateway_credential(self, request, *args, **kwargs):
        space_id = request.query_params.get("space_id")
        try:
            api_gateway_credential_name = SpaceConfig.get_config(space_id, ApiGatewayCredentialConfig.name)
            credential = self.queryset.get(
                space_id=space_id, name=api_gateway_credential_name, type=CredentialType.BK_APP.value
            )
        except (Credential.DoesNotExist, SpaceConfigDefaultValueNotExists) as e:
            logger.exception("CredentialViewSet 获取空间下的凭证异常, space_id={}, err={}, ".format(space_id, e))
            return Response({})

        return Response(credential.value)


class SpaceFilterSet(FilterSet):
    id_or_name = django_filters.CharFilter(method="filter_by_id_or_name")

    class Meta:
        model = Space
        fields = {"id": ["exact"], "name": ["exact", "icontains"]}

    @staticmethod
    def filter_by_id_or_name(queryset, name, value):
        if value:
            filter_qs = Q(name__icontains=value)
            if value.isdigit():
                filter_qs = filter_qs | Q(id=value)
            return queryset.filter(filter_qs)
        return queryset


class SpaceViewSet(AdminModelViewSet):
    queryset = Space.objects.filter(is_deleted=False)
    serializer_class = SpaceSerializer
    filter_backends = [DjangoFilterBackend]
    filter_class = SpaceFilterSet
    pagination_class = BKFLOWDefaultPagination
    permission_classes = [AdminPermission | SpaceSuperuserPermission | SpaceExemptionPermission]

    def create(self, request, *args, **kwargs):
        serializer = CreateSpaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not request.user.is_superuser:
            app_code = serializer.validated_data["app_code"]
            url = f'{settings.PAASV3_APIGW_API_HOST.rstrip("/")}/prod/system/uni_applications/query/by_id/'
            client = ApiGwClient()
            try:
                query_data: HttpRequestResult = client.request(url, method="GET", data={"id": app_code})
            except APIRequestError as e:
                logger.exception(f"SpaceViewSet 创建空间异常, app_code={app_code}, err={e}")
                raise APIException(e)
            if query_data.result is False:
                raise APIException(query_data.message)
            if not query_data.json_resp[0] or request.user.username not in query_data.json_resp[0]["developers"]:
                logger.error(f"app info error: {query_data.json_resp}")
                raise APIException(f"{request.user.username} is not the developer of the app {app_code}")

        request.data.update({"create_type": SpaceCreateType.WEB.value, "creator": request.user.username})
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            SpaceConfig.objects.batch_update(
                space_id=response.data.get("id"), configs={"superusers": [request.user.username]}
            )
        return response

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if not request.user.is_superuser:
            space_ids = SpaceConfig.objects.get_space_ids_of_superuser(request.user.username)
            queryset = queryset.filter(id__in=space_ids)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def get_meta(self, request, *args, **kwargs):
        meta_info = {}
        for f in Space._meta.get_fields():
            meta_info[f.name] = {"verbose_name": f.verbose_name}
            if getattr(f, "choices"):
                meta_info[f.name].update({"choices": [{"value": c[0], "text": c[1]} for c in f.choices]})
        return Response(meta_info)


@method_decorator(login_exempt, name="dispatch")
class SpaceInternalViewSet(AdminModelViewSet):
    queryset = Space.objects.filter(is_deleted=False)
    serializer_class = SpaceSerializer
    permission_classes = [AdminPermission | AppInternalPermission]
    CREDENTIAL_CONFIG_KEY = "default"

    @action(detail=False, methods=["POST"])
    def broadcast_task_events(self, request, *args, **kwargs):
        data = request.data
        scopes = [Scope(type=WebhookScopeType.SPACE.value, code=str(data["space_id"]))]
        event_broadcast_signal.send(sender=data["event"], scopes=scopes, extra_info=data.get("extra_info"))
        return Response("success")

    def get_credential_config(self, config, space_id, scope):
        try:
            credential_name = config
            # 如果是字符串直接查询对应凭证 否则提取对应 {scope_type}_{scope_id} 下的内容
            if isinstance(config, dict):
                # 提取过程中 需要考虑划分到其他没有配置凭证的 {scope_type}_{scope_id} 下的流程 使用 default 默认凭证
                credential_name = config.get(scope, config.get(self.CREDENTIAL_CONFIG_KEY))
            value = Credential.objects.get(
                space_id=space_id, name=credential_name, type=CredentialType.BK_APP.value
            ).value
        except (Credential.DoesNotExist, SpaceConfigDefaultValueNotExists) as e:
            logger.exception("CredentialViewSet 获取空间下的凭证异常, space_id={}, err={}, ".format(space_id, e))
            value = {}
        return value

    @action(detail=False, methods=["GET"])
    def get_space_infos(self, request, *args, **kwargs):
        data = request.query_params
        configs = {}
        for config_name in data.get("config_names", "").split(","):
            if config_name == "credential":
                value = SpaceConfig.get_config(data["space_id"], ApiGatewayCredentialConfig.name)
                scope = data.get("scope", self.CREDENTIAL_CONFIG_KEY)
                value = self.get_credential_config(config=value, space_id=data["space_id"], scope=scope)
            else:
                value = SpaceConfig.get_config(space_id=data["space_id"], config_name=config_name)
            configs[config_name] = value
        infos = {
            "configs": configs,
        }

        return Response(infos)


class SpaceConfigFilterSet(FilterSet):
    class Meta:
        model = SpaceConfig
        fields = {"space_id": ["exact"], "name": ["exact"]}


class SpaceConfigAdminViewSet(ModelViewSet, SimpleGenericViewSet):
    queryset = SpaceConfig.objects.all()
    serializer_class = SpaceConfigSerializer
    permission_classes = [AdminPermission | SpaceSuperuserPermission]

    def list(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            # 空间管理员不应该调用
            raise PermissionDenied()
        return super().list(request, *args, **kwargs)

    def process_config(self, config_dict):
        if not config_dict.get("default_value"):
            config_dict["default_value"] = None
        return config_dict

    @swagger_auto_schema(method="get", operation_summary="获取所有空间配置元信息", query_serializer=SpaceConfigBaseQuerySerializer)
    @action(detail=False, methods=["GET"])
    def config_meta(self, request, *args, **kwargs):
        configs = SpaceConfigHandler.get_all_configs()
        return Response({name: self.process_config(config.to_dict()) for name, config in configs.items()})

    @swagger_auto_schema(
        method="post",
        operation_summary="批量应用空间配置",
        request_body=SpaceConfigBatchApplySerializer,
    )
    @action(detail=False, methods=["POST"])
    def batch_apply(self, request, *args, **kwargs):
        ser = SpaceConfigBatchApplySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        space_id, configs = ser.validated_data["space_id"], ser.validated_data["configs"]
        SpaceConfig.objects.batch_update(space_id=space_id, configs=configs)
        return Response(SpaceConfig.objects.get_space_config_info(space_id=space_id, simplified=False))

    @swagger_auto_schema(method="get", operation_summary="获取空间下所有配置", query_serializer=SpaceConfigBaseQuerySerializer)
    @action(detail=False, methods=["GET"])
    def get_all_space_configs(self, request, *args, **kwargs):
        ser = SpaceConfigBaseQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        return Response(
            SpaceConfig.objects.get_space_config_info(space_id=ser.validated_data["space_id"], simplified=False)
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            SpaceConfig.objects.create_space_config(space_id=request.data["space_id"], data=serializer.validated_data)
        except Exception as e:
            err_msg = f"创建空间配置失败: {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})
        return Response(serializer.validated_data)

    def partial_update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            SpaceConfig.objects.update_space_config(
                space_id=request.data["space_id"], data=serializer.validated_data, instance=instance
            )
            return Response(serializer.validated_data)
        except Exception as e:
            err_msg = f"更新空间配置失败: {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})

    def destroy(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        try:
            SpaceConfig.objects.delete_space_config(pk=pk)
            return Response(pk)
        except Exception as e:
            err_msg = f"删除空间配置失败: {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})


class CredentialConfigAdminViewSet(ModelViewSet, SimpleGenericViewSet):
    """
    凭证接口
    """

    queryset = Credential.objects.all()
    serializer_class = CredentialSerializer
    permission_classes = [AdminPermission | SpaceSuperuserPermission]
    pagination_class = BKFLOWDefaultPagination

    def get_object(self):
        serializer = CredentialBaseQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        space_id = serializer.validated_data.get("space_id")

        pk = self.kwargs.get(self.lookup_field)
        obj = self.queryset.get(pk=pk, space_id=space_id)
        return obj

    def get_queryset(self):
        queryset = super().get_queryset()
        serializer = CredentialBaseQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        space_id = serializer.validated_data.get("space_id")
        queryset = queryset.filter(space_id=space_id, is_deleted=False)
        return queryset

    def create(self, request, *args, **kwargs):
        credential_serializer = CreateCredentialSerializer(data=request.data)
        credential_serializer.is_valid(raise_exception=True)
        credential_data = credential_serializer.validated_data

        serializer = CredentialBaseQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        space_id = serializer.validated_data.get("space_id")
        try:
            credential = Credential.create_credential(
                space_id=space_id,
                name=credential_data["name"],
                type=credential_data["type"],
                content=credential_data["content"],
                creator=request.user.username,
                desc=credential_data.get("desc"),
            )
        except DatabaseError as e:
            err_msg = f"创建凭证失败 {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})
        response_serializer = CredentialSerializer(credential)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Credential.DoesNotExist as e:
            err_msg = f"更新凭证不存在 {str(e)}"
            logger.error(err_msg)
            return Response(err_msg, status=404)

        serializer = UpdateCredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for attr, value in serializer.validated_data.items():
            setattr(instance, attr, value)

        instance.updated_by = request.user.username
        updated_keys = list(serializer.validated_data.keys()) + ["updated_by", "update_at"]
        try:
            instance.save(update_fields=updated_keys)
        except DatabaseError as e:
            err_msg = f"更新凭证失败 {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})
        # 序列化更新后的对象
        response_serializer = CredentialSerializer(instance)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.hard_delete()
        except Credential.DoesNotExist as e:
            err_msg = f"删除凭证不存在 {str(e)}"
            logger.error(err_msg)
            return Response(err_msg, status=404)
        return Response()


class SpaceConfigViewSet(ModelViewSet, SimpleGenericViewSet):
    queryset = SpaceConfig.objects.all()
    serializer_class = SpaceConfigSerializer
    permission_classes = [SpaceConfigExemptionPermission | AdminPermission | SpaceSuperuserPermission]
    pagination_class = BKFLOWDefaultPagination

    def process_config(self, config_dict):
        if not config_dict.get("default_value"):
            config_dict["default_value"] = None
        return config_dict

    @action(methods=["GET"], detail=False)
    def get_control_config(self, request, *args, **kwargs):
        try:
            configs = SpaceConfigHandler.get_control_configs()
            return Response({name: self.process_config(config.to_dict()) for name, config in configs.items()})
        except Exception as e:
            err_msg = f"获取控制配置失败 {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})

    @action(methods=["GET"], detail=True)
    def check_space_config(self, request, *args, **kwargs):
        space_id = kwargs.get("pk")
        name = request.query_params.get("name")
        if not name:
            return Response(exception=True, data={"detail": "name 配置名称不能为空"})
        try:
            superusers = SpaceConfig.get_config(space_id=space_id, config_name=SuperusersConfig.name)
            if request.user.username not in superusers and not getattr(
                SpaceConfigHandler.get_config(name), "control", False
            ):
                return Response(exception=True, data={"detail": "您无权限查看此配置"})
            config = SpaceConfig.get_config(space_id, name)
            return Response({"value": config}, status=200)
        except Exception as e:
            err_msg = f"检查空间配置失败：space_id: {space_id}, name: {name}, error: {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})
