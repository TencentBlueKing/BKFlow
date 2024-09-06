# -*- coding: utf-8 -*-
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
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import StringItemSchema

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService

__group_name__ = _("蓝鲸服务(BK)")


class DisplayService(BKFlowBaseService):
    def inputs_format(self):
        return [
            self.InputItem(
                name=_("展示内容"),
                key="bk_display_message",
                type="string",
                schema=StringItemSchema(description=_("展示内容")),
            ),
        ]

    def outputs_format(self):
        return []

    def plugin_execute(self, data, parent_data):
        return True


class DisplayComponent(Component):
    name = _("消息展示")
    code = "bk_display"
    bound_service = DisplayService
    version = "v1.0"
    form = "%scomponents/display/v1_0.js" % settings.STATIC_URL
    desc = _("本插件为仅用于消息展示的空节点")
