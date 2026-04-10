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

from bkflow.apigw.serializers.plugin import (
    GetPluginSchemaSerializer,
    ListPluginsSerializer,
)
from bkflow.apigw.views.list_plugins import list_plugins


class TestListPluginsSerializer:
    def test_default_values(self):
        ser = ListPluginsSerializer(data={})
        assert ser.is_valid()
        assert ser.validated_data["with_detail"] is False
        assert ser.validated_data["limit"] == 100
        assert ser.validated_data["offset"] == 0

    def test_keyword_filter(self):
        ser = ListPluginsSerializer(data={"keyword": "脚本"})
        assert ser.is_valid()
        assert ser.validated_data["keyword"] == "脚本"

    def test_invalid_plugin_type(self):
        ser = ListPluginsSerializer(data={"plugin_type": "invalid"})
        assert not ser.is_valid()


class TestGetPluginSchemaSerializer:
    def test_code_required(self):
        ser = GetPluginSchemaSerializer(data={})
        assert not ser.is_valid()
        assert "code" in ser.errors

    def test_valid(self):
        ser = GetPluginSchemaSerializer(data={"code": "test_code"})
        assert ser.is_valid()


class TestListPluginsView(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.plugin.services.plugin_schema_service.SpacePluginConfigModel")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPluginAuthorization")
    def test_list_plugins_success(self, mock_auth, mock_bp, mock_cm, mock_sc, mock_spcm):
        """测试正常调用 list_plugins"""
        mock_spcm.objects.get_space_allow_list.return_value = []
        mock_sc.get_config.return_value = None

        mock_obj = MagicMock()
        mock_obj.code = "test_plugin"
        mock_obj.name = "分组-测试插件"
        mock_obj.version = "v1.0.0"

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_obj]))
        mock_qs.count.return_value = 1
        mock_cm.objects.filter.return_value.exclude.return_value = mock_qs

        mock_bp.objects.filter.return_value = []
        mock_auth.objects.filter.return_value = []

        request = self.factory.get("/space/1/list_plugins/", {"plugin_type": "component"})
        request.user = MagicMock(username="admin")
        response = list_plugins(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is True
        assert data["count"] == 1
        assert data["data"][0]["code"] == "test_plugin"
