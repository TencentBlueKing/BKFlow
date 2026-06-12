# BKFlow Engine Admin Prototype Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 `prototypes/` 为“页面类型母版库 + feature 跟进目录”模式，并基于真实审计结果深度重建 `bkflow_engine_admin` 原型集合。

**Architecture:** 保留 `prototypes/assets/` 作为共享样式与交互层，新增 `masters/` 作为长期页面类型真源，新增 `features/` 作为单次需求目录，`examples/` 收缩为工具参考。预览服务器改为以 `masters / features / examples` 为主要索引对象，首个 feature 用母版组合出完整的 `space / system / plugin` 原型链路，同时将旧 `examples/` 与 `output/` 内容迁入新结构或 `_legacy/`。

**Tech Stack:** HTML5, CSS3, Vanilla JavaScript, Python 3 stdlib preview server, pytest contract tests

**Spec:** `docs/specs/2026-04-21-bkflow-engine-admin-prototype-overhaul-design.md`

**Audit Baseline:** `.ai/docs/specs/bkflow-engine-admin-interaction-audit-2026-04-20.md`

**TAPD Story:** `133683187`

---

## 执行前提

- 使用独立 worktree，避免污染当前脏工作区：

```bash
cd /Users/dengyh/Projects/bk-flow
git fetch origin master
git worktree add .worktrees/bkflow-engine-admin-prototype-overhaul -b codex/bkflow-engine-admin-prototype-overhaul origin/master
```

- 后续所有实现、验证、提交都在新 worktree 中执行。
- commit message 统一追加 `--story=133683187`。
- 交互细节以真实审计文档为准，尤其是：
  - 流程编辑页的两段式保存、节点配置抽屉、全局变量、发布弹窗
  - 任务详情页的只读画布、节点详情、执行记录、配置快照、调用日志
  - 调试执行链路的确认弹窗与异常态

---

## 文件结构

