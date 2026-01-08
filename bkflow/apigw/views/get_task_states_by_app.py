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
from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_task_bk_app_code, return_json_response
from bkflow.contrib.api.collections.task import TaskComponentClient


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_task_bk_app_code
@return_json_response
def get_task_states_by_app(request, task_id):
    """
    通过 bk_app_code 权限校验获取任务状态
    请求方的 bk_app_code 需要与任务所属模板绑定的 bk_app_code 一致
    """
    # space_id 已经在装饰器中挂载到 request 上
    space_id = request.space_id

    client = TaskComponentClient(space_id=space_id)
    data = {"space_id": space_id}
    result = client.get_task_states(task_id, data=data)
    return result
