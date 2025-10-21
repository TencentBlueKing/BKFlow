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

from bkflow.pipeline_plugins.components.collections.notify.v1_0 import NotifyComponent


class BkNotifyComponentTest(TestCase, ComponentTestMixin):
    def component_cls(self):
        return NotifyComponent

    def cases(self):
        return [
            SEND_MSG_FAIL_CASE,
            SEND_MSG_SUCCESS_CASE,
            SEND_VOICE_MSG_SUCCESS_CASE,
            SEND_MSG_SUCCESS_RECEIVER_ORDER_CASE,
        ]


class MockClient:
    def __init__(self, cc_search_business_return=None, cmsi_send_msg_return=None):
        self.cmsi = MagicMock()
        self.cmsi.send_msg = MagicMock(return_value=cmsi_send_msg_return)
        self.cmsi.send_voice_msg = MagicMock(return_value=cmsi_send_msg_return)


class MockStaffGroupSet:
    def __init__(self, expected_values_list):
        self.values_list = MagicMock(return_value=expected_values_list)
        self.filter = MagicMock(return_value=self.values_list)
        self.objects = MagicMock()
        self.objects.filter = self.filter


GET_CLIENT_BY_USER = "bkflow.utils.message.get_client_by_user"
HANDLE_API_ERROR = "bkflow.utils.message.handle_api_error"

COMMON_PARENT = {"executor": "tester", "biz_supplier_account": 0}

CMSI_SEND_MSG_FAIL_RETURN = {"result": False, "message": "send msg fail"}

CMSI_SEND_MSG_SUCCESS_RETURN = {"result": True, "message": "success"}


SEND_MSG_FAIL_CASE = ComponentTestCase(
    name="send msg fail case",
    inputs={
        "bk_notify_types": ["mail", "weixin", "voice"],
        "bk_notify_receivers": "a,b",
        "notify_executor": True,
        "bk_notify_title": "title",
        "bk_notify_content": "content",
    },
    parent_data=COMMON_PARENT,
    execute_assertion=ExecuteAssertion(
        success=False,
        outputs={"ex_data": "send msg fail;send msg fail;send msg fail;"},
    ),
    execute_call_assertion=[],
    schedule_assertion=None,
    patchers=[
        Patcher(
            target=GET_CLIENT_BY_USER,
            return_value=MockClient(
                cmsi_send_msg_return=CMSI_SEND_MSG_FAIL_RETURN,
            ),
        ),
        Patcher(target=HANDLE_API_ERROR, return_value="send msg fail"),
    ],
)

SEND_MSG_SUCCESS_CLIENT = MockClient(cmsi_send_msg_return=CMSI_SEND_MSG_SUCCESS_RETURN)

SEND_MSG_SUCCESS_CASE = ComponentTestCase(
    name="send msg success case",
    inputs={
        "bk_notify_types": ["mail", "weixin"],
        "bk_notify_receivers": "a,b",
        "notify_executor": True,
        "bk_notify_title": "title",
        "bk_notify_content": "content",
    },
    parent_data=COMMON_PARENT,
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    execute_call_assertion=[
        CallAssertion(
            func=SEND_MSG_SUCCESS_CLIENT.cmsi.send_msg,
            calls=[
                Call(
                    {
                        "receiver__username": "tester,a,b",
                        "title": "title",
                        "content": "<pre>content</pre>",
                        "msg_type": "mail",
                    }
                ),
                Call(
                    {
                        "receiver__username": "tester,a,b",
                        "title": "title",
                        "content": "content",
                        "msg_type": "weixin",
                    }
                ),
            ],
        )
    ],
    schedule_assertion=None,
    patchers=[Patcher(target=GET_CLIENT_BY_USER, return_value=SEND_MSG_SUCCESS_CLIENT)],
)

SEND_VOICE_MSG_SUCCESS_CASE = ComponentTestCase(
    name="send voice msg success case",
    inputs={
        "bk_notify_types": ["voice"],
        "bk_notify_receivers": "a,b",
        "notify_executor": True,
        "bk_notify_title": "title",
        "bk_notify_content": "content",
    },
    parent_data=COMMON_PARENT,
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    execute_call_assertion=[
        CallAssertion(
            func=SEND_MSG_SUCCESS_CLIENT.cmsi.send_voice_msg,
            calls=[
                Call(
                    {
                        "receiver__username": "tester,a,b",
                        "auto_read_message": "title,content",
                    }
                )
            ],
        )
    ],
    schedule_assertion=None,
    patchers=[Patcher(target=GET_CLIENT_BY_USER, return_value=SEND_MSG_SUCCESS_CLIENT)],
)


SEND_MSG_SUCCESS_RECEIVER_ORDER_CASE = ComponentTestCase(
    name="send msg success receiver order case",
    inputs={
        "bk_notify_types": ["mail", "weixin", "voice"],
        "bk_notify_receivers": "c,a,b",
        "notify_executor": True,
        "bk_notify_title": "title",
        "bk_notify_content": "content",
    },
    parent_data=COMMON_PARENT,
    execute_assertion=ExecuteAssertion(success=True, outputs={}),
    execute_call_assertion=[
        CallAssertion(
            func=SEND_MSG_SUCCESS_CLIENT.cmsi.send_msg,
            calls=[
                Call(
                    {
                        "receiver__username": "tester,c,a,b",
                        "title": "title",
                        "content": "<pre>content</pre>",
                        "msg_type": "mail",
                    }
                ),
                Call(
                    {"receiver__username": "tester,c,a,b", "title": "title", "content": "content", "msg_type": "weixin"}
                ),
            ],
        )
    ],
    schedule_assertion=None,
    patchers=[Patcher(target=GET_CLIENT_BY_USER, return_value=SEND_MSG_SUCCESS_CLIENT)],
)
