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
    ScheduleAssertion,
)

from bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0 import (
    UniformAPIComponent,
)


class UniformAPIComponentTest(TestCase, ComponentTestMixin):
    def component_cls(self):
        return UniformAPIComponent

    def cases(self):
        return [
            STANDARD_RESPONSE_SUCCESS_CASE,
            STANDARD_RESPONSE_FAILURE_CASE,
            STANDARD_RESPONSE_NON_JSON_CASE,
            STANDARD_RESPONSE_POLLING_SUCCESS_CASE,
            STANDARD_RESPONSE_POLLING_FAILURE_CASE,
            NON_STANDARD_RESPONSE_SUCCESS_CASE,
            NON_STANDARD_RESPONSE_FAILURE_CASE,
        ]


API_INPUT_DATA = {
    "uniform_api_plugin_url": "http://example.com/api",
    "uniform_api_plugin_method": "POST",
    "response_data_path": None,
}

API_POLLING_INPUT_DATA = {
    "uniform_api_plugin_url": "http://example.com/api",
    "uniform_api_plugin_method": "GET",
    "uniform_api_plugin_polling": {
        "url": "http://example.com/polling",
        "task_tag_key": "task_id",
        "success_tag": {"key": "status", "value": "success"},
        "fail_tag": {"key": "status", "value": "failed"},
        "running_tag": {"key": "status", "value": "running"},
    },
    "response_data_path": None,
}

TEST_PARENT_DATA = {
    "operator": "admin",
    "task_space_id": 1,
    "task_scope_type": "project",
    "task_scope_value": "project-1",
    "task_id": 1,
    "task_name": "test_task",
}


class MockAPIResponse:
    def __init__(self, status_code, json_resp, message, result):
        self.resp = MagicMock(status_code=status_code)
        self.json_resp = json_resp
        self.message = message
        self.result = result
        if json_resp is None:
            # 模拟非JSON响应
            self.resp.text = "plain text response"
        else:
            self.resp.text = str(json_resp)


# 标准响应模式 - 成功场景
STANDARD_RESPONSE_SPACE_CONFIG = {
    "result": True,
    "message": "success",
    "data": {
        "configs": {
            "uniform_api": {"enable_standard_response": True},
            "credential": {"bk_app_code": "mock_app_code", "bk_app_secret": "mock_app_secret"},
        }
    },
}

STANDARD_RESPONSE_SUCCESS_API_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"data": {"task_id": "12345"}}, message="success", result=True
)

STANDARD_RESPONSE_SUCCESS_CLIENT = MagicMock()
STANDARD_RESPONSE_SUCCESS_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
STANDARD_RESPONSE_SUCCESS_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
STANDARD_RESPONSE_SUCCESS_CLIENT.request = MagicMock(return_value=STANDARD_RESPONSE_SUCCESS_API_RESPONSE)

STANDARD_RESPONSE_SUCCESS_CASE = ComponentTestCase(
    name="standard_response_success_case",
    inputs={**API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=True, outputs={"status_code": 200, "data": {"data": {"task_id": "12345"}}}
    ),
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=STANDARD_RESPONSE_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=STANDARD_RESPONSE_SUCCESS_CLIENT,
        ),
    ],
)

# 标准响应模式 - 失败场景（非200状态码）
STANDARD_RESPONSE_FAILURE_API_RESPONSE = MockAPIResponse(
    status_code=404, json_resp={"message": "Not Found"}, message="Not Found", result=False
)

STANDARD_RESPONSE_FAILURE_CLIENT = MagicMock()
STANDARD_RESPONSE_FAILURE_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
STANDARD_RESPONSE_FAILURE_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
STANDARD_RESPONSE_FAILURE_CLIENT.request = MagicMock(return_value=STANDARD_RESPONSE_FAILURE_API_RESPONSE)

STANDARD_RESPONSE_FAILURE_CASE = ComponentTestCase(
    name="standard_response_failure_case",
    inputs={**API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=False,
        outputs={
            "status_code": 404,
            "ex_data": "[uniform_api error] HTTP status code: 404, message: Not Found",
        },
    ),
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=STANDARD_RESPONSE_FAILURE_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=STANDARD_RESPONSE_FAILURE_CLIENT,
        ),
    ],
)

# 标准响应模式 - 非JSON响应
STANDARD_RESPONSE_NON_JSON_API_RESPONSE = MockAPIResponse(
    status_code=200, json_resp=None, message="success", result=True
)

STANDARD_RESPONSE_NON_JSON_CLIENT = MagicMock()
STANDARD_RESPONSE_NON_JSON_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
STANDARD_RESPONSE_NON_JSON_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
STANDARD_RESPONSE_NON_JSON_CLIENT.request = MagicMock(return_value=STANDARD_RESPONSE_NON_JSON_API_RESPONSE)

