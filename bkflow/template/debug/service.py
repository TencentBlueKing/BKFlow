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
import datetime
import logging
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.pipeline_web.parser.format import classify_constants
from bkflow.template.debug.dependency import (
    build_dependency_graph,
    closure,
    compute_tree_fingerprint,
)
from bkflow.template.debug.gateway import (
    DEBUGGABLE_GATEWAY_TYPES,
    GatewayEvaluationError,
    evaluate_gateway,
    gateway_missing_vars,
)
from bkflow.template.models import (
    DebugContext,
    DebugNodeState,
    Template,
    TemplateMockData,
    TemplateMockScheme,
    TemplateSnapshot,
)

logger = logging.getLogger(__name__)

# 引擎（bamboo）整体结束态：据此释放调试锁
ENGINE_FINISHED_STATES = {"FINISHED", "REVOKED", "FAILED"}
# 引擎节点态 -> DebugNodeState.status 映射
NODE_STATE_MAP = {
    "FINISHED": "finished",
    "FAILED": "failed",
    "RUNNING": "running",
    "READY": "not_run",
    "SUSPENDED": "paused",
}
ENGINE_RUN_STATE_MAP = {"FINISHED": "finished", "FAILED": "failed", "REVOKED": "revoked"}


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
        gateways = self.pipeline_tree.get("gateways", {})
        debug_nodes = {**activities, **gateways}
        existing = {ns.node_id: ns for ns in DebugNodeState.objects.filter(debug_context=ctx)}
        tree_node_ids = set(debug_nodes)

        new_node_ids = [node_id for node_id in debug_nodes if node_id not in existing]
        to_create = [
            DebugNodeState(
                debug_context=ctx,
                node_id=node_id,
                node_type=debug_nodes[node_id].get("type", "ServiceActivity"),
            )
            for node_id in new_node_ids
        ]
        if to_create:
            # 并发安全：ignore_conflicts 保证并发 sync 不会因唯一键冲突报错
            DebugNodeState.objects.bulk_create(to_create, ignore_conflicts=True)
            self._apply_legacy_mock_scheme(ctx, [node_id for node_id in new_node_ids if node_id in activities])
        to_update = []
        for node_id, ns in existing.items():
            expected_type = (debug_nodes.get(node_id) or {}).get("type", "ServiceActivity")
            if node_id in debug_nodes and ns.node_type != expected_type:
                ns.node_type = expected_type
                to_update.append(ns)
        if to_update:
            DebugNodeState.objects.bulk_update(to_update, ["node_type"])
        if gateways:
            DebugNodeState.objects.filter(debug_context=ctx, node_id__in=gateways).exclude(
                execution_mode="real"
            ).update(execution_mode="real")
        stale = set(existing.keys()) - tree_node_ids
        if stale:
            DebugNodeState.objects.filter(debug_context=ctx, node_id__in=stale).delete()
        return ctx

    def _legacy_scheme_nodes(self):
        """读取该模板旧 TemplateMockScheme.data['nodes']，作为初始 mock 节点集合。"""
        scheme = TemplateMockScheme.objects.filter(template_id=self.template_id).first()
        if not scheme:
            return set()
        return set((scheme.data or {}).get("nodes", []))

    def _apply_legacy_mock_scheme(self, ctx, new_node_ids):
        """首次创建节点态时，把历史勾选的 mock 节点初始化为 mock，并用默认 TemplateMockData 填充 mock_outputs。

        仅作用于本次新建、且仍为默认 real 的节点（execution_mode='real' 过滤），不覆盖用户已有选择；
        无旧 scheme 时不做任何变更，避免误把节点改成 mock（regression 保护）。
        """
        targets = self._legacy_scheme_nodes().intersection(new_node_ids)
        for node_id in targets:
            default_md = TemplateMockData.objects.filter(
                template_id=self.template_id, node_id=node_id, is_default=True
            ).first()
            DebugNodeState.objects.filter(debug_context=ctx, node_id=node_id, execution_mode="real").update(
                execution_mode="mock", mock_outputs=(default_md.data if default_md else {}) or {}
            )

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

    def _is_debuggable_gateway(self, node_id):
        gateway = self.pipeline_tree.get("gateways", {}).get(node_id) or {}
        return gateway.get("type") in DEBUGGABLE_GATEWAY_TYPES

    def _is_gateway(self, node_id):
        return node_id in self.pipeline_tree.get("gateways", {})

    def build_context_view(self) -> dict:
        ctx = self.sync_node_states()
        self.sync_from_debug_task(ctx)
        ctx.refresh_from_db()
        node_views = []
        for ns in DebugNodeState.objects.filter(debug_context=ctx).order_by("node_id"):
            can_step, missing = self.compute_can_step(ctx, ns.node_id)
            is_gateway = self._is_gateway(ns.node_id)
            supports_step = not is_gateway or self._is_debuggable_gateway(ns.node_id)
            gateway_result = (ns.outputs or {}) if is_gateway else {}
            node_views.append(
                {
                    "node_id": ns.node_id,
                    "node_type": ns.node_type,
                    "execution_mode": "real" if is_gateway else ns.execution_mode,
                    "supports_step": supports_step,
                    "supports_mock": not is_gateway,
                    "mock_result": ns.mock_result if not is_gateway and ns.execution_mode == "mock" else None,
                    "mock_outputs": (
                        ns.mock_outputs
                        if not is_gateway and ns.execution_mode == "mock" and ns.mock_result == "success"
                        else None
                    ),
                    "mock_error": (
                        ns.mock_error
                        if not is_gateway and ns.execution_mode == "mock" and ns.mock_result == "fail"
                        else None
                    ),
                    "status": ns.status,
                    "waiting_reason": ns.waiting_reason or None,
                    "can_step": can_step,
                    "missing_vars": missing,
                    "duration_ms": ns.duration_ms,
                    "error_detail": ns.error_detail or None,
                    "log_ref": ns.log_ref or None,
                    "selected_flow_ids": gateway_result.get("selected_flow_ids", []),
                    "condition_results": gateway_result.get("condition_results", []),
                }
            )
        return {
            "template_id": self.template_id,
            "status": ctx.status,
            "locked_by": ctx.locked_by,
            "active_task_id": ctx.active_task_id,
            "active_run_type": ctx.active_run_type or None,
            "active_node_id": ctx.active_node_id or None,
            "last_task_id": ctx.last_task_id,
            "last_run_type": ctx.last_run_type or None,
            "last_run_status": ctx.last_run_status,
            "last_error_detail": ctx.last_error_detail or None,
            "last_inputs": ctx.last_inputs,
            "global_vars": ctx.global_vars,
            "nodes": node_views,
        }

    def compute_can_step(self, ctx, node_id):
        """判定节点是否可单步：引用的产出型变量须已在 global_vars 有值，否则返回缺失项。"""
        if self._is_debuggable_gateway(node_id):
            missing = gateway_missing_vars(self.pipeline_tree, node_id, ctx.global_vars or {})
            return (len(missing) == 0), missing
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
        """释放调试锁：复位状态并清空 active 字段，保留最近一次运行结果。"""
        ctx.status = status
        ctx.locked_by = ""
        ctx.locked_at = None
        ctx.active_task_id = None
        ctx.active_run_type = ""
        ctx.active_node_id = ""
        ctx.save(
            update_fields=[
                "status",
                "locked_by",
                "locked_at",
                "active_task_id",
                "active_run_type",
                "active_node_id",
            ]
        )

    def _reclaim_stale_lock(self, ctx: DebugContext) -> bool:
        """回收被遗弃的调试锁。

        正常情况下锁仅在 ``GET /debug/context`` 触发 ``sync_from_debug_task`` 时释放；若前端关闭
        或轮询中断，上下文会长期停留在 running/terminating，导致模板被一把永不释放的锁卡死（系统无
        后台 reaper）。这里在持锁超过 TTL 时，以 CAS 方式原子地把它复位为 idle，并尽力撤销可能仍在
        引擎侧运行的孤儿任务。

        :return: 成功回收返回 True 并刷新 ctx；否则返回 False（未持锁 / 未过期 / 竞争失败）。
        """
        if ctx.status not in ("running", "terminating") or not ctx.locked_at:
            return False
        ttl = getattr(settings, "BKFLOW_DEBUG_LOCK_TTL_SECONDS", 600)
        threshold = timezone.now() - datetime.timedelta(seconds=ttl)
        stale_task_id = ctx.active_task_id
        # CAS：仅当行仍处于陈旧的持锁态（running/terminating 且 locked_at 早于阈值）时才回收，
        # 避免与正常释放或他人正常持锁竞争。
        reclaimed = DebugContext.objects.filter(
            id=ctx.id, status__in=("running", "terminating"), locked_at__lt=threshold
        ).update(
            status="idle",
            locked_by="",
            locked_at=None,
            active_task_id=None,
            active_run_type="",
            active_node_id="",
        )
        if not reclaimed:
            return False
        logger.warning(
            "[debug] reclaimed stale debug lock, template_id=%s, prev_status=%s, prev_task_id=%s, prev_locked_by=%s",
            self.template_id,
            ctx.status,
            stale_task_id,
            ctx.locked_by,
        )
        if stale_task_id:
            try:
                self._task_client().operate_task(stale_task_id, "revoke", {"operator": "system"})
            except Exception:
                logger.warning(
                    "[debug] revoke orphan debug task on reclaim failed, template_id=%s, task_id=%s",
                    self.template_id,
                    stale_task_id,
                    exc_info=True,
                )
        ctx.refresh_from_db()
        return True

    def reset_run_results(self, ctx: DebugContext, node_ids=None):
        """清运行结果，保留 mock 配置；node_ids 为 None 时全量。"""
        qs = DebugNodeState.objects.filter(debug_context=ctx)
        if node_ids is not None:
            qs = qs.filter(node_id__in=node_ids)
        reset_ids = list(qs.values_list("node_id", flat=True))
        qs.update(
            status="not_run",
            waiting_reason="",
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
        if ctx.status != "idle" and not self._reclaim_stale_lock(ctx):
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
            ctx.active_run_type = "global"
            ctx.active_node_id = ""
            ctx.last_task_id = task_id
            ctx.last_run_type = "global"
            ctx.last_run_status = "running"
            ctx.last_error_detail = {}
            ctx.save(
                update_fields=[
                    "active_task_id",
                    "active_run_type",
                    "active_node_id",
                    "last_task_id",
                    "last_run_type",
                    "last_run_status",
                    "last_error_detail",
                ]
            )

            start_result = client.operate_task(task_id, "start", {"operator": operator})
            if not start_result.get("result"):
                message = start_result.get("message", "start debug task failed")
                logger.warning(
                    "[debug global_run] start debug task failed, template_id=%s, task_id=%s, message=%s",
                    self.template_id,
                    task_id,
                    message,
                )
                ctx.last_run_status = "failed"
                ctx.last_error_detail = {"type": "start", "message": message, "task_id": task_id}
                ctx.save(update_fields=["last_run_status", "last_error_detail"])
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

    @staticmethod
    def _flatten_state_children(children):
        flattened = {}
        pending = list((children or {}).items())
        while pending:
            node_id, child = pending.pop(0)
            flattened[node_id] = child
            pending.extend((child.get("children") or {}).items())
        return flattened

    @staticmethod
    def _debug_node_status(child):
        state = child.get("state")
        schedule_type = child.get("schedule_type")
        if state == "RUNNING" and schedule_type:
            return "waiting", str(schedule_type).lower()
        return NODE_STATE_MAP.get(state), ""

    @staticmethod
    def _task_error_detail(task_id, data, runtime_to_template, runtime_errors, children):
        ex_data = data.get("ex_data") or {}
        if not isinstance(ex_data, dict):
            ex_data = {"": ex_data}
        failures = []
        for runtime_id, message in ex_data.items():
            failures.append(
                {
                    "node_id": runtime_id or None,
                    "template_node_id": runtime_to_template.get(runtime_id),
                    "message": message or "task failed",
                }
            )
        if not failures:
            for runtime_id, message in runtime_errors.items():
                failures.append(
                    {
                        "node_id": runtime_id,
                        "template_node_id": runtime_to_template.get(runtime_id),
                        "message": message or "task failed",
                    }
                )
        if not failures:
            for runtime_id, child in children.items():
                if child.get("state") == "FAILED":
                    failures.append(
                        {
                            "node_id": runtime_id,
                            "template_node_id": runtime_to_template.get(runtime_id),
                            "message": "task failed",
                        }
                    )
        message = failures[0]["message"] if failures else "task failed"
        return {"type": "runtime", "message": message, "task_id": task_id, "failures": failures}

    def sync_from_debug_task(self, ctx: DebugContext):
        """惰性回写真实调试任务；全局和单步共用同一条状态生命周期。"""
        # 单节点终止由 terminate() 在 forced_fail 返回后立即重置；期间不读取引擎 FAILED，
        # 避免轮询抢先把节点回写为失败并释放调试锁。
        if ctx.status == "terminating" and ctx.active_node_id:
            return
        # 早返回守卫：仅运行中且存在 active_task_id 才同步，避免空闲态构建真实客户端
        if ctx.status not in ("running", "terminating") or not ctx.active_task_id:
            if ctx.status == "idle" and ctx.last_run_status == "revoked":
                active_node_ids = DebugNodeState.objects.filter(
                    debug_context=ctx,
                    status__in=("running", "waiting", "paused", "revoked"),
                ).values_list("node_id", flat=True)
                self.reset_run_results(ctx, node_ids=list(active_node_ids))
            return
        client = self._task_client()
        task_id = ctx.active_task_id
        states = client.get_task_states(task_id, data={"with_ex_data": True, "include_schedule": True})
        if not states.get("result"):
            return
        data = states["data"]
        children = self._flatten_state_children(data.get("children", {}))
        # id_map 失败时直接返回：避免空回写后误判结束而释放锁，导致该次结束的结果永久丢失
        id_map_resp = client.get_node_id_map(ctx.active_task_id)
        if not id_map_resp.get("result"):
            return
        id_map = id_map_resp.get("data", {})
        acts_outputs = self._acts_outputs()
        runtime_to_template = {runtime_id: tpl_node_id for tpl_node_id, runtime_id in id_map.items()}
        runtime_errors = {}
        observed_statuses = []

        for tpl_node_id, runtime_id in id_map.items():
            ns = DebugNodeState.objects.filter(debug_context=ctx, node_id=tpl_node_id).first()
            if ns is None:
                continue
            child = children.get(runtime_id)
            if not child:
                continue
            node_status, waiting_reason = self._debug_node_status(child)
            if node_status:
                ns.status = node_status
            ns.waiting_reason = waiting_reason
            observed_statuses.append(ns.status)
            ns.duration_ms = int((child.get("elapsed_time") or 0) * 1000)
            if ns.status in ("finished", "failed"):
                detail = client.get_task_node_detail(task_id, runtime_id, data={"include_data": True})
                ddata = detail.get("data", {}) if detail.get("result") else {}
                version = ddata.get("version") or ddata.get("history_id") or "v1"
                ns.log_ref = {"instance_id": task_id, "node_id": runtime_id, "version": version}
                outputs = {o["key"]: o["value"] for o in ddata.get("outputs", []) if isinstance(o, dict) and "key" in o}
                if ns.status == "finished":
                    if self._is_debuggable_gateway(tpl_node_id):
                        try:
                            ns.outputs = evaluate_gateway(self.pipeline_tree, tpl_node_id, ctx.global_vars or {})
                        except GatewayEvaluationError as error:
                            logger.warning(
                                "[debug] sync gateway selected flows failed, template_id=%s, node_id=%s, error=%s",
                                self.template_id,
                                tpl_node_id,
                                error,
                            )
                            ns.outputs = {
                                "selected_flow_ids": [],
                                "condition_results": error.condition_results,
                            }
                    else:
                        ns.outputs = outputs
                    ns.error_detail = {}
                    for out_key, var_key in acts_outputs.get(tpl_node_id, {}).items():
                        if out_key in outputs:
                            ctx.global_vars[var_key] = outputs[out_key]
                else:
                    message = ddata.get("ex_data") or "step failed"
                    runtime_errors[runtime_id] = message
                    if self._is_debuggable_gateway(tpl_node_id):
                        try:
                            gateway_result = evaluate_gateway(self.pipeline_tree, tpl_node_id, ctx.global_vars or {})
                            ns.outputs = gateway_result
                        except GatewayEvaluationError as error:
                            ns.outputs = {
                                "selected_flow_ids": [],
                                "condition_results": error.condition_results,
                            }
                    else:
                        ns.outputs = {}
                    ns.error_detail = {"type": "runtime", "message": message}
            ns.save()

        engine_state = data.get("state")
        active_child_statuses = []
        for child in children.values():
            child_status, _ = self._debug_node_status(child)
            if child_status in ("running", "waiting", "paused"):
                active_child_statuses.append(child_status)
        # 任务状态接口会在任一子节点失败时把仍在运行的根任务投影为 FAILED；此时任务尚未真正静止。
        failed_with_active_children = engine_state == "FAILED" and bool(active_child_statuses)
        if engine_state == "REVOKED":
            active_node_ids = DebugNodeState.objects.filter(
                debug_context=ctx,
                status__in=("running", "waiting", "paused", "revoked"),
            ).values_list("node_id", flat=True)
            self.reset_run_results(ctx, node_ids=list(active_node_ids))
        if engine_state == "FAILED":
            state_errors = data.get("ex_data") if isinstance(data.get("ex_data"), dict) else {}
            for runtime_id, child in children.items():
                if child.get("state") != "FAILED" or runtime_errors.get(runtime_id) or state_errors.get(runtime_id):
                    continue
                detail = client.get_task_node_detail(task_id, runtime_id, data={"include_data": True})
                ddata = detail.get("data", {}) if detail.get("result") else {}
                if ddata.get("ex_data"):
                    runtime_errors[runtime_id] = ddata["ex_data"]
        ctx.last_task_id = task_id
        ctx.last_run_type = ctx.active_run_type or ctx.last_run_type or "global"
        if failed_with_active_children:
            if "paused" in active_child_statuses:
                ctx.last_run_status = "paused"
            elif "waiting" in active_child_statuses:
                ctx.last_run_status = "waiting"
            else:
                ctx.last_run_status = "running"
        elif engine_state in ENGINE_RUN_STATE_MAP:
            ctx.last_run_status = ENGINE_RUN_STATE_MAP[engine_state]
        elif engine_state in ("NODE_SUSPENDED", "SUSPENDED") or "paused" in observed_statuses:
            ctx.last_run_status = "paused"
        elif "waiting" in observed_statuses:
            ctx.last_run_status = "waiting"
        else:
            ctx.last_run_status = "running"
        if ctx.last_run_status == "failed":
            ctx.last_error_detail = self._task_error_detail(
                task_id, data, runtime_to_template, runtime_errors, children
            )
        elif ctx.last_run_status in ("finished", "revoked"):
            ctx.last_error_detail = {}
        ctx.save(
            update_fields=[
                "global_vars",
                "last_task_id",
                "last_run_type",
                "last_run_status",
                "last_error_detail",
            ]
        )
        if engine_state in ENGINE_FINISHED_STATES and not failed_with_active_children:
            self._release_lock(ctx, status="idle")

    # ---- 重置 / 终止 / 历史 ----
    def reset(self, node_ids=None) -> list:
        """重置运行结果（保留 mock 配置）；运行中/终止中禁止重置。"""
        ctx = self.sync_node_states()
        if ctx.status in ("running", "terminating") and not self._reclaim_stale_lock(ctx):
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
        active_task_id = ctx.active_task_id
        previous_active_node_id = ctx.active_node_id
        ctx.status = "terminating"
        ctx.active_node_id = node_id or ""
        ctx.save(update_fields=["status", "active_node_id"])
        client = self._task_client()
        if node_id:
            id_map_resp = client.get_node_id_map(active_task_id)
            if not id_map_resp.get("result"):
                ctx.status = "running"
                ctx.active_node_id = previous_active_node_id
                ctx.save(update_fields=["status", "active_node_id"])
                raise DebugStateError("获取节点 id 映射失败")
            runtime_id = id_map_resp.get("data", {}).get(node_id, node_id)
            op_result = client.node_operate(
                active_task_id,
                runtime_id,
                "forced_fail",
                {"operator": operator, "suppress_failure_side_effects": True},
            )
        else:
            op_result = client.operate_task(active_task_id, "revoke", {"operator": operator})
        if not op_result.get("result"):
            ctx.status = "running"
            ctx.active_node_id = previous_active_node_id
            ctx.save(update_fields=["status", "active_node_id"])
            raise DebugStateError(op_result.get("message", "终止调试失败"))

        if node_id:
            reset_node_ids = self.reset_run_results(ctx, node_ids=[node_id])
            ctx.last_task_id = active_task_id
            ctx.last_run_type = ctx.active_run_type or ctx.last_run_type or "step"
            ctx.last_run_status = "not_run"
            ctx.last_error_detail = {}
            ctx.save(update_fields=["last_task_id", "last_run_type", "last_run_status", "last_error_detail"])
            self._release_lock(ctx, status="idle")
            return {"status": "idle", "reset_node_ids": reset_node_ids}

        # 全局终止由 sync_from_debug_task 在任务到达 REVOKED 时回写结果并释放锁。
        return {"status": "terminating"}

    def history(self) -> dict:
        """基于保留的 DEBUG 任务实例列出历次运行。"""
        client = self._task_client()
        result = client.task_list(
            data={"template_id": self.template_id, "space_id": self.space_id, "create_method": "DEBUG"}
        )
        items = (result.get("data") or {}).get("results", [])
        task_ids = [item["id"] for item in items if item.get("id") is not None]
        engine_states = {}
        if task_ids:
            states_result = client.get_tasks_states(data={"task_ids": task_ids, "space_id": self.space_id})
            if states_result.get("result"):
                engine_states = states_result.get("data") or {}
        status_map = {
            "CREATED": "created",
            "READY": "created",
            "RUNNING": "running",
            "SUSPENDED": "paused",
            "NODE_SUSPENDED": "paused",
            "FINISHED": "finished",
            "FAILED": "failed",
            "REVOKED": "revoked",
            "EXPIRED": "expired",
        }
        runs = []
        for item in items:
            task_id = item.get("id")
            engine_state = (engine_states.get(task_id) or engine_states.get(str(task_id)) or {}).get("state")
            run_status = status_map.get(engine_state)
            if not run_status:
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
                    "task_id": task_id,
                    "operator": item.get("creator") or item.get("executor"),
                    "started_at": item.get("start_time") or item.get("create_time"),
                    "status": run_status,
                }
            )
        return {"runs": runs}

    # ---- 变更影响分析（只读） ----
    def reset_impact(self) -> dict:
        """对比上次调试指纹与当前 draft 指纹，沿控制流∪数据流闭包推断受影响节点集。

        仅做只读告知（不改库；不创建 DebugContext）：
        - 无历史调试基线（从未运行过 / 无 DebugContext）→ 直接返回空，无需重置；
        - 节点配置变更 / 新增节点 → 作为种子；
        - 删除节点或连线/网关/常量整体变化 → 保守地把当前全部节点纳入种子；
        - 对种子集合做下游可达闭包，闭包内其余节点标注「受上游变更影响」。
        :return: {"reset_node_ids": [...], "reasons": {node_id: reason}}
        """
        ctx = DebugContext.objects.filter(template_id=self.template_id).first()
        old_fp = (ctx.tree_fingerprint if ctx else None) or {}
        if not old_fp:
            return {"reset_node_ids": [], "reasons": {}}
        new_fp = compute_tree_fingerprint(self.pipeline_tree)
        old_nodes = old_fp.get("nodes", {})
        new_nodes = new_fp.get("nodes", {})

        seeds, reasons = set(), {}
        # 配置变更 / 新增节点
        for nid, h in new_nodes.items():
            if nid in old_nodes and old_nodes[nid] != h:
                seeds.add(nid)
                reasons[nid] = "节点 {} 配置变更".format(nid)
            elif nid not in old_nodes:
                seeds.add(nid)
                reasons[nid] = "新增节点 {}".format(nid)
        # 删除节点：消费其输出的节点无法从新图获得，保守地把全部当前节点纳入闭包起点
        removed = set(old_nodes.keys()) - set(new_nodes.keys())
        # 连线/网关/常量整体指纹变化：保守处理（仅当对应指纹变化时）
        topo_changed = any(old_fp.get(k) != new_fp.get(k) for k in ("flows", "gateways", "constants"))

        graph = build_dependency_graph(self.pipeline_tree)
        if removed:
            for nid in graph["control"].keys():
                seeds.add(nid)
                reasons.setdefault(nid, "上游存在删除/连线变更，保守重置")
        if topo_changed and not seeds:
            for nid in graph["control"].keys():
                seeds.add(nid)
                reasons.setdefault(nid, "拓扑/连线/常量变更")

        impacted = closure(seeds, graph) if seeds else set()
        for nid in impacted:
            reasons.setdefault(nid, "受上游变更影响")
        return {"reset_node_ids": sorted(impacted), "reasons": {k: reasons[k] for k in sorted(impacted)}}

    # ---- 单步调试 / 节点 mock 配置 / 上下文变量 ----
    def _apply_outputs_to_global_vars(self, ctx, node_id, outputs: dict):
        """成功输出按 source_act/source_key 合并到 global_vars 并持久化（不触碰节点状态）。"""
        acts_outputs = self._acts_outputs().get(node_id, {})
        for out_key, var_key in acts_outputs.items():
            if out_key in (outputs or {}):
                ctx.global_vars[var_key] = outputs[out_key]
        ctx.save(update_fields=["global_vars"])

    def set_context_var(self, key, value) -> dict:
        """编辑调试上下文变量；运行中禁止编辑。"""
        ctx = self.get_or_create_context()
        if ctx.status != "idle" and not self._reclaim_stale_lock(ctx):
            raise DebugConflictError("调试运行中，禁止编辑变量")
        ctx.global_vars[key] = value
        ctx.save(update_fields=["global_vars"])
        return {"global_vars": ctx.global_vars}

    def node_mock(self, node_id, enable=True, mock_result="success", mock_outputs=None, mock_error="") -> dict:
        """节点 mock 纯配置：只改 execution_mode 与 mock_* 预设，不改运行状态（评审 #3）。"""
        ctx = self.sync_node_states()
        if ctx.status != "idle" and not self._reclaim_stale_lock(ctx):
            raise DebugConflictError("调试运行中，禁止配置 mock")
        try:
            ns = DebugNodeState.objects.get(debug_context=ctx, node_id=node_id)
        except DebugNodeState.DoesNotExist:
            raise DebugStateError({"detail": "节点不存在", "node_id": node_id})
        if self._is_gateway(node_id):
            message = "条件网关不支持 Mock" if self._is_debuggable_gateway(node_id) else "网关节点不支持 Mock"
            raise DebugStateError(message)
        if enable:
            ns.execution_mode = "mock"
            ns.mock_result = mock_result
            if mock_result == "success":
                ns.mock_outputs = mock_outputs or {}
                ns.mock_error = ""
                ns.save()
                # 配置成功输出即回写全局变量，便于下游立即单步消费；不改 status/outputs
                self._apply_outputs_to_global_vars(ctx, node_id, ns.mock_outputs)
            else:
                ns.mock_error = mock_error or "mock failed"
                ns.save()
        else:
            # M-3：关闭 mock 仅切回 real 并保留 mock_* 预设；此前回写的 global_vars 不回滚（设计如此，
            # 便于用户来回切换而不丢已消费的上游产出）。
            ns.execution_mode = "real"
            ns.save(update_fields=["execution_mode"])
        ctx.refresh_from_db()
        return {"node_id": node_id, "execution_mode": ns.execution_mode, "updated_global_vars": ctx.global_vars}

    def step_run(
        self,
        node_id,
        operator,
        mode=None,
        input_overrides=None,
        mock_result="success",
        mock_outputs=None,
        mock_error="",
    ) -> dict:
        """单步执行单个节点：mock 模式直出，real 模式经引擎跑微型任务。"""
        ctx = self.sync_node_states()
        if ctx.status != "idle" and not self._reclaim_stale_lock(ctx):
            raise DebugConflictError("模板正在被 {} 调试".format(ctx.locked_by or "其他用户"))
        try:
            ns = DebugNodeState.objects.get(debug_context=ctx, node_id=node_id)
        except DebugNodeState.DoesNotExist:
            raise DebugStateError({"detail": "节点不存在", "node_id": node_id})
        effective_mode = mode or ns.execution_mode

        if self._is_gateway(node_id) and not self._is_debuggable_gateway(node_id):
            raise DebugStateError("网关节点不支持单步调试")
        if self._is_debuggable_gateway(node_id):
            if effective_mode == "mock":
                raise DebugStateError("条件网关不支持 Mock")
            return self._step_run_gateway(ctx, ns, operator, input_overrides)
        if effective_mode == "mock":
            return self._step_run_mock(ctx, ns, mock_result, mock_outputs, mock_error)
        return self._step_run_real(ctx, ns, operator, input_overrides)

    def _step_run_gateway(self, ctx, ns, operator, input_overrides):
        values = dict(ctx.global_vars or {}) if input_overrides is None else dict(input_overrides)
        missing = gateway_missing_vars(self.pipeline_tree, ns.node_id, values)
        if missing:
            raise DebugStateError({"detail": "依赖未满足", "missing_vars": missing})

        self._acquire_lock(ctx, operator)
        started_at = time.monotonic()
        try:
            ns.execution_mode = "real"
            ns.status = "running"
            ns.waiting_reason = ""
            ns.outputs = {}
            ns.error_detail = {}
            ns.log_ref = {}
            ns.last_run_at = timezone.now()
            ns.save()
            try:
                result = evaluate_gateway(self.pipeline_tree, ns.node_id, values)
                ns.status = "finished"
                ns.outputs = result
                ns.error_detail = {}
                ctx.last_run_status = "finished"
                ctx.last_error_detail = {}
                response = {
                    "node_id": ns.node_id,
                    "status": "finished",
                    "selected_flow_ids": result["selected_flow_ids"],
                    "condition_results": result["condition_results"],
                    "error_detail": None,
                }
            except GatewayEvaluationError as error:
                detail = {"type": "gateway", "message": str(error)}
                ns.status = "failed"
                ns.outputs = {
                    "selected_flow_ids": [],
                    "condition_results": error.condition_results,
                }
                ns.error_detail = detail
                ctx.last_run_status = "failed"
                ctx.last_error_detail = detail
                response = {
                    "node_id": ns.node_id,
                    "status": "failed",
                    "selected_flow_ids": [],
                    "condition_results": error.condition_results,
                    "error_detail": detail,
                }

            ns.duration_ms = int((time.monotonic() - started_at) * 1000)
            ns.save()
            ctx.last_run_type = "step"
            ctx.save(update_fields=["last_run_type", "last_run_status", "last_error_detail"])
            return response
        finally:
            self._release_lock(ctx, status="idle")

    def _step_run_mock(self, ctx, ns, mock_result, mock_outputs, mock_error):
        ns.log_ref = {}
        ns.waiting_reason = ""
        ns.duration_ms = 0  # mock 不经引擎，耗时记 0
        ns.last_run_at = timezone.now()
        if mock_result == "fail":
            ns.status = "failed"
            ns.outputs = {}
            ns.error_detail = {"type": "mock", "message": mock_error or "mock failed"}
            ns.save()
            return {
                "node_id": ns.node_id,
                "status": "failed",
                "outputs": None,
                "error_detail": ns.error_detail,
                "updated_global_vars": ctx.global_vars,
                "log_ref": None,
            }
        outputs = mock_outputs if mock_outputs else (ns.mock_outputs or {})
        ns.status = "finished"
        ns.outputs = outputs
        ns.error_detail = {}
        ns.save()
        self._apply_outputs_to_global_vars(ctx, ns.node_id, outputs)
        ctx.refresh_from_db()
        return {
            "node_id": ns.node_id,
            "status": "finished",
            "outputs": outputs,
            "error_detail": None,
            "updated_global_vars": ctx.global_vars,
            "log_ref": None,
        }

    def _step_run_real(self, ctx, ns, operator, input_overrides):
        from bkflow.template.debug.pipeline_builder import (
            build_single_node_pipeline_tree,
        )

        # 依赖门控放在抢锁前：被阻断的调用不应改动状态或触达引擎（I-1）
        if input_overrides is None:
            can, missing = self.compute_can_step(ctx, ns.node_id)
            if not can:
                raise DebugStateError({"detail": "依赖未满足", "missing_vars": missing})
            var_values = dict(ctx.global_vars or {})
        else:
            var_values = dict(input_overrides)

        # real 单步与全局调试共用 active task 生命周期，结果由 context 轮询同步。
        self._acquire_lock(ctx, operator)
        client = self._task_client()
        task_id = None
        try:
            mini_tree = build_single_node_pipeline_tree(self.pipeline_tree, ns.node_id, var_values)
            template = Template.objects.filter(id=self.template_id).first()
            create_result = client.create_task(
                {
                    "template_id": self.template_id,
                    "space_id": self.space_id,
                    "scope_type": template.scope_type if template else None,
                    "scope_value": template.scope_value if template else None,
                    "pipeline_tree": mini_tree,
                    "mock_data": {"nodes": [], "outputs": {}},
                    "create_method": "DEBUG",
                    "trigger_method": "manual",
                }
            )
            if not create_result.get("result"):
                raise DebugStateError(create_result.get("message", "create step task failed"))
            task_id = create_result["data"]["id"]

            id_map_resp = client.get_node_id_map(task_id)
            runtime_id = (id_map_resp.get("data") or {}).get(ns.node_id) if id_map_resp.get("result") else None
            if not runtime_id:
                raise DebugStateError("node id map missing")

            ns.status = "running"
            ns.waiting_reason = ""
            ns.duration_ms = None
            ns.outputs = {}
            ns.error_detail = {}
            ns.log_ref = {"instance_id": task_id, "node_id": runtime_id, "version": "v1"}
            ns.last_run_at = timezone.now()
            ns.save(
                update_fields=[
                    "status",
                    "waiting_reason",
                    "duration_ms",
                    "outputs",
                    "error_detail",
                    "log_ref",
                    "last_run_at",
                ]
            )

            start_result = client.operate_task(task_id, "start", {"operator": operator})
            if not start_result.get("result"):  # I-2：启动失败必须收敛，否则会空轮询到超时
                raise DebugStateError(start_result.get("message", "start step task failed"))

            ctx.active_task_id = task_id
            ctx.active_run_type = "step"
            ctx.active_node_id = ns.node_id
            ctx.last_task_id = task_id
            ctx.last_run_type = "step"
            ctx.last_run_status = "running"
            ctx.last_error_detail = {}
            ctx.save(
                update_fields=[
                    "active_task_id",
                    "active_run_type",
                    "active_node_id",
                    "last_task_id",
                    "last_run_type",
                    "last_run_status",
                    "last_error_detail",
                ]
            )
            return {
                "node_id": ns.node_id,
                "task_id": task_id,
                "status": "running",
                "log_ref": ns.log_ref,
            }
        except Exception as exc:
            if not isinstance(exc, (DebugStateError, DebugConflictError)):
                logger.exception(
                    "[debug step_run] unexpected error, template_id=%s, task_id=%s",
                    self.template_id,
                    task_id,
                )
            # 未建立可追踪上下文的任务必须清理，避免遗留孤儿任务。
            if task_id is not None:
                try:
                    client.delete_task(task_id)
                except Exception:
                    logger.warning(
                        "[debug step_run] cleanup orphan step task failed, template_id=%s, task_id=%s",
                        self.template_id,
                        task_id,
                        exc_info=True,
                    )
            if ns.status == "running":
                ns.status = "failed"
                ns.waiting_reason = ""
                ns.save(update_fields=["status", "waiting_reason"])
            self._release_lock(ctx, status="idle")
            raise
