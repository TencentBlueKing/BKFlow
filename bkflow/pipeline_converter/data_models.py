# -*- coding: utf-8 -*-
from typing import List, Any, Dict

from pydantic import BaseModel


class Node(BaseModel):
    id: str
    name: str = ""
    type: str
    next: str | List[str] | None


class ComponentField(BaseModel):
    value: Any
    type: str
    key: str
    need_render: bool = True


class Component(BaseModel):
    code: str
    version: str
    data: List[ComponentField]


class AutoRetryConfig(BaseModel):
    enable: bool
    interval: int
    times: int


class TimeoutConfig(BaseModel):
    enable: bool
    seconds: int
    action: str


class ComponentNode(Node):
    component: Component
    skippable: bool = True
    retryable: bool = True
    error_ignorable: bool = False
    auto_retry: AutoRetryConfig = None
    timeout_config: TimeoutConfig = None


class Gateway(Node):
    pass


class ParallelGateway(Gateway):
    converge_gateway_id: str


class ConvergeGateway(Gateway):
    pass


class Condition(BaseModel):
    id: str
    name: str
    lang: str = "boolrule"
    expr: str


class ExclusiveGateway(Gateway):
    conditions: List[Condition]
    converge_gateway_id: str = ""


class Constant(BaseModel):
    name: str
    type: str
    key: str
    value: Any
    version: str = "legacy"
    source_type: str
    pre_render_mako: bool = False


class Extensions(BaseModel):
    nodes: Dict[str, Any]


class Pipeline(BaseModel):
    id: str
    name: str
    nodes: List[Node]
    constants: List[Constant]
    extensions: Extensions
