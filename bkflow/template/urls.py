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

from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter

from bkflow.template.views.template import (
    AdminTemplateViewSet,
    TemplateInternalViewSet,
    TemplateMockDataViewSet,
    TemplateMockSchemeViewSet,
    TemplateMockTaskViewSet,
    TemplateViewSet,
)
from bkflow.template.views.variable import VariableViewSet

router = DefaultRouter()
router.register(r"^variable", VariableViewSet, basename="variable")
router.register(r"^admin", AdminTemplateViewSet, basename="admin_template")
router.register(r"^template_mock_data", TemplateMockDataViewSet, basename="template_mock_data")
router.register(r"^template_mock_scheme", TemplateMockSchemeViewSet, basename="template_mock_scheme")
router.register(r"^template_mock_task", TemplateMockTaskViewSet, basename="template_mock_task")
router.register(r"", TemplateViewSet, basename="template")
router.register(r"^internal", TemplateInternalViewSet, basename="template_id")

urlpatterns = [
    url(r"^", include(router.urls)),
]
