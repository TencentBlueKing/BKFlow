from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.collectors.template_collector import TemplateStatisticsCollector
from bkflow.statistics.models import TemplateNodeStatistics, TemplateStatistics


class TestTemplateStatisticsCollector(TestCase):
    def _make_mock_template(self, template_id=1):
        mock = MagicMock()
        mock.id = template_id
        mock.space_id = 100
        mock.scope_type = "project"
        mock.scope_value = "proj_1"
        mock.name = "test_template"
        mock.creator = "admin"
        mock.is_enabled = True
        mock.create_at = timezone.now()
        mock.update_at = timezone.now()
        mock.snapshot_id = 10
        mock.pipeline_tree = {
            "activities": {
                "act1": {
                    "type": "ServiceActivity",
                    "name": "HTTP请求",
                    "component": {"code": "bk_http_request", "version": "v1.0"},
                },
                "act2": {
                    "type": "ServiceActivity",
                    "name": "远程插件",
                    "component": {
                        "code": "remote_plugin",
                        "version": "legacy",
                        "inputs": {
                            "plugin_code": {"value": "my_plugin"},
                            "plugin_version": {"value": "1.0.0"},
                        },
                    },
                },
            },
            "gateways": {"gw1": {}},
        }
        return mock

    @patch(
        "bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
        new_callable=PropertyMock,
    )
    def test_collect_creates_template_statistics(self, mock_template_prop):
        mock_template_prop.return_value = self._make_mock_template()
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        result = collector.collect()
        assert result is True
        assert TemplateStatistics.objects.filter(template_id=1).exists()
        stat = TemplateStatistics.objects.get(template_id=1)
        assert stat.atom_total == 2
        assert stat.gateways_total == 1

    @patch(
        "bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
        new_callable=PropertyMock,
    )
    def test_collect_creates_node_statistics(self, mock_template_prop):
        mock_template_prop.return_value = self._make_mock_template()
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        collector.collect()
        nodes = TemplateNodeStatistics.objects.filter(template_id=1)
        assert nodes.count() == 2
        codes = set(nodes.values_list("component_code", flat=True))
        assert "bk_http_request" in codes
        assert "my_plugin" in codes

    @patch(
        "bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
        new_callable=PropertyMock,
    )
    def test_collect_remote_plugin_extraction(self, mock_template_prop):
        mock_template_prop.return_value = self._make_mock_template()
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        collector.collect()
        remote_node = TemplateNodeStatistics.objects.get(template_id=1, is_remote=True)
        assert remote_node.component_code == "my_plugin"
        assert remote_node.version == "1.0.0"

    @patch(
        "bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
        new_callable=PropertyMock,
    )
    def test_collect_idempotent(self, mock_template_prop):
        mock_template_prop.return_value = self._make_mock_template()
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        collector.collect()
        collector.collect()
        assert TemplateStatistics.objects.filter(template_id=1).count() == 1
        assert TemplateNodeStatistics.objects.filter(template_id=1).count() == 2

    @patch(
        "bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
        new_callable=PropertyMock,
    )
    def test_collect_returns_false_when_template_not_found(self, mock_template_prop):
        mock_template_prop.return_value = None
        collector = TemplateStatisticsCollector(template_id=999, snapshot_id=10)
        result = collector.collect()
        assert result is False
