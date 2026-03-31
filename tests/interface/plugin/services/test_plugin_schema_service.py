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

from unittest.mock import MagicMock, patch

from bkflow.plugin.services.plugin_schema_service import PluginSchemaService


class TestListComponentPlugins:
    """测试内置插件列表查询"""

    @patch("bkflow.plugin.services.plugin_schema_service.SpacePluginConfigModel")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_list_component_plugins_basic(self, mock_cm, mock_sc, mock_spcm):
        """测试基本的内置插件列表查询"""
        mock_spcm.objects.get_space_allow_list.return_value = []
        mock_sc.get_config.return_value = None

        mock_obj1 = MagicMock()
        mock_obj1.code = "job_fast_execute_script"
        mock_obj1.name = "作业平台(JOB)-快速执行脚本"
        mock_obj1.version = "v1.0.0"

        mock_obj2 = MagicMock()
        mock_obj2.code = "bk_notify"
        mock_obj2.name = "蓝鲸服务(BK)-发送通知"
        mock_obj2.version = "v1.0.0"

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_obj1, mock_obj2]))
        mock_qs.count.return_value = 2
        mock_cm.objects.filter.return_value.exclude.return_value = mock_qs

        service = PluginSchemaService(space_id=1)
        plugins, count = service.list_plugins(plugin_type="component", without_detail=True)

        assert count == 2
        assert plugins[0]["code"] == "job_fast_execute_script"
        assert plugins[0]["plugin_type"] == "component"
        assert plugins[0]["name"] == "快速执行脚本"
        assert plugins[0]["group_name"] == "作业平台(JOB)"
        assert "inputs" not in plugins[0]

    @patch("bkflow.plugin.services.plugin_schema_service.SpacePluginConfigModel")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_list_component_plugins_keyword_filter(self, mock_cm, mock_sc, mock_spcm):
        """测试 keyword 搜索过滤"""
        mock_spcm.objects.get_space_allow_list.return_value = []
        mock_sc.get_config.return_value = None

        mock_obj1 = MagicMock()
        mock_obj1.code = "job_fast_execute_script"
        mock_obj1.name = "作业平台(JOB)-快速执行脚本"
        mock_obj1.version = "v1.0.0"

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_obj1]))
        mock_qs.count.return_value = 1
        mock_cm.objects.filter.return_value.exclude.return_value = mock_qs

        service = PluginSchemaService(space_id=1)
        plugins, count = service.list_plugins(plugin_type="component", keyword="脚本", without_detail=True)

        assert count == 1
        assert plugins[0]["code"] == "job_fast_execute_script"


class TestComponentSchema:
    """测试内置插件 schema 提取"""

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_component_schema(self, mock_cm, mock_lib):
        """测试从 ComponentLibrary 提取 inputs/outputs"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]

        mock_component = MagicMock()
        mock_component.desc = "执行脚本"
        mock_component.inputs_format.return_value = [
            {"key": "script_content", "name": "脚本内容", "type": "string", "required": True, "schema": {}},
        ]
        mock_component.outputs_format.return_value = [
            {"key": "_result", "name": "执行结果", "type": "bool", "schema": {}},
        ]
        mock_lib.get_component_class.return_value = mock_component

        service = PluginSchemaService(space_id=1)
        schema = service._get_component_schema("job_fast_execute_script")

        assert schema["inputs"][0]["key"] == "script_content"
        assert schema["outputs"][0]["key"] == "_result"
        assert schema["description"] == "执行脚本"

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_component_schema_with_version(self, mock_cm, mock_lib):
        """测试指定版本查询"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0", "v2.0.0"]

        mock_component = MagicMock()
        mock_component.desc = "v2 版本"
        mock_component.inputs_format.return_value = []
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        service = PluginSchemaService(space_id=1)
        schema = service._get_component_schema("test_code", version="v2.0.0")

        assert schema["description"] == "v2 版本"
        mock_lib.get_component_class.assert_called_with("test_code", "v2.0.0")


class TestRemotePlugins:
    """测试蓝鲸标准插件查询"""

    @patch("bkflow.plugin.services.plugin_schema_service.BKPluginAuthorization")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    def test_list_remote_plugins(self, mock_bp, mock_auth):
        """测试蓝鲸插件列表"""
        mock_plugin = MagicMock()
        mock_plugin.code = "my_plugin"
        mock_plugin.name = "我的插件"
        mock_plugin.introduction = "自定义插件"

        mock_bp.objects.filter.return_value = [mock_plugin]

        mock_auth_obj = MagicMock()
        mock_auth_obj.code = "my_plugin"
        mock_auth_obj.white_list = ["*"]
        mock_auth.objects.filter.return_value = [mock_auth_obj]

        service = PluginSchemaService(space_id=1)
        results = service._list_remote_plugins()

        assert len(results) == 1
        assert results[0]["code"] == "my_plugin"
        assert results[0]["plugin_type"] == "remote_plugin"
        assert results[0]["description"] == "自定义插件"

    @patch("bkflow.plugin.services.plugin_schema_service.BKPluginAuthorization")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    def test_list_remote_plugins_auth_filter(self, mock_bp, mock_auth):
        """测试蓝鲸插件授权过滤 — 非授权空间的插件不展示"""
        mock_plugin = MagicMock()
        mock_plugin.code = "restricted_plugin"
        mock_plugin.name = "受限插件"
        mock_plugin.introduction = ""

        mock_bp.objects.filter.return_value = [mock_plugin]

        mock_auth_obj = MagicMock()
        mock_auth_obj.code = "restricted_plugin"
        mock_auth_obj.white_list = ["999"]
        mock_auth.objects.filter.return_value = [mock_auth_obj]

        service = PluginSchemaService(space_id=1)
        results = service._list_remote_plugins()

        assert len(results) == 0

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
    def test_get_remote_plugin_schema(self, mock_client_cls, mock_cache):
        """测试蓝鲸插件 schema 获取"""
        mock_cache.get.return_value = None

        mock_client = MagicMock()
        mock_client.get_meta.return_value = {
            "result": True,
            "data": {
                "versions": ["1.0.0", "1.2.0"],
                "inputs": [
                    {"key": "param1", "name": "参数1", "type": "string", "required": True},
                ],
                "outputs": [
                    {"key": "result_data", "name": "结果", "type": "string"},
                ],
            },
        }
        mock_client_cls.return_value = mock_client

        service = PluginSchemaService(space_id=1)
        schema = service._get_remote_plugin_schema("my_plugin")

        assert schema["inputs"][0]["key"] == "param1"
        assert schema["outputs"][0]["key"] == "result_data"
        assert schema["version"] == "1.2.0"
        mock_cache.set.assert_called_once()
