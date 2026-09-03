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

    def test_position_basic(self):
        """基础流程：start -> node1 -> end，所有节点都应生成 location 与 line"""
        locations, lines = position.position(
            pipeline=self.pipeline,
            orders=self.orders,
            activity_size=self.activity_size,
            event_size=self.event_size,
            gateway_size=self.gateway_size,
            start=self.start,
            canvas_width=self.canvas_width,
            nodes_fill_nums={},
        )
        # 三个节点均生成 location
        self.assertCountEqual(locations.keys(), ["start", "node1", "end"])
        # 类型映射正确（web 端类型）
        self.assertEqual(locations["node1"]["type"], PWE.tasknode)
        self.assertEqual(locations["start"]["type"], PWE.startpoint)
        self.assertEqual(locations["end"]["type"], PWE.endpoint)
        # 两条连线均生成 line，且携带 source/target 端点
        self.assertCountEqual(lines.keys(), ["f1", "f2"])
        for flow_id in ("f1", "f2"):
            self.assertEqual(lines[flow_id]["source"]["id"], self.pipeline[PWE.flows][flow_id][PWE.source])
            self.assertEqual(lines[flow_id]["target"]["id"], self.pipeline[PWE.flows][flow_id][PWE.target])

    def test_position_coordinates_layout(self):
        """同一层级多节点纵向错开，横坐标随层推进"""
        pipeline = {
            "all_nodes": {
                "n1": {PWE.id: "n1", PWE.type: PWE.ServiceActivity},
                "n2": {PWE.id: "n2", PWE.type: PWE.ServiceActivity},
            },
            PWE.flows: {},
        }
        orders = {0: ["n1", "n2"]}
        locations, _ = position.position(
            pipeline=pipeline,
            orders=orders,
            activity_size=self.activity_size,
            event_size=self.event_size,
            gateway_size=self.gateway_size,
            start=self.start,
            canvas_width=self.canvas_width,
            nodes_fill_nums={},
        )
        # 同层第二个节点应纵向排布在第一个节点下方（shift_y 的倍数）
        self.assertEqual(locations["n1"]["x"], self.start[0])
        self.assertEqual(locations["n2"]["x"], self.start[0])
        self.assertGreater(locations["n2"]["y"], locations["n1"]["y"])

    def test_position_line_wrap_with_old_location(self):
        """换行场景：终点位于每行起始 x 时，line 应带 midpoint 比例"""
        # 构造一个需要换行的长流程：横向超出 canvas_width 触发换行
        pipeline = {
            "all_nodes": {f"g{i}": {PWE.id: f"g{i}", PWE.type: PWE.ServiceActivity} for i in range(10)},
            PWE.flows: {f"fl{i}": {PWE.id: f"fl{i}", PWE.source: f"g{i}", PWE.target: f"g{i + 1}"} for i in range(9)},
        }
        orders = {0: [f"g{i}" for i in range(10)]}
        # canvas_width 设置得很小，强制换行
        locations, lines = position.position(
            pipeline=pipeline,
            orders=orders,
            activity_size=self.activity_size,
            event_size=self.event_size,
            gateway_size=self.gateway_size,
            start=self.start,
            canvas_width=160,
            nodes_fill_nums={},
        )
        # 存在换行时，应至少有一个 line 设置 midpoint
        self.assertTrue(any("midpoint" in line for line in lines.values()))

    def test_position_with_old_locations_preserved(self):
        """已有 location（old_locations）时，新坐标覆盖且其它字段保留"""
        old_x, old_y, old_width = 999, 888, 123
        self.pipeline["location"] = [
            {
                "id": "node1",
                "type": PWE.tasknode,
                "name": "保留名称",
                "status": "FINISHED",
                "x": old_x,
                "y": old_y,
                "width": old_width,
            }
        ]
        locations, _ = position.position(
            pipeline=self.pipeline,
            orders=self.orders,
            activity_size=self.activity_size,
            event_size=self.event_size,
            gateway_size=self.gateway_size,
            start=self.start,
            canvas_width=self.canvas_width,
            nodes_fill_nums={},
        )
        # old_locations 中的 width 被保留，x/y 被新坐标覆盖
        self.assertEqual(locations["node1"]["width"], old_width)
        self.assertEqual(locations["node1"]["name"], "保留名称")
        self.assertEqual(locations["node1"]["status"], "FINISHED")
        self.assertNotEqual(locations["node1"]["x"], old_x)

    def test_position_dummy_nodes_only_occupy_slot(self):
        """虚拟占位节点（不在 all_nodes 中）仅占用纵向槽位，不生成 location"""
        pipeline = {
            "all_nodes": {
                "a": {PWE.id: "a", PWE.type: PWE.ServiceActivity},
                "b": {PWE.id: "b", PWE.type: PWE.ServiceActivity},
            },
            PWE.flows: {},
        }
        # 该层只含虚拟节点（不存在于 all_nodes），不生成 location
        orders = {0: ["dummy_only"]}
        locations, _ = position.position(
            pipeline=pipeline,
            orders=orders,
            activity_size=self.activity_size,
            event_size=self.event_size,
            gateway_size=self.gateway_size,
            start=self.start,
            canvas_width=self.canvas_width,
            nodes_fill_nums={},
        )
        self.assertEqual(locations, {})

    def test_position_with_more_flows(self):
        """more_flows 追加的连线也应生成 line"""
        # 构造 a、b 分属不同层级且画布足够宽不换行的 pipeline，
        # 使 b 的横坐标（rank_x 推进后）偏离起始列 start_x，
        # 从而避免触发 position_flows 中「终点在起始列」的换行 midpoint 分支（其 y 差为 0 时会除零）。
        pipeline = {
            "all_nodes": {
                "a": {PWE.id: "a", PWE.type: PWE.ServiceActivity},
                "b": {PWE.id: "b", PWE.type: PWE.ServiceActivity},
            },
            PWE.flows: {},
        }
        orders = {0: ["a"], 1: ["b"]}
        more_flows = {
            "extra": {PWE.id: "extra", PWE.source: "a", PWE.target: "b"},
        }
        locations, lines = position.position(
            pipeline=pipeline,
            orders=orders,
            activity_size=self.activity_size,
            event_size=self.event_size,
            gateway_size=self.gateway_size,
            start=self.start,
            canvas_width=self.canvas_width,
            nodes_fill_nums={},
            more_flows=more_flows,
        )
        self.assertIn("extra", lines)


