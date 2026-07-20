"""
TencentBlueKing is pleased to support the open source community by making
BlueKing Flow Engine Service available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License. See http://opensource.org/licenses/MIT.
"""

import json
from unittest import mock

from django.test import TestCase


class TestOpenPluginCallback(TestCase):
    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_forwards_token_authenticated_payload_to_engine(self, mock_client_class):
        """A valid callback is forwarded with its token intact."""

        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": True, "data": None, "message": "success"}
        mock_client_class.return_value = mock_client
        payload = {
            "open_plugin_run_id": "run-001",
            "status": "SUCCEEDED",
            "outputs": {"job_instance_id": 1001},
        }

        response = self.client.post(
            "/open_plugin_callback/space/10/task/123/node/node_a/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN="callback-token",
        )

        self.assertEqual(response.status_code, 200)
        mock_client_class.assert_called_once_with(space_id="10")
        mock_client.node_operate.assert_called_once_with(
            task_id=123,
            node_id="node_a",
            operation="callback",
            data={
                "operator": "system",
                "data": {**payload, "_callback_token": "callback-token"},
            },
        )

    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_rejects_invalid_payload_before_forwarding(self, mock_client_class):
        """Malformed callback data is rejected before crossing module boundaries."""

        response = self.client.post(
            "/open_plugin_callback/space/10/task/123/node/node_a/",
            data=json.dumps({"status": "SUCCEEDED"}),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN="callback-token",
        )

        self.assertEqual(response.status_code, 400)
        mock_client_class.assert_not_called()

    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_rejects_missing_token_before_forwarding(self, mock_client_class):
        """A callback without the shared run token is rejected immediately."""

        response = self.client.post(
            "/open_plugin_callback/space/10/task/123/node/node_a/",
            data=json.dumps({"open_plugin_run_id": "run-001", "status": "SUCCEEDED"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        mock_client_class.assert_not_called()

    @mock.patch("bkflow.interface.views.TaskComponentClient")
    def test_callback_propagates_engine_rejection_as_bad_request(self, mock_client_class):
        """The provider must not mark a callback delivered when the engine rejects it."""

        mock_client = mock.Mock()
        mock_client.node_operate.return_value = {"result": False, "data": None, "message": "invalid callback token"}
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/open_plugin_callback/space/10/task/123/node/node_a/",
            data=json.dumps({"open_plugin_run_id": "run-001", "status": "SUCCEEDED"}),
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN="callback-token",
        )

        self.assertEqual(response.status_code, 400)
