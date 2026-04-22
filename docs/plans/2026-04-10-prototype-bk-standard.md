# BKFlow 原型工具 `bk-standard` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `prototypes/` 升级为以 `bk-standard` 为主模式的原型编排层，动态消费 `@blueking/bkui-knowledge` 的设计规范、组件 API 与模板资产，默认输出真实 BK 组件预览并保留静态 fallback。

**Architecture:** 第一版继续以 Python 为编排主线，新增 `knowledge adapter -> prototype contract -> bk-standard renderer -> validator -> metadata` 链路。`bkui-knowledge` 的最新内容通过 `npm` 拉取与本地缓存进入渲染链路；在 AI 会话存在 MCP 时，由 `.ai/skills/prototype-generator` 优先使用 MCP 工具生成更完整的 contract 输入。

**Tech Stack:** Python 3, stdlib + `subprocess`, HTML, Vue 3 CDN, `bkui-vue` CDN preview shell, pytest, existing `prototypes/serve.py`

**Spec:** `docs/specs/2026-04-10-prototype-bk-standard-design.md`

**Scope:** 本计划仅覆盖 `bk-standard` 第一版基础链路：知识缓存、contract 编译、`preview-html` renderer、validator、metadata、`serve.py` 与 skill/doc 迁移。`preview-app`、复杂多路由原型和更多布局模板作为后续增量计划。

---

## 执行前提

在开始任何代码修改前，先完成以下前置动作：

- 准备独立 worktree：

```bash
cd /Users/dengyh/Projects/bk-flow
git worktree add ../bk-flow-prototype-bk-standard -b feat/prototype-bk-standard
```

- 准备 TAPD 单据 ID：
  - 若本地有 TAPD MCP，先按 `tapd-workitem-sync` 获取短 ID
  - 若当前会话没有 TAPD 能力，向需求方索取 TAPD 短 ID，再替换本计划里的 `<TAPD_ID>`
- 确认本地 `node` / `npm` 可用（用于 `npm view` / `npm pack`）：

```bash
node -v
npm -v
```

Expected:
- `node >= 18.20.4`
- `npm >= 10.7.0`

---

## 文件结构

```
prototypes/
├── __init__.py                              ← 让 prototypes 可作为 Python package 被 `python -m` 调用
├── generate.py                              ← CLI 入口；读取 contract、调用 renderer、写 output + metadata
├── knowledge_adapter.py                     ← `bkui-knowledge` 版本解析、npm 拉取、缓存加载、模板/API 读取
├── contract.py                              ← `prototype contract` 数据模型、校验与编译逻辑
├── project_overrides.py                     ← BKFlow 项目覆盖规则加载
├── validator.py                             ← 知识完整性、contract 完整性、渲染结果与降级校验
├── metadata.py                              ← 产物 metadata 写入与读取
├── renderers/
│   ├── __init__.py
│   ├── bk_standard.py                       ← 真实 BK 组件 `preview-html` 渲染器
│   └── static_fallback.py                   ← 现有 `base.html` + `bkflow-prototype.css/js` 的兜底渲染器
├── cache/
│   ├── .gitkeep
│   └── bkui-knowledge/                      ← 解包后的版本缓存
├── metadata/
│   └── .gitkeep                             ← 每个产物的 contract / metadata
├── project_overrides.json                   ← BKFlow 轻量覆盖：模块名、状态文案、token 等
├── serve.py                                 ← 预览服务器，新增 metadata 感知
├── README.md                                ← 更新为 `bk-standard` 默认模式
└── base.html                                ← 明确降级为 `static-fallback`

tests/interface/prototypes/
├── __init__.py
├── fixtures/
│   ├── contract_table_page.json             ← 样例 contract
│   ├── knowledge_manifest.json              ← 最小 manifest fixture
│   ├── preview_template.html                ← `bkui-demo` shell fixture
│   ├── layout_admin_left.vue                ← `bkui-builder` 布局 fixture
│   ├── page_table.vue                       ← `bkui-builder` 页面 fixture
│   └── component_api_navigation.json        ← 组件 API fixture
├── test_knowledge_adapter.py
├── test_contract.py
├── test_bk_standard_renderer.py
├── test_validator.py
├── test_generate_cli.py
└── test_serve.py

.ai/skills/
└── prototype-generator/SKILL.md             ← 默认进入 `bk-standard`，MCP-first，fallback-aware
```