| File | Action | Responsibility |
|---|---|---|
| `prototypes/README.md` | Modify | 说明新目录结构、预览入口、母版/feature 协作方式 |
| `prototypes/serve.py` | Modify | 根索引改为 `masters / features / examples`，兼容 `_legacy` 过渡内容 |
| `prototypes/assets/bkflow-prototype.css` | Modify | 新母版和 feature 共用的壳子、浮层、流程页、任务详情页样式 |
| `prototypes/assets/bkflow-prototype.js` | Modify | 新增导航组切换、通用 class toggle、局部状态切换等交互能力 |
| `prototypes/masters/README.md` | Create | 母版目录说明 |
| `prototypes/masters/_shared/README.md` | Create | 三套导航壳子说明 |
| `prototypes/masters/_shared/space-shell.html` | Create | 空间管理壳子 |
| `prototypes/masters/_shared/system-shell.html` | Create | 系统管理壳子 |
| `prototypes/masters/_shared/plugin-shell.html` | Create | 插件管理壳子 |
| `prototypes/masters/overlays/README.md` | Create | 浮层模式说明 |
| `prototypes/masters/overlays/dialogs.html` | Create | 确认弹窗 / 表单弹窗 / 异常弹窗示例 |
| `prototypes/masters/overlays/sidesliders.html` | Create | 右侧侧滑示例 |
| `prototypes/masters/list-page/README.md` | Create | 列表页母版说明 |
| `prototypes/masters/list-page/template.html` | Create | 列表页母版 |
| `prototypes/masters/list-page/states/*.html` | Create | 空态、异常态、批量态等 |
| `prototypes/masters/config-page/README.md` | Create | 长表单/代码编辑母版说明 |
| `prototypes/masters/config-page/template.html` | Create | 配置页母版 |
| `prototypes/masters/config-page/states/*.html` | Create | dirty / disabled / confirm 等状态 |
| `prototypes/masters/engine-panel/README.md` | Create | 调试面板母版说明 |
| `prototypes/masters/engine-panel/template.html` | Create | 调试面板母版 |
| `prototypes/masters/decision-editor/README.md` | Create | 决策表编辑页母版说明 |
| `prototypes/masters/decision-editor/template.html` | Create | 决策表编辑页母版 |
| `prototypes/masters/flow-editor/README.md` | Create | 流程编辑母版说明 |
| `prototypes/masters/flow-editor/template.html` | Create | 流程编辑母版主页面 |
| `prototypes/masters/flow-editor/states/*.html` | Create | 节点选中、保存可用、发布确认、调试确认等状态 |
| `prototypes/masters/task-detail/README.md` | Create | 任务详情母版说明 |
| `prototypes/masters/task-detail/template.html` | Create | 任务详情母版主页面 |
| `prototypes/masters/task-detail/states/*.html` | Create | 成功态、失败态、空日志态等 |
| `prototypes/features/README.md` | Create | feature 目录说明 |
| `prototypes/features/_legacy/README.md` | Create | 历史原型归档说明 |
| `prototypes/features/bkflow-engine-admin-prototype-overhaul/README.md` | Create | 本次 feature 说明与 spec/plan 回链 |
| `prototypes/features/bkflow-engine-admin-prototype-overhaul/CHANGELOG.md` | Create | feature 轻量变更记录 |
| `prototypes/features/bkflow-engine-admin-prototype-overhaul/index.html` | Create | feature 入口页 |
| `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/...` | Create | `space / system / plugin` 具体页面 |
| `prototypes/examples/README.md` | Create | examples 收缩后的用途说明 |
| `prototypes/examples/component-showcase.html` | Modify | 与新目录和资产约定保持一致 |
| `prototypes/examples/*.html` | Delete | 旧示例页迁入 `masters/` 后移除 |
| `prototypes/base.html` | Delete | 由 `_shared/` 三套壳子替代 |
| `prototypes/output/*` | Move/Delete | 历史产物迁入 `features/` 或 `_legacy/`，不再作为主产出 |
| `prototypes/cache/` | Delete | 删除未启用的空占位目录 |
| `prototypes/metadata/` | Delete | 删除未启用的空占位目录 |
| `prototypes/renderers/` | Delete | 删除未启用的空占位目录 |
| `.ai/skills/prototype-generator/SKILL.md` | Modify | 输出目标改为 `masters/features` 结构，移除对 `base.html` + 扁平 `output/` 的强绑定 |
| `tests/interface/prototypes/__init__.py` | Create | prototype 测试包 |
| `tests/interface/prototypes/test_serve.py` | Create | 预览服务器索引与 mtime 合同测试 |
| `tests/interface/prototypes/test_structure_contract.py` | Create | 新目录和 README 合同测试 |
| `tests/interface/prototypes/test_master_contract.py` | Create | 母版文件和关键 DOM 标记测试 |
| `tests/interface/prototypes/test_flow_editor_contract.py` | Create | 流程编辑母版深度合同测试 |
| `tests/interface/prototypes/test_task_detail_contract.py` | Create | 任务详情母版深度合同测试 |
| `tests/interface/prototypes/test_bkflow_engine_admin_feature.py` | Create | 首个 feature 页面清单与入口测试 |

---

### Task 1: 预览服务器与根索引切到新结构

**Files:**
- Create: `tests/interface/prototypes/__init__.py`
- Create: `tests/interface/prototypes/test_serve.py`
- Modify: `prototypes/serve.py`
- Modify: `prototypes/README.md`

- [ ] **Step 1: 写预览服务器失败测试**

创建 `tests/interface/prototypes/test_serve.py`，至少覆盖两个约束：

```python
from pathlib import Path
import importlib.util


def _load_serve():
    path = Path("prototypes/serve.py")
    spec = importlib.util.spec_from_file_location("prototype_serve", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_list_html_files_groups_new_sections(tmp_path, monkeypatch):
    serve = _load_serve()
    for section in ["masters", "features", "examples"]:
        root = tmp_path / section
        root.mkdir()
        (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
        monkeypatch.setattr(serve, f"{section.upper()}_DIR", str(root))

    items = serve.list_html_files()
    sections = {section for section, _ in items}
    assert "masters" in sections
    assert "features" in sections
    assert "examples" in sections


def test_latest_mtime_scans_new_roots(tmp_path, monkeypatch):
    serve = _load_serve()
    for section in ["masters", "features", "examples"]:
        root = tmp_path / section
        root.mkdir(exist_ok=True)
        (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
        monkeypatch.setattr(serve, f"{section.upper()}_DIR", str(root))

    mtime = serve.latest_mtime_under((serve.MASTERS_DIR, serve.FEATURES_DIR, serve.EXAMPLES_DIR))
    assert isinstance(mtime, float)
```

- [ ] **Step 2: 跑测试，确认当前实现失败**

