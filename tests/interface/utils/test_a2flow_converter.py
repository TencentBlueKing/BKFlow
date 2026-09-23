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
from unittest.mock import patch

from django.test import TestCase


class TestA2FlowConverterBasic(TestCase):
    """测试 A2FlowConverter 基本流程转换"""

    def _get_converter_class(self):
        from bkflow.utils.a2flow import A2FlowConverter

        return A2FlowConverter

    def _simple_linear_flow(self):
        """start -> activity -> end"""
        return [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "Activity", "id": "n1", "name": "测试节点", "code": "job_fast_execute_script"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "end"},
        ]

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_linear_flow_convert_success(self, mock_cm):
        """测试简单线性流程转换成功"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        converter = A2FlowConverter(self._simple_linear_flow())
        result = converter.convert()

        self.assertIn("activities", result)
        self.assertIn("start_event", result)
        self.assertIn("end_event", result)
        self.assertIn("flows", result)
        self.assertIn("gateways", result)
        self.assertIn("constants", result)
        self.assertIn("outputs", result)

        # 验证节点数量
        self.assertEqual(len(result["activities"]), 1)
        self.assertEqual(len(result["flows"]), 2)
        self.assertEqual(len(result["gateways"]), 0)

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_activity_fields_complete(self, mock_cm):
        """测试 Activity 节点字段完整性"""
        mock_cm.objects.filter.return_value.values_list.side_effect = lambda *args, **kwargs: (
            [("job_fast_execute_script", "v1.0")] if "flat" not in kwargs else ["v1.0"]
        )
        A2FlowConverter = self._get_converter_class()

        converter = A2FlowConverter(self._simple_linear_flow())
        result = converter.convert()

        activity = list(result["activities"].values())[0]
        self.assertEqual(activity["type"], "ServiceActivity")
        self.assertEqual(activity["name"], "测试节点")
        self.assertEqual(activity["component"]["code"], "job_fast_execute_script")
        self.assertEqual(activity["component"]["version"], "v1.0")
        self.assertIn("auto_retry", activity)
        self.assertIn("timeout_config", activity)
        self.assertIn("error_ignorable", activity)
        self.assertIn("retryable", activity)
        self.assertIn("skippable", activity)
        self.assertIn("optional", activity)

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_start_end_event_type(self, mock_cm):
        """测试开始/结束事件类型"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        converter = A2FlowConverter(self._simple_linear_flow())
        result = converter.convert()

        self.assertEqual(result["start_event"]["type"], "EmptyStartEvent")
        self.assertEqual(result["end_event"]["type"], "EmptyEndEvent")

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_flow_connections(self, mock_cm):
        """测试 flow 连接关系正确性"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        converter = A2FlowConverter(self._simple_linear_flow())
        result = converter.convert()

        flows = result["flows"]
        self.assertEqual(len(flows), 2)

        # 验证连接: start -> n1 -> end
        start_id = result["start_event"]["id"]
        # end_id = result["end_event"]["id"]
        activity_id = list(result["activities"].keys())[0]

        outgoing_flow_id = result["start_event"]["outgoing"]
        self.assertEqual(flows[outgoing_flow_id]["source"], start_id)
        self.assertEqual(flows[outgoing_flow_id]["target"], activity_id)

    def test_missing_start_event_raises(self):
        """测试缺少开始事件节点报错"""
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "Activity", "id": "n1", "name": "测试", "code": "test"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "n1", "target": "end"},
        ]

        with self.assertRaises(ValueError) as ctx:
            converter = A2FlowConverter(a2flow)
            converter.convert()
        self.assertIn("缺少开始/结束事件节点", str(ctx.exception))

    def test_missing_end_event_raises(self):
        """测试缺少结束事件节点报错"""
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "Activity", "id": "n1", "name": "测试", "code": "test"},
            {"type": "Link", "source": "start", "target": "n1"},
        ]

        with self.assertRaises(ValueError) as ctx:
            converter = A2FlowConverter(a2flow)
            converter.convert()
        self.assertIn("缺少开始/结束事件节点", str(ctx.exception))

    def test_link_references_undefined_node_raises(self):
        """测试 Link 引用未定义节点报错"""
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "nonexistent"},
        ]

        with self.assertRaises(KeyError) as ctx:
            A2FlowConverter(a2flow)
        self.assertIn("未定义的节点", str(ctx.exception))

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_name_type_parsed(self, mock_cm):
        """测试 name 类型节点解析"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "name", "value": "我的流程"},
        ] + self._simple_linear_flow()

        converter = A2FlowConverter(a2flow)
        self.assertEqual(converter.template_name, "我的流程")

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_node_ids_regenerated(self, mock_cm):
        """测试节点 ID 被重新生成"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        converter = A2FlowConverter(self._simple_linear_flow())
        result = converter.convert()

        # 原始 ID 不应出现在结果中
        self.assertNotIn("start", [result["start_event"]["id"]])
        self.assertNotIn("n1", list(result["activities"].keys()))
        self.assertNotIn("end", [result["end_event"]["id"]])

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_activity_data_normalized(self, mock_cm):
        """测试 Activity 的 data 字段被正确包装"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {
                "type": "Activity",
                "id": "n1",
                "name": "测试",
                "code": "test_code",
                "data": {"script_content": "echo hello", "ip_list": "127.0.0.1"},
            },
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        activity = list(result["activities"].values())[0]
        data = activity["component"]["data"]
        # 验证每个 data 字段都被包装为 {hook, need_render, value}
        self.assertEqual(data["script_content"]["value"], "echo hello")
        self.assertFalse(data["script_content"]["hook"])
        self.assertTrue(data["script_content"]["need_render"])
        self.assertEqual(data["ip_list"]["value"], "127.0.0.1")

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_activity_data_already_wrapped_not_double_wrapped(self, mock_cm):
        """测试已包装的 data 字段不会被二次包装"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        wrapped_value = {"hook": True, "need_render": False, "value": "test"}
        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "Activity", "id": "n1", "name": "测试", "code": "test_code", "data": {"field": wrapped_value}},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        activity = list(result["activities"].values())[0]
        self.assertEqual(activity["component"]["data"]["field"], wrapped_value)


class TestA2FlowConverterVariable(TestCase):
    """测试 A2FlowConverter 变量处理"""

    def _get_converter_class(self):
        from bkflow.utils.a2flow import A2FlowConverter

        return A2FlowConverter

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_variables_converted(self, mock_cm):
        """测试变量正确转换"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "end"},
            {
                "type": "Variable",
                "key": "${version}",
                "name": "版本号",
                "value": "1.0",
                "source_type": "custom",
                "custom_type": "input",
                "description": "资源版本号",
            },
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        self.assertIn("${version}", result["constants"])
        var = result["constants"]["${version}"]
        self.assertEqual(var["key"], "${version}")
        self.assertEqual(var["name"], "版本号")
        self.assertEqual(var["value"], "1.0")
        self.assertEqual(var["source_type"], "custom")
        self.assertEqual(var["custom_type"], "input")
        self.assertEqual(var["desc"], "资源版本号")

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_multiple_variables(self, mock_cm):
        """测试多个变量转换"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "end"},
            {"type": "Variable", "key": "${var1}", "name": "变量1"},
            {"type": "Variable", "key": "${var2}", "name": "变量2"},
            {"type": "Variable", "key": "${var3}", "name": "变量3"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        self.assertEqual(len(result["constants"]), 3)
        # 验证 index 递增
        self.assertEqual(result["constants"]["${var1}"]["index"], 0)
        self.assertEqual(result["constants"]["${var2}"]["index"], 1)
        self.assertEqual(result["constants"]["${var3}"]["index"], 2)

    def test_variable_missing_key_raises(self):
        """测试变量缺少 key 字段报错"""
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "end"},
            {"type": "Variable", "name": "缺少key的变量"},
        ]

        with self.assertRaises(KeyError) as ctx:
            converter = A2FlowConverter(a2flow)
            converter.convert()
        self.assertIn("Variable 缺少必填字段", str(ctx.exception))


class TestA2FlowConverterGateway(TestCase):
    """测试 A2FlowConverter 网关处理"""

    def _get_converter_class(self):
        from bkflow.utils.a2flow import A2FlowConverter

        return A2FlowConverter

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_parallel_gateway_convert(self, mock_cm):
        """测试并行网关转换"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "ParallelGateway", "id": "pg1", "name": "并行"},
            {"type": "Activity", "id": "n1", "name": "分支1", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "分支2", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "pg1"},
            {"type": "Link", "source": "pg1", "target": "n1"},
            {"type": "Link", "source": "pg1", "target": "n2"},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        self.assertEqual(len(result["gateways"]), 2)
        self.assertEqual(len(result["activities"]), 2)

        # 找到 ParallelGateway
        pg = None
        cg = None
        for gw in result["gateways"].values():
            if gw["type"] == "ParallelGateway":
                pg = gw
            elif gw["type"] == "ConvergeGateway":
                cg = gw

        self.assertIsNotNone(pg)
        self.assertIsNotNone(cg)
        self.assertEqual(len(pg["outgoing"]), 2)

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_parallel_gateway_auto_infer_converge_id(self, mock_cm):
        """测试并行网关自动推断 converge_gateway_id"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "ParallelGateway", "id": "pg1", "name": "并行"},
            {"type": "Activity", "id": "n1", "name": "分支1", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "分支2", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "pg1"},
            {"type": "Link", "source": "pg1", "target": "n1"},
            {"type": "Link", "source": "pg1", "target": "n2"},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        pg = [gw for gw in result["gateways"].values() if gw["type"] == "ParallelGateway"][0]
        cg = [gw for gw in result["gateways"].values() if gw["type"] == "ConvergeGateway"][0]

        # 验证自动推断的 converge_gateway_id 指向正确的汇聚网关
        self.assertEqual(pg["converge_gateway_id"], cg["id"])

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_parallel_gateway_explicit_converge_id_not_overridden(self, mock_cm):
        """测试显式指定 converge_gateway_id 不会被覆盖"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "ParallelGateway", "id": "pg1", "name": "并行", "converge_gateway_id": "cg1"},
            {"type": "Activity", "id": "n1", "name": "分支1", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "分支2", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "pg1"},
            {"type": "Link", "source": "pg1", "target": "n1"},
            {"type": "Link", "source": "pg1", "target": "n2"},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        pg = [gw for gw in result["gateways"].values() if gw["type"] == "ParallelGateway"][0]
        cg = [gw for gw in result["gateways"].values() if gw["type"] == "ConvergeGateway"][0]

        self.assertEqual(pg["converge_gateway_id"], cg["id"])

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_exclusive_gateway_with_conditions(self, mock_cm):
        """测试排他网关条件转换"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {
                "type": "ExclusiveGateway",
                "id": "eg1",
                "name": "条件判断",
                "conditions": [
                    {"evaluate": "${status}=='pass'", "target": "n1"},
                    {"evaluate": "${status}!='pass'", "target": "n2"},
                ],
            },
            {"type": "Activity", "id": "n1", "name": "成功分支", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "失败分支", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "eg1"},
            {"type": "Link", "source": "eg1", "target": "n1"},
            {"type": "Link", "source": "eg1", "target": "n2"},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        eg = [gw for gw in result["gateways"].values() if gw["type"] == "ExclusiveGateway"][0]

        self.assertIn("conditions", eg)
        self.assertEqual(len(eg["conditions"]), 2)

        # 验证条件表达式
        expressions = [c["evaluate"] for c in eg["conditions"].values()]
        self.assertIn("${status}=='pass'", expressions)
        self.assertIn("${status}!='pass'", expressions)

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_exclusive_gateway_default_condition(self, mock_cm):
        """测试排他网关默认分支 (is_default)"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {
                "type": "ExclusiveGateway",
                "id": "eg1",
                "name": "条件判断",
                "conditions": [
                    {"evaluate": "${status}=='pass'", "target": "n1"},
                    {"evaluate": "${status}!='pass'", "target": "n2"},
                ],
            },
            {"type": "Activity", "id": "n1", "name": "成功", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "失败", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "eg1"},
            {"type": "Link", "source": "eg1", "target": "n1"},
            {"type": "Link", "source": "eg1", "target": "n2", "is_default": True},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        eg = [gw for gw in result["gateways"].values() if gw["type"] == "ExclusiveGateway"][0]

        # 验证 default_condition 被设置
        self.assertIn("default_condition", eg)
        self.assertIn("flow_id", eg["default_condition"])
        self.assertTrue(len(eg["default_condition"]["flow_id"]) > 0)

        # 验证 default flow 的 is_default 为 True
        default_flow_id = eg["default_condition"]["flow_id"]
        self.assertTrue(result["flows"][default_flow_id]["is_default"])

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_exclusive_gateway_no_default_condition(self, mock_cm):
        """测试排他网关无默认分支时 default_condition 为空"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {
                "type": "ExclusiveGateway",
                "id": "eg1",
                "name": "条件判断",
                "conditions": [
                    {"evaluate": "${status}=='pass'", "target": "n1"},
                    {"evaluate": "${status}!='pass'", "target": "n2"},
                ],
            },
            {"type": "Activity", "id": "n1", "name": "成功", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "失败", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "eg1"},
            {"type": "Link", "source": "eg1", "target": "n1"},
            {"type": "Link", "source": "eg1", "target": "n2"},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        eg = [gw for gw in result["gateways"].values() if gw["type"] == "ExclusiveGateway"][0]
        self.assertEqual(eg["default_condition"], {})

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_conditional_parallel_gateway_builds_conditions(self, mock_cm):
        """测试条件并行网关会生成 schema 要求的 conditions 字段"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {
                "type": "ConditionalParallelGateway",
                "id": "cpg1",
                "name": "条件并行",
                "conditions": [
                    {"evaluate": "${score} > 60", "target": "n1", "name": "通过"},
                    {"evaluate": "${score} <= 60", "target": "n2", "name": "未通过"},
                ],
            },
            {"type": "Activity", "id": "n1", "name": "分支1", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "分支2", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "cpg1"},
            {"type": "Link", "source": "cpg1", "target": "n1"},
            {"type": "Link", "source": "cpg1", "target": "n2"},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        cpg = [gw for gw in result["gateways"].values() if gw["type"] == "ConditionalParallelGateway"][0]

        self.assertIn("conditions", cpg)
        self.assertEqual(len(cpg["conditions"]), 2)
        expressions = [condition["evaluate"] for condition in cpg["conditions"].values()]
        self.assertIn("${score} > 60", expressions)
        self.assertIn("${score} <= 60", expressions)

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_link_is_default_propagated_to_flow(self, mock_cm):
        """测试 Link 的 is_default 正确传递到 flow"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "ExclusiveGateway", "id": "eg1", "name": "判断"},
            {"type": "Activity", "id": "n1", "name": "分支1", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "分支2", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "eg1"},
            {"type": "Link", "source": "eg1", "target": "n1"},
            {"type": "Link", "source": "eg1", "target": "n2", "is_default": True},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        default_flows = [f for f in result["flows"].values() if f["is_default"]]
        non_default_flows = [f for f in result["flows"].values() if not f["is_default"]]

        self.assertEqual(len(default_flows), 1)
        self.assertTrue(len(non_default_flows) > 0)


class TestA2FlowConverterComplex(TestCase):
    """测试 A2FlowConverter 复杂场景"""

    def _get_converter_class(self):
        from bkflow.utils.a2flow import A2FlowConverter

        return A2FlowConverter

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_nested_parallel_and_exclusive_gateways(self, mock_cm):
        """测试并行网关嵌套排他网关的复杂流程"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "Activity", "id": "n1", "name": "审批", "code": "pause_node"},
            {"type": "ParallelGateway", "id": "pg1", "name": "并行创建"},
            {"type": "Activity", "id": "n2", "name": "iOS创建", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n3", "name": "Android创建", "code": "job_fast_execute_script"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "并行汇聚"},
            {
                "type": "ExclusiveGateway",
                "id": "eg1",
                "name": "校验判断",
                "conditions": [
                    {"evaluate": "${check}=='pass'", "target": "n4"},
                    {"evaluate": "${check}!='pass'", "target": "n5"},
                ],
            },
            {"type": "Activity", "id": "n4", "name": "发布", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n5", "name": "回滚", "code": "job_fast_execute_script"},
            {"type": "ConvergeGateway", "id": "cg2", "name": "条件汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "pg1"},
            {"type": "Link", "source": "pg1", "target": "n2"},
            {"type": "Link", "source": "pg1", "target": "n3"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "n3", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "eg1"},
            {"type": "Link", "source": "eg1", "target": "n4"},
            {"type": "Link", "source": "eg1", "target": "n5", "is_default": True},
            {"type": "Link", "source": "n4", "target": "cg2"},
            {"type": "Link", "source": "n5", "target": "cg2"},
            {"type": "Link", "source": "cg2", "target": "end"},
            {"type": "Variable", "key": "${check}", "name": "校验结果", "value": "pass"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        # 验证整体结构
        self.assertEqual(len(result["activities"]), 5)
        self.assertEqual(len(result["gateways"]), 4)  # pg1, cg1, eg1, cg2
        self.assertEqual(len(result["constants"]), 1)

        # 验证并行网关的 converge_gateway_id 被自动推断
        pg = [gw for gw in result["gateways"].values() if gw["type"] == "ParallelGateway"][0]
        cg_ids = [gw["id"] for gw in result["gateways"].values() if gw["type"] == "ConvergeGateway"]
        self.assertIn(pg["converge_gateway_id"], cg_ids)

        # 验证排他网关有 default_condition
        eg = [gw for gw in result["gateways"].values() if gw["type"] == "ExclusiveGateway"][0]
        self.assertIn("flow_id", eg["default_condition"])

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_full_client_update_flow(self, mock_cm):
        """测试完整的客户端更新流程（并行+排他+多汇聚）"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "name", "value": "客户端更新-创建资源版本"},
            {"type": "StartEvent", "id": "start", "name": "流程开始"},
            {"type": "Activity", "id": "n1", "name": "发布审批确认", "code": "pause_node"},
            {"type": "Activity", "id": "n2", "name": "备份当前版本", "code": "job_fast_execute_script"},
            {"type": "ParallelGateway", "id": "pg1", "name": "三平台并行创建"},
            {"type": "Activity", "id": "n3", "name": "iOS整包资源版本创建", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n4", "name": "iOS版本校验", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n5", "name": "Android整包资源版本创建", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n6", "name": "Android版本校验", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n7", "name": "PC整包资源版本创建", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n8", "name": "PC版本校验", "code": "job_fast_execute_script"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "并行汇聚"},
            {
                "type": "ExclusiveGateway",
                "id": "eg1",
                "name": "校验结果判断",
                "conditions": [
                    {"evaluate": "${check_result}=='pass'", "target": "n9"},
                    {"evaluate": "${check_result}!='pass'", "target": "n15"},
                ],
            },
            {"type": "Activity", "id": "n9", "name": "告警屏蔽", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n10", "name": "灰度发布", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n11", "name": "灰度效果确认", "code": "pause_node"},
            {
                "type": "ExclusiveGateway",
                "id": "eg2",
                "name": "灰度结果判断",
                "conditions": [
                    {"evaluate": "${gray_status}=='normal'", "target": "n12"},
                    {"evaluate": "${gray_status}!='normal'", "target": "n17"},
                ],
            },
            {"type": "Activity", "id": "n12", "name": "全量发布", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n13", "name": "告警恢复", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n14", "name": "发布成功通知", "code": "bk_notify"},
            {"type": "Activity", "id": "n15", "name": "校验失败回滚", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n16", "name": "校验失败通知", "code": "bk_notify"},
            {"type": "Activity", "id": "n17", "name": "灰度异常回滚", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n18", "name": "灰度异常告警恢复", "code": "job_fast_execute_script"},
            {"type": "Activity", "id": "n19", "name": "灰度异常通知", "code": "bk_notify"},
            {"type": "ConvergeGateway", "id": "cg2", "name": "校验分支汇聚"},
            {"type": "ConvergeGateway", "id": "cg3", "name": "灰度分支汇聚"},
            {"type": "EndEvent", "id": "end", "name": "流程结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "n2"},
            {"type": "Link", "source": "n2", "target": "pg1"},
            {"type": "Link", "source": "pg1", "target": "n3"},
            {"type": "Link", "source": "pg1", "target": "n5"},
            {"type": "Link", "source": "pg1", "target": "n7"},
            {"type": "Link", "source": "n3", "target": "n4"},
            {"type": "Link", "source": "n5", "target": "n6"},
            {"type": "Link", "source": "n7", "target": "n8"},
            {"type": "Link", "source": "n4", "target": "cg1"},
            {"type": "Link", "source": "n6", "target": "cg1"},
            {"type": "Link", "source": "n8", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "eg1"},
            {"type": "Link", "source": "eg1", "target": "n9"},
            {"type": "Link", "source": "eg1", "target": "n15", "is_default": True},
            {"type": "Link", "source": "n9", "target": "n10"},
            {"type": "Link", "source": "n10", "target": "n11"},
            {"type": "Link", "source": "n11", "target": "eg2"},
            {"type": "Link", "source": "eg2", "target": "n12"},
            {"type": "Link", "source": "eg2", "target": "n17", "is_default": True},
            {"type": "Link", "source": "n12", "target": "n13"},
            {"type": "Link", "source": "n13", "target": "n14"},
            {"type": "Link", "source": "n14", "target": "cg3"},
            {"type": "Link", "source": "n17", "target": "n18"},
            {"type": "Link", "source": "n18", "target": "n19"},
            {"type": "Link", "source": "n19", "target": "cg3"},
            {"type": "Link", "source": "cg3", "target": "cg2"},
            {"type": "Link", "source": "n15", "target": "n16"},
            {"type": "Link", "source": "n16", "target": "cg2"},
            {"type": "Link", "source": "cg2", "target": "end"},
            {"type": "Variable", "key": "${version}", "name": "资源版本号", "value": ""},
            {"type": "Variable", "key": "${check_result}", "name": "校验结果", "value": "pass"},
            {"type": "Variable", "key": "${gray_status}", "name": "灰度状态", "value": "normal"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        self.assertEqual(converter.template_name, "客户端更新-创建资源版本")
        self.assertEqual(len(result["activities"]), 19)
        self.assertEqual(len(result["gateways"]), 6)  # pg1, cg1, eg1, eg2, cg2, cg3
        self.assertEqual(len(result["constants"]), 3)

        # 验证 ParallelGateway 自动推断 converge_gateway_id
        pg = [gw for gw in result["gateways"].values() if gw["type"] == "ParallelGateway"][0]
        self.assertTrue(len(pg["converge_gateway_id"]) > 0)

        # 验证 pg1 有 3 个出向分支
        self.assertEqual(len(pg["outgoing"]), 3)

        # 验证两个 ExclusiveGateway 都有 default_condition
        egs = [gw for gw in result["gateways"].values() if gw["type"] == "ExclusiveGateway"]
        self.assertEqual(len(egs), 2)
        for eg in egs:
            self.assertIn("flow_id", eg["default_condition"])
            self.assertTrue(len(eg["default_condition"]["flow_id"]) > 0)

        # 验证 is_default 的 flow 有 2 条
        default_flows = [f for f in result["flows"].values() if f["is_default"]]
        self.assertEqual(len(default_flows), 2)

        # 验证所有 flow 的 source/target 都是合法节点 ID
        all_node_ids = set()
        all_node_ids.add(result["start_event"]["id"])
        all_node_ids.add(result["end_event"]["id"])
        all_node_ids.update(result["activities"].keys())
        all_node_ids.update(result["gateways"].keys())

        for flow in result["flows"].values():
            self.assertIn(flow["source"], all_node_ids, "flow source {} not in nodes".format(flow["source"]))
            self.assertIn(flow["target"], all_node_ids, "flow target {} not in nodes".format(flow["target"]))

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_nested_exclusive_gateway_does_not_break_parallel_converge_inference(self, mock_cm):
        """测试并行网关内嵌排他网关时不会误将内层汇聚配给外层并行网关"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "ParallelGateway", "id": "pg1", "name": "外层并行"},
            {
                "type": "ExclusiveGateway",
                "id": "eg1",
                "name": "内层判断",
                "conditions": [
                    {"evaluate": "${flag}", "target": "n1"},
                    {"evaluate": "!${flag}", "target": "n2"},
                ],
            },
            {"type": "Activity", "id": "n1", "name": "分支1", "code": "test"},
            {"type": "Activity", "id": "n2", "name": "分支2", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "内层汇聚"},
            {"type": "Activity", "id": "n3", "name": "并行旁路", "code": "test"},
            {"type": "ConvergeGateway", "id": "cg2", "name": "外层汇聚"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "pg1"},
            {"type": "Link", "source": "pg1", "target": "eg1"},
            {"type": "Link", "source": "pg1", "target": "n3"},
            {"type": "Link", "source": "eg1", "target": "n1"},
            {"type": "Link", "source": "eg1", "target": "n2", "is_default": True},
            {"type": "Link", "source": "n1", "target": "cg1"},
            {"type": "Link", "source": "n2", "target": "cg1"},
            {"type": "Link", "source": "cg1", "target": "cg2"},
            {"type": "Link", "source": "n3", "target": "cg2"},
            {"type": "Link", "source": "cg2", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        pg = [gw for gw in result["gateways"].values() if gw["type"] == "ParallelGateway"][0]
        cg_map = {gw["name"]: gw["id"] for gw in result["gateways"].values() if gw["type"] == "ConvergeGateway"}

        self.assertEqual(pg["converge_gateway_id"], cg_map["外层汇聚"])


class TestA2FlowConverterVersionLookup(TestCase):
    """测试 A2FlowConverter 组件版本查询"""

    def _get_converter_class(self):
        from bkflow.utils.a2flow import A2FlowConverter

        return A2FlowConverter

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_latest_version_selected(self, mock_cm):
        """测试选择最新版本"""
        mock_cm.objects.filter.return_value.values_list.side_effect = lambda *args, **kwargs: (
            [("test_component", "v1.0"), ("test_component", "v2.0"), ("test_component", "v1.5")]
            if "flat" not in kwargs
            else ["v1.0", "v2.0", "v1.5"]
        )
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "Activity", "id": "n1", "name": "测试", "code": "test_component"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        activity = list(result["activities"].values())[0]
        self.assertEqual(activity["component"]["version"], "v2.0")

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_no_version_fallback_to_legacy(self, mock_cm):
        """测试无版本时回退到 legacy"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "Activity", "id": "n1", "name": "测试", "code": "unknown_code"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        activity = list(result["activities"].values())[0]
        self.assertEqual(activity["component"]["version"], "legacy")

    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_empty_code_fallback_to_legacy(self, mock_cm):
        """测试空 code 回退到 legacy"""
        A2FlowConverter = self._get_converter_class()

        a2flow = [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "Activity", "id": "n1", "name": "测试", "code": ""},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "end"},
        ]

        converter = A2FlowConverter(a2flow)
        result = converter.convert()

        activity = list(result["activities"].values())[0]
        self.assertEqual(activity["component"]["version"], "legacy")
        # 不应该调用数据库查询
        mock_cm.objects.filter.assert_not_called()
