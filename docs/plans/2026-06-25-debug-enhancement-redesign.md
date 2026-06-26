# BKFlow 流程调试能力增强 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 `DebugContext` 为中心，为 BKFlow 实现全局调试、单步调试、统一调试上下文、变更影响重置、mock 单步与失败注入、调试态可观测、调试历史与输入复用（req1–req14）。

**Architecture:** 双模块落地——配置/编排态（`DebugContext`/`DebugNodeState`/`DebugService`）放 Interface 的 `bkflow.template` app；执行态复用 Engine 的真实 `TaskInstance(create_method="DEBUG")`，跨模块经 `TaskComponentClient` 调用。全局调试 = 全量 DEBUG 任务；单步 real = 仅含该节点的微型 DEBUG 任务；单步 mock 不经引擎，由 `DebugService` 直接产出。节点级重数据复用现有任务详情接口（`get_task_states`/`get_node_detail`/`get_node_log`），由 `log_ref` 定位。

**Tech Stack:** Django + DRF；`bamboo_engine_api` + `BambooDjangoRuntime`；pytest。调试快照类 JSON 字段统一用普通 `models.JSONField`（见决策 #1）。

**Spec:** `docs/specs/2026-06-24-debug-enhancement-redesign-design.md`

---

## 已确认的关键落地决策

1. **JSON 字段（不加密）**：spec 写的 `EncryptedJsonField` 在本仓库不存在。曾计划用 `SecretSingleJsonField`，但经代码评审确认它**只支持单层 `{str: 标量}`、遇到嵌套 dict/list 会抛 `ValueError`**（见 `bkflow/utils/models.py:get_prep_value`），而 `inputs/outputs/mock_outputs/global_vars/last_inputs` 等调试快照天然是嵌套结构。决策：这些调试快照**不算敏感数据，统一用普通 `models.JSONField`，不做字段级加密**。若后续确有敏感诉求，再单独引入"整体 `encrypt(json.dumps(...))`"的字段，不要复用 `SecretSingleJsonField`。
2. **模型归属**：`DebugContext`/`DebugNodeState` 放 **Interface 的 `bkflow.template`**（按模板维度、可直接读 draft `pipeline_tree` 做 `input_schema`/`reset_impact`）。执行靠 Engine 的 DEBUG 任务，重数据复用任务详情接口。
3. **单步 real**：建一个"仅含该节点"的微型 DEBUG `TaskInstance`（手工构造 `start→node→end` 最小 web pipeline_tree，引用变量注入为常量），复用现有任务基建跑通，`log_ref.instance_id` 指向它。
4. **节点 id 映射**：`create_instance` 调 `inject_template_node_id` 把原模板 id 写入 `activity["template_node_id"]`，再 `replace_all_id` 重映射 `id`。回写时用 Engine 新增的 node-id-map 端点拿 `{template_node_id: runtime_id}`。
5. **mock 失败注入向后兼容**：`TaskMockData.data` 增加可选 `fail_nodes`/`errors`；老 MOCK 任务无这两个键时行为与现状完全一致。

## 模块与文件结构

**Interface 侧（`bkflow.template`）— 新建/修改**

- Modify: `bkflow/template/models.py` — 追加 `DebugContext`、`DebugNodeState`（JSON 字段用普通 `models.JSONField`，无需新增加密字段 import）
- Create: `bkflow/template/debug/__init__.py`
- Create: `bkflow/template/debug/dependency.py` — `compute_node_config_hash` / `compute_tree_fingerprint` / `build_dependency_graph` / `closure`
- Create: `bkflow/template/debug/pipeline_builder.py` — `build_single_node_pipeline_tree`
- Create: `bkflow/template/debug/service.py` — `DebugService`（编排：抢锁/状态机/物化 mock/回写/单步/重置/终止/历史/input_schema）
- Create: `bkflow/template/debug/serializers.py` — Debug 各接口入参/出参序列化器
- Create: `bkflow/template/views/debug.py` — `DebugViewSet`
- Modify: `bkflow/template/urls.py` — 注册 `DebugViewSet`
- Migrations: `bkflow/template/migrations/00XX_*`（由 `makemigrations template` 生成）

**Engine 侧（`bkflow.task` / `bkflow.pipeline_plugins`）— 修改**

- Modify: `bkflow/task/models.py` — `CREATE_METHODS` 增加 `DEBUG`；`create_instance` 对 `DEBUG` 也物化 `TaskMockData`，并映射 `fail_nodes`/`errors`
- Modify: `bkflow/utils/context.py` — `TaskContext.is_mock = create_method in ("MOCK", "DEBUG")`
- Modify: `bkflow/task/serializers.py` — `mock_data` 序列化器增加 `fail_nodes`/`errors`
- Modify: `bkflow/task/views.py` — 任务列表默认隐藏 `DEBUG`；新增 `get_node_id_map` action
- Modify: `bkflow/pipeline_plugins/components/collections/base.py` — `mock_execute`/`mock_schedule` 失败注入
- Modify: `bkflow/contrib/api/collections/task.py` — `TaskComponentClient.get_node_id_map`
- Migrations: `bkflow/task/migrations/00XX_*`（由 `makemigrations task` 生成）

**通信**：`DebugService`（Interface）经 `TaskComponentClient` 调 Engine 的 `create_task`/`operate`/`get_task_states`/`get_task_node_detail`/`get_node_id_map`/`revoke`/`forced_fail`。

**测试落点**

- Interface：`tests/interface/template/debug/test_*.py`
- Engine：`tests/engine/task/test_*.py`、`tests/engine/task/test_bkflow_base_plugin_service.py`

**约定**

- 权限：Debug 视图复用模板维度鉴权 `[AdminPermission | SpaceSuperuserPermission | TemplateRelatedResourcePermission]`（同 `TemplateMockSchemeViewSet`）。
- 响应：Interface 视图 `Response(data)` / `Response(exception=True, data={"detail": ...})`；状态码 200/201；冲突 409；参数错误 400。
- `${key}` 表示全局变量键（含 `${}`）。
- 测试运行均假设项目 pytest/Django 配置已就绪，命令形如 `pytest <path>::<test> -v`。

---

# Phase 1 — 调试上下文模型 + 统一读 + 输入元数据（Interface）

产出：可创建/读取调试上下文，按 draft 树初始化各节点调试态，返回输入常量元数据。独立可测、可上线（不影响现有功能）。

### Task 1.1: DebugContext / DebugNodeState 模型与迁移

**Files:**
- Modify: `bkflow/template/models.py`（追加模型；确认顶部已有 `from bkflow.utils.models import CommonModel`；所有 JSON 字段用普通 `models.JSONField`，不引入加密字段）
- Test: `tests/interface/template/debug/test_models.py`

- [ ] **Step 1: 写失败测试**

Create `tests/interface/template/debug/__init__.py`（空文件）与 `tests/interface/template/debug/test_models.py`：

```python
# -*- coding: utf-8 -*-
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/interface/template/debug/test_models.py -v`
Expected: FAIL（`ImportError: cannot import name 'DebugContext'`）

- [ ] **Step 3: 追加模型实现**

在 `bkflow/template/models.py` 末尾追加（JSON 字段一律用普通 `models.JSONField`，无需加密字段 import）：

```python
class DebugContext(CommonModel):
    """每模板唯一的调试上下文，跨用户共享。

    生命周期约定：按模板维度 get_or_create，**不软删除**；reset 只清空 global_vars/节点态、
    不删除该行（故 template_id 的 unique 与 CommonModel 软删除不冲突）。
    """

    STATUS_CHOICES = (("idle", "idle"), ("running", "running"), ("terminating", "terminating"))

    template_id = models.BigIntegerField(_("模板ID"), unique=True)
    space_id = models.IntegerField(_("空间ID"), db_index=True)
    global_vars = models.JSONField(_("调试全局变量"), default=dict, blank=True)
    tree_fingerprint = models.JSONField(_("树指纹"), default=dict, blank=True)
    status = models.CharField(_("调试状态"), max_length=16, choices=STATUS_CHOICES, default="idle")
    active_task_id = models.BigIntegerField(_("当前DEBUG任务ID"), null=True, blank=True)
    last_inputs = models.JSONField(_("最近一次输入"), default=dict, blank=True)
    locked_by = models.CharField(_("持锁用户"), max_length=32, blank=True, default="")
    locked_at = models.DateTimeField(_("持锁时间"), null=True, blank=True)

    class Meta:
        verbose_name = _("调试上下文 DebugContext")
        verbose_name_plural = _("调试上下文 DebugContext")


class DebugNodeState(models.Model):
    """每模板每节点一份的调试态"""

    EXECUTION_MODE_CHOICES = (("real", "real"), ("mock", "mock"))
    MOCK_RESULT_CHOICES = (("success", "success"), ("fail", "fail"))
    STATUS_CHOICES = (
        ("not_run", "not_run"),
        ("running", "running"),
        ("finished", "finished"),
        ("failed", "failed"),
    )

    debug_context = models.ForeignKey(
        DebugContext, related_name="node_states", on_delete=models.CASCADE, verbose_name=_("所属上下文")
    )
    node_id = models.CharField(_("节点ID"), max_length=33)
    node_type = models.CharField(_("节点类型"), max_length=32, default="ServiceActivity")
    execution_mode = models.CharField(_("执行模式"), max_length=8, choices=EXECUTION_MODE_CHOICES, default="real")
    mock_result = models.CharField(_("Mock结果"), max_length=8, choices=MOCK_RESULT_CHOICES, default="success")
    mock_outputs = models.JSONField(_("Mock预设输出"), default=dict, blank=True)
    mock_error = models.CharField(_("Mock错误信息"), max_length=1024, blank=True, default="")
    status = models.CharField(_("运行状态"), max_length=16, choices=STATUS_CHOICES, default="not_run")
    inputs = models.JSONField(_("最近输入快照"), default=dict, blank=True)
    outputs = models.JSONField(_("最近输出快照"), default=dict, blank=True)
    duration_ms = models.IntegerField(_("耗时(ms)"), null=True, blank=True)
    error_detail = models.JSONField(_("错误详情"), default=dict, blank=True)
    log_ref = models.JSONField(_("引擎引用"), default=dict, blank=True)
    config_hash = models.CharField(_("配置指纹"), max_length=64, blank=True, default="")
    last_run_at = models.DateTimeField(_("最近运行时间"), null=True, blank=True)

    class Meta:
        verbose_name = _("调试节点态 DebugNodeState")
        verbose_name_plural = _("调试节点态 DebugNodeState")
        unique_together = (("debug_context", "node_id"),)
```

- [ ] **Step 4: 生成迁移**

Run: `python manage.py makemigrations template`
Expected: 生成 `bkflow/template/migrations/00XX_debugcontext_debugnodestate.py`（不要手改逻辑，仅按 Black/isort 格式化）

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/interface/template/debug/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bkflow/template/models.py bkflow/template/migrations/ tests/interface/template/debug/
git commit -m "feat(debug): 新增 DebugContext/DebugNodeState 调试上下文模型 --story=135505027"
```

### Task 1.2: 依赖图 / 指纹工具

**Files:**
- Create: `bkflow/template/debug/__init__.py`（空）
- Create: `bkflow/template/debug/dependency.py`
- Test: `tests/interface/template/debug/test_dependency.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.template.debug.dependency import (
    build_dependency_graph,
    closure,
    compute_node_config_hash,
    compute_tree_fingerprint,
)

