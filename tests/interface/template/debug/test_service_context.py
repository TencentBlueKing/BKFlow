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

GATEWAY_PIPELINE = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
    },
    "flows": {},
    "gateways": {
        "EG": {
            "id": "EG",
            "type": "ExclusiveGateway",
            "conditions": {"flow_positive": {"name": "positive", "evaluate": "${count} > 0"}},
            "default_condition": {"flow_id": "flow_default"},
            "extra_info": {"parse_lang": "boolrule"},
        },
        "CPG": {
            "id": "CPG",
            "type": "ConditionalParallelGateway",
            "conditions": {"flow_positive": {"name": "positive", "evaluate": "${count} > 0"}},
            "default_condition": {"flow_id": "flow_default"},
            "extra_info": {"parse_lang": "boolrule"},
        },
        "PG": {"id": "PG", "type": "ParallelGateway"},
        "CG": {"id": "CG", "type": "ConvergeGateway"},
    },
    "constants": {
        "${count}": {
            "key": "${count}",
            "name": "count",
            "show_type": "hide",
            "value": 1,
            "source_type": "custom",
            "source_info": {},
            "custom_type": "int",
            "source_tag": "",
        }
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

    def test_sync_node_states_repairs_changed_node_type(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=GATEWAY_PIPELINE)
        ctx = svc.get_or_create_context()
        DebugNodeState.objects.create(debug_context=ctx, node_id="EG", node_type="ServiceActivity")

        svc.sync_node_states()

        assert DebugNodeState.objects.get(debug_context=ctx, node_id="EG").node_type == "ExclusiveGateway"

    def test_sync_node_states_includes_only_debuggable_gateways(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=GATEWAY_PIPELINE)
        ctx = svc.sync_node_states()

        states = {
            node_id: node_type
            for node_id, node_type in DebugNodeState.objects.filter(debug_context=ctx).values_list(
                "node_id", "node_type"
            )
        }

        assert states == {"A": "ServiceActivity", "EG": "ExclusiveGateway", "CPG": "ConditionalParallelGateway"}

    def test_input_schema_excludes_hidden(self):
        tree = {
            "activities": {},
            "flows": {},
            "gateways": {},
            "constants": {"${h}": {"key": "${h}", "name": "h", "show_type": "hide", "custom_type": "input"}},
        }
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=tree)
        assert svc.input_schema() == []

    def test_build_context_view_renders_nodes(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        view = svc.build_context_view()
        assert view["status"] == "idle"
        assert view["template_id"] == 1
        assert [n["node_id"] for n in view["nodes"]] == ["A", "B"]  # 按 node_id 排序
        node_a = view["nodes"][0]
        assert node_a["execution_mode"] == "real"
        assert node_a["supports_mock"] is True
        assert node_a["mock_result"] is None  # real 模式不返回 mock_result
        assert node_a["mock_outputs"] is None
        assert node_a["status"] == "not_run"
        assert node_a["can_step"] is True  # Phase 3 前的占位
        assert node_a["log_ref"] is None and node_a["error_detail"] is None
        assert node_a["waiting_reason"] is None
        assert node_a["selected_flow_ids"] == []
        assert node_a["condition_results"] == []
        assert view["last_task_id"] is None
        assert view["last_run_type"] is None
        assert view["last_run_status"] == "not_run"
        assert view["last_error_detail"] is None

    def test_build_context_view_returns_gateway_capabilities_and_state(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=GATEWAY_PIPELINE)
        ctx = svc.sync_node_states()
        DebugNodeState.objects.filter(debug_context=ctx, node_id="EG").update(
            execution_mode="mock",
            status="finished",
            outputs={
                "selected_flow_ids": ["flow_positive"],
                "condition_results": [
                    {
                        "flow_id": "flow_positive",
                        "name": "positive",
                        "expression": "${count} > 0",
                        "resolved_expression": "1 > 0",
                        "matched": True,
                    }
                ],
            },
        )

        gateway = next(node for node in svc.build_context_view()["nodes"] if node["node_id"] == "EG")

        assert gateway["execution_mode"] == "real"
        assert gateway["supports_mock"] is False
        assert gateway["mock_result"] is None
        assert gateway["selected_flow_ids"] == ["flow_positive"]
        assert gateway["condition_results"][0]["matched"] is True

    def test_build_context_view_returns_mock_outputs_for_success_preset(self):
        """mock 成功预设刷新后应能回填保存的输出"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(
            execution_mode="mock", mock_result="success", mock_outputs={"response": {"code": 0}}
        )

        node_a = svc.build_context_view()["nodes"][0]

        assert node_a["mock_outputs"] == {"response": {"code": 0}}

    def test_build_context_view_returns_mock_error_for_fail_preset(self):
        """mock 失败预设刷新后应能回填错误文案"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        DebugNodeState.objects.filter(debug_context=ctx, node_id="A").update(
            execution_mode="mock", mock_result="fail", mock_error="preset boom"
        )

        node_a = svc.build_context_view()["nodes"][0]

        assert node_a["execution_mode"] == "mock"
        assert node_a["mock_result"] == "fail"
        assert node_a["mock_error"] == "preset boom"
        assert node_a["mock_outputs"] is None
