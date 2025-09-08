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
import json

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import (
    BooleanItemSchema,
    IntItemSchema,
    ObjectItemSchema,
    StringItemSchema,
)

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService

__group_name__ = _("蓝鲸服务(BK)")

__register_ignore__ = settings.ENVIRONMENT == "prod"


class DebugPluginService(BKFlowBaseService):
    def inputs_format(self):
        return [
            self.InputItem(
                name="string_input",
                key="string_input",
                type="string",
                schema=StringItemSchema(description="string input"),
            ),
            self.InputItem(
                name="int_input",
                key="int_input",
                type="int",
                schema=IntItemSchema(description="int input"),
            ),
            self.InputItem(
                name="boolean_input",
                key="boolean_input",
                type="boolean",
                schema=BooleanItemSchema(description="boolean input"),
            ),
            self.InputItem(
                name="object_input",
                key="object_input",
                type="object",
                schema=ObjectItemSchema(description="string input", property_schemas={}),
            ),
        ]

    def outputs_format(self):
        return [
            self.OutputItem(
                name="string_output",
                key="string_output",
                type="string",
                schema=StringItemSchema(description="string output"),
            ),
            self.OutputItem(
                name="int_output",
                key="int_output",
                type="int",
                schema=IntItemSchema(description="int output"),
            ),
            self.OutputItem(
                name="boolean_output",
                key="boolean_output",
                type="boolean",
                schema=BooleanItemSchema(description="boolean input"),
            ),
            self.OutputItem(
                name="object_output",
                key="object_output",
                type="object",
                schema=ObjectItemSchema(description="object output", property_schemas={}),
            ),
        ]

    def plugin_execute(self, data, parent_data):
        string_input = data.get_one_of_inputs("string_input")
        int_input = data.get_one_of_inputs("int_input")
        boolean_input = data.get_one_of_inputs("boolean_input")
        object_input = json.loads(data.get_one_of_inputs("object_input"))
        self.logger.info(
            f"string_input: {string_input}, int_input: {int_input},"
            f" boolean_input: {boolean_input}, object_input: {object_input}"
        )
        data.set_outputs("string_output", string_input)
        data.set_outputs("int_output", int_input)
        data.set_outputs("boolean_output", boolean_input)
        data.set_outputs("object_output", object_input)
        return True


class DebugPluginComponent(Component):
    name = "Debug Plugin"
    code = "debug_plugin"
    bound_service = DebugPluginService
    form = settings.STATIC_URL + "components/debug_plugin/v1_0_0.js"
    version = "v1.0.0"
    desc = "仅供调试"