Run: `pytest tests/interface/prototypes/test_serve.py -v`  
Expected: FAIL，因为当前 `serve.py` 仍只索引 `output/` 和 `examples/`。

- [ ] **Step 3: 改造 `prototypes/serve.py`**

实现以下行为：
- 增加 `MASTERS_DIR`、`FEATURES_DIR`
- `/` 根索引按 section 分组展示 `masters / features / examples`
- `output/` 仅作为过渡区展示，若为空则不作为主 section
- `/api/mtime` 轮询范围扩展到 `masters / features / examples / assets`
- 保留 HTML 自动注入 reload 脚本能力

- [ ] **Step 4: 更新 `prototypes/README.md` 的目录说明和启动说明**

明确写出：
- `masters/` 是长期真源
- `features/` 是单次需求目录
- `examples/` 只保留组件参考
- 根索引的推荐预览路径

- [ ] **Step 5: 重新跑测试和基础检查**

Run:

```bash
pytest tests/interface/prototypes/test_serve.py -v
python -m py_compile prototypes/serve.py
```

Expected:
- pytest 全绿
- `py_compile` 无报错

- [ ] **Step 6: Commit**

```bash
git add prototypes/serve.py prototypes/README.md tests/interface/prototypes/__init__.py tests/interface/prototypes/test_serve.py
git commit -m "feat(prototypes): 调整预览服务器以支持 masters 和 features --story=133683187"
```

---

### Task 2: 搭起新目录骨架与目录合同测试

**Files:**
- Create: `tests/interface/prototypes/test_structure_contract.py`
- Create: `prototypes/masters/README.md`
- Create: `prototypes/masters/_shared/README.md`
- Create: `prototypes/features/README.md`
- Create: `prototypes/features/_legacy/README.md`
- Create: `prototypes/examples/README.md`

- [ ] **Step 1: 写目录合同失败测试**

在 `tests/interface/prototypes/test_structure_contract.py` 中至少覆盖：

```python
from pathlib import Path


def test_required_root_directories_exist():
    required = [
        "prototypes/masters",
        "prototypes/features",
        "prototypes/examples",
    ]
    for path in required:
        assert Path(path).exists(), path


def test_required_readmes_exist():
    required = [
        "prototypes/masters/README.md",
        "prototypes/masters/_shared/README.md",
        "prototypes/features/README.md",
        "prototypes/features/_legacy/README.md",
        "prototypes/examples/README.md",
    ]
    for path in required:
        assert Path(path).is_file(), path
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_structure_contract.py -v`  
Expected: FAIL，因为新目录和 README 还不存在。

- [ ] **Step 3: 创建新目录与 README**

创建：
- `prototypes/masters/`
- `prototypes/masters/_shared/`
- `prototypes/features/`
- `prototypes/features/_legacy/`
- `prototypes/examples/README.md`

README 内容至少说明：
- 目录目的
- 什么该放、什么不该放
- 与 `docs/specs/` / `docs/plans/` 的关系

- [ ] **Step 4: 在 `prototypes/README.md` 中补充目录树**

将根 README 的目录结构更新为新版本，避免文档和真实结构脱节。

- [ ] **Step 5: 跑测试**

Run: `pytest tests/interface/prototypes/test_structure_contract.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add prototypes/README.md prototypes/masters/README.md prototypes/masters/_shared/README.md prototypes/features/README.md prototypes/features/_legacy/README.md prototypes/examples/README.md tests/interface/prototypes/test_structure_contract.py
git commit -m "feat(prototypes): 初始化新目录骨架与结构合同 --story=133683187"
```

---

### Task 3: 共享壳子、浮层体系与资产能力升级

**Files:**
- Modify: `prototypes/assets/bkflow-prototype.css`
- Modify: `prototypes/assets/bkflow-prototype.js`
- Create: `prototypes/masters/_shared/space-shell.html`
- Create: `prototypes/masters/_shared/system-shell.html`
- Create: `prototypes/masters/_shared/plugin-shell.html`
- Create: `prototypes/masters/overlays/README.md`
- Create: `prototypes/masters/overlays/dialogs.html`
- Create: `prototypes/masters/overlays/sidesliders.html`
- Create: `tests/interface/prototypes/test_master_contract.py`

- [ ] **Step 1: 写共享壳子失败测试**

在 `tests/interface/prototypes/test_master_contract.py` 中先写最小合同：

