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

from django.test import TestCase

from bkflow.pipeline_web.constants import PWE
from bkflow.pipeline_web.drawing_new.order import order


class TestOrder(TestCase):
    """测试 order 模块的各个函数"""

    def setUp(self):
        self.pipeline = {
            "all_nodes": {
                "node0": {PWE.id: "node0", PWE.incoming: "", PWE.outgoing: ["flow0", "flow1", "flow2"]},
                "node1": {PWE.id: "node1", PWE.incoming: "flow0", PWE.outgoing: ["flow3", "flow4"]},
                "node2": {PWE.id: "node2", PWE.incoming: "flow1", PWE.outgoing: ["flow5", "flow6", "flow7"]},
                "node3": {PWE.id: "node3", PWE.incoming: "flow2", PWE.outgoing: ["flow8", "flow9", "flow10"]},
                "node4": {PWE.id: "node4", PWE.incoming: ["flow3", "flow5", "flow8"], PWE.outgoing: ""},
                "node5": {PWE.id: "node5", PWE.incoming: ["flow4"], PWE.outgoing: ""},
                "node6": {PWE.id: "node6", PWE.incoming: ["flow6"], PWE.outgoing: ""},
                "node7": {PWE.id: "node7", PWE.incoming: ["flow7", "flow9"], PWE.outgoing: ""},
                "node8": {PWE.id: "node8", PWE.incoming: ["flow10"], PWE.outgoing: ""},
            },
            "flows": {
                "flow0": {PWE.id: "flow0", PWE.source: "node0", PWE.target: "node1"},
                "flow1": {PWE.id: "flow1", PWE.source: "node0", PWE.target: "node2"},
                "flow2": {PWE.id: "flow2", PWE.source: "node0", PWE.target: "node3"},
                "flow3": {PWE.id: "flow3", PWE.source: "node1", PWE.target: "node4"},
                "flow4": {PWE.id: "flow4", PWE.source: "node1", PWE.target: "node5"},
                "flow5": {PWE.id: "flow5", PWE.source: "node2", PWE.target: "node4"},
                "flow6": {PWE.id: "flow6", PWE.source: "node2", PWE.target: "node6"},
                "flow7": {PWE.id: "flow7", PWE.source: "node2", PWE.target: "node7"},
                "flow8": {PWE.id: "flow8", PWE.source: "node3", PWE.target: "node4"},
                "flow9": {PWE.id: "flow9", PWE.source: "node3", PWE.target: "node7"},
                "flow10": {PWE.id: "flow10", PWE.source: "node3", PWE.target: "node8"},
            },
        }
        self.ranks = {
            "node0": 0,
            "node1": 1,
            "node2": 1,
            "node3": 1,
            "node4": 2,
            "node5": 2,
            "node6": 2,
            "node7": 2,
            "node8": 2,
        }

    def test_init_order(self):
        """测试初始化 order"""
        orders = order.init_order(self.pipeline, self.ranks)
        self.assertEqual(
            orders, {0: ["node0"], 1: ["node1", "node2", "node3"], 2: ["node4", "node5", "node6", "node7", "node8"]}
        )

    def test_crossing_count(self):
        """测试计算交叉数"""
        orders = {0: ["node0"], 1: ["node1", "node2", "node3"], 2: ["node4", "node5", "node6", "node7", "node8"]}
        count = order.crossing_count(self.pipeline, orders)
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_sort_layer_and_median_value(self):
        """测试层内排序和中位值计算"""
        # Sort layer
        layer_order = ["a", "b", "c", "d", "e", "f"]
        weight = [3, 6, 2, 1, 5, 4]
        self.assertEqual(order.sort_layer(layer_order, weight), ["d", "c", "a", "f", "e", "b"])

        # Weight -1
        self.assertEqual(order.sort_layer(["a", "b"], [-1, -1]), ["a", "b"])

        # Mixed weights
        self.assertEqual(
            order.sort_layer(["a", "b", "c", "d", "e", "f"], [3, -1, 2, -1, 5, 4]), ["c", "b", "a", "d", "f", "e"]
        )

        # Median value
        refer_layer_orders = ["node1", "node2", "node3", "node4"]
        self.assertEqual(order.median_value(["node1"], refer_layer_orders), 0)
        self.assertEqual(order.median_value(["node1", "node4"], refer_layer_orders), 1.5)
        self.assertEqual(order.median_value(["node1", "node4", "node2"], refer_layer_orders), 1)

    def test_wmedian_and_edge_cases(self):
        """测试 wmedian 和边界情况"""
        # Wmedian
        orders = {0: ["node0"], 1: ["node1", "node2", "node3"], 2: ["node4", "node5", "node6", "node7", "node8"]}
        order.wmedian(self.pipeline, orders, 0, self.ranks)
        self.assertIsInstance(orders, dict)
        order.wmedian(self.pipeline, orders, 1, self.ranks)
        self.assertIsInstance(orders, dict)

        # Edge cases
        with self.assertRaises(ValueError):
            order.init_order({"all_nodes": {}, "flows": {}}, {})

        pipeline = {"all_nodes": {"node1": {PWE.id: "node1", PWE.incoming: "", PWE.outgoing: ""}}, "flows": {}}
        self.assertEqual(order.init_order(pipeline, {"node1": 0}), {0: ["node1"]})
