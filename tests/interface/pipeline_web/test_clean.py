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
from pipeline.utils.uniqid import node_uniqid

from bkflow.pipeline_web.constants import PWE
from bkflow.pipeline_web.parser.clean import PipelineWebTreeCleaner

# 创建测试数据
id_list = [node_uniqid() for i in range(10)]
id_list3 = [node_uniqid() for i in range(10)]

WEB_PIPELINE_DATA = {
    "id": id_list[0],
    "name": "name",
    "start_event": {
        "id": id_list[1],
        "name": "start",
        "type": "EmptyStartEvent",
        "incoming": None,
        "outgoing": id_list[5],
    },
    "end_event": {"id": id_list[2], "name": "end", "type": "EmptyEndEvent", "incoming": id_list[7], "outgoing": None},
    "activities": {
        id_list[3]: {
            "id": id_list[3],
            "type": "ServiceActivity",
            "name": "first_task",
            "incoming": id_list[5],
            "outgoing": id_list[6],
        },
        id_list[4]: {
            "id": id_list[4],
            "type": "ServiceActivity",
            "name": "second_task",
            "incoming": id_list[6],
            "outgoing": id_list[7],
        },
    },
    "flows": {
        id_list[5]: {"id": id_list[5], "source": id_list[1], "target": id_list[3]},
        id_list[6]: {"id": id_list[6], "source": id_list[3], "target": id_list[4]},
        id_list[7]: {"id": id_list[7], "source": id_list[4], "target": id_list[2]},
    },
    "gateways": {},
}

WEB_PIPELINE_WITH_SUB_PROCESS = {
    "id": id_list[0],
    "name": "name",
    "start_event": {
        "id": id_list[1],
        "name": "start",
        "type": "EmptyStartEvent",
        "incoming": None,
        "outgoing": id_list[5],
    },
    "end_event": {"id": id_list[2], "name": "end", "type": "EmptyEndEvent", "incoming": id_list[7], "outgoing": None},
    "activities": {
        id_list[3]: {
            "id": id_list[3],
            "type": "ServiceActivity",
            "name": "first_task",
            "incoming": id_list[5],
            "outgoing": id_list[6],
        },
        id_list[4]: {
            "id": id_list[4],
            "type": "SubProcess",
            "name": "sub_process",
            "incoming": id_list[6],
            "outgoing": id_list[7],
            "pipeline": {
                "id": id_list3[0],
                "start_event": {
                    "id": id_list3[1],
                    "type": "EmptyStartEvent",
                    "outgoing": id_list3[5],
                },
                "end_event": {"id": id_list3[2], "type": "EmptyEndEvent", "incoming": id_list3[6]},
                "activities": {
                    id_list3[3]: {
                        "id": id_list3[3],
                        "type": "ServiceActivity",
                        "name": "sub_task",
                        "incoming": id_list3[5],
                        "outgoing": id_list3[6],
                    },
                },
                "flows": {
                    id_list3[5]: {"id": id_list3[5], "source": id_list3[1], "target": id_list3[3]},
                    id_list3[6]: {"id": id_list3[6], "source": id_list3[3], "target": id_list3[2]},
                },
                "gateways": {},
            },
        },
    },
    "flows": {
        id_list[5]: {"id": id_list[5], "source": id_list[1], "target": id_list[3]},
        id_list[6]: {"id": id_list[6], "source": id_list[3], "target": id_list[4]},
        id_list[7]: {"id": id_list[7], "source": id_list[4], "target": id_list[2]},
    },
    "gateways": {},
}


