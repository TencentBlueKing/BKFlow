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

    def test_upsert_orders(self):
        """测试 upsert_orders 功能"""
        # Basic
        orders = ["node1", "node2", "node3"]
        nodes_fill_nums = {"node2": 2}
        new_orders, dummy_nodes = position.upsert_orders(orders, nodes_fill_nums)
        self.assertEqual(len(new_orders), 5)
        self.assertEqual(len(dummy_nodes), 2)

        # Empty
        new_orders, dummy_nodes = position.upsert_orders([], {})
        self.assertEqual(new_orders, [])
        self.assertEqual(dummy_nodes, [])

        # No fill
        new_orders, dummy_nodes = position.upsert_orders(["node1", "node2"], {})
        self.assertEqual(new_orders, ["node1", "node2"])
        self.assertEqual(dummy_nodes, [])

        # Multiple nodes
        orders = ["node1", "node2", "node3"]
        nodes_fill_nums = {"node1": 1, "node3": 2}
        new_orders, dummy_nodes = position.upsert_orders(orders, nodes_fill_nums)
        self.assertEqual(len(dummy_nodes), 3)
        self.assertEqual(len(new_orders), 6)


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
