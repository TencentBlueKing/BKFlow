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
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from packages.bkapi.bk_cmsi.shortcuts import get_client_by_username


@login_exempt
@csrf_exempt
@require_GET
def get_msg_types(request):
    """
    获取消息类型列表
    该接口允许跨域访问，供其他平台使用SDK对接时调用
    """
    client = get_client_by_username(request.user.username, stage=settings.BK_APIGW_STAGE_NAME)
    result = client.api.v1_channels_list(headers={"X-Bk-Tenant-Id": request.user.tenant_id})
    if not result["data"]:
        result = {"result": False, "data": [], "message": "获取消息通道列表失败"}
    else:
        result = {"result": True, "data": result["data"], "message": "获取消息通道列表成功"}
    return JsonResponse(result)
