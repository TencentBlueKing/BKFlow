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


class TestNodeType(TestCase):
    def test_node_type_values(self):
        from bkflow.pipeline_converter.constants import NodeType

        self.assertEqual(NodeType.START_EVENT, "StartEvent")
        self.assertEqual(NodeType.END_EVENT, "EndEvent")
        self.assertEqual(NodeType.ACTIVITY, "Activity")
        self.assertEqual(NodeType.PARALLEL_GATEWAY, "ParallelGateway")
        self.assertEqual(NodeType.CONDITIONAL_PARALLEL_GATEWAY, "ConditionalParallelGateway")
        self.assertEqual(NodeType.EXCLUSIVE_GATEWAY, "ExclusiveGateway")
        self.assertEqual(NodeType.CONVERGE_GATEWAY, "ConvergeGateway")

    def test_branch_gateway_types(self):
        from bkflow.pipeline_converter.constants import BRANCH_GATEWAY_TYPES

        self.assertIn("ParallelGateway", BRANCH_GATEWAY_TYPES)
        self.assertIn("ExclusiveGateway", BRANCH_GATEWAY_TYPES)
        self.assertIn("ConditionalParallelGateway", BRANCH_GATEWAY_TYPES)
        self.assertNotIn("ConvergeGateway", BRANCH_GATEWAY_TYPES)


class TestPluginTypeEnum(TestCase):
    def test_plugin_type_values(self):
        from bkflow.pipeline_converter.constants import A2FlowPluginType

        self.assertEqual(A2FlowPluginType.COMPONENT, "component")
        self.assertEqual(A2FlowPluginType.REMOTE_PLUGIN, "remote_plugin")
        self.assertEqual(A2FlowPluginType.UNIFORM_API, "uniform_api")


class TestA2FlowVersion(TestCase):
    def test_version_values(self):
        from bkflow.pipeline_converter.constants import A2FlowVersion

        self.assertEqual(A2FlowVersion.V1, "1.0")
        self.assertEqual(A2FlowVersion.V2, "2.0")
