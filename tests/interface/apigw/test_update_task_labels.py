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

from tests.interface.apigw.label_test_base import LabelApigwTestBase


class TestUpdateTaskLabels(LabelApigwTestBase):
    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.views.operate_task.TaskComponentClient")
    def test_update_task_labels_success(self, mock_client):
        label = self.create_label("task_child", ["task"])
        mock_client.return_value.update_labels.return_value = {
            "result": True,
            "data": {"label_ids": [label.id]},
            "code": 0,
        }

        url = f"/apigw/space/{self.space.id}/task/200/update_labels/"
        resp = self.client.post(
            path=url,
            data=json.dumps({"label_ids": [label.id]}),
            content_type="application/json",
        )
        data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["result"], True)
        mock_client.return_value.update_labels.assert_called_once_with(
            "200", data={"label_ids": [label.id], "space_id": str(self.space.id)}
        )
