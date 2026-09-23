from django.test import TestCase


class TestBuildParallelGateway(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import (
            build_gateway,
        )

        return build_gateway

    def test_parallel_gateway(self):
        build = self._get_builder()
        result = build(
            node_id="pg1",
            name="并行",
            node_type="ParallelGateway",
            incoming=["f_in"],
            outgoing=["f_out1", "f_out2"],
            converge_gateway_id="cg1",
        )
        self.assertEqual(result["id"], "pg1")
        self.assertEqual(result["type"], "ParallelGateway")
        self.assertEqual(result["outgoing"], ["f_out1", "f_out2"])
        self.assertEqual(result["converge_gateway_id"], "cg1")
        self.assertNotIn("conditions", result)


class TestBuildExclusiveGateway(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import (
            build_gateway,
        )

        return build_gateway

    def test_exclusive_gateway_with_conditions(self):
        build = self._get_builder()
        result = build(
            node_id="eg1",
            name="判断",
            node_type="ExclusiveGateway",
            incoming=["f_in"],
            outgoing=["f_out1", "f_out2"],
            conditions=[{"evaluate": "${x} > 0"}, {"evaluate": "${x} <= 0"}],
            default_next_flow_id="f_out2",
        )
        self.assertEqual(result["type"], "ExclusiveGateway")
        self.assertIn("f_out1", result["conditions"])
        self.assertIn("f_out2", result["conditions"])
        self.assertEqual(result["conditions"]["f_out1"]["evaluate"], "${x} > 0")
        self.assertEqual(result["default_condition"]["flow_id"], "f_out2")

    def test_exclusive_gateway_no_default(self):
        build = self._get_builder()
        result = build(
            node_id="eg2",
            name="判断",
            node_type="ExclusiveGateway",
            incoming=["f_in"],
            outgoing=["f_out1", "f_out2"],
            conditions=[{"evaluate": "${x} > 0"}, {"evaluate": "${x} <= 0"}],
        )
        self.assertEqual(result["default_condition"], {})


class TestBuildConditionalParallelGateway(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import (
            build_gateway,
        )

        return build_gateway

    def test_conditional_parallel_with_conditions(self):
        build = self._get_builder()
        result = build(
            node_id="cpg1",
            name="条件并行",
            node_type="ConditionalParallelGateway",
            incoming=["f_in"],
            outgoing=["f_out1", "f_out2"],
            conditions=[{"evaluate": "${env} == 'prod'"}, {"evaluate": "${env} == 'test'"}],
            converge_gateway_id="cg1",
        )
        self.assertEqual(result["type"], "ConditionalParallelGateway")
        self.assertIn("conditions", result)
        self.assertEqual(result["converge_gateway_id"], "cg1")


class TestBuildConvergeGateway(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import (
            build_gateway,
        )

        return build_gateway

    def test_converge_gateway(self):
        build = self._get_builder()
        result = build(node_id="cg1", name="汇聚", node_type="ConvergeGateway", incoming=["f1", "f2"], outgoing=["f_out"])
        self.assertEqual(result["type"], "ConvergeGateway")
        self.assertEqual(result["outgoing"], "f_out")
        self.assertNotIn("conditions", result)
