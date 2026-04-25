# Prototype Showcase Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `prototypes/` 根首页从路径列表页升级为中文原型展厅首页，以 `features/` 为主入口展示成套原型，并支持代码生成封面、搜索筛选和弱化的工具资源区。

**Architecture:** 保留 `prototypes/serve.py` 作为静态预览服务器和根路由入口，但把 feature 元数据收集与降级逻辑拆到新的 `prototypes/showcase_catalog.py` 中，使首页数据契约可测试、可演进。首页视觉和轻交互通过新增的 `prototypes/assets/bkflow-showcase.css` 与 `prototypes/assets/bkflow-showcase.js` 承接；每个 feature 通过 `feature.meta.json` 提供中文标题、摘要、封面主题和代表页信息，`masters/examples` 只在首页底部资源区以轻入口形式出现。

**Tech Stack:** Python 3 stdlib preview server, HTML5, CSS3, Vanilla JavaScript, JSON metadata, pytest contract tests

**Spec:** `docs/specs/2026-04-22-prototype-showcase-homepage-design.md`

**Related Baseline:** `prototypes/features/bkflow-engine-admin-prototype-overhaul/index.html`

**TAPD Story:** `133683187`

---

## 执行前提

- 所有修改都在 worktree `/Users/dengyh/Projects/bk-flow/.worktrees/bkflow-engine-admin-prototype-overhaul` 内完成。
- 验证命令统一优先使用当前 worktree 的虚拟环境：

```bash
cd /Users/dengyh/Projects/bk-flow/.worktrees/bkflow-engine-admin-prototype-overhaul
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django tests/interface/prototypes -v
```

- Python 语法兼容性必须对齐 CI 的 Python 3.9：

```bash
python3.9 -m py_compile prototypes/serve.py prototypes/showcase_catalog.py
```

- commit message 统一追加 `--story=133683187`。

---

## 文件结构

| File | Action | Responsibility |
|---|---|---|
| `prototypes/showcase_catalog.py` | Create | 解析 `features/<slug>/feature.meta.json`，汇总首页展厅所需数据，并实现缺失元数据时的降级逻辑 |
| `prototypes/serve.py` | Modify | 用展厅首页替换根路径列表页，渲染 Hero、Feature 卡片、代表页面和资源区，同时保留已有 mtime / HTML reload 逻辑 |
| `prototypes/assets/bkflow-showcase.css` | Create | 承接首页 Hero、展厅卡片、封面主题、资源区、响应式布局的专用样式 |
| `prototypes/assets/bkflow-showcase.js` | Create | 承接首页搜索、筛选和空结果提示的轻交互 |
| `prototypes/features/bkflow-engine-admin-prototype-overhaul/feature.meta.json` | Create | 为现有 feature 提供首页展示所需的中文标题、摘要、封面主题和代表页面信息 |
| `prototypes/features/README.md` | Modify | 说明 `feature.meta.json` 的职责、字段和新增 feature 时的维护要求 |
| `prototypes/README.md` | Modify | 更新首页定位、快速开始和元数据约定，说明根路径已升级为展厅首页 |
| `.ai/skills/prototype-generator/SKILL.md` | Modify | 将“新增 feature 时同步创建/更新 `feature.meta.json`”写入工具使用规则 |
| `tests/interface/prototypes/test_showcase_catalog.py` | Create | 覆盖 feature 元数据解析、降级、代表页选择和排序逻辑 |
| `tests/interface/prototypes/test_showcase_homepage.py` | Create | 覆盖根首页的 Hero、Feature 卡片、代表页面、资源区和交互 data hooks |
| `tests/interface/prototypes/test_structure_contract.py` | Modify | 增加 `feature.meta.json` 与首页静态资源的存在性合同 |

---

### Task 1: 建立首页元数据契约和 catalog 解析层

**Files:**
- Create: `tests/interface/prototypes/test_showcase_catalog.py`
- Create: `prototypes/showcase_catalog.py`
- Create: `prototypes/features/bkflow-engine-admin-prototype-overhaul/feature.meta.json`
- Modify: `prototypes/features/README.md`

- [ ] **Step 1: 写 catalog 失败测试**

在 `tests/interface/prototypes/test_showcase_catalog.py` 中新增至少 2 组测试，明确“有元数据”和“无元数据回退”两条路径：

