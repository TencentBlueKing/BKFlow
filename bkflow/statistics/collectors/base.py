import logging
from abc import ABC, abstractmethod
from typing import Tuple

from bkflow.statistics.conf import StatisticsSettings

logger = logging.getLogger("celery")


class BaseStatisticsCollector(ABC):
    def __init__(self):
        self.db_alias = StatisticsSettings.get_db_alias()
        self.engine_id = StatisticsSettings.get_engine_id()

    @abstractmethod
    def collect(self):
        raise NotImplementedError

    @staticmethod
    def count_pipeline_tree_nodes(pipeline_tree: dict) -> Tuple[int, int, int]:
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
        if not time_str:
            return None
        from django.utils.dateparse import parse_datetime

        if isinstance(time_str, str):
            time_str = time_str.replace(" +", "+").replace(" -", "-")
            return parse_datetime(time_str)
        return time_str
