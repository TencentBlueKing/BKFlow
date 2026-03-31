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

from bkflow.apigw.views.get_plugin_schema import get_plugin_schema


class TestGetPluginSchemaView(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_schema_success(self, mock_cm, mock_lib):
        """测试正常查询单个插件 schema"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_obj = MagicMock(code="test_code", version="v1.0.0")
        mock_obj.name = "分组-插件"
        mock_cm.objects.filter.return_value.first.return_value = mock_obj

        mock_component = MagicMock()
        mock_component.desc = "测试描述"
        mock_component.inputs_format.return_value = [
            {"key": "p1", "name": "参数1", "type": "string", "required": True, "schema": {}},
        ]
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        request = self.factory.get("/space/1/get_plugin_schema/", {"code": "test_code", "plugin_type": "component"})
        request.user = MagicMock(username="admin")
        response = get_plugin_schema(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["code"] == "test_code"
        assert len(data["data"]["inputs"]) == 1

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_schema_not_found(self, mock_cm, mock_bp):
        """测试插件不存在"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_cm.objects.filter.return_value.exists.return_value = False
        mock_bp.objects.filter.return_value.exists.return_value = False

        request = self.factory.get("/space/1/get_plugin_schema/", {"code": "nonexistent"})
        request.user = MagicMock(username="admin")
        response = get_plugin_schema(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is False
        assert "未找到" in data["message"]
