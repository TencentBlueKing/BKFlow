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

from bkflow_dmn.api import decide_single_table
from blueapps.account.decorators import login_exempt
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from bkflow.decision_table.models import DecisionTable
from bkflow.decision_table.permissions import DecisionTableUserPermission
from bkflow.decision_table.serializers import (
    DecisionTableEvaluationSerializer,
    DecisionTableSerializer,
)
from bkflow.decision_table.table_parser import DecisionTableParser
from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.utils.mixins import BKFLOWCommonMixin
from bkflow.utils.permissions import AdminPermission, AppInternalPermission
from bkflow.utils.views import AdminModelViewSet, UserModelViewSet

logger = logging.getLogger(__name__)


class AdminDecisionTableFilterSet(FilterSet):
    class Meta:
        model = DecisionTable
        fields = {
            "id": ["exact"],
            "space_id": ["exact"],
            "template_id": ["exact"],
            "name": ["exact", "icontains"],
            "creator": ["exact"],
            "updated_by": ["exact"],
            "scope_type": ["exact"],
            "scope_value": ["exact"],
            "create_at": ["gte", "lte"],
            "update_at": ["gte", "lte"],
        }


@method_decorator(login_exempt, name="dispatch")
class DecisionTableInternalViewSet(AdminModelViewSet):
    queryset = DecisionTable.objects.filter(is_deleted=False)
    serializer_class = DecisionTableSerializer
    permission_classes = [AdminPermission | AppInternalPermission]


class DecisionTableFilterSet(FilterSet):
    class Meta:
        model = DecisionTable
        fields = {
            "space_id": ["exact"],
            "template_id": ["exact"],
        }


class DecisionTableViewSet(
    BKFLOWCommonMixin, UserModelViewSet, mixins.ListModelMixin, mixins.DestroyModelMixin, mixins.CreateModelMixin
):
    queryset = DecisionTable.objects.filter(is_deleted=False)
    serializer_class = DecisionTableSerializer
    permission_classes = [DecisionTableUserPermission | AdminPermission | SpaceSuperuserPermission]
    filter_backends = [DjangoFilterBackend]
    filter_class = DecisionTableFilterSet

    def _check_before_operation(self):
        decision_table = self.get_object()
        try:
            used, matched_node_ids = decision_table.check_used_by_template()
        except ValueError as e:
            raise APIException(detail=f"[update check_used_by_template]{e}")
        if used:
            raise APIException(
                detail=f"[update error] the decision table has already been used in template nodes {matched_node_ids}"
            )

    @staticmethod
    def _validate_table_fields(obj_table_data: dict, ser_table_data: dict) -> bool:
        """check if the fields are different from the original table"""
        keys = ["inputs", "outputs"]
        return all(obj_table_data[key] == ser_table_data[key] for key in keys)

    def update(self, request, *args, **kwargs):
        try:
            self._check_before_operation()
        except APIException:
            # only update rules if the table is not used in template
            partial = kwargs.pop("partial", False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            if not self._validate_table_fields(instance.data, serializer.validated_data["data"]):
                raise
            instance.data = serializer.validated_data["data"]
            instance.save(update_fields=["data"])
            return Response(serializer.data)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._check_before_operation()
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(methods=["get"], operation_description="查询特定的决策表是否被对应流程的节点所引用")
    @action(methods=["GET"], detail=True)
    def check_decision_tabel_used_by_template(self, request, *args, **kwargs):
        decision_table = self.get_object()
        try:
            used, matched_node_ids = decision_table.check_used_by_template()
        except ValueError as e:
            raise APIException(detail=f"[check_decision_tabel_used_by_template]{e}")
        return Response({"has_used": used, "node_ids": matched_node_ids})

    @swagger_auto_schema(
        method="post",
        operation_summary="evaluate decision table with facts",
        request_body=DecisionTableEvaluationSerializer,
    )
    @action(detail=True, methods=["post"])
    def evaluate(self, request, *args, **kwargs):
        ser = DecisionTableEvaluationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        table_obj = self.get_object()
        facts, strict_mode = ser.validated_data["facts"], ser.validated_data["strict_mode"]
        try:
            parser = DecisionTableParser(title=table_obj.name, decision_table=table_obj.data)
            decision_table = parser.parse()
            outputs = decide_single_table(decision_table=decision_table, facts=facts, strict_mode=strict_mode)
        except Exception as e:
            msg = f"[evaluate decision table] error: {e}"
            logger.exception(msg)
            return Response({"outputs": None, "error_hint": msg})

        return Response({"outputs": outputs, "error_hint": ""})


class DecisionTableAdminViewSet(DecisionTableViewSet):
    permission_classes = [SpaceSuperuserPermission | AdminPermission]
    filter_class = AdminDecisionTableFilterSet
