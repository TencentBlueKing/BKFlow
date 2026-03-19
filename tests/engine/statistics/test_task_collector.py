from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.collectors.task_collector import TaskStatisticsCollector
from bkflow.statistics.models import TaskflowStatistics


class TestTaskStatisticsCollector(TestCase):
    def _make_mock_task(self, task_id=1, create_method="API"):
        mock = MagicMock()
        mock.id = task_id
        mock.instance_id = "inst_001"
        mock.template_id = 10
        mock.space_id = 100
        mock.scope_type = "project"
        mock.scope_value = "proj_1"
        mock.creator = "admin"
        mock.executor = "admin"
        mock.create_time = timezone.now()
        mock.start_time = None
        mock.finish_time = None
        mock.is_started = False
        mock.is_finished = False
        mock.is_revoked = False
        mock.create_method = create_method
        mock.trigger_method = "manual"
        mock.execution_data = {
            "activities": {
                "act1": {
                    "type": "ServiceActivity",
                    "id": "act1",
                    "name": "HTTP",
                    "component": {"code": "bk_http", "version": "v1"},
                },
            },
            "gateways": {},
        }
        return mock

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_on_create(self, mock_task_prop):
        mock_task_prop.return_value = self._make_mock_task()
        collector = TaskStatisticsCollector(task_id=1)
        result = collector.collect_on_create()
        assert result is True
        assert TaskflowStatistics.objects.filter(task_id=1).exists()
        stat = TaskflowStatistics.objects.get(task_id=1)
        assert stat.final_state == "CREATED"
        assert stat.atom_total == 1

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_on_create_skips_mock(self, mock_task_prop):
        mock_task_prop.return_value = self._make_mock_task(create_method="MOCK")
        collector = TaskStatisticsCollector(task_id=1)
        result = collector.collect_on_create()
        assert result is False
        assert not TaskflowStatistics.objects.filter(task_id=1).exists()

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_on_create_returns_false_no_task(self, mock_task_prop):
        mock_task_prop.return_value = None
        collector = TaskStatisticsCollector(task_id=999)
        result = collector.collect_on_create()
        assert result is False

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_collect_on_create_idempotent(self, mock_task_prop):
        mock_task_prop.return_value = self._make_mock_task()
        collector = TaskStatisticsCollector(task_id=1)
        collector.collect_on_create()
        collector.collect_on_create()
        assert TaskflowStatistics.objects.filter(task_id=1).count() == 1

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_update_task_statistics_finished(self, mock_task_prop):
        mock_task = self._make_mock_task()
        mock_task_prop.return_value = mock_task
        collector = TaskStatisticsCollector(task_id=1)
        collector.collect_on_create()

        now = timezone.now()
        mock_task.is_started = True
        mock_task.is_finished = True
        mock_task.is_revoked = False
        mock_task.start_time = now
        mock_task.finish_time = now
        collector._update_task_statistics()

        stat = TaskflowStatistics.objects.get(task_id=1)
        assert stat.final_state == "FINISHED"
        assert stat.is_finished is True

    @patch("bkflow.statistics.collectors.task_collector.TaskStatisticsCollector.task", new_callable=PropertyMock)
    def test_update_task_statistics_revoked(self, mock_task_prop):
        mock_task = self._make_mock_task()
        mock_task_prop.return_value = mock_task
        collector = TaskStatisticsCollector(task_id=1)
        collector.collect_on_create()

        mock_task.is_started = True
        mock_task.is_finished = False
        mock_task.is_revoked = True
        mock_task.start_time = timezone.now()
        mock_task.finish_time = timezone.now()
        collector._update_task_statistics()

        stat = TaskflowStatistics.objects.get(task_id=1)
        assert stat.final_state == "REVOKED"