class TestPlaceNormalNode(TestCase):
    """测试 _place_normal_node 函数"""

    def setUp(self):
        self.locations = {}
        self.old_locations = {}
        self.dummy_nodes = set()

    def test_place_new_normal_node(self):
        """全新普通节点写入 location，并返回 (occupy_x, bottom_y)"""
        node = {PWE.type: PWE.ServiceActivity, PWE.name: "act"}
        occupy_x, bottom_y = position._place_normal_node(
            node_id="n1",
            node=node,
            node_x=100,
            node_y=200,
            old_locations=self.old_locations,
            dummy_nodes=self.dummy_nodes,
            locations=self.locations,
            node_shift_x=60,
            shift_y=42,
        )
        self.assertIn("n1", self.locations)
        self.assertEqual(self.locations["n1"]["x"], 100)
        self.assertEqual(self.locations["n1"]["y"], 200)
        self.assertEqual(self.locations["n1"]["type"], PWE.tasknode)
        self.assertEqual(self.locations["n1"]["status"], "")
        # occupy_x = node_x + node_shift_x, bottom_y = node_y + shift_y
        self.assertEqual(occupy_x, 160)
        self.assertEqual(bottom_y, 242)

    def test_place_with_old_location_merges_fields(self):
        """存在 old_locations 时，深拷贝旧条目并覆盖 x/y，保留其它字段"""
        self.old_locations = {"n1": {"id": "n1", "type": PWE.tasknode, "name": "old", "x": 1, "y": 2, "width": 99}}
        node = {PWE.type: PWE.ServiceActivity, PWE.name: "new"}
        position._place_normal_node(
            node_id="n1",
            node=node,
            node_x=300,
            node_y=400,
            old_locations=self.old_locations,
            dummy_nodes=self.dummy_nodes,
            locations=self.locations,
            node_shift_x=60,
            shift_y=42,
        )
        # 旧字段 width 被保留，name 也被旧条目保留（deepcopy 优先）
        self.assertEqual(self.locations["n1"]["width"], 99)
        self.assertEqual(self.locations["n1"]["x"], 300)
        self.assertEqual(self.locations["n1"]["y"], 400)

    def test_place_dummy_node_skipped(self):
        """dummy 节点不写入 location"""
        self.dummy_nodes = {"d1"}
        node = {PWE.type: PWE.ServiceActivity}
        position._place_normal_node(
            node_id="d1",
            node=node,
            node_x=0,
            node_y=0,
            old_locations=self.old_locations,
            dummy_nodes=self.dummy_nodes,
            locations=self.locations,
            node_shift_x=60,
            shift_y=42,
        )
        self.assertNotIn("d1", self.locations)


