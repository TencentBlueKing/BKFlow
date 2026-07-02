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

from bkflow.label.models import Label, TemplateLabelRelation
from tests.interface.apigw.label_test_base import LabelApigwTestBase


class TestDeleteLabel(LabelApigwTestBase):
    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.views.delete_label.TaskComponentClient")
    def test_delete_label_deletes_root_and_children(self, mock_client):
        root = self.create_label("root", ["task"])
        child = self.create_label("child", ["task"], parent_id=root.id)
        TemplateLabelRelation.objects.create(template_id=1, label_id=child.id)
        mock_client.return_value.delete_task_label_relation.return_value = {"result": True, "data": None}

        url = f"/apigw/space/{self.space.id}/delete_label/{root.id}/"
        resp = self.client.post(path=url)
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)
        self.assertFalse(Label.objects.filter(id__in=[root.id, child.id]).exists())
        self.assertFalse(TemplateLabelRelation.objects.filter(label_id=child.id).exists())
        mock_client.return_value.delete_task_label_relation.assert_called_once_with({"label_ids": [root.id, child.id]})