# 最小 web 树：start -> A -> B -> end；B 引用 A 产出的 ${g1}
PIPELINE = {
    "start_event": {"id": "s", "type": "EmptyStartEvent", "incoming": None, "outgoing": "f0"},
    "end_event": {"id": "e", "type": "EmptyEndEvent", "incoming": "f2", "outgoing": None},
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "incoming": "f0", "outgoing": "f1",
              "component": {"code": "test", "data": {"x": {"hook": False, "value": "1"}}}},
        "B": {"id": "B", "type": "ServiceActivity", "incoming": "f1", "outgoing": "f2",
              "component": {"code": "test", "data": {"y": {"hook": True, "value": "${g1}"}}}},
    },
    "flows": {
        "f0": {"id": "f0", "source": "s", "target": "A"},
        "f1": {"id": "f1", "source": "A", "target": "B"},
        "f2": {"id": "f2", "source": "B", "target": "e"},
    },
    "gateways": {},
    "constants": {
        "${g1}": {"key": "${g1}", "name": "g1", "show_type": "hide", "value": "",
                  "source_type": "component_outputs", "custom_type": "", "source_tag": "",
                  "source_info": {"A": ["k1"]}},
    },
}


class TestDependency:
    def test_control_and_data_edges(self):
        graph = build_dependency_graph(PIPELINE)
        # 控制流：A -> B
        assert "B" in graph["control"]["A"]
        # 数据流：A 产出 ${g1}，B 消费 -> A -> B
        assert "B" in graph["data"]["A"]

    def test_closure_includes_downstream(self):
        graph = build_dependency_graph(PIPELINE)
        assert closure({"A"}, graph) == {"A", "B"}
        assert closure({"B"}, graph) == {"B"}

    def test_config_hash_stable_and_sensitive(self):
        h1 = compute_node_config_hash(PIPELINE["activities"]["A"])
        h2 = compute_node_config_hash(PIPELINE["activities"]["A"])
        assert h1 == h2
        changed = {**PIPELINE["activities"]["A"], "component": {"code": "test", "data": {"x": {"hook": False, "value": "2"}}}}
        assert compute_node_config_hash(changed) != h1

    def test_tree_fingerprint_has_nodes_and_topology(self):
        fp = compute_tree_fingerprint(PIPELINE)
        assert set(fp["nodes"].keys()) == {"A", "B"}
        assert "flows" in fp and "constants" in fp and "gateways" in fp
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_dependency.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `dependency.py`**

```python
# -*- coding: utf-8 -*-
import hashlib
import json
from typing import Dict, Set

from bkflow.pipeline_web.parser.format import classify_constants


def compute_node_config_hash(activity: dict) -> str:
    """节点配置指纹：仅取影响执行的字段（type/component），忽略坐标/备注"""
    payload = {
        "type": activity.get("type"),
        "component": activity.get("component", {}),
        "optional": activity.get("optional"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _hash_obj(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def compute_tree_fingerprint(pipeline_tree: dict) -> dict:
    """各节点 config_hash + 拓扑/连线/常量/网关指纹"""
    activities = pipeline_tree.get("activities", {})
    flows = {fid: {"source": f["source"], "target": f["target"]} for fid, f in pipeline_tree.get("flows", {}).items()}
    gateways = {
        gid: g.get("conditions", {}) for gid, g in pipeline_tree.get("gateways", {}).items()
    }
    constants = {
        key: {"source_type": c.get("source_type"), "source_info": c.get("source_info"), "value": c.get("value")}
        for key, c in pipeline_tree.get("constants", {}).items()
    }
    return {
        "nodes": {nid: compute_node_config_hash(act) for nid, act in activities.items()},
        "flows": _hash_obj(flows),
        "gateways": _hash_obj(gateways),
        "constants": _hash_obj(constants),
    }


def build_dependency_graph(pipeline_tree: dict) -> dict:
    """构建控制流图与数据流图（均为 producer_node -> set(consumer_node)）"""
    activities = pipeline_tree.get("activities", {})
    gateways = pipeline_tree.get("gateways", {})
    flows = pipeline_tree.get("flows", {})
    node_ids = set(activities.keys()) | set(gateways.keys())

    control: Dict[str, Set[str]] = {nid: set() for nid in node_ids}
    for flow in flows.values():
        src, tgt = flow.get("source"), flow.get("target")
        if src in control and tgt in node_ids:
            control[src].add(tgt)

    # 数据流：A 产出 ${var}（component_outputs.source_act），B 的 component.data 引用 ${var}
    classified = classify_constants(pipeline_tree.get("constants", {}), is_subprocess=False)
    var_producer = {}  # ${var} -> producer_node_id
    for var_key, info in classified["data_inputs"].items():
        if info.get("type") == "splice" and info.get("source_act"):
            var_producer[var_key] = info["source_act"]

    data: Dict[str, Set[str]] = {nid: set() for nid in node_ids}
    for nid, act in activities.items():
        component_data = act.get("component", {}).get("data", {})
        referenced = set()
        for field in component_data.values():
            value = field.get("value")
            if isinstance(value, str):
                for var_key, producer in var_producer.items():
                    if var_key in value:
                        referenced.add(producer)
        for producer in referenced:
            if producer in data and producer != nid:
                data[producer].add(nid)

    return {"control": control, "data": data}


def closure(seeds: Set[str], graph: dict) -> Set[str]:
    """沿控制流 ∪ 数据流并集做下游可达闭包（含种子自身）"""
    control, data = graph["control"], graph["data"]
    visited, stack = set(), list(seeds)
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for nxt in control.get(node, set()) | data.get(node, set()):
            if nxt not in visited:
                stack.append(nxt)
    return visited
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_dependency.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/template/debug/__init__.py bkflow/template/debug/dependency.py tests/interface/template/debug/test_dependency.py
git commit -m "feat(debug): 新增调试依赖图与树指纹工具 --story=135505027"
```

### Task 1.3: DebugService 基础（取上下文 / 同步节点态 / input_schema）

**Files:**
- Create: `bkflow/template/debug/service.py`
- Test: `tests/interface/template/debug/test_service_context.py`

> 说明：`DebugService` 用 `template_id` 构造，内部按需取 draft `pipeline_tree`。取 draft 快照逻辑复用 `bkflow/apigw/views/create_mock_task.py:54-60` 的模式（优先 `TemplateSnapshot(draft=True)`，否则 `template.pipeline_tree`）。

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, DebugNodeState

