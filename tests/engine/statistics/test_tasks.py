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
from bkflow.statistics.models import TaskflowStatistics
from bkflow.statistics.tasks import (
    task_archive_statistics_task,
    task_created_statistics_task,
)


class TestTaskStatisticsTasks(TestCase):
    """任务统计任务测试（在 Engine 模块执行）"""

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    def test_task_created_task_disabled(self, mock_is_enabled):
        """测试统计功能禁用时跳过采集"""
        mock_is_enabled.return_value = False
        task_created_statistics_task(task_id=1)

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    @patch("bkflow.statistics.collectors.TaskStatisticsCollector.collect_on_create")
    def test_task_created_task_enabled(self, mock_collect, mock_is_enabled):
        """测试任务创建统计"""
        mock_is_enabled.return_value = True
        mock_collect.return_value = True
        task_created_statistics_task(task_id=1)
        mock_collect.assert_called_once()

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    def test_task_archive_task_disabled(self, mock_is_enabled):
        """测试统计功能禁用时跳过归档采集"""
        mock_is_enabled.return_value = False
        task_archive_statistics_task(instance_id="instance_001")

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    @patch("bkflow.statistics.collectors.TaskStatisticsCollector.collect_on_archive")
    def test_task_archive_task_enabled(self, mock_collect, mock_is_enabled):
        """测试任务归档统计"""
        mock_is_enabled.return_value = True
        mock_collect.return_value = True
        task_archive_statistics_task(instance_id="instance_001")
        mock_collect.assert_called_once()

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    @patch("bkflow.statistics.collectors.TaskStatisticsCollector.collect_on_create")
    @patch("bkflow.statistics.collectors.TaskStatisticsCollector.collect_on_archive")
    def test_task_full_lifecycle(self, mock_archive, mock_create, mock_is_enabled):
        """测试任务完整生命周期统计"""
        mock_is_enabled.return_value = True
        mock_create.return_value = True
        mock_archive.return_value = True
        # 创建任务时采集
        task_created_statistics_task(task_id=1)
        mock_create.assert_called_once()
        # 归档任务时采集
        task_archive_statistics_task(instance_id="instance_001")
        mock_archive.assert_called_once()


class TestTaskStatisticsCollectorIntegration(TestCase):
    """任务统计采集器集成测试"""

    @patch("bkflow.statistics.conf.StatisticsConfig.get_engine_id")
    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    @patch("bkflow.statistics.conf.StatisticsConfig.include_mock_tasks")
    def test_collect_with_nested_subprocess(self, mock_include_mock, mock_db_alias, mock_engine_id):
        """测试采集嵌套子流程的任务"""
        mock_include_mock.return_value = True
        mock_db_alias.return_value = "default"
        mock_engine_id.return_value = "test_engine"

        collector = TaskStatisticsCollector(task_id=1)

        # 创建带嵌套子流程的 mock 任务
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
                "subprocess_1": {
                    "type": "SubProcess",
                    "pipeline": {
                        "activities": {
                            "sub_node_1": {"type": "ServiceActivity"},
                            "sub_node_2": {"type": "ServiceActivity"},
                        },
                        "gateways": {},
                    },
                },
            },
            "gateways": {
                "gateway_1": {"type": "ParallelGateway"},
            },
        }

        collector._task = mock_task

        result = collector.collect_on_create()
        self.assertTrue(result)

        stat = TaskflowStatistics.objects.get(task_id=1)
        # 1 (root) + 2 (subprocess) = 3 atoms
        self.assertEqual(stat.atom_total, 3)
        self.assertEqual(stat.subprocess_total, 1)
        self.assertEqual(stat.gateways_total, 1)
