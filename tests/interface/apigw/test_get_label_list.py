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


class TestGetLabelList(LabelApigwTestBase):
    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_label_list_returns_roots_and_has_children(self):
        root = self.create_label("root", ["task"])
        self.create_label("child", ["task"], parent_id=root.id)
        self.create_label("other", ["task"])

        url = f"/apigw/space/{self.space.id}/get_label_list/?label_scope=task&order_by=name"
        resp = self.client.get(path=url)
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)
        self.assertEqual(data["count"], 2)
        self.assertEqual([item["name"] for item in data["data"]], ["other", "root"])
        root_item = next(item for item in data["data"] if item["id"] == root.id)
        self.assertTrue(root_item["has_children"])