```python
import importlib.util
import json
from pathlib import Path


def _load_catalog():
    path = Path("prototypes/showcase_catalog.py")
    spec = importlib.util.spec_from_file_location("prototype_showcase_catalog", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_collect_feature_catalog_reads_meta_and_featured_pages(tmp_path):
    catalog = _load_catalog()
    feature_dir = tmp_path / "features" / "demo-feature"
    pages_dir = feature_dir / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "flow-edit.html").write_text("<html></html>", encoding="utf-8")
    (pages_dir / "task-detail.html").write_text("<html></html>", encoding="utf-8")
    (feature_dir / "feature.meta.json").write_text(
        json.dumps(
            {
                "title": "示例原型",
                "summary": "覆盖流程编辑与任务详情。",
                "status": "可评审",
                "tags": ["流程编辑", "任务详情"],
                "coverTheme": "mixed-admin",
                "featuredPages": [
                    {
                        "path": "pages/flow-edit.html",
                        "title": "流程编辑页",
                        "summary": "画布与节点抽屉。",
                        "pageType": "流程编辑",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    items = catalog.collect_feature_catalog(str(tmp_path / "features"))

    assert items[0]["title"] == "示例原型"
    assert items[0]["status"] == "可评审"
    assert items[0]["cover_theme"] == "mixed-admin"
    assert items[0]["page_count"] == 2
    assert items[0]["featured_pages"][0]["title"] == "流程编辑页"


def test_collect_feature_catalog_falls_back_when_meta_missing(tmp_path):
    catalog = _load_catalog()
    feature_dir = tmp_path / "features" / "demo-fallback"
    pages_dir = feature_dir / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "alpha.html").write_text("<html></html>", encoding="utf-8")
    (pages_dir / "beta.html").write_text("<html></html>", encoding="utf-8")

    items = catalog.collect_feature_catalog(str(tmp_path / "features"))

    assert items[0]["slug"] == "demo-fallback"
    assert items[0]["status"] == "待补充"
    assert items[0]["cover_theme"] == "mixed-admin"
    assert len(items[0]["featured_pages"]) == 2
```

- [ ] **Step 2: 跑测试，确认当前失败**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django tests/interface/prototypes/test_showcase_catalog.py -v
```

Expected:
- `test_showcase_catalog.py` 报错，因为 `prototypes/showcase_catalog.py` 尚不存在

- [ ] **Step 3: 实现 `prototypes/showcase_catalog.py` 的最小 catalog 解析**

实现以下具体函数，而不是把逻辑全部堆进 `serve.py`：

```python
DEFAULT_STATUS = "待补充"
DEFAULT_SUMMARY = "尚未补充首页摘要"
DEFAULT_THEME = "mixed-admin"


def collect_feature_catalog(features_dir: str) -> list[dict]:
    ...


def collect_showcase_stats(features_dir: str, masters_dir: str) -> dict:
    ...
```

最小实现要求：
- 扫描 `features/` 下的一级 feature 目录，跳过 `_legacy`
- 统计该 feature 下全部 `.html` 页面数
- 读取 `feature.meta.json`，并规范化字段名为首页渲染所需字段
- 元数据缺失时回退到默认 `summary / status / coverTheme`
- 无效 `featuredPages.path` 自动跳过
- 默认按 `order` 升序、更新时间降序排序

- [ ] **Step 4: 为现有 feature 补真实元数据，并同步目录说明**

新增 `prototypes/features/bkflow-engine-admin-prototype-overhaul/feature.meta.json`，至少包含：

```json
{
  "title": "BKFlow 引擎管理后台原型重构",
  "summary": "覆盖 Space / System / Plugin 三个入口，包含流程、任务、决策与配置链路。",
  "status": "可评审",
  "tags": ["流程编辑", "任务详情", "系统配置"],
  "coverTheme": "mixed-admin",
  "order": 10,
  "featuredPages": [
    {
      "path": "pages/space/flow-edit.html",
      "title": "流程编辑页",
      "summary": "画布编排、节点抽屉与两段式保存。",
      "pageType": "流程编辑"
    },
    {
      "path": "pages/space/task-detail-complete.html",
      "title": "任务详情页",
      "summary": "执行状态、节点观察与日志查看。",
      "pageType": "任务详情"
    }
  ]
}
```

同时更新 `prototypes/features/README.md`，明确：
- `feature.meta.json` 是首页展示契约
- README 继续承担说明文档职责
- 新增 feature 时需要同步维护两者

- [ ] **Step 5: 重新跑 catalog 测试**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django tests/interface/prototypes/test_showcase_catalog.py -v
python3.9 -m py_compile prototypes/showcase_catalog.py
```

