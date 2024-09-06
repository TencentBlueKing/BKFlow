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
from django.conf import settings

import env
from bkflow.interface.models import EnvironmentVariables


def bkflow_settings(request):
    frontend_entry_url = "{}bkflow".format(settings.STATIC_URL) if settings.RUN_VER == "open" else "/static/bkflow"
    enable_notice_center = int(EnvironmentVariables.objects.get_var("ENABLE_NOTICE_CENTER", 0))
    language = request.COOKIES.get("blueking_language", "zh-cn")
    run_ver_key = "BKAPP_RUN_VER_NAME" if language == "zh-cn" else "BKAPP_RUN_VER_NAME_{}".format(language.upper())

    ctx = {
        "STATIC_URL": settings.STATIC_URL,
        "BK_STATIC_URL": frontend_entry_url,
        "MAX_NODE_EXECUTE_TIMEOUT": settings.MAX_NODE_EXECUTE_TIMEOUT,
        "MEMBER_SELECTOR_DATA_HOST": settings.MEMBER_SELECTOR_DATA_HOST,
        "APP_CODE": settings.APP_CODE,
        "USERNAME": request.user.username,
        "BK_DOC_URL": f"{env.BK_DOC_CENTER_HOST}/markdown/ZH/BKFlow/1.8/UserGuide/Introduce/introduce.md",
        # 是否开启通知中心
        "ENABLE_NOTICE_CENTER": enable_notice_center,
        "BK_PAAS_SHARED_RES_URL": env.BKPAAS_SHARED_RES_URL,
        "APP_NAME": settings.APP_NAME,  # 应用名称
        "RUN_VER_NAME": EnvironmentVariables.objects.get_var(run_ver_key, settings.RUN_VER_NAME),
        "LOGIN_URL": env.BKFLOW_LOGIN_URL,
        "MESSAGE_HELPER_URL": env.MESSAGE_HELPER_URL,
        "BK_DOMAIN": env.BKPAAS_BK_DOMAIN,
        "BK_PAAS_ESB_HOST": env.BK_PAAS_ESB_HOST,
    }
    return ctx
