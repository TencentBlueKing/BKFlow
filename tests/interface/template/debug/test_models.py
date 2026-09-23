"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import pytest
from django.db import IntegrityError, transaction

from bkflow.template.models import DebugContext, DebugNodeState


@pytest.mark.django_db
class TestDebugModels:
    """DebugContext / DebugNodeState 基本约束"""

    def test_create_context_defaults(self):
        ctx = DebugContext.objects.create(template_id=1, space_id=10)
        assert ctx.status == "idle"
        assert ctx.global_vars == {}
        assert ctx.last_inputs == {}
        assert ctx.tree_fingerprint == {}
        assert ctx.active_task_id is None
        assert ctx.active_run_type == ""
        assert ctx.active_node_id == ""
        assert ctx.last_task_id is None
        assert ctx.last_run_type == ""
        assert ctx.last_run_status == "not_run"
        assert ctx.last_error_detail == {}
        assert ctx.locked_by == ""
        assert ctx.locked_at is None

    def test_template_id_unique(self):
        DebugContext.objects.create(template_id=1, space_id=10)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DebugContext.objects.create(template_id=1, space_id=10)

    def test_node_state_defaults_and_unique(self):
        ctx = DebugContext.objects.create(template_id=2, space_id=10)
        ns = DebugNodeState.objects.create(debug_context=ctx, node_id="n1")
        assert ns.execution_mode == "real"
        assert ns.mock_result == "success"
        assert ns.status == "not_run"
        assert ns.node_type == "ServiceActivity"
        assert ns.mock_outputs == {} and ns.inputs == {} and ns.outputs == {}
        assert ns.error_detail == {} and ns.duration_ms is None and ns.last_run_at is None
        assert ns.waiting_reason == ""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DebugNodeState.objects.create(debug_context=ctx, node_id="n1")

    def test_nested_json_persist_and_reload(self):
        """决策 #1：JSON 字段用普通 JSONField，必须能存取嵌套结构（不加密、不抛错）。"""
        ctx = DebugContext.objects.create(
            template_id=3,
            space_id=10,
            global_vars={"${ips}": ["1.1.1.1", "2.2.2.2"], "${obj}": {"a": {"b": 1}}},
        )
        ns = DebugNodeState.objects.create(
            debug_context=ctx,
            node_id="n2",
            inputs={"params": {"timeout": 30, "hosts": [1, 2, 3]}},
            outputs={"result": {"data": [{"k": "v"}]}},
            error_detail={"type": "runtime", "message": "boom", "extra": {"code": 500}},
        )
        ctx.refresh_from_db()
        ns.refresh_from_db()
        assert ctx.global_vars["${ips}"] == ["1.1.1.1", "2.2.2.2"]
        assert ctx.global_vars["${obj}"] == {"a": {"b": 1}}
        assert ns.inputs["params"]["hosts"] == [1, 2, 3]
        assert ns.outputs["result"]["data"] == [{"k": "v"}]
        assert ns.error_detail["extra"]["code"] == 500

    def test_node_states_related_name_and_cascade(self):
        """物理删除上下文时级联清理节点态（reset 走 queryset 删除，不依赖软删级联）。"""
        ctx = DebugContext.objects.create(template_id=4, space_id=10)
        DebugNodeState.objects.create(debug_context=ctx, node_id="a")
        DebugNodeState.objects.create(debug_context=ctx, node_id="b")
        assert ctx.node_states.count() == 2
        ctx.hard_delete()
        assert DebugNodeState.objects.filter(node_id__in=["a", "b"]).count() == 0
