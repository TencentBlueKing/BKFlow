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
from bkflow.pipeline_web.drawing_new import dummy
from bkflow.pipeline_web.drawing_new.constants import DUMMY_NODE_TYPE


class TestReplaceLongPathWithDummy(TestCase):
    """测试 replace_long_path_with_dummy 函数"""

    def setUp(self):
        self.node_id1 = "node1"
        self.node_id2 = "node2"
        self.flow_id = "line1"
        self.pipeline = {
            "all_nodes": {
                self.node_id1: {PWE.id: self.node_id1, PWE.incoming: "", PWE.outgoing: self.flow_id},
                self.node_id2: {PWE.id: self.node_id2, PWE.incoming: self.flow_id, PWE.outgoing: ""},
            },
            PWE.flows: {self.flow_id: {PWE.id: self.flow_id, PWE.source: self.node_id1, PWE.target: self.node_id2}},
        }
        self.pipeline_bak = deepcopy(self.pipeline)
        self.flows = deepcopy(self.pipeline[PWE.flows])
        self.ranks = {self.node_id1: -2, self.node_id2: 0}
        self.ranks_bak = deepcopy(self.ranks)

    def test_replace_long_path_with_dummy_nodes(self):
        """测试替换长路径为虚拟节点"""
        real_flows_chain = dummy.replace_long_path_with_dummy(self.pipeline, self.ranks)
        self.assertEqual(real_flows_chain, self.flows)
        # 验证 ranks 包含虚拟节点
        self.assertEqual(set(self.ranks.values()), {-2, -1, 0})
        # 验证节点的 outgoing/incoming 已被更新
        self.assertNotEqual(self.pipeline["all_nodes"][self.node_id1][PWE.outgoing], self.flow_id)
        self.assertNotEqual(self.pipeline["all_nodes"][self.node_id2][PWE.incoming], self.flow_id)
        # 验证生成了2条虚拟边
        self.assertEqual(len(list(self.pipeline[PWE.flows].keys())), 2)

    def test_no_long_path(self):
        """测试没有长路径的情况"""
        pipeline = {
            "all_nodes": {
                "n1": {PWE.id: "n1", PWE.incoming: "", PWE.outgoing: "f1"},
                "n2": {PWE.id: "n2", PWE.incoming: "f1", PWE.outgoing: ""},
            },
            PWE.flows: {"f1": {PWE.id: "f1", PWE.source: "n1", PWE.target: "n2"}},
        }
        ranks = {"n1": 0, "n2": 1}
        real_flows_chain = dummy.replace_long_path_with_dummy(pipeline, ranks)
        # 没有长路径，返回空字典
        self.assertEqual(real_flows_chain, {})
        # pipeline 不应该被修改
        self.assertEqual(len(pipeline[PWE.flows]), 1)

    def test_multiple_long_paths(self):
        """测试多条长路径的情况"""
        pipeline = {
            "all_nodes": {
                "n1": {PWE.id: "n1", PWE.type: "ServiceActivity", PWE.incoming: "", PWE.outgoing: ["f1", "f2"]},
                "n2": {PWE.id: "n2", PWE.type: "ServiceActivity", PWE.incoming: "f1", PWE.outgoing: ""},
                "n3": {PWE.id: "n3", PWE.type: "ServiceActivity", PWE.incoming: "f2", PWE.outgoing: ""},
            },
            PWE.flows: {
                "f1": {PWE.id: "f1", PWE.source: "n1", PWE.target: "n2"},
                "f2": {PWE.id: "f2", PWE.source: "n1", PWE.target: "n3"},
            },
        }
        ranks = {"n1": 0, "n2": 3, "n3": 4}

        real_flows_chain = dummy.replace_long_path_with_dummy(pipeline, ranks)
        # 两条长路径都应该被替换
        self.assertEqual(len(real_flows_chain), 2)
        self.assertIn("f1", real_flows_chain)
        self.assertIn("f2", real_flows_chain)


class TestComputeSortedListByOrder(TestCase):
    """测试 compute_sorted_list_by_order 函数"""

    def test_compute_sorted_list_by_order(self):
        """测试根据 orders 计算排序列表"""
        orders = {0: ["n1", "n2"], 1: ["n3"], 2: ["n4", "n5"]}
        dummy_nums_dict = {"n1": 1, "n3": 2, "n5": 3}

        result = dummy.compute_sorted_list_by_order(orders, dummy_nums_dict)
        self.assertEqual(result, ["n1", "n3", "n5"])