```python
from pathlib import Path


def test_shared_shells_exist():
    for path in [
        "prototypes/masters/_shared/space-shell.html",
        "prototypes/masters/_shared/system-shell.html",
        "prototypes/masters/_shared/plugin-shell.html",
    ]:
        assert Path(path).is_file(), path


def test_overlays_examples_exist():
    for path in [
        "prototypes/masters/overlays/dialogs.html",
        "prototypes/masters/overlays/sidesliders.html",
    ]:
        assert Path(path).is_file(), path
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_master_contract.py -v`  
Expected: FAIL

- [ ] **Step 3: 创建三套共享壳子**

壳子要求：
- 共享顶栏结构，但一级导航状态不同
- `space-shell.html` 带空间选择区与空间侧栏
- `system-shell.html` 带系统管理侧栏
- `plugin-shell.html` 带插件侧栏
- 页面只保留壳子和占位内容，不混入具体业务表格

- [ ] **Step 4: 创建浮层母版**

`dialogs.html` 至少包含：
- 删除确认弹窗
- 发布确认弹窗
- 异常提示弹窗

`sidesliders.html` 至少包含：
- 表单编辑侧滑
- 只读详情侧滑

- [ ] **Step 5: 升级共享 CSS/JS**

只补“多页面都要用”的通用能力：
- 导航组切换
- 通用 `data-toggle-target` / `data-toggle-class`
- 右侧面板开合
- 保存按钮从禁用到可用的 class 切换

不要把 feature 级业务逻辑塞进共享 JS。

- [ ] **Step 6: 跑测试和预览 smoke test**

Run:

```bash
pytest tests/interface/prototypes/test_master_contract.py -v
python prototypes/serve.py --port 9080 >/tmp/bkflow-prototypes.log 2>&1 &
sleep 2
curl -s http://localhost:9080/ | rg "masters|features|examples"
pkill -f "prototypes/serve.py --port 9080" || true
```

Expected:
- pytest 通过
- 根索引能看到 `masters`

- [ ] **Step 7: Commit**

```bash
git add prototypes/assets/bkflow-prototype.css prototypes/assets/bkflow-prototype.js prototypes/masters/_shared/ prototypes/masters/overlays/ tests/interface/prototypes/test_master_contract.py
git commit -m "feat(prototypes): 建立共享壳子与浮层母版 --story=133683187"
```

---

### Task 4: 落地中复杂度母版

**Files:**
- Create: `prototypes/masters/list-page/README.md`
- Create: `prototypes/masters/list-page/template.html`
- Create: `prototypes/masters/list-page/states/empty.html`
- Create: `prototypes/masters/list-page/states/error.html`
- Create: `prototypes/masters/list-page/states/bulk-actions.html`
- Create: `prototypes/masters/config-page/README.md`
- Create: `prototypes/masters/config-page/template.html`
- Create: `prototypes/masters/config-page/states/dirty.html`
- Create: `prototypes/masters/engine-panel/README.md`
- Create: `prototypes/masters/engine-panel/template.html`
- Create: `prototypes/masters/decision-editor/README.md`
- Create: `prototypes/masters/decision-editor/template.html`
- Modify: `tests/interface/prototypes/test_master_contract.py`

- [ ] **Step 1: 扩展母版合同测试**

为每类母版补文件和关键标记断言，例如：

```python
def test_list_page_template_contains_toolbar_and_table():
    html = Path("prototypes/masters/list-page/template.html").read_text(encoding="utf-8")
    assert "bk-toolbar" in html
    assert "bk-table" in html


def test_config_page_template_contains_form_and_save_bar():
    html = Path("prototypes/masters/config-page/template.html").read_text(encoding="utf-8")
    assert "bk-form" in html
    assert "保存" in html
```

- [ ] **Step 2: 跑测试，确认新增断言失败**

