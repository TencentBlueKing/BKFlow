# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Union

from pydantic import BaseModel

from bkflow.pipeline_converter.constants import ConstantTypes, NodeTypes


class Node(BaseModel):
    id: str
    name: str = ""
    type: str
    next: Union[str, List[str], None]


class EmptyStartNode(Node):
    type: str = NodeTypes.START_EVENT.value


class EmptyEndNode(Node):
    type: str = NodeTypes.END_EVENT.value
    next: None = None


class ComponentField(BaseModel):
    value: Any
    key: str
    need_render: bool = True


class Component(BaseModel):
    code: str
    version: str
    data: List[ComponentField]


class AutoRetryConfig(BaseModel):
    enable: bool = False
    interval: int = 0
    times: int = 1


class TimeoutConfig(BaseModel):
    enable: bool = False
    seconds: int = 10
    action: str = "forced_fail"


class ComponentNode(Node):
    type: str = NodeTypes.COMPONENT.value
    component: Component
    skippable: bool = True
    retryable: bool = True
    error_ignorable: bool = False
    auto_retry: AutoRetryConfig = AutoRetryConfig()
    timeout_config: TimeoutConfig = TimeoutConfig()


class Flow(BaseModel):
    id: str
    source: str
    target: str
    is_default: bool = False


class Gateway(Node):
    pass


class ParallelGateway(Gateway):
    converge_gateway_id: str
    type: str = NodeTypes.PARALLEL_GATEWAY.value


class ConvergeGateway(Gateway):
    type: str = NodeTypes.CONVERGE_GATEWAY.value


class Condition(BaseModel):
    name: str
    next: str


class DefaultCondition(Condition):
    pass


class ExprCondition(Condition):
    expr: str


class ExclusiveGateway(Gateway):
    lang: str = "boolrule"
    conditions: List[ExprCondition]
    default_condition: DefaultCondition = None
    type: str = NodeTypes.EXCLUSIVE_GATEWAY.value


class ConditionalParallelGateway(ExclusiveGateway, ParallelGateway):
    type: str = NodeTypes.CONDITIONAL_PARALLEL_GATEWAY.value


class SourceInfo(BaseModel):
    key: str
    value: str


class Constant(BaseModel):
    name: str
    type: str  # source_type
    key: str
    value: Any
    version: str = "legacy"
    desc: str = ""
    show_type: str = "show"
    validation: str = ""
    custom_type: str
    source_info: List[SourceInfo]
    source_tag: str


class CustomConstant(Constant):
    type: str = ConstantTypes.CUSTOM_CONSTANT.value
    pre_render_make: bool = False
    is_meta: bool = False


class ComponentInputConstant(Constant):
    type: str = ConstantTypes.COMPONENT_INPUTS_CONSTANT.value
    plugin_code: str = ""


class ComponentOutConstant(Constant):
    type: str = ConstantTypes.COMPONENT_OUTPUTS_CONSTANT.value
    show_type: str = "hide"
    plugin_code: str = ""


class Extensions(BaseModel):
    nodes: Dict[str, Any]


class Pipeline(BaseModel):
    id: str
    name: str
    nodes: List[Node]
    constants: List[Constant]
    extensions: Extensions = None
