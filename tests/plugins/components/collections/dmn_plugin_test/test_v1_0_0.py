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

from unittest.mock import MagicMock

from django.test import TestCase
from pipeline.component_framework.test import (
    Call,
    CallAssertion,
    ComponentTestCase,
    ComponentTestMixin,
    ExecuteAssertion,
    Patcher,
)

from bkflow.pipeline_plugins.components.collections.dmn_plugin.v1_0_0 import (
    DmnPluginComponent,
)

TEST_SPACE_ID = "some_space_id"
TEST_TABLE_ID = "some_table_id"
TEST_FACTS = {
    "input_param_1": {"value": "some_value", "variable": False},
    "input_param_2": {"value": "another_value", "variable": True},
}

SUCCESS_RESPONSE = {
    "result": True,
    "data": {
        "name": "some_decision_table",
        "data": {
            "inputs": [{"id": "input_param_1", "name": "input_param_1", "type": "string"}],
            "outputs": [{"id": "output_param_1", "name": "output_param_1", "type": "string"}],
            "records": [
                {
                    "inputs": {
                        "type": "common",
                        "conditions": [
                            {"compare": "equals", "right": {"obj": {"type": "string", "value": "some_value"}}}
                        ],
                    },
                    "outputs": {"output_param_1": "some_output_value"},
                }
            ],
        },
    },
}

FAIL_RESPONSE = {"result": False, "message": "some_error_message"}


class MockClient:
    def __init__(self, get_decision_table=None):
        self.get_decision_table = MagicMock(return_value=get_decision_table)


MOCK_SUCCESS_CLIENT = MockClient(get_decision_table=SUCCESS_RESPONSE)
MOCK_FAIL_CLIENT = MockClient(get_decision_table=FAIL_RESPONSE)


class DmnPluginComponentTest(TestCase, ComponentTestMixin):
    def component_cls(self):
        return DmnPluginComponent

    def cases(self):
        return [DMN_PLUGIN_SUCCESS_CASE, DMN_PLUGIN_FAIL_CASE]


DMN_PLUGIN_SUCCESS_CASE = ComponentTestCase(
    name="dmn_plugin_success_case",
    inputs={"facts": TEST_FACTS, "table_id": TEST_TABLE_ID},
    parent_data={"task_space_id": TEST_SPACE_ID},
    execute_assertion=ExecuteAssertion(success=True, outputs={"output_param_1": "some_output_value"}),
    execute_call_assertion=[
        CallAssertion(
            func=MOCK_SUCCESS_CLIENT.get_decision_table,
            calls=[Call(decision_table_id=TEST_TABLE_ID, data={"space_id": TEST_SPACE_ID})],
        )
    ],
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.dmn_plugin.v1_0_0.InterfaceModuleClient",
            return_value=MOCK_SUCCESS_CLIENT,
        )
    ],
)

DMN_PLUGIN_FAIL_CASE = ComponentTestCase(
    name="dmn_plugin_fail_case",
    inputs={"facts": TEST_FACTS, "table_id": TEST_TABLE_ID},
    parent_data={"task_space_id": TEST_SPACE_ID},
    execute_assertion=ExecuteAssertion(
        success=False, outputs={"ex_data": "[get decision table] error: some_error_message"}
    ),
    execute_call_assertion=[
        CallAssertion(
            func=MOCK_FAIL_CLIENT.get_decision_table,
            calls=[Call(decision_table_id=TEST_TABLE_ID, data={"space_id": TEST_SPACE_ID})],
        )
    ],
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.dmn_plugin.v1_0_0.InterfaceModuleClient",
            return_value=MOCK_FAIL_CLIENT,
        )
    ],
)
