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
from datetime import datetime

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from bamboo_engine import states
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.task import OperateTaskNodeSerializer
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.plugin.models import OpenPluginRunCallbackRef
from bkflow.plugin.services.open_plugin_callback import (
    callback_token_digest,
    parse_open_plugin_callback_token,
)
from bkflow.utils import err_code
from bkflow.utils.trace import CallFrom, append_attributes, start_trace


def _build_open_plugin_callback_payload(data):
    callback_payload = {
        "open_plugin_run_id": data["open_plugin_run_id"],
        "status": data["status"],
    }
    for key in ("outputs", "error_message", "truncated", "truncated_fields"):
        if key in data:
            callback_payload[key] = data[key]
    return callback_payload


def _operate_task_node_callback_success(message):
    return {"result": True, "message": message, "code": err_code.SUCCESS.code, "data": None}


def _operate_task_node_callback_error(message):
    return {"result": False, "message": message, "code": err_code.VALIDATION_ERROR.code, "data": None}


def _handle_open_plugin_callback(space_id, task_id, node_id, data):
    callback_token = data.pop("_callback_token", "")
    if not callback_token:
        return _operate_task_node_callback_error("missing callback token")

    try:
        token_payload = parse_open_plugin_callback_token(callback_token)
    except Exception:
        return _operate_task_node_callback_error("invalid callback token")

    expire_at = datetime.fromisoformat(token_payload["expire_at"])
    if timezone.is_naive(expire_at):
        expire_at = timezone.make_aware(expire_at, timezone.get_current_timezone())
    if expire_at <= timezone.now():
        return _operate_task_node_callback_error("callback token expired")

    with transaction.atomic():
        callback_ref = (
            OpenPluginRunCallbackRef.objects.select_for_update()
            .filter(task_id=task_id, node_id=node_id, open_plugin_run_id=data["open_plugin_run_id"])
            .first()
        )
        if callback_ref is None:
            return _operate_task_node_callback_error("callback token does not match open plugin run")

        if callback_ref.callback_token_digest != callback_token_digest(callback_token):
            return _operate_task_node_callback_error("callback token verification failed")
        if callback_ref.callback_expire_at <= timezone.now():
            return _operate_task_node_callback_error("callback token expired")
        if token_payload["task_id"] != int(task_id) or token_payload["node_id"] != node_id:
            return _operate_task_node_callback_error("callback token does not match task node")
        if token_payload["client_request_id"] != callback_ref.client_request_id:
            return _operate_task_node_callback_error("callback token does not match client request")
        if token_payload.get("node_version", "") != callback_ref.node_version:
            return _operate_task_node_callback_error("callback token does not match node version")
        if callback_ref.consumed_at:
            return _operate_task_node_callback_success("open plugin callback already consumed")

        runtime = BambooDjangoRuntime()
        node_state = runtime.get_state(node_id)
        if node_state.name not in [states.RUNNING, states.FAILED]:
            callback_ref.consumed_at = timezone.now()
            callback_ref.save(update_fields=["consumed_at", "update_time"])
            return _operate_task_node_callback_success("node already in terminal state")
        if node_state.version != callback_ref.node_version:
            callback_ref.consumed_at = timezone.now()
            callback_ref.save(update_fields=["consumed_at", "update_time"])
            return _operate_task_node_callback_success("node version already changed")

        callback_request_data = {
            "operator": "system",
            "version": callback_ref.node_version,
            "data": _build_open_plugin_callback_payload(data),
        }
        client = TaskComponentClient(space_id=space_id)
        result = client.node_operate(task_id, node_id, "callback", callback_request_data)
        if result.get("result"):
            callback_ref.consumed_at = timezone.now()
            callback_ref.save(update_fields=["consumed_at", "update_time"])
        return result


def _is_open_plugin_callback_request(operation, data):
    return operation == "callback" and isinstance(data, dict) and "open_plugin_run_id" in data


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def operate_task_node(request, space_id, task_id, node_id, operation):
    data = json.loads(request.body)
    if _is_open_plugin_callback_request(operation, data):
        data["_callback_token"] = request.META.get("HTTP_X_CALLBACK_TOKEN", "")
        return _handle_open_plugin_callback(space_id=int(space_id), task_id=int(task_id), node_id=node_id, data=data)

    ser = OperateTaskNodeSerializer(data=data)
    ser.is_valid(raise_exception=True)

    with start_trace(
        "operate_task_node_interface",
        True,
        space_id=space_id,
        task_id=task_id,
        node_id=node_id,
        call_from=CallFrom.APIGW.value,
    ):
        append_attributes({"operation": operation})
        client = TaskComponentClient(space_id=space_id)
        result = client.node_operate(task_id, node_id, operation, data)
        return result
