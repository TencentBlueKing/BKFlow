# -*- coding: utf-8 -*-
from enum import Enum


class NodeTypes(str, Enum):
    START_EVENT = "start_event"
    END_EVENT = "end_event"
    COMPONENT = "component"
    PARALLEL_GATEWAY = "parallel_gateway"
    EXCLUSIVE_GATEWAY = "exclusive_gateway"
    CONVERGE_GATEWAY = "converge_gateway"
    CONDITIONAL_PARALLEL_GATEWAY = "conditional_parallel_gateway"

    GATEWAYS = [
        PARALLEL_GATEWAY,
        EXCLUSIVE_GATEWAY,
        CONVERGE_GATEWAY,
        CONDITIONAL_PARALLEL_GATEWAY,
    ]


class ConstantTypes(str, Enum):
    CUSTOM_CONSTANT = "custom"
    COMPONENT_INPUTS_CONSTANT = "component_inputs"
    COMPONENT_OUTPUTS_CONSTANT = "component_outputs"


class DataTypes(str, Enum):
    DATA_MODEL = "data_model"
    JSON = "json"
    WEB_PIPELINE = "web_pipeline"
    ENGINE_PIPELINE = "engine_pipeline"