class TestPlaceSubCanvas(TestCase):
    """测试 _place_subcanvas 函数"""

    def setUp(self):
        self.locations = {}
        self.dummy_nodes = set()

    def test_place_subcanvas_with_old_size(self):
        """旧 location 提供 width/height，occupy_x 含 SUBCANVAS_EXTRA_GAP"""
        node = {
            PWE.type: PWE.SubCanvas,
            PWE.name: "sub",
            "pipeline": {"location": [{"id": "inner1", "x": 10, "y": 20}]},
        }
        old_locations = {"c1": {"id": "c1", "type": PWE.subcanvas, "x": 5, "y": 5, "width": 200, "height": 150}}
        occupy_x, bottom_y = position._place_subcanvas(
            node_id="c1",
            node=node,
            node_x=100,
            node_y=100,
            old_locations=old_locations,
            dummy_nodes=self.dummy_nodes,
            locations=self.locations,
            default_width=300,
            shift_y=42,
        )
        self.assertIn("c1", self.locations)
        # 旧 location 分支直接深拷贝 old_loc 并覆盖 x/y，宽高来自旧条目
        self.assertEqual(self.locations["c1"]["width"], 200)
        self.assertEqual(self.locations["c1"]["height"], 150)
        # 内部节点随容器移动：offset = (100-5, 100-5) = (95, 95)
        inner = node["pipeline"]["location"][0]
        self.assertEqual(inner["x"], 10 + 95)
        self.assertEqual(inner["y"], 20 + 95)
        # occupy_x = node_x + width + SUBCANVAS_EXTRA_GAP
        self.assertEqual(occupy_x, 100 + 200 + position.SUBCANVAS_EXTRA_GAP)
        self.assertEqual(bottom_y, 100 + 150 + 42)

    def test_place_subcanvas_without_old_size_uses_default(self):
        """无旧 location 时：不写 width（仅用 default_width 做横向占位），新节点分支写入 parent=True"""
        node = {PWE.type: PWE.SubCanvas, PWE.name: "sub", "pipeline": {"location": []}}
        occupy_x, bottom_y = position._place_subcanvas(
            node_id="c2",
            node=node,
            node_x=50,
            node_y=50,
            old_locations={},
            dummy_nodes=self.dummy_nodes,
            locations=self.locations,
            default_width=300,
            shift_y=42,
        )
        # 无旧 location 时 width 不写入 entry（sub_width 为 None），仅用 default_width 作为横向占位
        self.assertNotIn("width", self.locations["c2"])
        self.assertNotIn("height", self.locations["c2"])
        # 新节点分支标记 parent
        self.assertEqual(self.locations["c2"]["parent"], True)
        # occupy_x = node_x + default_width + SUBCANVAS_EXTRA_GAP
        self.assertEqual(occupy_x, 50 + 300 + position.SUBCANVAS_EXTRA_GAP)

    def test_place_subcanvas_no_inner_shift_when_offset_zero(self):
        """offset 为 0 时（旧 x/y 与当前一致），内部节点坐标不变"""
        node = {
            PWE.type: PWE.SubCanvas,
            "pipeline": {"location": [{"id": "inner1", "x": 10, "y": 20}]},
        }
        old_locations = {"c3": {"id": "c3", "type": PWE.subcanvas, "x": 100, "y": 100, "width": 200, "height": 150}}
        position._place_subcanvas(
            node_id="c3",
            node=node,
            node_x=100,
            node_y=100,
            old_locations=old_locations,
            dummy_nodes=self.dummy_nodes,
            locations=self.locations,
            default_width=300,
            shift_y=42,
        )
        inner = node["pipeline"]["location"][0]
        self.assertEqual(inner["x"], 10)
        self.assertEqual(inner["y"], 20)


