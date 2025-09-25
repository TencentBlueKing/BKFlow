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
import re
from enum import Enum

from django.utils.translation import ugettext_lazy as _

MAX_LEN_OF_TASK_NAME = 128
MAX_LEN_OF_TEMPLATE_NAME = 128
TEMPLATE_NODE_NAME_MAX_LENGTH = 50
USER_NAME_MAX_LENGTH = 32
ALL_SPACE = "*"
WHITE_LIST = "white_list"
BK_PLUGIN_SYNC_NUM = 100

formatted_key_pattern = re.compile(r"^\${(.*?)}$")


class PipelineContextObjType(Enum):
    instance = "instance"
    template = "template"


class TaskStates(Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class TaskOperationType(Enum):
    create = _("创建")
    delete = _("删除")
    update = _("修改")
    start = _("执行")
    pause = _("暂停")
    resume = _("继续")
    revoke = _("撤消")

    # 任务节点操作
    callback = _("回调")
    retry = _("重试")
    skip = _("跳过")
    skip_exg = _("跳过失败网关")
    skip_cpg = _("跳过并行条件网关")
    pause_subproc = _("暂停节点")
    resume_subproc = _("继续节点")
    forced_fail = _("强制失败")

    task_action = _("任务操作")
    nodes_action = _("节点操作")


class TaskOperationSource(Enum):
    """记录来源"""

    app = _("app 页面")
    api = _("api 接口")


class TemplateOperationType(Enum):
    create = _("创建")
    delete = _("删除")
    update = _("修改")


class TaskTriggerMethod(Enum):
    """任务触发方式"""

    api = _("api")
    manual = _("手动")
    timing = _("定时")
    subprocess = _("子流程")


class TemplateOperationSource(Enum):
    """记录来源"""

    app = _("app 页面")
    api = _("api 接口")
    parent = _("父任务")


class RecordType(Enum):
    """记录类型"""

    task = _("任务实例")
    task_node = _("任务节点")
    template = _("模版实例")


class WebhookScopeType(Enum):
    """webhook作用域类型"""

    SPACE = "space"


class WebhookEventType(Enum):
    """webhook事件类型"""

    TEMPLATE_UPDATE = "template_update"
    TEMPLATE_CREATE = "template_create"
    TASK_FAILED = "task_failed"
    TASK_FINISHED = "task_finished"
    TASK_CREATE = "task_create"


class TriggerConstantsMode(Enum):
    """触发器参数视图类型"""

    FORM = "form"
    JSON = "json"
