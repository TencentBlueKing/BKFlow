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

from bamboo_engine.builder import (
    EmptyEndEvent,
    EmptyStartEvent,
    ServiceActivity,
    build_tree,
)
from django.test import TestCase, override_settings

from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot


def build_pipeline_tree_with_constants():
    """构建包含 constants 和 outputs 的 pipeline tree"""
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="example_component")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start, data={"test": "test"})

    # 添加 constants 和 outputs
    pipeline["constants"] = {
        "${input_param}": {
            "key": "${input_param}",
            "name": "输入参数",
            "value": "",
            "show_type": "show",
            "source_type": "custom",
            "desc": "这是一个输入参数",
            "custom_type": "string",
            "index": 0,
        },
        "${output_param}": {
            "key": "${output_param}",
            "name": "输出参数",
            "value": "default_value",
            "show_type": "show",
            "source_type": "custom",
            "desc": "这是一个输出参数",
            "custom_type": "string",
            "index": 1,
        },
    }
    pipeline["outputs"] = ["${output_param}"]

    return pipeline


class TestGetTemplateDetail(TestCase):
    """Test get_template_detail view"""

    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")

    def build_pipeline_tree(self):
        return build_pipeline_tree_with_constants()

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_template_detail_default_format(self):
        """Test get_template_detail with default format (raw)"""
        pipeline_tree = self.build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_user", version="1.0.0")
        template = Template.objects.create(
            name="测试流程",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            desc="测试描述",
            creator="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        url = "/apigw/space/{}/template/{}/get_template_detail/".format(self.space.id, template.id)
        resp = self.client.get(path=url)

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertIn("data", resp_data)
        self.assertEqual(resp_data["data"]["name"], "测试流程")
        self.assertIn("pipeline_tree", resp_data["data"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_template_detail_plugin_format(self):
        """Test get_template_detail with format=plugin"""
        pipeline_tree = self.build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_user", version="1.0.0")
        template = Template.objects.create(
            name="测试流程",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            desc="测试描述",
            creator="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        url = "/apigw/space/{}/template/{}/get_template_detail/?format=plugin".format(self.space.id, template.id)
        resp = self.client.get(path=url)

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertIn("data", resp_data)

        data = resp_data["data"]
        # 检查基本字段
        self.assertEqual(data["id"], template.id)
        self.assertEqual(data["name"], "测试流程")
        self.assertEqual(data["desc"], "测试描述")
        self.assertEqual(data["space_id"], self.space.id)

        # 检查插件格式字段
        self.assertIn("inputs", data)
        self.assertIn("outputs", data)
        self.assertIn("context_inputs", data)

        # 检查 inputs 结构
        self.assertIn("type", data["inputs"])
        self.assertIn("properties", data["inputs"])
        self.assertEqual(data["inputs"]["type"], "object")
        self.assertIn("input_param", data["inputs"]["properties"])

        # 检查 outputs 结构
        self.assertIn("type", data["outputs"])
        self.assertIn("properties", data["outputs"])
        self.assertEqual(data["outputs"]["type"], "object")
        self.assertIn("output_param", data["outputs"]["properties"])

        # 检查 context_inputs 结构
        self.assertIn("type", data["context_inputs"])
        self.assertIn("properties", data["context_inputs"])
        self.assertEqual(data["context_inputs"]["type"], "object")
        self.assertIn("executor", data["context_inputs"]["properties"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_template_detail_not_found(self):
        """Test get_template_detail with non-existent template"""
        url = "/apigw/space/{}/template/99999/get_template_detail/".format(self.space.id)
        resp = self.client.get(path=url)

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertIn("message", resp_data)


class TestGetTemplateDetailByApp(TestCase):
    """Test get_template_detail_by_app view"""

    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")

    def build_pipeline_tree(self):
        return build_pipeline_tree_with_constants()

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_template_detail_by_app_default_format(self):
        """Test get_template_detail_by_app with default format (raw)"""
        pipeline_tree = self.build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_user", version="1.0.0")
        template = Template.objects.create(
            name="测试流程",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            desc="测试描述",
            creator="test_user",
            bk_app_code="test",
        )
        snapshot.template_id = template.id
        snapshot.save()

        url = "/apigw/template/{}/get_template_detail_by_app/".format(template.id)
        resp = self.client.get(path=url)

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertIn("data", resp_data)
        self.assertEqual(resp_data["data"]["name"], "测试流程")
        self.assertIn("pipeline_tree", resp_data["data"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_template_detail_by_app_plugin_format(self):
        """Test get_template_detail_by_app with format=plugin"""
        pipeline_tree = self.build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_user", version="1.0.0")
        template = Template.objects.create(
            name="测试流程",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            desc="测试描述",
            creator="test_user",
            bk_app_code="test",
        )
        snapshot.template_id = template.id
        snapshot.save()

        url = "/apigw/template/{}/get_template_detail_by_app/?format=plugin".format(template.id)
        resp = self.client.get(path=url)

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertIn("data", resp_data)

        data = resp_data["data"]
        # 检查基本字段
        self.assertEqual(data["id"], template.id)
        self.assertEqual(data["name"], "测试流程")
        self.assertEqual(data["desc"], "测试描述")
        self.assertEqual(data["space_id"], self.space.id)
        self.assertEqual(data["bk_app_code"], "test")

        # 检查插件格式字段
        self.assertIn("inputs", data)
        self.assertIn("outputs", data)
        self.assertIn("context_inputs", data)

        # 检查 inputs 结构
        self.assertIn("type", data["inputs"])
        self.assertIn("properties", data["inputs"])
        self.assertEqual(data["inputs"]["type"], "object")
        self.assertIn("input_param", data["inputs"]["properties"])

        # 检查 outputs 结构
        self.assertIn("type", data["outputs"])
        self.assertIn("properties", data["outputs"])
        self.assertEqual(data["outputs"]["type"], "object")
        self.assertIn("output_param", data["outputs"]["properties"])

        # 检查 context_inputs 结构
        self.assertIn("type", data["context_inputs"])
        self.assertIn("properties", data["context_inputs"])
        self.assertEqual(data["context_inputs"]["type"], "object")
        self.assertIn("executor", data["context_inputs"]["properties"])
