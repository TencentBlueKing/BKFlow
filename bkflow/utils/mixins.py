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

from django.utils.translation import ugettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.viewsets import GenericViewSet

from bkflow.exceptions import UserNotFound

logger = logging.getLogger("root")


class CustomViewSetMixin:
    def perform_create(self, serializer):
        """创建时补充基础Model中的字段"""
        user = serializer.context.get("request").user
        username = getattr(user, "username", None)
        if username is None:
            logger.info("[CustomViewSetMixin->perform_create] 用户名不存在")
            raise UserNotFound(_("用户名不存在"))
        serializer.save(creator=username, updated_by=username)

    def perform_update(self, serializer):
        """更新时补充基础Model中的字段"""
        user = serializer.context.get("request").user
        username = getattr(user, "username", None)
        if username is None:
            logger.info("[CustomViewSetMixin->perform_update] 用户名不存在")
            raise UserNotFound(_("用户名不存在"))
        serializer.save(updated_by=username)


class BKFLOWDefaultPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 200


class BKFLOWNoMaxLimitPagination(LimitOffsetPagination):
    default_limit = 10

    def paginate_queryset(self, queryset, request, view=None):
        # 当 limit = -1 的时候，返回所有数据
        if request.query_params.get(self.limit_query_param) == "-1":
            data = list(queryset)
            data_len = len(data)
            setattr(self, "count", data_len)
            setattr(self, "limit", data_len)
            setattr(self, "offset", 0)
            return data
        return super(BKFLOWNoMaxLimitPagination, self).paginate_queryset(queryset, request, view)


class BKFlowOrderingFilter(OrderingFilter):
    ordering_param = "order_by"


class BKFLOWCommonMixin(GenericViewSet):
    pagination_class = BKFLOWDefaultPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, BKFlowOrderingFilter)

    def get_queryset(self):
        """支持不同acton调用不同的queryset"""
        self.queryset = getattr(self, f"{self.action}_queryset", self.queryset)
        return super(BKFLOWCommonMixin, self).get_queryset()

    def get_serializer_class(self):
        """支持不同acton调用不同的serializer_class"""
        self.serializer_class = getattr(self, f"{self.action}_serializer_class", self.serializer_class)
        return super(BKFLOWCommonMixin, self).get_serializer_class()
