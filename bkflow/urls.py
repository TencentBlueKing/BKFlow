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
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.conf.urls import url
from django.urls import include, path, register_converter
from django.views.decorators.csrf import csrf_exempt
from pipeline.contrib.engine_admin import views as engine_admin_views
from pipeline.contrib.engine_admin.urls import EngineConverter

from module_settings import BKFLOWModuleType

urlpatterns = []

if settings.BKFLOW_MODULE.type == BKFLOWModuleType.interface:
    urlpatterns += [
        url(r"^", include("bkflow.interface.urls")),
        url(r"^api/template/", include("bkflow.template.urls")),
        url(r"^api/decision_table/", include("bkflow.decision_table.urls")),
        url(r"^api/space/", include("bkflow.space.urls")),
        url(r"^api/plugin/", include("bkflow.plugin.urls")),
        url(r"^api/bk_plugin/", include("bkflow.bk_plugin.urls")),
        url(r"^api/admin/", include("bkflow.admin.urls")),
        url(r"^api/permission/", include("bkflow.permission.urls")),
        url(r"^api/plugin_query/", include("bkflow.pipeline_plugins.query.urls")),
        url(r"^api/plugin_service/", include("plugin_service.urls")),
        url(r"^notice/", include("bk_notice_sdk.urls")),
        url(r"^version_log/", include("version_log.urls", namespace="version_log")),
    ]
elif settings.BKFLOW_MODULE.type == BKFLOWModuleType.engine:
    engine_admin_actions = [
        "task_pause",
        "task_resume",
        "task_revoke",
        "node_retry",
        "node_skip",
        "node_callback",
        "node_skip_exg",
        "node_skip_cpg",
        "node_forced_fail",
    ]
    register_converter(EngineConverter, "engine")
    engine_admin_urlpatterns = [
        path(
            f"task_engine_admin/api/v1/<engine:engine_type>/{action}/<str:instance_id>/",
            csrf_exempt(login_exempt(getattr(engine_admin_views, action))),
        )
        for action in engine_admin_actions
    ]
    urlpatterns += [
        url(r"^task/", include("bkflow.task.urls")),
    ] + engine_admin_urlpatterns
