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


class TestGetTaskList(TestCase):
    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_list.TaskComponentClient")
    def test_get_task_list_with_task_id_list(self, mock_client_class):
        """task_id_list 以逗号分隔字符串入参，应被映射为 id__in 透传给下游"""
        space = self.create_space()
        mock_client = mock_client_class.return_value
        mock_client.task_list.return_value = {
            "result": True,
            "data": {"count": 0, "next": None, "previous": None, "results": []},
        }

        url = f"/apigw/space/{space.id}/get_task_list/?task_id_list=1,3"
        resp = self.client.get(url)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)

        mock_client_class.assert_called_once_with(space_id=str(space.id))
        mock_client.task_list.assert_called_once()
        called_data = mock_client.task_list.call_args.kwargs["data"]
        self.assertEqual(called_data["id__in"], "1,3")
        self.assertNotIn("task_id_list", called_data)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_list.TaskComponentClient")
    def test_get_task_list_with_empty_task_id_list_should_fail(self, mock_client_class):
        """传入了 task_id_list 但值为空，应当校验失败，下游不应被调用"""
        space = self.create_space()

        url = f"/apigw/space/{space.id}/get_task_list/?task_id_list="
        resp = self.client.get(url)
        resp_data = json.loads(resp.content)

        self.assertFalse(resp_data["result"])
        self.assertIn("task_id_list", str(resp_data.get("message", "")))
        mock_client_class.assert_not_called()