Run: `pytest tests/interface/prototypes/test_master_contract.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现 `list-page` 母版**

要求：
- 顶部工具栏
- 搜索/筛选
- 状态列
- 操作列
- 分页
- 空态 / 异常态 / 批量操作态

- [ ] **Step 4: 实现 `config-page`、`engine-panel`、`decision-editor` 母版**

分别覆盖：
- 配置页：长表单、代码块、保存禁用态、dirty 态
- 调试面板：请求区、响应区、发送/重置按钮
- 决策编辑：基础信息、规则区、空态、底部操作区

- [ ] **Step 5: 跑测试**

Run: `pytest tests/interface/prototypes/test_master_contract.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add prototypes/masters/list-page prototypes/masters/config-page prototypes/masters/engine-panel prototypes/masters/decision-editor tests/interface/prototypes/test_master_contract.py
git commit -m "feat(prototypes): 增加列表页与配置类母版 --story=133683187"
```

---

### Task 5: 实现流程编辑深度母版

**Files:**
- Create: `prototypes/masters/flow-editor/README.md`
- Create: `prototypes/masters/flow-editor/template.html`
- Create: `prototypes/masters/flow-editor/states/node-selected.html`
- Create: `prototypes/masters/flow-editor/states/save-ready.html`
- Create: `prototypes/masters/flow-editor/states/publish-confirm.html`
- Create: `prototypes/masters/flow-editor/states/mock-debug-confirm.html`
- Create: `tests/interface/prototypes/test_flow_editor_contract.py`
- Modify: `prototypes/assets/bkflow-prototype.css`
- Modify: `prototypes/assets/bkflow-prototype.js`

- [ ] **Step 1: 写流程编辑母版失败测试**

创建 `tests/interface/prototypes/test_flow_editor_contract.py`：

```python
from pathlib import Path


def test_flow_editor_template_has_required_regions():
    html = Path("prototypes/masters/flow-editor/template.html").read_text(encoding="utf-8")
    assert "流程编辑" in html or "flow-editor" in html
    assert "全局变量" in html
    assert "发布" in html
    assert "保存" in html


def test_flow_editor_state_pages_exist():
    for path in [
        "prototypes/masters/flow-editor/states/node-selected.html",
        "prototypes/masters/flow-editor/states/save-ready.html",
        "prototypes/masters/flow-editor/states/publish-confirm.html",
        "prototypes/masters/flow-editor/states/mock-debug-confirm.html",
    ]:
        assert Path(path).is_file(), path
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_flow_editor_contract.py -v`  
Expected: FAIL

- [ ] **Step 3: 基于真实审计实现主母版**

`template.html` 至少覆盖：
- 流程标题、版本区、返回入口
- 画布区、节点悬浮工具条
- 节点配置抽屉
- 全局变量入口
- 顶部保存 / 发布 / 调试入口

- [ ] **Step 4: 用状态页拆出关键状态机**

状态页必须分别体现：
- 节点选中后出现配置工具条
- 节点抽屉点“确定”后顶部“保存”变可用
- 发布前确认弹窗
- 调试执行前确认弹窗

- [ ] **Step 5: 用最少共享 JS 支撑状态切换**

只实现可复用的状态切换：
- 节点选中 -> 打开抽屉
- 确认配置 -> 顶部保存按钮可用
- 发布 / 调试 -> 弹出确认层

- [ ] **Step 6: 跑测试与手工 smoke**

Run:

```bash
pytest tests/interface/prototypes/test_flow_editor_contract.py -v
python prototypes/serve.py --port 9080 >/tmp/bkflow-prototypes.log 2>&1 &
sleep 2
curl -s http://localhost:9080/masters/flow-editor/template.html | head -n 5
pkill -f "prototypes/serve.py --port 9080" || true
```

Expected:
- pytest 通过
- 页面可被服务到

- [ ] **Step 7: Commit**

```bash
git add prototypes/masters/flow-editor prototypes/assets/bkflow-prototype.css prototypes/assets/bkflow-prototype.js tests/interface/prototypes/test_flow_editor_contract.py
git commit -m "feat(prototypes): 落地流程编辑深度母版 --story=133683187"
```

---

### Task 6: 实现任务详情深度母版

**Files:**
- Create: `prototypes/masters/task-detail/README.md`
- Create: `prototypes/masters/task-detail/template.html`
- Create: `prototypes/masters/task-detail/states/complete.html`
- Create: `prototypes/masters/task-detail/states/failed.html`
- Create: `prototypes/masters/task-detail/states/empty-log.html`
- Create: `tests/interface/prototypes/test_task_detail_contract.py`
- Modify: `prototypes/assets/bkflow-prototype.css`
- Modify: `prototypes/assets/bkflow-prototype.js`

- [ ] **Step 1: 写任务详情母版失败测试**

创建 `tests/interface/prototypes/test_task_detail_contract.py`：

```python
from pathlib import Path


