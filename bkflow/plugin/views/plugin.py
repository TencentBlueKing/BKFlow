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

from django_filters import FilterSet
from drf_yasg.utils import swagger_auto_schema
from pipeline.component_framework.models import ComponentModel

from bkflow.plugin.serializers.comonent import (
    ComponentListQuerySerializer,
    ComponentModelDetailSerializer,
    ComponentModelListSerializer,
)
from bkflow.plugin.space_plugin_config_parser import SpacePluginConfigParser
from bkflow.space.configs import SpacePluginConfig
from bkflow.space.models import SpaceConfig
from bkflow.utils.mixins import BKFLOWCommonMixin
from bkflow.utils.views import ReadOnlyViewSet

logger = logging.getLogger("root")


class ComponentModelFilter(FilterSet):
    class Meta:
        model = ComponentModel
        fields = ["version"]


class ComponentModelSetViewSet(BKFLOWCommonMixin, ReadOnlyViewSet):
    queryset = ComponentModel.objects.filter(status=True).exclude(code__in=["remote_plugin", "uniform_api"])
    retrieve_queryset = ComponentModel.objects.filter(status=True).order_by("name")
    serializer_class = ComponentModelListSerializer
    retrieve_serializer_class = ComponentModelDetailSerializer
    filterset_class = ComponentModelFilter
    pagination_class = None
    lookup_field = "code"

    def get_queryset(self):
        queryset = super().get_queryset()
        space_id = self.request.query_params.get("space_id")
        scope_type = self.request.query_params.get("scope_type")
        scope_id = self.request.query_params.get("scope_id")
        scope_code = f"{scope_type}_{scope_id}"
        space_plugin_config = SpaceConfig.get_config(space_id=space_id, config_name=SpacePluginConfig.name)
        if space_plugin_config:
            parser = SpacePluginConfigParser(space_plugin_config)
            queryset = parser.get_filtered_plugin_qs(scope_code, queryset)
        return queryset

    @swagger_auto_schema(query_serializer=ComponentListQuerySerializer)
    def list(self, request, *args, **kwargs):
        query_ser = ComponentListQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        return super().list(request, *args, **kwargs)
