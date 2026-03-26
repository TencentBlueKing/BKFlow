"""模板维度统计数据采集器

采集模板的 pipeline 节点构成信息和各节点的插件详情。
在模板保存时触发，当 snapshot_id 发生变化（即 pipeline 结构有修改）时会重新采集节点统计。
"""

import logging
from copy import deepcopy
from typing import List

import ujson as json
from django.db import transaction

from bkflow.statistics.collectors.base import BaseStatisticsCollector
from bkflow.statistics.models import TemplateNodeStatistics, TemplateStatistics

logger = logging.getLogger("celery")


class TemplateStatisticsCollector(BaseStatisticsCollector):
    """模板统计数据采集器"""

    def __init__(self, template_id: int, snapshot_id: int = None):
        super().__init__()
        self.template_id = template_id
        self.snapshot_id = snapshot_id
        self._template = None

    @property
    def template(self):
        if self._template is None:
            try:
                from bkflow.template.models import Template

                self._template = Template.objects.get(id=self.template_id)
            except Exception as e:
                logger.warning(f"Template {self.template_id} not found: {e}")
        return self._template

    def collect(self):
        if not self.template:
            return False
        try:
            self._collect_template_statistics()
            self._collect_node_statistics()
            return True
        except Exception as e:
            logger.exception(f"[TemplateStatisticsCollector] template_id={self.template_id} error: {e}")
            return False

    def collect_meta_only(self):
        """仅更新模板元信息（名称、启用状态、更新时间），不重新采集节点统计"""
        if not self.template:
            return False
        try:
            TemplateStatistics.objects.using(self.db_alias).filter(template_id=self.template_id).update(
                template_name=self.template.name,
                is_enabled=self.template.is_enabled,
                template_update_time=self.template.update_at,
            )
            return True
        except Exception as e:
            logger.exception(f"[TemplateStatisticsCollector] collect_meta_only error: {e}")
            return False

    def _collect_template_statistics(self):
        pipeline_tree = self.template.pipeline_tree or {}
        atom_total, subprocess_total, gateways_total = self.count_pipeline_tree_nodes(pipeline_tree)

        TemplateStatistics.objects.using(self.db_alias).update_or_create(
            template_id=self.template_id,
            defaults={
                "space_id": self.template.space_id,
                "scope_type": self.template.scope_type or "",
                "scope_value": self.template.scope_value or "",
                "atom_total": atom_total,
                "subprocess_total": subprocess_total,
                "gateways_total": gateways_total,
                "template_name": self.template.name,
                "is_enabled": self.template.is_enabled,
                "template_create_time": self.template.create_at,
                "template_update_time": self.template.update_at,
            },
        )

    def _collect_node_statistics(self):
        pipeline_tree = self.template.pipeline_tree or {}
        component_list = self._collect_nodes(pipeline_tree, [], False)

        with transaction.atomic(using=self.db_alias):
            TemplateNodeStatistics.objects.using(self.db_alias).filter(template_id=self.template_id).delete()
            if component_list:
                TemplateNodeStatistics.objects.using(self.db_alias).bulk_create(component_list, batch_size=100)

    def _collect_nodes(self, pipeline_tree: dict, subprocess_stack: list, is_sub: bool) -> List[TemplateNodeStatistics]:
        """递归遍历 pipeline tree，为每个 ServiceActivity 创建节点统计记录

        对 remote_plugin 类型的节点，从 data（或 inputs）中提取实际的插件编码和版本。
        SubProcess 节点会递归进入其内部 pipeline，通过 subprocess_stack 记录嵌套路径。
        """
        component_list = []
        activities = pipeline_tree.get("activities", {})

        for act_id, act in activities.items():
            act_type = act.get("type", "")

            if act_type == "ServiceActivity":
                component = act.get("component", {})
                code = component.get("code", "")
                version = component.get("version", "legacy")
                is_remote = False

                if code == "remote_plugin":
                    params = component.get("data") or component.get("inputs") or {}
                    code = params.get("plugin_code", {}).get("value", code)
                    version = params.get("plugin_version", {}).get("value", version)
                    is_remote = True

                component_list.append(
                    TemplateNodeStatistics(
                        component_code=code,
                        version=version,
                        is_remote=is_remote,
                        template_id=self.template_id,
                        space_id=self.template.space_id,
                        scope_type=self.template.scope_type or "",
                        scope_value=self.template.scope_value or "",
                        node_id=act_id,
                        node_name=act.get("name", ""),
                        is_sub=is_sub,
                        subprocess_stack=json.dumps(subprocess_stack),
                    )
                )

            elif act_type == "SubProcess":
                sub_pipeline = act.get("pipeline", {})
                if sub_pipeline:
                    new_stack = deepcopy(subprocess_stack)
                    new_stack.insert(0, act_id)
                    component_list.extend(self._collect_nodes(sub_pipeline, new_stack, True))

        return component_list
