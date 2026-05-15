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


class TestUpdateLabel(LabelApigwTestBase):
    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_update_label_success_and_not_found(self):
        label = self.create_label("before", ["task"], color="#111111")

        ok_url = f"/apigw/space/{self.space.id}/update_label/{label.id}/"
        ok_resp = self.client.patch(
            path=ok_url,
            data=json.dumps({"name": "after", "color": "#222222"}),
            content_type="application/json",
        )
        ok_data = json.loads(ok_resp.content)

        label.refresh_from_db()
        self.assertEqual(ok_resp.status_code, 200)
        self.assertEqual(ok_data["result"], True)
        self.assertEqual(label.name, "after")
        self.assertEqual(label.color, "#222222")
        self.assertEqual(label.updated_by, "tester")

        miss_url = f"/apigw/space/{self.space.id}/update_label/999999/"
        miss_resp = self.client.patch(
            path=miss_url,
            data=json.dumps({"name": "nope"}),
            content_type="application/json",
        )
        miss_data = json.loads(miss_resp.content)

        self.assertEqual(miss_resp.status_code, 200)
        self.assertEqual(miss_data["result"], False)
        self.assertIn("标签不存在", miss_data["message"])
