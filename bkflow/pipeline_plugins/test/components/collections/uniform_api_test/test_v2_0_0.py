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


class UniformAPIComponentTest(TestCase, ComponentTestMixin):
    def component_cls(self):
        return UniformAPIComponent

    def cases(self):
        return [API_TRIGGER_SUCCESS_CASE, API_CALLBACK_SUCCESS_CASE]


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

API_CALLBACK_INPUT_DATA = {**API_INPUT_DATA, "need_callback": True}

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


SUCCESS_SPACE_CONFIG = {
    "result": True,
    "message": "success",
    "data": {
        "configs": {
            "uniform_api": {
                "api": {
                    "default": {
                        "meta_apis": "https://example.com/meta_apis",
                        "api_categories": "https://example.com/api_categories",
                        "display_name": "Default API",
                    }
                },
                "enable_api_parameter_conversion": True,
            },
            "credential": {"bk_app_code": "mock_app_code", "bk_app_secret": "mock_app_secret"},
        }
    },
}
SUCCESS_API_HEADER = {
    "X-Bkapi-Authorization": "mock_token",
    "X-Bkapi-App-Code": "mock_app_code",
    "X-Bkapi-App-Secret": "mock_app_secret",
    "X-Bkapi-User": "mock_operator",
}
SUCCESS_API_RESPONSE_DATA = MockAPIResponse(
    status_code=200, json_resp={"result": "success", "data": {"space_id": 1}}, message="success", result=True
)


class MockUniformAPIClient:
    def __init__(self, get_space_infos=None, gen_default_apigw_header=None, request=None):
        self.get_space_infos = MagicMock(return_value=get_space_infos)
        self.gen_default_apigw_header = MagicMock(return_value=gen_default_apigw_header)
        self.request = MagicMock(return_value=request)


SUCCESS_API_CLIENT = MockUniformAPIClient(
    get_space_infos=SUCCESS_SPACE_CONFIG, gen_default_apigw_header=SUCCESS_API_HEADER, request=SUCCESS_API_RESPONSE_DATA
)


API_TRIGGER_SUCCESS_CASE = ComponentTestCase(
    name="api_trigger_success_case",
    inputs={**API_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(outputs={"need_callback": True, "status_code": 200}, success=True),
    schedule_assertion=ScheduleAssertion(
        outputs={"need_callback": True, "status_code": 200}, success=True, callback_data={"result": "success"}
    ),
    patchers=[
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

API_CALLBACK_SUCCESS_CASE = ComponentTestCase(
    name="api_callback_success_case",
    inputs={**API_CALLBACK_INPUT_DATA},
    parent_data={**TEST_PARENT_DATA},
    execute_assertion=ExecuteAssertion(
        success=True,
        outputs={"need_callback": True, "status_code": 200},
    ),
    schedule_assertion=ScheduleAssertion(
        success=True,
        callback_data={"result": "success"},
        outputs={"need_callback": True, "status_code": 200},
    ),
    patchers=[
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
