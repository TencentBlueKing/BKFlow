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
from unittest.mock import MagicMock, patch

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

# Mock settings patcher for API request timeout
SETTINGS_PATCHER = Patcher(
    target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.settings",
    return_value=MagicMock(BKAPP_API_PLUGIN_REQUEST_TIMEOUT=30),
)


class UniformAPIComponentTest(TestCase, ComponentTestMixin):
    def setUp(self):
        # 默认关闭trace开关
        self.trace_patcher = patch("django.conf.settings.ENABLE_OTEL_TRACE", False)
        self.trace_patcher.start()
        super().setUp()

    def tearDown(self):
        self.trace_patcher.stop()
        super().tearDown()

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
            CREDENTIAL_KEY_USER_PROVIDED_CASE,
            CREDENTIAL_KEY_SPACE_CONFIG_CASE,
            API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_CASE,
            # 新增测试用例
            CALLBACK_SUCCESS_CASE,
            CALLBACK_FAILURE_CASE,
            RESPONSE_DATA_PATH_CASE,
            CUSTOM_HEADERS_CASE,
            NO_CREDENTIAL_CASE,
            REQUEST_EXCEPTION_CASE,
            EXCLUDE_NONE_FIELDS_CASE,
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
        "success_tag": {"key": "status", "value": "success", "data_key": "data.result"},
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
            "uniform_api": {
                "api": {
                    "default": {
                        "meta_apis": "http://example.com/meta_apis",
                        "api_categories": "http://example.com/api_categories",
                        "display_name": "默认API",
                    }
                },
                "common": {"enable_standard_response": True},
            },
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
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"data": {"task_id": "12345"}}},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
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
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={
            "status_code": 404,
            "ex_data": "[uniform_api error] HTTP status code: 404, message: Not Found",
        },
        schedule_finished=False,
    ),
    patchers=[
        SETTINGS_PATCHER,
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
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": "plain text response"},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
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
# 触发API返回任务标识
STANDARD_RESPONSE_POLLING_TRIGGER_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"task_id": "12345", "message": "Task started"}, message="success", result=True
)
# 轮询API返回成功状态
STANDARD_RESPONSE_POLLING_SUCCESS_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"status": "success", "data": {"result": "completed"}}, message="success", result=True
)

STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT = MagicMock()
STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
# 使用 side_effect 返回不同的响应：第一次触发返回 task_id，第二次轮询返回成功状态
STANDARD_RESPONSE_POLLING_SUCCESS_CLIENT.request = MagicMock(
    side_effect=[STANDARD_RESPONSE_POLLING_TRIGGER_RESPONSE, STANDARD_RESPONSE_POLLING_SUCCESS_RESPONSE]
)

STANDARD_RESPONSE_POLLING_SUCCESS_CASE = ComponentTestCase(
    name="standard_response_polling_success_case",
    inputs={**API_POLLING_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=[
        # 第一次 schedule: 触发 API，设置 need_polling 和 trigger_data
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"task_id": "12345", "message": "Task started"},
            },
            schedule_finished=False,
        ),
        # 第二次 schedule: 轮询 API，获取成功状态
        ScheduleAssertion(
            success=True,
            outputs={
                "status_code": 200,
                "need_polling": True,
                "trigger_data": {"task_id": "12345", "message": "Task started"},
                "data": "completed",
            },
            schedule_finished=True,
        ),
    ],
    patchers=[
        SETTINGS_PATCHER,
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
    inputs={**API_POLLING_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={
            "status_code": 500,
            "ex_data": "[uniform_api error] HTTP status code: 500, message: Internal Server Error",
        },
        schedule_finished=False,
    ),
    patchers=[
        SETTINGS_PATCHER,
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
            "uniform_api": {
                "api": {
                    "default": {
                        "meta_apis": "http://example.com/meta_apis",
                        "api_categories": "http://example.com/api_categories",
                        "display_name": "默认API",
                    }
                },
            },
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
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"result": True, "data": {"task_id": "12345"}}},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
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
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=False,
        outputs={
            "status_code": 200,
            "ex_data": "[uniform_api error] HTTP status code: 200, message: Operation failed",
        },
        schedule_finished=False,
    ),
    patchers=[
        SETTINGS_PATCHER,
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

# 凭证选择测试用例
CREDENTIAL_KEY_USER_PROVIDED_SPACE_CONFIG = {
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
                "common": {"enable_standard_response": True},
            },
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
    },
}

