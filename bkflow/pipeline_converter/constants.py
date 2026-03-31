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
from enum import Enum


class NodeType:
    START_EVENT = "StartEvent"
    END_EVENT = "EndEvent"
    ACTIVITY = "Activity"
    PARALLEL_GATEWAY = "ParallelGateway"
    CONDITIONAL_PARALLEL_GATEWAY = "ConditionalParallelGateway"
    EXCLUSIVE_GATEWAY = "ExclusiveGateway"
    CONVERGE_GATEWAY = "ConvergeGateway"


BRANCH_GATEWAY_TYPES = {
    NodeType.PARALLEL_GATEWAY,
    NodeType.CONDITIONAL_PARALLEL_GATEWAY,
    NodeType.EXCLUSIVE_GATEWAY,
}

GATEWAY_TYPES = BRANCH_GATEWAY_TYPES | {NodeType.CONVERGE_GATEWAY}

RESERVED_IDS = {"start", "end"}


class A2FlowPluginType(str, Enum):
    COMPONENT = "component"
    REMOTE_PLUGIN = "remote_plugin"
    UNIFORM_API = "uniform_api"


class A2FlowVersion(str, Enum):
    V1 = "1.0"
    V2 = "2.0"


SUPPORTED_V2_ALIASES = (None, "", "2", "2.0", 2, 2.0)


def normalize_a2flow_version(version):
    """将各种 v2 版本表示统一为 '2.0'，非 v2 版本原样返回字符串形式"""
    if version in SUPPORTED_V2_ALIASES:
        return "2.0"
    return str(version)


DEFAULT_ACTIVITY_CONFIG = {
    "auto_retry": {"enable": False, "interval": 0, "times": 1},
    "timeout_config": {"action": "forced_fail", "enable": False, "seconds": 10},
    "error_ignorable": False,
    "retryable": True,
    "skippable": True,
    "optional": True,
    "labels": [],
    "loop": None,
}
