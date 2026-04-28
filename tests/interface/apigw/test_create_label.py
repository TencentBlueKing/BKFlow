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

from bkflow.label.models import Label
from tests.interface.apigw.label_test_base import LabelApigwTestBase


class TestCreateLabel(LabelApigwTestBase):
    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_create_label_success(self):
        url = f"/apigw/space/{self.space.id}/create_label/"
        payload = {"name": "created", "color": "#123456", "label_scope": ["task"]}

        resp = self.client.post(path=url, data=json.dumps(payload), content_type="application/json")
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)
        self.assertEqual(data["data"]["name"], "created")
        self.assertEqual(data["data"]["creator"], "")
        self.assertEqual(data["data"]["updated_by"], "")
        self.assertTrue(Label.objects.filter(space_id=self.space.id, name="created").exists())

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_create_label_supports_parent_child_name(self):
        url = f"/apigw/space/{self.space.id}/create_label/"
        payload = {"name": "parent/child", "color": "#123456", "label_scope": ["task"]}

        resp = self.client.post(path=url, data=json.dumps(payload), content_type="application/json")
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)

        parent = Label.objects.get(space_id=self.space.id, name="parent", parent_id=None)
        child = Label.objects.get(space_id=self.space.id, name="child", parent_id=parent.id)
        self.assertEqual(data["data"]["id"], child.id)
