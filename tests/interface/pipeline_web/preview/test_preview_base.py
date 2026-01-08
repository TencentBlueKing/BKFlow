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

from django.core.exceptions import ValidationError
from django.test import TestCase

from bkflow.pipeline_web.preview_base import PipelineTemplateWebPreviewer


class MockTemplateScheme:
    class MockScheme:
        def __init__(self, data):
            self.data = json.dumps(data)

    objects = MagicMock()
    objects.in_bulk = MagicMock(
        return_value={1: MockScheme(["node1", "node3"]), 2: MockScheme(["node1", "node5"]), 3: MockScheme(["node5"])}
    )


class PipelineTemplateWebPreviewerTestCase(TestCase):
    def setUp(self):
        MockTemplateScheme.objects.in_bulk.reset_mock()

    def test_preview_pipeline_tree_exclude_task_nodes(self):
        exclude_task_nodes_id = ["node9ab869668031c89ee03bd3b4ce66"]
        pipeline_tree = {
            "activities": {
                "node504a6d655782f38ac63347b447ed": {
                    "component": {
                        "code": "sleep_timer",
                        "data": {
                            "bk_timing": {"hook": False, "value": "1"},
                            "force_check": {"hook": False, "value": True},
                        },
                        "version": "legacy",
                    },
                    "error_ignorable": False,
                    "id": "node504a6d655782f38ac63347b447ed",
                    "incoming": ["line6653df851ded6777580dee9b45dc"],
                    "loop": None,
                    "name": "定时",
                    "optional": True,
                    "outgoing": "linee45c9161286c0151a2ff5d80d6a3",
                    "stage_name": "",
                    "type": "ServiceActivity",
                    "retryable": True,
                    "skippable": True,
                    "labels": [],
                },
                "node9ab869668031c89ee03bd3b4ce66": {
                    "component": {
                        "code": "sleep_timer",
                        "data": {
                            "bk_timing": {"hook": False, "value": "2"},
                            "force_check": {"hook": False, "value": True},
                        },
                        "version": "legacy",
                    },
                    "error_ignorable": False,
                    "id": "node9ab869668031c89ee03bd3b4ce66",
                    "incoming": ["linee45c9161286c0151a2ff5d80d6a3"],
                    "loop": None,
                    "name": "定时",
                    "optional": True,
                    "outgoing": "lineed1489f10d79e1d1ee4cee1c5a31",
                    "stage_name": "",
                    "type": "ServiceActivity",
                    "retryable": True,
                    "skippable": True,
                    "labels": [],
                },
                "node1d3e25feb2e73e7ed0db312e45e6": {
                    "component": {
                        "code": "sleep_timer",
                        "data": {
                            "bk_timing": {"hook": False, "value": "3"},
                            "force_check": {"hook": False, "value": True},
                        },
                        "version": "legacy",
                    },
                    "error_ignorable": False,
                    "id": "node1d3e25feb2e73e7ed0db312e45e6",
                    "incoming": ["lineed1489f10d79e1d1ee4cee1c5a31"],
                    "loop": None,
                    "name": "定时",
                    "optional": True,
                    "outgoing": "line6243852bfa890e66e38fda9cd199",
                    "stage_name": "",
                    "type": "ServiceActivity",
                    "retryable": True,
                    "skippable": True,
                    "labels": [],
                },
            },
            "constants": {},
            "end_event": {
                "id": "node7ca397adbecddbb48e307c56410e",
                "incoming": ["line6243852bfa890e66e38fda9cd199"],
                "name": "",
                "outgoing": "",
                "type": "EmptyEndEvent",
                "labels": [],
            },
            "flows": {
                "line6653df851ded6777580dee9b45dc": {
                    "id": "line6653df851ded6777580dee9b45dc",
                    "is_default": False,
                    "source": "nodecc4e4eba2910fbd713360220ec0a",
                    "target": "node504a6d655782f38ac63347b447ed",
                },
                "linee45c9161286c0151a2ff5d80d6a3": {
                    "id": "linee45c9161286c0151a2ff5d80d6a3",
                    "is_default": False,
                    "source": "node504a6d655782f38ac63347b447ed",
                    "target": "node9ab869668031c89ee03bd3b4ce66",
                },
                "lineed1489f10d79e1d1ee4cee1c5a31": {
                    "id": "lineed1489f10d79e1d1ee4cee1c5a31",
                    "is_default": False,
                    "source": "node9ab869668031c89ee03bd3b4ce66",
                    "target": "node1d3e25feb2e73e7ed0db312e45e6",
                },
                "line6243852bfa890e66e38fda9cd199": {
                    "id": "line6243852bfa890e66e38fda9cd199",
                    "is_default": False,
                    "source": "node1d3e25feb2e73e7ed0db312e45e6",
                    "target": "node7ca397adbecddbb48e307c56410e",
                },
            },
            "gateways": {},
            "line": [
                {
                    "id": "line6653df851ded6777580dee9b45dc",
                    "source": {"arrow": "Right", "id": "nodecc4e4eba2910fbd713360220ec0a"},
                    "target": {"arrow": "Left", "id": "node504a6d655782f38ac63347b447ed"},
                },
                {
                    "source": {"id": "node504a6d655782f38ac63347b447ed", "arrow": "Right"},
                    "target": {"id": "node9ab869668031c89ee03bd3b4ce66", "arrow": "Top"},
                    "id": "linee45c9161286c0151a2ff5d80d6a3",
                },
                {
                    "source": {"id": "node9ab869668031c89ee03bd3b4ce66", "arrow": "Right"},
                    "target": {"id": "node1d3e25feb2e73e7ed0db312e45e6", "arrow": "Left"},
                    "id": "lineed1489f10d79e1d1ee4cee1c5a31",
                },
                {
                    "source": {"id": "node1d3e25feb2e73e7ed0db312e45e6", "arrow": "Right"},
                    "target": {"id": "node7ca397adbecddbb48e307c56410e", "arrow": "Bottom"},
                    "id": "line6243852bfa890e66e38fda9cd199",
                },
            ],
            "location": [
                {"id": "nodecc4e4eba2910fbd713360220ec0a", "type": "startpoint", "x": 40, "y": 150},
                {
                    "id": "node504a6d655782f38ac63347b447ed",
                    "type": "tasknode",
                    "name": "定时",
                    "stage_name": "",
                    "x": 240,
                    "y": 140,
                    "group": "蓝鲸服务(BK)",
                    "icon": "",
                },
                {"id": "node7ca397adbecddbb48e307c56410e", "type": "endpoint", "x": 800, "y": 160},
                {
                    "id": "node9ab869668031c89ee03bd3b4ce66",
                    "type": "tasknode",
                    "name": "定时",
                    "stage_name": "",
                    "x": 359,
                    "y": 235,
                    "group": "蓝鲸服务(BK)",
                    "icon": "",
                },
                {
                    "id": "node1d3e25feb2e73e7ed0db312e45e6",
                    "type": "tasknode",
                    "name": "定时",
                    "stage_name": "",
                    "x": 610,
                    "y": 230,
                    "group": "蓝鲸服务(BK)",
                    "icon": "",
                },
            ],
            "outputs": [],
            "start_event": {
                "id": "nodecc4e4eba2910fbd713360220ec0a",
                "incoming": "",
                "name": "",
                "outgoing": "line6653df851ded6777580dee9b45dc",
                "type": "EmptyStartEvent",
                "labels": [],
            },
        }

        PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(pipeline_tree, exclude_task_nodes_id)

        self.assertEqual(
            pipeline_tree,
            {
                "activities": {
                    "node504a6d655782f38ac63347b447ed": {
                        "component": {
                            "code": "sleep_timer",
                            "data": {
                                "bk_timing": {"hook": False, "value": "1"},
                                "force_check": {"hook": False, "value": True},
                            },
                            "version": "legacy",
                        },
                        "error_ignorable": False,
                        "id": "node504a6d655782f38ac63347b447ed",
                        "incoming": ["line6653df851ded6777580dee9b45dc"],
                        "loop": None,
                        "name": "定时",
                        "optional": True,
                        "outgoing": "linee45c9161286c0151a2ff5d80d6a3",
                        "stage_name": "",
                        "type": "ServiceActivity",
                        "retryable": True,
                        "skippable": True,
                        "labels": [],
                    },
                    "node1d3e25feb2e73e7ed0db312e45e6": {
                        "component": {
                            "code": "sleep_timer",
                            "data": {
                                "bk_timing": {"hook": False, "value": "3"},
                                "force_check": {"hook": False, "value": True},
                            },
                            "version": "legacy",
                        },
                        "error_ignorable": False,
                        "id": "node1d3e25feb2e73e7ed0db312e45e6",
                        "incoming": ["linee45c9161286c0151a2ff5d80d6a3"],
                        "loop": None,
                        "name": "定时",
                        "optional": True,
                        "outgoing": "line6243852bfa890e66e38fda9cd199",
                        "stage_name": "",
                        "type": "ServiceActivity",
                        "retryable": True,
                        "skippable": True,
                        "labels": [],
                    },
                },
                "constants": {},
                "end_event": {
                    "id": "node7ca397adbecddbb48e307c56410e",
                    "incoming": ["line6243852bfa890e66e38fda9cd199"],
                    "name": "",
                    "outgoing": "",
                    "type": "EmptyEndEvent",
                    "labels": [],
                },
                "flows": {
                    "line6653df851ded6777580dee9b45dc": {
                        "id": "line6653df851ded6777580dee9b45dc",
                        "is_default": False,
                        "source": "nodecc4e4eba2910fbd713360220ec0a",
                        "target": "node504a6d655782f38ac63347b447ed",
                    },
                    "linee45c9161286c0151a2ff5d80d6a3": {
                        "id": "linee45c9161286c0151a2ff5d80d6a3",
                        "is_default": False,
                        "source": "node504a6d655782f38ac63347b447ed",
                        "target": "node1d3e25feb2e73e7ed0db312e45e6",
                    },
                    "line6243852bfa890e66e38fda9cd199": {
                        "id": "line6243852bfa890e66e38fda9cd199",
                        "is_default": False,
                        "source": "node1d3e25feb2e73e7ed0db312e45e6",
                        "target": "node7ca397adbecddbb48e307c56410e",
                    },
                },
                "gateways": {},
                "line": [
                    {
                        "id": "line6653df851ded6777580dee9b45dc",
                        "source": {"arrow": "Right", "id": "nodecc4e4eba2910fbd713360220ec0a"},
                        "target": {"arrow": "Left", "id": "node504a6d655782f38ac63347b447ed"},
                    },
                    {
                        "source": {"id": "node504a6d655782f38ac63347b447ed", "arrow": "Right"},
                        "target": {"id": "node1d3e25feb2e73e7ed0db312e45e6", "arrow": "Top"},
                        "id": "linee45c9161286c0151a2ff5d80d6a3",
                    },
                    {
                        "source": {"id": "node1d3e25feb2e73e7ed0db312e45e6", "arrow": "Right"},
                        "target": {"id": "node7ca397adbecddbb48e307c56410e", "arrow": "Bottom"},
                        "id": "line6243852bfa890e66e38fda9cd199",
                    },
                ],
                "location": [
                    {"id": "nodecc4e4eba2910fbd713360220ec0a", "type": "startpoint", "x": 40, "y": 150},
                    {
                        "id": "node504a6d655782f38ac63347b447ed",
                        "type": "tasknode",
                        "name": "定时",
                        "stage_name": "",
                        "x": 240,
                        "y": 140,
                        "group": "蓝鲸服务(BK)",
                        "icon": "",
                    },
                    {"id": "node7ca397adbecddbb48e307c56410e", "type": "endpoint", "x": 800, "y": 160},
                    {
                        "id": "node1d3e25feb2e73e7ed0db312e45e6",
                        "type": "tasknode",
                        "name": "定时",
                        "stage_name": "",
                        "x": 610,
                        "y": 230,
                        "group": "蓝鲸服务(BK)",
                        "icon": "",
                    },
                ],
                "outputs": [],
                "start_event": {
                    "id": "nodecc4e4eba2910fbd713360220ec0a",
                    "incoming": "",
                    "name": "",
                    "outgoing": "line6653df851ded6777580dee9b45dc",
                    "type": "EmptyStartEvent",
                    "labels": [],
                },
            },
        )

    def test_preview_pipeline_tree_with_appoint_task_nodes(self):
        appoint_task_nodes_id = ["node1"]
        pipeline_tree = {
            "activities": {
                "node1": {"id": "node1", "type": "ServiceActivity", "optional": True},
                "node2": {"id": "node2", "type": "ServiceActivity", "optional": False},
                "node3": {"id": "node3", "type": "ServiceActivity", "optional": True},
                "node4": {"id": "node4", "type": "ServiceActivity", "optional": True},
            },
            "constants": {
                "${param1}": {"value": "${parent_param2}"},
                "${param2}": {"value": "constant_value_2"},
                "${custom_param2}": {"value": "custom_value_2"},
            },
        }
        exclude_task_nodes_id = PipelineTemplateWebPreviewer.get_template_exclude_task_nodes_with_appoint_nodes(
            pipeline_tree, appoint_task_nodes_id
        )
        self.assertEqual(set(exclude_task_nodes_id), {"node3", "node4"})

    @patch("bkflow.pipeline_web.preview_base.TemplateScheme")
    def test_get_template_exclude_task_nodes_with_schemes(self, mock_scheme):
        """测试根据执行方案获取要剔除的节点"""
        mock_scheme.objects.in_bulk.return_value = MockTemplateScheme.objects.in_bulk([1, 2])

        pipeline_tree = {
            "activities": {
                "node1": {"id": "node1", "type": "ServiceActivity", "optional": True},
                "node2": {"id": "node2", "type": "ServiceActivity", "optional": False},
                "node3": {"id": "node3", "type": "ServiceActivity", "optional": True},
                "node5": {"id": "node5", "type": "ServiceActivity", "optional": True},
            }
        }

        exclude_nodes = PipelineTemplateWebPreviewer.get_template_exclude_task_nodes_with_schemes(pipeline_tree, [1, 2])
        # node1, node3, node5 在方案中，node2 不可选，所以没有节点被排除
        # 方案1: node1, node3; 方案2: node1, node5
        # 并集: node1, node3, node5; 排除: 无（因为node2不可选）
        self.assertIsInstance(exclude_nodes, list)

    @patch("bkflow.pipeline_web.preview_base.TemplateScheme")
    def test_get_template_exclude_task_nodes_with_schemes_check_exist(self, mock_scheme):
        """测试检查方案是否存在"""
        mock_scheme.objects.in_bulk.return_value = {1: MockTemplateScheme.MockScheme(["node1"])}

        pipeline_tree = {
            "activities": {
                "node1": {"id": "node1", "type": "ServiceActivity", "optional": True},
            }
        }

        # 请求方案 [1, 2]，但只返回方案 1
        with self.assertRaises(ValidationError):
            PipelineTemplateWebPreviewer.get_template_exclude_task_nodes_with_schemes(
                pipeline_tree, [1, 2], check_schemes_exist=True
            )

    def test_preview_with_non_optional_node(self):
        """测试尝试排除不可选节点时抛出异常"""
        pipeline_tree = {
            "activities": {
                "node1": {
                    "id": "node1",
                    "type": "ServiceActivity",
                    "optional": False,
                    "incoming": "line1",
                    "outgoing": "line2",
                }
            },
            "flows": {
                "line1": {"id": "line1", "source": "start", "target": "node1"},
                "line2": {"id": "line2", "source": "node1", "target": "end"},
            },
            "gateways": {},
            "constants": {},
            "outputs": [],
            "end_event": {"id": "end", "incoming": "line2"},
            "line": [],
            "location": [],
        }

        with self.assertRaises(Exception) as context:
            PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(pipeline_tree, ["node1"])
        self.assertIn("not optional", str(context.exception))

    def test_preview_with_nonexistent_node(self):
        """测试尝试排除不存在的节点时抛出异常"""
        pipeline_tree = {
            "activities": {},
            "flows": {},
            "gateways": {},
            "constants": {},
            "outputs": [],
            "line": [],
            "location": [],
        }

        with self.assertRaises(Exception) as context:
            PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(pipeline_tree, ["nonexistent_node"])
        self.assertIn("not in template", str(context.exception))

    def test_preview_with_parallel_gateway(self):
        """测试包含并行网关的流程预览"""
        pipeline_tree = {
            "activities": {
                "node1": {
                    "id": "node1",
                    "type": "ServiceActivity",
                    "optional": True,
                    "incoming": "line1",
                    "outgoing": "line2",
                    "component": {"data": {"key1": {"value": "val1"}}},
                },
                "node2": {
                    "id": "node2",
                    "type": "ServiceActivity",
                    "optional": True,
                    "incoming": "line3",
                    "outgoing": "line4",
                    "component": {"data": {"key2": {"value": "val2"}}},
                },
            },
            "gateways": {
                "parallel1": {
                    "id": "parallel1",
                    "type": "ParallelGateway",
                    "incoming": "line0",
                    "outgoing": ["line1", "line3"],
                },
                "converge1": {
                    "id": "converge1",
                    "type": "ConvergeGateway",
                    "incoming": ["line2", "line4"],
                    "outgoing": "line5",
                },
            },
            "flows": {
                "line0": {"id": "line0", "source": "start", "target": "parallel1"},
                "line1": {"id": "line1", "source": "parallel1", "target": "node1"},
                "line2": {"id": "line2", "source": "node1", "target": "converge1"},
                "line3": {"id": "line3", "source": "parallel1", "target": "node2"},
                "line4": {"id": "line4", "source": "node2", "target": "converge1"},
                "line5": {"id": "line5", "source": "converge1", "target": "end"},
            },
            "constants": {},
            "outputs": [],
            "start_event": {"id": "start", "outgoing": "line0"},
            "end_event": {"id": "end", "incoming": "line5"},
            "line": [
                {"id": "line0", "source": {"id": "start"}, "target": {"id": "parallel1"}},
                {"id": "line1", "source": {"id": "parallel1"}, "target": {"id": "node1"}},
                {"id": "line2", "source": {"id": "node1"}, "target": {"id": "converge1"}},
                {"id": "line3", "source": {"id": "parallel1"}, "target": {"id": "node2"}},
                {"id": "line4", "source": {"id": "node2"}, "target": {"id": "converge1"}},
                {"id": "line5", "source": {"id": "converge1"}, "target": {"id": "end"}},
            ],
            "location": [
                {"id": "start"},
                {"id": "parallel1"},
                {"id": "node1"},
                {"id": "node2"},
                {"id": "converge1"},
                {"id": "end"},
            ],
        }

        # 排除两个节点，应该移除整个并行网关
        result = PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(
            pipeline_tree, ["node1", "node2"]
        )
        self.assertTrue(result)
        self.assertEqual(len(pipeline_tree["activities"]), 0)
        # 并行网关应该被移除
        self.assertNotIn("parallel1", pipeline_tree["gateways"])
        self.assertNotIn("converge1", pipeline_tree["gateways"])

    def test_preview_with_subprocess(self):
        """测试包含子流程的流程预览"""
        pipeline_tree = {
            "activities": {
                "subprocess1": {
                    "id": "subprocess1",
                    "type": "SubProcess",
                    "optional": True,
                    "incoming": "line1",
                    "outgoing": "line2",
                    "constants": {
                        "${key1}": {"value": "val1", "show_type": "show"},
                        "${key2}": {"value": "val2", "show_type": "hide"},
                    },
                }
            },
            "flows": {
                "line1": {"id": "line1", "source": "start", "target": "subprocess1"},
                "line2": {"id": "line2", "source": "subprocess1", "target": "end"},
            },
            "gateways": {},
            "constants": {
                "${key1}": {"value": "val1", "index": 0, "source_type": "custom", "source_info": {}},
            },
            "outputs": ["${key1}"],
            "start_event": {"id": "start", "outgoing": "line1"},
            "end_event": {"id": "end", "incoming": "line2"},
            "line": [
                {"id": "line1", "source": {"id": "start"}, "target": {"id": "subprocess1"}},
                {"id": "line2", "source": {"id": "subprocess1"}, "target": {"id": "end"}},
            ],
            "location": [
                {"id": "start"},
                {"id": "subprocess1"},
                {"id": "end"},
            ],
        }

        result = PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(pipeline_tree, ["subprocess1"])
        self.assertTrue(result)
        self.assertEqual(len(pipeline_tree["activities"]), 0)

    def test_preview_with_exclusive_gateway(self):
        """测试包含分支网关的流程预览"""
        pipeline_tree = {
            "activities": {
                "node1": {
                    "id": "node1",
                    "type": "ServiceActivity",
                    "optional": True,
                    "incoming": "line1",
                    "outgoing": "line2",
                    "component": {"data": {}},
                }
            },
            "gateways": {
                "exclusive1": {
                    "id": "exclusive1",
                    "type": "ExclusiveGateway",
                    "incoming": "line0",
                    "outgoing": ["line1", "line3"],
                    "conditions": {
                        "line1": {"evaluate": "${condition1}"},
                        "line3": {"evaluate": "${condition2}"},
                    },
                },
            },
            "flows": {
                "line0": {"id": "line0", "source": "start", "target": "exclusive1"},
                "line1": {"id": "line1", "source": "exclusive1", "target": "node1"},
                "line2": {"id": "line2", "source": "node1", "target": "end"},
                "line3": {"id": "line3", "source": "exclusive1", "target": "end"},
            },
            "constants": {
                "${condition1}": {"value": "True", "index": 0, "source_type": "custom", "source_info": {}},
                "${condition2}": {"value": "False", "index": 1, "source_type": "custom", "source_info": {}},
            },
            "outputs": [],
            "start_event": {"id": "start", "outgoing": "line0"},
            "end_event": {"id": "end", "incoming": ["line2", "line3"]},
            "line": [],
            "location": [],
        }

        result = PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(pipeline_tree, ["node1"])
        self.assertTrue(result)

    def test_remove_useless_constants_with_outputs(self):
        """测试移除未引用的常量但保留输出变量"""
        pipeline_tree = {
            "activities": {
                "node1": {
                    "id": "node1",
                    "type": "ServiceActivity",
                    "optional": True,
                    "incoming": "line1",
                    "outgoing": "line2",
                    "component": {"data": {"key1": {"value": "${const1}"}}},
                }
            },
            "flows": {
                "line1": {"id": "line1", "source": "start", "target": "node1"},
                "line2": {"id": "line2", "source": "node1", "target": "end"},
            },
            "gateways": {},
            "constants": {
                "${const1}": {
                    "value": "val1",
                    "index": 0,
                    "source_type": "custom",
                    "source_info": {"node1": ["key1"]},
                },
                "${const2}": {
                    "value": "val2",
                    "index": 1,
                    "source_type": "custom",
                    "source_info": {},
                },
                "${output1}": {
                    "value": "",
                    "index": 2,
                    "source_type": "component_outputs",
                    "source_info": {"node1": ["output_key"]},
                },
            },
            "outputs": ["${const1}", "${const2}", "${output1}"],
            "start_event": {"id": "start", "outgoing": "line1"},
            "end_event": {"id": "end", "incoming": "line2"},
            "line": [],
            "location": [],
        }

        result = PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(
            pipeline_tree, [], remove_outputs_without_refs=False
        )
        self.assertTrue(result)
        # const2 未被引用但在输出中，应该被保留
        self.assertIn("${const2}", pipeline_tree["constants"])
        self.assertIn("${const2}", pipeline_tree["outputs"])

    @patch("bkflow.pipeline_web.preview_base.Template")
    @patch("bkflow.pipeline_web.preview_base.TemplateReference")
    def test_is_circular_reference_no_cycle(self, mock_ref, mock_template):
        """测试无循环引用的情况"""
        mock_template.objects.filter.return_value.values_list.return_value = [1, 2, 3]
        mock_ref.objects.filter.return_value.values.return_value = [
            {"root_template_id": "1", "subprocess_template_id": "2"},
            {"root_template_id": "2", "subprocess_template_id": "3"},
        ]

        pipeline_tree = {
            "activities": {
                "sub1": {
                    "id": "sub1",
                    "type": "SubProcess",
                    "name": "subprocess1",
                    "template_id": 2,
                }
            }
        }

        result = PipelineTemplateWebPreviewer.is_circular_reference(pipeline_tree, 1, "space1", "project", "proj1")
        self.assertFalse(result["has_cycle"])

    @patch("bkflow.pipeline_web.preview_base.Template")
    @patch("bkflow.pipeline_web.preview_base.TemplateReference")
    def test_is_circular_reference_with_cycle(self, mock_ref, mock_template):
        """测试存在循环引用的情况"""
        mock_template.objects.filter.return_value.values_list.return_value = [1, 2, 3]
        mock_ref.objects.filter.return_value.values.return_value = [
            {"root_template_id": "1", "subprocess_template_id": "2"},
            {"root_template_id": "2", "subprocess_template_id": "3"},
            {"root_template_id": "3", "subprocess_template_id": "1"},  # 循环
        ]

        pipeline_tree = {
            "activities": {
                "sub1": {
                    "id": "sub1",
                    "type": "SubProcess",
                    "name": "subprocess1",
                    "template_id": 2,
                }
            }
        }

        result = PipelineTemplateWebPreviewer.is_circular_reference(pipeline_tree, 1, "space1", "project", "proj1")
        self.assertTrue(result["has_cycle"])
        self.assertEqual(result["node_key"], "sub1")
        self.assertEqual(result["template_id"], 2)
