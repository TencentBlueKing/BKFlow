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

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
)
from bkflow.statistics.tasks import (
    clean_expired_statistics_task,
    generate_daily_summary_task,
    generate_plugin_summary_task,
    template_post_save_statistics_task,
)


class TestTemplateStatisticsTasks(TestCase):
    """模板统计任务测试"""

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    def test_template_task_disabled(self, mock_is_enabled):
        """测试统计功能禁用时跳过采集"""
        mock_is_enabled.return_value = False
        # Should not raise any exception
        template_post_save_statistics_task(template_id=1)

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    @patch("bkflow.statistics.collectors.TemplateStatisticsCollector.collect")
    def test_template_task_enabled(self, mock_collect, mock_is_enabled):
        """测试统计功能启用时执行采集"""
        mock_is_enabled.return_value = True
        mock_collect.return_value = True
        template_post_save_statistics_task(template_id=1)
        mock_collect.assert_called_once()


class TestSummaryTasks(TestCase):
    """汇总任务测试（在 Interface 模块执行）"""

    def setUp(self):
        """创建测试数据"""
        now = timezone.now()

        # 创建任务统计数据
        TaskflowStatistics.objects.create(
            task_id=1,
            instance_id="instance_001",
            space_id=1,
            scope_type="biz",
            scope_value="2",
            create_time=now - timedelta(days=1),
            is_started=True,
            is_finished=True,
            is_success=True,
            elapsed_time=60,
        )
        TaskflowStatistics.objects.create(
            task_id=2,
            instance_id="instance_002",
            space_id=1,
            scope_type="biz",
            scope_value="2",
            create_time=now - timedelta(days=1),
            is_started=True,
            is_finished=True,
            is_success=False,
            elapsed_time=120,
        )

        # 创建节点执行统计数据
        TaskflowExecutedNodeStatistics.objects.create(
            component_code="test_component",
            version="v1.0",
            task_id=1,
            instance_id="instance_001",
            space_id=1,
            scope_type="biz",
            scope_value="2",
            node_id="node_1",
            started_time=now - timedelta(days=1),
            status=True,
            state="FINISHED",
            task_create_time=now - timedelta(days=1),
        )

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    def test_daily_summary_task_disabled(self, mock_is_enabled):
        """测试统计功能禁用时跳过汇总"""
        mock_is_enabled.return_value = False
        generate_daily_summary_task()
        self.assertEqual(DailyStatisticsSummary.objects.count(), 0)

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_daily_summary_task_enabled(self, mock_db_alias, mock_is_enabled):
        """测试每日汇总任务"""
        mock_is_enabled.return_value = True
        mock_db_alias.return_value = "default"
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        generate_daily_summary_task(target_date=yesterday)
        # 检查是否创建了汇总记录
        summaries = DailyStatisticsSummary.objects.all()
        self.assertGreaterEqual(summaries.count(), 1)

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_plugin_summary_task(self, mock_db_alias, mock_is_enabled):
        """测试插件汇总任务"""
        mock_is_enabled.return_value = True
        mock_db_alias.return_value = "default"
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        generate_plugin_summary_task(period_type="day", target_date=yesterday)
        # 检查是否创建了汇总记录
        summaries = PluginExecutionSummary.objects.all()
        self.assertGreaterEqual(summaries.count(), 1)

    @patch("bkflow.statistics.conf.StatisticsConfig.is_enabled")
    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    @patch("bkflow.statistics.conf.StatisticsConfig.get_retention_days")
    def test_clean_expired_statistics_task(self, mock_retention, mock_db_alias, mock_is_enabled):
        """测试清理过期统计数据"""
        mock_is_enabled.return_value = True
        mock_db_alias.return_value = "default"
        mock_retention.return_value = 30
        # 创建过期数据
        old_date = timezone.localdate() - timedelta(days=60)
        DailyStatisticsSummary.objects.create(
            date=old_date,
            space_id=1,
        )
        clean_expired_statistics_task()
        # 过期数据应该被清理
        self.assertEqual(DailyStatisticsSummary.objects.filter(date=old_date).count(), 0)
