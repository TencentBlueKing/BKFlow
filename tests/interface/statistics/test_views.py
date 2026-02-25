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

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from blueapps.account.models import User
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.statistics.models import (
    DailyStatisticsSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateStatistics,
)
from bkflow.statistics.views import SpaceStatisticsViewSet


@pytest.mark.django_db
class TestSpaceStatisticsViewSet:
    """空间统计 API 测试"""

    def setup_method(self):
        """设置测试数据"""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="testuser", password="password")
        now = timezone.now()

        # 创建模板统计
        TemplateStatistics.objects.create(
            template_id=1,
            space_id=1,
            template_name="测试模板1",
            atom_total=5,
            is_enabled=True,
        )
        TemplateStatistics.objects.create(
            template_id=2,
            space_id=1,
            template_name="测试模板2",
            atom_total=3,
            is_enabled=True,
        )

        # 创建任务统计
        for i in range(10):
            TaskflowStatistics.objects.create(
                task_id=i + 1,
                instance_id=f"instance_{i+1:03d}",
                template_id=1 if i < 6 else 2,
                space_id=1,
                create_time=now - timedelta(days=i % 7),
                is_started=True,
                is_finished=True,
                is_success=(i % 3 != 0),
                elapsed_time=60 + i * 10,
            )

        # 创建节点执行统计
        for i in range(20):
            TaskflowExecutedNodeStatistics.objects.create(
                component_code=f"component_{i % 3}",
                version="v1.0",
                task_id=(i % 10) + 1,
                instance_id=f"instance_{(i % 10)+1:03d}",
                space_id=1,
                node_id=f"node_{i}",
                started_time=now - timedelta(days=i % 7),
                status=(i % 4 != 0),
                state="FINISHED" if i % 4 != 0 else "FAILED",
                elapsed_time=5 + i,
                task_create_time=now - timedelta(days=i % 7),
            )

        # 创建每日汇总
        for i in range(7):
            DailyStatisticsSummary.objects.create(
                date=date.today() - timedelta(days=i),
                space_id=1,
                task_created_count=10 + i,
                task_finished_count=9 + i,
                task_success_count=8 + i,
            )

    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_overview_without_space_id(self, mock_db_alias):
        """测试缺少 space_id 参数"""
        mock_db_alias.return_value = "default"

        view = SpaceStatisticsViewSet.as_view({"get": "overview"})
        request = self.factory.get("/api/statistics/space/overview/")
        force_authenticate(request, user=self.user)

        response = view(request)
        assert response.status_code == 400
        assert "error" in response.data

    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_overview_with_space_id(self, mock_db_alias):
        """测试获取空间概览"""
        mock_db_alias.return_value = "default"

        view = SpaceStatisticsViewSet.as_view({"get": "overview"})
        request = self.factory.get("/api/statistics/space/overview/", {"space_id": 1})
        force_authenticate(request, user=self.user)

        response = view(request)
        assert response.status_code == 200
        assert response.data["space_id"] == 1
        assert "total_tasks" in response.data
        assert "success_rate" in response.data
        assert "total_templates" in response.data

    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_task_trend(self, mock_db_alias):
        """测试获取任务趋势"""
        mock_db_alias.return_value = "default"

        view = SpaceStatisticsViewSet.as_view({"get": "task_trend"})
        request = self.factory.get("/api/statistics/space/task-trend/", {"space_id": 1, "date_range": "7d"})
        force_authenticate(request, user=self.user)

        response = view(request)
        assert response.status_code == 200
        assert isinstance(response.data, list)

    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_plugin_ranking(self, mock_db_alias):
        """测试获取插件排行"""
        mock_db_alias.return_value = "default"

        view = SpaceStatisticsViewSet.as_view({"get": "plugin_ranking"})
        request = self.factory.get("/api/statistics/space/plugin-ranking/", {"space_id": 1})
        force_authenticate(request, user=self.user)

        response = view(request)
        assert response.status_code == 200
        assert isinstance(response.data, list)
        if len(response.data) > 0:
            assert "component_code" in response.data[0]
            assert "execution_count" in response.data[0]
            assert "success_rate" in response.data[0]

    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_template_ranking(self, mock_db_alias):
        """测试获取模板排行"""
        mock_db_alias.return_value = "default"

        view = SpaceStatisticsViewSet.as_view({"get": "template_ranking"})
        request = self.factory.get("/api/statistics/space/template-ranking/", {"space_id": 1})
        force_authenticate(request, user=self.user)

        response = view(request)
        assert response.status_code == 200
        assert isinstance(response.data, list)
        if len(response.data) > 0:
            assert "template_id" in response.data[0]
            assert "task_count" in response.data[0]
            assert "success_rate" in response.data[0]

    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_daily_summary(self, mock_db_alias):
        """测试获取每日统计汇总"""
        mock_db_alias.return_value = "default"

        view = SpaceStatisticsViewSet.as_view({"get": "daily_summary"})
        request = self.factory.get("/api/statistics/space/daily-summary/", {"space_id": 1, "date_range": "7d"})
        force_authenticate(request, user=self.user)

        response = view(request)
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) > 0

    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_overview_with_scope_filter(self, mock_db_alias):
        """测试带范围过滤的概览"""
        mock_db_alias.return_value = "default"

        # 创建带 scope 的数据
        TaskflowStatistics.objects.create(
            task_id=100,
            instance_id="instance_100",
            space_id=1,
            scope_type="biz",
            scope_value="2",
            create_time=timezone.now(),
            is_finished=True,
            is_success=True,
        )

        view = SpaceStatisticsViewSet.as_view({"get": "overview"})
        request = self.factory.get(
            "/api/statistics/space/overview/", {"space_id": 1, "scope_type": "biz", "scope_value": "2"}
        )
        force_authenticate(request, user=self.user)

        response = view(request)
        assert response.status_code == 200

    @patch("bkflow.statistics.conf.StatisticsConfig.get_db_alias")
    def test_plugin_ranking_order_by(self, mock_db_alias):
        """测试插件排行排序"""
        mock_db_alias.return_value = "default"

        view = SpaceStatisticsViewSet.as_view({"get": "plugin_ranking"})

        # 按执行次数排序
        request = self.factory.get(
            "/api/statistics/space/plugin-ranking/", {"space_id": 1, "order_by": "execution_count"}
        )
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200

        # 按成功率排序
        request = self.factory.get("/api/statistics/space/plugin-ranking/", {"space_id": 1, "order_by": "success_rate"})
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
