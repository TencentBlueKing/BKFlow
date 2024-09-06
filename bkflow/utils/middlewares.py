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
import uuid

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework import serializers

from bkflow.exceptions import BKFLOWException, ValidationError
from bkflow.utils import err_code
from bkflow.utils.logging import local


class AppInfoInjectMiddleware(MiddlewareMixin):
    """用于注入内部模块间调用的权限校验所需的信息"""

    def process_request(self, request):
        request.app_internal_token = request.META.get(settings.APP_INTERNAL_TOKEN_REQUEST_META_KEY, "")


class ExceptionMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, BKFLOWException):
            return JsonResponse(
                {
                    "result": False,
                    "message": str(exception),
                    "code": exception.CODE,
                    "data": None,
                }
            )
        # 全局处理序列化器的异常
        elif isinstance(exception, serializers.ValidationError):
            # 序列化器异常转换为我们的code
            return JsonResponse(
                {
                    "result": False,
                    "message": str(exception),
                    "code": ValidationError.CODE,
                    "data": None,
                }
            )

        return JsonResponse(
            {
                "result": False,
                "message": str(exception),
                "code": err_code.ERROR.code,
                "data": None,
            }
        )


class TraceIDInjectMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.trace_id = request.META.get("HTTP_TRACEPARENT", uuid.uuid4().hex)
        local.trace_id = request.trace_id

    def process_response(self, request, response):
        delattr(local, "trace_id")
        if (
            isinstance(response, HttpResponse)
            and response.get("Content-Type") == "application/json"
            and hasattr(request, "trace_id")
        ):
            response.setdefault("Bkflow-Engine-Trace-Id", request.trace_id)
        return response
