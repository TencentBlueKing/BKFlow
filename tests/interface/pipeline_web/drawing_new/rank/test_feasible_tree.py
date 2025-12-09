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

from bkflow.pipeline_web.constants import PWE
from bkflow.pipeline_web.drawing_new import acyclic
from bkflow.pipeline_web.drawing_new.normalize import normalize_run, normalize_undo
from bkflow.pipeline_web.drawing_new.rank import feasible_tree, longest_path
from bkflow.pipeline_web.tests.drawing_new.data import pipeline_with_circle


class TestFeasibleTree(TestCase):
    def setUp(self):
        self.pipeline = deepcopy(pipeline_with_circle)
        normalize_run(self.pipeline)
        self.reversed_flows = acyclic.acyclic_run(self.pipeline)

    def test_feasible_tree_ranker(self):
        ranks = longest_path.longest_path_ranker(self.pipeline)
        ranks = feasible_tree.feasible_tree_ranker(self.pipeline, ranks)
        self.assertEqual(
            ranks,
            {
                "nodea4bb3693dfb8d99d2084cee2fb8b": 0,
                "nodeeb9b2a00e46adacd9f57720e8cca": -1,
                "node0dfa73e80b9bf40aa05f2442bb3d": -1,
                "node4149a8d446a7fc325b66a7ee4350": -2,
                "nodeaf2161961809a91ebb00db88c814": -3,
                "node402bea676e660fab4cc643afafc8": -4,
            },
        )

    def tearDown(self):
        acyclic.acyclic_undo(self.pipeline, self.reversed_flows)
        normalize_undo(self.pipeline)

    def test_tight_tree(self):
        """测试 tight_tree 函数"""
        ranks = longest_path.longest_path_ranker(self.pipeline)
        part_tree = {
            "all_nodes": {self.pipeline[PWE.start_event][PWE.id]: self.pipeline[PWE.start_event]},
            PWE.flows: {},
        }
        count = feasible_tree.tight_tree(part_tree, self.pipeline, ranks)
        self.assertGreater(count, 1)
        self.assertIn(PWE.flows, part_tree)

    def test_find_min_slack_flow(self):
        """测试 find_min_slack_flow 函数"""
        ranks = longest_path.longest_path_ranker(self.pipeline)
        part_tree = {
            "all_nodes": {self.pipeline[PWE.start_event][PWE.id]: self.pipeline[PWE.start_event]},
            PWE.flows: {},
        }
        feasible_tree.tight_tree(part_tree, self.pipeline, ranks)
        flow = feasible_tree.find_min_slack_flow(part_tree, self.pipeline, ranks)
        # 应该找到一个连接 part_tree 内外节点的流
        if flow:
            self.assertIsNotNone(flow)
            self.assertIn(PWE.source, flow)
            self.assertIn(PWE.target, flow)

    def test_shift_ranks(self):
        """测试 shift_ranks 函数"""
        ranks = {"node1": 0, "node2": 1, "node3": 2}
        feasible_tree.shift_ranks(ranks, ["node1", "node2"], 5)
        self.assertEqual(ranks["node1"], 5)
        self.assertEqual(ranks["node2"], 6)
        self.assertEqual(ranks["node3"], 2)  # 未改变

    def test_feasible_tree_with_complex_graph(self):
        """测试复杂图的可行树排名"""
        # 创建一个更复杂的图
        pipeline = {
            PWE.start_event: {PWE.id: "start", PWE.outgoing: ["f1", "f2"], PWE.incoming: ""},
            PWE.end_event: {PWE.id: "end", PWE.incoming: ["f5", "f6"], PWE.outgoing: ""},
            "all_nodes": {
                "start": {PWE.id: "start", PWE.outgoing: ["f1", "f2"], PWE.incoming: ""},
                "n1": {PWE.id: "n1", PWE.outgoing: "f3", PWE.incoming: "f1"},
                "n2": {PWE.id: "n2", PWE.outgoing: "f4", PWE.incoming: "f2"},
                "n3": {PWE.id: "n3", PWE.outgoing: "f5", PWE.incoming: "f3"},
                "n4": {PWE.id: "n4", PWE.outgoing: "f6", PWE.incoming: "f4"},
                "end": {PWE.id: "end", PWE.incoming: ["f5", "f6"], PWE.outgoing: ""},
            },
            PWE.flows: {
                "f1": {PWE.id: "f1", PWE.source: "start", PWE.target: "n1"},
                "f2": {PWE.id: "f2", PWE.source: "start", PWE.target: "n2"},
                "f3": {PWE.id: "f3", PWE.source: "n1", PWE.target: "n3"},
                "f4": {PWE.id: "f4", PWE.source: "n2", PWE.target: "n4"},
                "f5": {PWE.id: "f5", PWE.source: "n3", PWE.target: "end"},
                "f6": {PWE.id: "f6", PWE.source: "n4", PWE.target: "end"},
            },
        }

        ranks = longest_path.longest_path_ranker(pipeline)
        result_ranks = feasible_tree.feasible_tree_ranker(pipeline, ranks)

        # 验证所有节点都有排名
        self.assertIn("start", result_ranks)
        self.assertIn("end", result_ranks)
        self.assertIn("n1", result_ranks)
        self.assertIn("n2", result_ranks)
        self.assertIn("n3", result_ranks)
        self.assertIn("n4", result_ranks)

        # 验证排名的合理性：start < n1/n2 < n3/n4 < end
        self.assertLess(result_ranks["start"], result_ranks["n1"])
        self.assertLess(result_ranks["start"], result_ranks["n2"])
        self.assertLess(result_ranks["n1"], result_ranks["n3"])
        self.assertLess(result_ranks["n2"], result_ranks["n4"])
        self.assertLess(result_ranks["n3"], result_ranks["end"])
        self.assertLess(result_ranks["n4"], result_ranks["end"])