---

## Task 1: 搭好 `bk-standard` 骨架与测试夹具

**Files:**
- Create: `prototypes/__init__.py`
- Create: `prototypes/renderers/__init__.py`
- Create: `prototypes/cache/.gitkeep`
- Create: `prototypes/metadata/.gitkeep`
- Create: `prototypes/project_overrides.json`
- Create: `tests/interface/prototypes/__init__.py`
- Create: `tests/interface/prototypes/fixtures/contract_table_page.json`
- Create: `tests/interface/prototypes/fixtures/knowledge_manifest.json`
- Create: `tests/interface/prototypes/fixtures/preview_template.html`
- Create: `tests/interface/prototypes/fixtures/layout_admin_left.vue`
- Create: `tests/interface/prototypes/fixtures/page_table.vue`
- Create: `tests/interface/prototypes/fixtures/component_api_navigation.json`

- [ ] **Step 1: 创建最小目录和占位文件**

```bash
mkdir -p prototypes/renderers prototypes/cache prototypes/metadata
mkdir -p tests/interface/prototypes/fixtures
touch prototypes/__init__.py
touch prototypes/renderers/__init__.py
touch prototypes/cache/.gitkeep
touch prototypes/metadata/.gitkeep
touch tests/interface/prototypes/__init__.py
```

- [ ] **Step 2: 写入 BKFlow 项目覆盖默认值**

```json
{
  "product_name": "BKFlow",
  "navigation": {
    "header_title": "BKFlow",
    "side_title": "工作流平台"
  },
  "status_labels": {
    "enabled": "启用",
    "disabled": "停用",
    "draft": "草稿"
  },
  "design_tokens": {
    "brand_primary": "#3a84ff"
  }
}
```

- [ ] **Step 3: 从当前 `bkui-knowledge` 版本提取最小 fixture**

将以下内容保存为 fixture：
- `knowledge/manifest.json` -> `knowledge_manifest.json`
- `knowledge/skills/bkui-demo/assets/preview-template.html` -> `preview_template.html`
- `knowledge/skills/bkui-builder/assets/layouts/admin-layout-left.vue` -> `layout_admin_left.vue`
- `knowledge/skills/bkui-builder/assets/pages/table-page.vue` -> `page_table.vue`
- `knowledge/component-apis/vue3/navigation.json` -> `component_api_navigation.json`

- [ ] **Step 4: 写入样例 contract**

```json
{
  "name": "space-variable-manage",
  "mode": "bk-standard",
  "layout_pattern": "table-page",
  "preview_strategy": "preview-html",
  "component_plan": ["navigation", "table", "pagination", "dialog", "input", "button"],
  "design_rules": ["prefer-standard-admin-layout", "prefer-real-bk-components"],
  "anti_patterns": ["avoid-handwritten-fake-dialog"],
  "project_overrides": {
    "module_name": "空间变量"
  },
  "knowledge_context": {
    "version": "0.0.1-beta.32",
    "skills": ["bkui-builder", "bkui-cheatsheet", "bkui-quick-start", "bkui-demo"],
    "components": ["navigation", "table", "pagination", "dialog"]
  },
  "page_model": {
    "title": "空间变量",
    "actions": ["新建", "编辑", "删除"],
    "filters": ["状态", "关键字"]
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add prototypes/__init__.py prototypes/renderers/__init__.py prototypes/cache/.gitkeep prototypes/metadata/.gitkeep prototypes/project_overrides.json tests/interface/prototypes/
git commit -m "feat(prototypes): 初始化 bk-standard 骨架与测试夹具 --story=<TAPD_ID>"
```

---

## Task 2: 实现 `knowledge_adapter` 的版本解析、npm 拉取与缓存回退

**Files:**
- Create: `prototypes/knowledge_adapter.py`
- Create: `tests/interface/prototypes/test_knowledge_adapter.py`

- [ ] **Step 1: 写失败测试，覆盖版本解析与缓存回退**

