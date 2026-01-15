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

from unittest.mock import patch

from django.test import TestCase, override_settings

from bkflow.statistics.conf import StatisticsConfig


class TestStatisticsConfigForEngine(TestCase):
    """Engine 模块统计配置测试"""

    @patch("env.STATISTICS_ENABLED", True)
    @patch("env.BKFLOW_MODULE_TYPE", "engine")
    def test_should_collect_task_stats_engine(self):
        """测试 Engine 模块采集任务统计"""
        result = StatisticsConfig.should_collect_task_stats()
        self.assertTrue(result)

    @patch("env.STATISTICS_ENABLED", True)
    @patch("env.BKFLOW_MODULE_TYPE", "interface")
    def test_should_collect_task_stats_interface(self):
        """测试 Interface 模块不采集任务统计"""
        result = StatisticsConfig.should_collect_task_stats()
        self.assertFalse(result)

    @patch("env.STATISTICS_ENABLED", False)
    @patch("env.BKFLOW_MODULE_TYPE", "engine")
    def test_should_collect_task_stats_disabled(self):
        """测试统计功能禁用时不采集任务统计"""
        result = StatisticsConfig.should_collect_task_stats()
        self.assertFalse(result)

    @patch("env.BKFLOW_MODULE_CODE", "engine_001")
    def test_get_engine_id(self):
        """测试获取 Engine ID"""
        with patch.object(StatisticsConfig, "get_engine_id") as mock_method:
            mock_method.return_value = "engine_001"
            result = StatisticsConfig.get_engine_id()
            self.assertEqual(result, "engine_001")

    def test_get_db_alias_default(self):
        """测试获取默认数据库别名"""
        result = StatisticsConfig.get_db_alias()
        self.assertEqual(result, "default")

    @override_settings(
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
            "statistics": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        }
    )
    def test_get_db_alias_with_statistics(self):
        """测试配置了 statistics 数据库时的别名"""
        result = StatisticsConfig.get_db_alias()
        self.assertEqual(result, "statistics")
