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

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.collectors import TaskStatisticsCollector
from bkflow.statistics.collectors.base import BaseStatisticsCollector
from bkflow.statistics.models import TaskflowStatistics


class TestTaskStatisticsCollector(TestCase):
    """任务统计采集器测试"""

    def test_collector_initialization(self):
        """测试采集器初始化"""
        collector = TaskStatisticsCollector(task_id=1)
        self.assertEqual(collector.task_id, 1)
        self.assertIsNone(collector.instance_id)

        collector2 = TaskStatisticsCollector(instance_id="instance_001")
        self.assertIsNone(collector2.task_id)
        self.assertEqual(collector2.instance_id, "instance_001")

    def test_collect_without_task(self):
        """测试任务不存在时的采集"""
        collector = TaskStatisticsCollector(task_id=999)
        collector._task = None
        result = collector.collect_on_create()
        self.assertFalse(result)

    @patch("bkflow.statistics.conf.StatisticsConfig.include_mock_tasks")
    def test_skip_mock_task(self, mock_include_mock):
        """测试跳过 Mock 任务"""
        mock_include_mock.return_value = False

        collector = TaskStatisticsCollector(task_id=1)

        # 创建 Mock 任务
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.create_method = "MOCK"

        collector._task = mock_task
        result = collector.collect_on_create()
        self.assertFalse(result)

    @patch("bkflow.statistics.conf.StatisticsConfig.include_mock_tasks")
    @patch("bkflow.statistics.conf.StatisticsConfig.get_engine_id")
    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_collect_on_create_success(self, mock_db_alias, mock_engine_id, mock_include_mock):
        """测试成功创建任务统计"""
        mock_include_mock.return_value = True
        mock_engine_id.return_value = "test_engine"
        mock_db_alias.return_value = "default"

        collector = TaskStatisticsCollector(task_id=1)

        # 创建 mock 任务
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.instance_id = "instance_001"
        mock_task.template_id = 1
        mock_task.space_id = 1
        mock_task.scope_type = "biz"
        mock_task.scope_value = "2"
        mock_task.creator = "admin"
        mock_task.executor = "admin"
        mock_task.create_time = timezone.now()
        mock_task.create_method = "API"
        mock_task.trigger_method = "manual"
        mock_task.is_started = False
        mock_task.execution_data = {
            "activities": {
                "node_1": {"type": "ServiceActivity"},
            },
            "gateways": {},
        }

        collector._task = mock_task

        result = collector.collect_on_create()
        self.assertTrue(result)

        # 验证是否创建了统计记录
        stat = TaskflowStatistics.objects.get(task_id=1)
        self.assertEqual(stat.instance_id, "instance_001")
        self.assertEqual(stat.engine_id, "test_engine")

    def test_count_nodes_in_pipeline_tree(self):
        """测试统计 pipeline_tree 中的节点"""
        pipeline_tree = {
            "activities": {
                "node_1": {"type": "ServiceActivity"},
                "node_2": {"type": "ServiceActivity"},
                "node_3": {"type": "SubProcess", "pipeline": {}},
            },
            "gateways": {
                "gateway_1": {"type": "ParallelGateway"},
            },
        }

        atom, subprocess, gateways = BaseStatisticsCollector.count_pipeline_tree_nodes(pipeline_tree)
        self.assertEqual(atom, 2)
        self.assertEqual(subprocess, 1)
        self.assertEqual(gateways, 1)