Expected:
- pytest 全绿
- `py_compile` 无语法报错

- [ ] **Step 6: Commit**

```bash
git add prototypes/showcase_catalog.py \
  prototypes/features/README.md \
  prototypes/features/bkflow-engine-admin-prototype-overhaul/feature.meta.json \
  tests/interface/prototypes/test_showcase_catalog.py
git commit -m "feat(prototypes): 增加首页展厅元数据契约 --story=133683187"
```

---

### Task 2: 用展厅布局替换根首页的路径列表

**Files:**
- Create: `tests/interface/prototypes/test_showcase_homepage.py`
- Modify: `prototypes/serve.py`
- Modify: `prototypes/README.md`

- [ ] **Step 1: 写首页结构失败测试**

在 `tests/interface/prototypes/test_showcase_homepage.py` 中创建一组基于临时目录的服务器测试，覆盖中文 Hero、统计信息、最近更新、Feature 卡片、代表页面和资源区：

```python
import importlib.util
import json
import threading
from contextlib import contextmanager
from http.server import HTTPServer
from pathlib import Path
from urllib.request import urlopen


def _load_serve():
    path = Path("prototypes/serve.py")
    spec = importlib.util.spec_from_file_location("prototype_serve", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@contextmanager
def _run_server(serve):
    server = HTTPServer(("127.0.0.1", 0), serve.PrototypeRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_root_index_renders_showcase_sections(tmp_path, monkeypatch):
    serve = _load_serve()
    root = tmp_path / "prototypes"
    features = root / "features" / "demo-feature"
    masters = root / "masters" / "flow-editor"
    examples = root / "examples"
    assets = root / "assets"
    (features / "pages").mkdir(parents=True)
    masters.mkdir(parents=True)
    examples.mkdir(parents=True)
    assets.mkdir(parents=True)
    (features / "index.html").write_text("<html></html>", encoding="utf-8")
    (features / "pages" / "flow-edit.html").write_text("<html></html>", encoding="utf-8")
    (features / "feature.meta.json").write_text(
        json.dumps(
            {
                "title": "示例原型",
                "summary": "覆盖流程编辑。",
                "status": "可评审",
                "coverTheme": "flow-editor",
                "featuredPages": [
                    {
                        "path": "pages/flow-edit.html",
                        "title": "流程编辑页",
                        "summary": "画布编排。",
                        "pageType": "流程编辑"
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(serve, "PROTOTYPES_ROOT", str(root))
    monkeypatch.setattr(serve, "FEATURES_DIR", str(root / "features"))
    monkeypatch.setattr(serve, "MASTERS_DIR", str(root / "masters"))
    monkeypatch.setattr(serve, "EXAMPLES_DIR", str(root / "examples"))
    monkeypatch.setattr(serve, "ASSETS_DIR", str(root / "assets"))

    with _run_server(serve) as base_url:
        body = urlopen(base_url).read().decode("utf-8")

    assert "BKFlow 原型展厅" in body
    assert "示例原型" in body
    assert "最近更新" in body
    assert "代表页面" in body
    assert "工具资源" in body
    assert "查看这组原型" in body
```

- [ ] **Step 2: 跑首页测试，确认当前失败**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django tests/interface/prototypes/test_showcase_homepage.py -v
```

Expected:
- FAIL，因为根首页目前仍是英文路径列表页

- [ ] **Step 3: 改造 `prototypes/serve.py` 的根路径渲染**

把 `/` 的渲染方式替换为展厅首页，并保证其职责清晰：

```python
from showcase_catalog import collect_feature_catalog, collect_showcase_stats


def _send_index(self) -> None:
    feature_items = collect_feature_catalog(FEATURES_DIR)
    stats = collect_showcase_stats(FEATURES_DIR, MASTERS_DIR)
    body = render_showcase_homepage(
        feature_items=feature_items,
        stats=stats,
        masters_dir=MASTERS_DIR,
        examples_dir=EXAMPLES_DIR,
    )
    ...
```

首页 HTML 结构至少包含：
- Hero 首屏
- 统计信息条
- 最近更新区
- Feature 展区
- 代表页面区
- 工具资源区

同时要移除当前这种主布局：

```html
<h2>masters</h2>
<ul>
  <li><a href="/masters/...">...</a></li>
