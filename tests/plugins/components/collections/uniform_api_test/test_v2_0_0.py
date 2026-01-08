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

from bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0 import (
    UniformAPIComponent,
)

# Mock settings patcher for API request timeout
SETTINGS_PATCHER = Patcher(
    target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.settings",
    return_value=MagicMock(
        BKAPP_API_PLUGIN_REQUEST_TIMEOUT=30,
        USE_BKFLOW_CREDENTIAL=False,
    ),
)


class UniformAPIComponentTest(TestCase, ComponentTestMixin):
    def component_cls(self):
        return UniformAPIComponent

    def cases(self):
        return [
            API_TRIGGER_FAIL_CASE,
            API_POLLING_FAIL_CASE,
            API_TRIGGER_SUCCESS_CASE,
            API_POLLING_SUCCESS_CASE,
            API_POLLING_RUNNING_CASE,
            API_POLLING_FAIL_STATUS_CASE,
            API_CALLBACK_SUCCESS_CASE,
            API_CALLBACK_FAIL_CASE,
            API_TRIGGER_REQUEST_EXCEPTION_CASE,
            API_TRIGGER_NO_JSON_RESPONSE_CASE,
            API_TRIGGER_RESULT_FALSE_CASE,
            API_POLLING_NO_TASK_TAG_CASE,
        ]


API_INPUT_DATA = {
    "uniform_api_plugin_callback": {
        "success_tag": {"key": "result", "value": "success"},
        "fail_tag": {"key": "result", "value": "fail"},
    },
    "uniform_api_plugin_url": "http://example.com",
    "uniform_api_plugin_polling": True,
    "uniform_api_plugin_method": "GET",
    "response_data_path": None,
}

API_POLLING_INPUT_DATA = {**API_INPUT_DATA, "need_polling": True}

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

    def extract_json_resp_with_jmespath(self, path):
        import jmespath

        return jmespath.search(path, self.json_resp)


CLIENT_API_SPACE_CONFIG = {
    "result": False,
    "message": "api trigger fail",
}
SUCCESS_API_HEADER = {
    "X-Bkapi-Authorization": "mock_token",
    "X-Bkapi-App-Code": "mock_app_code",
    "X-Bkapi-App-Secret": "mock_app_secret",
    "X-Bkapi-User": "mock_operator",
}
SUCCESS_API_RESPONSE_DATA = MockAPIResponse(
    status_code=200, json_resp={"result": True, "data": {"space_id": 1}}, message="success", result=True
)


class MockUniformAPIClient:
    def __init__(self, get_space_infos=None, gen_default_apigw_header=None, request=None):
        self.get_space_infos = MagicMock(return_value=get_space_infos)
        self.gen_default_apigw_header = MagicMock(return_value=gen_default_apigw_header)
        self.request = MagicMock(return_value=request)


SUCCESS_API_CLIENT = MockUniformAPIClient(
    get_space_infos=CLIENT_API_SPACE_CONFIG,
    gen_default_apigw_header=SUCCESS_API_HEADER,
    request=SUCCESS_API_RESPONSE_DATA,
)


API_TRIGGER_FAIL_CASE = ComponentTestCase(
    name="api_trigger_fail_case",
    inputs={**API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        outputs={"ex_data": "[uniform_api error] get apigw credential failed: api trigger fail"}, success=False
    ),
    schedule_assertion=ScheduleAssertion(
        outputs={"need_callback": False, "status_code": 200}, success=False, callback_data={"result": False}
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=SUCCESS_API_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=SUCCESS_API_CLIENT,
        ),
    ],
)

API_POLLING_FAIL_CASE = ComponentTestCase(
    name="api_polling_fail_case",
    inputs={**API_POLLING_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        outputs={"ex_data": "[uniform_api error] get apigw credential failed: api trigger fail"}, success=False
    ),
    schedule_assertion=ScheduleAssertion(
        success=False,
        callback_data={"result": False},
        outputs={"need_callback": False, "status_code": 200},
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=SUCCESS_API_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=SUCCESS_API_CLIENT,
        ),
    ],
)

# ========== 成功场景测试用例 ==========

