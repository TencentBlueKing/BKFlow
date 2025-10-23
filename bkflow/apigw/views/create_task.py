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
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from webhook.signals import event_broadcast_signal

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.task import CreateTaskSerializer
from bkflow.constants import TaskTriggerMethod, WebhookEventType, WebhookScopeType
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.exceptions import ValidationError
from bkflow.template.models import Template
from bkflow.utils.trace import CallFrom, trace_view


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@trace_view(attr_keys=["space_id"], call_from=CallFrom.APIGW.value)
@check_jwt_and_space
@return_json_response
def create_task(request, space_id):
    data = json.loads(request.body)
    ser = CreateTaskSerializer(data=data)
    ser.is_valid(raise_exception=True)
    try:
        template = Template.objects.get(id=ser.data["template_id"], space_id=space_id, is_deleted=False)
    except Template.DoesNotExist:
        raise ValidationError(
            _("模版不存在，space_id={space_id}, template_id={template_id}").format(
                space_id=space_id, template_id=ser.data["template_id"]
            )
        )

    create_task_data = dict(ser.data)
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
            "trigger_source": TaskTriggerMethod.manual.name,
        },
    )
    return result
