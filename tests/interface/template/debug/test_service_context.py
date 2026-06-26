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
from bkflow.template.models import DebugContext, DebugNodeState

PIPELINE = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
        "B": {
            "id": "B",
            "type": "ServiceActivity",
            "component": {"code": "t", "data": {"y": {"hook": True, "value": "${biz}"}}},
        },
    },
    "flows": {},
    "gateways": {},
    "constants": {
        "${biz}": {
            "key": "${biz}",
            "name": "业务",
            "show_type": "show",
            "value": "",
            "source_type": "custom",
            "custom_type": "input",
            "source_tag": "input.input",
            "source_info": {},
        },
    },
}


@pytest.mark.django_db
class TestDebugServiceContext:
    def test_get_or_create_context_and_sync_nodes(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        assert isinstance(ctx, DebugContext)
        svc.sync_node_states()
        assert set(DebugNodeState.objects.filter(debug_context=ctx).values_list("node_id", flat=True)) == {"A", "B"}

    def test_sync_node_states_prunes_removed(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        DebugNodeState.objects.create(debug_context=ctx, node_id="GHOST")
        svc.sync_node_states()
        assert not DebugNodeState.objects.filter(debug_context=ctx, node_id="GHOST").exists()

    def test_input_schema_returns_show_constants(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        fields = svc.input_schema()
        assert fields == [{"key": "${biz}", "name": "业务", "type": "input", "default": "", "required": True}]

    def test_sync_node_states_idempotent(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        svc.sync_node_states()  # 二次同步：不报错、不重复
        assert set(DebugNodeState.objects.filter(debug_context=ctx).values_list("node_id", flat=True)) == {"A", "B"}

    def test_sync_node_states_sets_node_type(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").node_type == "ServiceActivity"

    def test_input_schema_excludes_hidden(self):
        tree = {
            "activities": {},
            "flows": {},
            "gateways": {},
            "constants": {"${h}": {"key": "${h}", "name": "h", "show_type": "hide", "custom_type": "input"}},
        }
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=tree)
        assert svc.input_schema() == []