# 通用成功的空间配置
SUCCESS_SPACE_CONFIG = {
    "result": True,
    "message": "success",
    "data": {
        "configs": {
            "uniform_api": {
                "api": {
                    "default": {
                        "meta_apis": "http://example.com/meta_apis",
                        "api_categories": "http://example.com/api_categories",
                        "display_name": "默认API",
                    }
                },
                "common": {"enable_standard_response": False},
            },
            "credential": {"bk_app_code": "mock_app_code", "bk_app_secret": "mock_app_secret"},
        }
    },
}

# API触发成功 - 无轮询无回调
SIMPLE_API_INPUT_DATA = {
    "uniform_api_plugin_url": "http://example.com/api",
    "uniform_api_plugin_method": "POST",
    "response_data_path": None,
}

SIMPLE_SUCCESS_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"result": True, "data": {"task_id": "12345"}}, message="success", result=True
)

TRIGGER_SUCCESS_CLIENT = MagicMock()
TRIGGER_SUCCESS_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
TRIGGER_SUCCESS_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
TRIGGER_SUCCESS_CLIENT.request = MagicMock(return_value=SIMPLE_SUCCESS_RESPONSE)

API_TRIGGER_SUCCESS_CASE = ComponentTestCase(
    name="api_trigger_success_case",
    inputs={**SIMPLE_API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"result": True, "data": {"task_id": "12345"}}},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=TRIGGER_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=TRIGGER_SUCCESS_CLIENT,
        ),
    ],
)

# 轮询成功场景
POLLING_INPUT_DATA = {
    "uniform_api_plugin_url": "http://example.com/api",
    "uniform_api_plugin_method": "GET",
    "uniform_api_plugin_polling": {
        "url": "http://example.com/polling",
        "task_tag_key": "task_id",
        "success_tag": {"key": "status", "value": "success", "data_key": "data.result"},
        "fail_tag": {"key": "status", "value": "failed", "msg_key": "message"},
        "running_tag": {"key": "status", "value": "running"},
    },
    "response_data_path": None,
}

# 触发API返回任务标识
POLLING_TRIGGER_RESPONSE = MockAPIResponse(
    status_code=200,
    json_resp={"result": True, "task_id": "12345", "message": "Task started"},
    message="success",
    result=True,
)
# 轮询API返回成功状态
POLLING_SUCCESS_RESPONSE = MockAPIResponse(
    status_code=200,
    json_resp={"result": True, "status": "success", "data": {"result": "completed"}},
    message="success",
    result=True,
)

POLLING_SUCCESS_CLIENT = MagicMock()
POLLING_SUCCESS_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
POLLING_SUCCESS_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
POLLING_SUCCESS_CLIENT.request = MagicMock(side_effect=[POLLING_TRIGGER_RESPONSE, POLLING_SUCCESS_RESPONSE])

API_POLLING_SUCCESS_CASE = ComponentTestCase(
    name="api_polling_success_case",
    inputs={**POLLING_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=[
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
            },
            schedule_finished=False,
        ),
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
                "data": "completed",
            },
            schedule_finished=True,
        ),
    ],
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=POLLING_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=POLLING_SUCCESS_CLIENT,
        ),
    ],
)

# 轮询进行中场景
POLLING_RUNNING_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"result": True, "status": "running", "data": {}}, message="success", result=True
)

POLLING_RUNNING_CLIENT = MagicMock()
POLLING_RUNNING_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
POLLING_RUNNING_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
POLLING_RUNNING_CLIENT.request = MagicMock(
    side_effect=[POLLING_TRIGGER_RESPONSE, POLLING_RUNNING_RESPONSE, POLLING_SUCCESS_RESPONSE]
)

API_POLLING_RUNNING_CASE = ComponentTestCase(
    name="api_polling_running_case",
    inputs={**POLLING_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=[
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
            },
            schedule_finished=False,
        ),
        # 第二次轮询返回running状态，继续调度
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
            },
            schedule_finished=False,
        ),
        # 第三次轮询返回成功状态
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
                "data": "completed",
            },
            schedule_finished=True,
        ),
    ],
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=POLLING_RUNNING_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=POLLING_RUNNING_CLIENT,
        ),
    ],
)

# 轮询失败状态场景
POLLING_FAIL_STATUS_RESPONSE = MockAPIResponse(
    status_code=200,
    json_resp={"result": True, "status": "failed", "message": "Task execution failed"},
    message="success",
    result=True,
)