</ul>
```

它可以退化为资源区内部的轻量链接，但不能再是首页主体。

- [ ] **Step 4: 更新 `prototypes/README.md` 的首页说明**

把 README 中的“浏览器预览”改成展厅式入口描述，明确：
- 根路径是中文展厅首页
- `features` 是首页主角
- `masters/examples` 是底部资源区

- [ ] **Step 5: 跑首页测试和已有服务器测试**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django \
  tests/interface/prototypes/test_showcase_homepage.py \
  tests/interface/prototypes/test_serve.py -v
python3.9 -m py_compile prototypes/serve.py prototypes/showcase_catalog.py
```

Expected:
- 新旧服务器相关测试都为 PASS
- `py_compile` 无报错

- [ ] **Step 6: Commit**

```bash
git add prototypes/serve.py prototypes/README.md tests/interface/prototypes/test_showcase_homepage.py
git commit -m "feat(prototypes): 将根首页改为原型展厅入口 --story=133683187"
```

---

### Task 3: 补首页专用视觉系统、封面主题和搜索筛选交互

**Files:**
- Create: `prototypes/assets/bkflow-showcase.css`
- Create: `prototypes/assets/bkflow-showcase.js`
- Modify: `prototypes/serve.py`
- Modify: `tests/interface/prototypes/test_showcase_homepage.py`

- [ ] **Step 1: 先补一轮失败测试，锁定资产引用和交互 hooks**

在 `tests/interface/prototypes/test_showcase_homepage.py` 中增加契约测试，要求首页至少具备以下 tokens：

```python
def test_root_index_includes_showcase_assets_and_filter_hooks(tmp_path, monkeypatch):
    ...
    assert 'href="/assets/bkflow-showcase.css"' in body
    assert 'src="/assets/bkflow-showcase.js"' in body
    assert 'data-showcase-search' in body
    assert 'data-showcase-filter="all"' in body
    assert 'data-feature-card' in body
    assert 'data-cover-theme="flow-editor"' in body
```

- [ ] **Step 2: 跑测试，确认当前失败**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django tests/interface/prototypes/test_showcase_homepage.py -v
```

Expected:
- FAIL，因为首页还没有引入专用 CSS / JS，也没有搜索筛选 hooks

- [ ] **Step 3: 创建首页专用 CSS，落 Hero、卡片和封面主题**

新建 `prototypes/assets/bkflow-showcase.css`，至少覆盖：
- Hero 大标题和统计卡片
- Feature 卡片网格
- 代表页面卡片
- 资源区弱化样式
- 4 到 5 种代码生成封面主题
- 移动端单列布局

建议最小结构：

```css
.bk-showcase-page {}
.bk-showcase-hero {}
.bk-showcase-stat-grid {}
.bk-feature-grid {}
.bk-feature-card {}
.bk-feature-cover[data-cover-theme="flow-editor"] {}
.bk-feature-cover[data-cover-theme="task-detail"] {}
.bk-page-preview-grid {}
.bk-resource-grid {}
```

- [ ] **Step 4: 创建首页专用 JS，并在 `serve.py` 中接入**

新建 `prototypes/assets/bkflow-showcase.js`，只做轻交互：

```javascript
document.addEventListener("DOMContentLoaded", () => {
  const search = document.querySelector("[data-showcase-search]");
  const filters = Array.from(document.querySelectorAll("[data-showcase-filter]"));
  const cards = Array.from(document.querySelectorAll("[data-feature-card]"));

  function applyFilters() {
    const keyword = (search?.value || "").trim().toLowerCase();
    const active = document.querySelector("[data-showcase-filter].active")?.dataset.showcaseFilter || "all";
    ...
  }

  search?.addEventListener("input", applyFilters);
  filters.forEach((button) => button.addEventListener("click", ...));
});
```

并在 `serve.py` 的首页 HTML 中：
- 引入 `/assets/bkflow-showcase.css`
- 引入 `/assets/bkflow-showcase.js`
- 为卡片输出 `data-feature-card`、`data-tags`、`data-status`、`data-cover-theme`
- 增加搜索框、筛选按钮和空结果占位

- [ ] **Step 5: 跑首页测试和全量原型测试**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django tests/interface/prototypes -v
python3.9 -m py_compile prototypes/serve.py prototypes/showcase_catalog.py
```

Expected:
- 全部 prototype tests PASS
- `py_compile` PASS

- [ ] **Step 6: Commit**

```bash
git add prototypes/assets/bkflow-showcase.css \
  prototypes/assets/bkflow-showcase.js \
  prototypes/serve.py \
  tests/interface/prototypes/test_showcase_homepage.py
git commit -m "feat(prototypes): 增加首页展厅视觉与筛选交互 --story=133683187"
```

---

