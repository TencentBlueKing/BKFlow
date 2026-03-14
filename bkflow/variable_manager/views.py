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
from django_filters import FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.constants import VariableType
from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.utils.permissions import AdminPermission, AppInternalPermission
from bkflow.utils.views import AdminModelViewSet
from bkflow.variable_manager.models import VariableManager
from bkflow.variable_manager.serializers import VariableManagerSerializer


class VariableFilterSet(FilterSet):
    class Meta:
        model = VariableManager
        fields = {
            "id": ["exact"],
            "space_id": ["exact"],
            "type": ["exact"],
            "key": ["exact"],
            "name": ["icontains"],
            "creator": ["exact"],
        }


class VariableViewSet(AdminModelViewSet):
    queryset = VariableManager.objects.filter(is_deleted=False)
    permission_classes = [AdminPermission | SpaceSuperuserPermission]
    serializer_class = VariableManagerSerializer
    filter_backends = [DjangoFilterBackend]
    filter_class = VariableFilterSet


@method_decorator(login_exempt, name="dispatch")
class VariableInternalViewSet(AdminModelViewSet):
    queryset = VariableManager.objects.all()
    permission_classes = [AdminPermission | AppInternalPermission]

    @action(methods=["GET"], detail=False)
    def get_variable(self, request):
        space_id = request.query_params["space_id"]
        variables = self.queryset.filter(space_id=space_id, type=VariableType.SPACE.value, is_deleted=False).only(
            "key", "value"
        )
        data = {"${_space_%s}" % c.key: c.value for c in variables}
        return Response(data)
