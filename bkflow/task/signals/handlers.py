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
import datetime
import logging

from bamboo_engine import states as bamboo_engine_states
from django.conf import settings
from django.dispatch import receiver
from pipeline.eri.signals import post_set_state

from bkflow.task.celery.tasks import auto_retry_node, send_task_message
from bkflow.task.models import AutoRetryNodeStrategy, TaskInstance, TimeoutNodeConfig
from bkflow.task.utils import ATOM_FAILED, TASK_FINISHED, redis_inst_check

logger = logging.getLogger("root")


def _dispatch_auto_retry_node_task(root_pipeline_id, node_id):
    try:
        strategy = AutoRetryNodeStrategy.objects.get(root_pipeline_id=root_pipeline_id, node_id=node_id)
    except AutoRetryNodeStrategy.DoesNotExist:
        # auto retry not set
        return False

    # auto retry times exceed limit
    if strategy.retry_times + 1 > strategy.max_retry_times:
        return False

    try:
        auto_retry_node.apply_async(
            kwargs={
                "taskflow_id": strategy.taskflow_id,
                "root_pipeline_id": root_pipeline_id,
                "node_id": node_id,
                "retry_times": strategy.retry_times,
            },
            queue=f"node_auto_retry_{settings.BKFLOW_MODULE.code}",
            routing_key=f"node_auto_retry_{settings.BKFLOW_MODULE.code}",
            countdown=strategy.interval,
        )
    except Exception:
        logger.exception("auto retry dispatch failed, root_pipeline_id: %s, node_id: %s" % (root_pipeline_id, node_id))
        return False

    return True


@redis_inst_check
def _node_timeout_info_update(redis_inst, to_state, node_id, version):
    key = f"{node_id}_{version}"
    if to_state == bamboo_engine_states.RUNNING:
        now = datetime.datetime.now()
        timeout_qs = TimeoutNodeConfig.objects.filter(node_id=node_id).only("timeout")
        if not timeout_qs:
            return
        timeout_time = (now + datetime.timedelta(seconds=timeout_qs[0].timeout)).timestamp()
        redis_inst.zadd(settings.EXECUTING_NODE_POOL, mapping={key: timeout_time}, nx=True)
    elif to_state in [bamboo_engine_states.FAILED, bamboo_engine_states.FINISHED, bamboo_engine_states.SUSPENDED]:
        redis_inst.zrem(settings.EXECUTING_NODE_POOL, key)


@receiver(post_set_state)
def bamboo_engine_eri_post_set_state_handler(sender, node_id, to_state, version, root_id, parent_id, loop, **kwargs):
    if to_state == bamboo_engine_states.FAILED:
        retry_result = _dispatch_auto_retry_node_task(root_id, node_id)
        if retry_result:
            return
        send_task_message.apply_async(
            kwargs={
                "task_id": root_id,
                "msg_type": ATOM_FAILED,
            },
            queue=f"task_common_{settings.BKFLOW_MODULE.code}",
            routing_key=f"task_common_{settings.BKFLOW_MODULE.code}",
        )
    elif to_state == bamboo_engine_states.REVOKED and node_id == root_id:
        try:
            TaskInstance.objects.set_revoked(root_id)
        except Exception as e:
            logger.exception(f"TaskInstance set revoked error: {e}")
    elif to_state == bamboo_engine_states.FINISHED and node_id == root_id:
        try:
            TaskInstance.objects.set_finished(root_id)
        except Exception as e:
            logger.exception(f"TaskInstance set finished error: {e}")
        send_task_message.apply_async(
            kwargs={
                "task_id": root_id,
                "msg_type": TASK_FINISHED,
            },
            queue=f"task_common_{settings.BKFLOW_MODULE.code}",
            routing_key=f"task_common_{settings.BKFLOW_MODULE.code}",
        )

    try:
        _node_timeout_info_update(settings.redis_inst, to_state, node_id, version)
    except Exception as e:
        logger.exception(f"node_timeout_info_update error: {e}")
