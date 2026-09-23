from django.test import TestCase


class TestBuildConstant(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.variable_builder import (
            build_constant,
        )

        return build_constant

    def test_basic_constant(self):
        build = self._get_builder()
        from bkflow.pipeline_converter.converters.a2flow_v2.data_models import (
            A2FlowVariable,
        )

        var = A2FlowVariable(key="${ip}", name="服务器IP", value="10.0.0.1", description="目标机器")
        result = build(var, index=0)
        self.assertEqual(result["key"], "${ip}")
        self.assertEqual(result["name"], "服务器IP")
        self.assertEqual(result["value"], "10.0.0.1")
        self.assertEqual(result["desc"], "目标机器")
        self.assertEqual(result["custom_type"], "input")
        self.assertEqual(result["source_type"], "custom")
        self.assertEqual(result["show_type"], "show")
        self.assertEqual(result["index"], 0)
        self.assertFalse(result["hook"])
        self.assertTrue(result["need_render"])

    def test_hidden_variable(self):
        build = self._get_builder()
        from bkflow.pipeline_converter.converters.a2flow_v2.data_models import (
            A2FlowVariable,
        )

        var = A2FlowVariable(key="${secret}", show_type="hide", value="token123")
        result = build(var, index=1)
        self.assertEqual(result["show_type"], "hide")
        self.assertEqual(result["index"], 1)

    def test_defaults(self):
        build = self._get_builder()
        from bkflow.pipeline_converter.converters.a2flow_v2.data_models import (
            A2FlowVariable,
        )

        var = A2FlowVariable(key="${x}")
        result = build(var, index=0)
        self.assertEqual(result["name"], "")
        self.assertEqual(result["value"], "")
        self.assertEqual(result["desc"], "")