```python
from pathlib import Path

from prototypes.knowledge_adapter import KnowledgeAdapter


def test_loads_cached_version_without_hitting_npm(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    package_dir = cache_dir / "bkui-knowledge" / "0.0.1-beta.32" / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "knowledge").mkdir()
    (package_dir / "knowledge" / "manifest.json").write_text('{"version":"0.0.1-beta.32"}', encoding="utf-8")

    adapter = KnowledgeAdapter(cache_root=cache_dir)

    def _boom(*args, **kwargs):
        raise AssertionError("npm should not be called")

    monkeypatch.setattr(adapter, "_run_npm", _boom)

    resolved = adapter.resolve(version="0.0.1-beta.32", allow_network=False)

    assert resolved.version == "0.0.1-beta.32"
    assert resolved.source == "cache"


def test_falls_back_to_cached_version_when_pack_fails(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cached = cache_dir / "bkui-knowledge" / "0.0.1-beta.31" / "package"
    cached.mkdir(parents=True)
    (cached / "knowledge").mkdir()
    (cached / "knowledge" / "manifest.json").write_text('{"version":"0.0.1-beta.31"}', encoding="utf-8")

    adapter = KnowledgeAdapter(cache_root=cache_dir)
    monkeypatch.setattr(adapter, "_fetch_latest_version", lambda: "0.0.1-beta.32")
    monkeypatch.setattr(adapter, "_download_package", lambda version: (_ for _ in ()).throw(RuntimeError("pack failed")))

    resolved = adapter.resolve(version=None, allow_network=True)

    assert resolved.version == "0.0.1-beta.31"
    assert resolved.source == "cache-fallback"
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_knowledge_adapter.py -v`  
Expected: `ModuleNotFoundError` 或 `ImportError`，因为 `prototypes/knowledge_adapter.py` 尚不存在。

- [ ] **Step 3: 实现最小 `KnowledgeAdapter`**

```python
from __future__ import annotations

import json
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class KnowledgePackage:
    version: str
    source: str
    package_root: Path


class KnowledgeAdapter:
    def __init__(self, cache_root: Path | str):
        self.cache_root = Path(cache_root)
        self.package_cache_root = self.cache_root / "bkui-knowledge"

    def resolve(self, version: str | None, allow_network: bool = True) -> KnowledgePackage:
        requested = version or (self._fetch_latest_version() if allow_network else None)
        if requested:
            cached = self._package_dir(requested)
            if cached.exists():
                return KnowledgePackage(version=requested, source="cache", package_root=cached)
        if requested and allow_network:
            try:
                return self._download_package(requested)
            except Exception:
                fallback = self._latest_cached_package()
                if fallback:
                    return fallback
                raise
        fallback = self._latest_cached_package()
        if fallback:
            return fallback
        raise RuntimeError("No bkui-knowledge package is available")

    def load_manifest(self, package: KnowledgePackage) -> dict:
        path = package.package_root / "knowledge" / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def load_text_asset(self, package: KnowledgePackage, relative_path: str) -> str:
        return (package.package_root / relative_path).read_text(encoding="utf-8")
```

- [ ] **Step 4: 补齐 `npm view` / `npm pack` / tar 解包细节，并让测试通过**

Run: `pytest tests/interface/prototypes/test_knowledge_adapter.py -v`  
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add prototypes/knowledge_adapter.py tests/interface/prototypes/test_knowledge_adapter.py
git commit -m "feat(prototypes): 增加 bkui-knowledge 缓存与 npm 回退适配器 --story=<TAPD_ID>"
```

---

## Task 3: 实现 `prototype contract` 模型、编译器与项目覆盖合并

**Files:**
- Create: `prototypes/contract.py`
- Create: `prototypes/project_overrides.py`
- Create: `tests/interface/prototypes/test_contract.py`

- [ ] **Step 1: 写失败测试，覆盖 contract 必填项和覆盖合并**

```python
import json
from pathlib import Path

import pytest

from prototypes.contract import PrototypeContract, compile_contract


def test_compile_contract_merges_project_overrides(tmp_path):
    override_file = tmp_path / "project_overrides.json"
    override_file.write_text('{"navigation":{"header_title":"BKFlow"}}', encoding="utf-8")

    compiled = compile_contract(
        raw_contract={
            "name": "space-variable-manage",
            "mode": "bk-standard",
            "layout_pattern": "table-page",
            "preview_strategy": "preview-html",
            "component_plan": ["navigation", "table"],
            "knowledge_context": {"version": "0.0.1-beta.32", "skills": [], "components": []},
            "page_model": {"title": "空间变量"}
        },
        override_path=override_file,
    )

    assert compiled.project_overrides["navigation"]["header_title"] == "BKFlow"


