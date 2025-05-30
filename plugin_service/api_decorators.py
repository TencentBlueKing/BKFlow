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

import functools
import logging

from django.http import JsonResponse
from rest_framework.request import Request

from plugin_service.exceptions import PluginServiceException
from plugin_service.plugin_client import PluginServiceApiClient

from .conf import PLUGIN_CLIENT_LOGGER

logger = logging.getLogger(PLUGIN_CLIENT_LOGGER)


def inject_plugin_client(func):
    """往request中注入client"""

    @functools.wraps(func)
    def wrapper(request: Request):
        plugin_code = request.validated_data.get("plugin_code")
        try:
            plugin_client = PluginServiceApiClient(plugin_code)
        except PluginServiceException as e:
            logger.error(f"[inject_plugin_client] error: {e}")
            return JsonResponse({"message": str(e), "result": False, "data": None})
        setattr(request, "plugin_client", plugin_client)
        return func(request)

    return wrapper


def validate_params(serializer_cls):
    """利用Serializer对请求参数进行校验"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(request: Request):
            data = request.query_params if request.method == "GET" else request.data
            serializer = serializer_cls(data=data)
            serializer.is_valid(raise_exception=True)
            setattr(request, "validated_data", serializer.validated_data)
            return func(request)

        return wrapper

    return decorator
