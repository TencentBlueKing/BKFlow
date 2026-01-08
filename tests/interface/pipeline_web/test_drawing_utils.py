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
from bkflow.pipeline_web.drawing_new import normalize, utils


class TestFormatPipelineNodeTypes(TestCase):
    def setUp(self):
        self.pipeline = {
            PWE.start_event: {"id": "start"},
            PWE.end_event: {"id": "end"},
            PWE.activities: {
                "act1": {"id": "act1"},
                "act2": {"id": "act2"},
            },
            PWE.gateways: {
                "gw1": {"id": "gw1"},
                "gw2": {"id": "gw2"},
            },
        }

    def test_format_pipeline_node_types(self):
        """测试格式化流程节点类型"""
        node_types = utils.format_pipeline_node_types(self.pipeline)

        self.assertEqual(node_types["start"], PWE.start_event)
        self.assertEqual(node_types["end"], PWE.end_event)
        self.assertEqual(node_types["act1"], PWE.activities)
        self.assertEqual(node_types["act2"], PWE.activities)
        self.assertEqual(node_types["gw1"], PWE.gateways)
        self.assertEqual(node_types["gw2"], PWE.gateways)


class TestAddFlowIdToNodeIO(TestCase):
    def test_add_flow_id_to_empty_list(self):
        """测试添加流ID到空列表"""
        node = {PWE.incoming: []}
        utils.add_flow_id_to_node_io(node, "flow1", PWE.incoming)
        self.assertEqual(node[PWE.incoming], ["flow1"])

    def test_add_flow_id_to_existing_list(self):
        """测试添加流ID到已有列表"""
        node = {PWE.incoming: ["flow1"]}
        utils.add_flow_id_to_node_io(node, "flow2", PWE.incoming)
        self.assertEqual(node[PWE.incoming], ["flow1", "flow2"])

    def test_add_flow_id_to_string(self):
        """测试添加流ID到字符串"""
        node = {PWE.incoming: "flow1"}
        utils.add_flow_id_to_node_io(node, "flow2", PWE.incoming)
        self.assertEqual(node[PWE.incoming], ["flow1", "flow2"])

    def test_add_flow_id_to_empty_string(self):
        """测试添加流ID到空字符串"""
        node = {PWE.incoming: ""}
        utils.add_flow_id_to_node_io(node, "flow1", PWE.incoming)
        self.assertEqual(node[PWE.incoming], "flow1")


class TestDeleteFlowIdFromNodeIO(TestCase):
    def test_delete_flow_id_from_string_match(self):
        """测试从字符串中删除匹配的流ID"""
        node = {PWE.incoming: "flow1", PWE.type: PWE.ServiceActivity}
        utils.delete_flow_id_from_node_io(node, "flow1", PWE.incoming)
        self.assertEqual(node[PWE.incoming], "")

    def test_delete_flow_id_from_list_single(self):
        """测试从列表中删除单个流ID（非网关节点）"""
        node = {PWE.incoming: ["flow1"], PWE.type: PWE.ServiceActivity}
        utils.delete_flow_id_from_node_io(node, "flow1", PWE.incoming)
        self.assertEqual(node[PWE.incoming], "")

    def test_delete_flow_id_from_list_single_gateway(self):
        """测试从列表中删除单个流ID（网关节点）"""
        node = {PWE.incoming: ["flow1"], PWE.type: PWE.ParallelGateway}
        utils.delete_flow_id_from_node_io(node, "flow1", PWE.incoming)
        self.assertEqual(node[PWE.incoming], [])

    def test_delete_flow_id_from_list_multiple(self):
        """测试从列表中删除多个流ID中的一个"""
        node = {PWE.incoming: ["flow1", "flow2"], PWE.type: PWE.ServiceActivity}
        utils.delete_flow_id_from_node_io(node, "flow1", PWE.incoming)
        self.assertEqual(node[PWE.incoming], ["flow2"])


class TestNormalize(TestCase):
    def setUp(self):
        self.pipeline = {
            "start_event": {"id": "start"},
            "end_event": {"id": "end"},
            "activities": {
                "act1": {"id": "act1"},
                "act2": {"id": "act2"},
            },
            "gateways": {
                "gw1": {"id": "gw1"},
            },
        }

    def test_normalize_undo(self):
        """测试标准化还原"""
        self.pipeline["all_nodes"] = {"node1": {}, "node2": {}}

        normalize.normalize_undo(self.pipeline)

        self.assertNotIn("all_nodes", self.pipeline)
