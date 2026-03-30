from bkflow.statistics.serializers import (
    DateRangeParamSerializer,
    FailureAnalysisSerializer,
    PluginRankingSerializer,
    SpaceRankingSerializer,
    StatisticsOverviewSerializer,
    TaskTrendSerializer,
    TemplateRankingSerializer,
)


class TestStatisticsOverviewSerializer:
    def test_valid_data(self):
        data = {
            "total_templates": 100,
            "total_tasks": 500,
            "total_tasks_finished": 450,
            "total_tasks_failed": 50,
            "total_nodes_executed": 5000,
            "avg_task_elapsed_time": 120.5,
            "success_rate": 0.9,
        }
        s = StatisticsOverviewSerializer(data=data)
        assert s.is_valid(), s.errors


class TestTaskTrendSerializer:
    def test_valid_data(self):
        data = {
            "date": "2026-01-01",
            "task_created_count": 10,
            "task_finished_count": 8,
            "task_success_count": 7,
            "task_failed_count": 1,
            "task_revoked_count": 0,
            "node_executed_count": 100,
            "avg_task_elapsed_time": 60.0,
        }
        s = TaskTrendSerializer(data=data)
        assert s.is_valid(), s.errors


class TestPluginRankingSerializer:
    def test_valid_data(self):
        data = {
            "component_code": "bk_http",
            "version": "v1",
            "plugin_type": "component",
            "execution_count": 100,
            "success_count": 95,
            "failed_count": 5,
            "success_rate": 0.95,
            "avg_elapsed_time": 3.5,
        }
        s = PluginRankingSerializer(data=data)
        assert s.is_valid(), s.errors


class TestTemplateRankingSerializer:
    def test_valid_data(self):
        data = {
            "template_id": 1,
            "template_name": "My Template",
            "space_id": 100,
            "task_count": 50,
            "task_success_count": 45,
            "task_failed_count": 5,
        }
        s = TemplateRankingSerializer(data=data)
        assert s.is_valid(), s.errors


class TestSpaceRankingSerializer:
    def test_valid_data(self):
        data = {
            "space_id": 100,
            "scope_type": "project",
            "scope_value": "proj_1",
            "total_templates": 20,
            "total_tasks": 200,
            "total_nodes_executed": 2000,
            "success_rate": 0.85,
        }
        s = SpaceRankingSerializer(data=data)
        assert s.is_valid(), s.errors


class TestFailureAnalysisSerializer:
    def test_valid_data(self):
        data = {
            "component_code": "bk_http",
            "version": "v1",
            "plugin_type": "component",
            "failed_count": 10,
            "total_count": 100,
            "failure_rate": 0.1,
            "avg_elapsed_time": 5.0,
        }
        s = FailureAnalysisSerializer(data=data)
        assert s.is_valid(), s.errors


class TestDateRangeParamSerializer:
    def test_date_range_shortcut(self):
        s = DateRangeParamSerializer(data={"date_range": "7d"})
        assert s.is_valid(), s.errors

    def test_explicit_dates(self):
        s = DateRangeParamSerializer(data={"date_start": "2026-01-01", "date_end": "2026-01-31"})
        assert s.is_valid(), s.errors

    def test_no_params_invalid(self):
        s = DateRangeParamSerializer(data={})
        assert not s.is_valid()