class TestComputeNodeRightToLeft(TestCase):
    """测试 compute_node_right_to_left 函数"""

    def test_compute_node_right_to_left(self):
        """测试从右到左计算节点"""
        pipeline = {
            PWE.activities: {
                "n1": {PWE.id: "n1", PWE.incoming: ["f1"], PWE.outgoing: "f2"},
                "n2": {PWE.id: "n2", PWE.incoming: [], PWE.outgoing: "f1"},
            },
            PWE.flows: {
                "f1": {PWE.id: "f1", PWE.source: "n2", PWE.target: "n1"},
                "f2": {PWE.id: "f2", PWE.source: "n1", PWE.target: "n3"},
            },
        }
        nodes_dummy_nums = {}

        dummy.compute_node_right_to_left(pipeline, "f2", 5, nodes_dummy_nums)
        self.assertEqual(nodes_dummy_nums["n1"], 5)


class TestComputeNodeLeftToRight(TestCase):
    """测试 compute_node_left_to_right 函数"""

    def test_compute_node_left_to_right_with_dummy_node(self):
        """测试从左到右计算虚拟节点"""
        pipeline = {
            "all_nodes": {
                "dummy1": {PWE.id: "dummy1", PWE.type: DUMMY_NODE_TYPE, PWE.incoming: "f1", PWE.outgoing: "f2"},
                "dummy2": {PWE.id: "dummy2", PWE.type: DUMMY_NODE_TYPE, PWE.incoming: "f2", PWE.outgoing: "f3"},
                "n1": {PWE.id: "n1", PWE.type: "ServiceActivity", PWE.incoming: "f3", PWE.outgoing: ""},
            },
            PWE.flows: {
                "f1": {PWE.id: "f1", PWE.source: "n0", PWE.target: "dummy1"},
                "f2": {PWE.id: "f2", PWE.source: "dummy1", PWE.target: "dummy2"},
                "f3": {PWE.id: "f3", PWE.source: "dummy2", PWE.target: "n1"},
            },
        }
        nodes_dummy_nums = {}

        dummy.compute_node_left_to_right(pipeline, "f1", 3, nodes_dummy_nums)
        # 虚拟节点应该被赋值
        self.assertEqual(nodes_dummy_nums.get("dummy1"), 3)
        self.assertEqual(nodes_dummy_nums.get("dummy2"), 3)


class TestComputeNodesFillNum(TestCase):
    """测试 compute_nodes_fill_num 函数"""

    def test_compute_nodes_fill_num_with_parallel_gateway(self):
        """测试包含并行网关的节点填充数量计算"""
        pipeline = {
            PWE.activities: {
                "n1": {PWE.id: "n1", PWE.type: "ServiceActivity", PWE.incoming: ["f1"], PWE.outgoing: "f2"},
            },
            "gateways": {
                "pg1": {
                    PWE.id: "pg1",
                    PWE.type: PWE.ParallelGateway,
                    PWE.incoming: ["f2"],
                    PWE.outgoing: ["f3", "f4", "f5"],
                    "converge_gateway_id": "cg1",
                },
                "cg1": {
                    PWE.id: "cg1",
                    PWE.type: PWE.ConvergeGateway,
                    PWE.incoming: ["f6", "f7", "f8"],
                    PWE.outgoing: "f9",
                },
            },
            PWE.flows: {
                "f1": {PWE.id: "f1", PWE.source: "start", PWE.target: "n1"},
                "f2": {PWE.id: "f2", PWE.source: "n1", PWE.target: "pg1"},
            },
            "all_nodes": {
                "n1": {PWE.id: "n1", PWE.type: "ServiceActivity", PWE.incoming: ["f1"], PWE.outgoing: "f2"},
                "pg1": {
                    PWE.id: "pg1",
                    PWE.type: PWE.ParallelGateway,
                    PWE.incoming: ["f2"],
                    PWE.outgoing: ["f3", "f4", "f5"],
                },
                "cg1": {
                    PWE.id: "cg1",
                    PWE.type: PWE.ConvergeGateway,
                    PWE.incoming: ["f6", "f7", "f8"],
                    PWE.outgoing: "f9",
                },
            },
        }
        orders = {0: ["n1"], 1: ["pg1"], 2: ["cg1"]}

        result = dummy.compute_nodes_fill_num(pipeline, orders)

        # 并行网关有3个出口，应该填充 3-1=2
        self.assertEqual(result.get("pg1"), 2)
        # 汇聚网关有3个入口，应该填充 3-1=2
        self.assertEqual(result.get("cg1"), 2)

    def test_compute_nodes_fill_num_with_exclusive_gateway(self):
        """测试包含分支网关的节点填充数量计算"""
        pipeline = {
            PWE.activities: {
                "n0": {PWE.id: "n0", PWE.type: "ServiceActivity", PWE.incoming: "", PWE.outgoing: "f1"},
            },
            "gateways": {
                "eg1": {
                    PWE.id: "eg1",
                    PWE.type: PWE.ExclusiveGateway,
                    PWE.incoming: ["f1"],
                    PWE.outgoing: ["f2", "f3"],
                },
            },
            PWE.flows: {
                "f1": {PWE.id: "f1", PWE.source: "n0", PWE.target: "eg1"},
            },
            "all_nodes": {
                "n0": {PWE.id: "n0", PWE.type: "ServiceActivity", PWE.incoming: "", PWE.outgoing: "f1"},
                "eg1": {
                    PWE.id: "eg1",
                    PWE.type: PWE.ExclusiveGateway,
                    PWE.incoming: ["f1"],
                    PWE.outgoing: ["f2", "f3"],
                },
            },
        }
        orders = {0: ["n0"], 1: ["eg1"]}

        result = dummy.compute_nodes_fill_num(pipeline, orders)
        # 分支网关有2个出口，应该填充 2-1=1
        self.assertEqual(result.get("eg1"), 1)
        # 节点 n0 应该继承网关的值
        self.assertEqual(result.get("n0"), 1)

    def test_empty_pipeline(self):
        """测试空 pipeline"""
        pipeline = {
            PWE.activities: {},
            "gateways": {},
            PWE.flows: {},
            "all_nodes": {},
        }
        orders = {}

        result = dummy.compute_nodes_fill_num(pipeline, orders)
        self.assertEqual(result, {})


