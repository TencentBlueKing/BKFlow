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

from django.test import TestCase, override_settings

from bkflow.statistics.db_router import StatisticsDBRouter
from bkflow.statistics.models import TaskflowStatistics, TemplateStatistics


class TestStatisticsDBRouter(TestCase):
    """统计数据库路由器测试"""

    def setUp(self):
        self.router = StatisticsDBRouter()

    def test_db_for_read_statistics_model(self):
        """测试统计模型读操作路由"""
        model = TemplateStatistics
        result = self.router.db_for_read(model)
        # Should return 'default' since 'statistics' db is not configured
        self.assertEqual(result, "default")

    def test_db_for_write_statistics_model(self):
        """测试统计模型写操作路由"""
        model = TaskflowStatistics
        result = self.router.db_for_write(model)
        self.assertEqual(result, "default")

    def test_db_for_read_non_statistics_model(self):
        """测试非统计模型读操作路由"""
        mock_model = MagicMock()
        mock_model._meta.app_label = "other_app"
        result = self.router.db_for_read(mock_model)
        self.assertIsNone(result)

    def test_db_for_write_non_statistics_model(self):
        """测试非统计模型写操作路由"""
        mock_model = MagicMock()
        mock_model._meta.app_label = "other_app"
        result = self.router.db_for_write(mock_model)
        self.assertIsNone(result)

    def test_allow_relation_same_app(self):
        """测试同一 app 内的关联"""
        mock_obj1 = MagicMock()
        mock_obj1._meta.app_label = "statistics"
        mock_obj2 = MagicMock()
        mock_obj2._meta.app_label = "statistics"
        result = self.router.allow_relation(mock_obj1, mock_obj2)
        self.assertTrue(result)

    def test_allow_relation_different_app(self):
        """测试不同 app 间的关联"""
        mock_obj1 = MagicMock()
        mock_obj1._meta.app_label = "statistics"
        mock_obj2 = MagicMock()
        mock_obj2._meta.app_label = "other_app"
        result = self.router.allow_relation(mock_obj1, mock_obj2)
        self.assertFalse(result)

    def test_allow_relation_both_non_statistics(self):
        """测试两个都是非统计 app 的关联"""
        mock_obj1 = MagicMock()
        mock_obj1._meta.app_label = "app1"
        mock_obj2 = MagicMock()
        mock_obj2._meta.app_label = "app2"
        result = self.router.allow_relation(mock_obj1, mock_obj2)
        self.assertIsNone(result)

    def test_allow_migrate_statistics_app(self):
        """测试统计 app 的迁移路由"""
        result = self.router.allow_migrate("default", "statistics")
        self.assertTrue(result)

        result = self.router.allow_migrate("statistics", "statistics")
        self.assertFalse(result)  # statistics db doesn't exist, so returns False

    def test_allow_migrate_other_app(self):
        """测试其他 app 的迁移路由"""
        # 非统计 app 可以在 default 数据库迁移
        result = self.router.allow_migrate("default", "other_app")
        self.assertTrue(result)

        # 非统计 app 不应该在 statistics 数据库迁移
        result = self.router.allow_migrate("statistics", "other_app")
        self.assertFalse(result)

    @override_settings(
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
            "statistics": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        }
    )
    def test_get_db_alias_with_statistics_db(self):
        """测试配置了 statistics 数据库时的别名获取"""
        result = self.router._get_db_alias()
        self.assertEqual(result, "statistics")

    def test_get_db_alias_without_statistics_db(self):
        """测试未配置 statistics 数据库时的别名获取"""
        result = self.router._get_db_alias()
        self.assertEqual(result, "default")
