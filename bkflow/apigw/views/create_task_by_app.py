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
from webhook.signals import event_broadcast_signal

from bkflow.apigw.decorators import check_template_bk_app_code, return_json_response
from bkflow.apigw.serializers.task import CreateTaskByAppSerializer
from bkflow.constants import TaskTriggerMethod, WebhookEventType, WebhookScopeType
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.utils.trace import CallFrom, trace_view


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@trace_view(attr_keys=["template_id"], call_from=CallFrom.APIGW.value)
@check_template_bk_app_code
@return_json_response
def create_task_by_app(request, template_id):
    """
    通过 bk_app_code 权限校验创建任务
    请求方的 bk_app_code 需要与模板绑定的 bk_app_code 一致
    创建者从网关认证的用户信息中获取
    """
    data = json.loads(request.body)
    # 使用装饰器中的 template_id
    data["template_id"] = int(template_id)
    ser = CreateTaskByAppSerializer(data=data)
    ser.is_valid(raise_exception=True)

    # template 和 space_id 已经在装饰器中挂载到 request 上
    template = request.template
    space_id = request.space_id

    create_task_data = dict(ser.data)
    # 从网关认证的用户信息中获取创建者
    create_task_data["creator"] = request.user.username
    create_task_data["scope_type"] = template.scope_type
    create_task_data["scope_value"] = template.scope_value
    create_task_data["space_id"] = space_id
    create_task_data["pipeline_tree"] = template.pipeline_tree
    create_task_data["trigger_method"] = TaskTriggerMethod.api.name
    DEFAULT_NOTIFY_CONFIG = {
        "notify_type": {"fail": [], "success": []},
        "notify_receivers": {"more_receiver": "", "receiver_group": []},
    }
    create_task_data.setdefault("extra_info", {}).update(
        {"notify_config": template.notify_config or DEFAULT_NOTIFY_CONFIG}
    )

    # 将credentials放入extra_info的custom_context中，以便通过TaskContext和parent_data.inputs获取
    # custom_context用于统一管理自定义上下文数据
    credentials = ser.data.get("credentials", {})
    if credentials:
        create_task_data.setdefault("extra_info", {}).setdefault("custom_context", {})["credentials"] = credentials

    client = TaskComponentClient(space_id=space_id)
    result = client.create_task(create_task_data)

    task_data = result["data"]
    event_broadcast_signal.send(
        sender=WebhookEventType.TASK_CREATE.value,
        scopes=[(WebhookScopeType.SPACE.value, str(space_id))],
        extra_info={
            "task_id": task_data["id"],
            "task_name": task_data["name"],
            "template_id": task_data["template_id"],
            "parameters": task_data["parameters"],
            "trigger_source": TaskTriggerMethod.api.name,
        },
    )
    return result
