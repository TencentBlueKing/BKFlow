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

from pydantic import BaseModel, Field, validator

from bkflow.pipeline_converter.constants import A2FlowPluginType, NodeType


class A2FlowCondition(BaseModel):
    """a2flow v2 排他网关分支条件"""

    evaluate: str = "True"
    name: str = ""

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

    class Config:
        extra = "forbid"
