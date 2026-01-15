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
    TemplateNodeStatistics,
    TemplateStatistics,
)


class TestTemplateNodeStatistics(TestCase):
    """模板节点统计模型测试"""

    def test_create_template_node_statistics(self):
        """测试创建模板节点统计"""
        stat = TemplateNodeStatistics.objects.create(
            component_code="test_component",
            version="v1.0",
            is_remote=False,
            template_id=1,
            space_id=1,
            scope_type="biz",
            scope_value="2",
            node_id="node_1",
            node_name="测试节点",
            is_sub=False,
            subprocess_stack="[]",
            template_creator="admin",
            template_create_time=timezone.now(),
            template_update_time=timezone.now(),
        )
        self.assertEqual(stat.component_code, "test_component")
        self.assertEqual(stat.template_id, 1)
        self.assertFalse(stat.is_remote)

    def test_str_representation(self):
        """测试字符串表示"""
        stat = TemplateNodeStatistics(
            component_code="test_component",
            template_id=1,
            node_id="node_1",
        )
        self.assertEqual(str(stat), "test_component_1_node_1")


class TestTemplateStatistics(TestCase):
    """模板统计模型测试"""

    def test_create_template_statistics(self):
        """测试创建模板统计"""
        stat = TemplateStatistics.objects.create(
            template_id=1,
            space_id=1,
            atom_total=5,
            subprocess_total=2,
            gateways_total=3,
            input_count=4,
            output_count=2,
            template_name="测试模板",
            template_creator="admin",
            is_enabled=True,
        )
        self.assertEqual(stat.atom_total, 5)
        self.assertEqual(stat.template_name, "测试模板")

    def test_unique_template_id(self):
        """测试模板ID唯一性"""
        TemplateStatistics.objects.create(
            template_id=1,
            space_id=1,
        )
        with self.assertRaises(Exception):
            TemplateStatistics.objects.create(
                template_id=1,
                space_id=1,
            )


class TestDailyStatisticsSummary(TestCase):
    """每日统计汇总模型测试"""

    def test_create_daily_summary(self):
        """测试创建每日统计汇总"""
        stat = DailyStatisticsSummary.objects.create(
            date=date.today(),
            space_id=1,
            task_created_count=100,
            task_success_count=90,
            task_failed_count=10,
            avg_task_elapsed_time=60.5,
        )
        self.assertEqual(stat.task_created_count, 100)
        self.assertEqual(stat.task_success_count, 90)

    def test_unique_together(self):
        """测试唯一约束"""
        today = date.today()
        DailyStatisticsSummary.objects.create(
            date=today,
            space_id=1,
            scope_type="biz",
            scope_value="2",
        )
        with self.assertRaises(Exception):
            DailyStatisticsSummary.objects.create(
                date=today,
                space_id=1,
                scope_type="biz",
                scope_value="2",
            )


class TestPluginExecutionSummary(TestCase):
    """插件执行汇总模型测试"""

    def test_create_plugin_summary(self):
        """测试创建插件执行汇总"""
        stat = PluginExecutionSummary.objects.create(
            period_type="day",
            period_start=date.today(),
            space_id=1,
            component_code="test_component",
            version="v1.0",
            execution_count=100,
            success_count=95,
            failed_count=5,
            avg_elapsed_time=5.5,
        )
        self.assertEqual(stat.execution_count, 100)
        self.assertEqual(stat.success_count, 95)
