from django.test import TestCase


class TestBuildStartEvent(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.node_builder import (
            build_start_event,
        )

        return build_start_event

    def test_start_event_structure(self):
        build = self._get_builder()
        result = build(node_id="n_start_001", name="开始", outgoing="flow_001")
        self.assertEqual(result["id"], "n_start_001")
        self.assertEqual(result["type"], "EmptyStartEvent")
        self.assertEqual(result["incoming"], "")
        self.assertEqual(result["outgoing"], "flow_001")
        self.assertEqual(result["labels"], [])

    def test_start_event_default_name(self):
        build = self._get_builder()
        result = build(node_id="n_start_001", name="", outgoing="flow_001")
        self.assertEqual(result["name"], "")


class TestBuildEndEvent(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.node_builder import (
            build_end_event,
        )

        return build_end_event

    def test_end_event_structure(self):
        build = self._get_builder()
        result = build(node_id="n_end_001", name="结束", incoming=["flow_001", "flow_002"])
        self.assertEqual(result["id"], "n_end_001")
        self.assertEqual(result["type"], "EmptyEndEvent")
        self.assertEqual(result["incoming"], ["flow_001", "flow_002"])
        self.assertEqual(result["outgoing"], "")


class TestBuildActivity(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.node_builder import (
            build_activity,
        )

        return build_activity

    def test_builtin_activity(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import (
            ResolvedPlugin,
        )

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="component", original_code="sleep_timer", wrapper_code="sleep_timer", wrapper_version="v1.0.0"
        )
        result = build(
            node_id="n001",
            name="等待",
            data={"bk_timing": 5},
            plugin=plugin,
            incoming=["flow_in"],
            outgoing="flow_out",
            stage_name="等待阶段",
        )
        self.assertEqual(result["id"], "n001")
        self.assertEqual(result["type"], "ServiceActivity")
        self.assertEqual(result["component"]["code"], "sleep_timer")
        self.assertEqual(result["component"]["version"], "v1.0.0")
        self.assertEqual(result["component"]["data"]["bk_timing"]["value"], 5)
        self.assertEqual(result["component"]["data"]["bk_timing"]["hook"], False)
        self.assertEqual(result["stage_name"], "等待阶段")
        self.assertTrue(result["retryable"])
        self.assertTrue(result["skippable"])

    def test_remote_plugin_activity(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import (
            ResolvedPlugin,
        )

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="remote_plugin",
            original_code="my_bk_plugin",
            wrapper_code="remote_plugin",
            wrapper_version="1.0.0",
            remote_plugin_version="1.2.3",
        )
        result = build(
            node_id="n002",
            name="远程",
            data={"param1": "hello"},
            plugin=plugin,
            incoming=["flow_in"],
            outgoing="flow_out",
        )
        comp = result["component"]
        self.assertEqual(comp["code"], "remote_plugin")
        self.assertEqual(comp["version"], "1.0.0")
        self.assertEqual(comp["data"]["plugin_code"]["value"], "my_bk_plugin")
        self.assertEqual(comp["data"]["plugin_version"]["value"], "1.2.3")
        self.assertEqual(comp["data"]["param1"]["value"], "hello")

    def test_uniform_api_activity(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import (
            ResolvedPlugin,
        )

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="uniform_api",
            original_code="my_api",
            wrapper_code="uniform_api",
            wrapper_version="v3.0.0",
            api_meta={
                "id": "my_api",
                "name": "测试API",
                "category": {},
                "meta_url": "http://example.com/meta",
                "url": "http://example.com/run",
                "methods": ["POST"],
                "api_key": "default",
            },
        )
        result = build(
            node_id="n003", name="API调用", data={"biz_id": 123}, plugin=plugin, incoming=["flow_in"], outgoing="flow_out"
        )
        comp = result["component"]
        self.assertEqual(comp["code"], "uniform_api")
        self.assertEqual(comp["version"], "v3.0.0")
        self.assertEqual(comp["api_meta"]["id"], "my_api")
        self.assertIn("meta_url", comp["api_meta"])

    def test_data_wrapping_preserves_pre_wrapped(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import (
            ResolvedPlugin,
        )

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="component", original_code="test", wrapper_code="test", wrapper_version="v1.0.0"
        )
        result = build(
            node_id="n004",
            name="测试",
            data={"already_wrapped": {"hook": True, "value": "ref"}},
            plugin=plugin,
            incoming=["f1"],
            outgoing="f2",
        )
        self.assertEqual(result["component"]["data"]["already_wrapped"]["hook"], True)
        self.assertEqual(result["component"]["data"]["already_wrapped"]["value"], "ref")

    def test_stage_name_defaults_to_name(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import (
            ResolvedPlugin,
        )

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="component", original_code="test", wrapper_code="test", wrapper_version="v1.0.0"
        )
        result = build(node_id="n005", name="节点名", data={}, plugin=plugin, incoming=["f1"], outgoing="f2")
        self.assertEqual(result["stage_name"], "节点名")
