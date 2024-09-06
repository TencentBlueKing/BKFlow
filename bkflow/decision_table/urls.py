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
from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter

from bkflow.decision_table.views import (
    DecisionTableAdminViewSet,
    DecisionTableInternalViewSet,
    DecisionTableViewSet,
)

drf_router = DefaultRouter()
drf_router.register(r"user", DecisionTableViewSet, basename="decision_table")
drf_router.register(r"admin", DecisionTableAdminViewSet, basename="admin_decision_table")
drf_router.register(r"internal", DecisionTableInternalViewSet, basename="internal_decision_table")


urlpatterns = [
    url(r"", include(drf_router.urls)),
]
