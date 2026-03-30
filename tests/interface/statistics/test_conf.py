from unittest.mock import patch

from bkflow.statistics.conf import StatisticsSettings


class TestStatisticsSettings:
    def test_is_enabled_default(self):
        assert StatisticsSettings.is_enabled() is True

    @patch("bkflow.statistics.conf.env")
    def test_is_enabled_false(self, mock_env):
        mock_env.STATISTICS_ENABLED = False
        assert StatisticsSettings.is_enabled() is False

    def test_get_db_alias_default(self):
        assert StatisticsSettings.get_db_alias() == "default"

    @patch("bkflow.statistics.conf.env")
    def test_should_collect_template_stats_interface(self, mock_env):
        mock_env.STATISTICS_ENABLED = True
        mock_env.BKFLOW_MODULE_TYPE = "interface"
        assert StatisticsSettings.should_collect_template_stats() is True

    @patch("bkflow.statistics.conf.env")
    def test_should_collect_task_stats_engine(self, mock_env):
        mock_env.STATISTICS_ENABLED = True
        mock_env.BKFLOW_MODULE_TYPE = "engine"
        assert StatisticsSettings.should_collect_task_stats() is True

    @patch("bkflow.statistics.conf.env")
    def test_should_collect_task_stats_interface(self, mock_env):
        mock_env.STATISTICS_ENABLED = True
        mock_env.BKFLOW_MODULE_TYPE = "interface"
        assert StatisticsSettings.should_collect_task_stats() is False

    def test_get_detail_retention_days_default(self):
        assert StatisticsSettings.get_detail_retention_days() == 90

    def test_get_summary_retention_days_default(self):
        assert StatisticsSettings.get_summary_retention_days() == 365

    @patch("bkflow.statistics.conf.env")
    def test_include_mock_tasks_default(self, mock_env):
        mock_env.STATISTICS_INCLUDE_MOCK = False
        assert StatisticsSettings.include_mock_tasks() is False

    @patch("bkflow.statistics.conf.env")
    def test_get_engine_id_default(self, mock_env):
        mock_env.BKFLOW_MODULE_CODE = "default"
        result = StatisticsSettings.get_engine_id()
        assert isinstance(result, str)
        assert len(result) > 0
