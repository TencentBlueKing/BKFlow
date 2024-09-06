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
from urllib.parse import quote

from blueapps.account.middlewares import LoginRequiredMiddleware
from django.conf import settings
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render


def page_not_found(request, exception):
    if request.path.startswith(settings.STATIC_URL):
        return HttpResponseNotFound()

    user = LoginRequiredMiddleware().authenticate(request)

    # 未登录重定向到首页，跳到登录页面
    if not user:
        refer_url = quote(request.build_absolute_uri())
        return HttpResponseRedirect(settings.SITE_URL + "?{}={}".format(settings.PAGE_NOT_FOUND_URL_KEY, refer_url))
    request.user = user
    return render(request, "base_vue.html", {})
