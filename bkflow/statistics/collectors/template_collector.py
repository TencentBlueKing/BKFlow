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
from typing import List

import ujson as json
from django.db import transaction

from bkflow.statistics.collectors.base import BaseStatisticsCollector
from bkflow.statistics.models import TemplateNodeStatistics, TemplateStatistics

logger = logging.getLogger("celery")


class TemplateStatisticsCollector(BaseStatisticsCollector):
    """模板统计采集器"""

    def __init__(self, template_id: int):
        super().__init__()
        self.template_id = template_id
        self._template = None

    @property
    def template(self):
        """获取模板实例"""
        if self._template is None:
            try:
                from bkflow.template.models import Template

                self._template = Template.objects.get(id=self.template_id)
            except Exception as e:
                logger.warning(f"Template {self.template_id} not found: {e}")
        return self._template

    def collect(self):
        """执行模板统计采集"""
        if not self.template:
            logger.warning(f"Template {self.template_id} not found, skip statistics collection")
            return False

        try:
            # 1. 采集模板节点统计
            self._collect_node_statistics()

            # 2. 采集模板整体统计
            self._collect_template_statistics()

            return True
        except Exception as e:
            logger.exception(f"[TemplateStatisticsCollector] template_id={self.template_id} error: {e}")
            return False

    def _collect_node_statistics(self):
        """采集模板节点统计"""
        pipeline_tree = self.template.pipeline_tree or {}

        # 删除旧数据
        with transaction.atomic(using=self.db_alias):
            TemplateNodeStatistics.objects.using(self.db_alias).filter(template_id=self.template_id).delete()

        # 收集节点数据
        component_list = self._collect_nodes(
            pipeline_tree=pipeline_tree,
            subprocess_stack=[],
            is_sub=False,
        )

        # 批量创建
        if component_list:
            TemplateNodeStatistics.objects.using(self.db_alias).bulk_create(component_list, batch_size=100)

    def _collect_nodes(
        self,
        pipeline_tree: dict,
        subprocess_stack: list,
        is_sub: bool,
    ) -> List[TemplateNodeStatistics]:
        """递归收集模板中的节点统计数据"""
        component_list = []
        activities = pipeline_tree.get("activities", {})

        for act_id, act in activities.items():
            act_type = act.get("type", "")

            if act_type == "ServiceActivity":
                # 标准插件节点
                component = act.get("component", {})
                component_code = component.get("code", "")
                component_version = component.get("version", "legacy")

                # 判断是否第三方插件
                is_remote = False
                if component_code == "remote_plugin":
                    inputs = component.get("inputs", {})
                    component_code = inputs.get("plugin_code", {}).get("value", component_code)
                    component_version = inputs.get("plugin_version", {}).get("value", component_version)
                    is_remote = True

                node_stat = TemplateNodeStatistics(
                    component_code=component_code,
                    version=component_version,
                    is_remote=is_remote,
                    template_id=self.template_id,
                    space_id=self.template.space_id,
                    scope_type=self.template.scope_type,
                    scope_value=self.template.scope_value,
                    node_id=act_id,
                    node_name=act.get("name", ""),
                    is_sub=is_sub,
                    subprocess_stack=json.dumps(subprocess_stack),
                    template_creator=self.template.creator,
                    template_create_time=self.template.create_at,
                    template_update_time=self.template.update_at,
                )
                component_list.append(node_stat)

            elif act_type == "SubProcess":
                # 子流程节点，递归处理
                sub_pipeline = act.get("pipeline", {})
                if sub_pipeline:
                    new_stack = deepcopy(subprocess_stack)
                    new_stack.insert(0, act_id)
                    sub_components = self._collect_nodes(
                        pipeline_tree=sub_pipeline,
                        subprocess_stack=new_stack,
                        is_sub=True,
                    )
                    component_list.extend(sub_components)

        return component_list

    def _collect_template_statistics(self):
        """采集模板整体统计"""
        pipeline_tree = self.template.pipeline_tree or {}

        # 统计节点数量
        atom_total, subprocess_total, gateways_total = self.count_pipeline_tree_nodes(pipeline_tree)

        # 统计变量数量
        data = pipeline_tree.get("data", {})
        constants = pipeline_tree.get("constants", {})

        input_count = 0
        output_count = 0

        # 通过 constants 统计变量
        for key, const in constants.items():
            source_type = const.get("source_type", "")
            if source_type == "component_outputs":
                output_count += 1
            else:
                input_count += 1

        # 如果没有 constants，通过 data 统计
        if not constants:
            input_count = len(data.get("inputs", {}))
            output_count = len(data.get("outputs", []))

        TemplateStatistics.objects.using(self.db_alias).update_or_create(
            template_id=self.template_id,
            defaults={
                "space_id": self.template.space_id,
                "scope_type": self.template.scope_type,
                "scope_value": self.template.scope_value,
                "atom_total": atom_total,
                "subprocess_total": subprocess_total,
                "gateways_total": gateways_total,
                "input_count": input_count,
                "output_count": output_count,
                "template_name": self.template.name,
                "template_creator": self.template.creator,
                "template_create_time": self.template.create_at,
                "template_update_time": self.template.update_at,
                "is_enabled": self.template.is_enabled,
            },
        )