class TestShiftInnerLocations(TestCase):
    """测试 _shift_inner_locations 函数"""

    def test_shift_inner_locations(self):
        node = {
            "pipeline": {
                "location": [
                    {"id": "a", "x": 1, "y": 2},
                    {"id": "b", "x": 3, "y": 4},
                ]
            }
        }
        position._shift_inner_locations(node, offset_x=10, offset_y=20)
        self.assertEqual(node["pipeline"]["location"][0]["x"], 11)
        self.assertEqual(node["pipeline"]["location"][0]["y"], 22)
        self.assertEqual(node["pipeline"]["location"][1]["x"], 13)
        self.assertEqual(node["pipeline"]["location"][1]["y"], 24)

    def test_shift_inner_locations_zero_offset_noop(self):
        node = {"pipeline": {"location": [{"id": "a", "x": 1, "y": 2}]}}
        position._shift_inner_locations(node, offset_x=0, offset_y=0)
        self.assertEqual(node["pipeline"]["location"][0]["x"], 1)
        self.assertEqual(node["pipeline"]["location"][0]["y"], 2)

    def test_shift_inner_locations_missing_pipeline(self):
        node = {}
        # 不应抛异常
        position._shift_inner_locations(node, offset_x=5, offset_y=5)


class TestPositionFlows(TestCase):
    """测试 position_flows 函数"""

    # position_flows 会把此字典透传给 arrow_flow，key 为后端类型
    shift_map = {PWE.ServiceActivity: 0}

    def test_position_flows_basic(self):
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 0, "y": 0},
            "t": {"id": "t", "type": PWE.tasknode, "x": 200, "y": 0},
        }
        flows = {"f1": {PWE.id: "f1", PWE.source: "s", PWE.target: "t"}}
        lines = position.position_flows(flows, locations, self.shift_map, start_x=0, shift_y=42)
        self.assertIn("f1", lines)
        self.assertEqual(lines["f1"]["source"]["id"], "s")
        self.assertEqual(lines["f1"]["target"]["id"], "t")

    def test_position_flows_midpoint_on_wrap(self):
        """终点 x 等于每行起始 x（换行）时设置 midpoint"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 0, "y": 0},
            "t": {"id": "t", "type": PWE.tasknode, "x": 0, "y": 100},
        }
        flows = {"f1": {PWE.id: "f1", PWE.source: "s", PWE.target: "t"}}
        lines = position.position_flows(flows, locations, self.shift_map, start_x=0, shift_y=42)
        self.assertIn("midpoint", lines["f1"])
        # midpoint = 1 - shift_y * 0.5 / (target_y - source_y)
        self.assertAlmostEqual(lines["f1"]["midpoint"], 1 - 42 * 0.5 / 100)

    def test_position_flows_no_midpoint_when_not_wrap(self):
        """终点不在每行起始 x 时不设置 midpoint"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 0, "y": 0},
            "t": {"id": "t", "type": PWE.tasknode, "x": 200, "y": 0},
        }
        flows = {"f1": {PWE.id: "f1", PWE.source: "s", PWE.target: "t"}}
        lines = position.position_flows(flows, locations, self.shift_map, start_x=0, shift_y=42)
        self.assertNotIn("midpoint", lines["f1"])


