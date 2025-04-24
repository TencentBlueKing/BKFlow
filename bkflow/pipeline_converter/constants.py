# -*- coding: utf-8 -*-
from enum import Enum


class NodeTypes(str, Enum):
    START_EVENT = "start_event"
    END_EVENT = "end_event"
    COMPONENT = "component"


class DataTypes(str, Enum):
    DATA_MODEL = "data_model"
    JSON = "json"
    PIPELINE_TREE = "pipeline_tree"