POLLING_FAIL_STATUS_CLIENT = MagicMock()
POLLING_FAIL_STATUS_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
POLLING_FAIL_STATUS_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
POLLING_FAIL_STATUS_CLIENT.request = MagicMock(side_effect=[POLLING_TRIGGER_RESPONSE, POLLING_FAIL_STATUS_RESPONSE])

API_POLLING_FAIL_STATUS_CASE = ComponentTestCase(
    name="api_polling_fail_status_case",
    inputs={**POLLING_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=[
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
            },
            schedule_finished=False,
        ),
        ScheduleAssertion(
            success=False,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
                "ex_data": "Task execution failed",
            },
            schedule_finished=False,
        ),
    ],
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=POLLING_FAIL_STATUS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=POLLING_FAIL_STATUS_CLIENT,
        ),
    ],
)

# 回调成功场景
CALLBACK_INPUT_DATA = {
    "uniform_api_plugin_url": "http://example.com/api",
    "uniform_api_plugin_method": "POST",
    "uniform_api_plugin_callback": {
        "success_tag": {"key": "status", "value": "success", "data_key": "data.result"},
        "fail_tag": {"key": "status", "value": "failed", "msg_key": "message"},
    },
    "response_data_path": None,
}

CALLBACK_TRIGGER_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"result": True, "message": "Task started"}, message="success", result=True
)

CALLBACK_SUCCESS_CLIENT = MagicMock()
CALLBACK_SUCCESS_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
CALLBACK_SUCCESS_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
CALLBACK_SUCCESS_CLIENT.request = MagicMock(return_value=CALLBACK_TRIGGER_RESPONSE)

API_CALLBACK_SUCCESS_CASE = ComponentTestCase(
    name="api_callback_success_case",
    inputs={**CALLBACK_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=True,
        outputs={"status_code": 200, "need_callback": True},
    ),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={
            "status_code": 200,
            "need_callback": True,
            "data": "callback_result_data",
        },
        schedule_finished=True,
        callback_data={"status": "success", "data": {"result": "callback_result_data"}},
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=CALLBACK_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=CALLBACK_SUCCESS_CLIENT,
        ),
    ],
)

# 回调失败场景
API_CALLBACK_FAIL_CASE = ComponentTestCase(
    name="api_callback_fail_case",
    inputs={**CALLBACK_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=True,
        outputs={"status_code": 200, "need_callback": True},
    ),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={
            "status_code": 200,
            "need_callback": True,
            "ex_data": "Callback failed",
        },
        schedule_finished=False,
        callback_data={"status": "failed", "message": "Callback failed"},
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=CALLBACK_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=CALLBACK_SUCCESS_CLIENT,
        ),
    ],
)

# 无凭证场景
NO_CREDENTIAL_SPACE_CONFIG = {
    "result": True,
    "message": "success",
    "data": {
        "configs": {
            "uniform_api": {
                "api": {
                    "default": {
                        "meta_apis": "http://example.com/meta_apis",
                        "api_categories": "http://example.com/api_categories",
                        "display_name": "默认API",
                    }
                },
            },
            # 没有 credential
        }
    },
}

NO_CREDENTIAL_CLIENT = MagicMock()
NO_CREDENTIAL_CLIENT.get_space_infos = MagicMock(return_value=NO_CREDENTIAL_SPACE_CONFIG)
NO_CREDENTIAL_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)

API_TRIGGER_NO_CREDENTIAL_CASE = ComponentTestCase(
    name="api_trigger_no_credential_case",
    inputs={**SIMPLE_API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={"ex_data": "不存在调用凭证"},
        schedule_finished=False,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=NO_CREDENTIAL_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=NO_CREDENTIAL_CLIENT,
        ),
    ],
)

# 请求异常场景
REQUEST_EXCEPTION_CLIENT = MagicMock()
REQUEST_EXCEPTION_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
REQUEST_EXCEPTION_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
REQUEST_EXCEPTION_CLIENT.request = MagicMock(side_effect=Exception("Connection timeout"))

API_TRIGGER_REQUEST_EXCEPTION_CASE = ComponentTestCase(
    name="api_trigger_request_exception_case",
    inputs={**SIMPLE_API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={"ex_data": "[uniform_api error] url request failed: Connection timeout"},
        schedule_finished=False,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=REQUEST_EXCEPTION_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=REQUEST_EXCEPTION_CLIENT,
        ),
    ],
)

