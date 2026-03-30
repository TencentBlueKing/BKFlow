from unittest.mock import MagicMock

from bkflow.statistics.db_router import StatisticsDBRouter


class TestStatisticsDBRouter:
    def setup_method(self):
        self.router = StatisticsDBRouter()

    def test_db_for_read_statistics_model_fallback(self):
        from bkflow.statistics.models import TaskflowStatistics

        result = self.router.db_for_read(TaskflowStatistics)
        assert result == "default"

    def test_db_for_write_statistics_model_fallback(self):
        from bkflow.statistics.models import TaskflowStatistics

        result = self.router.db_for_write(TaskflowStatistics)
        assert result == "default"

    def test_db_for_read_non_statistics_model(self):
        non_stat_model = MagicMock()
        non_stat_model._meta.app_label = "task"
        result = self.router.db_for_read(non_stat_model)
        assert result is None

    def test_allow_relation_both_statistics(self):
        obj1 = MagicMock()
        obj1._meta.app_label = "statistics"
        obj2 = MagicMock()
        obj2._meta.app_label = "statistics"
        assert self.router.allow_relation(obj1, obj2) is True

    def test_allow_relation_mixed(self):
        obj1 = MagicMock()
        obj1._meta.app_label = "statistics"
        obj2 = MagicMock()
        obj2._meta.app_label = "task"
        assert self.router.allow_relation(obj1, obj2) is False

    def test_allow_migrate_statistics_to_default(self):
        assert self.router.allow_migrate("default", "statistics") is True

    def test_allow_migrate_other_app_not_to_statistics(self):
        assert self.router.allow_migrate("statistics", "task") is False