def test_compile_contract_requires_preview_strategy(tmp_path):
    with pytest.raises(ValueError, match="preview_strategy"):
        compile_contract(
            raw_contract={
                "name": "broken",
                "mode": "bk-standard",
                "layout_pattern": "table-page",
                "component_plan": ["navigation"]
            },
            override_path=tmp_path / "missing.json",
        )
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_contract.py -v`  
Expected: `ModuleNotFoundError` 或 `ImportError`。

- [ ] **Step 3: 实现 dataclass + 校验函数**

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PrototypeContract:
    name: str
    mode: str
    layout_pattern: str
    preview_strategy: str
    component_plan: list[str]
    knowledge_context: dict
    page_model: dict
    design_rules: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    project_overrides: dict = field(default_factory=dict)


def compile_contract(raw_contract: dict, override_path) -> PrototypeContract:
    required = ["name", "mode", "layout_pattern", "preview_strategy", "component_plan", "knowledge_context", "page_model"]
    for key in required:
        if not raw_contract.get(key):
            raise ValueError(f"Missing required contract field: {key}")
    overrides = load_project_overrides(override_path)
    merged = dict(raw_contract)
    merged["project_overrides"] = deep_merge(overrides, raw_contract.get("project_overrides", {}))
    return PrototypeContract(**merged)
```

- [ ] **Step 4: 让测试通过，并补一条序列化测试**

Run: `pytest tests/interface/prototypes/test_contract.py -v`  
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add prototypes/contract.py prototypes/project_overrides.py tests/interface/prototypes/test_contract.py
git commit -m "feat(prototypes): 增加 prototype contract 编译与项目覆盖合并 --story=<TAPD_ID>"
```

---

## Task 4: 实现 `bk_standard` 渲染器，生成真实 BK 组件 `preview-html`

**Files:**
- Create: `prototypes/renderers/bk_standard.py`
- Create: `tests/interface/prototypes/test_bk_standard_renderer.py`

- [ ] **Step 1: 写失败测试，覆盖模板选择与 HTML 注入**

```python
from pathlib import Path

from prototypes.contract import compile_contract
from prototypes.renderers.bk_standard import BKStandardRenderer


def test_render_preview_html_uses_real_bk_shell(tmp_path):
    contract = compile_contract(
        raw_contract={
            "name": "space-variable-manage",
            "mode": "bk-standard",
            "layout_pattern": "table-page",
            "preview_strategy": "preview-html",
            "component_plan": ["navigation", "table", "pagination", "dialog"],
            "knowledge_context": {
                "version": "0.0.1-beta.32",
                "skills": ["bkui-builder", "bkui-demo"],
                "components": ["navigation", "table"]
            },
            "page_model": {"title": "空间变量"}
        },
        override_path=Path("prototypes/project_overrides.json"),
    )

    renderer = BKStandardRenderer(
        preview_template=Path("tests/interface/prototypes/fixtures/preview_template.html"),
        layout_template=Path("tests/interface/prototypes/fixtures/layout_admin_left.vue"),
        page_template=Path("tests/interface/prototypes/fixtures/page_table.vue"),
    )

    html = renderer.render(contract)

    assert "cdn.jsdelivr.net/npm/vue@3.4" in html
    assert "cdn.jsdelivr.net/npm/bkui-vue@2.0.2-beta.112" in html
    assert "空间变量" in html
    assert "bk-navigation" in html
    assert "bk-table" in html
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_bk_standard_renderer.py -v`  
Expected: `ModuleNotFoundError` 或 `ImportError`。

- [ ] **Step 3: 实现 SFC 片段提取与模板拼装**

```python
import re
from pathlib import Path


def extract_sfc_blocks(content: str) -> dict[str, str]:
    def _match(tag: str) -> str:
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", content, re.S)
        return m.group(1).strip() if m else ""
    return {
        "template": _match("template"),
        "script_setup": _match("script"),
        "style": _match("style"),
    }