class TestPipelineWebTreeCleaner(TestCase):
    def setUp(self):
        web_pipeline_tree = deepcopy(WEB_PIPELINE_DATA)
        web_pipeline_tree[PWE.activities][id_list[3]][PWE.labels] = [
            {"label": "label11", "group": "group1"},
            {"label": "label12", "group": "group1"},
        ]
        web_pipeline_tree[PWE.activities][id_list[4]][PWE.labels] = [{"label": "label21", "group": "group2"}]
        cleaner = PipelineWebTreeCleaner(web_pipeline_tree)
        self.cleaner_simple = cleaner

        web_pipeline_tree_with_sub = deepcopy(WEB_PIPELINE_WITH_SUB_PROCESS)
        web_pipeline_tree_with_sub[PWE.activities][id_list[3]][PWE.labels] = [
            {"label": "label11", "group": "group1"},
            {"label": "label12", "group": "group1"},
        ]
        sub_pipeline = web_pipeline_tree_with_sub[PWE.activities][id_list[4]][PWE.pipeline]
        sub_pipeline[PWE.activities][id_list3[3]][PWE.labels] = [{"label": "label21", "group": "group2"}]
        cleaner_with_sub = PipelineWebTreeCleaner(web_pipeline_tree_with_sub)
        self.cleaner_with_sub = cleaner_with_sub

    def test_clean__without_subprocess(self):
        nodes_attr = self.cleaner_simple.clean()
        assert_attr = {
            id_list[3]: {
                PWE.labels: [{"label": "label11", "group": "group1"}, {"label": "label12", "group": "group1"}]
            },
            id_list[4]: {PWE.labels: [{"label": "label21", "group": "group2"}]},
        }
        self.assertEqual(nodes_attr, assert_attr)
        self.assertEqual(self.cleaner_simple.pipeline_tree, WEB_PIPELINE_DATA)

    def test_clean__with_subprocess(self):
        nodes_attr = self.cleaner_with_sub.clean(with_subprocess=True)
        assert_attr = {
            id_list[3]: {
                PWE.labels: [{"label": "label11", "group": "group1"}, {"label": "label12", "group": "group1"}]
            },
            PWE.subprocess_detail: {id_list[4]: {id_list3[3]: {PWE.labels: [{"label": "label21", "group": "group2"}]}}},
        }
        self.assertEqual(nodes_attr, assert_attr)
        self.assertEqual(self.cleaner_with_sub.pipeline_tree, WEB_PIPELINE_WITH_SUB_PROCESS)

    def test_replace_id(self):
        nodes_attr = {
            id_list[3]: {
                PWE.labels: [{"label": "label11", "group": "group1"}, {"label": "label12", "group": "group1"}]
            },
            PWE.subprocess_detail: {id_list[4]: {id_list3[3]: {PWE.labels: [{"label": "label21", "group": "group2"}]}}},
        }
        nodes_id_maps = {
            PWE.activities: {id_list[3]: "new_id3", id_list[4]: "new_id4"},
            PWE.subprocess_detail: {"new_id4": {PWE.activities: {id_list3[3]: "new_id5"}}},
        }
        new_nodes_attr = PipelineWebTreeCleaner.replace_id(nodes_attr, nodes_id_maps, with_subprocess=True)
        self.assertEqual(
            new_nodes_attr,
            {
                "new_id3": {
                    PWE.labels: [{"label": "label11", "group": "group1"}, {"label": "label12", "group": "group1"}]
                },
                PWE.subprocess_detail: {
                    "new_id4": {"new_id5": {PWE.labels: [{"label": "label21", "group": "group2"}]}}
                },
            },
        )

    def test_to_web__without_subprocess(self):
        nodes_attr = {
            id_list[3]: {
                PWE.labels: [{"label": "label11", "group": "group1"}, {"label": "label12", "group": "group1"}]
            },
            id_list[4]: {PWE.labels: [{"label": "label21", "group": "group2"}]},
        }
        self.cleaner_simple.clean()
        self.cleaner_simple.to_web(nodes_attr)
        self.assertEqual(self.cleaner_simple.pipeline_tree, self.cleaner_simple.origin_data)

    def test_to_web__with_subprocess__recursive_nodes_attr(self):
        nodes_attr = {
            id_list[3]: {
                PWE.labels: [{"label": "label11", "group": "group1"}, {"label": "label12", "group": "group1"}]
            },
            PWE.subprocess_detail: {id_list[4]: {id_list3[3]: {PWE.labels: [{"label": "label21", "group": "group2"}]}}},
        }
        self.cleaner_with_sub.clean(with_subprocess=True)
        self.cleaner_with_sub.to_web(nodes_attr, with_subprocess=True)
        self.assertEqual(self.cleaner_with_sub.pipeline_tree, self.cleaner_with_sub.origin_data)

    def test_to_web__with_subprocess__plain_nodes_attr(self):
        nodes_attr = {
            id_list[3]: {
                PWE.labels: [{"label": "label11", "group": "group1"}, {"label": "label12", "group": "group1"}]
            },
            id_list3[3]: {PWE.labels: [{"label": "label21", "group": "group2"}]},
        }
        self.cleaner_with_sub.clean(with_subprocess=True)
        self.cleaner_with_sub.to_web(nodes_attr, with_subprocess=True)
        self.assertEqual(self.cleaner_with_sub.pipeline_tree, self.cleaner_with_sub.origin_data)