def test_task_detail_template_has_required_tabs():
    html = Path("prototypes/masters/task-detail/template.html").read_text(encoding="utf-8")
    for label in ["执行记录", "配置快照", "操作历史", "调用日志"]:
        assert label in html


def test_task_detail_states_exist():
    for path in [
        "prototypes/masters/task-detail/states/complete.html",
        "prototypes/masters/task-detail/states/failed.html",
        "prototypes/masters/task-detail/states/empty-log.html",
    ]:
        assert Path(path).is_file(), path
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_task_detail_contract.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现 `task-detail` 主母版**

要求：
- 执行态页头
- 模板回链
- 只读画布
- 点击节点打开详情
- 右侧详情 / 变量 / 记录面板

- [ ] **Step 4: 用状态页覆盖关键执行结果**

分别体现：
- 成功态
- 失败态
- 调用日志为空态

- [ ] **Step 5: 跑测试**

Run: `pytest tests/interface/prototypes/test_task_detail_contract.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add prototypes/masters/task-detail prototypes/assets/bkflow-prototype.css prototypes/assets/bkflow-prototype.js tests/interface/prototypes/test_task_detail_contract.py
git commit -m "feat(prototypes): 落地任务详情深度母版 --story=133683187"
```

---

### Task 7: 用母版拼出首个 feature

**Files:**
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/README.md`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/CHANGELOG.md`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/index.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/template-list.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/flow-view.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/flow-edit.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/flow-debug.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/task-list.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/debug-task-list.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/task-detail-complete.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/task-detail-failed.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/decision-list.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/decision-editor.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/space-config.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/credential-list.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/label-list.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/statistics-exception.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/system/space-config-list.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/system/module-config-list.html`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/plugin/plugin-list.html`
- Create: `tests/interface/prototypes/test_bkflow_engine_admin_feature.py`

- [ ] **Step 1: 写 feature 页面清单失败测试**

创建 `tests/interface/prototypes/test_bkflow_engine_admin_feature.py`，至少覆盖：

```python
from pathlib import Path


FEATURE_ROOT = Path("prototypes/features/bkflow-engine-admin-prototype-overhaul")


def test_feature_docs_exist_and_link_spec_plan():
    readme = (FEATURE_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/specs/2026-04-21-bkflow-engine-admin-prototype-overhaul-design.md" in readme
    assert "docs/plans/2026-04-21-bkflow-engine-admin-prototype-overhaul.md" in readme


def test_feature_pages_exist():
    required = [
        FEATURE_ROOT / "pages/space/flow-edit.html",
        FEATURE_ROOT / "pages/space/task-detail-complete.html",
        FEATURE_ROOT / "pages/system/module-config-list.html",
        FEATURE_ROOT / "pages/plugin/plugin-list.html",
    ]
    for path in required:
        assert path.is_file(), path
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_bkflow_engine_admin_feature.py -v`  
Expected: FAIL

- [ ] **Step 3: 创建 feature 文档和入口**

`README.md` 必须包含：
- spec 路径
- plan 路径
- 使用到的母版
- 页面入口清单

`index.html` 必须按 `space / system / plugin` 分组列出所有页面入口。

- [ ] **Step 4: 逐页落成首个 feature**

按真实审计优先级处理：
- 先 `template-list / flow-view / flow-edit / flow-debug`
- 再 `task-list / debug-task-list / task-detail-*`
- 最后 `decision-* / space-config / credential / label / statistics / system / plugin`

每个页面都必须：
- 使用正确的相对路径引用 `assets`：
  - `index.html` 使用 `../../assets/...`
  - `pages/space/*.html`、`pages/system/*.html`、`pages/plugin/*.html` 使用 `../../../../assets/...`
- 保持导航高亮正确
- 体现对应页面的关键状态

- [ ] **Step 5: 跑测试和入口检查**

Run:

```bash
pytest tests/interface/prototypes/test_bkflow_engine_admin_feature.py -v
python prototypes/serve.py --port 9080 >/tmp/bkflow-prototypes.log 2>&1 &
sleep 2
curl -s http://localhost:9080/ | rg "bkflow-engine-admin-prototype-overhaul"
pkill -f "prototypes/serve.py --port 9080" || true
```

Expected:
- pytest 通过
- 根索引能看到该 feature

- [ ] **Step 6: Commit**

```bash
git add prototypes/features/bkflow-engine-admin-prototype-overhaul tests/interface/prototypes/test_bkflow_engine_admin_feature.py
git commit -m "feat(prototypes): 交付 bkflow engine admin 首个 feature 原型集 --story=133683187"
```

