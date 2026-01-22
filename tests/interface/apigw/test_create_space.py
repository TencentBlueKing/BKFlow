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

from django.test import TestCase, override_settings


class TestCreateSpace(TestCase):
    url = "/apigw/create_space/"

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    def test_create_space_serializer_failed(self):
        data = {"name": "test_space", "platform_url": "xxxx", "app_code": "test", "desc": "test"}
        resp = self.client.post(path=self.url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)
        self.assertEqual(resp_data["result"], False)
        err_message = json.loads(resp_data["message"])
        self.assertEqual(err_message["platform_url"], "请输入合法的URL。")

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    def test_create_space_success(self):
        data = {"name": "test_space", "platform_url": "http://abc.com", "app_code": "test", "desc": "test"}

        resp = self.client.post(path=self.url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertIsInstance(resp_data["data"]["space"]["id"], int)
        self.assertGreater(resp_data["data"]["space"]["id"], 0)
        self.assertEqual(resp_data["data"]["space"]["name"], "test_space")
