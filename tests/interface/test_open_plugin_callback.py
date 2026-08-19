"""
TencentBlueKing is pleased to support the open source community by making
BlueKing Flow Engine Service available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License. See http://opensource.org/licenses/MIT.
"""

import json
from unittest import mock

from cryptography.fernet import Fernet
from django.conf import settings
from django.test import TestCase, override_settings


@override_settings(CALLBACK_KEY=Fernet.generate_key())
class TestOpenPluginCallback(TestCase):
    @staticmethod
    def _callback_path(node_version="v4.0.0"):
        token = Fernet(settings.CALLBACK_KEY).encrypt(f"10:123:node_a:{node_version}".encode()).decode("utf-8")
        return f"/callback/{token}/"

    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_forwards_token_authenticated_payload_to_engine(self, mock_client_class):
        """方案 B 存量入口把开放插件运行 token 透传给 engine。"""

        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": True, "data": None, "message": "success"}
        mock_client_class.return_value = mock_client
        payload = {
            "open_plugin_run_id": "run-001",
            "status": "SUCCEEDED",
            "outputs": {"job_instance_id": 1001},
        }

        response = self.client.post(
            self._callback_path(),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN="callback-token",
        )

        self.assertEqual(response.status_code, 200)
        mock_client_class.assert_called_once_with(space_id="10")
        mock_client.node_operate.assert_called_once_with(
            task_id="123",
            node_id="node_a",
            operation="callback",
            data={
                "version": "v4.0.0",
                "data": {**payload, "_callback_token": "callback-token"},
            },
        )

    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_rejects_invalid_payload_before_forwarding(self, mock_client_class):
        """携带开放插件 token 的非法 payload 不进入 task 模块。"""

        response = self.client.post(
            self._callback_path(),
            data=json.dumps({"status": "SUCCEEDED"}),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN="callback-token",
        )

        self.assertEqual(response.status_code, 400)
        mock_client_class.assert_not_called()

    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_keeps_legacy_payload_when_business_field_collides(self, mock_client_class):
        """普通回调即使携带 open_plugin_run_id 业务字段，没有专用 token 仍走原协议。"""

        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": True, "data": None, "message": "success"}
        mock_client_class.return_value = mock_client
        payload = {"open_plugin_run_id": "biz-001", "status": "success", "data": {"result": "done"}}

        response = self.client.post(
            self._callback_path(node_version="v3.0.0"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mock_client.node_operate.assert_called_once_with(
            task_id="123",
            node_id="node_a",
            operation="callback",
            data={"version": "v3.0.0", "data": payload},
        )

    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_propagates_engine_rejection_as_bad_request(self, mock_client_class):
        """engine 拒绝开放插件回调时返回非 2xx，供提供方重试。"""

        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": False, "data": None, "message": "invalid callback token"}
        mock_client_class.return_value = mock_client

        response = self.client.post(
            self._callback_path(),
            data=json.dumps({"open_plugin_run_id": "run-001", "status": "SUCCEEDED"}),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN="callback-token",
        )

        self.assertEqual(response.status_code, 400)

    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_keeps_legacy_payload_behavior(self, mock_client_class):
        """普通存量回调不要求开放插件 token，转发结构保持不变。"""

        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": True, "data": None, "message": "success"}
        mock_client_class.return_value = mock_client
        payload = {"status": "success", "data": {"result": "done"}}

        response = self.client.post(
            self._callback_path(node_version="v3.0.0"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mock_client.node_operate.assert_called_once_with(
            task_id="123",
            node_id="node_a",
            operation="callback",
            data={"version": "v3.0.0", "data": payload},
        )