PIPELINE = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
        "B": {"id": "B", "type": "ServiceActivity", "component": {"code": "t", "data": {"y": {"hook": True, "value": "${biz}"}}}},
    },
    "flows": {}, "gateways": {},
    "constants": {
        "${biz}": {"key": "${biz}", "name": "业务", "show_type": "show", "value": "",
                   "source_type": "custom", "custom_type": "input", "source_tag": "input.input", "source_info": {}},
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
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_service_context.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `DebugService` 基础**

```python
# -*- coding: utf-8 -*-
import logging

from django.utils import timezone

from bkflow.template.debug.dependency import compute_node_config_hash, compute_tree_fingerprint
from bkflow.template.models import DebugContext, DebugNodeState, Template, TemplateSnapshot

logger = logging.getLogger(__name__)


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
            template = Template.objects.get(id=self.template_id)
            try:
                self._pipeline_tree = TemplateSnapshot.objects.get(
                    template_id=template.id, draft=True, is_deleted=False
                ).data
            except TemplateSnapshot.DoesNotExist:
                self._pipeline_tree = template.pipeline_tree
        return self._pipeline_tree

    def get_or_create_context(self) -> DebugContext:
        ctx, _ = DebugContext.objects.get_or_create(
            template_id=self.template_id, defaults={"space_id": self.space_id}
        )
        return ctx

    def sync_node_states(self) -> DebugContext:
        """按当前 pipeline_tree 增删 DebugNodeState；保留已存在节点的配置与运行态。"""
        ctx = self.get_or_create_context()
        activities = self.pipeline_tree.get("activities", {})
        existing = {ns.node_id: ns for ns in DebugNodeState.objects.filter(debug_context=ctx)}
        tree_node_ids = set(activities.keys())

        for node_id, act in activities.items():
            if node_id not in existing:
                DebugNodeState.objects.create(
                    debug_context=ctx, node_id=node_id, node_type=act.get("type", "ServiceActivity")
                )
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
                    "type": c.get("custom_type") or c.get("source_type") or "string",
                    "default": c.get("value", ""),
                    "required": True,
                }
            )
        return fields

    # ---- 内部工具 ----
    def _refresh_tree_fingerprint(self, ctx: DebugContext):
        ctx.tree_fingerprint = compute_tree_fingerprint(self.pipeline_tree)
        for ns in DebugNodeState.objects.filter(debug_context=ctx):
            act = self.pipeline_tree.get("activities", {}).get(ns.node_id)
            if act is not None:
                ns.config_hash = compute_node_config_hash(act)
                ns.save(update_fields=["config_hash"])
        ctx.save(update_fields=["tree_fingerprint"])
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_service_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/template/debug/service.py tests/interface/template/debug/test_service_context.py
git commit -m "feat(debug): 新增 DebugService 上下文同步与输入元数据解析 --story=135505027"
```

### Task 1.4: 序列化器 + `DebugViewSet`（context / input_schema）+ 路由

**Files:**
- Create: `bkflow/template/debug/serializers.py`
- Create: `bkflow/template/views/debug.py`
- Modify: `bkflow/template/urls.py`
- Test: `tests/interface/template/debug/test_views_context.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

from bkflow.template.models import DebugContext
from bkflow.template.views.debug import DebugViewSet

User = get_user_model()


@pytest.mark.django_db
class TestDebugContextViews:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser("admin", "a@a.com", "x")

    def test_get_context_creates_and_returns(self, mocker):
        mocker.patch(
            "bkflow.template.debug.service.DebugService.pipeline_tree",
            new_callable=mocker.PropertyMock,
            return_value={"activities": {}, "flows": {}, "gateways": {}, "constants": {}},
        )
        mocker.patch(
            "bkflow.template.debug.service.DebugService.space_id",
            new_callable=mocker.PropertyMock,
            return_value=10,
        )
        view = DebugViewSet.as_view({"get": "context"})
        request = self.factory.get("/debug/context/", {"template_id": 1})
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["status"] == "idle"
        assert DebugContext.objects.filter(template_id=1).exists()

    def test_input_schema_view(self, mocker):
        mocker.patch(
            "bkflow.template.debug.service.DebugService.pipeline_tree",
            new_callable=mocker.PropertyMock,
            return_value={"constants": {"${b}": {"name": "b", "show_type": "show", "value": "", "custom_type": "input"}}},
        )
        view = DebugViewSet.as_view({"get": "input_schema"})
        request = self.factory.get("/debug/input_schema/", {"template_id": 1})
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["fields"][0]["key"] == "${b}"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_views_context.py -v`
Expected: FAIL（`DebugViewSet` 不存在）

- [ ] **Step 3: 实现 serializers**

`bkflow/template/debug/serializers.py`：

```python
# -*- coding: utf-8 -*-
from rest_framework import serializers


class TemplateIdQuerySerializer(serializers.Serializer):
    template_id = serializers.IntegerField()


class GlobalRunSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    inputs = serializers.JSONField(default=dict)


class StepRunSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    node_id = serializers.CharField()
    mode = serializers.ChoiceField(choices=["real", "mock"], required=False)
    input_overrides = serializers.JSONField(required=False)
    mock_result = serializers.ChoiceField(choices=["success", "fail"], required=False, default="success")
    mock_outputs = serializers.JSONField(required=False, default=dict)
    mock_error = serializers.CharField(required=False, allow_blank=True, default="")


class NodeMockSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    node_id = serializers.CharField()
    enable = serializers.BooleanField(required=False, default=True)
    mock_result = serializers.ChoiceField(choices=["success", "fail"], required=False, default="success")
    mock_outputs = serializers.JSONField(required=False, default=dict)
    mock_error = serializers.CharField(required=False, allow_blank=True, default="")


class ContextVarSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    key = serializers.CharField()
    value = serializers.JSONField()


class ResetSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    node_ids = serializers.ListField(child=serializers.CharField(), required=False)


class TerminateSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    node_id = serializers.CharField(required=False)
```

- [ ] **Step 4: 实现 `DebugViewSet`（先只含 context / input_schema）**

`bkflow/template/views/debug.py`：

```python
# -*- coding: utf-8 -*-
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.template.debug.serializers import TemplateIdQuerySerializer
from bkflow.template.debug.service import DebugService
from bkflow.template.permissions import TemplateRelatedResourcePermission
from bkflow.utils.permissions import AdminPermission


class DebugViewSet(GenericViewSet):
    permission_classes = [AdminPermission | SpaceSuperuserPermission | TemplateRelatedResourcePermission]

    @action(methods=["GET"], detail=False)
    def context(self, request, *args, **kwargs):
        query = TemplateIdQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        svc = DebugService(template_id=query.validated_data["template_id"])
        return Response(svc.build_context_view())

    @action(methods=["GET"], detail=False)
    def input_schema(self, request, *args, **kwargs):
        query = TemplateIdQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        svc = DebugService(template_id=query.validated_data["template_id"])
        return Response({"fields": svc.input_schema()})
```

> 注：`TemplateRelatedResourcePermission` 与 `TemplatePermission` 来自 `bkflow/template/permissions.py`（`TemplateMockSchemeViewSet` 在用）。实现前先 `Read` 确认导入路径与构造方式（其按 `template_id` 校验空间/模板权限）。

- [ ] **Step 5: 在 `DebugService` 增加 `build_context_view`**

在 `service.py` 追加：

```python
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
```

- [ ] **Step 6: 注册路由**

先 `Read bkflow/template/urls.py` 确认 router 变量名，然后追加（与现有 `register` 风格一致）：

```python
from bkflow.template.views.debug import DebugViewSet

drf_router.register(r"debug", DebugViewSet, basename="debug")
```

- [ ] **Step 7: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_views_context.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add bkflow/template/debug/serializers.py bkflow/template/views/debug.py bkflow/template/urls.py bkflow/template/debug/service.py tests/interface/template/debug/test_views_context.py
git commit -m "feat(debug): 新增 Debug 上下文/输入元数据接口 --story=135505027"
```

---

# Phase 2 — 全局调试（Engine 接入 + Interface 编排）

产出：`POST /debug/global_run` 创建并运行真实 DEBUG 任务，跑完把节点态/全局变量/`log_ref` 回写统一上下文；`reset`/`terminate`/`history` 可用。

### Task 2.1: Engine 支持 `create_method="DEBUG"` 与 mock 物化扩展

**Files:**
- Modify: `bkflow/task/models.py`（`CREATE_METHODS`、`create_instance`）
- Modify: `bkflow/utils/context.py`（`TaskContext.is_mock`）
- Modify: `bkflow/task/serializers.py`（`mock_data` 增加 `fail_nodes`/`errors`）
- Modify: `bkflow/task/views.py`（列表默认隐藏 DEBUG）
- Test: `tests/engine/task/test_debug_create_instance.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.task.models import TaskInstance, TaskMockData
from bkflow.utils.context import TaskContext

PIPELINE = {
    "id": "p",
    "start_event": {"id": "s", "type": "EmptyStartEvent", "incoming": None, "outgoing": "f0"},
    "end_event": {"id": "e", "type": "EmptyEndEvent", "incoming": "f1", "outgoing": None},
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "incoming": "f0", "outgoing": "f1", "optional": True,
              "component": {"code": "test", "data": {}}},
    },
    "flows": {"f0": {"id": "f0", "source": "s", "target": "A"}, "f1": {"id": "f1", "source": "A", "target": "e"}},
    "gateways": {}, "constants": {}, "outputs": [],
}


@pytest.mark.django_db
class TestDebugCreateInstance:
    def test_debug_method_materializes_mock_with_fail_nodes(self):
        instance = TaskInstance.objects.create_instance(
            pipeline_tree={**PIPELINE},
            space_id=10,
            create_method="DEBUG",
            creator="admin",
            mock_data={"nodes": ["A"], "outputs": {"A": {"k": "v"}}, "fail_nodes": ["A"], "errors": {"A": "boom"}},
        )
        mock = TaskMockData.objects.get(taskflow_id=instance.id)
        # 节点 id 经 replace_all_id 重映射，但单节点可断言键集合非空
        assert mock.data["nodes"]
        assert "fail_nodes" in mock.data and mock.data["fail_nodes"]
        assert "errors" in mock.data and list(mock.data["errors"].values()) == ["boom"]

    def test_debug_task_is_mock_true(self):
        instance = TaskInstance.objects.create_instance(
            pipeline_tree={**PIPELINE}, space_id=10, create_method="DEBUG", creator="admin",
        )
        assert TaskContext(instance).is_mock is True
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/engine/task/test_debug_create_instance.py -v`
Expected: FAIL（`is_mock` 为 False / `fail_nodes` 未映射）

- [ ] **Step 3: 改 `CREATE_METHODS` 与 `create_instance`**

`bkflow/task/models.py`：

```python
    CREATE_METHODS = (("API", "API"), ("MOCK", "MOCK"), ("DEBUG", "DEBUG"))
```

把物化分支条件从 `== "MOCK"` 改为包含 DEBUG，并映射 `fail_nodes`/`errors`：

```python
            if kwargs.get("create_method") in ("MOCK", "DEBUG"):
                new_mock_data = {}
                act_mappings = node_mappings[PE.activities]
                new_mock_data["nodes"] = [act_mappings[node_id] for node_id in mock_data.get("nodes", [])]
                new_mock_data["outputs"] = {
                    act_mappings[node_id]: outputs for node_id, outputs in mock_data.get("outputs", {}).items()
                }
                if mock_data.get("fail_nodes"):
                    new_mock_data["fail_nodes"] = [act_mappings[nid] for nid in mock_data["fail_nodes"]]
                if mock_data.get("errors"):
                    new_mock_data["errors"] = {
                        act_mappings[nid]: msg for nid, msg in mock_data["errors"].items()
                    }
                TaskMockData.objects.create(
                    taskflow_id=instance.id, data=new_mock_data, mock_data_ids=mock_data.get("mock_data_ids", {})
                )
```

- [ ] **Step 4: 改 `TaskContext.is_mock`**

`bkflow/utils/context.py`：

```python
        self.is_mock = taskflow.create_method in ("MOCK", "DEBUG")
```

- [ ] **Step 5: `mock_data` 序列化器增加 fail 字段**

`bkflow/task/serializers.py`（找到 task 创建用的 mock_data serializer，追加）：

```python
    fail_nodes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    errors = serializers.JSONField(required=False, default=dict)
```

- [ ] **Step 6: 列表默认隐藏 DEBUG**

`bkflow/task/views.py` 的 `TaskInstanceViewSet`，重写 `get_queryset`：

```python
    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list" and "create_method" not in self.request.query_params:
            queryset = queryset.exclude(create_method="DEBUG")
        return queryset
```

- [ ] **Step 7: 生成迁移并跑测试**

Run: `python manage.py makemigrations task && pytest tests/engine/task/test_debug_create_instance.py -v`
Expected: 生成 `task` choices 迁移；测试 PASS

- [ ] **Step 8: Commit**

```bash
git add bkflow/task/models.py bkflow/utils/context.py bkflow/task/serializers.py bkflow/task/views.py bkflow/task/migrations/ tests/engine/task/test_debug_create_instance.py
git commit -m "feat(debug): Engine 支持 DEBUG 任务与 mock 失败物化 --story=135505027"
```

### Task 2.2: Engine 节点 id 映射端点 + Client 方法

**Files:**
- Modify: `bkflow/task/views.py`（新增 `get_node_id_map` action）
- Modify: `bkflow/contrib/api/collections/task.py`（`TaskComponentClient.get_node_id_map`）
- Test: `tests/engine/task/test_node_id_map.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

from bkflow.task.models import TaskInstance
from bkflow.task.views import TaskInstanceViewSet

User = get_user_model()
PIPELINE = {
    "id": "p",
    "start_event": {"id": "s", "type": "EmptyStartEvent", "incoming": None, "outgoing": "f0"},
    "end_event": {"id": "e", "type": "EmptyEndEvent", "incoming": "f1", "outgoing": None},
    "activities": {"A": {"id": "A", "type": "ServiceActivity", "incoming": "f0", "outgoing": "f1",
                         "optional": True, "component": {"code": "t", "data": {}}}},
    "flows": {"f0": {"id": "f0", "source": "s", "target": "A"}, "f1": {"id": "f1", "source": "A", "target": "e"}},
    "gateways": {}, "constants": {}, "outputs": [],
}


@pytest.mark.django_db
class TestNodeIdMap:
    def test_returns_template_to_runtime_map(self):
        user = User.objects.create_superuser("admin", "a@a.com", "x")
        instance = TaskInstance.objects.create_instance(
            pipeline_tree={**PIPELINE}, space_id=10, create_method="DEBUG", creator="admin"
        )
        factory = APIRequestFactory()
        view = TaskInstanceViewSet.as_view({"get": "get_node_id_map"})
        request = factory.get(f"/task/{instance.id}/get_node_id_map/")
        force_authenticate(request, user=user)
        response = view(request, pk=instance.id)
        assert response.status_code == 200
        # 模板节点 A -> 运行时 id（重映射后非 "A"）
        assert "A" in response.data["data"]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/engine/task/test_node_id_map.py -v`
Expected: FAIL（action 不存在）

- [ ] **Step 3: 实现 action**

`bkflow/task/views.py` 的 `TaskInstanceViewSet` 追加（`execution_data` 来自执行快照，活动节点带 `template_node_id` 与重映射后的 `id`）：

```python
    @action(detail=True, methods=["get"], url_path="get_node_id_map")
    def get_node_id_map(self, request, *args, **kwargs):
        task_instance = self.get_object()
        activities = task_instance.execution_data.get("activities", {})
        mapping = {act.get("template_node_id", act_id): act_id for act_id, act in activities.items()}
        return Response({"result": True, "data": mapping, "message": ""})
