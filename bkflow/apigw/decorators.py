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
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.space.models import Space
from bkflow.template.models import Template
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
                        "message": _("空间不存在，space_id={}").format(space_id),
                    },
                )
            if space.app_code != request.app.bk_app_code:
                return JsonResponse(
                    status=403,
                    data={
                        "result": False,
                        "message": _("当前应用无权操作此空间，app={}").format(request.app.bk_app_code),
                    },
                )

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def check_template_bk_app_code(view_func):
    """
    检查请求的 bk_app_code 是否与模板绑定的 bk_app_code 一致
    用于基于 bk_app_code 的流程权限控制
    @param view_func:
    @return:
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        exempt = getattr(settings, "BK_APIGW_REQUIRE_EXEMPT", False)
        if exempt:
            return view_func(request, *args, **kwargs)

        template_id = request.resolver_match.kwargs.get("template_id")
        if template_id is None:
            return JsonResponse(
                status=400,
                data={
                    "result": False,
                    "message": _("template_id 是必填参数"),
                },
            )

        template = Template.objects.filter(id=template_id, is_deleted=False).first()
        if template is None:
            return JsonResponse(
                status=404,
                data={
                    "result": False,
                    "message": _("模板不存在，template_id={}").format(template_id),
                },
            )

        # 检查模板是否绑定了 bk_app_code
        if not template.bk_app_code:
            return JsonResponse(
                status=403,
                data={
                    "result": False,
                    "message": _("模板未绑定任何 bk_app_code，template_id={}").format(template_id),
                },
            )

        # 检查请求的 bk_app_code 是否与模板绑定的 bk_app_code 一致
        request_app_code = request.app.bk_app_code
        if template.bk_app_code != request_app_code:
            return JsonResponse(
                status=403,
                data={
                    "result": False,
                    "message": _("当前应用无权操作此模板，app={}，模板绑定的 app={}").format(request_app_code, template.bk_app_code),
                },
            )

        # 将 template 和 space_id 挂载到 request 上，方便后续使用
        request.template = template
        request.space_id = template.space_id

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def check_task_bk_app_code(view_func):
    """
    检查请求的 bk_app_code 是否与任务所属模板绑定的 bk_app_code 一致
    用于基于 bk_app_code 的任务权限控制
    @param view_func:
    @return:
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        exempt = getattr(settings, "BK_APIGW_REQUIRE_EXEMPT", False)
        if exempt:
            return view_func(request, *args, **kwargs)

        task_id = request.resolver_match.kwargs.get("task_id")
        if task_id is None:
            return JsonResponse(
                status=400,
                data={
                    "result": False,
                    "message": _("task_id 是必填参数"),
                },
            )

        # 通过 TaskComponentClient 获取任务详情（使用默认的 space_id=0 配置）
        try:
            client = TaskComponentClient(space_id=0)
            task_result = client.get_task_detail(task_id)
        except Exception as e:
            logger.exception(f"[check_task_bk_app_code] get task detail error: {e}")
            return JsonResponse(
                status=500,
                data={
                    "result": False,
                    "message": _("获取任务详情失败，task_id={}").format(task_id),
                },
            )

        if not task_result.get("result"):
            return JsonResponse(
                status=404,
                data={
                    "result": False,
                    "message": _("任务不存在，task_id={}").format(task_id),
                },
            )

        task_data = task_result.get("data", {})
        task_template_id = task_data.get("template_id")
        task_space_id = task_data.get("space_id")

        # 获取任务关联的模板
        if not task_template_id:
            return JsonResponse(
                status=403,
                data={
                    "result": False,
                    "message": _("任务未关联任何模板，task_id={}").format(task_id),
                },
            )

        template = Template.objects.filter(id=task_template_id, is_deleted=False).first()
        if template is None:
            return JsonResponse(
                status=404,
                data={
                    "result": False,
                    "message": _("任务关联的模板不存在，task_id={}，template_id={}").format(task_id, task_template_id),
                },
            )

        # 检查模板是否绑定了 bk_app_code
        if not template.bk_app_code:
            return JsonResponse(
                status=403,
                data={
                    "result": False,
                    "message": _("任务关联的模板未绑定任何 bk_app_code，task_id={}，template_id={}").format(
                        task_id, task_template_id
                    ),
                },
            )

        # 检查请求的 bk_app_code 是否与模板绑定的 bk_app_code 一致
        request_app_code = request.app.bk_app_code
        if template.bk_app_code != request_app_code:
            return JsonResponse(
                status=403,
                data={
                    "result": False,
                    "message": _("当前应用无权操作此任务，app={}，模板绑定的 app={}").format(request_app_code, template.bk_app_code),
                },
            )

        # 将 task_data, template 和 space_id 挂载到 request 上，方便后续使用
        request.task_data = task_data
        request.template = template
        request.space_id = task_space_id

        return view_func(request, *args, **kwargs)

    return _wrapped_view
