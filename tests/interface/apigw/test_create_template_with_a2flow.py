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
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from bkflow.space.models import Space


class TestCreateTemplateWithA2FlowSerializer(TestCase):
    """测试 CreateTemplateWithA2FlowSerializer"""

    def _get_serializer_class(self):
        from bkflow.apigw.serializers.a2flow import CreateTemplateWithA2FlowSerializer

        return CreateTemplateWithA2FlowSerializer

    def test_valid_data(self):
        """测试有效数据通过校验"""
        Serializer = self._get_serializer_class()
        data = {
            "name": "测试流程",
            "a2flow": [
                {"type": "StartEvent", "id": "start", "name": "开始"},
                {"type": "EndEvent", "id": "end", "name": "结束"},
                {"type": "Link", "source": "start", "target": "end"},
            ],
        }
        ser = Serializer(data=data)
        self.assertTrue(ser.is_valid())

    def test_missing_name_fails(self):
        """测试缺少 name 字段校验失败"""
        Serializer = self._get_serializer_class()
        data = {
            "a2flow": [{"type": "StartEvent", "id": "start", "name": "开始"}],
        }
        ser = Serializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn("name", ser.errors)

    def test_missing_a2flow_fails(self):
        """测试缺少 a2flow 字段校验失败"""
        Serializer = self._get_serializer_class()
        data = {"name": "测试流程"}
        ser = Serializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn("a2flow", ser.errors)

    def test_a2flow_not_list_fails(self):
        """测试 a2flow 不是数组时校验失败"""
        Serializer = self._get_serializer_class()
        data = {"name": "测试", "a2flow": {"type": "StartEvent"}}
        ser = Serializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn("a2flow", ser.errors)

    def test_a2flow_empty_list_fails(self):
        """测试 a2flow 为空数组时校验失败"""
        Serializer = self._get_serializer_class()
        data = {"name": "测试", "a2flow": []}
        ser = Serializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn("a2flow", ser.errors)

    def test_scope_type_without_value_fails(self):
        """测试 scope_type 和 scope_value 必须同时填写"""
        Serializer = self._get_serializer_class()
        data = {
            "name": "测试",
            "a2flow": [{"type": "StartEvent", "id": "start", "name": "开始"}],
            "scope_type": "biz",
        }
        ser = Serializer(data=data)
        self.assertFalse(ser.is_valid())

    def test_scope_value_without_type_fails(self):
        """测试 scope_value 缺少 scope_type 时校验失败"""
        Serializer = self._get_serializer_class()
        data = {
            "name": "测试",
            "a2flow": [{"type": "StartEvent", "id": "start", "name": "开始"}],
            "scope_value": "123",
        }
        ser = Serializer(data=data)
        self.assertFalse(ser.is_valid())

    def test_scope_type_and_value_both_present_ok(self):
        """测试 scope_type 和 scope_value 同时填写通过"""
        Serializer = self._get_serializer_class()
        data = {
            "name": "测试",
            "a2flow": [{"type": "StartEvent", "id": "start", "name": "开始"}],
            "scope_type": "biz",
            "scope_value": "123",
        }
        ser = Serializer(data=data)
        self.assertTrue(ser.is_valid())

    def test_optional_fields(self):
        """测试可选字段有效"""
        Serializer = self._get_serializer_class()
        data = {
            "name": "测试",
            "a2flow": [{"type": "StartEvent", "id": "start", "name": "开始"}],
            "creator": "admin",
            "desc": "描述",
            "auto_release": True,
        }
        ser = Serializer(data=data)
        self.assertTrue(ser.is_valid())
        self.assertEqual(ser.validated_data["creator"], "admin")
        self.assertEqual(ser.validated_data["desc"], "描述")
        self.assertTrue(ser.validated_data["auto_release"])