# 无JSON响应场景
NO_JSON_RESPONSE = MockAPIResponse(status_code=200, json_resp=None, message="Not JSON", result=True)

NO_JSON_CLIENT = MagicMock()
NO_JSON_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
NO_JSON_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
NO_JSON_CLIENT.request = MagicMock(return_value=NO_JSON_RESPONSE)

API_TRIGGER_NO_JSON_RESPONSE_CASE = ComponentTestCase(
    name="api_trigger_no_json_response_case",
    inputs={**SIMPLE_API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={
            "status_code": 200,
            "ex_data": "[uniform_api error] get json response data failed: Not JSON",
        },
        schedule_finished=False,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=NO_JSON_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=NO_JSON_CLIENT,
        ),
    ],
)

# result=False 响应场景
RESULT_FALSE_RESPONSE = MockAPIResponse(
    status_code=200,
    json_resp={"result": False, "message": "Operation failed"},
    message="Operation failed",
    result=False,
)

RESULT_FALSE_CLIENT = MagicMock()
RESULT_FALSE_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
RESULT_FALSE_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
RESULT_FALSE_CLIENT.request = MagicMock(return_value=RESULT_FALSE_RESPONSE)

API_TRIGGER_RESULT_FALSE_CASE = ComponentTestCase(
    name="api_trigger_result_false_case",
    inputs={**SIMPLE_API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={
            "status_code": 200,
            "ex_data": "[uniform_api error] response result is False: Operation failed",
        },
        schedule_finished=False,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=RESULT_FALSE_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=RESULT_FALSE_CLIENT,
        ),
    ],
)

# 轮询无法匹配task_tag_key场景
POLLING_NO_TASK_TAG_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"result": True, "no_task_id": "12345"}, message="success", result=True
)

POLLING_NO_TASK_TAG_CLIENT = MagicMock()
POLLING_NO_TASK_TAG_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
POLLING_NO_TASK_TAG_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
POLLING_NO_TASK_TAG_CLIENT.request = MagicMock(side_effect=[POLLING_NO_TASK_TAG_RESPONSE, POLLING_SUCCESS_RESPONSE])

API_POLLING_NO_TASK_TAG_CASE = ComponentTestCase(
    name="api_polling_no_task_tag_case",
    inputs={**POLLING_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=[
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "no_task_id": "12345"},
            },
            schedule_finished=False,
        ),
        ScheduleAssertion(
            success=False,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "no_task_id": "12345"},
                "ex_data": (
                    "[uniform_api polling] can not matched task_tag_key task_id in output data"
                    " {'result': True, 'no_task_id': '12345'}"
                ),
            },
            schedule_finished=False,
        ),
    ],
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=POLLING_NO_TASK_TAG_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=POLLING_NO_TASK_TAG_CLIENT,
        ),
    ],
)

# 轮询配置无效场景
POLLING_INVALID_CONFIG_INPUT = {
    "uniform_api_plugin_url": "http://example.com/api",
    "uniform_api_plugin_method": "GET",
    "uniform_api_plugin_polling": {
        "url": "http://example.com/polling",
        # 缺少必需字段 task_tag_key
    },
    "response_data_path": None,
}

POLLING_INVALID_CONFIG_CLIENT = MagicMock()
POLLING_INVALID_CONFIG_CLIENT.get_space_infos = MagicMock(return_value=SUCCESS_SPACE_CONFIG)
POLLING_INVALID_CONFIG_CLIENT.gen_default_apigw_header = MagicMock(return_value=SUCCESS_API_HEADER)
POLLING_INVALID_CONFIG_CLIENT.request = MagicMock(return_value=POLLING_TRIGGER_RESPONSE)

API_POLLING_INVALID_CONFIG_CASE = ComponentTestCase(
    name="api_polling_invalid_config_case",
    inputs={**POLLING_INVALID_CONFIG_INPUT},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=[
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
            },
            schedule_finished=False,
        ),
        ScheduleAssertion(
            success=False,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"result": True, "task_id": "12345", "message": "Task started"},
            },
            schedule_finished=False,
        ),
    ],
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.InterfaceModuleClient",
            return_value=POLLING_INVALID_CONFIG_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v2_0_0.UniformAPIClient",
            return_value=POLLING_INVALID_CONFIG_CLIENT,
        ),
    ],
)