STANDARD_RESPONSE_NON_JSON_CASE = ComponentTestCase(
    name="standard_response_non_json_case",
    inputs={**API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={"status_code": 200, "data": "plain text response"}),
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=STANDARD_RESPONSE_NON_JSON_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=STANDARD_RESPONSE_NON_JSON_CLIENT,
        ),
    ],
)

# 标准响应模式 - 轮询成功
STANDARD_RESPONSE_POLLING_SUCCESS_API_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"status": "success", "data": {"result": "completed"}}, message="success", result=True
)

STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT = MagicMock()
STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT.request = MagicMock(
    return_value=STANDARD_RESPONSE_POLLING_SUCCESS_API_RESPONSE
)

STANDARD_RESPONSE_POLLING_SUCCESS_CASE = ComponentTestCase(
    name="standard_response_polling_success_case",
    inputs={**API_POLLING_INPUT_DATA, "need_polling": True, "trigger_data": {"task_id": "12345"}},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=False),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"result": "completed"}},
    ),
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT,
        ),
    ],
)

# 标准响应模式 - 轮询失败（非200状态码）
STANDARD_RESPONSE_POLLING_FAILURE_API_RESPONSE = MockAPIResponse(
    status_code=500, json_resp={"message": "Internal Server Error"}, message="Internal Server Error", result=False
)

STANDARD_RESPONSE_POLLING_FAILURE_CLIENT = MagicMock()
STANDARD_RESPONSE_POLLING_FAILURE_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
STANDARD_RESPONSE_POLLING_FAILURE_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
STANDARD_RESPONSE_POLLING_FAILURE_CLIENT.request = MagicMock(
    return_value=STANDARD_RESPONSE_POLLING_FAILURE_API_RESPONSE
)

STANDARD_RESPONSE_POLLING_FAILURE_CASE = ComponentTestCase(
    name="standard_response_polling_failure_case",
    inputs={**API_POLLING_INPUT_DATA, "need_polling": True, "trigger_data": {"task_id": "12345"}},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=False),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={
            "status_code": 500,
            "ex_data": "[uniform_api polling error] HTTP status code: 500, message: Internal Server Error",
        },
    ),
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=STANDARD_RESPONSE_POLLING_FAILURE_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=STANDARD_RESPONSE_POLLING_FAILURE_CLIENT,
        ),
    ],
)

# 非标准响应模式 - 成功场景
NON_STANDARD_RESPONSE_SPACE_CONFIG = {
    "result": True,
    "message": "success",
    "data": {
        "configs": {
            "uniform_api": {},
            "credential": {"bk_app_code": "mock_app_code", "bk_app_secret": "mock_app_secret"},
        }
    },
}

NON_STANDARD_RESPONSE_SUCCESS_API_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"result": True, "data": {"task_id": "12345"}}, message="success", result=True
)

NON_STANDARD_RESPONSE_SUCCESS_CLIENT = MagicMock()
NON_STANDARD_RESPONSE_SUCCESS_CLIENT.get_space_infos = MagicMock(return_value=NON_STANDARD_RESPONSE_SPACE_CONFIG)
NON_STANDARD_RESPONSE_SUCCESS_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
NON_STANDARD_RESPONSE_SUCCESS_CLIENT.request = MagicMock(return_value=NON_STANDARD_RESPONSE_SUCCESS_API_RESPONSE)

NON_STANDARD_RESPONSE_SUCCESS_CASE = ComponentTestCase(
    name="non_standard_response_success_case",
    inputs={**API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=True, outputs={"status_code": 200, "data": {"result": True, "data": {"task_id": "12345"}}}
    ),
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=NON_STANDARD_RESPONSE_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=NON_STANDARD_RESPONSE_SUCCESS_CLIENT,
        ),
    ],
)

# 非标准响应模式 - 失败场景（result=False）
NON_STANDARD_RESPONSE_FAILURE_API_RESPONSE = MockAPIResponse(
    status_code=200,
    json_resp={"result": False, "message": "Operation failed"},
    message="Operation failed",
    result=False,
)

NON_STANDARD_RESPONSE_FAILURE_CLIENT = MagicMock()
NON_STANDARD_RESPONSE_FAILURE_CLIENT.get_space_infos = MagicMock(return_value=NON_STANDARD_RESPONSE_SPACE_CONFIG)
NON_STANDARD_RESPONSE_FAILURE_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
NON_STANDARD_RESPONSE_FAILURE_CLIENT.request = MagicMock(return_value=NON_STANDARD_RESPONSE_FAILURE_API_RESPONSE)

NON_STANDARD_RESPONSE_FAILURE_CASE = ComponentTestCase(
    name="non_standard_response_failure_case",
    inputs={**API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=False,
        outputs={
            "status_code": 200,
            "ex_data": "[uniform_api error] HTTP status code: 200, message: Operation failed",
        },
    ),
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=NON_STANDARD_RESPONSE_FAILURE_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=NON_STANDARD_RESPONSE_FAILURE_CLIENT,
        ),
    ],
)