---

### Task 8: 迁移历史内容并更新原型生成约定

**Files:**
- Modify: `.ai/skills/prototype-generator/SKILL.md`
- Modify: `prototypes/examples/component-showcase.html`
- Delete: `prototypes/base.html`
- Delete: `prototypes/examples/composite-page.html`
- Delete: `prototypes/examples/detail-page.html`
- Delete: `prototypes/examples/flow-edit.html`
- Delete: `prototypes/examples/form-slider.html`
- Delete: `prototypes/examples/list-page.html`
- Delete: `prototypes/examples/tab-page.html`
- Delete: `prototypes/examples/task-detail.html`
- Delete: `prototypes/cache/`
- Delete: `prototypes/metadata/`
- Delete: `prototypes/renderers/`
- Move/Create: `prototypes/features/_legacy/sops-open-plugin/*`
- Move/Create: `prototypes/features/_legacy/space-variable-manage/*`
- Move/Create: `prototypes/features/_legacy/node-output-viewer/*`
- Delete/Deprecate: `prototypes/output/*`
- Modify: `tests/interface/prototypes/test_structure_contract.py`

- [ ] **Step 1: 扩展结构合同，约束 examples/output 的新职责**

在 `tests/interface/prototypes/test_structure_contract.py` 增加断言：
- `examples/` 只保留 `README.md` 和 `component-showcase.html`
- `base.html` 不再存在
- `cache/ metadata/ renderers` 不再存在
- 历史 output 页面迁入 `features/_legacy/`

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_structure_contract.py -v`  
Expected: FAIL

- [ ] **Step 3: 迁移旧 examples 与 output**

迁移策略：
- 旧 `examples/*.html` 对应吸收进 `masters/`
- `output/sops-open-plugin-*.html` 迁入 `prototypes/features/_legacy/sops-open-plugin/`
- `output/space-variable-manage.html` 迁入 `prototypes/features/_legacy/space-variable-manage/`
- `output/node-output-viewer-proposal-v1.html` 迁入 `prototypes/features/_legacy/node-output-viewer/`

- [ ] **Step 4: 删除 `base.html` 并更新 skill**

`.ai/skills/prototype-generator/SKILL.md` 需要同步：
- 生成目标从 `output/<name>.html` 改为 `features/<slug>/...`
- 不再要求先读 `base.html`
- 生成时优先复用 `masters/`
- 历史/临时页面才进入 `_legacy`

- [ ] **Step 5: 跑完整 prototype 测试集合**

Run:

```bash
pytest tests/interface/prototypes -v
python -m py_compile prototypes/serve.py
```

Expected:
- `tests/interface/prototypes` 全绿
- `py_compile` 通过

- [ ] **Step 6: Commit**

```bash
git add .ai/skills/prototype-generator/SKILL.md prototypes tests/interface/prototypes
git commit -m "refactor(prototypes): 迁移历史原型并更新新结构约定 --story=133683187"
```

---

## 完成检查

全部任务完成后，再做一次完整验证：

```bash
pytest tests/interface/prototypes -v
python -m py_compile prototypes/serve.py
python prototypes/serve.py --port 9080 >/tmp/bkflow-prototypes.log 2>&1 &
sleep 2
curl -s http://localhost:9080/ | rg "masters|features|examples|bkflow-engine-admin-prototype-overhaul"
pkill -f "prototypes/serve.py --port 9080" || true
```

Expected:
- prototype 测试全绿
- 预览服务器可启动
- 根索引能看到 `masters / features / examples`
- 首个 feature 可从根索引进入

## 交付标准

- `prototypes/` 根目录第一次打开即可分清母版、feature、示例
- `flow-editor` 与 `task-detail` 母版明确分离，且均带关键状态页
- `bkflow-engine-admin-prototype-overhaul` 覆盖 `space / system / plugin` 核心页面
- 历史原型不再堆在扁平 `output/`
- `prototype-generator` skill 与新目录结构一致

## 人工审阅提示

执行实现时，优先看以下页面是否真正“做深做准”：
- `prototypes/masters/flow-editor/template.html`
- `prototypes/masters/task-detail/template.html`
- `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/flow-edit.html`
- `prototypes/features/bkflow-engine-admin-prototype-overhaul/pages/space/task-detail-complete.html`
