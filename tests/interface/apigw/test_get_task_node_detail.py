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
from unittest import mock

from django.test import TestCase, override_settings


class TestGetTaskNodeDetail(TestCase):
    """Test get_task_node_detail apigw view"""

    def _url(self, space_id=1, task_id=123, node_id="node_1"):
        return "/apigw/space/{}/task/{}/node/{}/get_task_node_detail/".format(space_id, task_id, node_id)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_node_detail.TaskComponentClient")
    def test_default_does_not_include_snapshot_config(self, mock_client_class):
        """
        When include_snapshot_config is not passed, response has no snapshot_config
        and get_node_snapshot_config is not called
        """
        mock_client = mock.Mock()
        mock_client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"name": "节点1", "state": "READY"},
            "message": "success",
        }
        mock_client_class.return_value = mock_client

        resp = self.client.get(self._url())
        resp_data = resp.json()

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp_data["result"])
        self.assertNotIn("snapshot_config", resp_data["data"])
        mock_client.get_task_node_detail.assert_called_once()
        mock_client.get_node_snapshot_config.assert_not_called()

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_node_detail.TaskComponentClient")
    def test_include_snapshot_config_false_does_not_fetch_snapshot(self, mock_client_class):
        """When include_snapshot_config=false, get_node_snapshot_config is not called"""
        mock_client = mock.Mock()
        mock_client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"name": "节点1"},
            "message": "success",
        }
        mock_client_class.return_value = mock_client

        resp = self.client.get(self._url() + "?include_snapshot_config=false")
        resp_data = resp.json()

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("snapshot_config", resp_data["data"])
        mock_client.get_node_snapshot_config.assert_not_called()

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_node_detail.TaskComponentClient")
    def test_include_snapshot_config_true_returns_snapshot_in_data(self, mock_client_class):
        """When include_snapshot_config=true, response includes snapshot_config from get_node_snapshot_config"""
        mock_client = mock.Mock()
        mock_client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"name": "节点1", "state": "READY"},
            "message": "success",
        }
        mock_client.get_node_snapshot_config.return_value = {
            "result": True,
            "data": {"component": {"code": "example_component", "inputs": {}}},
            "message": "success",
        }
        mock_client_class.return_value = mock_client

        resp = self.client.get(self._url() + "?include_snapshot_config=true")
        resp_data = resp.json()

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp_data["result"])
        self.assertIn("snapshot_config", resp_data["data"])
        self.assertEqual(
            resp_data["data"]["snapshot_config"],
            {"component": {"code": "example_component", "inputs": {}}},
        )
        mock_client.get_node_snapshot_config.assert_called_once_with("123", data={"node_id": "node_1"})

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_node_detail.TaskComponentClient")
    def test_include_snapshot_config_not_called_when_node_detail_fails(self, mock_client_class):
        """When get_task_node_detail fails, get_node_snapshot_config is not called"""
        mock_client = mock.Mock()
        mock_client.get_task_node_detail.return_value = {
            "result": False,
            "data": None,
            "message": "node not found",
        }
        mock_client_class.return_value = mock_client

        resp = self.client.get(self._url() + "?include_snapshot_config=true")
        resp_data = resp.json()

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp_data["result"])
        mock_client.get_node_snapshot_config.assert_not_called()

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_node_detail.TaskComponentClient")
    def test_include_snapshot_config_none_when_snapshot_fetch_fails(self, mock_client_class):
        """When get_node_snapshot_config fails, snapshot_config is None in response"""
        mock_client = mock.Mock()
        mock_client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"name": "节点1"},
            "message": "success",
        }
        mock_client.get_node_snapshot_config.return_value = {
            "result": False,
            "data": None,
            "message": "template_node_id 未找到",
        }
        mock_client_class.return_value = mock_client

        resp = self.client.get(self._url() + "?include_snapshot_config=true")
        resp_data = resp.json()

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp_data["result"])
        self.assertIn("snapshot_config", resp_data["data"])
        self.assertIsNone(resp_data["data"]["snapshot_config"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_node_detail.TaskComponentClient")
    def test_include_snapshot_config_not_passed_to_engine(self, mock_client_class):
        """include_snapshot_config is apigw-only; data passed to get_task_node_detail must not contain it"""
        mock_client = mock.Mock()
        mock_client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"name": "节点1"},
            "message": "success",
        }
        mock_client_class.return_value = mock_client

        self.client.get(self._url() + "?include_snapshot_config=true&loop=1")

        call_kwargs = mock_client.get_task_node_detail.call_args[1]
        data = call_kwargs["data"]
        self.assertNotIn("include_snapshot_config", data)
        self.assertEqual(data.get("loop"), 1)