### Task 4: 对齐文档、生成规则和结构合同，确保后续 feature 能自动接入首页

**Files:**
- Modify: `tests/interface/prototypes/test_structure_contract.py`
- Modify: `prototypes/README.md`
- Modify: `prototypes/features/README.md`
- Modify: `.ai/skills/prototype-generator/SKILL.md`

- [ ] **Step 1: 写失败测试，锁定静态资源和元数据合同**

扩展 `tests/interface/prototypes/test_structure_contract.py`，至少新增：

```python
from pathlib import Path


def test_showcase_assets_exist():
    required = [
        "prototypes/assets/bkflow-showcase.css",
        "prototypes/assets/bkflow-showcase.js",
    ]
    for path in required:
        assert Path(path).is_file(), path


def test_active_feature_has_showcase_meta():
    path = Path("prototypes/features/bkflow-engine-admin-prototype-overhaul/feature.meta.json")
    assert path.is_file(), path
    assert '"title"' in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: 跑失败测试**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django tests/interface/prototypes/test_structure_contract.py -v
```

Expected:
- 如果前面任务尚未完成，会先看到缺资源或缺元数据失败

- [ ] **Step 3: 更新 README 与 skill 规则**

把以下内容写实：
- `prototypes/README.md`：首页展厅定位、`feature.meta.json` 简介、首页展示来源
- `prototypes/features/README.md`：新增 feature 时必须同步维护 `feature.meta.json`
- `.ai/skills/prototype-generator/SKILL.md`：当生成 `features/<slug>/` 时，同步创建或更新 `feature.meta.json`

禁止继续沿用旧思路：
- 不要让 AI 只创建 `README.md` 和 `index.html` 却漏掉首页元数据
- 不要让首页展示信息硬编码到 `serve.py`

- [ ] **Step 4: 跑结构测试与文档相关回归**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django \
  tests/interface/prototypes/test_structure_contract.py \
  tests/interface/prototypes/test_showcase_catalog.py \
  tests/interface/prototypes/test_showcase_homepage.py -v
```

Expected:
- 结构合同、catalog、homepage 三类测试全部 PASS

- [ ] **Step 5: 做一次本地烟测**

Run:

```bash
python prototypes/serve.py --port 9139 >/tmp/prototype-showcase.log 2>&1 &
sleep 1
curl -s http://127.0.0.1:9139/ | head -80
```

Expected:
- 返回首页 HTML
- 输出中包含 `BKFlow 原型展厅`
- 输出中包含 `查看这组原型`

结束后停止本地进程，避免占用端口。

- [ ] **Step 6: Commit**

```bash
git add tests/interface/prototypes/test_structure_contract.py \
  prototypes/README.md \
  prototypes/features/README.md \
  .ai/skills/prototype-generator/SKILL.md
git commit -m "docs(prototypes): 对齐展厅首页的元数据与使用规则 --story=133683187"
```

---

## 最终验证清单

在所有 task 完成后，统一执行以下验证：

- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -c /dev/null -p no:django tests/interface/prototypes -v`
- [ ] `python3.9 -m py_compile prototypes/serve.py prototypes/showcase_catalog.py`
- [ ] 本地打开 `http://localhost:9139/` 确认首页首屏、Feature 卡片、代表页面区、资源区和筛选交互正常
- [ ] 打开 `prototypes/features/bkflow-engine-admin-prototype-overhaul/index.html` 确认 feature 内页入口未被首页改造破坏

## 风险提醒

1. `serve.py` 仍然是 stdlib 单文件服务器，首页渲染逻辑不要无限膨胀，catalog 与 HTML 片段生成应尽量分层。
2. 搜索和筛选只做前端轻交互，不要把首页做成复杂后台。
3. `feature.meta.json` 是展示契约，不要把完整 README 内容复制进去。
4. 现阶段只有一个 active feature，首页要为未来多个 feature 预留布局，但不要为了未来过度设计。

## 完成定义

当以下条件全部满足时，才算本计划完成：

1. 根首页从 URL 列表页升级为中文原型展厅首页。
2. 首页主区域以 `features/` 为主角，而不是 `masters/examples`。
3. 首页展示中文标题、摘要、标签和代码生成封面，而不是要求用户阅读 slug。
4. 现有 `bkflow-engine-admin-prototype-overhaul` feature 能通过 `feature.meta.json` 自动出现在首页。
5. 新增 feature 时，只要补 `feature.meta.json`，就能被首页自动纳入展示。
6. 所有 prototype tests 和 Python 3.9 语法校验通过。
