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
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.template.debug.serializers import TemplateIdQuerySerializer
from bkflow.template.debug.service import DebugService
from bkflow.template.permissions import TemplateRelatedResourcePermission
from bkflow.utils.permissions import AdminPermission


class DebugViewSet(GenericViewSet):
    permission_classes = [AdminPermission | SpaceSuperuserPermission | TemplateRelatedResourcePermission]

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
