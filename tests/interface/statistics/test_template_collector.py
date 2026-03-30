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
                        "data": {
                            "plugin_code": {"hook": False, "value": "my_plugin"},
                            "plugin_version": {"hook": False, "value": "1.0.0"},
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
        remote_node = TemplateNodeStatistics.objects.get(template_id=1, plugin_type="remote_plugin")
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

    @patch(
        "bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
        new_callable=PropertyMock,
    )
    def test_collect_remote_plugin_with_data_field(self, mock_template_prop):
        """验证 remote_plugin 从 component.data 中提取实际插件编码

        pipeline_tree 中 component 的参数存放在 data 字段而非 inputs。
        """
        mock = self._make_mock_template()
        mock.pipeline_tree = {
            "activities": {
                "node1": {
                    "type": "ServiceActivity",
                    "name": "标准运维流程执行",
                    "component": {
                        "code": "remote_plugin",
                        "data": {
                            "plugin_code": {"hook": False, "value": "bk-sops-plugin"},
                            "plugin_version": {"hook": False, "value": "1.0.0"},
                        },
                        "version": "1.0.0",
                    },
                },
            },
            "gateways": {},
        }
        mock_template_prop.return_value = mock
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        collector.collect()

        node = TemplateNodeStatistics.objects.get(template_id=1, plugin_type="remote_plugin")
        assert node.component_code == "bk-sops-plugin", f"Expected 'bk-sops-plugin', got '{node.component_code}'"
        assert node.version == "1.0.0"

    @patch(
        "bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
        new_callable=PropertyMock,
    )
    def test_collect_uniform_api_with_api_meta(self, mock_template_prop):
        """验证 uniform_api 从 api_meta.id 提取插件编码，从 api_meta.name 提取名称"""
        mock = self._make_mock_template()
        mock.pipeline_tree = {
            "activities": {
                "node1": {
                    "type": "ServiceActivity",
                    "name": "调用标准运维API",
                    "component": {
                        "code": "uniform_api",
                        "version": "v2.0.0",
                        "data": {
                            "uniform_api_plugin_url": {"hook": False, "value": "http://example.com/api"},
                            "uniform_api_plugin_method": {"hook": False, "value": "POST"},
                        },
                        "api_meta": {
                            "id": "sops_execute",
                            "name": "流程执行",
                            "meta_url": "http://example.com/meta",
                            "api_key": "sops_key",
                            "category": {"id": "cat_1", "name": "标准运维"},
                        },
                    },
                },
            },
            "gateways": {},
        }
        mock_template_prop.return_value = mock
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        collector.collect()

        node = TemplateNodeStatistics.objects.get(template_id=1)
        assert node.component_code == "sops_execute", f"Expected 'sops_execute', got '{node.component_code}'"
        assert node.component_name == "标准运维-流程执行"
        assert node.plugin_type == "uniform_api"
