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
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.conf import settings
from pipeline.core.flow.io import ArrayItemSchema, BooleanItemSchema, StringItemSchema

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService
from bkflow.utils.message import send_message

__group_name__ = _("蓝鲸服务(BK)")


class NotifyService(BKFlowBaseService):
    def inputs_format(self):
        return [
            self.InputItem(
                name=_("通知方式"),
                key="bk_notify_types",
                type="array",
                schema=ArrayItemSchema(
                    description=_("需要使用的通知方式，从 API 网关自动获取已实现的通知渠道"), item_schema=StringItemSchema(description=_("通知方式"))
                ),
            ),
            self.InputItem(
                name=_("接收人"),
                key="bk_notify_receivers",
                type="string",
                schema=StringItemSchema(description=_("接收通知的用户")),
            ),
            self.InputItem(
                name=_("通知标题"), key="bk_notify_title", type="string", schema=StringItemSchema(description=_("通知的标题"))
            ),
            self.InputItem(
                name=_("通知内容"), key="bk_notify_content", type="string", schema=StringItemSchema(description=_("通知的内容"))
            ),
            self.InputItem(
                name=_("通知执行人"),
                key="notify_executor",
                type="boolean",
                schema=BooleanItemSchema(description=_("通知执行人名字")),
            ),
        ]

    def outputs_format(self):
        return [
            self.OutputItem(
                name=_("通知结果"),
                key="notify_result",
                type="string",
                schema=StringItemSchema(description=_("通知结果")),
            ),
        ]

    def plugin_execute(self, data, parent_data):
        executor = parent_data.get_one_of_inputs("executor")

        notify_types = data.inputs.bk_notify_types
        title = data.inputs.bk_notify_title
        content = data.inputs.bk_notify_content
        receivers = data.inputs.bk_notify_receivers.split(",")
        notify_executor = data.inputs.notify_executor

        # 当通知接收人包含执行人时，执行人放在列表第一位，且对通知名单进行去重处理
        if notify_executor or executor in receivers:
            receivers.insert(0, executor)
        unique_receivers = sorted(set(receivers), key=receivers.index)

        has_error, error_message = send_message(
            executor=executor,
            notify_types=notify_types,
            receivers=",".join(unique_receivers),
            title=title,
            content=content,
        )

        if has_error:
            # 这里不需要返回 html 格式到前端，避免导致异常信息展示格式错乱
            data.set_outputs("ex_data", error_message.replace("<", "|").replace(">", "|"))
            return False

        return True


class NotifyComponent(Component):
    name = _("发送通知")
    desc = _(
        "通知方式从 API 网关自动获取已实现的通知渠道，API网关定义了这些消息通知组件的接口协议，但是并没有完全实现组件内容，"
        "用户可根据接口协议，重写此部分组件。API网关为降低实现消息通知组件的难度，提供了在线更新组件配置，"
        "不需编写组件代码的方案。详情请查阅PaaS->API网关->使用指南。"
    )
    code = "bk_notify"
    bound_service = NotifyService
    version = "v1.0"
    form = "%scomponents/notify/v1_0.js" % settings.STATIC_URL