class TestCreateTemplateWithA2FlowView(TestCase):
    """测试 create_template_with_a2flow API 接口"""

    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    def _simple_a2flow(self):
        return [
            {"type": "StartEvent", "id": "start", "name": "开始"},
            {"type": "Activity", "id": "n1", "name": "测试节点", "code": "bk_display"},
            {"type": "EndEvent", "id": "end", "name": "结束"},
            {"type": "Link", "source": "start", "target": "n1"},
            {"type": "Link", "source": "n1", "target": "end"},
        ]

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_create_template_with_a2flow_success(self, mock_cm):
        """测试通过 a2flow 创建模板成功"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        space = self.create_space()

        data = {
            "name": "测试A2Flow流程",
            "a2flow": self._simple_a2flow(),
        }

        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp_data["result"])
        self.assertEqual(resp_data["data"]["name"], "测试A2Flow流程")
        self.assertIn("pipeline_tree", resp_data["data"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_create_template_with_a2flow_and_desc(self, mock_cm):
        """测试带描述信息创建模板"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        space = self.create_space()

        data = {
            "name": "带描述的流程",
            "desc": "这是一个测试流程",
            "a2flow": self._simple_a2flow(),
        }

        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp_data["result"])
        self.assertEqual(resp_data["data"]["desc"], "这是一个测试流程")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_create_template_with_a2flow_missing_name(self):
        """测试缺少 name 字段返回校验失败"""
        space = self.create_space()

        data = {
            "a2flow": self._simple_a2flow(),
        }

        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp_data["result"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_create_template_with_a2flow_empty_a2flow(self):
        """测试空 a2flow 数组返回校验失败"""
        space = self.create_space()

        data = {
            "name": "测试",
            "a2flow": [],
        }

        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp_data["result"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_create_template_with_a2flow_conversion_error(self, mock_cm):
        """测试转换失败返回错误信息"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        space = self.create_space()

        # 缺少结束节点，转换时会报错
        data = {
            "name": "错误流程",
            "a2flow": [
                {"type": "StartEvent", "id": "start", "name": "开始"},
                {"type": "Activity", "id": "n1", "name": "测试", "code": "test"},
                {"type": "Link", "source": "start", "target": "n1"},
            ],
        }

        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp_data["result"])
        self.assertIn("流程转换失败", resp_data["message"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_create_template_with_a2flow_pipeline_tree_structure(self, mock_cm):
        """测试返回的 pipeline_tree 结构完整"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        space = self.create_space()

        data = {
            "name": "结构验证",
            "a2flow": self._simple_a2flow(),
        }

        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertTrue(resp_data["result"])
        pipeline_tree = resp_data["data"]["pipeline_tree"]

        self.assertIn("activities", pipeline_tree)
        self.assertIn("gateways", pipeline_tree)
        self.assertIn("flows", pipeline_tree)
        self.assertIn("start_event", pipeline_tree)
        self.assertIn("end_event", pipeline_tree)
        self.assertIn("constants", pipeline_tree)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_create_template_with_variables(self, mock_cm):
        """测试带变量的流程创建"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        space = self.create_space()

        data = {
            "name": "带变量的流程",
            "a2flow": self._simple_a2flow()
            + [
                {"type": "Variable", "key": "${version}", "name": "版本号", "value": "1.0"},
                {"type": "Variable", "key": "${env}", "name": "环境", "value": "prod"},
            ],
        }

        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertTrue(resp_data["result"])
        constants = resp_data["data"]["pipeline_tree"]["constants"]
        self.assertIn("${version}", constants)
        self.assertIn("${env}", constants)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.utils.a2flow.ComponentModel")
    def test_create_template_with_parallel_gateway(self, mock_cm):
        """测试带并行网关的流程创建"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        space = self.create_space()

        data = {
            "name": "并行网关流程",
            "a2flow": [
                {"type": "StartEvent", "id": "start", "name": "开始"},
                {"type": "ParallelGateway", "id": "pg1", "name": "并行"},
                {"type": "Activity", "id": "n1", "name": "分支1", "code": "bk_display"},
                {"type": "Activity", "id": "n2", "name": "分支2", "code": "bk_display"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"},
                {"type": "EndEvent", "id": "end", "name": "结束"},
                {"type": "Link", "source": "start", "target": "pg1"},
                {"type": "Link", "source": "pg1", "target": "n1"},
                {"type": "Link", "source": "pg1", "target": "n2"},
                {"type": "Link", "source": "n1", "target": "cg1"},
                {"type": "Link", "source": "n2", "target": "cg1"},
                {"type": "Link", "source": "cg1", "target": "end"},
            ],
        }

        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertTrue(resp_data["result"])
        gateways = resp_data["data"]["pipeline_tree"]["gateways"]
        self.assertEqual(len(gateways), 2)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_create_template_with_a2flow_get_method_not_allowed(self):
        """测试 GET 方法不允许"""
        space = self.create_space()
        url = "/apigw/space/{}/create_template_with_a2flow/".format(space.id)
        resp = self.client.get(path=url)
        self.assertEqual(resp.status_code, 405)


class TestCreateTemplateWithA2FlowV2Serializer(TestCase):
    """v2 序列化器测试"""

    def _get_serializer_class(self):
        from bkflow.apigw.serializers.a2flow import CreateTemplateWithA2FlowV2Serializer

        return CreateTemplateWithA2FlowV2Serializer

    def test_valid_v2_input(self):
        Ser = self._get_serializer_class()
        data = {
            "a2flow": {
                "version": "2.0",
                "name": "测试流程",
                "nodes": [{"id": "n1", "name": "步骤", "code": "sleep_timer", "next": "end"}],
            }
        }
        ser = Ser(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_a2flow_must_be_dict(self):
        Ser = self._get_serializer_class()
        data = {"a2flow": [{"type": "name", "value": "test"}]}
        ser = Ser(data=data)
        self.assertFalse(ser.is_valid())

    def test_a2flow_must_have_nodes(self):
        Ser = self._get_serializer_class()
        data = {"a2flow": {"version": "2.0", "name": "空流程"}}
        ser = Ser(data=data)
        self.assertFalse(ser.is_valid())

    def test_a2flow_name_required(self):
        Ser = self._get_serializer_class()
        data = {
            "a2flow": {
                "version": "2.0",
                "nodes": [{"id": "n1", "name": "步骤", "code": "sleep_timer", "next": "end"}],
            }
        }
        ser = Ser(data=data)
        self.assertFalse(ser.is_valid())

    def test_optional_fields(self):
        Ser = self._get_serializer_class()
        data = {
            "a2flow": {
                "version": "2.0",
                "name": "测试",
                "nodes": [{"id": "n1", "name": "步骤", "code": "x", "next": "end"}],
            },
            "creator": "admin",
            "auto_release": True,
            "scope_type": "biz",
            "scope_value": "123",
        }
        ser = Ser(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)


class TestCreateTemplateWithA2FlowV2View(TestCase):
    """v2 API 视图测试"""

    def create_space(self):
        return Space.objects.create(app_code="test_v2", platform_url="http://test.com", name="space_v2")

    def _mock_component_model(self, mock_cm, codes_versions=None):
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

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_v2_create_template_success(self, mock_cm, mock_bkp):
        self._mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False
        space = self.create_space()

        data = {
            "a2flow": {
                "version": "2.0",
                "name": "v2测试流程",
                "nodes": [{"id": "n1", "name": "等待", "code": "sleep_timer", "data": {"bk_timing": 5}, "next": "end"}],
            }
        }
        resp = self.client.post(
            "/apigw/space/{}/create_template_with_a2flow/".format(space.id),
            data=json.dumps(data),
            content_type="application/json",
        )
        result = resp.json()
        self.assertTrue(result.get("result"), result)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_v2_missing_version_defaults_to_success(self, mock_cm, mock_bkp):
        self._mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False
        space = self.create_space()

        data = {
            "a2flow": {
                "name": "v2默认版本流程",
                "nodes": [{"id": "n1", "name": "等待", "code": "sleep_timer", "data": {"bk_timing": 5}, "next": "end"}],
            }
        }
        resp = self.client.post(
            "/apigw/space/{}/create_template_with_a2flow/".format(space.id),
            data=json.dumps(data),
            content_type="application/json",
        )
        result = resp.json()
        self.assertTrue(result.get("result"), result)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_v2_validation_error_returns_structured(self):
        space = self.create_space()
        data = {
            "a2flow": {
                "version": "2.0",
                "name": "错误流程",
                "nodes": [{"id": "n1", "name": "x", "code": "y", "next": "nonexistent"}],
            }
        }
        resp = self.client.post(
            "/apigw/space/{}/create_template_with_a2flow/".format(space.id),
            data=json.dumps(data),
            content_type="application/json",
        )
        result = resp.json()
        self.assertFalse(result.get("result"))
        self.assertIn("errors", result)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_v2_unsupported_version_returns_structured(self):
        space = self.create_space()
        data = {
            "a2flow": {
                "version": "9.9",
                "name": "错误版本",
                "nodes": [{"id": "n1", "name": "x", "code": "y", "next": "end"}],
            }
        }
        resp = self.client.post(
            "/apigw/space/{}/create_template_with_a2flow/".format(space.id),
            data=json.dumps(data),
            content_type="application/json",
        )
        result = resp.json()
        self.assertFalse(result.get("result"))
        self.assertIn("errors", result)
        self.assertEqual(result["errors"][0]["type"], "UNSUPPORTED_VERSION")
