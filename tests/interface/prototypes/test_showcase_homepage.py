from __future__ import annotations

import importlib.util
import subprocess
from textwrap import dedent
from io import BytesIO
from pathlib import Path


def _load_serve():
    path = Path("prototypes/serve.py")
    spec = importlib.util.spec_from_file_location("prototype_serve", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_handler(serve):
    handler = object.__new__(serve.PrototypeRequestHandler)
    handler.wfile = BytesIO()
    handler.send_response = lambda *args, **kwargs: None
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda *args, **kwargs: None
    return handler


def _write_feature(root, slug, meta, pages):
    feature_dir = root / slug
    feature_dir.mkdir()
    (feature_dir / "feature.meta.json").write_text(meta, encoding="utf-8")
    for rel_path, content in pages.items():
        page_path = feature_dir / rel_path
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(content, encoding="utf-8")
    return feature_dir


def _run_showcase_js_behavior() -> dict:
    script = dedent(
        r"""
        const fs = require('fs');
        const vm = require('vm');

        function makeClassList(initial) {
          const tokens = new Set((initial || '').split(/\s+/).filter(Boolean));
          return {
            toggle(token, force) {
              const shouldHave = force === undefined ? !tokens.has(token) : !!force;
              if (shouldHave) tokens.add(token); else tokens.delete(token);
            },
            contains(token) { return tokens.has(token); },
            toString() { return Array.from(tokens).join(' '); },
          };
        }

        function createElement(tag, attrs = {}, text = '') {
          const el = {
            tagName: tag.toUpperCase(),
            attrs: { ...attrs },
            children: [],
            parentNode: null,
            textContent: text,
            hidden: false,
            value: attrs.value || '',
            classList: makeClassList(attrs.class || ''),
            listeners: {},
            setAttribute(name, value) { this.attrs[name] = String(value); },
            getAttribute(name) { return this.attrs[name]; },
            addEventListener(type, cb) {
              (this.listeners[type] = this.listeners[type] || []).push(cb);
            },
            dispatchEvent(event) {
              (this.listeners[event.type] || []).forEach((cb) => cb(event));
            },
            contains(node) {
              if (node === this) return true;
              return this.children.some((child) => child.contains && child.contains(node));
            },
            closest(selector) {
              return matches(this, selector) ? this : null;
            },
            querySelector(selector) {
              return queryAll(this, selector)[0] || null;
            },
            querySelectorAll(selector) {
              return queryAll(this, selector);
            },
          };
          el.className = attrs.class || '';
          return el;
        }

        function matches(el, selector) {
          const active = selector.includes('.is-active');
          if (active && !el.classList.contains('is-active')) return false;
          const attrMatch = selector.match(/\[([^\]=]+)(?:="([^"]*)")?\]/);
          if (!attrMatch) return false;
          const name = attrMatch[1];
          const expected = attrMatch[2];
          if (!(name in el.attrs)) return false;
          return expected === undefined || String(el.attrs[name]) === expected;
        }

        function queryAll(root, selector) {
          const results = [];
          (function walk(node) {
            if (matches(node, selector)) results.push(node);
            node.children.forEach(walk);
          })(root);
          return results;
        }

        const search = createElement('input', { 'data-showcase-search': '', type: 'search' });
        const summary = createElement('p', { 'data-showcase-summary': '' }, '');
        const emptyState = createElement('p', { 'data-showcase-empty': '' }, '');
        const cardOne = createElement('article', {
          'data-feature-card': '',
          'data-status': '进行中',
          'data-tags': '代码生成,流程编排',
          'data-search-index': '流程总览 overview 总览页 详情页',
        });
        const cardTwo = createElement('article', {
          'data-feature-card': '',
          'data-status': '已完成',
          'data-tags': '资源库',
          'data-search-index': '资源中心 resource',
        });
        const statusGroup = createElement('div', { 'data-showcase-filter-group': 'status' });
        const statusAll = createElement('button', { 'data-showcase-filter': 'all', class: 'is-active' });
        const statusLive = createElement('button', { 'data-showcase-filter': '进行中' });
        statusGroup.children = [statusAll, statusLive];
        statusAll.parentNode = statusGroup;
        statusLive.parentNode = statusGroup;
        const tagGroup = createElement('div', { 'data-showcase-filter-group': 'tag' });
        const tagAll = createElement('button', { 'data-showcase-filter': 'all', class: 'is-active' });
        const tagCode = createElement('button', { 'data-showcase-filter': '代码生成' });
        tagGroup.children = [tagAll, tagCode];
        tagAll.parentNode = tagGroup;
        tagCode.parentNode = tagGroup;
        const root = createElement('main', { 'data-showcase-root': '' });
        root.children = [search, summary, emptyState, cardOne, cardTwo, statusGroup, tagGroup];
        [search, summary, emptyState, cardOne, cardTwo, statusGroup, tagGroup].forEach((child) => { child.parentNode = root; });

        const document = {
          readyState: 'complete',
          querySelector(selector) {
            return selector === '[data-showcase-root]' ? root : null;
          },
          addEventListener() {},
        };

        const context = {
          document,
          console,
          setInterval,
          clearInterval,
          location: { reload() {} },
          fetch() { return Promise.resolve({ json() { return Promise.resolve({ mtime: 1 }); } }); },
        };

        vm.runInNewContext(fs.readFileSync('prototypes/assets/bkflow-showcase.js', 'utf8'), context);

        const initial = {
          summary: summary.textContent,
          cardOneHidden: cardOne.hidden,
          cardTwoHidden: cardTwo.hidden,
          emptyHidden: emptyState.hidden,
        };

        search.value = '资源';
        search.dispatchEvent({ type: 'input', target: search });
        const afterSearch = {
          summary: summary.textContent,
          cardOneHidden: cardOne.hidden,
          cardTwoHidden: cardTwo.hidden,
          emptyHidden: emptyState.hidden,
        };

        statusGroup.dispatchEvent({ type: 'click', target: statusLive });
        const afterFilter = {
          summary: summary.textContent,
          cardOneHidden: cardOne.hidden,
          cardTwoHidden: cardTwo.hidden,
          emptyHidden: emptyState.hidden,
        };

        process.stdout.write(JSON.stringify({ initial, afterSearch, afterFilter }));
        """
    )
    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    return __import__("json").loads(completed.stdout)


def test_root_showcase_homepage_renders_chinese_hero_sections_and_cta(tmp_path, monkeypatch):
    """Root homepage should render the showcase layout and consume catalog data."""

    serve = _load_serve()
    root = tmp_path / "prototypes"
    masters = root / "masters"
    features = root / "features"
    examples = root / "examples"
    assets = root / "assets"
    for directory in [masters, features, examples, assets]:
        directory.mkdir(parents=True)

    _write_feature(
        features,
        "demo-feature",
        """
        {
          "title": "流程总览",
          "summary": "首页主角 feature",
          "status": "进行中",
          "coverTheme": "flow-editor",
          "tags": ["代码生成", "流程编排"],
          "order": 1,
          "featuredPages": [
            {"path": "overview.html", "title": "总览页", "pageType": "流程编辑"},
            {"path": "details.html", "title": "详情页", "pageType": "任务详情"},
            {"path": "card-only.html", "title": "卡片页", "pageType": "列表管理"}
          ]
        }
        """.strip(),
        {
            "overview.html": "<html><body>overview</body></html>",
            "details.html": "<html><body>details</body></html>",
            "card-only.html": "<html><body>card</body></html>",
        },
    )

    (masters / "list-page.html").write_text("<html><body>master</body></html>", encoding="utf-8")
    (examples / "component-showcase.html").write_text("<html><body>showcase</body></html>", encoding="utf-8")
    (assets / "bkflow-prototype.css").write_text("body{}", encoding="utf-8")

    monkeypatch.setattr(serve, "PROTOTYPES_ROOT", str(root))
    monkeypatch.setattr(serve, "MASTERS_DIR", str(masters))
    monkeypatch.setattr(serve, "FEATURES_DIR", str(features))
    monkeypatch.setattr(serve, "EXAMPLES_DIR", str(examples))
    monkeypatch.setattr(serve, "ASSETS_DIR", str(assets))

    handler = object.__new__(serve.PrototypeRequestHandler)
    handler.wfile = BytesIO()
    handler.send_response = lambda *args, **kwargs: None
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda *args, **kwargs: None

    serve.PrototypeRequestHandler._send_index(handler)
    body = handler.wfile.getvalue().decode("utf-8")

    assert "BKFlow 原型展厅" in body
    assert "最近更新" in body
    assert "流程总览" in body
    assert 'href="/assets/bkflow-showcase.css"' in body
    assert 'src="/assets/bkflow-showcase.js"' in body
    assert 'data-showcase-search' in body
    assert 'data-showcase-filter="all"' in body
    assert 'data-feature-card' in body
    assert 'data-status="进行中"' in body
    assert 'data-tags="代码生成,流程编排"' in body
    assert 'data-cover-theme="flow-editor"' in body
    assert 'href="/features/demo-feature/card-only.html"' in body
    assert "代表页面" in body
    assert "流程编辑" in body
    assert "任务详情" in body
    assert "列表管理" in body
    assert "工具资源" in body
    assert 'href="#feature-showcase"' in body
    assert "查看 Feature 展区" in body
    assert 'data-showcase-empty' in body


def test_root_showcase_homepage_falls_back_to_default_cover_theme_when_missing(tmp_path, monkeypatch):
    """Missing coverTheme metadata should fall back to the default showcase theme."""

    serve = _load_serve()
    root = tmp_path / "prototypes"
    masters = root / "masters"
    features = root / "features"
    examples = root / "examples"
    assets = root / "assets"
    for directory in [masters, features, examples, assets]:
        directory.mkdir(parents=True)

    feature_dir = features / "demo-feature"
    feature_dir.mkdir()
    (feature_dir / "feature.meta.json").write_text(
        """
        {
          "title": "流程总览",
          "summary": "缺省主题回退",
          "status": "进行中",
          "tags": ["代码生成"],
          "featuredPages": [{"path": "overview.html", "title": "总览页"}]
        }
        """.strip(),
        encoding="utf-8",
    )
    (feature_dir / "overview.html").write_text("<html><body>overview</body></html>", encoding="utf-8")

    monkeypatch.setattr(serve, "PROTOTYPES_ROOT", str(root))
    monkeypatch.setattr(serve, "MASTERS_DIR", str(masters))
    monkeypatch.setattr(serve, "FEATURES_DIR", str(features))
    monkeypatch.setattr(serve, "EXAMPLES_DIR", str(examples))
    monkeypatch.setattr(serve, "ASSETS_DIR", str(assets))

    handler = _make_handler(serve)
    serve.PrototypeRequestHandler._send_index(handler)
    body = handler.wfile.getvalue().decode("utf-8")

    assert 'data-cover-theme="mixed-admin"' in body
    assert "Mixed Admin" in body


def test_root_showcase_homepage_keeps_spec_cover_theme_variants_and_labels(tmp_path, monkeypatch):
    """Spec coverTheme variants should render distinct previews instead of collapsing to the default theme."""

    serve = _load_serve()
    root = tmp_path / "prototypes"
    masters = root / "masters"
    features = root / "features"
    examples = root / "examples"
    assets = root / "assets"
    for directory in [masters, features, examples, assets]:
        directory.mkdir(parents=True)

    for order, (slug, theme, title) in enumerate(
        [
            ("task-detail-feature", "task-detail", "任务详情"),
            ("list-management-feature", "list-management", "列表管理"),
            ("config-panel-feature", "config-panel", "配置面板"),
        ],
        start=1,
    ):
        _write_feature(
            features,
            slug,
            f"""
            {{
              "title": "{title}",
              "summary": "{theme} 主题校验",
              "status": "进行中",
              "coverTheme": "{theme}",
              "order": {order},
              "featuredPages": [
                {{"path": "page.html", "title": "页面", "pageType": "{title}"}}
              ]
            }}
            """.strip(),
            {"page.html": "<html><body>page</body></html>"},
        )

    monkeypatch.setattr(serve, "PROTOTYPES_ROOT", str(root))
    monkeypatch.setattr(serve, "MASTERS_DIR", str(masters))
    monkeypatch.setattr(serve, "FEATURES_DIR", str(features))
    monkeypatch.setattr(serve, "EXAMPLES_DIR", str(examples))
    monkeypatch.setattr(serve, "ASSETS_DIR", str(assets))

    handler = _make_handler(serve)
    serve.PrototypeRequestHandler._send_index(handler)
    body = handler.wfile.getvalue().decode("utf-8")

    assert 'data-cover-theme="task-detail"' in body
    assert 'data-cover-theme="list-management"' in body
    assert 'data-cover-theme="config-panel"' in body
    assert 'cover-preview--task-detail' in body
    assert 'cover-preview--list-management' in body
    assert 'cover-preview--config-panel' in body
    assert "Task Detail" in body
    assert "List Management" in body
    assert "Config Panel" in body
    assert "code-console" not in body
    assert "dashboard" not in body
    assert "mobile-first" not in body


def test_root_showcase_homepage_representative_pages_show_page_type_and_feature(tmp_path, monkeypatch):
    """Representative pages should stay grouped by feature and expose page type context."""

    serve = _load_serve()
    root = tmp_path / "prototypes"
    masters = root / "masters"
    features = root / "features"
    examples = root / "examples"
    assets = root / "assets"
    for directory in [masters, features, examples, assets]:
        directory.mkdir(parents=True)

    _write_feature(
        features,
        "flow-feature",
        """
        {
          "title": "流程总览",
          "summary": "代表页面要带上下文",
          "status": "进行中",
          "coverTheme": "flow-editor",
          "order": 1,
          "featuredPages": [
            {"path": "overview.html", "title": "总览页", "pageType": "流程编辑"},
            {"path": "detail.html", "title": "详情页", "pageType": "任务详情"}
          ]
        }
        """.strip(),
        {
            "overview.html": "<html><body>overview</body></html>",
            "detail.html": "<html><body>detail</body></html>",
        },
    )

    monkeypatch.setattr(serve, "PROTOTYPES_ROOT", str(root))
    monkeypatch.setattr(serve, "MASTERS_DIR", str(masters))
    monkeypatch.setattr(serve, "FEATURES_DIR", str(features))
    monkeypatch.setattr(serve, "EXAMPLES_DIR", str(examples))
    monkeypatch.setattr(serve, "ASSETS_DIR", str(assets))

    handler = _make_handler(serve)
    serve.PrototypeRequestHandler._send_index(handler)
    body = handler.wfile.getvalue().decode("utf-8")

    assert "代表页面" in body
    assert "流程总览" in body
    assert "流程编辑" in body
    assert "任务详情" in body
    assert "所属 Feature" in body
    assert 'href="/features/flow-feature/overview.html"' in body
    assert 'href="/features/flow-feature/detail.html"' in body


def test_bkflow_showcase_js_updates_hidden_summary_and_empty_state(tmp_path):
    """Search and filter interactions should update the lightweight showcase state."""

    result = _run_showcase_js_behavior()

    assert result["initial"]["summary"] == "当前展示 2 个 Feature"
    assert result["initial"]["cardOneHidden"] is False
    assert result["initial"]["cardTwoHidden"] is False
    assert result["initial"]["emptyHidden"] is True
    assert result["afterSearch"]["summary"] == "当前展示 1 个 Feature"
    assert result["afterSearch"]["cardOneHidden"] is True
    assert result["afterSearch"]["cardTwoHidden"] is False
    assert result["afterSearch"]["emptyHidden"] is True
    assert result["afterFilter"]["summary"] == "当前没有匹配的 Feature"
    assert result["afterFilter"]["cardOneHidden"] is True
    assert result["afterFilter"]["cardTwoHidden"] is True
    assert result["afterFilter"]["emptyHidden"] is False
