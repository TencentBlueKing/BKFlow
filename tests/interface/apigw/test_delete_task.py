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
from unittest.mock import patch

from django.test import TestCase, override_settings


class TestDeleteTask(TestCase):
    url = "/apigw/space/{space_id}/delete_task/"

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.views.delete_task.TaskComponentClient")
    def test_delete_task_success(self, mock_task_client):
        """测试正常删除任务成功"""
        mock_instance = mock_task_client.return_value
        mock_instance.batch_delete_tasks.return_value = {
            "result": True,
            "data": {"deleted_count": 2},
            "message": "删除成功",
        }
        data = {"task_ids": [1, 2, 3], "is_full": False}
        resp = self.client.post(
            path=self.url.format(space_id=1),
            data=json.dumps(data),
            content_type="application/json",
        )
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["data"]["deleted_count"], 2)

        mock_instance.batch_delete_tasks.assert_called_once_with(
            {"task_ids": [1, 2, 3], "is_full": False, "space_id": "1"}
        )

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.views.delete_task.TaskComponentClient")
    def test_delete_all_tasks_success(self, mock_task_client):
        """测试完整删除所有任务成功"""
        mock_instance = mock_task_client.return_value
        mock_instance.batch_delete_tasks.return_value = {
            "result": True,
            "data": {"deleted_count": 10},
            "message": "全部删除成功",
        }

        data = {"is_full": True, "is_mock": False}

        resp = self.client.post(
            path=self.url.format(space_id=1),
            data=json.dumps(data),
            content_type="application/json",
        )
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["data"]["deleted_count"], 10)

        mock_instance.batch_delete_tasks.assert_called_once_with(
            {"task_ids": [], "is_full": True, "is_mock": False, "space_id": "1"}
        )

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.views.delete_task.TaskComponentClient")
    def test_delete_all_tasks_mock_success(self, mock_task_client):
        """测试模拟删除所有任务成功"""
        mock_instance = mock_task_client.return_value
        mock_instance.batch_delete_tasks.return_value = {
            "result": True,
            "data": {"deleted_count": 0, "is_mock": True},
            "message": "模拟删除成功",
        }

        data = {"is_full": True, "is_mock": True}

        resp = self.client.post(
            path=self.url.format(space_id=1),
            data=json.dumps(data),
            content_type="application/json",
        )
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["data"]["deleted_count"], 0)
        self.assertEqual(resp_data["data"]["is_mock"], True)

        mock_instance.batch_delete_tasks.assert_called_once_with(
            {"task_ids": [], "is_full": True, "is_mock": True, "space_id": "1"}
        )
