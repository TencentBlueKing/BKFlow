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
import json
import logging
import traceback

from blueapps.account import ConfFixture
from blueapps.account.decorators import login_exempt
from blueapps.account.handlers.response import ResponseHandler
from blueapps.utils import get_client_by_request
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.space.configs import SuperusersConfig
from bkflow.space.models import Space, SpaceConfig

logger = logging.getLogger("root")


def home(request):
    return render(request, "base_vue.html")


def user_exit(request):
    logout(request)
    # 验证不通过，需要跳转至统一登录平台
    request.path = request.path.replace("logout", "")
    handler = ResponseHandler(ConfFixture, settings)
    return handler.build_401_response(request)


def is_admin_or_space_superuser(request):
    """
    判断是否是管理员或者空间超级管理员
    """
    space_ids = SpaceConfig.objects.get_space_ids_of_superuser(request.user.username)
    is_space_superuser = (
        True if (space_ids and Space.objects.filter(id__in=space_ids, is_deleted=False).exists()) else False
    )

    return JsonResponse(
        {
            "result": True,
            "data": {"is_admin": request.user.is_superuser, "is_space_superuser": is_space_superuser},
            "message": "",
        }
    )


def is_admin_or_current_space_superuser(request):
    """
    判断是否是管理员或者当前空间超级管理员
    """
    space_id = request.GET.get("space_id")

    if space_id is None:
        return JsonResponse({"result": False, "data": None, "message": "space_id is required"})

    is_space_superuser = SpaceConfig.objects.filter(
        space_id=space_id, name=SuperusersConfig.name, json_value__contains=request.user.username
    ).exists()

    return JsonResponse(
        {
            "result": True,
            "data": {"is_admin": request.user.is_superuser, "is_space_superuser": is_space_superuser},
            "message": "",
        }
    )


@require_GET
def get_msg_types(request):
    client = get_client_by_request(request)
    result = client.cmsi.get_msg_type()
    return JsonResponse(result)


@login_exempt
@csrf_exempt
@require_POST
def callback(request, token):
    try:
        f = Fernet(settings.CALLBACK_KEY)
        back_load = f.decrypt(bytes(token, encoding="utf8")).decode().split(":")
        # 不带 root_pipeline_id 的回调 payload
        [space_id, task_id, node_id, node_version] = back_load[:4]
    except Exception:
        logger.warning("invalid token %s" % token)
        return JsonResponse({"result": False, "message": "invalid token"}, status=400)
    try:
        callback_data = json.loads(request.body)
    except Exception:
        message = _("节点回调失败: 无效的请求, 请重试. 如持续失败可联系管理员处理. {msg} | api callback").format(msg=traceback.format_exc())
        logger.error(message)
        return JsonResponse({"result": False, "message": message}, status=400)

    client = TaskComponentClient(space_id=space_id)

    data = {"version": node_version, "data": callback_data}
    try:
        resp = client.node_operate(task_id=task_id, node_id=node_id, operation="callback", data=data)
    except Exception:
        message = _("节点回调失败: 请求失败task模块失败. {msg} | api callback").format(msg=traceback.format_exc())
        logger.error(message)
        return JsonResponse({"result": False, "message": message}, status=400)

    logger.info(
        "[callback] resp, space_id={}, task_id={}, node_id={}, resp={}".format(space_id, task_id, node_id, resp)
    )
    return JsonResponse(resp)