class TestRemoveDummy(TestCase):
    """测试 remove_dummy 函数"""

    def setUp(self):
        self.node_id1 = "node1"
        self.node_id2 = "node2"
        self.flow_id = "line1"
        self.pipeline = {
            "all_nodes": {
                self.node_id1: {PWE.id: self.node_id1, PWE.incoming: "", PWE.outgoing: self.flow_id},
                self.node_id2: {PWE.id: self.node_id2, PWE.incoming: self.flow_id, PWE.outgoing: ""},
            },
            PWE.flows: {self.flow_id: {PWE.id: self.flow_id, PWE.source: self.node_id1, PWE.target: self.node_id2}},
        }
        self.pipeline_bak = deepcopy(self.pipeline)
        self.ranks = {self.node_id1: -2, self.node_id2: 0}
        self.ranks_bak = deepcopy(self.ranks)

    def test_remove_dummy_nodes(self):
        """测试删除虚拟节点"""
        real_flows_chain = dummy.replace_long_path_with_dummy(self.pipeline, self.ranks)
        dummy.remove_dummy(self.pipeline, real_flows_chain, dummy_nodes_included=[self.ranks])
        # 验证 pipeline 被还原到原始状态
        self.assertEqual(self.pipeline, self.pipeline_bak)
        # 验证 ranks 被还原到原始状态
        self.assertEqual(self.ranks, self.ranks_bak)

    def test_remove_dummy_with_flows_included(self):
        """测试删除虚拟节点和虚拟边（包含额外的 flows 数据）"""
        real_flows_chain = dummy.replace_long_path_with_dummy(self.pipeline, self.ranks)

        # 创建一个额外的 flows 字典
        extra_flows = {}
        for flow_id in self.pipeline[PWE.flows].keys():
            extra_flows[flow_id] = {"extra": "data"}

        dummy.remove_dummy(
            self.pipeline, real_flows_chain, dummy_nodes_included=[self.ranks], dummy_flows_included=[extra_flows]
        )

        # 验证虚拟边从 extra_flows 中被删除
        self.assertEqual(len(extra_flows), 0)

    def test_remove_dummy_with_none_params(self):
        """测试使用 None 参数删除虚拟节点"""
        real_flows_chain = dummy.replace_long_path_with_dummy(self.pipeline, self.ranks)

        # 使用默认的 None 参数
        dummy.remove_dummy(self.pipeline, real_flows_chain, None, None)

        # 验证虚拟节点和虚拟边被正确删除
        for node in self.pipeline["all_nodes"].values():
            self.assertNotEqual(node.get(PWE.type), DUMMY_NODE_TYPE)

    def test_remove_dummy_with_non_dict_included(self):
        """测试包含非字典类型的 included 参数"""
        real_flows_chain = dummy.replace_long_path_with_dummy(self.pipeline, self.ranks)

        # 传入非字典类型
        dummy.remove_dummy(
            self.pipeline, real_flows_chain, dummy_nodes_included=["not_a_dict", {}], dummy_flows_included=[123, {}]
        )

        # 不应该抛出异常，虚拟节点应该被正确删除
        for node in self.pipeline["all_nodes"].values():
            self.assertNotEqual(node.get(PWE.type), DUMMY_NODE_TYPE)
