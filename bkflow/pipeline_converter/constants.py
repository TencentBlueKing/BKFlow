# -*- coding: utf-8 -*-
from enum import Enum

from pipeline.variable_framework.models import VariableModel


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
    # 自定义常量
    CUSTOM_CONSTANT = "custom"
    # 节点输入常量
    COMPONENT_INPUTS_CONSTANT = "component_inputs"
    # 节点输出常量
    COMPONENT_OUTPUTS_CONSTANT = "component_outputs"

    CUSTOM_CONSTANT_CUSTOMS = [variable.code for variable in VariableModel.objects.filter(status=True)]
    CUSTOM_CONSTANT_TAGS = [variable.tag for variable in VariableModel.objects.filter(status=True)]


class DataTypes(str, Enum):
    DATA_MODEL = "data_model"
    JSON = "json"
    WEB_PIPELINE = "web_pipeline"
    ENGINE_PIPELINE = "engine_pipeline"
