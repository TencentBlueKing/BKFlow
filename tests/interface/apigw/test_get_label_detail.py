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

from django.test import override_settings

from tests.interface.apigw.label_test_base import LabelApigwTestBase


class TestGetLabelDetail(LabelApigwTestBase):
    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_label_detail_success_and_not_found(self):
        label = self.create_label("detail", ["task"])
        self.create_label("detail_child", ["task"], parent_id=label.id)

        ok_url = f"/apigw/space/{self.space.id}/label/{label.id}/get_label_detail/"
        ok_resp = self.client.get(path=ok_url)
        ok_data = json.loads(ok_resp.content)

        self.assertEqual(ok_resp.status_code, 200)
        self.assertEqual(ok_data["result"], True)
        self.assertEqual(ok_data["data"]["id"], label.id)
        self.assertTrue(ok_data["data"]["has_children"])

        miss_url = f"/apigw/space/{self.space.id}/label/999999/get_label_detail/"
        miss_resp = self.client.get(path=miss_url)
        miss_data = json.loads(miss_resp.content)

        self.assertEqual(miss_resp.status_code, 200)
        self.assertEqual(miss_data["result"], False)
        self.assertIn("标签不存在", miss_data["message"])
