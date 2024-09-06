# -*- coding: utf-8 -*-
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

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import serializers

from bkflow.contrib.api.collections.itsm import BKItsmClient
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.utils.handlers import handle_api_error

logger = logging.getLogger("root")

# 审批状态对应审批结果value
TRANSITION_MAP = {True: "TONGYI", False: "JUJUE"}


class ITSMViewRequestSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text="空间ID")
    task_id = serializers.IntegerField(help_text="任务ID")
    node_id = serializers.CharField(help_text="节点ID")
    is_passed = serializers.BooleanField(help_text="是否通过")
    message = serializers.CharField(help_text="审批备注", allow_blank=True)


class ITSMViewResponse(serializers.Serializer):
    result = serializers.BooleanField(read_only=True, help_text="请求结果")
    message = serializers.CharField(read_only=True, help_text="请求结果失败时返回信息")


@csrf_exempt
@require_POST
def itsm_approve(request):
    data = json.loads(request.body)
    if "is_passed" not in data:
        return JsonResponse({"result": False, "message": "is_passed 该字段是必填项"})
    operator = request.user.username
    serializer = ITSMViewRequestSerializer(data=data)
    serializer.is_valid(raise_exception=True)

    serializer_data = serializer.data

    space_id = serializer_data["space_id"]

    # 判断是否是拒绝,如果是拒绝并且没有填写备注则失败
    if not serializer_data["is_passed"] and not serializer_data["message"]:
        return JsonResponse({"result": False, "message": "审批拒绝后需填入备注"})

    client = TaskComponentClient(space_id=space_id)

    # 获取当前任务id以及节点id查询目前的itsm单据sn
    node_detail = client.get_task_node_detail(
        task_id=serializer_data["task_id"], node_id=serializer_data["node_id"], username=operator
    )

    if not node_detail["result"]:
        message = node_detail["message"]
        logger.error(message)
        result = {"result": False, "message": message}
        return JsonResponse(result)

    # 获取节点输出
    node_outputs = node_detail["data"]["outputs"]
    if not node_outputs:
        return JsonResponse({"result": False, "message": "获取该节点输出参数为空"})

    # 从node_outputs中获取单号
    sn = ""
    for node_output in node_outputs:
        if node_output["key"] == "sn":
            sn = node_output["value"]
            break
    if not sn:
        return JsonResponse({"result": False, "message": "该审批节点输出参数中没有itsm单据(sn)"})

    # 创建client
    client = BKItsmClient(username=operator)

    # 获取单据信息查询节点id
    ticket_info_result = client.get_ticket_info(sn)
    if not ticket_info_result["result"]:
        message = handle_api_error("itsm", "get_ticket_info", request.data, ticket_info_result)
        logger.error(message)
        result = {"result": False, "message": message}
        return JsonResponse(result)

    # 获取当前单据的步骤
    ticket_info_data = ticket_info_result["data"]
    current_steps = ticket_info_data["current_steps"]

    # 获取itsm节点id部分
    state_id = ""
    # 由于标准运维生成的审批流程是itsm特定的,所以当审批步骤的name为"内置审批节点"时
    # 则可以认为该节点是审批节点
    for current_step in current_steps:
        if current_step["name"] == "内置审批节点":
            state_id = current_step["state_id"]
            break
    if not state_id:
        return JsonResponse({"result": False, "message": "该审批流程已结束"})

    # 构建审批表单字段列表参数
    fields = []
    # 获取该单据下该节点的字段
    ticket_fields = ticket_info_data["fields"]
    for ticket_field in reversed(ticket_fields):
        if ticket_field["name"] == "备注":
            field = {"key": ticket_field["key"], "value": serializer_data["message"]}
            fields.append(field)
        elif ticket_field["name"] == "审批意见":
            field = {"key": ticket_field["key"], "value": str(serializer_data["is_passed"]).lower()}
            fields.append(field)
        # 由于审批时,审批通过和审批拒绝时的"备注"字段是不同的,并且不可区分
        # 所以不管是通过还是拒绝,都需要将两个备注字段赋值写入
        # 并且审批是否通过的布尔值小写写入,所以一共需要写入三个字段
        # 所以此处判断fields长度为3时即可以认为两个备注和一个审批意见都已写入,使用break结束循环
        if len(fields) == 3:
            break

    # 构建请求参数
    kwargs = {"operator": operator, "sn": sn, "state_id": state_id, "action_type": "TRANSITION", "fields": fields}

    itsm_result = client.operate_node(**kwargs)

    # 判断api请求结果是否成功
    if not itsm_result["result"]:
        message = handle_api_error("itsm", "operate_node", kwargs, itsm_result)
        logger.error(message)
        result = {"result": False, "message": message}
        return JsonResponse(result)

    return JsonResponse({"result": True, "data": None})