```

- [ ] **Step 4: 实现 Client 方法**

`bkflow/contrib/api/collections/task.py` 的 `TaskComponentClient`：

```python
    def get_node_id_map(self, task_id):
        return self._request(method="get", url=self._get_task_url("task/{}/get_node_id_map/".format(task_id)), data={})
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/engine/task/test_node_id_map.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bkflow/task/views.py bkflow/contrib/api/collections/task.py tests/engine/task/test_node_id_map.py
git commit -m "feat(debug): 新增任务节点 id 映射端点 --story=135505027"
```

### Task 2.3: DebugService 全局调试（抢锁 / 重置 / 物化 / 创建并启动 DEBUG 任务）

**Files:**
- Modify: `bkflow/template/debug/service.py`
- Test: `tests/interface/template/debug/test_service_global_run.py`

> 全局调试经 `TaskComponentClient.create_task` 创建 `create_method="DEBUG"` 任务，再 `operate/start`。`create_task`/`operate` 已存在，无需改 Engine 接口。

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, DebugNodeState

PIPELINE = {"activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
            "flows": {}, "gateways": {}, "constants": {}}


@pytest.mark.django_db
class TestGlobalRun:
    def _svc(self, mocker, create_ok=True, task_id=456):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=PIPELINE)
        client = mocker.MagicMock()
        client.create_task.return_value = {"result": create_ok, "data": {"task_id": task_id}, "message": ""}
        client.task_operate.return_value = {"result": True, "data": {}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)
        return svc, client

    def test_global_run_locks_resets_and_starts(self, mocker):
        svc, client = self._svc(mocker)
        ctx = svc.get_or_create_context()
        DebugNodeState.objects.create(debug_context=ctx, node_id="A", status="finished", outputs={"k": "v"},
                                      execution_mode="mock", mock_outputs={"k": "v"})
        result = svc.global_run(inputs={"${biz}": "100"}, operator="admin")
        ctx.refresh_from_db()
        assert result["task_id"] == 456
        assert ctx.status == "running"
        assert ctx.active_task_id == 456
        assert ctx.last_inputs == {"${biz}": "100"}
        # 重置运行结果、保留 mock 配置
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "not_run" and ns.outputs == {}
        assert ns.execution_mode == "mock" and ns.mock_outputs == {"k": "v"}
        # 物化 mock_data 传入 create_task
        sent = client.create_task.call_args.args[0] if client.create_task.call_args.args else client.create_task.call_args.kwargs
        assert sent["create_method"] == "DEBUG"

    def test_global_run_rejects_when_not_idle(self, mocker):
        svc, _ = self._svc(mocker)
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.locked_by = "bob"
        ctx.save()
        with pytest.raises(Exception) as exc:
            svc.global_run(inputs={}, operator="admin")
        assert "bob" in str(exc.value)
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_service_global_run.py -v`
Expected: FAIL（`global_run` 不存在）

- [ ] **Step 3: 实现 `global_run` 及依赖工具**

在 `service.py` 顶部补充 import：

```python
from django.db import transaction
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.template.constants import TaskTriggerMethod  # 若无则用字符串 "manual"
```

追加方法（自定义异常用现有 `bkflow` 校验异常或简单 `ValueError`，视项目而定；下例用 `DebugConflictError`/`DebugStateError` 两个轻量异常，定义在 `service.py` 顶部）：

```python
class DebugConflictError(Exception):
    """并发锁冲突（HTTP 409）"""


class DebugStateError(Exception):
    """状态/参数错误（HTTP 400）"""


# class DebugService 内：

    def _task_client(self):
        return TaskComponentClient(space_id=self.space_id)

    def _acquire_lock(self, ctx: DebugContext, operator: str):
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
            status="not_run", inputs={}, outputs={}, duration_ms=None,
            error_detail={}, log_ref={}, last_run_at=None,
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

            template = Template.objects.get(id=self.template_id)
            create_data = {
                "template_id": self.template_id,
                "space_id": self.space_id,
                "scope_type": template.scope_type,
                "scope_value": template.scope_value,
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
            task_id = create_result["data"]["task_id"]
            ctx.active_task_id = task_id
            ctx.save(update_fields=["active_task_id"])

            start_result = client.task_operate(task_id, "start", {"operator": operator})
            if not start_result.get("result"):
                self._release_lock(ctx, status="idle")
                raise DebugStateError(start_result.get("message", "start debug task failed"))
            return {"task_id": task_id, "status": "running"}
        except (DebugConflictError, DebugStateError):
            raise
        except Exception:
            self._release_lock(ctx, status="idle")
            raise
```

> 注：`client.create_task` / `client.task_operate` 的精确方法名以 `bkflow/contrib/api/collections/task.py` 为准（`create_task` 已确认存在；启动方法形如 `task_operate(task_id, "start", data)`，实现前 `Read` 确认签名）。
>
> **【评审 #5 阻塞校准】`inputs` 初值如何注入必须实现前确认**：本计划用 `create_data["constants"]` 传入 `inputs`，但全局调试的语义是「用用户输入覆盖 `pipeline_tree.constants` 里 show 常量的 `value`」。实现前先 `Read bkflow/task/serializers.py` 确认 `create_task` 是否接收 `constants` 字段及其格式。**若不接收，改为在构造 `create_data["pipeline_tree"]` 前，把 `inputs[key]` 写回 `pipeline_tree["constants"][key]["value"]`**（深拷贝后修改，勿污染 draft 快照），这是最稳的初值注入方式。对应需补一个单测：`global_run` 后该常量 value 等于传入 inputs。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_service_global_run.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/template/debug/service.py tests/interface/template/debug/test_service_global_run.py
git commit -m "feat(debug): DebugService 全局调试编排（抢锁/重置/物化/启动） --story=135505027"
```

### Task 2.4: 全局运行结果回写（节点态 / 全局变量 / log_ref）

**Files:**
- Modify: `bkflow/template/debug/service.py`（`sync_from_debug_task`）
- Test: `tests/interface/template/debug/test_service_sync.py`

> 由 `GET /debug/context` 触发的"惰性同步"：当 `status=running` 且存在 `active_task_id` 时，读 `get_task_states` 判断是否结束，再回写。real 节点重数据不落库，仅落 `log_ref` + 轻量 `status`/`duration_ms`；mock 节点态由物化阶段决定、运行后由引擎短路产生，但其结果（成功输出）已知，回写到 `outputs` 并按 `source_act/source_key` 合并到 `global_vars`。

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugNodeState

PIPELINE = {
    "activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
    "flows": {}, "gateways": {},
    "constants": {"${g1}": {"key": "${g1}", "name": "g1", "show_type": "hide", "value": "",
                            "source_type": "component_outputs", "custom_type": "", "source_tag": "",
                            "source_info": {"A": ["k1"]}}},
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
        client.get_task_states.return_value = {"result": True, "data": {"state": "FINISHED",
            "children": {"rtA": {"state": "FINISHED", "elapsed_time": 2}}}, "message": ""}
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        # 节点 A 的输出（含产出 k1）
        client.get_task_node_detail.return_value = {"result": True,
            "data": {"outputs": [{"key": "k1", "value": "produced"}], "version": "v1"}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)

        svc.sync_from_debug_task(ctx)
        ctx.refresh_from_db()
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "finished"
        assert ns.log_ref == {"instance_id": 456, "node_id": "rtA", "version": "v1"}
        assert ctx.global_vars.get("${g1}") == "produced"
        assert ctx.status == "idle"  # 整体结束后解锁
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_service_sync.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `sync_from_debug_task`**

在 `service.py` 追加（`classify_constants` 提供 `acts_outputs[node_id][output_key]=var_key` 映射，用于把节点输出写回全局变量）：

```python
from bkflow.pipeline_web.parser.format import classify_constants

ENGINE_FINISHED_STATES = {"FINISHED", "REVOKED", "FAILED"}
NODE_STATE_MAP = {"FINISHED": "finished", "FAILED": "failed", "RUNNING": "running", "READY": "not_run"}


# class DebugService 内：

    def _acts_outputs(self):
        return classify_constants(self.pipeline_tree.get("constants", {}), is_subprocess=False)["acts_outputs"]

    def sync_from_debug_task(self, ctx: DebugContext):
        if ctx.status not in ("running", "terminating") or not ctx.active_task_id:
            return
        client = self._task_client()
        states = client.get_task_states(ctx.active_task_id)
        if not states.get("result"):
            return
        data = states["data"]
        children = data.get("children", {})
        id_map = client.get_node_id_map(ctx.active_task_id).get("data", {})
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
```

> 注：`get_task_states` 子节点状态字段命名、`get_task_node_detail` 返回 `outputs` 结构以实际接口为准（参见调研：`get_node_data` 返回 `{"inputs", "outputs", "ex_data"}`，`outputs` 为 list）。实现前 `Read bkflow/task/operations.py` 的 `get_node_data`/`get_task_states` 校准字段。
>
> **【评审 #4 children 结构校准】**`get_task_states` 内部用 `flat_children=False`，返回的 `data["children"]` 是**嵌套树**。经核对：并行/分支网关的活动节点都是 root 的**直接子节点**（网关只分流、不嵌套），故 `data["children"][runtime_id]` 对本计划追踪的模板级活动可直接命中；只有**子流程**会把内部节点嵌套到子流程节点的 `children` 下，而本期不追踪子流程内部节点（子流程节点本身是顶层活动，可正常命中）。实现时用含**并行网关**的模板验证一次：所有模板活动都能在顶层 `children` 取到。若未来要追踪子流程内部，再改为递归展平或 `flat_children=True`。

- [ ] **Step 4: 在 `build_context_view` 入口触发惰性同步**

把 `build_context_view` 首行改为：

```python
        ctx = self.sync_node_states()
        self.sync_from_debug_task(ctx)
        ctx.refresh_from_db()
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_service_sync.py tests/interface/template/debug/test_views_context.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bkflow/template/debug/service.py tests/interface/template/debug/test_service_sync.py
git commit -m "feat(debug): 全局调试结果回写统一上下文 --story=135505027"
```

### Task 2.5: reset / terminate / history + 视图

**Files:**
- Modify: `bkflow/template/debug/service.py`（`terminate` / `history`）
- Modify: `bkflow/template/views/debug.py`（`global_run`/`reset`/`terminate`/`history` actions）
- Test: `tests/interface/template/debug/test_views_run_ops.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

from bkflow.template.models import DebugContext, DebugNodeState
from bkflow.template.views.debug import DebugViewSet

