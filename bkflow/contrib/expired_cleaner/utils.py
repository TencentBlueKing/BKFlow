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

import logging

from django.conf import settings
from django.db import transaction
from pipeline.eri.models import (
    CallbackData,
    ContextOutputs,
    ContextValue,
    Data,
    ExecutionData,
    ExecutionHistory,
    Node,
    Process,
    Schedule,
    State,
)

from bkflow.task.models import (
    AutoRetryNodeStrategy,
    TaskExecutionSnapshot,
    TaskInstance,
    TaskMockData,
    TaskOperationRecord,
    TaskSnapshot,
    TimeoutNodeConfig,
)

logger = logging.getLogger("celery")


def _default_func(data, *args, **kwargs):
    return data


def chunk_data(data, chunk_size, func=None, *args, **kwargs):
    return [(func or _default_func)(data[i : i + chunk_size], *args, **kwargs) for i in range(0, len(data), chunk_size)]


def get_expired_data(previous_execute_time, current_execute_time):

    task_query = TaskInstance.objects.filter(
        create_time__gte=previous_execute_time, create_time__lt=current_execute_time
    )
    # 查询这段时间内的 task_instance_ids
    task_instance = task_query.values("instance_id", "id")[: settings.CLEAN_TASK_BATCH_NUM]
    task_instance = list(task_instance)
    if not task_instance:
        logger.info("no cleaning task, exit...")
        return None, None
    logger.info(f"batch cleaning task_instances {task_instance}")

    task_instance_ids = [instance["instance_id"] for instance in task_instance]
    task_ids = [instance["id"] for instance in task_instance]
    chunk_size = settings.CLEAN_TASK_NODE_BATCH_NUM

    # task_ids -> 其他任务关联资源 一对一
    context_value = ContextValue.objects.filter(pipeline_id__in=task_instance_ids)
    context_outputs = ContextOutputs.objects.filter(pipeline_id__in=task_instance_ids)

    task_operation_record = TaskOperationRecord.objects.filter(instance_id__in=task_ids)
    task_mock_data = TaskMockData.objects.filter(taskflow_id__in=task_ids)

    # task_instance task_execution_snapshot 直接根据时间过滤
    task_execution_snapshot_query = TaskExecutionSnapshot.objects.filter(
        create_time__gte=previous_execute_time, create_time__lt=current_execute_time
    )
    task_snapshot_query = TaskSnapshot.objects.filter(
        create_time__gte=previous_execute_time, create_time__lt=current_execute_time
    )

    # task_ids -> node_ids
    node_query = (
        Process.objects.filter(root_pipeline_id__in=task_instance_ids)
        .values_list("current_node_id", flat=True)
        .distinct()
    )
    node_ids = list(node_query)
    logger.info(f"batch cleaning node_ids {node_ids}")

    # 重构 node 和 task query 避免因前序查询导致结构变化无法执行操作
    node_query = Process.objects.filter(root_pipeline_id__in=task_instance_ids)
    task_query = TaskInstance.objects.filter(
        create_time__gte=previous_execute_time, create_time__lt=current_execute_time
    )

    # node_ids -> 其他节点关联资源 一对多 callbackdata 为一对一 且没有索引
    callbackdata = CallbackData.objects.filter(node_id__in=node_ids)  # callbackdata 没有索引 走全表扫描
    nodes_list = chunk_data(node_ids, chunk_size, lambda x: Node.objects.filter(node_id__in=x))
    data_list = chunk_data(node_ids, chunk_size, lambda x: Data.objects.filter(node_id__in=x))
    states_list = chunk_data(node_ids, chunk_size, lambda x: State.objects.filter(node_id__in=x))
    execution_history_list = chunk_data(node_ids, chunk_size, lambda x: ExecutionHistory.objects.filter(node_id__in=x))
    execution_data_list = chunk_data(node_ids, chunk_size, lambda x: ExecutionData.objects.filter(node_id__in=x))
    schedules_list = chunk_data(node_ids, chunk_size, lambda x: Schedule.objects.filter(node_id__in=x))

    retry_node_list = chunk_data(node_ids, chunk_size, lambda x: AutoRetryNodeStrategy.objects.filter(node_id__in=x))
    timeout_node_list = chunk_data(node_ids, chunk_size, lambda x: TimeoutNodeConfig.objects.filter(node_id__in=x))

    # 将一对一 和 一对多的分开返回 便于删除时区分
    return {
        "task_execution_snapshot_query": task_execution_snapshot_query,
        "task_snapshot_query": task_snapshot_query,
        "callbackdata": callbackdata,
        "context_value": context_value,
        "context_outputs": context_outputs,
        "task_operation_record": task_operation_record,
        "task_mock_data": task_mock_data,
        "node_ids": node_query,
        "task_instance": task_query,
    }, {
        "nodes_list": nodes_list,
        "data_list": data_list,
        "states_list": states_list,
        "execution_history_list": execution_history_list,
        "execution_data_list": execution_data_list,
        "schedules_list": schedules_list,
        "retry_node_list": retry_node_list,
        "timeout_node_list": timeout_node_list,
    }


def delete_expired_data(previous_execute_time, current_execute_time):

    expired_data, expired_batch_data = get_expired_data(previous_execute_time, current_execute_time)
    if not expired_data:
        return
    with transaction.atomic():
        # 清理无分块内容
        for field, qs in expired_data.items():
            logger.info(f"clean no batch {field} querySet ids : {qs.values_list('pk', flat=True)[:10]}...")
            qs.delete()
        # 清理分块内容
        for field, qs in expired_batch_data.items():
            logger.info(
                f"clean {field} {len(qs)} batch data, "
                f"e.x.: {qs[0].values_list('pk', flat=True)[:10] if len(qs) > 0 else None}..."
            )
            [q.delete() for q in qs]
        logger.info("clean task done...")
