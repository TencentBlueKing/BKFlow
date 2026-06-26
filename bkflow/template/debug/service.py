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

import logging

from django.db import transaction
from django.utils import timezone

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.models import (
    DebugContext,
    DebugNodeState,
    Template,
    TemplateSnapshot,
)

logger = logging.getLogger(__name__)


class DebugConflictError(Exception):
    """并发锁冲突（HTTP 409）"""


class DebugStateError(Exception):
    """状态/参数错误（HTTP 400）"""


class DebugService:
    """调试编排服务（Interface 侧）。所有写操作以 DebugContext 为中心。"""

    def __init__(self, template_id, space_id=None, pipeline_tree=None):
        self.template_id = template_id
        self._space_id = space_id
        self._pipeline_tree = pipeline_tree

    @property
    def space_id(self):
        if self._space_id is None:
            self._space_id = Template.objects.get(id=self.template_id).space_id
        return self._space_id

    @property
    def pipeline_tree(self):
        """优先草稿快照，否则取已发布 pipeline_tree"""
        if self._pipeline_tree is None:
            try:
                self._pipeline_tree = TemplateSnapshot.objects.get(
                    template_id=self.template_id, draft=True, is_deleted=False
                ).data
            except TemplateSnapshot.DoesNotExist:
                self._pipeline_tree = Template.objects.get(id=self.template_id).pipeline_tree
        return self._pipeline_tree

    def get_or_create_context(self) -> DebugContext:
        ctx, _ = DebugContext.objects.get_or_create(template_id=self.template_id, defaults={"space_id": self.space_id})
        return ctx

    def sync_node_states(self) -> DebugContext:
        """按当前 pipeline_tree 增删 DebugNodeState；保留已存在节点的配置与运行态。"""
        ctx = self.get_or_create_context()
        activities = self.pipeline_tree.get("activities", {})
        existing = {ns.node_id: ns for ns in DebugNodeState.objects.filter(debug_context=ctx)}
        tree_node_ids = set(activities.keys())

        to_create = [
            DebugNodeState(debug_context=ctx, node_id=node_id, node_type=act.get("type", "ServiceActivity"))
            for node_id, act in activities.items()
            if node_id not in existing
        ]
        if to_create:
            DebugNodeState.objects.bulk_create(to_create, ignore_conflicts=True)
        stale = set(existing.keys()) - tree_node_ids
        if stale:
            DebugNodeState.objects.filter(debug_context=ctx, node_id__in=stale).delete()
        return ctx

    def input_schema(self):
        """解析用户输入类常量（show_type=show），返回前端可渲染元数据。"""
        fields = []
        for key, c in self.pipeline_tree.get("constants", {}).items():
            if c.get("show_type") != "show":
                continue
            fields.append(
                {
                    "key": key,
                    "name": c.get("name", key),
                    "type": c.get("custom_type") or "string",
                    "default": c.get("value", ""),
                    "required": True,
                }
            )
        return fields

    def build_context_view(self) -> dict:
        ctx = self.sync_node_states()
        node_views = []
        for ns in DebugNodeState.objects.filter(debug_context=ctx).order_by("node_id"):
            can_step, missing = self.compute_can_step(ctx, ns.node_id)
            node_views.append(
                {
                    "node_id": ns.node_id,
                    "node_type": ns.node_type,
                    "execution_mode": ns.execution_mode,
                    "mock_result": ns.mock_result if ns.execution_mode == "mock" else None,
                    "status": ns.status,
                    "can_step": can_step,
                    "missing_vars": missing,
                    "duration_ms": ns.duration_ms,
                    "error_detail": ns.error_detail or None,
                    "log_ref": ns.log_ref or None,
                }
            )
        return {
            "template_id": self.template_id,
            "status": ctx.status,
            "locked_by": ctx.locked_by,
            "active_task_id": ctx.active_task_id,
            "last_inputs": ctx.last_inputs,
            "global_vars": ctx.global_vars,
            "nodes": node_views,
        }

    def compute_can_step(self, ctx, node_id):
        """占位：Phase 3 Task 3.5 实现真正逻辑，此处先恒返回可单步。"""
        return True, []

    # ---- 内部工具 ----
    def _refresh_tree_fingerprint(self, ctx: DebugContext):
        ctx.tree_fingerprint = compute_tree_fingerprint(self.pipeline_tree)
        node_hashes = ctx.tree_fingerprint["nodes"]
        states = list(DebugNodeState.objects.filter(debug_context=ctx))
        for ns in states:
            if ns.node_id in node_hashes:
                ns.config_hash = node_hashes[ns.node_id]
        if states:
            DebugNodeState.objects.bulk_update(states, ["config_hash"])
        ctx.save(update_fields=["tree_fingerprint"])

    # ---- 全局调试编排 ----
    def _task_client(self):
        return TaskComponentClient(space_id=self.space_id)

    def _acquire_lock(self, ctx: DebugContext, operator: str):
        """CAS 抢锁：仅当 status=idle 时置为 running，0 行更新即冲突。"""
        updated = DebugContext.objects.filter(id=ctx.id, status="idle").update(
            status="running", locked_by=operator, locked_at=timezone.now()
        )
        if not updated:
            ctx.refresh_from_db()
            raise DebugConflictError("模板正在被 {} 调试".format(ctx.locked_by or "其他用户"))
        ctx.refresh_from_db()

    def _release_lock(self, ctx: DebugContext, status="idle"):
        ctx.status = status
        ctx.locked_by = ""
        ctx.locked_at = None
        ctx.save(update_fields=["status", "locked_by", "locked_at"])

    def reset_run_results(self, ctx: DebugContext, node_ids=None):
        """清运行结果，保留 mock 配置；node_ids 为 None 时全量。"""
        qs = DebugNodeState.objects.filter(debug_context=ctx)
        if node_ids is not None:
            qs = qs.filter(node_id__in=node_ids)
        reset_ids = list(qs.values_list("node_id", flat=True))
        qs.update(
            status="not_run",
            inputs={},
            outputs={},
            duration_ms=None,
            error_detail={},
            log_ref={},
            last_run_at=None,
        )
        return reset_ids

    def materialize_mock_data(self, ctx: DebugContext):
        """把 execution_mode=mock 的节点物化为 TaskMockData 入参（模板 id，Engine 侧再映射）。"""
        nodes, outputs, fail_nodes, errors = [], {}, [], {}
        for ns in DebugNodeState.objects.filter(debug_context=ctx, execution_mode="mock"):
            nodes.append(ns.node_id)
            if ns.mock_result == "fail":
                fail_nodes.append(ns.node_id)
                errors[ns.node_id] = ns.mock_error or "mock failed"
            else:
                outputs[ns.node_id] = ns.mock_outputs or {}
        return {"nodes": nodes, "outputs": outputs, "fail_nodes": fail_nodes, "errors": errors}

    def global_run(self, inputs: dict, operator: str) -> dict:
        """全局调试：抢锁 -> 重置 -> 物化 -> 创建并启动 DEBUG 任务。"""
        ctx = self.sync_node_states()
        if ctx.status != "idle":
            raise DebugConflictError("模板正在被 {} 调试".format(ctx.locked_by or "其他用户"))
        self._acquire_lock(ctx, operator)
        try:
            with transaction.atomic():
                self.reset_run_results(ctx, node_ids=None)
                ctx.global_vars = dict(inputs or {})
                ctx.last_inputs = dict(inputs or {})
                self._refresh_tree_fingerprint(ctx)
                ctx.save(update_fields=["global_vars", "last_inputs"])

            template = Template.objects.filter(id=self.template_id).first()
            create_data = {
                "template_id": self.template_id,
                "space_id": self.space_id,
                "scope_type": template.scope_type if template else None,
                "scope_value": template.scope_value if template else None,
                "pipeline_tree": self.pipeline_tree,
                "mock_data": self.materialize_mock_data(ctx),
                "create_method": "DEBUG",
                "trigger_method": "manual",
                "constants": inputs or {},
            }
            client = self._task_client()
            create_result = client.create_task(create_data)
            if not create_result.get("result"):
                self._release_lock(ctx, status="idle")
                raise DebugStateError(create_result.get("message", "create debug task failed"))
            task_id = create_result["data"]["id"]
            ctx.active_task_id = task_id
            ctx.save(update_fields=["active_task_id"])

            start_result = client.operate_task(task_id, "start", {"operator": operator})
            if not start_result.get("result"):
                self._release_lock(ctx, status="idle")
                raise DebugStateError(start_result.get("message", "start debug task failed"))
            return {"task_id": task_id, "status": "running"}
        except (DebugConflictError, DebugStateError):
            raise
        except Exception:
            self._release_lock(ctx, status="idle")
            raise
