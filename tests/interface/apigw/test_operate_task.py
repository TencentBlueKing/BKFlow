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
from inspect import unwrap
from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase, override_settings

from bkflow.apigw.views.operate_task_by_app import operate_task_by_app
from bkflow.space.models import Space


class TestOperateTask(TestCase):
    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.operate_task.TaskComponentClient")
    def test_start_task_does_not_prefetch_task_detail(self, mock_client_class):
        """普通启动入口不再无条件拉取完整任务详情。"""
        mock_client = mock.Mock()
        mock_client.operate_task.return_value = {"result": True, "data": {"id": 1}}
        mock_client_class.return_value = mock_client

        data = {"operator": "test_user"}
        url = "/apigw/space/{}/task/1/operate_task/start/".format(self.space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(resp.status_code, 200)
        mock_client.get_task_detail.assert_not_called()
        mock_client.operate_task.assert_called_once()

    @mock.patch("bkflow.apigw.views.operate_task_by_app.TaskComponentClient")
    def test_start_task_by_app_does_not_prefetch_task_detail(self, mock_client_class):
        """按应用启动入口把开放插件预检交给已持有任务数据的 Engine 路径。"""
        mock_client = mock_client_class.return_value
        mock_client.operate_task.return_value = {"result": True, "data": {"id": 1}}
        request = RequestFactory().post("/apigw/task/1/operate_task_by_app/start/", data={})
        request.space_id = self.space.id
        request.user = SimpleNamespace(username="test_user")

        result = unwrap(operate_task_by_app)(request, task_id=1, operation="start")

        self.assertEqual(result["result"], True)
        mock_client.get_task_detail.assert_not_called()
        mock_client.operate_task.assert_called_once()
