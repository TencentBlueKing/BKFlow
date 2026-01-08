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
import datetime

from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


class TaskContext:
    """
    @summary: 流程任务内置环境变量
    """

    prefix = "_system"

    def __init__(self, taskflow):
        self.task_space_id = taskflow.space_id
        self.task_scope_type = taskflow.scope_type
        self.task_scope_value = taskflow.scope_value
        self.operator = taskflow.executor
        self.executor = taskflow.executor
        self.task_id = taskflow.id
        self.task_name = taskflow.name
        self.is_mock = taskflow.create_method == "MOCK"
        tz = timezone.pytz.timezone(settings.TIME_ZONE)
        self.task_start_time = datetime.datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M:%S")

        # 从extra_info中提取custom_context，使其可以通过parent_data.inputs访问
        extra_info = getattr(taskflow, "extra_info", {}) or {}
        custom_context = extra_info.get("custom_context", {}) or {}
        # 将custom_context中的字段添加到TaskContext的属性中，使其可以通过parent_data.inputs访问
        for key, value in custom_context.items():
            setattr(self, key, value)

    def context(self):
        return {"${%s}" % TaskContext.prefix: {"type": "plain", "is_param": True, "value": self}}

    @classmethod
    def to_flat_key(cls, key):
        return "${{{}.{}}}".format(cls.prefix, key)

    @classmethod
    def flat_details(cls):
        # index: 展示在前端全局变量的顺序，越小越靠前
        details = {
            cls.to_flat_key("task_name"): {
                "key": cls.to_flat_key("task_name"),
                "name": _("任务名称"),
                "index": -1,
                "desc": "",
            },
            cls.to_flat_key("task_id"): {
                "key": cls.to_flat_key("task_id"),
                "index": -2,
                "name": _("任务ID"),
                "desc": "",
            },
            cls.to_flat_key("task_start_time"): {
                "key": cls.to_flat_key("task_start_time"),
                "name": _("任务开始时间"),
                "index": -3,
                "desc": "",
            },
            cls.to_flat_key("operator"): {
                "key": cls.to_flat_key("operator"),
                "name": _("任务的执行人（点击开始执行的人员）"),
                "index": -4,
                "desc": "",
            },
        }
        for item in list(details.values()):
            item.update(
                {
                    "show_type": "hide",
                    "source_type": "system",
                    "source_tag": "",
                    "source_info": {},
                    "custom_type": "",
                    "value": "",
                    "hook": False,
                    "validation": "",
                }
            )
        return details