class BKStandardRenderer:
    def __init__(self, preview_template: Path, layout_template: Path, page_template: Path):
        self.preview_template = preview_template
        self.layout_template = layout_template
        self.page_template = page_template

    def render(self, contract) -> str:
        preview = self.preview_template.read_text(encoding="utf-8")
        page_blocks = extract_sfc_blocks(self.page_template.read_text(encoding="utf-8"))
        html = preview.replace("{{PAGE_TITLE}}", contract.page_model["title"])
        html = html.replace("{{COMPONENT_TEMPLATE}}", page_blocks["template"])
        html = html.replace("{{COMPONENT_SETUP}}", page_blocks["script_setup"])
        html = html.replace("{{CUSTOM_STYLES}}", page_blocks["style"])
        return html
```

- [ ] **Step 4: 补齐布局选择、页面模式映射和 title / action / filter 注入**

Run: `pytest tests/interface/prototypes/test_bk_standard_renderer.py -v`  
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add prototypes/renderers/bk_standard.py tests/interface/prototypes/test_bk_standard_renderer.py
git commit -m "feat(prototypes): 实现 bk-standard preview-html 渲染器 --story=<TAPD_ID>"
```

---

## Task 5: 实现 validator、metadata 与静态 fallback 选择

**Files:**
- Create: `prototypes/validator.py`
- Create: `prototypes/metadata.py`
- Create: `prototypes/renderers/static_fallback.py`
- Create: `tests/interface/prototypes/test_validator.py`

- [ ] **Step 1: 写失败测试，覆盖强约束、降级标记与 metadata 写入**

```python
import json
from pathlib import Path

import pytest

from prototypes.metadata import write_metadata
from prototypes.validator import ValidationResult, validate_contract


def test_validate_contract_requires_knowledge_context():
    result = validate_contract({
        "name": "space-variable-manage",
        "mode": "bk-standard",
        "layout_pattern": "table-page",
        "preview_strategy": "preview-html",
        "component_plan": ["navigation"]
    })
    assert not result.ok
    assert "knowledge_context" in result.errors[0]


def test_write_metadata_marks_degraded_output(tmp_path):
    metadata_file = tmp_path / "space-variable-manage.json"
    write_metadata(
        metadata_file,
        {
            "name": "space-variable-manage",
            "mode": "static-fallback",
            "degraded": True,
            "degrade_reason": "bk-standard-render failed"
        },
    )
    payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert payload["degraded"] is True
    assert payload["degrade_reason"] == "bk-standard-render failed"
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_validator.py -v`  
Expected: `ModuleNotFoundError` 或 `ImportError`。

- [ ] **Step 3: 实现 validator 与 metadata 写入**

```python
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_contract(contract: dict) -> ValidationResult:
    errors = []
    for key in ["name", "mode", "layout_pattern", "preview_strategy", "component_plan", "knowledge_context"]:
        if not contract.get(key):
            errors.append(f"Missing required field: {key}")
    return ValidationResult(ok=not errors, errors=errors)
```

- [ ] **Step 4: 实现 `static_fallback` 渲染器，只包装现有 `base.html` 链路**

```python
from pathlib import Path


class StaticFallbackRenderer:
    def __init__(self, base_html: Path):
        self.base_html = base_html

    def render(self, body_html: str) -> str:
        base = self.base_html.read_text(encoding="utf-8")
        return base.replace("<!-- BKFLOW_PROTOTYPE_CONTENT -->", body_html)
```

- [ ] **Step 5: 让测试通过，并补一条“降级后必须写 metadata”的测试**

Run: `pytest tests/interface/prototypes/test_validator.py -v`  
Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add prototypes/validator.py prototypes/metadata.py prototypes/renderers/static_fallback.py tests/interface/prototypes/test_validator.py
git commit -m "feat(prototypes): 增加 validator、metadata 与静态 fallback 渲染器 --story=<TAPD_ID>"
```

---

## Task 6: 实现 `generate.py` CLI，并把 output / metadata 串起来

**Files:**
- Create: `prototypes/generate.py`
- Create: `tests/interface/prototypes/test_generate_cli.py`

- [ ] **Step 1: 写失败测试，覆盖 contract 输入与产物输出**

```python
import json
from pathlib import Path

from prototypes.generate import main


