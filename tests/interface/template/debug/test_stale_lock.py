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

import datetime

import pytest
from django.utils import timezone

from bkflow.template.debug.service import DebugConflictError, DebugService
from bkflow.template.models import DebugNodeState

PIPELINE = {
    "activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
    "flows": {},
    "gateways": {},
    "constants": {},
}


@pytest.mark.django_db
class TestStaleLockReclaim:
    """被遗弃（前端关闭/轮询中断）且超过 TTL 的调试锁应可被新操作回收，避免模板卡死。"""

    def _svc(self, mocker):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        client = mocker.MagicMock()
        client.create_task.return_value = {"result": True, "data": {"id": 456}, "message": ""}
        client.operate_task.return_value = {"result": True, "data": {}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)
        return svc, client

    def _make_stale_running_ctx(self, svc, minutes_ago=30, task_id=999):
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.locked_by = "ghost"
        ctx.locked_at = timezone.now() - datetime.timedelta(minutes=minutes_ago)
        ctx.active_task_id = task_id
        ctx.save()
        return ctx

    def test_global_run_reclaims_stale_lock_and_revokes_orphan(self, mocker):
        svc, client = self._svc(mocker)
        ctx = self._make_stale_running_ctx(svc, minutes_ago=30, task_id=999)

        result = svc.global_run(inputs={}, operator="admin")

        ctx.refresh_from_db()
        assert result["status"] == "running"
        assert ctx.status == "running"
        assert ctx.locked_by == "admin"
        assert ctx.active_task_id == 456
        # 孤儿任务被尽力撤销
        client.operate_task.assert_any_call(999, "revoke", {"operator": "system"})

    def test_global_run_fresh_lock_still_conflicts(self, mocker):
        svc, _ = self._svc(mocker)
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.locked_by = "bob"
        ctx.locked_at = timezone.now()
        ctx.active_task_id = 111
        ctx.save()

        with pytest.raises(DebugConflictError) as exc:
            svc.global_run(inputs={}, operator="admin")
        assert "bob" in str(exc.value)

    def test_reset_reclaims_stale_lock(self, mocker):
        svc, _ = self._svc(mocker)
        ctx = self._make_stale_running_ctx(svc, minutes_ago=30, task_id=999)
        DebugNodeState.objects.create(debug_context=ctx, node_id="A", status="finished", outputs={"k": "v"})

        reset_ids = svc.reset()

        ctx.refresh_from_db()
        assert ctx.status == "idle"
        assert "A" in reset_ids
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "not_run" and ns.outputs == {}

    def test_reclaim_respects_custom_ttl(self, mocker, settings):
        settings.BKFLOW_DEBUG_LOCK_TTL_SECONDS = 60
        svc, _ = self._svc(mocker)
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.locked_by = "ghost"
        ctx.locked_at = timezone.now() - datetime.timedelta(seconds=120)
        ctx.active_task_id = 999
        ctx.save()

        assert svc._reclaim_stale_lock(ctx) is True
        ctx.refresh_from_db()
        assert ctx.status == "idle"

    def test_reclaim_noop_when_not_stale(self, mocker, settings):
        settings.BKFLOW_DEBUG_LOCK_TTL_SECONDS = 600
        svc, _ = self._svc(mocker)
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.locked_by = "ghost"
        ctx.locked_at = timezone.now() - datetime.timedelta(seconds=60)
        ctx.active_task_id = 999
        ctx.save()

        assert svc._reclaim_stale_lock(ctx) is False
        ctx.refresh_from_db()
        assert ctx.status == "running"
