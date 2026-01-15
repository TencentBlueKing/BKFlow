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
from abc import ABC, abstractmethod
from typing import Tuple

from bkflow.statistics.conf import StatisticsConfig

logger = logging.getLogger("celery")


class BaseStatisticsCollector(ABC):
    """统计采集器基类"""

    def __init__(self):
        self.db_alias = StatisticsConfig.get_db_alias()
        self.engine_id = StatisticsConfig.get_engine_id()

    @abstractmethod
    def collect(self):
        """执行采集"""
        raise NotImplementedError

    @staticmethod
    def count_pipeline_tree_nodes(pipeline_tree: dict) -> Tuple[int, int, int]:
        """
        统计 pipeline_tree 中的节点数量

        Args:
            pipeline_tree: pipeline 树结构

        Returns:
            tuple: (atom_total, subprocess_total, gateways_total)
        """
        activities = pipeline_tree.get("activities", {})
        gateways = pipeline_tree.get("gateways", {})

        atom_total = 0
        subprocess_total = 0

        for act_id, act in activities.items():
            act_type = act.get("type", "")
            if act_type == "ServiceActivity":
                atom_total += 1
            elif act_type == "SubProcess":
                subprocess_total += 1
                # 递归统计子流程内的节点
                sub_pipeline = act.get("pipeline", {})
                if sub_pipeline:
                    sub_atom, sub_subproc, _ = BaseStatisticsCollector.count_pipeline_tree_nodes(sub_pipeline)
                    atom_total += sub_atom
                    subprocess_total += sub_subproc

        gateways_total = len(gateways)

        return atom_total, subprocess_total, gateways_total

    @staticmethod
    def parse_datetime(time_str):
        """解析时间字符串"""
        if not time_str:
            return None
        from django.utils.dateparse import parse_datetime

        # 处理多种可能的时间格式
        if isinstance(time_str, str):
            # 替换空格分隔的时区格式
            time_str = time_str.replace(" +", "+").replace(" -", "-")
            return parse_datetime(time_str)
        return time_str
