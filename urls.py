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

from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.views import static
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from bkflow.utils.django_error_hanlder import page_not_found

urlpatterns = [
    url(r"^bkflow_admin/", admin.site.urls),
    url(r"^", include("bkflow.urls")),
    url(r"^apigw/", include("bkflow.apigw.urls")),
    url(r"^account/", include("blueapps.account.urls")),
    url(r"^i18n/", include("django.conf.urls.i18n")),
]

if settings.IS_LOCAL:
    urlpatterns += [
        # media
        url(r"^media/(?P<path>.*)$", static.serve, {"document_root": settings.MEDIA_ROOT}),
        url("favicon.ico", static.serve, {"document_root": settings.STATIC_ROOT, "path": "core/images/bk_sops.png"}),
    ]
    if not settings.DEBUG:
        urlpatterns += [
            url(r"^static/(?P<path>.*)$", static.serve, {"document_root": settings.STATIC_ROOT}),
        ]

handler404 = page_not_found

schema_view = get_schema_view(
    openapi.Info(
        title="BK-FLOW API",
        default_version="v1",
        description="BKFlow API文档，接口返回中默认带有result、data、message等字段，如果响应体中没有体现，则说明响应体只展示了其中data字段的内容。",
    ),
    public=True,
    permission_classes=(permissions.IsAdminUser,),
)


if settings.ENVIRONMENT != "production" or settings.ENABLE_SWAGGER_UI:
    urlpatterns += [
        url(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
        url(r"^swagger/$", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
        url(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    ]
