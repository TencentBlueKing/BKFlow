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


from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import ObjectItemSchema, StringItemSchema

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService

__group_name__ = _("蓝鲸服务(BK)")


class PauseService(BKFlowBaseService):
    __need_schedule__ = True

    def plugin_execute(self, data, parent_data):
        return True

    def plugin_schedule(self, data, parent_data, callback_data=None):
        if callback_data is not None:
            data.outputs.callback_data = callback_data
            self.finish_schedule()
        return True

    def inputs_format(self):
        return [
            self.InputItem(
                name=_("描述"),
                key="description",
                type="string",
                schema=StringItemSchema(description=_("描述")),
            )
        ]

    def outputs_format(self):
        return [
            self.OutputItem(
                name=_("API回调数据"),
                key="callback_data",
                type="object",
                schema=ObjectItemSchema(
                    description=_("通过node_callback API接口回调并传入数据,支持dict数据"),
                    property_schemas={},
                ),
            ),
        ]


class PauseComponent(Component):
    name = _("暂停")
    code = "pause_node"
    bound_service = PauseService
    form = settings.STATIC_URL + "components/pause/legacy.js"
    desc = _("该节点可以通过node_callback API接口进行回调并传入数据，callback_data参数为dict类型，回调数据会作为该节点的输出数据")
