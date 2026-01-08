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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_task_bk_app_code, return_json_response
from bkflow.apigw.serializers.task import OperateTaskSerializer
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.utils.trace import CallFrom, append_attributes, start_trace


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_task_bk_app_code
@return_json_response
def operate_task_by_app(request, task_id, operation):
    """
    通过 bk_app_code 权限校验执行任务操作
    请求方的 bk_app_code 需要与任务所属模板绑定的 bk_app_code 一致
    """
    data = json.loads(request.body)
    ser = OperateTaskSerializer(data=data)
    ser.is_valid(raise_exception=True)

    # space_id 已经在装饰器中挂载到 request 上
    space_id = request.space_id

    with start_trace(
        "operate_task_interface", True, space_id=space_id, task_id=task_id, call_from=CallFrom.APIGW.value
    ):
        append_attributes({"operation": operation})
        client = TaskComponentClient(space_id=space_id)
        result = client.operate_task(task_id, operation, data=ser.data)
        return result
