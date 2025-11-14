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

from bkflow.space.views import (
    CredentialConfigAdminViewSet,
    CredentialViewSet,
    SpaceConfigAdminViewSet,
    SpaceConfigViewSet,
    SpaceInternalViewSet,
    SpaceViewSet,
)

router = DefaultRouter()
router.register(r"", SpaceViewSet)
router.register("credential", CredentialViewSet)
router.register(r"internal", SpaceInternalViewSet, basename="internal")
router.register(r"config", SpaceConfigViewSet, basename="config")

admin_router = DefaultRouter()
admin_router.register(r"space_config", SpaceConfigAdminViewSet, basename="space_config")
admin_router.register(r"credential_config", CredentialConfigAdminViewSet, basename="credential_config")

urlpatterns = [
    url(r"^", include(router.urls)),
    url(r"^admin/", include(admin_router.urls)),
]
