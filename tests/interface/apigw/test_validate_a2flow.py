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
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from bkflow.apigw.views.validate_a2flow import validate_a2flow


class TestValidateA2FlowView(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.apigw.views.validate_a2flow.A2FlowV2Converter")
    def test_validate_success(self, mock_converter_cls):
        """测试合法流程校验通过"""
        mock_converter = MagicMock()
        mock_converter.convert.return_value = {
            "activities": {
                "n1": {"component": {"code": "job_fast_execute_script"}},
            },
            "start_event": {},
            "end_event": {},
        }
        mock_converter_cls.return_value = mock_converter

        body = json.dumps(
            {
                "a2flow": {
                    "version": "2.0",
                    "name": "测试流程",
                    "nodes": [
                        {
                            "id": "n1",
                            "name": "执行脚本",
                            "code": "job_fast_execute_script",
                            "data": {"script_content": "echo hello"},
                            "next": "end",
                        },
                    ],
                }
            }
        )
        request = self.factory.post("/space/1/validate_a2flow/", data=body, content_type="application/json")
        request.user = MagicMock(username="admin")
        response = validate_a2flow(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["valid"] is True
        assert data["data"]["node_count"] == 1
        assert "job_fast_execute_script" in data["data"]["plugin_codes"]

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    def test_validate_missing_a2flow(self):
        """测试缺少 a2flow 字段"""
        body = json.dumps({})
        request = self.factory.post("/space/1/validate_a2flow/", data=body, content_type="application/json")
        request.user = MagicMock(username="admin")
        response = validate_a2flow(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is False
