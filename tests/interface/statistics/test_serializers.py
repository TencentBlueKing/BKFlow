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

from datetime import date

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowStatistics,
    TemplateStatistics,
)
from bkflow.statistics.serializers import (
    DailyStatisticsSummarySerializer,
    PluginExecutionSummarySerializer,
    PluginRankingSerializer,
    StatisticsOverviewSerializer,
    TaskflowStatisticsSerializer,
    TaskTrendSerializer,
    TemplateRankingSerializer,
    TemplateStatisticsSerializer,
)


class TestStatisticsOverviewSerializer(TestCase):
    """统计概览序列化器测试"""

    def test_serialization(self):
        """测试序列化"""
        data = {
            "space_id": 1,
            "scope_type": "biz",
            "scope_value": "2",
            "total_tasks": 100,
            "success_tasks": 90,
            "failed_tasks": 10,
            "success_rate": 90.0,
            "total_templates": 50,
            "active_templates": 45,
            "total_nodes_executed": 1000,
            "node_success_rate": 95.0,
            "avg_task_elapsed_time": 60.5,
        }
        serializer = StatisticsOverviewSerializer(data)
        self.assertEqual(serializer.data["space_id"], 1)
        self.assertEqual(serializer.data["success_rate"], 90.0)


class TestTaskTrendSerializer(TestCase):
    """任务趋势序列化器测试"""

    def test_serialization(self):
        """测试序列化"""
        data = {
            "date": date.today(),
            "task_created_count": 10,
            "task_finished_count": 8,
            "task_success_count": 7,
            "success_rate": 87.5,
        }
        serializer = TaskTrendSerializer(data)
        self.assertEqual(serializer.data["task_created_count"], 10)


class TestPluginRankingSerializer(TestCase):
    """插件排行序列化器测试"""

    def test_serialization(self):
        """测试序列化"""
        data = {
            "component_code": "test_component",
            "version": "v1.0",
            "execution_count": 100,
            "success_count": 95,
            "failed_count": 5,
            "success_rate": 95.0,
            "avg_elapsed_time": 5.5,
        }
        serializer = PluginRankingSerializer(data)
        self.assertEqual(serializer.data["component_code"], "test_component")
        self.assertEqual(serializer.data["success_rate"], 95.0)


class TestTemplateRankingSerializer(TestCase):
    """模板排行序列化器测试"""

    def test_serialization(self):
        """测试序列化"""
        data = {
            "template_id": 1,
            "template_name": "测试模板",
            "task_count": 50,
            "success_count": 45,
            "success_rate": 90.0,
        }
        serializer = TemplateRankingSerializer(data)
        self.assertEqual(serializer.data["template_id"], 1)
        self.assertEqual(serializer.data["template_name"], "测试模板")


class TestModelSerializers(TestCase):
    """模型序列化器测试"""

    def test_template_statistics_serializer(self):
        """测试模板统计序列化器"""
        stat = TemplateStatistics(
            template_id=1,
            space_id=1,
            atom_total=5,
            template_name="测试模板",
        )
        serializer = TemplateStatisticsSerializer(stat)
        self.assertEqual(serializer.data["template_id"], 1)

    def test_taskflow_statistics_serializer(self):
        """测试任务统计序列化器"""
        stat = TaskflowStatistics(
            task_id=1,
            instance_id="instance_001",
            space_id=1,
            create_time=timezone.now(),
        )
        serializer = TaskflowStatisticsSerializer(stat)
        self.assertEqual(serializer.data["task_id"], 1)

    def test_daily_summary_serializer(self):
        """测试每日汇总序列化器"""
        stat = DailyStatisticsSummary(
            date=date.today(),
            space_id=1,
            task_created_count=100,
        )
        serializer = DailyStatisticsSummarySerializer(stat)
        self.assertEqual(serializer.data["task_created_count"], 100)

    def test_plugin_summary_serializer(self):
        """测试插件汇总序列化器"""
        stat = PluginExecutionSummary(
            period_type="day",
            period_start=date.today(),
            space_id=1,
            component_code="test_component",
            execution_count=50,
        )
        serializer = PluginExecutionSummarySerializer(stat)
        self.assertEqual(serializer.data["execution_count"], 50)
