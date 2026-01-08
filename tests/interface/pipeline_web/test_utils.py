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

from copy import deepcopy

from django.test import TestCase

from bkflow.pipeline_plugins.components.collections.value_assign.v1_0_0 import (
    ValueAssignComponent,
)
from bkflow.pipeline_web import utils


class TestTopologySort(TestCase):
    def test_topology_sort(self):
        """测试拓扑排序"""
        # Simple
        relations = {"a": ["b"], "b": ["c"], "c": []}
        result = utils.topology_sort(relations)
        self.assertEqual(set(result), {"a", "b", "c"})
        self.assertLess(result.index("c"), result.index("b"))

        # Complex
        relations = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        result = utils.topology_sort(relations)
        self.assertEqual(set(result), {"a", "b", "c", "d"})
        self.assertLess(result.index("d"), result.index("b"))

        # Empty
        self.assertEqual(utils.topology_sort({}), [])

        # No dependencies
        result = utils.topology_sort({"a": [], "b": [], "c": []})
        self.assertEqual(set(result), {"a", "b", "c"})


class TestPreHandlePipelineTree(TestCase):
    def setUp(self):
        self.pipeline_tree = {
            "activities": {
                "node1": {
                    "type": "ServiceActivity",
                    "component": {
                        "code": ValueAssignComponent.code,
                        "data": {
                            "bk_assignment_list": {
                                "value": [
                                    {"key": "var1", "value": "value1"},
                                    {"key": "var2", "value": "value2"},
                                ]
                            }
                        },
                    },
                },
                "node2": {
                    "type": "ServiceActivity",
                    "component": {
                        "code": "other_component",
                        "data": {},
                    },
                },
                "node3": {
                    "type": "SubProcess",
                    "component": {
                        "code": ValueAssignComponent.code,
                        "data": {
                            "bk_assignment_list": {
                                "value": [
                                    {"key": "var3", "value": "value3"},
                                ]
                            }
                        },
                    },
                },
            }
        }

    def test_pre_handle_pipeline_tree_with_value_assign(self):
        """测试预处理包含变量赋值节点的流程树"""
        utils.pre_handle_pipeline_tree(self.pipeline_tree)

        # node1 的 key 应该被添加 ${} 包裹
        assignments = self.pipeline_tree["activities"]["node1"]["component"]["data"]["bk_assignment_list"]["value"]
        self.assertEqual(assignments[0]["key"], "${var1}")
        self.assertEqual(assignments[1]["key"], "${var2}")

        # node2 不应该被修改
        self.assertEqual(self.pipeline_tree["activities"]["node2"]["component"]["code"], "other_component")

        # node3 是 SubProcess，不应该被处理
        assignments = self.pipeline_tree["activities"]["node3"]["component"]["data"]["bk_assignment_list"]["value"]
        self.assertEqual(assignments[0]["key"], "var3")


class TestPostHandlePipelineTree(TestCase):
    def setUp(self):
        self.pipeline_tree = {
            "activities": {
                "node1": {
                    "type": "ServiceActivity",
                    "component": {
                        "code": ValueAssignComponent.code,
                        "data": {
                            "bk_assignment_list": {
                                "value": [
                                    {"key": "${var1}", "value": "value1"},
                                    {"key": "${var2}", "value": "value2"},
                                    {"key": "var3", "value": "value3"},  # 没有 ${} 包裹的
                                ]
                            }
                        },
                    },
                },
                "node2": {
                    "type": "ServiceActivity",
                    "component": {
                        "code": "other_component",
                        "data": {},
                    },
                },
                "node3": {
                    "type": "SubProcess",
                    "component": {
                        "code": ValueAssignComponent.code,
                        "data": {
                            "bk_assignment_list": {
                                "value": [
                                    {"key": "${var4}", "value": "value4"},
                                ]
                            }
                        },
                    },
                },
            }
        }

    def test_post_handle_pipeline_tree_with_wrapped_keys(self):
        """测试后处理包含 ${} 包裹的 key"""
        utils.post_handle_pipeline_tree(self.pipeline_tree)

        # node1 的 key 应该被去除 ${} 包裹
        assignments = self.pipeline_tree["activities"]["node1"]["component"]["data"]["bk_assignment_list"]["value"]
        self.assertEqual(assignments[0]["key"], "var1")
        self.assertEqual(assignments[1]["key"], "var2")
        # 没有 ${} 包裹的应该保持不变
        self.assertEqual(assignments[2]["key"], "var3")

        # node2 不应该被修改
        self.assertEqual(self.pipeline_tree["activities"]["node2"]["component"]["code"], "other_component")

        # node3 是 SubProcess，不应该被处理
        assignments = self.pipeline_tree["activities"]["node3"]["component"]["data"]["bk_assignment_list"]["value"]
        self.assertEqual(assignments[0]["key"], "${var4}")

    def test_pre_and_post_handle_roundtrip(self):
        """测试预处理和后处理的往返"""
        original_tree = {
            "activities": {
                "node1": {
                    "type": "ServiceActivity",
                    "component": {
                        "code": ValueAssignComponent.code,
                        "data": {
                            "bk_assignment_list": {
                                "value": [
                                    {"key": "var1", "value": "value1"},
                                    {"key": "var2", "value": "value2"},
                                ]
                            }
                        },
                    },
                },
            }
        }
        processed_tree = deepcopy(original_tree)
        utils.pre_handle_pipeline_tree(processed_tree)
        utils.post_handle_pipeline_tree(processed_tree)
        self.assertEqual(
            processed_tree["activities"]["node1"]["component"]["data"]["bk_assignment_list"]["value"],
            original_tree["activities"]["node1"]["component"]["data"]["bk_assignment_list"]["value"],
        )
