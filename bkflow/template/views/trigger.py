# -*- coding: utf-8 -*-
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

from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.template.models import Trigger
from bkflow.template.serializers.trigger import (
    CreateTriggerSerializer,
    ListTriggerSerializer,
    TriggerSerializer,
)
from bkflow.utils.mixins import BKFLOWDefaultPagination
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import SimpleGenericViewSet

logger = logging.getLogger("root")


class TriggerViewSet(ModelViewSet, SimpleGenericViewSet):
    queryset = Trigger.objects.all()
    serializer_class = TriggerSerializer
    permission_classes = [AdminPermission | SpaceSuperuserPermission]
    pagination_class = BKFLOWDefaultPagination

    def get_object(self):
        serializer = ListTriggerSerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        space_id = serializer.validated_data.get("space_id")
        pk = self.kwargs.get(self.lookup_field)
        template_id = serializer.validated_data.get("template_id")

        queryset = self.queryset.filter(space_id=space_id)
        if template_id is not None:
            queryset = queryset.filter(template_id=template_id)

        obj = queryset.get(pk=pk)
        return obj

    def get_queryset(self):
        queryset = super().get_queryset()
        serializer = ListTriggerSerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)

        space_id = serializer.validated_data.get("space_id")
        queryset = queryset.filter(space_id=space_id, is_deleted=False)

        template_id = serializer.validated_data.get("template_id")
        if template_id is not None:
            queryset = queryset.filter(template_id=template_id)

        return queryset

    def create(self, request, *args, **kwargs):
        trigger_serializer = CreateTriggerSerializer(data=request.data)
        trigger_serializer.is_valid(raise_exception=True)
        trigger_data = trigger_serializer.validated_data

        space_id = trigger_serializer.validated_data.get("space_id")
        template_id = trigger_serializer.validated_data.get("template_id")

        try:
            # TODO 定时触发器
            trigger = Trigger.objects.create(
                space_id=space_id,
                template_id=template_id,
                is_enabled=trigger_data.get("is_enabled", True),
                name=trigger_data["name"],
                condition=trigger_data["condition"],
                config=trigger_data.get("config", {}),
                token=trigger_data.get("token", ""),
                type=trigger_data["type"],
                creator=request.user.username,
            )
            return Response({"id": trigger.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            err_msg = f"创建触发器失败 {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})

    def partial_update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Trigger.DoesNotExist as e:
            err_msg = f"更新触发器不存在 {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg}, status=404)

        serializer = CreateTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for attr, value in serializer.validated_data.items():
            setattr(instance, attr, value)

        instance.updated_by = request.user.username
        updated_keys = list(serializer.validated_data.keys()) + ["updated_by", "update_at"]
        try:
            instance.save(update_fields=updated_keys)
        except Exception as e:
            err_msg = f"更新触发器失败 {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg})
        return Response(status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.hard_delete()
        except Trigger.DoesNotExist as e:
            err_msg = f"删除触发器不存在 {str(e)}"
            logger.error(err_msg)
            return Response(exception=True, data={"detail": err_msg}, status=404)
        return Response()
