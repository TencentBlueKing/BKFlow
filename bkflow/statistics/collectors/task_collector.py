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
from copy import deepcopy
from typing import List, Optional

import ujson as json
from django.utils import timezone

from bkflow.statistics.collectors.base import BaseStatisticsCollector
from bkflow.statistics.conf import StatisticsConfig
from bkflow.statistics.models import TaskflowExecutedNodeStatistics, TaskflowStatistics

logger = logging.getLogger("celery")


class TaskStatisticsCollector(BaseStatisticsCollector):
    """任务统计采集器"""

    def __init__(self, task_id: int = None, instance_id: str = None):
        super().__init__()
        self.task_id = task_id
        self.instance_id = instance_id
        self._task = None

    @property
    def task(self):
        """获取任务实例"""
        if self._task is None:
            try:
                from bkflow.task.models import TaskInstance

                if self.task_id:
                    self._task = TaskInstance.objects.get(id=self.task_id)
                elif self.instance_id:
                    self._task = TaskInstance.objects.get(instance_id=self.instance_id)
            except Exception as e:
                logger.warning(f"TaskInstance not found: task_id={self.task_id}, instance_id={self.instance_id}: {e}")
        return self._task

    def collect(self):
        """执行任务统计采集（创建时）"""
        return self.collect_on_create()

    def collect_on_create(self):
        """任务创建时采集"""
        if not self.task:
            return False

        # 检查是否需要排除 Mock 任务
        if self.task.create_method == "MOCK" and not StatisticsConfig.include_mock_tasks():
            logger.debug(f"Skip mock task statistics: task_id={self.task.id}")
            return False

        try:
            pipeline_tree = self.task.execution_data or {}
            atom_total, subprocess_total, gateways_total = self.count_pipeline_tree_nodes(pipeline_tree)

            TaskflowStatistics.objects.using(self.db_alias).update_or_create(
                task_id=self.task.id,
                defaults={
                    "instance_id": self.task.instance_id,
                    "template_id": self.task.template_id,
                    "space_id": self.task.space_id,
                    "scope_type": self.task.scope_type,
                    "scope_value": self.task.scope_value,
                    "engine_id": self.engine_id,
                    "atom_total": atom_total,
                    "subprocess_total": subprocess_total,
                    "gateways_total": gateways_total,
                    "node_total": atom_total + subprocess_total + gateways_total + 2,  # +2 for start/end
                    "creator": self.task.creator,
                    "executor": self.task.executor,
                    "create_time": self.task.create_time,
                    "create_method": self.task.create_method,
                    "trigger_method": getattr(self.task, "trigger_method", "manual"),
                    "is_started": self.task.is_started,
                    "is_finished": False,
                    "is_success": False,
                },
            )
            return True
        except Exception as e:
            logger.exception(f"[TaskStatisticsCollector] collect_on_create error: {e}")
            return False

    def collect_on_archive(self):
        """任务归档时采集（完成/撤销）"""
        if not self.task:
            return False

        try:
            # 1. 更新任务统计
            self._update_task_statistics()

            # 2. 采集节点执行统计
            self._collect_node_statistics()

            return True
        except Exception as e:
            logger.exception(f"[TaskStatisticsCollector] collect_on_archive error: {e}")
            return False

    def _update_task_statistics(self):
        """更新任务统计信息"""
        is_success = self.task.is_finished and not self.task.is_revoked
        final_state = ""
        if self.task.is_finished:
            final_state = "FINISHED"
        elif self.task.is_revoked:
            final_state = "REVOKED"

        elapsed_time = None
        if self.task.start_time and self.task.finish_time:
            elapsed_time = int((self.task.finish_time - self.task.start_time).total_seconds())

        TaskflowStatistics.objects.using(self.db_alias).filter(task_id=self.task.id).update(
            start_time=self.task.start_time,
            finish_time=self.task.finish_time,
            elapsed_time=elapsed_time,
            is_started=self.task.is_started,
            is_finished=self.task.is_finished,
            is_success=is_success,
            final_state=final_state,
            executor=self.task.executor,
        )

    def _collect_node_statistics(self):
        """采集节点执行统计"""
        try:
            from bamboo_engine import api as bamboo_engine_api
            from pipeline.eri.runtime import BambooDjangoRuntime

            # 获取状态树
            runtime = BambooDjangoRuntime()
            status_result = bamboo_engine_api.get_pipeline_states(
                runtime=runtime,
                root_id=self.task.instance_id,
            )

            if not status_result.result:
                logger.error(f"get_pipeline_states failed: {status_result.message}")
                return

            status_tree = status_result.data
            pipeline_tree = self.task.execution_data or {}

            # 删除旧数据
            TaskflowExecutedNodeStatistics.objects.using(self.db_alias).filter(task_id=self.task.id).delete()

            # 采集节点数据
            executed_nodes = self._extract_executed_nodes(pipeline_tree, status_tree)

            if executed_nodes:
                TaskflowExecutedNodeStatistics.objects.using(self.db_alias).bulk_create(
                    executed_nodes,
                    batch_size=100,
                )

            # 更新任务统计的节点计数
            executed_count = len([n for n in executed_nodes if not n.is_retry])
            failed_count = len([n for n in executed_nodes if not n.status and not n.is_retry])
            retry_count = len([n for n in executed_nodes if n.is_retry])

            TaskflowStatistics.objects.using(self.db_alias).filter(task_id=self.task.id).update(
                executed_node_count=executed_count,
                failed_node_count=failed_count,
                retry_node_count=retry_count,
            )
        except ImportError:
            logger.warning("bamboo_engine not available, skip node statistics collection")
        except Exception as e:
            logger.exception(f"[TaskStatisticsCollector] _collect_node_statistics error: {e}")

    def _extract_executed_nodes(
        self,
        pipeline_tree: dict,
        status_tree: dict,
        subprocess_stack: list = None,
        is_sub: bool = False,
    ) -> List[TaskflowExecutedNodeStatistics]:
        """递归提取已执行节点"""
        if subprocess_stack is None:
            subprocess_stack = []

        nodes = []
        activities = pipeline_tree.get("activities", {})
        children = status_tree.get("children", {})

        for act_id, act in activities.items():
            if act_id not in children:
                continue

            node_status = children[act_id]
            act_type = act.get("type", "")

            if act_type == "ServiceActivity":
                node = self._create_node_statistics(act, node_status, subprocess_stack, is_sub)
                if node:
                    nodes.append(node)

            elif act_type == "SubProcess":
                sub_pipeline = act.get("pipeline", {})
                sub_status = node_status.get("children", {})
                if sub_pipeline and sub_status:
                    new_stack = deepcopy(subprocess_stack)
                    new_stack.insert(0, act_id)
                    sub_nodes = self._extract_executed_nodes(
                        sub_pipeline,
                        {"children": sub_status},
                        new_stack,
                        True,
                    )
                    nodes.extend(sub_nodes)

        return nodes

    def _create_node_statistics(
        self,
        activity: dict,
        status: dict,
        subprocess_stack: list,
        is_sub: bool,
    ) -> Optional[TaskflowExecutedNodeStatistics]:
        """创建节点统计记录"""
        state = status.get("state", "")
        if state not in ("FINISHED", "FAILED", "REVOKED", "SUSPENDED"):
            return None

        component = activity.get("component", {})
        component_code = component.get("code", "")
        version = component.get("version", "legacy")
        is_remote = False

        if component_code == "remote_plugin":
            inputs = component.get("inputs", {})
            component_code = inputs.get("plugin_code", {}).get("value", component_code)
            version = inputs.get("plugin_version", {}).get("value", version)
            is_remote = True

        started_time = self.parse_datetime(status.get("start_time"))
        archived_time = self.parse_datetime(status.get("finish_time"))
        elapsed_time = status.get("elapsed_time")

        return TaskflowExecutedNodeStatistics(
            component_code=component_code,
            version=version,
            is_remote=is_remote,
            task_id=self.task.id,
            instance_id=self.task.instance_id,
            template_id=self.task.template_id,
            space_id=self.task.space_id,
            scope_type=self.task.scope_type,
            scope_value=self.task.scope_value,
            engine_id=self.engine_id,
            node_id=activity.get("id", ""),
            node_name=activity.get("name", ""),
            template_node_id=activity.get("template_node_id", ""),
            is_sub=is_sub,
            subprocess_stack=json.dumps(subprocess_stack),
            started_time=started_time or timezone.now(),
            archived_time=archived_time,
            elapsed_time=elapsed_time,
            status=(state == "FINISHED"),
            state=state,
            is_skip=status.get("skip", False),
            retry_count=status.get("retry", 0),
            loop_count=status.get("loop", 1),
            task_create_time=self.task.create_time,
            task_start_time=self.task.start_time,
            task_finish_time=self.task.finish_time,
        )
