from collections import namedtuple
from unittest.mock import patch

from django.test import TestCase

MockComponent = namedtuple("MockComponent", ["code", "version"])


class TestPluginResolver(TestCase):
    """插件类型识别与包装测试"""

    def _get_resolver_class(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import (
            PluginResolver,
        )

        return PluginResolver

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_builtin_plugin(self, mock_cm, mock_safe_fetch_meta):
        """内置插件：code 在 ComponentModel 中找到"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0", "v2.0.0"]
        mock_safe_fetch_meta.return_value = None
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("sleep_timer", plugin_type_hint=None)
        self.assertEqual(result.plugin_type, "component")
        self.assertEqual(result.wrapper_code, "sleep_timer")
        self.assertEqual(result.wrapper_version, "v2.0.0")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_remote_plugin_version")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_bk_standard_plugin(self, mock_cm, mock_bkp, mock_fetch_version, mock_safe_fetch_meta):
        """蓝鲸标准插件：code 不在 ComponentModel，在 BKPlugin 中找到"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_bkp.objects.filter.return_value.exists.return_value = True
        mock_fetch_version.return_value = "1.2.3"
        mock_safe_fetch_meta.return_value = None
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("custom_bk_plugin", plugin_type_hint=None)
        self.assertEqual(result.plugin_type, "remote_plugin")
        self.assertEqual(result.wrapper_code, "remote_plugin")
        self.assertEqual(result.original_code, "custom_bk_plugin")
        self.assertEqual(result.remote_plugin_version, "1.2.3")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_uniform_api_with_explicit_type(self, mock_cm, mock_fetch_meta):
        """API 插件：显式指定 plugin_type"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v3.0.0"]
        mock_fetch_meta.return_value = {
            "id": "my_api_plugin",
            "name": "测试API",
            "category": {},
            "meta_url": "http://example.com/meta",
            "url": "http://example.com/run",
            "methods": ["POST"],
            "api_key": "default",
        }
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("my_api_plugin", plugin_type_hint="uniform_api")
        self.assertEqual(result.plugin_type, "uniform_api")
        self.assertEqual(result.wrapper_code, "uniform_api")
        self.assertEqual(result.original_code, "my_api_plugin")
        self.assertEqual(result.api_meta["id"], "my_api_plugin")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_with_explicit_component_type(self, mock_cm):
        """显式指定 plugin_type=component"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("sleep_timer", plugin_type_hint="component")
        self.assertEqual(result.plugin_type, "component")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_unknown_plugin(self, mock_cm, mock_bkp, mock_safe_fetch_meta):
        """未知 code 应报 UNKNOWN_PLUGIN_CODE"""
        from bkflow.pipeline_converter.exceptions import A2FlowConvertError

        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_bkp.objects.filter.return_value.exists.return_value = False
        mock_safe_fetch_meta.return_value = None
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        with self.assertRaises(A2FlowConvertError) as ctx:
            resolver.resolve("nonexistent_plugin", plugin_type_hint=None)
        self.assertEqual(ctx.exception.error_type, "UNKNOWN_PLUGIN_CODE")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_ambiguous_plugin(self, mock_cm, mock_bkp, mock_safe_fetch_meta):
        """code 同时在 ComponentModel 和 BKPlugin 中找到应报 AMBIGUOUS_PLUGIN_CODE"""
        from bkflow.pipeline_converter.exceptions import A2FlowConvertError

        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_bkp.objects.filter.return_value.exists.return_value = True
        mock_safe_fetch_meta.return_value = None
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        with self.assertRaises(A2FlowConvertError) as ctx:
            resolver.resolve("ambiguous_code", plugin_type_hint=None)
        self.assertEqual(ctx.exception.error_type, "AMBIGUOUS_PLUGIN_CODE")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_auto_resolve_uniform_api(self, mock_cm, mock_bkp, mock_fetch_meta):
        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_bkp.objects.filter.return_value.exists.return_value = False
        mock_fetch_meta.return_value = {
            "id": "my_api",
            "name": "测试API",
            "category": {},
            "meta_url": "http://example.com/meta",
            "url": "http://example.com/run",
            "methods": ["POST"],
            "api_key": "default",
        }
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("my_api", plugin_type_hint=None)
        self.assertEqual(result.plugin_type, "uniform_api")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_batch(self, mock_cm, mock_bkp, mock_safe_fetch, mock_fetch_meta):
        """批量解析多个 Activity 节点的插件"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_bkp.objects.filter.return_value.exists.return_value = False
        mock_safe_fetch.return_value = None
        mock_fetch_meta.return_value = {
            "id": "my_api",
            "name": "测试API",
            "category": {},
            "meta_url": "http://example.com/meta",
            "url": "http://example.com/run",
            "methods": ["POST"],
            "api_key": "default",
        }
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        nodes_info = [
            {"code": "sleep_timer", "plugin_type": None},
            {"code": "my_api", "plugin_type": "uniform_api"},
        ]
        results = resolver.resolve_batch(nodes_info)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[("sleep_timer", None)].plugin_type, "component")
        self.assertEqual(results[("my_api", "uniform_api")].plugin_type, "uniform_api")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_version_parsing_picks_latest(self, mock_cm):
        """版本选择应取语义化最新"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["legacy", "v1.0.0", "v2.1.0", "v2.0.0"]
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("test_code", plugin_type_hint="component")
        self.assertEqual(result.wrapper_version, "v2.1.0")
