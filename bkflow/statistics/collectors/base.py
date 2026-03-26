"""统计数据采集器基类，定义数据采集的公共接口和工具方法"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple

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
            if act_type == "ServiceActivity":
                atom_total += 1
            elif act_type == "SubProcess":
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
        """从 pipeline_tree 的 component 字典中解析出实际的插件编码、名称和版本

        对 remote_plugin 和 uniform_api 进行特殊处理，提取被代理的实际插件信息。
        """
        code = component.get("code", "")
        version = component.get("version", "legacy")
        name = ""
        is_remote = False

        if code == "remote_plugin":
            params = component.get("data") or component.get("inputs") or {}
            code = params.get("plugin_code", {}).get("value", code)
            version = params.get("plugin_version", {}).get("value", version)
            name = params.get("plugin_name", {}).get("value", "")
            is_remote = True
        elif code == "uniform_api":
            api_meta = component.get("api_meta") or {}
            if api_meta:
                code = api_meta.get("id", code)
                name = api_meta.get("name", "")
                category = api_meta.get("category") or {}
                if category.get("name") and name:
                    name = f"{category['name']}-{name}"

        return ComponentInfo(code=code, name=name, version=version, is_remote=is_remote)


@dataclass
class ComponentInfo:
    code: str
    name: str
    version: str
    is_remote: bool
