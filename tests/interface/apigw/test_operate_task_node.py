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
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from bkflow.plugin.models import OpenPluginRunCallbackRef
from bkflow.plugin.services.open_plugin_callback import (
    callback_token_digest,
    issue_open_plugin_callback_token,
)
from bkflow.space.models import Space


class TestOperateTaskNode(TestCase):
    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")
        self.task_id = 1
        self.node_id = "node_001"
        self.client_request_id = "task-1-node-node_001-attempt-1"
        self.open_plugin_run_id = "run-001"
        self.node_version = "v4.0.0"

    def _create_callback_ref(self, token, consumed_at=None):
        return OpenPluginRunCallbackRef.objects.create(
            task_id=self.task_id,
            node_id=self.node_id,
            node_version=self.node_version,
            client_request_id=self.client_request_id,
            open_plugin_run_id=self.open_plugin_run_id,
            callback_token_digest=callback_token_digest(token),
            callback_expire_at=timezone.now() + timedelta(hours=1),
            plugin_source="builtin",
            plugin_id="open_plugin_001",
            plugin_version="1.2.0",
            consumed_at=consumed_at,
        )

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.operate_task_node.TaskComponentClient")
    def test_callback_rejects_invalid_open_plugin_token(self, mock_client_class):
        valid_token, _ = issue_open_plugin_callback_token(
            task_id=self.task_id,
            node_id=self.node_id,
            client_request_id=self.client_request_id,
            node_version=self.node_version,
        )
        self._create_callback_ref(valid_token)

        body = {
            "open_plugin_run_id": self.open_plugin_run_id,
            "status": "SUCCEEDED",
            "outputs": {"job_instance_id": 1001},
        }
        url = "/apigw/space/{}/task/{}/node/{}/operate_node/callback/".format(
            self.space.id, self.task_id, self.node_id
        )
        resp = self.client.post(
            path=url,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN="invalid-token",
        )

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["code"], 400)
        self.assertIn("callback token", resp_data["message"])
        mock_client_class.return_value.node_operate.assert_not_called()

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.operate_task_node.BambooDjangoRuntime")
    @mock.patch("bkflow.apigw.views.operate_task_node.TaskComponentClient")
    def test_callback_accepts_valid_open_plugin_payload(self, mock_client_class, mock_runtime_cls):
        token, _ = issue_open_plugin_callback_token(
            task_id=self.task_id,
            node_id=self.node_id,
            client_request_id=self.client_request_id,
            node_version=self.node_version,
        )
        ref = self._create_callback_ref(token)

        state = mock.Mock()
        state.name = "RUNNING"
        state.version = self.node_version
        mock_runtime_cls.return_value.get_state.return_value = state

        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": True, "data": None, "message": "success"}
        mock_client_class.return_value = mock_client

        body = {
            "open_plugin_run_id": self.open_plugin_run_id,
            "status": "SUCCEEDED",
            "outputs": {"job_instance_id": 1001},
        }
        url = "/apigw/space/{}/task/{}/node/{}/operate_node/callback/".format(
            self.space.id, self.task_id, self.node_id
        )
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
                "version": self.node_version,
                "data": {
                    "open_plugin_run_id": self.open_plugin_run_id,
                    "status": "SUCCEEDED",
                    "outputs": {"job_instance_id": 1001},
                },
            },
        )
        ref.refresh_from_db()
        self.assertIsNotNone(ref.consumed_at)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.operate_task_node.TaskComponentClient")
    def test_callback_duplicate_request_is_idempotent(self, mock_client_class):
        token, _ = issue_open_plugin_callback_token(
            task_id=self.task_id,
            node_id=self.node_id,
            client_request_id=self.client_request_id,
            node_version=self.node_version,
        )
        self._create_callback_ref(token, consumed_at=timezone.now())

        body = {
            "open_plugin_run_id": self.open_plugin_run_id,
            "status": "SUCCEEDED",
            "outputs": {"job_instance_id": 1001},
        }
        url = "/apigw/space/{}/task/{}/node/{}/operate_node/callback/".format(
            self.space.id, self.task_id, self.node_id
        )
        resp = self.client.post(
            path=url,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN=token,
        )

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertIn("already consumed", resp_data["message"])
        mock_client_class.return_value.node_operate.assert_not_called()

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.operate_task_node.BambooDjangoRuntime")
    @mock.patch("bkflow.apigw.views.operate_task_node.TaskComponentClient")
    def test_callback_terminal_node_is_swallowed(self, mock_client_class, mock_runtime_cls):
        token, _ = issue_open_plugin_callback_token(
            task_id=self.task_id,
            node_id=self.node_id,
            client_request_id=self.client_request_id,
            node_version=self.node_version,
        )
        self._create_callback_ref(token)

        state = mock.Mock()
        state.name = "FINISHED"
        state.version = self.node_version
        mock_runtime_cls.return_value.get_state.return_value = state

        body = {
            "open_plugin_run_id": self.open_plugin_run_id,
            "status": "SUCCEEDED",
            "outputs": {"job_instance_id": 1001},
        }
        url = "/apigw/space/{}/task/{}/node/{}/operate_node/callback/".format(
            self.space.id, self.task_id, self.node_id
        )
        resp = self.client.post(
            path=url,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN=token,
        )

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertIn("already in terminal state", resp_data["message"])
        mock_client_class.return_value.node_operate.assert_not_called()
