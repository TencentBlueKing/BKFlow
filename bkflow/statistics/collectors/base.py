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
from dataclasses import dataclass
from typing import Tuple

from pipeline.core.constants import PE

from bkflow.statistics.conf import StatisticsSettings

logger = logging.getLogger("celery")


class BaseStatisticsCollector(ABC):
    """统计数据采集器的抽象基类

    所有具体的采集器（模板、任务）需要继承此类并实现 collect() 方法。
    提供了 pipeline tree 节点计数和时间解析等公共工具方法。
    """

    def __init__(self):
        self.db_alias = StatisticsSettings.get_db_alias()
        self.engine_id = StatisticsSettings.get_engine_id()

    @abstractmethod
    def collect(self):
        raise NotImplementedError

    @staticmethod
    def count_pipeline_tree_nodes(pipeline_tree: dict) -> Tuple[int, int, int]:
        """递归统计 pipeline tree 中各类型节点的数量

        遍历 activities 区分 ServiceActivity（标准插件）和 SubProcess（子流程），
        子流程会递归进入其内部 pipeline 继续计数。

        :return: (atom_total, subprocess_total, gateways_total)
        """
        activities = pipeline_tree.get("activities", {})
        gateways = pipeline_tree.get("gateways", {})

        atom_total = 0
        subprocess_total = 0
        gateways_total = len(gateways)

        for act_id, act in activities.items():
            act_type = act.get("type", "")
            if act_type == PE.ServiceActivity:
                atom_total += 1
            elif act_type == PE.SubProcess:
                subprocess_total += 1
                sub_pipeline = act.get("pipeline", {})
                if sub_pipeline:
                    sub_atom, sub_sub, sub_gw = BaseStatisticsCollector.count_pipeline_tree_nodes(sub_pipeline)
                    atom_total += sub_atom
                    subprocess_total += sub_sub
                    gateways_total += sub_gw

        return atom_total, subprocess_total, gateways_total

    @staticmethod
    def parse_datetime(time_str):
        """解析时间字符串，兼容带时区偏移的格式（如 "2024-01-01 12:00:00 +0800"）"""
        if not time_str:
            return None
        from django.utils.dateparse import parse_datetime

        if isinstance(time_str, str):
            time_str = time_str.replace(" +", "+").replace(" -", "-")
            return parse_datetime(time_str)
        return time_str

    @staticmethod
    def resolve_component_info(component: dict) -> "ComponentInfo":
        """从 pipeline_tree 的 component 字典中解析出实际的插件编码、名称、版本和类型

        对 remote_plugin 和 uniform_api 进行特殊处理，提取被代理的实际插件信息。
        """
        from bkflow.statistics.models import PluginType

        code = component.get("code", "")
        version = component.get("version", "legacy")
        name = ""
        plugin_type = PluginType.COMPONENT

        if code == "remote_plugin":
            params = component.get("data") or component.get("inputs") or {}
            code = params.get("plugin_code", {}).get("value", code)
            version = params.get("plugin_version", {}).get("value", version)
            name = params.get("plugin_name", {}).get("value", "")
            plugin_type = PluginType.REMOTE_PLUGIN
        elif code == "uniform_api":
            plugin_type = PluginType.UNIFORM_API
            api_meta = component.get("api_meta") or {}
            if api_meta:
                code = api_meta.get("id", code)
                name = api_meta.get("name", "")
                category = api_meta.get("category") or {}
                if category.get("name") and name:
                    name = f"{category['name']}-{name}"

        return ComponentInfo(code=code, name=name, version=version, plugin_type=plugin_type)


@dataclass
class ComponentInfo:
    code: str
    name: str
    version: str
    plugin_type: str
