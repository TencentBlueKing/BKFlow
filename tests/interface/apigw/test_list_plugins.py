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

import pytest
from django.test import RequestFactory, SimpleTestCase, override_settings

from bkflow.apigw.serializers.plugin import (
    GetPluginSchemaSerializer,
    ListPluginsSerializer,
)
from bkflow.apigw.views.list_plugins import list_plugins
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability


def create_open_plugin_catalog(space_id=1, source_key="sops"):
    OpenPluginCatalogIndex.objects.create(
        space_id=space_id,
        source_key=source_key,
        plugin_id="open_plugin_001",
        plugin_code="job_execute_task",
        plugin_name="JOB 执行作业",
        plugin_source="builtin",
        group_name="作业平台",
        default_version="1.2.0",
        latest_version="1.3.0",
        wrapper_version="v4.0.0",
        versions=["1.2.0", "1.3.0"],
        meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
        status=OpenPluginCatalogIndex.Status.AVAILABLE,
    )
    SpaceOpenPluginAvailability.objects.create(
        space_id=space_id,
        source_key=source_key,
        plugin_id="open_plugin_001",
        enabled=True,
    )


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
    def test_code_or_plugin_id_required(self):
        ser = GetPluginSchemaSerializer(data={})
        assert not ser.is_valid()

    def test_plugin_id_only_is_valid(self):
        ser = GetPluginSchemaSerializer(data={"plugin_id": "open_plugin_001"})
        assert ser.is_valid()
        assert ser.validated_data["plugin_id"] == "open_plugin_001"

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

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.apigw.views.list_plugins.PluginSchemaService")
    def test_list_plugins_forwards_plugin_source(self, mock_service_cls):
        """plugin_source 需传到 PluginSchemaService，而不是只停在序列化器。"""
        mock_service = MagicMock()
        mock_service.list_plugins.return_value = ([], 0)
        mock_service_cls.return_value = mock_service

        request = self.factory.get(
            "/space/1/list_plugins/",
            {"plugin_type": "uniform_api", "plugin_source": "builtin"},
        )
        request.user = MagicMock(username="admin")
        response = list_plugins(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is True
        mock_service.list_plugins.assert_called_once_with(
            keyword=None,
            plugin_type="uniform_api",
            with_detail=False,
            limit=100,
            offset=0,
            plugin_source="builtin",
        )


@pytest.mark.django_db
@override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
def test_list_plugins_returns_enabled_uniform_api_source():
    create_open_plugin_catalog(space_id=1, source_key="sops")

    factory = RequestFactory()
    request = factory.get("/space/1/list_plugins/", {"plugin_type": "uniform_api"})
    request.user = MagicMock(username="admin")
    response = list_plugins(request, space_id="1")

    data = json.loads(response.content)
    assert data["result"] is True
    assert data["count"] == 1
    assert data["data"][0]["code"] == "open_plugin_001"
    assert data["data"][0]["source_key"] == "sops"
