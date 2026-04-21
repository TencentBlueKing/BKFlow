from django.test import TestCase

from bkflow.statistics.collectors.base import BaseStatisticsCollector, ComponentInfo
from bkflow.statistics.models import PluginType


class TestResolveComponentInfo(TestCase):
    """验证 resolve_component_info 对各类 component 的解析"""

    def test_regular_component(self):
        component = {"code": "bk_http_request", "version": "v1.0"}
        info = BaseStatisticsCollector.resolve_component_info(component)
        assert info == ComponentInfo(
            code="bk_http_request",
            name="",
            version="v1.0",
            plugin_type=PluginType.COMPONENT,
            plugin_source="",
        )

    def test_remote_plugin_with_data(self):
        component = {
            "code": "remote_plugin",
            "version": "1.0.0",
            "data": {
                "plugin_code": {"hook": False, "value": "bk-sops-plugin"},
                "plugin_version": {"hook": False, "value": "2.0.0"},
                "plugin_name": {"hook": False, "value": "标准运维插件"},
            },
        }
        info = BaseStatisticsCollector.resolve_component_info(component)
        assert info.code == "bk-sops-plugin"
        assert info.name == "标准运维插件"
        assert info.version == "2.0.0"
        assert info.plugin_type == PluginType.REMOTE_PLUGIN
        assert info.plugin_source == ""

    def test_remote_plugin_without_name(self):
        component = {
            "code": "remote_plugin",
            "data": {
                "plugin_code": {"hook": False, "value": "my-plugin"},
                "plugin_version": {"hook": False, "value": "1.0"},
            },
        }
        info = BaseStatisticsCollector.resolve_component_info(component)
        assert info.code == "my-plugin"
        assert info.name == ""
        assert info.plugin_type == PluginType.REMOTE_PLUGIN
        assert info.plugin_source == ""

    def test_remote_plugin_with_inputs_fallback(self):
        component = {
            "code": "remote_plugin",
            "inputs": {
                "plugin_code": {"value": "legacy-plugin"},
                "plugin_version": {"value": "0.1"},
            },
        }
        info = BaseStatisticsCollector.resolve_component_info(component)
        assert info.code == "legacy-plugin"
        assert info.version == "0.1"
        assert info.plugin_type == PluginType.REMOTE_PLUGIN
        assert info.plugin_source == ""

    def test_uniform_api_with_api_meta(self):
        component = {
            "code": "uniform_api",
            "version": "v2.0.0",
            "data": {
                "uniform_api_plugin_url": {"hook": False, "value": "http://example.com/api"},
            },
            "api_meta": {
                "id": "sops_api_001",
                "name": "流程执行",
                "meta_url": "http://example.com/meta",
                "api_key": "sops_execute",
                "plugin_source": "builtin",
                "category": {"id": "cat_1", "name": "标准运维"},
            },
        }
        info = BaseStatisticsCollector.resolve_component_info(component)
        assert info.code == "sops_api_001"
        assert info.name == "标准运维-流程执行"
        assert info.version == "v2.0.0"
        assert info.plugin_type == PluginType.UNIFORM_API
        assert info.plugin_source == "builtin"

    def test_uniform_api_without_api_meta(self):
        """旧版 uniform_api 没有 api_meta，保持原始 code"""
        component = {
            "code": "uniform_api",
            "version": "v1.0.0",
            "data": {
                "api_config": {"hook": False, "value": {}},
            },
        }
        info = BaseStatisticsCollector.resolve_component_info(component)
        assert info.code == "uniform_api"
        assert info.name == ""
        assert info.plugin_type == PluginType.UNIFORM_API
        assert info.plugin_source == ""

    def test_uniform_api_with_api_meta_no_category(self):
        component = {
            "code": "uniform_api",
            "version": "v2.0.0",
            "api_meta": {"id": "my_api", "name": "我的API"},
        }
        info = BaseStatisticsCollector.resolve_component_info(component)
        assert info.code == "my_api"
        assert info.name == "我的API"
        assert info.plugin_source == ""

    def test_empty_component(self):
        info = BaseStatisticsCollector.resolve_component_info({})
        assert info.code == ""
        assert info.name == ""
        assert info.version == "legacy"
        assert info.plugin_type == PluginType.COMPONENT
        assert info.plugin_source == ""
