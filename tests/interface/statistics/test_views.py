from datetime import date, timedelta

from blueapps.account.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateStatistics,
)
from bkflow.statistics.views import SpaceStatisticsViewSet, SystemStatisticsViewSet


class TestSystemStatisticsViewSet(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view_set = SystemStatisticsViewSet
        self.admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )

        now = timezone.now()
        yesterday = date.today() - timedelta(days=1)

        TemplateStatistics.objects.create(template_id=1, space_id=100, template_name="t1")
        TemplateStatistics.objects.create(template_id=2, space_id=100, template_name="t2")

        TaskflowStatistics.objects.create(
            task_id=1,
            space_id=100,
            create_time=now,
            final_state="FINISHED",
            is_started=True,
            is_finished=True,
            elapsed_time=120,
        )
        TaskflowStatistics.objects.create(
            task_id=2,
            space_id=100,
            create_time=now,
            final_state="CREATED",
        )

        TaskflowExecutedNodeStatistics.objects.create(
            task_id=1,
            space_id=100,
            component_code="bk_http",
            node_id="n1",
            started_time=now,
            status=True,
            state="FINISHED",
        )

        DailyStatisticsSummary.objects.create(
            date=yesterday,
            space_id=100,
            task_created_count=5,
            task_finished_count=4,
            task_success_count=3,
            task_failed_count=1,
            task_revoked_count=0,
            node_executed_count=50,
            avg_task_elapsed_time=60.0,
        )

        PluginExecutionSummary.objects.create(
            period_type="day",
            period_start=yesterday,
            space_id=100,
            component_code="bk_http",
            version="v1",
            execution_count=100,
            success_count=90,
            failed_count=10,
            avg_elapsed_time=2.5,
        )

    def test_overview(self):
        request = self.factory.get("/api/statistics/system/overview/", {"date_range": "30d"})
        force_authenticate(request, user=self.admin_user)
        view = self.view_set.as_view({"get": "overview"})
        response = view(request)
        assert response.status_code == 200
        assert "total_templates" in response.data
        assert response.data["total_templates"] == 2

    def test_task_trend(self):
        request = self.factory.get("/api/statistics/system/task-trend/", {"date_range": "30d"})
        force_authenticate(request, user=self.admin_user)
        view = self.view_set.as_view({"get": "task_trend"})
        response = view(request)
        assert response.status_code == 200
        assert isinstance(response.data, list)

    def test_space_ranking(self):
        request = self.factory.get("/api/statistics/system/space-ranking/", {"date_range": "30d"})
        force_authenticate(request, user=self.admin_user)
        view = self.view_set.as_view({"get": "space_ranking"})
        response = view(request)
        assert response.status_code == 200

    def test_plugin_ranking(self):
        request = self.factory.get("/api/statistics/system/plugin-ranking/", {"date_range": "30d"})
        force_authenticate(request, user=self.admin_user)
        view = self.view_set.as_view({"get": "plugin_ranking"})
        response = view(request)
        assert response.status_code == 200

    def test_failure_analysis(self):
        request = self.factory.get("/api/statistics/system/failure-analysis/", {"date_range": "30d"})
        force_authenticate(request, user=self.admin_user)
        view = self.view_set.as_view({"get": "failure_analysis"})
        response = view(request)
        assert response.status_code == 200


class TestSpaceStatisticsViewSet(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view_set = SpaceStatisticsViewSet
        self.admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )

        now = timezone.now()
        yesterday = date.today() - timedelta(days=1)

        TemplateStatistics.objects.create(template_id=10, space_id=200, template_name="space_t1")

        TaskflowStatistics.objects.create(
            task_id=10,
            space_id=200,
            template_id=10,
            create_time=now,
            final_state="FINISHED",
            is_started=True,
            is_finished=True,
            elapsed_time=60,
        )

        DailyStatisticsSummary.objects.create(
            date=yesterday,
            space_id=200,
            task_created_count=3,
            task_finished_count=2,
            task_success_count=2,
            task_failed_count=0,
            task_revoked_count=0,
            node_executed_count=20,
        )

    def test_overview(self):
        request = self.factory.get("/api/statistics/spaces/200/overview/", {"date_range": "30d"})
        force_authenticate(request, user=self.admin_user)
        view = self.view_set.as_view({"get": "overview"})
        response = view(request, space_id="200")
        assert response.status_code == 200
        assert response.data["total_templates"] == 1

    def test_template_ranking(self):
        request = self.factory.get("/api/statistics/spaces/200/template-ranking/", {"date_range": "30d"})
        force_authenticate(request, user=self.admin_user)
        view = self.view_set.as_view({"get": "template_ranking"})
        response = view(request, space_id="200")
        assert response.status_code == 200

    def test_daily_summary(self):
        request = self.factory.get("/api/statistics/spaces/200/daily-summary/", {"date_range": "30d"})
        force_authenticate(request, user=self.admin_user)
        view = self.view_set.as_view({"get": "daily_summary"})
        response = view(request, space_id="200")
        assert response.status_code == 200
        assert isinstance(response.data, list)