CREDENTIAL_KEY_USER_PROVIDED_API_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"data": {"task_id": "12345"}}, message="success", result=True
)

CREDENTIAL_KEY_USER_PROVIDED_CLIENT = MagicMock()
CREDENTIAL_KEY_USER_PROVIDED_CLIENT.get_space_infos = MagicMock(return_value=CREDENTIAL_KEY_USER_PROVIDED_SPACE_CONFIG)
CREDENTIAL_KEY_USER_PROVIDED_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
CREDENTIAL_KEY_USER_PROVIDED_CLIENT.request = MagicMock(return_value=CREDENTIAL_KEY_USER_PROVIDED_API_RESPONSE)

CREDENTIAL_KEY_USER_PROVIDED_CASE = ComponentTestCase(
    name="credential_key_user_provided_case",
    inputs={
        **API_INPUT_DATA,
        "uniform_api_plugin_credential_key": "custom_credential",
    },
    parent_data={
        **TEST_PARENT_DATA,
        "credentials": {
            "custom_credential": {
                "bk_app_code": "user_app_code",
                "bk_app_secret": "user_app_secret",
            }
        },
    },
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"data": {"task_id": "12345"}}},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=CREDENTIAL_KEY_USER_PROVIDED_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=CREDENTIAL_KEY_USER_PROVIDED_CLIENT,
        ),
    ],
)

# credential_key 匹配空间配置的 api_gateway_credential_name
CREDENTIAL_KEY_SPACE_CONFIG_SPACE_CONFIG = {
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
                "common": {"enable_standard_response": True},
            },
            "api_gateway_credential_name": "custom_credential",
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
    },
}

CREDENTIAL_KEY_SPACE_CONFIG_CLIENT = MagicMock()
CREDENTIAL_KEY_SPACE_CONFIG_CLIENT.get_space_infos = MagicMock(return_value=CREDENTIAL_KEY_SPACE_CONFIG_SPACE_CONFIG)
CREDENTIAL_KEY_SPACE_CONFIG_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
CREDENTIAL_KEY_SPACE_CONFIG_CLIENT.request = MagicMock(return_value=CREDENTIAL_KEY_USER_PROVIDED_API_RESPONSE)

CREDENTIAL_KEY_SPACE_CONFIG_CASE = ComponentTestCase(
    name="credential_key_space_config_case",
    inputs={
        **API_INPUT_DATA,
        "uniform_api_plugin_credential_key": "custom_credential",
    },
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"data": {"task_id": "12345"}}},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=CREDENTIAL_KEY_SPACE_CONFIG_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=CREDENTIAL_KEY_SPACE_CONFIG_CLIENT,
        ),
    ],
)

# 没有 credential_key，但 api_gateway_credential_name 在用户 credentials 中
API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_SPACE_CONFIG = {
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
                "common": {"enable_standard_response": True},
            },
            "api_gateway_credential_name": "default_credential",
            "credential": {"bk_app_code": "space_app", "bk_app_secret": "space_secret"},
        }
    },
}

API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_CLIENT = MagicMock()
API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_CLIENT.get_space_infos = MagicMock(
    return_value=API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_SPACE_CONFIG
)
API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_CLIENT.gen_default_apigw_header = MagicMock(
    return_value={"X-Bkapi-Authorization": "mock_token"}
)
API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_CLIENT.request = MagicMock(
    return_value=CREDENTIAL_KEY_USER_PROVIDED_API_RESPONSE
)

