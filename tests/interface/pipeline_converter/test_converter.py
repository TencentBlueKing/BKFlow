"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

COMPONENT_PATCH = "bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel"
BKPLUGIN_PATCH = "bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin"


def _mock_component_model(mock_cm, codes_versions=None):
    """Helper: ComponentModel mock that returns versions for given codes."""
    codes_versions = codes_versions or {}

    def filter_side_effect(**kwargs):
        result = MagicMock()
        code = kwargs.get("code") or kwargs.get("code__in", [None])
        if isinstance(code, (list, set)):
            all_versions = []
            for c in code:
                all_versions.extend(codes_versions.get(c, []))
            result.values_list.return_value = all_versions
        else:
            result.values_list.return_value = codes_versions.get(code, [])
        result.exists.return_value = bool(result.values_list.return_value)
        return result

    mock_cm.objects.filter.side_effect = filter_side_effect


def _get_converter_class():
    from bkflow.pipeline_converter.converters.a2flow_v2.converter import (
        A2FlowV2Converter,
    )

    return A2FlowV2Converter


class TestConverterLinearFlow(TestCase):
    """线性流程转换测试"""

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_single_activity(self, mock_cm, mock_bkp):
        """最简流程：1 个 Activity，隐式 Start/End"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "version": "2.0",
            "name": "简单流程",
            "nodes": [
                {"id": "n1", "name": "等待", "code": "sleep_timer", "data": {"bk_timing": 5}, "next": "end"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertIn("start_event", result)
        self.assertIn("end_event", result)
        self.assertEqual(len(result["activities"]), 1)
        self.assertEqual(result["start_event"]["type"], "EmptyStartEvent")
        self.assertEqual(result["end_event"]["type"], "EmptyEndEvent")
        self.assertEqual(len(result["flows"]), 2)
        self.assertEqual(result["constants"], {})

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_two_activities_linear(self, mock_cm, mock_bkp):
        """2 个 Activity 串行"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"], "bk_notify": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "两步流程",
            "nodes": [
                {"id": "n1", "name": "等待", "code": "sleep_timer", "data": {"bk_timing": 5}, "next": "n2"},
                {"id": "n2", "name": "通知", "code": "bk_notify", "data": {"title": "done"}, "next": "end"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertEqual(len(result["activities"]), 2)
        self.assertEqual(len(result["flows"]), 3)

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_explicit_start_and_end(self, mock_cm, mock_bkp):
        """显式声明 StartEvent/EndEvent 不重复注入"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "显式事件",
            "nodes": [
                {"type": "StartEvent", "id": "my_start", "name": "开始", "next": "n1"},
                {"id": "n1", "name": "等待", "code": "sleep_timer", "next": "my_end"},
                {"type": "EndEvent", "id": "my_end", "name": "结束"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertEqual(len(result["activities"]), 1)
        self.assertNotEqual(result["start_event"]["id"], "start")

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_variables(self, mock_cm, mock_bkp):
        """变量转换"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "带变量",
            "nodes": [{"id": "n1", "name": "x", "code": "sleep_timer", "next": "end"}],
            "variables": [{"key": "${ip}", "name": "IP", "value": "10.0.0.1"}],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertIn("${ip}", result["constants"])
        self.assertEqual(result["constants"]["${ip}"]["value"], "10.0.0.1")


class TestConverterGatewayFlow(TestCase):
    """包含网关的流程转换测试"""

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_parallel_gateway(self, mock_cm, mock_bkp):
        """并行网关 + 汇聚网关"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "并行流程",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "sleep_timer", "next": "pg1"},
                {"type": "ParallelGateway", "id": "pg1", "name": "并行", "next": ["n2", "n3"]},
                {"id": "n2", "name": "分支A", "code": "sleep_timer", "next": "cg1"},
                {"id": "n3", "name": "分支B", "code": "sleep_timer", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "end"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertEqual(len(result["gateways"]), 2)
        pg = [g for g in result["gateways"].values() if g["type"] == "ParallelGateway"][0]
        cg = [g for g in result["gateways"].values() if g["type"] == "ConvergeGateway"][0]
        self.assertEqual(pg["converge_gateway_id"], cg["id"])

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_exclusive_gateway(self, mock_cm, mock_bkp):
        """排他网关 + 条件"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "条件流程",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "sleep_timer", "next": "eg1"},
                {
                    "type": "ExclusiveGateway",
                    "id": "eg1",
                    "name": "判断",
                    "next": ["n2", "n3"],
                    "conditions": [{"evaluate": "${x} > 0"}, {"evaluate": "${x} <= 0"}],
                    "default_next": "n3",
                },
                {"id": "n2", "name": "成功", "code": "sleep_timer", "next": "cg1"},
                {"id": "n3", "name": "失败", "code": "sleep_timer", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "end"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        eg = [g for g in result["gateways"].values() if g["type"] == "ExclusiveGateway"][0]
        self.assertIn("conditions", eg)
        self.assertIn("default_condition", eg)


class TestConverterValidation(TestCase):
    """转换校验测试"""

    def test_invalid_next_reference(self):
        """引用不存在的节点应报错"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {"name": "错误引用", "nodes": [{"id": "n1", "name": "x", "code": "y", "next": "nonexistent"}]}
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "INVALID_REFERENCE" for e in errors))

    def test_duplicate_node_id(self):
        """重复节点 ID 应报错"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "重复ID",
            "nodes": [
                {"id": "n1", "name": "a", "code": "x", "next": "end"},
                {"id": "n1", "name": "b", "code": "y", "next": "end"},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "DUPLICATE_NODE_ID" for e in errors))

    def test_conditions_mismatch(self):
        """conditions 数量与 next 分支数不一致应报错"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "条件不匹配",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "x", "next": "eg1"},
                {
                    "type": "ExclusiveGateway",
                    "id": "eg1",
                    "name": "判断",
                    "next": ["n2", "n3"],
                    "conditions": [{"evaluate": "True"}],
                },
                {"id": "n2", "name": "a", "code": "x", "next": "cg1"},
                {"id": "n3", "name": "b", "code": "x", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "end"},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "CONDITIONS_MISMATCH" for e in errors))

    def test_activity_missing_next(self):
        """Activity 缺少 next 应报 MISSING_REQUIRED_FIELD"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {"name": "缺少next", "nodes": [{"id": "n1", "name": "x", "code": "y"}]}
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "MISSING_REQUIRED_FIELD" and e.field == "next" for e in errors))

    def test_gateway_missing_conditions(self):
        """ExclusiveGateway 缺少 conditions 应报 MISSING_REQUIRED_FIELD"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "缺少conditions",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "x", "next": "eg1"},
                {"type": "ExclusiveGateway", "id": "eg1", "name": "判断", "next": ["n2", "n3"]},
                {"id": "n2", "name": "a", "code": "x", "next": "cg1"},
                {"id": "n3", "name": "b", "code": "x", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "end"},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "MISSING_REQUIRED_FIELD" and e.field == "conditions" for e in errors))

    def test_parallel_gateway_next_must_be_list(self):
        """ParallelGateway 的 next 必须是数组"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "错误并行",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "x", "next": "pg1"},
                {"type": "ParallelGateway", "id": "pg1", "name": "并行", "next": "n2"},
                {"id": "n2", "name": "a", "code": "x", "next": "end"},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "MISSING_REQUIRED_FIELD" and e.field == "next" for e in errors))

    def test_converge_gateway_next_must_be_string(self):
        """ConvergeGateway 的 next 必须是字符串"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "错误汇聚",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "x", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": ["end"]},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "MISSING_REQUIRED_FIELD" and e.field == "next" for e in errors))

    def test_unsupported_version(self):
        """不支持的 version 应报 UNSUPPORTED_VERSION"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "version": "9.9",
            "name": "错误版本",
            "nodes": [{"id": "n1", "name": "x", "code": "y", "next": "end"}],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "UNSUPPORTED_VERSION" for e in errors))

    def test_reserved_id_conflict(self):
        """保留 ID start/end 仅允许对应事件类型"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {"name": "保留ID冲突", "nodes": [{"id": "start", "name": "非法", "code": "y", "next": "end"}]}
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "RESERVED_ID_CONFLICT" for e in errors))

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_plugin_type_flow(self, mock_cm, mock_bkp, mock_safe_fetch, mock_fetch_meta):
        """混合插件类型流程"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
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

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "混合插件",
            "nodes": [
                {"id": "n1", "name": "内置", "code": "sleep_timer", "next": "n2"},
                {
                    "id": "n2",
                    "name": "API调用",
                    "code": "my_api",
                    "plugin_type": "uniform_api",
                    "data": {"biz_id": 1},
                    "next": "end",
                },
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        activities = list(result["activities"].values())
        self.assertEqual(activities[0]["component"]["code"], "sleep_timer")
        self.assertEqual(activities[1]["component"]["code"], "uniform_api")