class TestArrowFlow(TestCase):
    """测试 arrow_flow 函数"""

    # arrow_flow 内部会把 web 端 type 经 PIPELINE_WEB_TO_ELEMENT 反查为后端类型，
    # 再用后端类型查此字典，因此 key 必须是后端类型
    shift_map = {PWE.ServiceActivity: 0, PWE.EmptyStartEvent: 0}

    def _make_flow(self, source, target):
        return {PWE.source: source, PWE.target: target}

    def test_arrow_normal_left_to_right(self):
        """源在目标左侧同水平：source=right, target=left"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 0, "y": 0},
            "t": {"id": "t", "type": PWE.tasknode, "x": 200, "y": 0},
        }
        src, tgt = position.arrow_flow(self._make_flow("s", "t"), locations, self.shift_map)
        self.assertEqual(src, PWE.right)
        self.assertEqual(tgt, PWE.left)

    def test_arrow_branch_source_top(self):
        """源在目标左上方（发起分支）：source=bottom, target=left"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 0, "y": 0},
            "t": {"id": "t", "type": PWE.tasknode, "x": 200, "y": 100},
        }
        src, tgt = position.arrow_flow(self._make_flow("s", "t"), locations, self.shift_map)
        self.assertEqual(src, PWE.bottom)
        self.assertEqual(tgt, PWE.left)

    def test_arrow_converge_source_bottom(self):
        """源在目标左下方（汇聚分支）：source=right, target=bottom"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 0, "y": 200},
            "t": {"id": "t", "type": PWE.tasknode, "x": 200, "y": 100},
        }
        src, tgt = position.arrow_flow(self._make_flow("s", "t"), locations, self.shift_map)
        self.assertEqual(src, PWE.right)
        self.assertEqual(tgt, PWE.bottom)

    def test_arrow_wrap_right_to_left_top(self):
        """源在目标右侧上方（换行）：source=right, target=left"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 300, "y": 0},
            "t": {"id": "t", "type": PWE.tasknode, "x": 0, "y": 100},
        }
        src, tgt = position.arrow_flow(self._make_flow("s", "t"), locations, self.shift_map)
        self.assertEqual(src, PWE.right)
        self.assertEqual(tgt, PWE.left)

    def test_arrow_rollback_right_bottom(self):
        """源在目标右侧且下侧（打回流程）：source=bottom, target=bottom"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 300, "y": 200},
            "t": {"id": "t", "type": PWE.tasknode, "x": 0, "y": 100},
        }
        src, tgt = position.arrow_flow(self._make_flow("s", "t"), locations, self.shift_map)
        self.assertEqual(src, PWE.bottom)
        self.assertEqual(tgt, PWE.bottom)

    def test_arrow_same_x_top_to_bottom(self):
        """源目标同 x，源在上：source=bottom, target=top"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 0, "y": 0},
            "t": {"id": "t", "type": PWE.tasknode, "x": 0, "y": 100},
        }
        src, tgt = position.arrow_flow(self._make_flow("s", "t"), locations, self.shift_map)
        self.assertEqual(src, PWE.bottom)
        self.assertEqual(tgt, PWE.top)

    def test_arrow_shift_y_applied(self):
        """pipeline_element_shift_y 影响纵向比较基准"""
        locations = {
            "s": {"id": "s", "type": PWE.tasknode, "x": 0, "y": 0},
            "t": {"id": "t", "type": PWE.startpoint, "x": 0, "y": 0},
        }
        # t 为事件节点，shift_y=10，则 target 实际比较 y = 0 - 10 = -10 < source 的 0
        # 源 target 同 x、source_y(0) > target_y(-10) -> source=top, target=bottom
        shift_map = {PWE.ServiceActivity: 0, PWE.EmptyStartEvent: 10}
        src, tgt = position.arrow_flow(self._make_flow("s", "t"), locations, shift_map)
        self.assertEqual(src, PWE.top)
        self.assertEqual(tgt, PWE.bottom)
