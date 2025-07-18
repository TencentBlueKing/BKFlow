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
import time

from celery import current_app
from django.conf import settings
from pipeline.eri.models import Process, State
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.constants import WebhookEventType
from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.task.models import (
    AutoRetryNodeStrategy,
    TaskInstance,
    TimeoutNodeConfig,
    TimeoutNodesRecord,
)
from bkflow.task.node_timeout import node_timeout_handler
from bkflow.task.operations import TaskNodeOperation
from bkflow.task.utils import ATOM_FAILED, redis_inst_check, send_task_instance_message

logger = logging.getLogger("celery")


def _ensure_node_can_retry(node_id):
    count = 0
    while count < 3:
        if BambooDjangoRuntime().get_sleep_process_info_with_current_node_id(node_id):
            return True
        time.sleep(0.1)
        count += 1

    return False


@current_app.task
@redis_inst_check
def auto_retry_node(taskflow_id, root_pipeline_id, node_id, retry_times):
    lock_name = "%s-%s-%s" % (root_pipeline_id, node_id, retry_times)
    if not settings.redis_inst.set(name=lock_name, value=1, nx=True, ex=5):
        logger.warning("[auto_retry_node] lock %s acquire failed, operation give up" % lock_name)
        return

    # wait process enter a valid state
    can_retry = _ensure_node_can_retry(node_id=node_id)
    if not can_retry:
        settings.redis_inst.delete(lock_name)
        logger.warning("[auto_retry_node] task(%s) node(%s) ensure_node_can_retry timeout" % (taskflow_id, node_id))
        return

    try:
        task_instance = TaskInstance.objects.get(id=taskflow_id)
    except TaskInstance.DoesNotExist:
        logger.exception("[auto_retry_node] celery get task for (task_id={}) fail.".format(taskflow_id))
        return
    operation = TaskNodeOperation(task_instance=task_instance, node_id=node_id)
    result = operation.retry(operator="system", inputs={})

    if not result.result:
        logger.error("[auto_retry_node] task(%s) node(%s) auto retry failed: %s" % (taskflow_id, node_id, dict(result)))

    AutoRetryNodeStrategy.objects.filter(root_pipeline_id=root_pipeline_id, node_id=node_id).update(
        retry_times=retry_times + 1
    )
    settings.redis_inst.delete(lock_name)


@current_app.task
def send_task_message(task_id, msg_type):
    try:
        task_instance = TaskInstance.objects.get(instance_id=task_id)
        send_task_instance_message(task_instance, msg_type)

        # broadcast events through webhooks
        event = WebhookEventType.TASK_FAILED.value if msg_type == ATOM_FAILED else WebhookEventType.TASK_FINISHED.value
        interface_client = InterfaceModuleClient()
        interface_client.broadcast_task_events(
            data={"space_id": task_instance.space_id, "event": event, "extra_info": {"task_id": task_instance.id}}
        )
    except Exception as e:
        logger.exception(f"[send_task_message] task({task_id}) send message({msg_type}) error: {e}")
    else:
        logger.info(f"[send_task_message] task({task_id}) send message({msg_type}) success")


@current_app.task(acks_late=True)
def dispatch_timeout_nodes(record_id: int):
    record = TimeoutNodesRecord.objects.get(id=record_id)
    nodes = json.loads(record.timeout_nodes)
    for node in nodes:
        node_id, version = node.split("_")
        execute_node_timeout_strategy.apply_async(
            kwargs={"node_id": node_id, "version": version},
            queue=f"timeout_node_execute_{settings.BKFLOW_MODULE.code}",
            routing_key=f"timeout_node_execute_{settings.BKFLOW_MODULE.code}",
        )


@current_app.task(ignore_result=True)
def execute_node_timeout_strategy(node_id, version):
    timeout_config = (
        TimeoutNodeConfig.objects.filter(node_id=node_id).only("task_id", "root_pipeline_id", "action").first()
    )
    task_id, action, root_pipeline_id = (
        timeout_config.task_id,
        timeout_config.action,
        timeout_config.root_pipeline_id,
    )
    task_inst = TaskInstance.objects.get(pk=task_id)

    # 判断当前节点是否符合策略执行要求
    is_process_current_node = Process.objects.filter(
        root_pipeline_id=root_pipeline_id, current_node_id=node_id
    ).exists()
    node_match = State.objects.filter(node_id=node_id, version=version).exists()
    if not (node_match and is_process_current_node):
        message = f"超时策略激活失败: 节点[ID: {node_id}], 版本[{version}], 任务[ID: {task_id}] 现已通过"
        logger.error(message)
        return {"result": False, "message": message, "data": None}

    handler = node_timeout_handler[action]
    action_result = handler.deal_with_timeout_node(task_inst, node_id)
    logger.info(
        f"[execute_node_timeout_strategy] node {node_id} with version {version} in task {task_id} "
        f"action result is: {action_result}."
    )

    return action_result
