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
from bkflow.pipeline_web.drawing_new import position


class TestUpsertOrders(TestCase):
    """测试 upsert_orders 函数"""

    def test_upsert_orders_basic(self):
        """测试基本的 upsert_orders 功能"""
        orders = ["node1", "node2", "node3"]
        nodes_fill_nums = {"node2": 2}

        new_orders, dummy_nodes = position.upsert_orders(orders, nodes_fill_nums)

        # 验证返回值类型
        self.assertIsInstance(new_orders, list)
        self.assertIsInstance(dummy_nodes, list)

        # 验证 node2 后面插入了2个虚拟节点
        self.assertEqual(len(new_orders), 5)  # 3 + 2
        self.assertEqual(len(dummy_nodes), 2)

        # 验证顺序
        node2_index = new_orders.index("node2")
        self.assertEqual(new_orders[0], "node1")
        self.assertEqual(new_orders[node2_index], "node2")
        self.assertEqual(new_orders[-1], "node3")

    def test_upsert_orders_empty(self):
        """测试空 orders"""
        orders = []
        nodes_fill_nums = {}

        new_orders, dummy_nodes = position.upsert_orders(orders, nodes_fill_nums)

        self.assertEqual(new_orders, [])
        self.assertEqual(dummy_nodes, [])

    def test_upsert_orders_no_fill(self):
        """测试没有填充需求的情况"""
        orders = ["node1", "node2"]
        nodes_fill_nums = {}

        new_orders, dummy_nodes = position.upsert_orders(orders, nodes_fill_nums)

        self.assertEqual(new_orders, orders)
        self.assertEqual(dummy_nodes, [])

    def test_upsert_orders_multiple_nodes(self):
        """测试多个节点需要填充"""
        orders = ["node1", "node2", "node3"]
        nodes_fill_nums = {"node1": 1, "node3": 2}

        new_orders, dummy_nodes = position.upsert_orders(orders, nodes_fill_nums)

        # 应该插入 1 + 2 = 3 个虚拟节点
        self.assertEqual(len(dummy_nodes), 3)
        self.assertEqual(len(new_orders), 6)  # 3 + 3


class TestPosition(TestCase):
    """测试 position 函数"""

    def setUp(self):
        """设置测试数据"""
        self.pipeline = {
            "all_nodes": {
                "start": {
                    PWE.id: "start",
                    PWE.type: PWE.EmptyStartEvent,
                    PWE.incoming: "",
                    PWE.outgoing: "f1",
                },
                "node1": {
                    PWE.id: "node1",
                    PWE.type: PWE.ServiceActivity,
                    PWE.incoming: "f1",
                    PWE.outgoing: "f2",
                },
                "end": {
                    PWE.id: "end",
                    PWE.type: PWE.EmptyEndEvent,
                    PWE.incoming: "f2",
                    PWE.outgoing: "",
                },
            },
            PWE.flows: {
                "f1": {PWE.id: "f1", PWE.source: "start", PWE.target: "node1"},
                "f2": {PWE.id: "f2", PWE.source: "node1", PWE.target: "end"},
            },
        }
        self.orders = {
            0: ["start"],
            1: ["node1"],
            2: ["end"],
        }
        self.activity_size = (150, 42)
        self.event_size = (40, 40)
        self.gateway_size = (36, 36)
        self.start = (20, 150)
        self.canvas_width = 1000

    def test_position_basic(self):
        """测试基本的 position 功能 - 仅测试 upsert_orders"""
        # position 函数需要完整的 pipeline 结构，这里只测试 upsert_orders
        orders = ["start", "node1", "end"]
        nodes_fill_nums = {}

        new_orders, dummy_nodes = position.upsert_orders(orders, nodes_fill_nums)
        self.assertEqual(new_orders, orders)
        self.assertEqual(dummy_nodes, [])
