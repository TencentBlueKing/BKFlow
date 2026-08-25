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
from typing import Any, Dict, List, Optional, Union

from pipeline.variable_framework.models import VariableModel
from pydantic import BaseModel, Field, root_validator, validator

from bkflow.pipeline_converter.constants import A2FlowPluginType, NodeType


class A2FlowCondition(BaseModel):
    """a2flow v2 排他网关分支条件"""

    evaluate: str = "True"
    name: str = ""

    class Config:
        extra = "forbid"


class A2FlowAutoRetry(BaseModel):
    enable: bool = False
    interval: int = 0  # 秒
    times: int = 1  # >=1

    class Config:
        extra = "forbid"


class A2FlowTimeoutConfig(BaseModel):
    enable: bool = False
    seconds: int = 10
    action: str = "forced_fail"  # forced_fail / forced_fail_and_skip

    class Config:
        extra = "forbid"


class A2FlowFailureStrategy(BaseModel):
    """节点失败处理策略（仅对 Activity 生效）"""

    error_ignorable: bool = False
    retryable: bool = True
    skippable: bool = True
    auto_retry: A2FlowAutoRetry = Field(default_factory=A2FlowAutoRetry)
    timeout_config: A2FlowTimeoutConfig = Field(default_factory=A2FlowTimeoutConfig)

    class Config:
        extra = "forbid"


class A2FlowNode(BaseModel):
    """a2flow v2 流程节点（输入侧）"""

    id: str
    name: str = ""
    type: str = NodeType.ACTIVITY
    code: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    next: Union[str, List[str], None] = None
    stage_name: Optional[str] = None
    plugin_type: Optional[str] = None
    conditions: Optional[List[A2FlowCondition]] = None
    default_next: Optional[str] = None
    converge_gateway_id: Optional[str] = None
    constants: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    always_use_latest: bool = False
    failure_strategy: Optional[A2FlowFailureStrategy] = None

    @validator("type", pre=True, always=True)
    def set_default_type(cls, v):
        return v or NodeType.ACTIVITY

    @validator("plugin_type")
    def validate_plugin_type(cls, v):
        if v is not None:
            valid_values = {e.value for e in A2FlowPluginType}
            if v not in valid_values:
                raise ValueError(f"plugin_type 必须是 {valid_values} 之一，收到: {v}")
        return v

    @root_validator
    def validate_subprocess_required_fields(cls, values):
        """SubProcess 类型节点必须提供 template_id"""
        if values.get("type") != NodeType.SUBPROCESS:
            return values
        if not values.get("template_id"):
            node_id = values.get("id") or "<unknown>"
            raise ValueError("SubProcess 节点 '{}' 缺少必填字段: template_id".format(node_id))
        return values

    class Config:
        extra = "forbid"


class A2FlowVariable(BaseModel):
    """a2flow v2 流程变量（输入侧）"""

    key: str
    name: str = ""
    value: Any = ""
    source_type: str = "custom"
    custom_type: str = "input"
    description: str = ""
    show_type: str = "show"
    source_info: Dict[str, Any] = Field(default_factory=dict)
    validation: str = ""

    class Config:
        extra = "forbid"


class A2FlowPipeline(BaseModel):
    """a2flow v2 流程定义（输入侧）"""

    version: str = "2.0"
    name: str
    desc: str = ""
    nodes: List[A2FlowNode]
    variables: List[A2FlowVariable] = Field(default_factory=list)

    @validator("nodes")
    def nodes_not_empty(cls, v):
        if not v:
            raise ValueError("nodes 不能为空")
        return v

    @root_validator
    def validate_variables_custom_type(cls, values):
        """在 Pipeline 级别一次性预取合法变量类型集合"""
        variables = values.get("variables") or []
        if not variables:
            return values

        valid_codes = {item.code for item in VariableModel.objects.all().only("code")}
        for var in variables:
            if var.custom_type == "":
                continue
            if var.custom_type not in valid_codes:
                raise ValueError(
                    "custom_type 必须是有效的变量类型，收到: {}，可用的变量类型: {}".format(var.custom_type, sorted(valid_codes))
                )
        return values

    class Config:
        extra = "forbid"