def test_generate_cli_writes_output_and_metadata(tmp_path):
    contract_file = tmp_path / "contract.json"
    contract_file.write_text(
        Path("tests/interface/prototypes/fixtures/contract_table_page.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    metadata_dir = tmp_path / "metadata"
    output_dir.mkdir()
    metadata_dir.mkdir()

    exit_code = main([
        "--contract", str(contract_file),
        "--output-dir", str(output_dir),
        "--metadata-dir", str(metadata_dir),
        "--mode", "bk-standard",
    ])

    assert exit_code == 0
    assert (output_dir / "space-variable-manage.html").exists()
    assert (metadata_dir / "space-variable-manage.json").exists()
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_generate_cli.py -v`  
Expected: `ModuleNotFoundError` 或 `ImportError`。

- [ ] **Step 3: 实现 CLI 主流程**

```python
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--mode", default="bk-standard")
    parser.add_argument("--output-dir", default="prototypes/output")
    parser.add_argument("--metadata-dir", default="prototypes/metadata")
    args = parser.parse_args(argv)

    raw_contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    contract = compile_contract(raw_contract, Path("prototypes/project_overrides.json"))
    validation = validate_contract(raw_contract)
    if not validation.ok:
        raise SystemExit("\n".join(validation.errors))

    html = render_contract(contract, mode=args.mode)
    output_path = Path(args.output_dir) / f"{contract.name}.html"
    output_path.write_text(html, encoding="utf-8")
    write_metadata(Path(args.metadata_dir) / f"{contract.name}.json", {"name": contract.name, "mode": args.mode})
    return 0
```

- [ ] **Step 4: 让测试通过，并增加 `static-fallback` 选择分支**

Run: `pytest tests/interface/prototypes/test_generate_cli.py -v`  
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add prototypes/generate.py tests/interface/prototypes/test_generate_cli.py
git commit -m "feat(prototypes): 增加 bk-standard 原型生成 CLI --story=<TAPD_ID>"
```

---

## Task 7: 升级 `serve.py`、README 与 `prototype-generator` skill

**Files:**
- Modify: `prototypes/serve.py`
- Modify: `prototypes/README.md`
- Modify: `.ai/skills/prototype-generator/SKILL.md`
- Create: `tests/interface/prototypes/test_serve.py`

- [ ] **Step 1: 写失败测试，覆盖 index 页面展示 metadata**

```python
from prototypes.serve import PrototypeRequestHandler, list_html_files, latest_mtime_under


def test_index_lists_html_files_and_mode_badges(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    metadata_dir = tmp_path / "metadata"
    output_dir.mkdir()
    metadata_dir.mkdir()
    (output_dir / "space-variable-manage.html").write_text("<html></html>", encoding="utf-8")
    (metadata_dir / "space-variable-manage.json").write_text('{"mode":"bk-standard","knowledge_version":"0.0.1-beta.32"}', encoding="utf-8")

    monkeypatch.setattr("prototypes.serve.OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr("prototypes.serve.METADATA_DIR", str(metadata_dir))

    items = list_html_files()
    assert items[0][1].endswith("space-variable-manage.html")
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `pytest tests/interface/prototypes/test_serve.py -v`  
Expected: `ImportError` 或断言失败，因为 `METADATA_DIR` / metadata 感知尚未实现。

- [ ] **Step 3: 修改 `serve.py`，增加 metadata 感知与标准模式展示**

需要完成：
- 新增 `METADATA_DIR = os.path.join(PROTOTYPES_ROOT, "metadata")`
- index 页面读取对应 metadata，展示：
  - 渲染模式
  - `bkui-knowledge` 版本
  - 是否发生降级
- 保持现有 `/api/mtime` 和自动刷新行为不回归

- [ ] **Step 4: 更新 README**

README 需改为：
- `bk-standard` 是默认推荐模式
- 静态 HTML 是 fallback
- 新增生成命令示例：

```bash
python -m prototypes.generate --contract prototypes/metadata/space-variable-manage.contract.json --mode bk-standard
```

- [ ] **Step 5: 更新 `.ai/skills/prototype-generator/SKILL.md`**

将 skill 主流程改为：
- 优先生成 `bk-standard` contract
- 若 AI 会话有 `bkui-knowledge` MCP，则先调用：
  - `recommend_skills`
  - `batch_load`
  - `get_component_api`
- 将结果写入 `prototypes/metadata/<name>.contract.json`
- 再调用 `python -m prototypes.generate --contract ... --mode bk-standard`
- 仅在标准链路失败时退回 `static-fallback`

- [ ] **Step 6: 跑测试和 smoke verification**

Run: `pytest tests/interface/prototypes/test_serve.py -v`  
Expected: `2 passed`.

Run: `python -m prototypes.generate --contract tests/interface/prototypes/fixtures/contract_table_page.json --mode bk-standard --output-dir prototypes/output --metadata-dir prototypes/metadata`  
Expected: 生成 `prototypes/output/space-variable-manage.html` 与 `prototypes/metadata/space-variable-manage.json`。

Run: `cd prototypes && python serve.py --port 9090`  
Expected: 打开 `http://localhost:9090/` 可看到 `space-variable-manage.html` 及其 `bk-standard` / 版本信息。

- [ ] **Step 7: Commit**

```bash
git add prototypes/serve.py prototypes/README.md .ai/skills/prototype-generator/SKILL.md tests/interface/prototypes/test_serve.py prototypes/output prototypes/metadata
git commit -m "feat(prototypes): 切换到 bk-standard 默认原型工作流 --story=<TAPD_ID>"
```

---

## Task 8: 做一轮端到端验收并清理遗留文案

**Files:**
- Modify: `prototypes/README.md`
- Modify: `prototypes/base.html`（仅增加 fallback 注释或占位标记时修改）
- Modify: `docs/specs/2026-04-10-prototype-bk-standard-design.md`（仅在实现后发现偏差时回写）

- [ ] **Step 1: 运行完整原型测试集**

Run: `pytest tests/interface/prototypes/ -v`  
Expected: 全部通过。

- [ ] **Step 2: 手工检查产物与 metadata 一致性**

检查项：
- `output/*.html` 是否包含 Vue 3 + `bkui-vue` CDN
- `metadata/*.json` 是否记录 `mode`、`knowledge_version`、`degraded`
- index 页面是否能区分 `bk-standard` 与 `static-fallback`

- [ ] **Step 3: 清理 README / `base.html` 中仍把静态模式写成主路线的文案**

保留原则：
- `base.html` 只作为 fallback 资产
- README 与 skill 文案都必须明确 `bk-standard` 是默认推荐模式

- [ ] **Step 4: 运行最终 smoke verification**

Run: `python -m prototypes.generate --contract tests/interface/prototypes/fixtures/contract_table_page.json --mode bk-standard --output-dir /tmp/bk-standard-output --metadata-dir /tmp/bk-standard-metadata`  
Expected: `/tmp/bk-standard-output/space-variable-manage.html` 成功生成。

Run: `python -m prototypes.generate --contract tests/interface/prototypes/fixtures/contract_table_page.json --mode static-fallback --output-dir /tmp/bk-static-output --metadata-dir /tmp/bk-static-metadata`  
Expected: fallback 产物成功生成，metadata 中 `mode = static-fallback`。

- [ ] **Step 5: Commit**

```bash
git add prototypes/README.md prototypes/base.html docs/specs/2026-04-10-prototype-bk-standard-design.md
git commit -m "docs(prototypes): 收口 bk-standard 文档与验收记录 --story=<TAPD_ID>"
```

---

## 最终验证清单

执行完成后，至少运行以下命令：

```bash
pytest tests/interface/prototypes/ -v
python -m prototypes.generate --contract tests/interface/prototypes/fixtures/contract_table_page.json --mode bk-standard --output-dir prototypes/output --metadata-dir prototypes/metadata
python -m prototypes.generate --contract tests/interface/prototypes/fixtures/contract_table_page.json --mode static-fallback --output-dir /tmp/bk-static-output --metadata-dir /tmp/bk-static-metadata
cd prototypes && python serve.py --port 9090
```

成功标准：

- `tests/interface/prototypes/` 全绿
- `bk-standard` 产物包含真实 BK 组件预览壳
- metadata 记录模式、版本和降级状态
- `serve.py` 首页可识别标准模式产物
- skill 与 README 都把 `bk-standard` 作为主路径
