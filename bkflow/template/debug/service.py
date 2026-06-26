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

import copy
import logging

from django.db import transaction
from django.utils import timezone

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.pipeline_web.parser.format import classify_constants
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.models import (
    DebugContext,
    DebugNodeState,
    Template,
    TemplateSnapshot,
)

logger = logging.getLogger(__name__)

# 引擎（bamboo）整体结束态：据此释放调试锁
ENGINE_FINISHED_STATES = {"FINISHED", "REVOKED", "FAILED"}
# 引擎节点态 -> DebugNodeState.status 映射
NODE_STATE_MAP = {"FINISHED": "finished", "FAILED": "failed", "RUNNING": "running", "READY": "not_run"}


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
        self.sync_from_debug_task(ctx)
        ctx.refresh_from_db()
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
        """判定节点是否可单步：引用的产出型变量须已在 global_vars 有值，否则返回缺失项。"""
        act = self.pipeline_tree.get("activities", {}).get(node_id)
        if not act:
            return False, []
        # classify_constants 会就地写入 is_param，深拷贝避免污染共享树
        constants = copy.deepcopy(self.pipeline_tree.get("constants", {}))
        classified = classify_constants(constants, is_subprocess=False)
        produced = {  # ${var} -> producer_node_id
            key: info["source_act"]
            for key, info in classified["data_inputs"].items()
            if info.get("type") == "splice" and info.get("source_act")
        }
        component_data = act.get("component", {}).get("data", {})
        missing = []
        for field in component_data.values():
            value = field.get("value")
            if not isinstance(value, str):
                continue
            for var_key, producer in produced.items():
                if var_key in value and var_key not in (ctx.global_vars or {}):
                    item = {"key": var_key, "source_node_id": producer}
                    if item not in missing:
                        missing.append(item)
        return (len(missing) == 0), missing

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
        """构造调用 Engine 任务接口的客户端（按空间隔离）。"""
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
        """释放调试锁：复位状态、清空持锁用户与持锁时间。"""
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
        # M-3：抢锁前先做幂等的并发预检，避免被拒绝（冲突）的调用提前 sync 改动节点态
        ctx = self.get_or_create_context()
        if ctx.status != "idle":
            raise DebugConflictError("模板正在被 {} 调试".format(ctx.locked_by or "其他用户"))
        self.sync_node_states()
        self._acquire_lock(ctx, operator)

        # task_id 在 create 成功后才赋值；失败兜底据此判断是否需要清理孤儿任务
        task_id = None
        try:
            with transaction.atomic():
                # M-2：每次全局运行都从干净状态开始，故先重置；若后续 create 失败，
                # 这些被清空的历史结果是预期被丢弃的（设计如此）。
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
                message = create_result.get("message", "create debug task failed")
                logger.warning(
                    "[debug global_run] create debug task failed, template_id=%s, message=%s",
                    self.template_id,
                    message,
                )
                raise DebugStateError(message)
            task_id = create_result["data"]["id"]
            ctx.active_task_id = task_id
            ctx.save(update_fields=["active_task_id"])

            start_result = client.operate_task(task_id, "start", {"operator": operator})
            if not start_result.get("result"):
                message = start_result.get("message", "start debug task failed")
                logger.warning(
                    "[debug global_run] start debug task failed, template_id=%s, task_id=%s, message=%s",
                    self.template_id,
                    task_id,
                    message,
                )
                raise DebugStateError(message)
            return {"task_id": task_id, "status": "running"}
        except DebugConflictError:
            # 理论上不会在持锁后再次发生并发冲突；直接抛出，不释放他人持有的锁
            raise
        except Exception as exc:
            if not isinstance(exc, DebugStateError):
                logger.exception(
                    "[debug global_run] unexpected error, template_id=%s, task_id=%s",
                    self.template_id,
                    task_id,
                )
            # 已创建但未成功启动的任务为孤儿，尽力清理并清空悬挂的 active_task_id
            if task_id is not None:
                try:
                    self._task_client().delete_task(task_id)
                except Exception:
                    logger.warning(
                        "[debug global_run] cleanup orphan debug task failed, template_id=%s, task_id=%s",
                        self.template_id,
                        task_id,
                        exc_info=True,
                    )
                ctx.active_task_id = None
                ctx.save(update_fields=["active_task_id"])
            self._release_lock(ctx, status="idle")
            raise

    # ---- 全局调试结果回写 ----
    def _acts_outputs(self):
        """节点输出 -> 全局变量映射：acts_outputs[node_id][output_key] = var_key。"""
        # classify_constants 会就地写入 info["is_param"]，深拷贝避免污染可能被缓存的快照
        constants = copy.deepcopy(self.pipeline_tree.get("constants", {}))
        return classify_constants(constants, is_subprocess=False)["acts_outputs"]

    def sync_from_debug_task(self, ctx: DebugContext):
        """惰性回写：读引擎任务态，回填节点 status/duration/log_ref/outputs 与全局变量，结束则解锁。"""
        # 早返回守卫：仅运行中且存在 active_task_id 才同步，避免空闲态构建真实客户端
        if ctx.status not in ("running", "terminating") or not ctx.active_task_id:
            return
        client = self._task_client()
        states = client.get_task_states(ctx.active_task_id)
        if not states.get("result"):
            return
        data = states["data"]
        children = data.get("children", {})
        # id_map 失败时直接返回：避免空回写后误判结束而释放锁，导致该次结束的结果永久丢失
        id_map_resp = client.get_node_id_map(ctx.active_task_id)
        if not id_map_resp.get("result"):
            return
        id_map = id_map_resp.get("data", {})
        acts_outputs = self._acts_outputs()

        for tpl_node_id, runtime_id in id_map.items():
            ns = DebugNodeState.objects.filter(debug_context=ctx, node_id=tpl_node_id).first()
            if ns is None:
                continue
            child = children.get(runtime_id)
            if not child:
                continue
            ns.status = NODE_STATE_MAP.get(child.get("state"), ns.status)
            ns.duration_ms = int((child.get("elapsed_time") or 0) * 1000)
            if ns.status in ("finished", "failed"):
                detail = client.get_task_node_detail(ctx.active_task_id, runtime_id, data={"include_data": True})
                ddata = detail.get("data", {}) if detail.get("result") else {}
                version = ddata.get("version") or ddata.get("history_id") or "v1"
                ns.log_ref = {"instance_id": ctx.active_task_id, "node_id": runtime_id, "version": version}
                outputs = {o["key"]: o["value"] for o in ddata.get("outputs", []) if isinstance(o, dict) and "key" in o}
                ns.outputs = outputs
                # 输出按 source_act/source_key 回写全局变量
                for out_key, var_key in acts_outputs.get(tpl_node_id, {}).items():
                    if out_key in outputs:
                        ctx.global_vars[var_key] = outputs[out_key]
            ns.save()

        if data.get("state") in ENGINE_FINISHED_STATES:
            self._release_lock(ctx, status="idle")
        ctx.save(update_fields=["global_vars"])

    # ---- 重置 / 终止 / 历史 ----
    def reset(self, node_ids=None) -> list:
        """重置运行结果（保留 mock 配置）；运行中/终止中禁止重置。"""
        ctx = self.sync_node_states()
        if ctx.status in ("running", "terminating"):
            raise DebugConflictError("调试运行中，不能重置")
        return self.reset_run_results(ctx, node_ids=node_ids)

    def terminate(self, node_id=None, operator="") -> dict:
        """终止调试：node_id 指定时强制失败单节点，否则撤销整个任务。

        若引擎拒绝操作，则把状态回滚到 running（保留 locked_by/active_task_id），并抛 DebugStateError，
        避免上下文卡在 terminating 且锁永不释放（系统无 reaper）。
        """
        ctx = self.get_or_create_context()
        if ctx.status == "idle" or not ctx.active_task_id:
            raise DebugStateError("当前没有运行中的调试")
        ctx.status = "terminating"
        ctx.save(update_fields=["status"])
        client = self._task_client()
        if node_id:
            id_map_resp = client.get_node_id_map(ctx.active_task_id)
            if not id_map_resp.get("result"):
                ctx.status = "running"
                ctx.save(update_fields=["status"])
                raise DebugStateError("获取节点 id 映射失败")
            runtime_id = id_map_resp.get("data", {}).get(node_id, node_id)
            op_result = client.node_operate(ctx.active_task_id, runtime_id, "forced_fail", {"operator": operator})
        else:
            op_result = client.operate_task(ctx.active_task_id, "revoke", {"operator": operator})
        if not op_result.get("result"):
            ctx.status = "running"
            ctx.save(update_fields=["status"])
            raise DebugStateError(op_result.get("message", "终止调试失败"))
        # 锁由 sync_from_debug_task 在任务到达 REVOKED 时释放（其守卫含 terminating）
        return {"status": "terminating"}

    def history(self) -> dict:
        """基于保留的 DEBUG 任务实例列出历次运行。"""
        client = self._task_client()
        result = client.task_list(
            data={"template_id": self.template_id, "space_id": self.space_id, "create_method": "DEBUG"}
        )
        items = (result.get("data") or {}).get("results", [])
        runs = []
        for item in items:
            if item.get("is_revoked"):
                run_status = "revoked"
            elif item.get("is_finished"):
                run_status = "finished"
            elif item.get("is_started"):
                run_status = "running"
            else:
                run_status = "created"
            runs.append(
                {
                    "task_id": item.get("id"),
                    "operator": item.get("creator") or item.get("executor"),
                    "started_at": item.get("start_time") or item.get("create_time"),
                    "status": run_status,
                }
            )
        return {"runs": runs}