User = get_user_model()
TREE = {"activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
        "flows": {}, "gateways": {}, "constants": {}}


@pytest.mark.django_db
class TestRunOpsViews:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser("admin", "a@a.com", "x")

    def _patch_tree(self, mocker):
        mocker.patch("bkflow.template.debug.service.DebugService.pipeline_tree",
                     new_callable=mocker.PropertyMock, return_value=TREE)
        mocker.patch("bkflow.template.debug.service.DebugService.space_id",
                     new_callable=mocker.PropertyMock, return_value=10)

    def test_global_run_conflict_returns_409(self, mocker):
        self._patch_tree(mocker)
        ctx = DebugContext.objects.create(template_id=1, space_id=10, status="running", locked_by="bob")
        view = DebugViewSet.as_view({"post": "global_run"})
        request = self.factory.post("/debug/global_run/", {"template_id": 1, "inputs": {}}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 409

    def test_reset_clears_results(self, mocker):
        self._patch_tree(mocker)
        ctx = DebugContext.objects.create(template_id=1, space_id=10)
        DebugNodeState.objects.create(debug_context=ctx, node_id="A", status="finished", outputs={"k": "v"})
        view = DebugViewSet.as_view({"post": "reset"})
        request = self.factory.post("/debug/reset/", {"template_id": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert "A" in response.data["reset_node_ids"]
        assert DebugNodeState.objects.get(debug_context=ctx, node_id="A").status == "not_run"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_views_run_ops.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `terminate` / `history`**

`service.py` 追加：

```python
    def reset(self, node_ids=None) -> list:
        ctx = self.sync_node_states()
        if ctx.status == "running":
            raise DebugConflictError("调试运行中，不能重置")
        return self.reset_run_results(ctx, node_ids=node_ids)

    def terminate(self, node_id=None, operator="") -> dict:
        ctx = self.get_or_create_context()
        if ctx.status == "idle" or not ctx.active_task_id:
            raise DebugStateError("当前没有运行中的调试")
        ctx.status = "terminating"
        ctx.save(update_fields=["status"])
        client = self._task_client()
        if node_id:
            id_map = client.get_node_id_map(ctx.active_task_id).get("data", {})
            runtime_id = id_map.get(node_id, node_id)
            client.task_node_operate(ctx.active_task_id, runtime_id, "forced_fail", {"operator": operator})
        else:
            client.task_operate(ctx.active_task_id, "revoke", {"operator": operator})
        return {"status": "terminating"}

    def history(self):
        """基于保留的 DEBUG 任务实例列出历次运行。"""
        client = self._task_client()
        result = client.task_list(
            data={"template_id": self.template_id, "space_id": self.space_id, "create_method": "DEBUG"}
        )
        runs = []
        for item in (result.get("data", {}) or {}).get("results", result.get("data", []) if isinstance(result.get("data"), list) else []):
            runs.append({
                "task_id": item.get("id"),
                "operator": item.get("creator") or item.get("executor"),
                "started_at": item.get("start_time") or item.get("create_at"),
                "status": item.get("state") or item.get("status"),
            })
        return {"runs": runs}
```

> 注：`task_list` 返回分页结构以实际接口为准；`task_node_operate` 方法名/签名以 `TaskComponentClient` 为准（Engine 路由 `node_operate/{node_id}/{operation}`）。实现前 `Read` 校准。

- [ ] **Step 4: 视图层补 actions**

`bkflow/template/views/debug.py` 追加（异常 → HTTP 状态码映射）：

```python
from rest_framework import status

from bkflow.template.debug.serializers import (
    GlobalRunSerializer, ResetSerializer, TerminateSerializer,
)
from bkflow.template.debug.service import DebugConflictError, DebugStateError


def _err(exc, code):
    return Response(exception=True, data={"detail": str(exc)}, status=code)


# DebugViewSet 内：

    @action(methods=["POST"], detail=False)
    def global_run(self, request, *args, **kwargs):
        ser = GlobalRunSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        svc = DebugService(template_id=ser.validated_data["template_id"])
        try:
            data = svc.global_run(inputs=ser.validated_data["inputs"], operator=request.user.username)
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        except DebugStateError as e:
            return _err(e, status.HTTP_400_BAD_REQUEST)
        return Response(data)

    @action(methods=["POST"], detail=False)
    def reset(self, request, *args, **kwargs):
        ser = ResetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        svc = DebugService(template_id=ser.validated_data["template_id"])
        try:
            reset_ids = svc.reset(node_ids=ser.validated_data.get("node_ids"))
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        return Response({"reset_node_ids": reset_ids})

    @action(methods=["POST"], detail=False)
    def terminate(self, request, *args, **kwargs):
        ser = TerminateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        svc = DebugService(template_id=ser.validated_data["template_id"])
        try:
            data = svc.terminate(node_id=ser.validated_data.get("node_id"), operator=request.user.username)
        except DebugStateError as e:
            return _err(e, status.HTTP_400_BAD_REQUEST)
        return Response(data)

    @action(methods=["GET"], detail=False)
    def history(self, request, *args, **kwargs):
        query = TemplateIdQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        svc = DebugService(template_id=query.validated_data["template_id"])
        return Response(svc.history())
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_views_run_ops.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bkflow/template/debug/service.py bkflow/template/views/debug.py tests/interface/template/debug/test_views_run_ops.py
git commit -m "feat(debug): 全局调试运行/重置/终止/历史接口 --story=135505027"
```

---

# Phase 3 — 单步调试 + mock 配置 + 失败注入

产出：`step_run`（real 微型任务 / mock 直出）、`node_mock`（方案 A）、`context_var`，以及引擎 mock 失败注入。

### Task 3.1: 引擎 mock 失败注入（向后兼容）

**Files:**
- Modify: `bkflow/pipeline_plugins/components/collections/base.py`（`mock_execute` / `mock_schedule`）
- Test: `tests/engine/task/test_bkflow_base_plugin_service.py`（追加用例）

> 现状：`mock_execute`/`mock_schedule` 恒 `return True`。扩展：`TaskMockData.data["fail_nodes"]` 含本节点时，设置 `ex_data=errors[node_id]` 并 `return False`。无 `fail_nodes` 时行为与现状完全一致。

- [ ] **Step 1: 写失败测试**（追加到现有测试文件，复用其 MOCK_DATA 夹具风格）

```python
class TestMockFailInjection:
    """mock 失败注入：fail_nodes 命中时 execute 返回 False 并写 ex_data"""

    def _service(self, mocker, mock_data):
        from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService
        mocker.patch.object(BKFlowBaseService, "get_taskflow_mock_data", return_value=mock_data)

        class _S(BKFlowBaseService):
            def inputs_format(self): return []
            def outputs_format(self): return []
            def execute_method(self, data, parent_data): return True
            def need_schedule(self): return False

        svc = _S()
        svc.id = "node1"
        return svc

    def test_mock_execute_fail_sets_ex_data_and_returns_false(self, mocker):
        svc = self._service(mocker, {"nodes": ["node1"], "outputs": {}, "fail_nodes": ["node1"], "errors": {"node1": "boom"}})
        data = mocker.MagicMock()
        parent_data = mocker.MagicMock()
        result = svc.mock_execute(data, parent_data)
        assert result is False
        data.set_outputs.assert_any_call("ex_data", "boom")

    def test_mock_execute_success_unchanged(self, mocker):
        svc = self._service(mocker, {"nodes": ["node1"], "outputs": {"node1": {"k": "v"}}})
        data = mocker.MagicMock()
        parent_data = mocker.MagicMock()
        assert svc.mock_execute(data, parent_data) is True
        data.set_outputs.assert_any_call("k", "v")
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/engine/task/test_bkflow_base_plugin_service.py::TestMockFailInjection -v`
Expected: FAIL（fail 分支未实现）

- [ ] **Step 3: 扩展 `mock_execute` / `mock_schedule`**

`bkflow/pipeline_plugins/components/collections/base.py`，新增私有方法并在两处优先判定失败：

```python
    def _get_mock_fail_info(self, taskflow_id):
        mock_data = self.get_taskflow_mock_data(taskflow_id)
        return mock_data.get("fail_nodes", []), mock_data.get("errors", {})

    def mock_execute(self, data, parent_data):
        taskflow_id = parent_data.get_one_of_inputs("task_id")
        fail_nodes, errors = self._get_mock_fail_info(taskflow_id)
        if self.id in fail_nodes:
            data.set_outputs("ex_data", errors.get(self.id, "mock failed"))
            return False
        if self.need_schedule():
            self.interval = StaticIntervalGenerator(2)
            return True
        taskflow_outputs = self.get_mock_outputs(taskflow_id)
        mock_outputs = taskflow_outputs.get(self.id, {})
        for k, value in mock_outputs.items():
            data.set_outputs(k, value)
        return True

    def mock_schedule(self, data, parent_data, callback_data=None):
        taskflow_id = parent_data.get_one_of_inputs("task_id")
        fail_nodes, errors = self._get_mock_fail_info(taskflow_id)
        if self.id in fail_nodes:
            data.set_outputs("ex_data", errors.get(self.id, "mock failed"))
            return False
        taskflow_outputs = self.get_mock_outputs(taskflow_id)
        mock_outputs = taskflow_outputs.get(self.id, {})
        for k, value in mock_outputs.items():
            data.set_outputs(k, value)
        self.finish_schedule()
        return True
```

> fail 判定在 `need_schedule` 之前，故 schedule 型失败节点在 execute 即失败，不进入轮询。

- [ ] **Step 4: 运行确认通过（含原有 mock 用例不回归）**

Run: `pytest tests/engine/task/test_bkflow_base_plugin_service.py -v`
Expected: PASS（新用例 + 原成功用例均通过）

- [ ] **Step 5: Commit**

```bash
git add bkflow/pipeline_plugins/components/collections/base.py tests/engine/task/test_bkflow_base_plugin_service.py
git commit -m "feat(debug): mock 节点支持失败注入（向后兼容） --story=135505027"
```

### Task 3.2: 微型单节点 pipeline 构造器

**Files:**
- Create: `bkflow/template/debug/pipeline_builder.py`
- Test: `tests/interface/template/debug/test_pipeline_builder.py`

> 手工构造 `start→node→end` 最小 web 树；节点引用的变量注入为 plain 常量（值取 `var_values`）；`component_outputs` 型常量降级为 `custom`（mini 树中无产出节点）。

- [ ] **Step 1: 写失败测试**

```python
from bkflow.template.debug.pipeline_builder import build_single_node_pipeline_tree

FULL_TREE = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "name": "A", "optional": True,
              "component": {"code": "t", "data": {"x": {"hook": False, "value": "1"}}}},
        "B": {"id": "B", "type": "ServiceActivity", "name": "B", "optional": True,
              "component": {"code": "t", "data": {"y": {"hook": True, "value": "${g1}"}}}},
    },
    "flows": {}, "gateways": {},
    "constants": {"${g1}": {"key": "${g1}", "name": "g1", "show_type": "hide", "value": "",
                            "source_type": "component_outputs", "custom_type": "", "source_tag": "",
                            "source_info": {"A": ["k1"]}}},
}


class TestBuildSingleNode:
    def test_minimal_topology_and_constants(self):
        tree = build_single_node_pipeline_tree(FULL_TREE, "B", var_values={"${g1}": "hydrated"})
        # 仅一个活动节点 B，且 start->B->end 连通
        assert list(tree["activities"].keys()) == ["B"]
        b = tree["activities"]["B"]
        assert tree["start_event"]["outgoing"] == b["incoming"]
        assert tree["end_event"]["incoming"] == b["outgoing"]
        assert len(tree["flows"]) == 2
        # ${g1} 被注入值并降级为 custom
        c = tree["constants"]["${g1}"]
        assert c["value"] == "hydrated"
        assert c["source_type"] == "custom" and c["source_info"] == {}

    def test_node_not_found_raises(self):
        import pytest
        with pytest.raises(KeyError):
            build_single_node_pipeline_tree(FULL_TREE, "ZZZ", var_values={})
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_pipeline_builder.py -v`
Expected: FAIL

- [ ] **Step 3: 实现构造器**

```python
# -*- coding: utf-8 -*-
import copy

from pipeline.core.constants import PE
from pipeline.utils.uniqid import node_uniqid


def build_single_node_pipeline_tree(full_tree: dict, node_id: str, var_values: dict) -> dict:
    """构造仅含 node_id 的最小 web pipeline_tree：start -> node -> end。

    :param full_tree: 完整 draft pipeline_tree
    :param node_id: 目标节点（必须是 ServiceActivity）
    :param var_values: 注入到常量的取值 {${key}: value}
    """
    if node_id not in full_tree.get("activities", {}):
        raise KeyError("node {} not in pipeline activities".format(node_id))

    node = copy.deepcopy(full_tree["activities"][node_id])
    start_id, end_id = node_uniqid(), node_uniqid()
    flow_in, flow_out = node_uniqid(), node_uniqid()

    node["incoming"] = flow_in
    node["outgoing"] = flow_out
    node.setdefault("optional", True)

    constants = {}
    for key, c in full_tree.get("constants", {}).items():
        nc = copy.deepcopy(c)
        if key in var_values:
            nc["value"] = var_values[key]
        # mini 树中没有产出节点，所有产出型常量降级为 custom 直接给值
        if nc.get("source_type") == "component_outputs":
            nc["source_type"] = "custom"
            nc["source_info"] = {}
            nc["source_tag"] = ""
            if key in var_values:
                nc["value"] = var_values[key]
        constants[key] = nc

    return {
        "id": node_uniqid(),
        "name": "debug_single_node",
        "start_event": {"id": start_id, "name": "start", "type": "EmptyStartEvent", "incoming": None, "outgoing": flow_in},
        "end_event": {"id": end_id, "name": "end", "type": "EmptyEndEvent", "incoming": flow_out, "outgoing": None},
        "activities": {node_id: node},
        "flows": {
            flow_in: {"id": flow_in, "source": start_id, "target": node_id},
            flow_out: {"id": flow_out, "source": node_id, "target": end_id},
        },
        "gateways": {},
        "constants": constants,
        "outputs": [],
    }
```

> 注：`node_uniqid` / `PE` 导入路径以仓库实际为准（`bkflow/task/models.py` 已 `from pipeline...` 引入 `node_uniqid`、`replace_all_id`、`PE`）。实现前 `Read` 校准 import。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_pipeline_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/template/debug/pipeline_builder.py tests/interface/template/debug/test_pipeline_builder.py
git commit -m "feat(debug): 新增单节点最小 pipeline 构造器 --story=135505027"
```

### Task 3.3: 可单步性判定（can_step）

**Files:**
- Modify: `bkflow/template/debug/service.py`（替换占位 `compute_can_step`）
- Test: `tests/interface/template/debug/test_can_step.py`

> 规则：解析节点引用的变量；普通用户常量恒可用；`component_outputs` 产出型变量须已在 `global_vars` 有值；缺值则不可单步并返回缺失项。

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext

TREE = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
        "B": {"id": "B", "type": "ServiceActivity", "component": {"code": "t", "data": {"y": {"hook": True, "value": "${g1}"}}}},
    },
    "flows": {}, "gateways": {},
    "constants": {"${g1}": {"key": "${g1}", "name": "g1", "show_type": "hide", "value": "",
                            "source_type": "component_outputs", "source_info": {"A": ["k1"]}, "custom_type": "", "source_tag": ""}},
}


@pytest.mark.django_db
class TestCanStep:
    def test_no_dependency_node_can_step(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        can, missing = svc.compute_can_step(ctx, "A")
        assert can is True and missing == []

    def test_consumer_blocked_until_producer_ran(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        can, missing = svc.compute_can_step(ctx, "B")
        assert can is False
        assert missing == [{"key": "${g1}", "source_node_id": "A"}]
        ctx.global_vars = {"${g1}": "v"}
        ctx.save()
        can2, missing2 = svc.compute_can_step(ctx, "B")
        assert can2 is True and missing2 == []
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_can_step.py -v`
Expected: FAIL（占位实现恒 True）

- [ ] **Step 3: 实现 `compute_can_step`**

替换 `service.py` 中的占位实现：

```python
    def compute_can_step(self, ctx, node_id):
        act = self.pipeline_tree.get("activities", {}).get(node_id)
        if not act:
            return False, []
        classified = classify_constants(self.pipeline_tree.get("constants", {}), is_subprocess=False)
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
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_can_step.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/template/debug/service.py tests/interface/template/debug/test_can_step.py
git commit -m "feat(debug): 实现单步可执行性判定 --story=135505027"
```

### Task 3.4: step_run（real 微型任务 / mock 直出）+ node_mock + context_var

**Files:**
- Modify: `bkflow/template/debug/service.py`（`step_run` / `node_mock` / `set_context_var` / `writeback_outputs`）
- Modify: `bkflow/template/views/debug.py`（`step_run`/`node_mock`/`context_var` actions）
- Test: `tests/interface/template/debug/test_step_run.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.template.debug.service import DebugConflictError, DebugService, DebugStateError
from bkflow.template.models import DebugContext, DebugNodeState

TREE = {
    "activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
    "flows": {}, "gateways": {},
    "constants": {"${g1}": {"key": "${g1}", "name": "g1", "show_type": "hide", "value": "",
                            "source_type": "component_outputs", "source_info": {"A": ["k1"]}, "custom_type": "", "source_tag": ""}},
}


@pytest.mark.django_db
class TestStepRunAndMock:
    def test_step_run_mock_success_writes_global_vars(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        result = svc.step_run(node_id="A", operator="admin", mode="mock",
                              mock_result="success", mock_outputs={"k1": "produced"})
        assert result["status"] == "finished"
        assert result["outputs"] == {"k1": "produced"}
        ctx.refresh_from_db()
        assert ctx.global_vars["${g1}"] == "produced"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "finished" and ns.log_ref in (None, {})

    def test_step_run_mock_fail_sets_failed_no_writeback(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        result = svc.step_run(node_id="A", operator="admin", mode="mock",
                              mock_result="fail", mock_error="boom")
        assert result["status"] == "failed"
        assert result["error_detail"]["message"] == "boom"
        ctx.refresh_from_db()
        assert "${g1}" not in ctx.global_vars

    def test_node_mock_sets_execution_mode_mock_and_writes_back(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        result = svc.node_mock(node_id="A", enable=True, mock_result="success", mock_outputs={"k1": "v"})
        assert result["execution_mode"] == "mock"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.execution_mode == "mock" and ns.mock_outputs == {"k1": "v"}
        ctx.refresh_from_db()
        assert ctx.global_vars["${g1}"] == "v"

    def test_node_mock_disable_keeps_presets(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        svc.node_mock(node_id="A", enable=True, mock_result="success", mock_outputs={"k1": "v"})
        result = svc.node_mock(node_id="A", enable=False)
        assert result["execution_mode"] == "real"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.execution_mode == "real" and ns.mock_outputs == {"k1": "v"}

    def test_context_var_sets_value(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        result = svc.set_context_var(key="${biz}", value="200")
        assert result["global_vars"]["${biz}"] == "200"

    def test_context_var_blocked_when_running(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        ctx.status = "running"
        ctx.save()
        with pytest.raises(DebugConflictError):
            svc.set_context_var(key="${biz}", value="200")

    def test_node_mock_does_not_mark_status(self):
        """配置 mock 不应把节点标记为 finished（评审 #3）"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        svc.node_mock(node_id="A", enable=True, mock_result="success", mock_outputs={"k1": "v"})
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.status == "not_run"  # 仅配置，未运行

    def test_step_run_real_targets_activity_and_records_duration(self, mocker):
        """real 单步应命中活动 runtime id（非 start/end 事件）并落库耗时（评审 #1/#2）"""
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()

        client = mocker.MagicMock()
        client.create_task.return_value = {"result": True, "data": {"task_id": 789}, "message": ""}
        client.task_operate.return_value = {"result": True, "data": {}, "message": ""}
        client.get_node_id_map.return_value = {"result": True, "data": {"A": "rtA"}, "message": ""}
        client.get_task_states.return_value = {"result": True, "data": {"state": "FINISHED", "children": {
            "start_evt": {"state": "FINISHED", "elapsed_time": 0},
            "rtA": {"state": "FINISHED", "elapsed_time": 3},
        }}, "message": ""}
        client.get_task_node_detail.return_value = {"result": True,
            "data": {"outputs": [{"key": "k1", "value": "produced"}], "version": "v1"}, "message": ""}
        mocker.patch.object(svc, "_task_client", return_value=client)

        result = svc.step_run(node_id="A", operator="admin", mode="real")
        assert result["status"] == "finished"
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        assert ns.log_ref == {"instance_id": 789, "node_id": "rtA", "version": "v1"}
        assert ns.duration_ms == 3000
        ctx.refresh_from_db()
        assert ctx.global_vars["${g1}"] == "produced"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_step_run.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 step_run / node_mock / set_context_var + 共用回写**

`service.py` 追加（real 路径用 Task 3.2 构造器建微型 DEBUG 任务并启动，跑完读单节点结果；mock 路径不经引擎直接产出）：

```python
    def _apply_outputs_to_global_vars(self, ctx, node_id, outputs: dict):
        """成功输出按 source_act/source_key 合并到 global_vars 并持久化（不触碰节点状态）。"""
        acts_outputs = self._acts_outputs().get(node_id, {})
        for out_key, var_key in acts_outputs.items():
            if out_key in (outputs or {}):
                ctx.global_vars[var_key] = outputs[out_key]
        ctx.save(update_fields=["global_vars"])

    def set_context_var(self, key, value) -> dict:
        ctx = self.get_or_create_context()
        if ctx.status != "idle":
            raise DebugConflictError("调试运行中，禁止编辑变量")
        ctx.global_vars[key] = value
        ctx.save(update_fields=["global_vars"])
        return {"global_vars": ctx.global_vars}

    def node_mock(self, node_id, enable=True, mock_result="success", mock_outputs=None, mock_error="") -> dict:
        # node_mock 是纯「配置」：只改 execution_mode 与 mock_* 预设；
        # 不改节点运行状态（status），mock 角标由 execution_mode=mock 体现（评审 #3）。
        ctx = self.sync_node_states()
        if ctx.status != "idle":
            raise DebugConflictError("调试运行中，禁止配置 mock")
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id=node_id)
        if enable:
            ns.execution_mode = "mock"
            ns.mock_result = mock_result
            if mock_result == "success":
                ns.mock_outputs = mock_outputs or {}
                ns.mock_error = ""
                ns.save()
                # 配置成功输出即回写全局变量，便于下游立即单步消费（req5）；不改 status/outputs
                self._apply_outputs_to_global_vars(ctx, node_id, ns.mock_outputs)
            else:
                ns.mock_error = mock_error or "mock failed"
                ns.save()
        else:
            ns.execution_mode = "real"  # 保留 mock_* 预设
            ns.save(update_fields=["execution_mode"])
        ctx.refresh_from_db()
        return {"node_id": node_id, "execution_mode": ns.execution_mode, "updated_global_vars": ctx.global_vars}

    def step_run(self, node_id, operator, mode=None, input_overrides=None,
                 mock_result="success", mock_outputs=None, mock_error="") -> dict:
        ctx = self.sync_node_states()
        if ctx.status != "idle":
            raise DebugConflictError("模板正在被 {} 调试".format(ctx.locked_by or "其他用户"))
        ns = DebugNodeState.objects.get(debug_context=ctx, node_id=node_id)
        effective_mode = mode or ns.execution_mode

        if effective_mode == "mock":
            return self._step_run_mock(ctx, ns, mock_result, mock_outputs, mock_error)
        return self._step_run_real(ctx, ns, operator, input_overrides)

    def _step_run_mock(self, ctx, ns, mock_result, mock_outputs, mock_error):
        ns.log_ref = {}
        ns.duration_ms = 0  # mock 不经引擎，耗时记 0（req12 仍记录该字段）
        ns.last_run_at = timezone.now()
        if mock_result == "fail":
            ns.status = "failed"
            ns.outputs = {}
            ns.error_detail = {"type": "mock", "message": mock_error or "mock failed"}
            ns.save()
            return {"node_id": ns.node_id, "status": "failed", "outputs": None,
                    "error_detail": ns.error_detail, "updated_global_vars": ctx.global_vars, "log_ref": None}
        outputs = mock_outputs if mock_outputs else (ns.mock_outputs or {})
        ns.status = "finished"
        ns.outputs = outputs
        ns.error_detail = {}
        ns.save()
        self._apply_outputs_to_global_vars(ctx, ns.node_id, outputs)
        ctx.refresh_from_db()
        return {"node_id": ns.node_id, "status": "finished", "outputs": outputs,
                "error_detail": None, "updated_global_vars": ctx.global_vars, "log_ref": None}

    def _step_run_real(self, ctx, ns, operator, input_overrides):
        from bkflow.template.debug.pipeline_builder import build_single_node_pipeline_tree

        if input_overrides is None:
            can, missing = self.compute_can_step(ctx, ns.node_id)
            if not can:
                raise DebugStateError({"detail": "依赖未满足", "missing_vars": missing})
            var_values = dict(ctx.global_vars or {})
        else:
            var_values = dict(input_overrides)

        mini_tree = build_single_node_pipeline_tree(self.pipeline_tree, ns.node_id, var_values)
        template = Template.objects.get(id=self.template_id)
        client = self._task_client()
        create_result = client.create_task({
            "template_id": self.template_id,
            "space_id": self.space_id,
            "scope_type": template.scope_type,
            "scope_value": template.scope_value,
            "pipeline_tree": mini_tree,
            "mock_data": {"nodes": [], "outputs": {}},
            "create_method": "DEBUG",
            "trigger_method": "manual",
        })
        if not create_result.get("result"):
            raise DebugStateError(create_result.get("message", "create step task failed"))
        task_id = create_result["data"]["task_id"]
        ns.status = "running"
        ns.last_run_at = timezone.now()
        ns.save(update_fields=["status", "last_run_at"])
        client.task_operate(task_id, "start", {"operator": operator})

        # 用节点 id 映射精确定位该活动的 runtime id，避免误读 start/end 事件（评审 #1）
        runtime_id = client.get_node_id_map(task_id).get("data", {}).get(ns.node_id)
        outputs, status_str, error_detail, version, duration_ms = self._poll_single_node_result(
            client, task_id, runtime_id
        )
        ns.status = status_str
        ns.duration_ms = duration_ms  # 落库单步耗时（评审 #2）
        ns.log_ref = {"instance_id": task_id, "node_id": runtime_id, "version": version} if runtime_id else {}
        if status_str == "finished":
            ns.outputs = outputs
            ns.error_detail = {}
            ns.save()
            self._apply_outputs_to_global_vars(ctx, ns.node_id, outputs)
        else:
            ns.outputs = {}
            ns.error_detail = error_detail or {"type": "runtime", "message": "step failed"}
            ns.save()
        ctx.refresh_from_db()
        return {"node_id": ns.node_id, "status": ns.status,
                "outputs": outputs if status_str == "finished" else None,
                "error_detail": ns.error_detail or None,
                "updated_global_vars": ctx.global_vars, "log_ref": ns.log_ref or None}

    def _poll_single_node_result(self, client, task_id, runtime_id, max_loops=60, interval=1.0):
        """只针对目标活动节点的 runtime_id 轮询。

        :return: (outputs, status, error_detail, version, duration_ms)
        """
        import time
        if not runtime_id:
            return {}, "failed", {"type": "runtime", "message": "node id map missing"}, "v1", None
        for _ in range(max_loops):
            states = client.get_task_states(task_id)
            data = states.get("data", {}) if states.get("result") else {}
            child = (data.get("children", {}) or {}).get(runtime_id)
            if child and child.get("state") in ("FINISHED", "FAILED"):
                duration_ms = int((child.get("elapsed_time") or 0) * 1000)
                detail = client.get_task_node_detail(task_id, runtime_id, data={"include_data": True})
                ddata = detail.get("data", {}) if detail.get("result") else {}
                version = ddata.get("version") or ddata.get("history_id") or "v1"
                outputs = {o["key"]: o["value"] for o in ddata.get("outputs", []) if isinstance(o, dict) and "key" in o}
                if child["state"] == "FINISHED":
                    return outputs, "finished", {}, version, duration_ms
                return {}, "failed", {"type": "runtime", "message": ddata.get("ex_data", "step failed")}, version, duration_ms
            if data.get("state") in ("FINISHED", "FAILED", "REVOKED"):
                break
            time.sleep(interval)
        return {}, "failed", {"type": "timeout", "message": "step run timeout"}, "v1", None
```

> 注：轮询为同步实现（简单可靠，单节点通常秒级）。若节点为长轮询插件，可在后续迭代改为异步 + `GET /debug/context` 拉取。`get_task_states`/`get_task_node_detail` 字段以实际接口为准。

- [ ] **Step 4: 视图层补 actions**

`bkflow/template/views/debug.py` 追加：

```python
from bkflow.template.debug.serializers import ContextVarSerializer, NodeMockSerializer, StepRunSerializer


# DebugViewSet 内：

    @action(methods=["POST"], detail=False)
    def step_run(self, request, *args, **kwargs):
        ser = StepRunSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        svc = DebugService(template_id=vd["template_id"])
        try:
            data = svc.step_run(
                node_id=vd["node_id"], operator=request.user.username, mode=vd.get("mode"),
                input_overrides=vd.get("input_overrides"), mock_result=vd["mock_result"],
                mock_outputs=vd["mock_outputs"], mock_error=vd["mock_error"],
            )
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        except DebugStateError as e:
            detail = e.args[0] if e.args else str(e)
            return Response(exception=True, data={"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)

    @action(methods=["POST"], detail=False)
    def node_mock(self, request, *args, **kwargs):
        ser = NodeMockSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        svc = DebugService(template_id=vd["template_id"])
        try:
            data = svc.node_mock(node_id=vd["node_id"], enable=vd["enable"], mock_result=vd["mock_result"],
                                 mock_outputs=vd["mock_outputs"], mock_error=vd["mock_error"])
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        return Response(data)

    @action(methods=["POST"], detail=False)
    def context_var(self, request, *args, **kwargs):
        ser = ContextVarSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        svc = DebugService(template_id=vd["template_id"])
        try:
            data = svc.set_context_var(key=vd["key"], value=vd["value"])
        except DebugConflictError as e:
            return _err(e, status.HTTP_409_CONFLICT)
        return Response(data)
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_step_run.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bkflow/template/debug/service.py bkflow/template/views/debug.py tests/interface/template/debug/test_step_run.py
git commit -m "feat(debug): 单步调试/节点mock/上下文变量编辑 --story=135505027"
```

---

# Phase 4 — 变更重置（reset_impact）+ 旧 mock 兼容迁移

产出：`POST /debug/reset_impact` 后端 diff 只读告知；`TemplateMockScheme` 历史勾选迁移为 `execution_mode=mock` 初值。

### Task 4.1: reset_impact diff + 闭包

**Files:**
- Modify: `bkflow/template/debug/service.py`（`reset_impact`）
- Test: `tests/interface/template/debug/test_reset_impact.py`

> 用 `DebugContext.tree_fingerprint`（上次调试时指纹）对比当前 draft 指纹得 seed：① 节点 `config_hash` 变化 → 该节点；② 删除节点 → 消费其输出的节点 + 控制下游；③ 新增节点 → 其自身 + 下游；④ `flows`/`gateways`/`constants` 整体指纹变化时，对受影响 seed 取闭包。沿控制流 ∪ 数据流并集闭包传播。仅返回结果，不改库。

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext

TREE_V1 = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "optional": True, "component": {"code": "t", "data": {"x": {"hook": False, "value": "1"}}}},
        "B": {"id": "B", "type": "ServiceActivity", "optional": True, "component": {"code": "t", "data": {"y": {"hook": True, "value": "${g1}"}}}},
    },
    "flows": {"f1": {"id": "f1", "source": "A", "target": "B"}}, "gateways": {},
    "constants": {"${g1}": {"key": "${g1}", "name": "g1", "show_type": "hide", "value": "",
                            "source_type": "component_outputs", "source_info": {"A": ["k1"]}, "custom_type": "", "source_tag": ""}},
}


@pytest.mark.django_db
class TestResetImpact:
    def test_node_config_change_propagates_downstream(self):
        ctx = DebugContext.objects.create(template_id=1, space_id=10,
                                          tree_fingerprint=compute_tree_fingerprint(TREE_V1))
        # A 配置变更
        tree_v2 = {**TREE_V1, "activities": {
            "A": {"id": "A", "type": "ServiceActivity", "optional": True, "component": {"code": "t", "data": {"x": {"hook": False, "value": "CHANGED"}}}},
            "B": TREE_V1["activities"]["B"],
        }}
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=tree_v2)
        result = svc.reset_impact()
        assert set(result["reset_node_ids"]) == {"A", "B"}
        assert "A" in result["reasons"]

    def test_no_change_returns_empty(self):
        ctx = DebugContext.objects.create(template_id=1, space_id=10,
                                          tree_fingerprint=compute_tree_fingerprint(TREE_V1))
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_V1)
        result = svc.reset_impact()
        assert result["reset_node_ids"] == []
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_reset_impact.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `reset_impact`**

`service.py` 追加（用 `build_dependency_graph`/`closure`）：

```python
from bkflow.template.debug.dependency import build_dependency_graph, closure

# class DebugService 内：

    def reset_impact(self) -> dict:
        ctx = self.get_or_create_context()
        old_fp = ctx.tree_fingerprint or {}
        new_fp = compute_tree_fingerprint(self.pipeline_tree)
        old_nodes = old_fp.get("nodes", {})
        new_nodes = new_fp.get("nodes", {})

        seeds, reasons = set(), {}
        # 配置变更
        for nid, h in new_nodes.items():
            if nid in old_nodes and old_nodes[nid] != h:
                seeds.add(nid)
                reasons[nid] = "节点 {} 配置变更".format(nid)
            elif nid not in old_nodes:
                seeds.add(nid)
                reasons[nid] = "新增节点 {}".format(nid)
        # 删除节点：消费其输出的节点入种子（用旧图无法直接拿，保守地把全部当前节点纳入闭包起点）
        removed = set(old_nodes.keys()) - set(new_nodes.keys())
        # 连线/网关/常量整体变化：把所有当前节点作为潜在 seed 的保守处理（仅当对应指纹变化）
        topo_changed = any(old_fp.get(k) != new_fp.get(k) for k in ("flows", "gateways", "constants"))

        graph = build_dependency_graph(self.pipeline_tree)
        if removed:
            # 删除节点的下游无法从新图获得，退化为：对仍存在节点全集做闭包标记原因
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
```

> 注：删除节点/连线变更的精确传播在"无旧依赖图"时退化为保守全量重置，安全但偏粗。后续可在 `tree_fingerprint` 中额外持久化旧依赖图以做精确 diff（增量优化，非本期阻塞项）。

- [ ] **Step 4: 视图层补 action**

`bkflow/template/views/debug.py`：

```python
    @action(methods=["POST"], detail=False)
    def reset_impact(self, request, *args, **kwargs):
        query = TemplateIdQuerySerializer(data=request.data)
        query.is_valid(raise_exception=True)
        svc = DebugService(template_id=query.validated_data["template_id"])
        return Response(svc.reset_impact())
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_reset_impact.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bkflow/template/debug/service.py bkflow/template/views/debug.py tests/interface/template/debug/test_reset_impact.py
git commit -m "feat(debug): 变更影响 reset_impact 只读告知 --story=135505027"
```

### Task 4.2: 旧 mock 兼容 — TemplateMockScheme → execution_mode 初值（req6）

**Files:**
- Modify: `bkflow/template/debug/service.py`（`apply_legacy_mock_scheme`：sync 时把历史勾选节点初始化为 mock）
- Test: `tests/interface/template/debug/test_legacy_compat.py`

> 不写 data migration（DebugContext 按需懒创建）；改为：首次为某模板创建 DebugContext 时，读取该模板的 `TemplateMockScheme.data["nodes"]`，把这些节点的初始 `execution_mode` 置为 `mock`，并用 `TemplateMockData`（is_default）填充 `mock_outputs`。满足"旧 mock 数据可继续使用"。

- [ ] **Step 1: 写失败测试**

```python
import pytest

from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugNodeState, TemplateMockData, TemplateMockScheme

TREE = {"activities": {"A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
                       "B": {"id": "B", "type": "ServiceActivity", "component": {"code": "t", "data": {}}}},
        "flows": {}, "gateways": {}, "constants": {}}


@pytest.mark.django_db
class TestLegacyCompat:
    def test_scheme_nodes_initialized_as_mock(self):
        TemplateMockScheme.objects.create(space_id=10, template_id=1, data={"nodes": ["A"]})
        TemplateMockData.objects.create(space_id=10, template_id=1, node_id="A", name="d",
                                        data={"k": "v"}, is_default=True)
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        svc.sync_node_states()
        a = DebugNodeState.objects.get(debug_context=ctx, node_id="A")
        b = DebugNodeState.objects.get(debug_context=ctx, node_id="B")
        assert a.execution_mode == "mock"
        assert a.mock_outputs == {"k": "v"}
        assert b.execution_mode == "real"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/interface/template/debug/test_legacy_compat.py -v`
Expected: FAIL

- [ ] **Step 3: 实现迁移逻辑**

在 `service.py` 的 `sync_node_states` 里，对**新创建**的 DebugNodeState 应用旧 scheme：

```python
from bkflow.template.models import TemplateMockData, TemplateMockScheme

# sync_node_states 内，新建分支替换为：
        scheme_nodes = self._legacy_scheme_nodes()
        for node_id, act in activities.items():
            if node_id not in existing:
                ns = DebugNodeState.objects.create(
                    debug_context=ctx, node_id=node_id, node_type=act.get("type", "ServiceActivity")
                )
                if node_id in scheme_nodes:
                    ns.execution_mode = "mock"
                    default_md = TemplateMockData.objects.filter(
                        template_id=self.template_id, node_id=node_id, is_default=True
                    ).first()
                    if default_md:
                        ns.mock_outputs = default_md.data or {}
                    ns.save(update_fields=["execution_mode", "mock_outputs"])
```

并新增辅助：

```python
    def _legacy_scheme_nodes(self):
        scheme = TemplateMockScheme.objects.filter(template_id=self.template_id).first()
        if not scheme:
            return set()
        return set((scheme.data or {}).get("nodes", []))
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/interface/template/debug/test_legacy_compat.py tests/interface/template/debug/test_service_context.py -v`
Expected: PASS（旧用例不回归）

- [ ] **Step 5: Commit**

```bash
git add bkflow/template/debug/service.py tests/interface/template/debug/test_legacy_compat.py
git commit -m "feat(debug): 旧 TemplateMockScheme 迁移为节点 mock 初值 --story=135505027"
```

### Task 4.3: 全量回归 + APIGW 文档（如需）

**Files:**
- Test: 全量 `tests/interface/template/debug/` 与改动的 engine 测试

- [ ] **Step 1: 跑全部调试相关测试**

Run: `pytest tests/interface/template/debug/ tests/engine/task/test_debug_create_instance.py tests/engine/task/test_node_id_map.py tests/engine/task/test_bkflow_base_plugin_service.py -v`
Expected: 全部 PASS

- [ ] **Step 2: Black / isort / flake8**

Run: `black --line-length 120 bkflow/template/debug/ bkflow/template/views/debug.py && isort bkflow/template/debug/ && flake8 --max-line-length 120 bkflow/template/debug/`
Expected: 无错误

- [ ] **Step 3: 若 Debug 接口需经 APIGW 暴露**

按 `.cursor/rules/apigw-resource-sync.mdc` 与 `api-doc-sync` skill 同步 `bkflow/apigw/` 资源与文档。否则跳过（本期 Debug 接口仅 Interface 模块内部使用）。

- [ ] **Step 4: Commit（如有格式化改动）**

```bash
git add -A && git commit -m "style(debug): 格式化与回归校验 --story=135505027"
```

---

## 自检（写完计划后的 fresh-eyes 复核）

**1. Spec 覆盖**

| spec 需求 | 对应 Task | 覆盖 |
|---|---|---|
| req1 全局调试 | 2.1–2.5 | ✓ |
| req2 单步调试 | 3.2/3.3/3.4 | ✓ |
| req3 统一上下文 | 1.3/1.4/2.4 | ✓ |
| req4 变更重置 | 4.1 | ✓ |
| req5 mock 单步回写 | 3.4 | ✓ |
| req6 旧 mock 兼容 | 2.1/4.2 | ✓ |
| req7 运行中锁编辑 | 2.3/3.4（status 校验） | ✓ |
| req8 即时终止 | 2.5 | ✓ |
| req9 手动输入试运行 | 3.4（input_overrides） | ✓ |
| req10 编辑上下文变量 | 3.4（context_var） | ✓ |
| req11 mock 失败注入 | 3.1/3.4 | ✓ |
| req12 调试态可观测 | 2.4/3.4（duration/error/log_ref） | ✓ |
| req13 调试历史 | 2.5（history） | ✓ |
| req14 输入复用/元数据 | 1.3（input_schema）/2.3（last_inputs） | ✓ |

> 网关分支求值结果（req12 子项）：当前由 `get_task_states`/节点详情透出，前端经 `log_ref` 回查；后端未单独落库（spec 已将其归为复用任务详情接口的数据，非本计划新表字段）。

**2. 占位符扫描**：计划内代码均为可运行实现；标注「以实际接口为准 / 实现前 Read 校准」处为**对既有接口字段名的核对动作**（非代码占位），执行时按指示读取真实签名即可。`compute_can_step` 的 Phase 1 占位在 Task 3.3 已被真实实现替换。

**3. 类型一致性**：
- `log_ref` 结构统一为 `{"instance_id", "node_id", "version"}`（2.4 / 3.4 一致）。
- `error_detail` 统一为 `{"type", "message"}`。
- mock 物化 `mock_data` 结构统一为 `{"nodes", "outputs", "fail_nodes", "errors"}`（Interface 2.3 产出 ↔ Engine 2.1 消费 ↔ 引擎 3.1 读取一致）。
- 异常类型 `DebugConflictError`→409、`DebugStateError`→400 全程一致。
- `DebugService` 公有方法签名跨 Task 一致：`global_run/step_run/node_mock/set_context_var/reset/terminate/history/reset_impact/input_schema/build_context_view`。

**4. 执行前必读校准清单**（避免接口字段漂移）：
- `bkflow/contrib/api/collections/task.py`：`create_task` / `task_operate` / `task_node_operate` / `task_list` / `get_task_states` / `get_task_node_detail` 精确方法名与签名。
- `bkflow/task/operations.py`：`get_task_states` 子节点字段（state/elapsed_time/children）、`get_node_data` 的 outputs 结构。
- `bkflow/task/serializers.py`：create_task 入参字段（是否接收 `constants` / `mock_data` 子字段）。
- `bkflow/template/permissions.py`：`TemplateRelatedResourcePermission` 构造与 template_id 取值方式。
- `bkflow/template/urls.py`：router 变量名。

---

## 执行交接

**计划已保存到 `docs/plans/2026-06-25-debug-enhancement-redesign.md`。两种执行方式：**

1. **Subagent-Driven（推荐）** —— 每个 Task 派发独立子代理实现，Task 间双段 review，迭代快。REQUIRED SUB-SKILL: superpowers:subagent-driven-development。
2. **Inline Execution** —— 在本会话按计划批量执行，带检查点 review。REQUIRED SUB-SKILL: superpowers:executing-plans。

选哪种？
