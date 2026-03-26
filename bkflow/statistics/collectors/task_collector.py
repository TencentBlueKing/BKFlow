"""任务维度统计数据采集器

采集任务生命周期中两个阶段的统计数据：
- 创建阶段（collect_on_create）：记录任务基本信息和 pipeline 节点构成
- 归档阶段（collect_on_archive）：更新最终状态、耗时，并采集每个已执行节点的执行详情
"""

import logging
from copy import deepcopy
from typing import List, Optional

from django.db import transaction
from django.utils import timezone

from bkflow.statistics.collectors.base import BaseStatisticsCollector
from bkflow.statistics.conf import StatisticsSettings
from bkflow.statistics.models import TaskflowExecutedNodeStatistics, TaskflowStatistics

logger = logging.getLogger("celery")


class TaskStatisticsCollector(BaseStatisticsCollector):
    """任务统计数据采集器，支持通过 task_id 或 instance_id 定位任务"""

    def __init__(self, task_id: int = None, instance_id: str = None):
        super().__init__()
        self.task_id = task_id
        self.instance_id = instance_id
        self._task = None

    @property
    def task(self):
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
        return self.collect_on_create()

    def collect_on_create(self):
        """任务创建时采集统计数据：pipeline 节点构成、创建方式等基础信息"""
        if not self.task:
            return False

        if self.task.create_method == "MOCK" and not StatisticsSettings.include_mock_tasks():
            return False

        try:
            pipeline_tree = self.task.execution_data or {}
            atom_total, subprocess_total, gateways_total = self.count_pipeline_tree_nodes(pipeline_tree)

            TaskflowStatistics.objects.using(self.db_alias).update_or_create(
                task_id=self.task.id,
                defaults={
                    "space_id": self.task.space_id,
                    "scope_type": self.task.scope_type or "",
                    "scope_value": self.task.scope_value or "",
                    "template_id": self.task.template_id,
                    "engine_id": self.engine_id,
                    "atom_total": atom_total,
                    "subprocess_total": subprocess_total,
                    "gateways_total": gateways_total,
                    "create_time": self.task.create_time,
                    "create_method": self.task.create_method,
                    "trigger_method": getattr(self.task, "trigger_method", "manual"),
                    "is_started": self.task.is_started,
                    "is_finished": False,
                    "final_state": "CREATED",
                },
            )
            return True
        except Exception as e:
            logger.exception(f"[TaskStatisticsCollector] collect_on_create error: {e}")
            return False

    def collect_on_archive(self):
        """任务归档时采集统计数据：更新最终状态和耗时，并采集各节点的执行详情"""
        if not self.task:
            return False

        try:
            self._update_task_statistics()
            self._collect_node_statistics()
            return True
        except Exception as e:
            logger.exception(f"[TaskStatisticsCollector] collect_on_archive error: {e}")
            return False

    def _update_task_statistics(self):
        final_state = "FINISHED"
        if self.task.is_revoked:
            final_state = "REVOKED"
        elif not self.task.is_finished:
            final_state = "RUNNING"

        elapsed_time = None
        if self.task.start_time and self.task.finish_time:
            elapsed_time = int((self.task.finish_time - self.task.start_time).total_seconds())

        TaskflowStatistics.objects.using(self.db_alias).filter(task_id=self.task.id).update(
            start_time=self.task.start_time,
            finish_time=self.task.finish_time,
            elapsed_time=elapsed_time,
            is_started=self.task.is_started,
            is_finished=self.task.is_finished,
            final_state=final_state,
        )

    def _collect_node_statistics(self):
        """通过 bamboo_engine API 获取节点执行状态，采集已执行节点的统计信息"""
        try:
            from bamboo_engine import api as bamboo_engine_api
            from pipeline.eri.runtime import BambooDjangoRuntime

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

            root_data = status_tree.get(self.task.instance_id, {})
            executed_nodes = self._extract_executed_nodes(pipeline_tree, root_data)

            with transaction.atomic(using=self.db_alias):
                TaskflowExecutedNodeStatistics.objects.using(self.db_alias).filter(task_id=self.task.id).delete()
                if executed_nodes:
                    TaskflowExecutedNodeStatistics.objects.using(self.db_alias).bulk_create(
                        executed_nodes, batch_size=100
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
        """递归遍历 pipeline tree 和对应的执行状态树，提取已执行的 ServiceActivity 节点

        对于 SubProcess 节点，会进入其内部 pipeline 递归提取，
        并通过 subprocess_stack 记录子流程嵌套路径。
        """
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
                    sub_nodes = self._extract_executed_nodes(sub_pipeline, {"children": sub_status}, new_stack, True)
                    nodes.extend(sub_nodes)

        return nodes

    def _create_node_statistics(
        self, activity: dict, status: dict, subprocess_stack: list, is_sub: bool
    ) -> Optional[TaskflowExecutedNodeStatistics]:
        """根据节点定义和执行状态创建节点统计记录

        仅处理已完成的节点（FINISHED/FAILED/REVOKED/SUSPENDED）。
        通过 resolve_component_info 提取实际的插件编码、名称和版本。
        """
        state = status.get("state", "")
        if state not in ("FINISHED", "FAILED", "REVOKED", "SUSPENDED"):
            return None

        component = activity.get("component", {})
        info = self.resolve_component_info(component)

        started_time = self.parse_datetime(status.get("started_time"))
        archived_time = self.parse_datetime(status.get("archived_time"))
        elapsed_time = None
        if started_time and archived_time:
            elapsed_time = int((archived_time - started_time).total_seconds())

        retry_count = status.get("retry", 0)
        is_retry = False  # current execution is not a retry; historical retries are not stored individually

        return TaskflowExecutedNodeStatistics(
            task_id=self.task.id,
            space_id=self.task.space_id,
            engine_id=self.engine_id,
            component_code=info.code,
            component_name=info.name,
            version=info.version,
            is_remote=info.is_remote,
            node_id=activity.get("id", ""),
            started_time=started_time or timezone.now(),
            archived_time=archived_time,
            elapsed_time=elapsed_time,
            status=(state == "FINISHED"),
            state=state,
            is_skip=status.get("skip", False),
            is_retry=is_retry,
            retry_count=retry_count,
        )
