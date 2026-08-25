from unittest.mock import MagicMock, patch

from django.test import TestCase
from pydantic import ValidationError


def _get_models():
    from bkflow.pipeline_converter.converters.a2flow_v2.data_models import (
        A2FlowCondition,
        A2FlowNode,
        A2FlowPipeline,
        A2FlowVariable,
    )

    return A2FlowNode, A2FlowPipeline, A2FlowVariable, A2FlowCondition


class TestA2FlowNode(TestCase):
    """a2flow v2 节点 DataModel 测试"""

    def test_activity_defaults_type(self):
        """缺省 type 应为 Activity"""
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="测试", code="sleep_timer", next="n2")
        self.assertEqual(node.type, "Activity")

    def test_activity_explicit_type(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="测试", type="Activity", code="sleep_timer", next="n2")
        self.assertEqual(node.type, "Activity")

    def test_gateway_type(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="pg1", name="并行", type="ParallelGateway", next=["n1", "n2"])
        self.assertEqual(node.type, "ParallelGateway")
        self.assertEqual(node.next, ["n1", "n2"])

    def test_start_event(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="start", name="开始", type="StartEvent", next="n1")
        self.assertEqual(node.type, "StartEvent")

    def test_end_event(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="end", name="结束", type="EndEvent")
        self.assertIsNone(node.next)

    def test_exclusive_gateway_with_conditions(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(
            id="eg1",
            name="判断",
            type="ExclusiveGateway",
            next=["n1", "n2"],
            conditions=[{"evaluate": "${x} > 0"}, {"evaluate": "${x} <= 0"}],
            default_next="n2",
        )
        self.assertEqual(len(node.conditions), 2)
        self.assertEqual(node.default_next, "n2")

    def test_activity_with_plugin_type(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="远程插件", code="my_plugin", plugin_type="remote_plugin", next="n2")
        self.assertEqual(node.plugin_type, "remote_plugin")

    def test_activity_allows_missing_next_for_late_converter_validation(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="测试", code="sleep_timer")
        self.assertIsNone(node.next)

    def test_node_id_required(self):
        A2FlowNode, *_ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowNode(name="无ID")

    def test_node_data_defaults_empty(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="测试", code="sleep_timer", next="n2")
        self.assertEqual(node.data, {})


class TestA2FlowVariable(TestCase):
    """a2flow v2 变量 DataModel 测试"""

    def test_variable_defaults(self):
        _, A2FlowPipeline, A2FlowVariable, _ = _get_models()
        var = A2FlowVariable(key="${ip}")
        self.assertEqual(var.name, "")
        self.assertEqual(var.value, "")
        self.assertEqual(var.source_type, "custom")
        self.assertEqual(var.custom_type, "input")
        self.assertEqual(var.show_type, "show")

    def test_variable_key_required(self):
        _, _, A2FlowVariable, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowVariable()


class TestA2FlowPipeline(TestCase):
    """a2flow v2 顶层结构测试"""

    def test_minimal_pipeline(self):
        _, A2FlowPipeline, _, _ = _get_models()
        pipeline = A2FlowPipeline(
            name="简单流程",
            nodes=[{"id": "n1", "name": "步骤1", "code": "sleep_timer", "next": "end"}],
        )
        self.assertEqual(pipeline.version, "2.0")
        self.assertEqual(len(pipeline.nodes), 1)
        self.assertEqual(pipeline.variables, [])

    def test_pipeline_name_required(self):
        _, A2FlowPipeline, _, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowPipeline(nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}])

    def test_pipeline_nodes_required(self):
        _, A2FlowPipeline, _, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowPipeline(name="空流程")

    def test_pipeline_empty_nodes_rejected(self):
        _, A2FlowPipeline, _, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowPipeline(name="空流程", nodes=[])

    def test_pipeline_version_default(self):
        _, A2FlowPipeline, _, _ = _get_models()
        pipeline = A2FlowPipeline(name="测试", nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}])
        self.assertEqual(pipeline.version, "2.0")

    def _mock_variable_model(self, valid_codes):
        """mock VariableModel.objects.all().only('code') 返回内存假集合，
        使基于 VariableModel 的 custom_type 校验在单测空库下可稳定运行（保留原始校验语义）。"""
        fake_rows = [MagicMock(code=code) for code in valid_codes]
        mock_qs = MagicMock()
        mock_qs.only.return_value = fake_rows
        mock_objects = MagicMock()
        mock_objects.all.return_value = mock_qs
        return patch(
            "bkflow.pipeline_converter.converters.a2flow_v2.data_models.VariableModel.objects",
            mock_objects,
        )

    def test_pipeline_with_variables(self):
        _, A2FlowPipeline, _, _ = _get_models()
        with self._mock_variable_model(["input", "textarea", "datetime"]):
            pipeline = A2FlowPipeline(
                name="带变量",
                nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}],
                variables=[{"key": "${ip}", "name": "IP地址"}],
            )
        self.assertEqual(len(pipeline.variables), 1)
        self.assertEqual(pipeline.variables[0].key, "${ip}")

    def test_pipeline_rejects_invalid_variable_custom_type(self):
        """非法 custom_type 应在 Pipeline 级别被一次性校验拒绝"""
        _, A2FlowPipeline, _, _ = _get_models()
        with self._mock_variable_model(["input", "textarea", "datetime"]):
            with self.assertRaises(ValidationError):
                A2FlowPipeline(
                    name="非法变量类型",
                    nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}],
                    variables=[{"key": "${ip}", "custom_type": "not_exist_type"}],
                )

    def test_pipeline_accepts_valid_variable_custom_type(self):
        """合法的 custom_type 应通过校验"""
        _, A2FlowPipeline, _, _ = _get_models()
        with self._mock_variable_model(["input", "textarea", "datetime"]):
            pipeline = A2FlowPipeline(
                name="合法变量类型",
                nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}],
                variables=[{"key": "${ip}", "custom_type": "input"}],
            )
        self.assertEqual(pipeline.variables[0].custom_type, "input")

    def test_pipeline_variable_custom_type_non_string_rejected(self):
        """custom_type 为非字符串类型（如数字）时应被校验拒绝"""
        _, A2FlowPipeline, _, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowPipeline(
                name="非法变量类型",
                nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}],
                variables=[{"key": "${ip}", "custom_type": 123}],
            )

    def test_pipeline_variable_custom_type_empty_string_allowed(self):
        """custom_type 为空串时合法（下游 classify_constants 对空串有特殊处理）"""
        _, A2FlowPipeline, _, _ = _get_models()
        pipeline = A2FlowPipeline(
            name="空串变量类型",
            nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}],
            variables=[{"key": "${ip}", "custom_type": ""}],
        )
        self.assertEqual(pipeline.variables[0].custom_type, "")
