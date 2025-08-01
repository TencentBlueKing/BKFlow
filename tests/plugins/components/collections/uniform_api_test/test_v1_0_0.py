"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock

from django.test import TestCase
from pipeline.component_framework.test import (
    ComponentTestCase,
    ComponentTestMixin,
    ExecuteAssertion,
    Patcher,
)

from bkflow.pipeline_plugins.components.collections.uniform_api.v1_0_0 import (
    UniformAPIComponent,
)


class UniformAPIComponentTest(TestCase, ComponentTestMixin):
    def component_cls(self):
        return UniformAPIComponent

    def cases(self):
        return [SUCCESS_TEST_CASE, FAILURE_TEST_CASE]


class MockRequestResult:
    def __init__(self, status_code, json_resp, message, result):
        self.resp = MagicMock(status_code=status_code)
        self.json_resp = json_resp
        self.message = message
        self.result = result


TEST_API_CONFIG = {
    "url": "https://example.com/api",
    "method": "POST",
    "params": [{"key": "param1", "value": "value1"}, {"key": "param2", "value": "value2"}],
    "timeout": 30,
}

TEST_PARENT_DATA = {
    "operator": "admin",
    "task_space_id": "space123",
    "task_scope_type": "project",
    "task_scope_value": "project123",
    "task_id": "task123",
    "task_name": "test_task",
}

SUCCESS_SPACE_INFO = {
    "result": True,
    "message": "success",
    "data": {
        "configs": {
            "uniform_api": {"enable_api_parameter_conversion": True},
            "credential": {"bk_app_code": "mock_app_code", "bk_app_secret": "mock_app_secret"},
        }
    },
}
SUCCESS_API_HEADERS = {
    "X-Bkapi-Authorization": "mock_token",
    "X-Bkapi-App-Code": "mock_app_code",
    "X-Bkapi-App-Secret": "mock_app_secret",
    "X-Bkapi-User": "mock_operator",
}
SUCCESS_API_RESPONSE = MockRequestResult(
    status_code=200, json_resp={"result": "success", "data": {"space_id": 1}}, message="success", result=True
)


class MockAPIClient:
    def __init__(self, get_space_infos=None, gen_default_apigw_header=None, request=None):
        self.get_space_infos = MagicMock(return_value=get_space_infos)
        self.gen_default_apigw_header = MagicMock(return_value=gen_default_apigw_header)
        self.request = MagicMock(return_value=request)


SUCCESS_CLIENT = MockAPIClient(
    get_space_infos=SUCCESS_SPACE_INFO, gen_default_apigw_header=SUCCESS_API_HEADERS, request=SUCCESS_API_RESPONSE
)
FAILURE_CLIENT = MockAPIClient(get_space_infos={"result": False, "message": "get space infos failed"})

SUCCESS_TEST_CASE = ComponentTestCase(
    name="uniform_api_success_test",
    inputs={"api_config": TEST_API_CONFIG},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=True, outputs={"status_code": 200, "data": {"result": "success", "data": {"space_id": 1}}}
    ),
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v1_0_0.InterfaceModuleClient",
            return_value=SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v1_0_0.UniformAPIClient",
            return_value=SUCCESS_CLIENT,
        ),
    ],
)

FAILURE_TEST_CASE = ComponentTestCase(
    name="uniform_api_failure_test",
    inputs={"api_config": TEST_API_CONFIG},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=False, outputs={"ex_data": "[uniform_api error] get apigw credential failed: get space infos failed"}
    ),
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v1_0_0.InterfaceModuleClient",
            return_value=FAILURE_CLIENT,
        )
    ],
)
