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

from unittest.mock import MagicMock, patch

from bamboo_engine.eri import ContextValue, ContextValueType
from django.test import TestCase
from pipeline.component_framework.test import (
    Call,
    CallAssertion,
    ComponentTestCase,
    ComponentTestMixin,
    ExecuteAssertion,
    Patcher,
)

from bkflow.pipeline_plugins.components.collections.value_assign.v1_0_0 import (
    ValueAssignComponent,
    ValueAssignService,
)


class ValueAssignComponentTest(TestCase, ComponentTestMixin):
    def setUp(self):
        ValueAssignService.top_pipeline_id = "top_pipeline_id"
        # 默认关闭trace开关
        self.trace_patcher = patch("django.conf.settings.ENABLE_OTEL_TRACE", False)
        self.trace_patcher.start()
        super().setUp()

    def tearDown(self):
        self.trace_patcher.stop()
        super().tearDown()

    def component_cls(self):
        return ValueAssignComponent

    def cases(self):
        return [SUCCESS_TEST_CASE, FAILURE_TEST_CASE]


ASSIGNMENT_DATA = [
    {"key": "var1", "value": "hello", "value_type": "String"},
]

SUCCESS_CONTEXT_VALUES = [ContextValue(key="${var1}", type=ContextValueType.PLAIN, value="123", code=None)]
FAILURE_CONTEXT_VALUES = [ContextValue(key="${var1}", type=ContextValueType.PLAIN, value=123, code=None)]


BAMBOO_RUNTIME_CLASS = "bkflow.pipeline_plugins.components.collections.value_assign.v1_0_0.BambooDjangoRuntime"


class MockContextClient:
    def __init__(self, get_context_values):
        self.get_context_values = MagicMock(return_value=get_context_values)
        self.update_context_values = MagicMock(return_value=True)


SUCCESS_CLIENT = MockContextClient(get_context_values=SUCCESS_CONTEXT_VALUES)
FAILURE_CLIENT = MockContextClient(get_context_values=FAILURE_CONTEXT_VALUES)


SUCCESS_TEST_CASE = ComponentTestCase(
    name="value_assign_success_test",
    inputs={"bk_assignment_list": ASSIGNMENT_DATA},
    parent_data={},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=None,
    execute_call_assertion=[
        CallAssertion(
            func=SUCCESS_CLIENT.get_context_values, calls=[Call(pipeline_id="top_pipeline_id", keys={"${var1}"})]
        )
    ],
    patchers=[Patcher(target=BAMBOO_RUNTIME_CLASS, return_value=SUCCESS_CLIENT)],
)

FAILURE_TEST_CASE = ComponentTestCase(
    name="value_assign_failure_test",
    inputs={"bk_assignment_list": ASSIGNMENT_DATA},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=False, outputs={"ex_data": "expected type String not match target variable type <class 'int'>"}
    ),
    schedule_assertion=None,
    execute_call_assertion=[
        CallAssertion(
            func=FAILURE_CLIENT.get_context_values,
            calls=[Call(pipeline_id="top_pipeline_id", keys={"${var1}"})],
        )
    ],
    patchers=[Patcher(target=BAMBOO_RUNTIME_CLASS, return_value=FAILURE_CLIENT)],
)
