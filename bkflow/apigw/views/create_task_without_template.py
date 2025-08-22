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
from bkflow.apigw.serializers.task import CreateTaskWithoutTemplateSerializer
from bkflow.constants import TaskTriggerMethod
from bkflow.contrib.api.collections.task import TaskComponentClient


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def create_task_without_template(request, space_id):
    data = json.loads(request.body)
    ser = CreateTaskWithoutTemplateSerializer(data=data)
    ser.is_valid(raise_exception=True)

    create_task_data = dict(ser.validated_data)
    create_task_data["space_id"] = space_id
    DEFAULT_NOTIFY_CONFIG = {
        "notify_type": {"fail": [], "success": []},
        "notify_receivers": {"more_receiver": "", "receiver_group": []},
    }
    notify_config = create_task_data.pop("notify_config", {}) or DEFAULT_NOTIFY_CONFIG
    create_task_data.setdefault("extra_info", {}).update(
        {"notify_config": notify_config, "create_source": TaskTriggerMethod.api.name}
    )

    client = TaskComponentClient(space_id=space_id)
    result = client.create_task(create_task_data)
    return result
