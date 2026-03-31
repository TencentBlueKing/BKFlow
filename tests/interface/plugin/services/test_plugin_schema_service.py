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
