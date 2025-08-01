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

from django.test import TestCase
from pipeline.component_framework.test import (
    ComponentTestCase,
    ComponentTestMixin,
    ExecuteAssertion,
)

from bkflow.pipeline_plugins.components.collections.debug_plugin.v1_0_0 import (
    DebugPluginComponent,
)


class DebugPluginComponentTest(TestCase, ComponentTestMixin):
    def component_cls(self):
        return DebugPluginComponent

    def cases(self):
        return [DEBUG_PLUGIN_EXECUTE]


INPUTS = {"string_input": "string", "int_input": 1, "boolean_input": True, "object_input": json.dumps({"key": "value"})}

OUTPUT = {"string_output": "string", "int_output": 1, "boolean_output": True, "object_output": {"key": "value"}}

DEBUG_PLUGIN_EXECUTE = ComponentTestCase(
    name="debug plugin execute",
    inputs=INPUTS,
    parent_data={},
    execute_assertion=ExecuteAssertion(success=True, outputs=OUTPUT),
    schedule_assertion=None,
)
