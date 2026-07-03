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
from unittest import mock

from django.test import TestCase, override_settings

from bkflow.space.models import Space


class TestOperateTaskNode(TestCase):
    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")
        self.task_id = 1
        self.node_id = "node_001"
        self.client_request_id = "task-1-node-node_001-attempt-1"
        self.open_plugin_run_id = "run-001"
        self.node_version = "v4.0.0"

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.operate_task_node.TaskComponentClient")
    def test_callback_forwards_open_plugin_payload_to_engine(self, mock_client_class):
        token = "callback-token"
        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": True, "data": None, "message": "success"}
        mock_client_class.return_value = mock_client

        body = {
            "open_plugin_run_id": self.open_plugin_run_id,
            "status": "SUCCEEDED",
            "outputs": {"job_instance_id": 1001},
        }
        url = "/apigw/space/{}/task/{}/node/{}/operate_node/callback/".format(self.space.id, self.task_id, self.node_id)
        resp = self.client.post(
            path=url,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN=token,
        )

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        mock_client.node_operate.assert_called_once_with(
            self.task_id,
            self.node_id,
            "callback",
            {
                "operator": "system",
                "data": {
                    "open_plugin_run_id": self.open_plugin_run_id,
                    "status": "SUCCEEDED",
                    "outputs": {"job_instance_id": 1001},
                    "_callback_token": token,
                },
            },
        )

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.operate_task_node.TaskComponentClient")
    def test_callback_forwards_missing_open_plugin_token_to_engine(self, mock_client_class):
        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": False, "data": None, "message": "missing callback token"}
        mock_client_class.return_value = mock_client

        body = {
            "open_plugin_run_id": self.open_plugin_run_id,
            "status": "SUCCEEDED",
            "outputs": {"job_instance_id": 1001},
        }
        url = "/apigw/space/{}/task/{}/node/{}/operate_node/callback/".format(self.space.id, self.task_id, self.node_id)
        resp = self.client.post(
            path=url,
            data=json.dumps(body),
            content_type="application/json",
        )

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        mock_client.node_operate.assert_called_once_with(
            self.task_id,
            self.node_id,
            "callback",
            {
                "operator": "system",
                "data": {
                    "open_plugin_run_id": self.open_plugin_run_id,
                    "status": "SUCCEEDED",
                    "outputs": {"job_instance_id": 1001},
                    "_callback_token": "",
                },
            },
        )
