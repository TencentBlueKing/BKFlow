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
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from rest_framework import serializers

from bkflow.space.models import Space
from bkflow.utils import err_code
from bkflow.utils.drf_error_handler import format_drf_serializers_exception

logger = logging.getLogger(__name__)


def return_json_response(view_func):
    """
    将返回的dict数据转为JsonResponse
    @param view_func:
    @return:
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            result = view_func(request, *args, **kwargs)
        except serializers.ValidationError as e:
            logger.exception(f"[return_json_response] validation error: {e}")
            result = {
                "result": False,
                "message": format_drf_serializers_exception(e),
                # 需要定义返回code
                "code": err_code.VALIDATION_ERROR.code,
                "data": None,
            }
        except Exception as e:
            logger.exception(f"[return_json_response] exception: {e}")
            result = {
                "result": False,
                "message": str(e),
                # 需要定义返回code
                "code": 500,
                "data": None,
            }
        # 如果返回的是dict且request中有trace_id，则在响应中加上
        if isinstance(result, dict):
            if hasattr(request, "trace_id"):
                result["trace_id"] = request.trace_id
            result = JsonResponse(result)
        return result

    return _wrapped_view


def check_jwt_and_space(view_func):
    """
    检查请求的app_code 和 space_id 是否一致
    @param view_func:
    @return:
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        exempt = getattr(settings, "BK_APIGW_REQUIRE_EXEMPT", False)
        if exempt:
            return view_func(request, *args, **kwargs)

        space_id = request.resolver_match.kwargs.get("space_id")
        if space_id is not None:
            space = Space.objects.filter(id=space_id).first()
            if space is None:
                return JsonResponse(
                    status=403,
                    data={
                        "result": False,
                        "message": "space does not exist. space_id={}".format(space_id),
                    },
                )
            if space.app_code != request.app.bk_app_code:
                return JsonResponse(
                    status=403,
                    data={
                        "result": False,
                        "message": "The current application does not have permission to operate this space，"
                        "app={}".format(request.app.bk_app_code),
                    },
                )

        return view_func(request, *args, **kwargs)

    return _wrapped_view
