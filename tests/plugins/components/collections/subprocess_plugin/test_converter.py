"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy

from django.test import TestCase

from bkflow.pipeline_plugins.components.collections.subprocess_plugin.converter import (
    PipelineTreeSubprocessConverter,
)


class PipelineTreeSubprocessConverterTest(TestCase):
    """PipelineTreeSubprocessConverter 单元测试"""

    def setUp(self):
        """测试前置设置"""
        self.sample_pipeline_tree = {
            "activities": {
                "node1": {
                    "id": "node1",
                    "name": "普通节点",
                    "type": "ServiceActivity",
                    "component": {"code": "normal_plugin"},
                },
                "node2": {
                    "id": "node2",
                    "name": "子流程节点",
                    "type": "SubProcess",
                    "template_id": "template_123",
                    "version": "v1.0.0",
                    "always_use_latest": False,
                    "constants": {"key1": "value1"},
                    "optional": True,
                    "outgoing": "node3",
                    "stage_name": "stage1",
                    "labels": ["label1"],
                    "incoming": "node1",
                    "original_template_id": "original_123",
                    "original_template_version": "v0.1.0",
                    "error_ignorable": True,
                    "skippable": False,
                    "retryable": True,
                    "timeout_config": {"enabled": True, "seconds": 30},
                    "auto_retry": {"enabled": True, "interval": 5, "times": 3},
                    "template_node_id": "template_node_123",
                },
            },
            "constants": [
                ("constant1", {"value": "old_value1"}),
                ("constant2", {"value": "old_value2"}),
            ],
            "location": [
                {"type": "tasknode", "id": "node1"},
                {"type": "subflow", "id": "node2"},
            ],
        }

    def test_init_without_constants(self):
        """测试初始化时不提供constants参数"""
        converter = PipelineTreeSubprocessConverter(self.sample_pipeline_tree)
        self.assertEqual(converter.pipeline_tree, self.sample_pipeline_tree)
        self.assertEqual(converter.constants, {})

    def test_init_with_constants(self):
        """测试初始化时提供constants参数"""
        constants = {"constant1": "new_value1", "constant2": "new_value2"}
        converter = PipelineTreeSubprocessConverter(self.sample_pipeline_tree, constants)
        self.assertEqual(converter.pipeline_tree, self.sample_pipeline_tree)
        self.assertEqual(converter.constants, constants)

    def test_pre_convert_method_exists(self):
        """测试pre_convert方法存在且可调用"""
        converter = PipelineTreeSubprocessConverter(self.sample_pipeline_tree)
        converter.pre_convert()

    def test_get_converted_subprocess_basic_conversion(self):
        """测试get_converted_subprocess方法的基本转换功能"""
        converter = PipelineTreeSubprocessConverter(self.sample_pipeline_tree)
        original_data = self.sample_pipeline_tree["activities"]["node2"]

        converted_data = converter.get_converted_subprocess(original_data)

        self.assertEqual(converted_data["id"], "node2")
        self.assertEqual(converted_data["name"], "子流程节点")
        self.assertEqual(converted_data["optional"], True)
        self.assertEqual(converted_data["stage_name"], "stage1")
        self.assertEqual(converted_data["labels"], ["label1"])
        self.assertEqual(converted_data["error_ignorable"], True)
        self.assertEqual(converted_data["skippable"], False)
        self.assertEqual(converted_data["retryable"], True)
        self.assertEqual(converted_data["timeout_config"], {"enabled": True, "seconds": 30})
        self.assertEqual(converted_data["auto_retry"], {"enabled": True, "interval": 5, "times": 3})
        self.assertEqual(converted_data["template_node_id"], "template_node_123")

        component_data = converted_data["component"]["data"]["subprocess"]["value"]
        self.assertEqual(component_data["template_id"], "template_123")
        self.assertEqual(component_data["version"], "v1.0.0")
        self.assertEqual(component_data["always_use_latest"], False)
        self.assertEqual(component_data["constants"], {"key1": "value1"})
        self.assertEqual(component_data["subprocess_name"], "子流程节点")

        self.assertEqual(converted_data["type"], "ServiceActivity")
        self.assertEqual(converted_data["component"]["code"], "subprocess_plugin")
        self.assertEqual(converted_data["component"]["version"], "1.0.0")

    def test_get_converted_subprocess_without_convert_fields(self):
        """测试没有转换字段的情况"""
        converter = PipelineTreeSubprocessConverter(self.sample_pipeline_tree)
        original_data = {
            "id": "node3",
            "name": "简单节点",
            "type": "SubProcess",
            "optional": False,
        }

        converted_data = converter.get_converted_subprocess(original_data)

        self.assertEqual(converted_data["id"], "node3")
        self.assertEqual(converted_data["name"], "简单节点")
        self.assertEqual(converted_data["optional"], False)

        component_data = converted_data["component"]["data"]["subprocess"]["value"]
        self.assertEqual(component_data["subprocess_name"], "简单节点")
        self.assertEqual(len(component_data), 1)  # 只有subprocess_name

    def test_convert_method(self):
        """测试convert方法的完整转换流程"""
        constants = {"constant1": "updated_value1"}
        converter = PipelineTreeSubprocessConverter(self.sample_pipeline_tree, constants)

        converter.convert()

        activities = converter.pipeline_tree["activities"]
        self.assertEqual(activities["node1"]["type"], "ServiceActivity")
        self.assertEqual(activities["node2"]["type"], "ServiceActivity")

        converted_node = activities["node2"]
        self.assertEqual(converted_node["component"]["code"], "subprocess_plugin")

        constants_list = converter.pipeline_tree["constants"]
        for key, constant in constants_list:
            if key == "constant1":
                self.assertEqual(constant["value"], "updated_value1")
            elif key == "constant2":
                self.assertEqual(constant["value"], "old_value2")

        locations = converter.pipeline_tree["location"]
        for location in locations:
            if location["id"] == "node2":
                self.assertEqual(location["type"], "tasknode")

    def test_convert_method_without_subprocess_nodes(self):
        """测试没有SubProcess节点时的convert方法"""
        pipeline_tree = {
            "activities": {
                "node1": {
                    "id": "node1",
                    "name": "普通节点1",
                    "type": "ServiceActivity",
                },
                "node2": {
                    "id": "node2",
                    "name": "普通节点2",
                    "type": "ServiceActivity",
                },
            },
            "constants": [],
            "location": [
                {"type": "tasknode", "id": "node1"},
                {"type": "tasknode", "id": "node2"},
            ],
        }

        converter = PipelineTreeSubprocessConverter(pipeline_tree)
        original_activities = copy.deepcopy(pipeline_tree["activities"])

        converter.convert()

        self.assertEqual(converter.pipeline_tree["activities"], original_activities)
        self.assertEqual(converter.pipeline_tree["location"], pipeline_tree["location"])

    def test_convert_method_without_constants(self):
        """测试没有提供constants时的convert方法"""
        pipeline_tree = {
            "activities": {
                "node1": {
                    "id": "node1",
                    "name": "子流程节点",
                    "type": "SubProcess",
                    "template_id": "template_123",
                },
            },
            "constants": [
                ("constant1", {"value": "old_value1"}),
            ],
            "location": [
                {"type": "subflow", "id": "node1"},
            ],
        }

        converter = PipelineTreeSubprocessConverter(pipeline_tree)
        original_constants = copy.deepcopy(pipeline_tree["constants"])

        converter.convert()

        self.assertEqual(converter.pipeline_tree["constants"], original_constants)
