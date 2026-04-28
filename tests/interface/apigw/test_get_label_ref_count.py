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

from django.test import override_settings

from bkflow.label.models import TemplateLabelRelation
from tests.interface.apigw.label_test_base import LabelApigwTestBase


class TestGetLabelRefCount(LabelApigwTestBase):
    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.views.get_label_ref_count.TaskComponentClient")
    def test_get_label_ref_count_aggregates_root_children(self, mock_client):
        root = self.create_label("root", ["task", "template"])
        child_a = self.create_label("child_a", ["task", "template"], parent_id=root.id)
        child_b = self.create_label("child_b", ["task", "template"], parent_id=root.id)
        leaf = self.create_label("leaf", ["task", "template"])

        template = self.create_template()
        TemplateLabelRelation.objects.create(template_id=template.id, label_id=child_a.id)
        TemplateLabelRelation.objects.create(template_id=template.id, label_id=child_b.id)
        TemplateLabelRelation.objects.create(template_id=template.id, label_id=leaf.id)

        mock_client.return_value.get_task_label_ref_count.return_value = {
            "result": True,
            "data": {str(child_a.id): 2, str(child_b.id): 1, str(leaf.id): 1},
        }

        url = f"/apigw/space/{self.space.id}/get_label_ref_count/?label_ids={root.id},{leaf.id}"
        resp = self.client.get(path=url)
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)
        self.assertEqual(data["data"][str(root.id)]["template_count"], 2)
        self.assertEqual(data["data"][str(root.id)]["task_count"], 3)
        self.assertEqual(data["data"][str(leaf.id)]["template_count"], 1)
        self.assertEqual(data["data"][str(leaf.id)]["task_count"], 1)