API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_CASE = ComponentTestCase(
    name="api_gateway_credential_name_user_provided_case",
    inputs={**API_INPUT_DATA},
    parent_data={
        **TEST_PARENT_DATA,
        "credentials": {
            "default_credential": {
                "bk_app_code": "user_app_code",
                "bk_app_secret": "user_app_secret",
            }
        },
    },
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"data": {"task_id": "12345"}}},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=API_GATEWAY_CREDENTIAL_NAME_USER_PROVIDED_CLIENT,
        ),
    ],
)

# ========== 回调模式测试用例 ==========

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
    status_code=200, json_resp={"message": "Task started"}, message="success", result=True
)

CALLBACK_SUCCESS_CLIENT = MagicMock()
CALLBACK_SUCCESS_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
CALLBACK_SUCCESS_CLIENT.gen_default_apigw_header = MagicMock(return_value={"X-Bkapi-Authorization": "mock_token"})
CALLBACK_SUCCESS_CLIENT.request = MagicMock(return_value=CALLBACK_TRIGGER_RESPONSE)

CALLBACK_SUCCESS_CASE = ComponentTestCase(
    name="callback_success_case",
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
            "data": "callback_data",
        },
        schedule_finished=True,
        callback_data={"status": "success", "data": {"result": "callback_data"}},
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=CALLBACK_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=CALLBACK_SUCCESS_CLIENT,
        ),
    ],
)

# 回调失败场景
CALLBACK_FAILURE_CASE = ComponentTestCase(
    name="callback_failure_case",
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
            "ex_data": "Callback execution failed",
        },
        schedule_finished=False,
        callback_data={"status": "failed", "message": "Callback execution failed"},
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=CALLBACK_SUCCESS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=CALLBACK_SUCCESS_CLIENT,
        ),
    ],
)

# ========== response_data_path 测试用例 ==========

RESPONSE_DATA_PATH_INPUT_DATA = {
    "uniform_api_plugin_url": "http://example.com/api",
    "uniform_api_plugin_method": "POST",
    "response_data_path": "data.items",
}

RESPONSE_DATA_PATH_RESPONSE = MockAPIResponse(
    status_code=200, json_resp={"data": {"items": [{"id": 1}, {"id": 2}]}}, message="success", result=True
)

# 添加 extract_json_resp_with_jmespath 方法
RESPONSE_DATA_PATH_RESPONSE.extract_json_resp_with_jmespath = lambda path: [{"id": 1}, {"id": 2}]

RESPONSE_DATA_PATH_CLIENT = MagicMock()
RESPONSE_DATA_PATH_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
RESPONSE_DATA_PATH_CLIENT.gen_default_apigw_header = MagicMock(return_value={"X-Bkapi-Authorization": "mock_token"})
RESPONSE_DATA_PATH_CLIENT.request = MagicMock(return_value=RESPONSE_DATA_PATH_RESPONSE)

RESPONSE_DATA_PATH_CASE = ComponentTestCase(
    name="response_data_path_case",
    inputs={**RESPONSE_DATA_PATH_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": [{"id": 1}, {"id": 2}]},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=RESPONSE_DATA_PATH_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=RESPONSE_DATA_PATH_CLIENT,
        ),
    ],
)

# ========== 自定义 Headers 测试用例 ==========

CUSTOM_HEADERS_SPACE_CONFIG = {
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
                        "headers": {
                            "X-Custom-Header": "custom_value",
                            "X-Operator": "${_system.operator}",
                            "X-Task-Id": "${_system.task_id}",
                        },
                    }
                },
                "common": {"enable_standard_response": True},
            },
            "credential": {"bk_app_code": "mock_app_code", "bk_app_secret": "mock_app_secret"},
        }
    },
}

CUSTOM_HEADERS_CLIENT = MagicMock()
CUSTOM_HEADERS_CLIENT.get_space_infos = MagicMock(return_value=CUSTOM_HEADERS_SPACE_CONFIG)
CUSTOM_HEADERS_CLIENT.gen_default_apigw_header = MagicMock(return_value={"X-Bkapi-Authorization": "mock_token"})
CUSTOM_HEADERS_CLIENT.request = MagicMock(return_value=STANDARD_RESPONSE_SUCCESS_API_RESPONSE)

