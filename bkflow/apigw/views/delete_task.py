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

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.task import BatchTaskSerializer
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.utils.trace import CallFrom, trace_view


@csrf_exempt
@login_exempt
@require_POST
@apigw_require
@trace_view(attr_keys=["space_id"], call_from=CallFrom.APIGW.value)
@check_jwt_and_space
@return_json_response
def delete_task(request, space_id):
    """删除任务"""
    data = json.loads(request.body)
    ser = BatchTaskSerializer(data=data)
    ser.is_valid(raise_exception=True)

    data = {
        "task_ids": ser.validated_data["task_ids"],
        "is_full": ser.validated_data["is_full"],
        "space_id": space_id,
    }
    if ser.validated_data["is_full"]:
        data["is_mock"] = ser.validated_data["is_mock"]

    client = TaskComponentClient(space_id=space_id)
    result = client.batch_delete_tasks(data)

    return result
