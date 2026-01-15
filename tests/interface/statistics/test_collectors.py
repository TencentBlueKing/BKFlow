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

from unittest.mock import MagicMock

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.collectors import TemplateStatisticsCollector
from bkflow.statistics.collectors.base import BaseStatisticsCollector


class TestBaseStatisticsCollector(TestCase):
    """基础统计采集器测试"""

    def test_count_pipeline_tree_nodes_empty(self):
        """测试空 pipeline_tree 节点计数"""
        pipeline_tree = {}
        atom, subprocess, gateways = BaseStatisticsCollector.count_pipeline_tree_nodes(pipeline_tree)
        self.assertEqual(atom, 0)
        self.assertEqual(subprocess, 0)
        self.assertEqual(gateways, 0)

    def test_count_pipeline_tree_nodes_with_activities(self):
        """测试带有活动节点的 pipeline_tree 计数"""
        pipeline_tree = {
            "activities": {
                "node_1": {"id": "node_1", "type": "ServiceActivity"},
                "node_2": {"id": "node_2", "type": "ServiceActivity"},
                "node_3": {"id": "node_3", "type": "SubProcess", "pipeline": {}},
            },
            "gateways": {
                "gateway_1": {"id": "gateway_1", "type": "ParallelGateway"},
                "gateway_2": {"id": "gateway_2", "type": "ConvergeGateway"},
            },
        }
        atom, subprocess, gateways = BaseStatisticsCollector.count_pipeline_tree_nodes(pipeline_tree)
        self.assertEqual(atom, 2)
        self.assertEqual(subprocess, 1)
        self.assertEqual(gateways, 2)

    def test_count_pipeline_tree_nodes_with_nested_subprocess(self):
        """测试嵌套子流程的节点计数"""
        pipeline_tree = {
            "activities": {
                "node_1": {"id": "node_1", "type": "ServiceActivity"},
                "subprocess_1": {
                    "id": "subprocess_1",
                    "type": "SubProcess",
                    "pipeline": {
                        "activities": {
                            "sub_node_1": {"id": "sub_node_1", "type": "ServiceActivity"},
                            "sub_node_2": {"id": "sub_node_2", "type": "ServiceActivity"},
                        },
                        "gateways": {},
                    },
                },
            },
            "gateways": {},
        }
        atom, subprocess, gateways = BaseStatisticsCollector.count_pipeline_tree_nodes(pipeline_tree)
        self.assertEqual(atom, 3)  # 1 + 2 from subprocess
        self.assertEqual(subprocess, 1)
        self.assertEqual(gateways, 0)

    def test_parse_datetime_with_valid_string(self):
        """测试解析有效时间字符串"""
        time_str = "2024-01-15T10:30:00+08:00"
        result = BaseStatisticsCollector.parse_datetime(time_str)
        self.assertIsNotNone(result)

    def test_parse_datetime_with_none(self):
        """测试解析空值"""
        result = BaseStatisticsCollector.parse_datetime(None)
        self.assertIsNone(result)

    def test_parse_datetime_with_space_timezone(self):
        """测试解析带空格时区的时间字符串"""
        time_str = "2024-01-15 10:30:00 +0800"
        result = BaseStatisticsCollector.parse_datetime(time_str)
        # Should handle space-separated timezone
        self.assertIsNotNone(result)


class TestTemplateStatisticsCollector(TestCase):
    """模板统计采集器测试"""

    def test_collect_without_template(self):
        """测试模板不存在时的采集"""
        collector = TemplateStatisticsCollector(template_id=999)
        collector._template = None  # Force template to be None
        result = collector.collect()
        self.assertFalse(result)

    def test_collect_nodes_from_pipeline_tree(self):
        """测试从 pipeline_tree 收集节点"""
        collector = TemplateStatisticsCollector(template_id=1)

        # Create mock template
        mock_template = MagicMock()
        mock_template.id = 1
        mock_template.space_id = 1
        mock_template.scope_type = "biz"
        mock_template.scope_value = "2"
        mock_template.creator = "admin"
        mock_template.create_at = timezone.now()
        mock_template.update_at = timezone.now()
        mock_template.pipeline_tree = {
            "activities": {
                "node_1": {
                    "id": "node_1",
                    "type": "ServiceActivity",
                    "name": "节点1",
                    "component": {"code": "test_component", "version": "v1.0"},
                },
            },
            "gateways": {},
        }

        collector._template = mock_template

        nodes = collector._collect_nodes(
            pipeline_tree=mock_template.pipeline_tree,
            subprocess_stack=[],
            is_sub=False,
        )

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].component_code, "test_component")
        self.assertEqual(nodes[0].node_name, "节点1")

    def test_collect_remote_plugin_nodes(self):
        """测试收集第三方插件节点"""
        collector = TemplateStatisticsCollector(template_id=1)

        mock_template = MagicMock()
        mock_template.id = 1
        mock_template.space_id = 1
        mock_template.scope_type = "biz"
        mock_template.scope_value = "2"
        mock_template.creator = "admin"
        mock_template.create_at = timezone.now()
        mock_template.update_at = timezone.now()
        mock_template.pipeline_tree = {
            "activities": {
                "node_1": {
                    "id": "node_1",
                    "type": "ServiceActivity",
                    "name": "远程插件节点",
                    "component": {
                        "code": "remote_plugin",
                        "version": "v1.0",
                        "inputs": {
                            "plugin_code": {"value": "my_remote_plugin"},
                            "plugin_version": {"value": "v2.0"},
                        },
                    },
                },
            },
            "gateways": {},
        }

        collector._template = mock_template

        nodes = collector._collect_nodes(
            pipeline_tree=mock_template.pipeline_tree,
            subprocess_stack=[],
            is_sub=False,
        )

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].component_code, "my_remote_plugin")
        self.assertEqual(nodes[0].version, "v2.0")
        self.assertTrue(nodes[0].is_remote)