CUSTOM_HEADERS_CASE = ComponentTestCase(
    name="custom_headers_case",
    inputs={**API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"data": {"task_id": "12345"}}},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=CUSTOM_HEADERS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=CUSTOM_HEADERS_CLIENT,
        ),
    ],
)

# ========== 无凭证场景 ==========

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
                "common": {"enable_standard_response": True},
            },
            # 没有 credential
        }
    },
}

NO_CREDENTIAL_CLIENT = MagicMock()
NO_CREDENTIAL_CLIENT.get_space_infos = MagicMock(return_value=NO_CREDENTIAL_SPACE_CONFIG)
NO_CREDENTIAL_CLIENT.gen_default_apigw_header = MagicMock(return_value={"X-Bkapi-Authorization": "mock_token"})

NO_CREDENTIAL_CASE = ComponentTestCase(
    name="no_credential_case",
    inputs={**API_INPUT_DATA},
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
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=NO_CREDENTIAL_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=NO_CREDENTIAL_CLIENT,
        ),
    ],
)

# ========== 请求异常场景 ==========

REQUEST_EXCEPTION_CLIENT = MagicMock()
REQUEST_EXCEPTION_CLIENT.get_space_infos = MagicMock(return_value=STANDARD_RESPONSE_SPACE_CONFIG)
REQUEST_EXCEPTION_CLIENT.gen_default_apigw_header = MagicMock(return_value={"X-Bkapi-Authorization": "mock_token"})
REQUEST_EXCEPTION_CLIENT.request = MagicMock(side_effect=Exception("Connection timeout"))

REQUEST_EXCEPTION_CASE = ComponentTestCase(
    name="request_exception_case",
    inputs={**API_INPUT_DATA},
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
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=REQUEST_EXCEPTION_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=REQUEST_EXCEPTION_CLIENT,
        ),
    ],
)

# ========== exclude_none_fields 测试用例 ==========

EXCLUDE_NONE_FIELDS_SPACE_CONFIG = {
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
                "common": {"enable_standard_response": True, "exclude_none_fields": True},
            },
            "credential": {"bk_app_code": "mock_app_code", "bk_app_secret": "mock_app_secret"},
        }
    },
}

EXCLUDE_NONE_FIELDS_INPUT_DATA = {
    "uniform_api_plugin_url": "http://example.com/api",
    "uniform_api_plugin_method": "POST",
    "response_data_path": None,
    "empty_field": "",  # 空字符串应该被过滤
    "valid_field": "value",
}

EXCLUDE_NONE_FIELDS_CLIENT = MagicMock()
EXCLUDE_NONE_FIELDS_CLIENT.get_space_infos = MagicMock(return_value=EXCLUDE_NONE_FIELDS_SPACE_CONFIG)
EXCLUDE_NONE_FIELDS_CLIENT.gen_default_apigw_header = MagicMock(return_value={"X-Bkapi-Authorization": "mock_token"})
EXCLUDE_NONE_FIELDS_CLIENT.request = MagicMock(return_value=STANDARD_RESPONSE_SUCCESS_API_RESPONSE)

EXCLUDE_NONE_FIELDS_CASE = ComponentTestCase(
    name="exclude_none_fields_case",
    inputs={**EXCLUDE_NONE_FIELDS_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"status_code": 200, "data": {"data": {"task_id": "12345"}}},
        schedule_finished=True,
    ),
    patchers=[
        SETTINGS_PATCHER,
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.InterfaceModuleClient",
            return_value=EXCLUDE_NONE_FIELDS_CLIENT,
        ),
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.uniform_api.v3_0_0.UniformAPIClient",
            return_value=EXCLUDE_NONE_FIELDS_CLIENT,
        ),
    ],
)
