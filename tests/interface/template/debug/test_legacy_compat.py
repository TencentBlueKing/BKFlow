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

import pytest

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugNodeState, TemplateMockData, TemplateMockScheme

TREE = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
        "B": {"id": "B", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
    },
    "flows": {},
    "gateways": {},
    "constants": {},
}


@pytest.mark.django_db
class TestLegacyCompat:
    def test_scheme_nodes_initialized_as_mock(self):
        TemplateMockScheme.objects.create(space_id=10, template_id=1, data={"nodes": ["A"]})
        TemplateMockData.objects.create(
            space_id=10, template_id=1, node_id="A", name="d", data={"k": "v"}, is_default=True
        )
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        a = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        b = DebugNodeState.objects.get(debug_context=ctx, node_id="B")
        assert a.execution_mode == "mock"
        assert a.mock_outputs == {"k": "v"}
        assert b.execution_mode == "real"

    def test_no_scheme_keeps_all_real(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        a = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        b = DebugNodeState.objects.get(debug_context=ctx, node_id="B")
        assert a.execution_mode == "real"
        assert b.execution_mode == "real"
