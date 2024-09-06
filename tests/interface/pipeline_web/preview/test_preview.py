# -*- coding: utf-8 -*-
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


from unittest.mock import MagicMock, patch

from django.test import TestCase

from bkflow.pipeline_web.preview import preview_template_tree

MOCK_PIPELINE_TREE = {
    "activities": {
        "node1": {"id": "node1", "type": "ServiceActivity", "optional": True},
        "node2": {"id": "node2", "type": "ServiceActivity", "optional": True},
        "node3": {"id": "node3", "type": "ServiceActivity", "optional": True},
        "node4": {"id": "node4", "type": "ServiceActivity", "optional": True},
    },
    "constants": {
        "${param1}": {"value": "${parent_param2}", "show_type": "show", "source_type": "else"},
        "${param2}": {"value": "constant_value_2", "show_type": "show", "source_type": "else"},
        "${custom_param2}": {"value": "custom_value_2", "show_type": "show", "source_type": "custom"},
    },
}


class MockTemplate(object):
    def __init__(self, pipeline_tree):
        self.pipeline_tree = pipeline_tree

    def get_pipeline_tree_by_version(self, version):
        return self.pipeline_tree

    def get_outputs(self, version):
        return {
            "${outputs_param1}": {
                "name": "outputs_param1",
                "key": "${outputs_param1}",
                "source_info": {"node1": ["_loop"]},
                "source_type": "component_outputs",
            },
            "${outputs_param2}": {
                "name": "outputs_param2",
                "key": "${outputs_param2}",
                "source_info": {"node3": ["_result"]},
                "source_type": "component_outputs",
            },
            "${inputs_param1}": {
                "name": "inputs_param1",
                "key": "${inputs_param1}",
                "source_info": {"node2": ["${_loop}"]},
                "source_type": "component_inputs",
            },
            "${inputs_param2}": {
                "name": "inputs_param2",
                "key": "${inputs_param2}",
                "source_info": {"node4": ["${_loop}"]},
                "source_type": "component_inputs",
            },
            "${custom_param1}": {
                "name": "custom_param1",
                "key": "${custom_param1}",
                "source_info": {},
                "source_type": "custom",
            },
            "${custom_param2}": {
                "name": "custom_param2",
                "key": "${custom_param2}",
                "source_info": {},
                "source_type": "custom",
            },
        }


def mock_preview_pipeline_tree_exclude_task_nodes(pipeline_tree, exclude_task_nodes_id=None):
    pipeline_tree["activities"] = {
        k: v for k, v in pipeline_tree["activities"].items() if k not in exclude_task_nodes_id
    }

    pipeline_tree["constants"].pop("${param2}", "")
    pipeline_tree["constants"].pop("${custom_param2}", "")


class MockPipelineTemplateWebPreviewer(object):
    def __init__(self):
        self.preview_pipeline_tree_exclude_task_nodes = MagicMock(
            side_effect=mock_preview_pipeline_tree_exclude_task_nodes
        )


MockPipelineTemplateWebPreviewer = MockPipelineTemplateWebPreviewer()


class PipelineTemplateWebPreviewerTestCase(TestCase):
    @patch("bkflow.pipeline_web.preview.PipelineTemplateWebPreviewer", MockPipelineTemplateWebPreviewer)
    def test_preview_template_tree(self):
        data = preview_template_tree(MOCK_PIPELINE_TREE, ["node1", "node4"])

        MockPipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes.assert_called()

        self.assertEqual(
            data,
            {
                "pipeline_tree": {
                    "activities": {
                        "node2": {"id": "node2", "type": "ServiceActivity", "optional": True},
                        "node3": {"id": "node3", "type": "ServiceActivity", "optional": True},
                    },
                    "constants": {
                        "${param1}": {"value": "${parent_param2}", "show_type": "show", "source_type": "else"}
                    },
                },
                "constants_not_referred": {
                    "${param2}": {"value": "constant_value_2", "show_type": "show", "source_type": "else"},
                    "${custom_param2}": {"value": "custom_value_2", "show_type": "show", "source_type": "custom"},
                },
            },
        )
