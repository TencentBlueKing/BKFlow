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
from bkflow.template.models import DebugNodeState

PIPELINE = {
    "activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
    "flows": {},
    "gateways": {},
    "constants": {
        "${g1}": {
            "key": "${g1}",
            "name": "g1",
            "show_type": "hide",
            "value": "",
            "source_type": "component_outputs",
            "custom_type": "",
            "source_tag": "",
            "source_info": {"A": ["k1"]},
        }
    },
}


@pytest.mark.django_db
class TestSyncFromDebugTask:
    def test_sync_writes_back_status_and_global_vars(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        ctx.status = "running"
        ctx.active_task_id = 456
        ctx.save()

        client = mocker.MagicMock()
        # 任务整体结束
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FINISHED", "children": {"rtA": {"state": "FINISHED", "elapsed_time": 2}}},
            "message": "",
        }
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        # 节点 A 的输出（含产出 k1）
        client.get_task_node_detail.return_value = {
            "result": True,
            "data": {"outputs": [{"key": "k1", "value": "produced"}], "version": "v1"},
            "message": "",
        }
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)
        ctx.refresh_from_db()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "finished"
        assert ns.log_ref == {"instance_id": 456, "node_id": "rtA", "version": "v1"}
        assert ctx.global_vars.get("${g1}") == "produced"
        assert ctx.status == "idle"  # 整体结束后解锁
