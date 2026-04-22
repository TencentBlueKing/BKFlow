#!/usr/bin/env python3
"""Zero-dependency static preview server for BKFlow prototypes (stdlib only)."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from html import escape
import os
import sys
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Union
from urllib.parse import unquote, urlparse

try:
    from prototypes.showcase_catalog import collect_feature_catalog, collect_showcase_stats
except ImportError:  # pragma: no cover - fallback for direct `cd prototypes && python serve.py`
    from showcase_catalog import collect_feature_catalog, collect_showcase_stats

PROTOTYPES_ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PROTOTYPES_ROOT, "assets")
MASTERS_DIR = os.path.join(PROTOTYPES_ROOT, "masters")
FEATURES_DIR = os.path.join(PROTOTYPES_ROOT, "features")
EXAMPLES_DIR = os.path.join(PROTOTYPES_ROOT, "examples")
DEFAULT_COVER_THEME = "mixed-admin"
SUPPORTED_COVER_THEMES = {
    "flow-editor": "Flow Editor",
    "task-detail": "Task Detail",
    "list-management": "List Management",
    "config-panel": "Config Panel",
    "mixed-admin": "Mixed Admin",
}

# Injected before </body> or </html>; polls /api/mtime every 1s and reloads on change.
_RELOAD_SCRIPT = (
    b"<script>"
    b"(function(){"
    b"var last=null;"
    b"function tick(){"
    b"fetch('/api/mtime').then(function(r){return r.json();}).then(function(d){"
    b"var m=Number(d.mtime)||0;"
    b"if(last!==null&&m>last){location.reload();return;}"
    b"last=m;"
    b"});"
    b"}"
    b"fetch('/api/mtime').then(function(r){return r.json();}).then(function(d){"
    b"last=Number(d.mtime)||0;"
    b"setInterval(tick,1000);"
    b"});"
    b"})();"
    b"</script>"
)


def _is_safe_relpath(rel: str) -> bool:
    if not rel or rel.startswith("/"):
        return False
    parts = rel.replace("\\", "/").split("/")
    return ".." not in parts


def _under_root(full: str, root: str) -> bool:
    full_abs = os.path.abspath(full)
    root_abs = os.path.abspath(root)
    try:
        os.path.commonpath([full_abs, root_abs])
    except ValueError:
        return False
    return full_abs == root_abs or full_abs.startswith(root_abs + os.sep)


def latest_mtime_under(bases: tuple[str, ...]) -> float:
    """Latest mtime among non-hidden files under given directories."""
    latest = 0.0
    for base in bases:
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            try:
                dir_mtime = os.path.getmtime(dirpath)
            except OSError:
                dir_mtime = None
            if dir_mtime is not None and dir_mtime > latest:
                latest = dir_mtime
            for name in filenames:
                if name.startswith("."):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    m = os.path.getmtime(path)
                except OSError:
                    continue
                if m > latest:
                    latest = m
    return latest


def list_html_files() -> list[tuple[str, str]]:
    """Return [(section, url_path), ...] for *.html under masters/features/examples."""
    found: list[tuple[str, str]] = []
    mapping = (("masters", MASTERS_DIR), ("features", FEATURES_DIR), ("examples", EXAMPLES_DIR))
    for section, base in mapping:
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in sorted(filenames):
                if not name.lower().endswith(".html"):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, PROTOTYPES_ROOT)
                url_path = rel.replace(os.sep, "/")
                found.append((section, url_path))
    found.sort(key=lambda x: (x[0], x[1]))
    return found


def inject_reload_script(html: bytes) -> bytes:
    low = html.lower()
    idx = low.rfind(b"</body>")
    if idx != -1:
        return html[:idx] + _RELOAD_SCRIPT + html[idx:]
    idx = low.rfind(b"</html>")
    if idx != -1:
        return html[:idx] + _RELOAD_SCRIPT + html[idx:]
    return html + _RELOAD_SCRIPT


def _format_timestamp(value: float) -> str:
    if not value:
        return "暂无更新"
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")


def _format_stat_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _normalize_cover_theme(theme: object) -> str:
    value = str(theme or DEFAULT_COVER_THEME).strip().lower().replace("_", "-")
    return value if value in SUPPORTED_COVER_THEMES else DEFAULT_COVER_THEME


def _collect_filter_options(features: list[dict]) -> tuple[list[str], list[str]]:
    statuses: list[str] = []
    tags: list[str] = []
    for feature in features:
        status = str(feature.get("status") or "").strip()
        if status and status not in statuses:
            statuses.append(status)
        feature_tags = feature.get("tags", [])
        if not isinstance(feature_tags, list):
            continue
        for tag in feature_tags:
            tag_value = str(tag).strip()
            if tag_value and tag_value not in tags:
                tags.append(tag_value)
    return statuses, tags[:6]


def _render_cover_theme_preview(theme: str) -> str:
    normalized = _normalize_cover_theme(theme)
    if normalized == "flow-editor":
        return (
            '<div class="cover-preview cover-preview--flow-editor">'
            '<div class="cover-window">'
            '<span class="cover-window-bar"></span>'
            '<div class="cover-flow-canvas">'
            '<span class="cover-flow-node cover-flow-node--input">表单</span>'
            '<span class="cover-flow-link"></span>'
            '<span class="cover-flow-node cover-flow-node--action">生成</span>'
            '<span class="cover-flow-link"></span>'
            '<span class="cover-flow-node cover-flow-node--review">审核</span>'
            "</div>"
            "</div>"
            f'<span class="cover-theme-label">{SUPPORTED_COVER_THEMES[normalized]}</span>'
            "</div>"
        )
    if normalized == "task-detail":
        return (
            '<div class="cover-preview cover-preview--task-detail">'
            '<div class="cover-detail-shell">'
            '<div class="cover-detail-sidebar">'
            '<span></span><span></span><span></span>'
            "</div>"
            '<div class="cover-detail-main">'
            '<span class="cover-detail-title"></span>'
            '<span class="cover-detail-panel"></span>'
            '<span class="cover-detail-panel cover-detail-panel--wide"></span>'
            "</div>"
            "</div>"
            f'<span class="cover-theme-label">{SUPPORTED_COVER_THEMES[normalized]}</span>'
            "</div>"
        )
    if normalized == "list-management":
        return (
            '<div class="cover-preview cover-preview--list-management">'
            '<div class="cover-list-board">'
            '<div class="cover-list-toolbar">'
            '<span></span><span></span>'
            "</div>"
            '<div class="cover-list-table">'
            '<span class="cover-list-row cover-list-row--head"></span>'
            '<span class="cover-list-row"></span>'
            '<span class="cover-list-row"></span>'
            '<span class="cover-list-row"></span>'
            "</div>"
            f'<span class="cover-theme-label">{SUPPORTED_COVER_THEMES[normalized]}</span>'
            "</div>"
        )
    if normalized == "config-panel":
        return (
            '<div class="cover-preview cover-preview--config-panel">'
            '<div class="cover-config-form">'
            '<span class="cover-config-field cover-config-field--label"></span>'
            '<span class="cover-config-field"></span>'
            '<span class="cover-config-field cover-config-field--label"></span>'
            '<span class="cover-config-field"></span>'
            '<span class="cover-config-field cover-config-field--wide"></span>'
            "</div>"
            f'<span class="cover-theme-label">{SUPPORTED_COVER_THEMES[normalized]}</span>'
            "</div>"
        )
    return (
        '<div class="cover-preview cover-preview--mixed-admin">'
        '<div class="cover-mixed-grid">'
        '<span class="cover-mixed-card"></span>'
        '<span class="cover-mixed-card"></span>'
        '<span class="cover-mixed-card cover-mixed-card--wide"></span>'
        "</div>"
        f'<span class="cover-theme-label">{SUPPORTED_COVER_THEMES[normalized]}</span>'
        "</div>"
    )


def _render_filter_buttons(label: str, options: list[str], group: str) -> str:
    buttons = [
        f'<button type="button" class="showcase-filter-pill is-active" data-showcase-filter="all">{escape(label)}</button>'
    ]
    for option in options:
        buttons.append(
            f'<button type="button" class="showcase-filter-pill" data-showcase-filter="{escape(option)}">{escape(option)}</button>'
        )
    return "".join(buttons)


def _render_feature_pages(feature: dict) -> str:
    slug = escape(str(feature.get("slug") or ""))
    pages = feature.get("featured_pages", [])
    if not pages:
        return "<p class=\"empty\">暂无代表页面。</p>"
    items = []
    for page in pages:
        title = escape(str(page.get("title") or page.get("path") or ""))
        summary = escape(str(page.get("summary") or ""))
        path = escape(str(page.get("path") or ""))
        items.append(
            "<li class=\"showcase-page\">"
            f'<a href="/features/{slug}/{path}"><strong>{title}</strong></a>'
            f'<span>{summary or path}</span>'
            "</li>"
        )
    return "<ul class=\"showcase-page-list\">" + "".join(items) + "</ul>"


def _render_feature_card(feature: dict) -> str:
    slug = escape(str(feature.get("slug") or ""))
    title = escape(str(feature.get("title") or slug))
    summary = escape(str(feature.get("summary") or ""))
    status = escape(str(feature.get("status") or ""))
    cover_theme = _normalize_cover_theme(feature.get("cover_theme") or feature.get("coverTheme"))
    cover_label = escape(cover_theme.replace("-", " ").title())
    updated_at = _format_timestamp(float(feature.get("updated_at") or 0))
    page_count = _format_stat_value(feature.get("page_count"))
    tags = feature.get("tags", [])
    tag_values: list[str] = []
    search_terms = [title, summary, status, slug]
    tag_html = ""
    if isinstance(tags, list) and tags:
        tag_values = [str(tag).strip() for tag in tags if str(tag).strip()]
        search_terms.extend(tag_values)
        tag_html = "<div class=\"showcase-tags\">" + "".join(
            f'<span class="showcase-tag">{escape(tag)}</span>' for tag in tag_values
        ) + "</div>"
    featured_pages = feature.get("featured_pages", [])
    if isinstance(featured_pages, list):
        for page in featured_pages:
            if not isinstance(page, dict):
                continue
            page_title = str(page.get("title") or page.get("path") or "").strip()
            page_summary = str(page.get("summary") or "").strip()
            page_type = str(page.get("page_type") or "").strip()
            if page_title:
                search_terms.append(page_title)
            if page_summary:
                search_terms.append(page_summary)
            if page_type:
                search_terms.append(page_type)
    return (
        f'<article class="showcase-card" data-feature-card data-status="{status}" data-tags="{escape(",".join(tag_values))}" data-cover-theme="{escape(cover_theme)}" data-search-index="{escape(" ".join(search_terms))}">'
        f"{_render_cover_theme_preview(cover_theme)}"
        f'<div class="showcase-card-head"><h3>{title}</h3><span class="showcase-badge">{status}</span></div>'
        f'<p class="showcase-cover-meta">{cover_label}</p>'
        f"<p>{summary}</p>"
        f"<dl class=\"showcase-meta\">"
        f"<div><dt>Slug</dt><dd>{slug}</dd></div>"
        f"<div><dt>页面数</dt><dd>{page_count}</dd></div>"
        f"<div><dt>最近更新</dt><dd>{updated_at}</dd></div>"
        f"</dl>"
        f"{tag_html}"
        f'<div class="showcase-actions"><a class="bk-button bk-button-primary" href="/features/{slug}/">查看这组原型</a></div>'
        f"{_render_feature_pages(feature)}"
        "</article>"
    )


def _render_recent_updates(features: list[dict]) -> str:
    if not features:
        return '<p class="empty">暂无最近更新的原型。</p>'
    items = []
    for feature in sorted(features, key=lambda item: (item.get("updated_at") or 0, str(item.get("slug") or "")), reverse=True)[:3]:
        title = escape(str(feature.get("title") or feature.get("slug") or ""))
        summary = escape(str(feature.get("summary") or ""))
        updated_at = _format_timestamp(float(feature.get("updated_at") or 0))
        items.append(
            "<li>"
            f'<strong>{title}</strong>'
            f"<span>{summary}</span>"
            f"<small>{updated_at}</small>"
            "</li>"
        )
    return "<ul class=\"showcase-updates\">" + "".join(items) + "</ul>"


def _render_representative_pages(features: list[dict]) -> str:
    groups = []
    for feature in features:
        feature_title = escape(str(feature.get("title") or feature.get("slug") or ""))
        feature_summary = escape(str(feature.get("summary") or ""))
        page_items = []
        for page in feature.get("featured_pages", [])[:2]:
            if not isinstance(page, dict):
                continue
            page_title = escape(str(page.get("title") or page.get("path") or ""))
            page_summary = escape(str(page.get("summary") or ""))
            page_type = escape(str(page.get("page_type") or ""))
            page_path = escape(str(page.get("path") or ""))
            meta_bits = [f'<span class="showcase-page-feature">所属 Feature：{feature_title}</span>']
            if page_type:
                meta_bits.append(f'<span class="showcase-page-type">{page_type}</span>')
            if page_summary:
                meta_bits.append(f'<span class="showcase-page-summary">{page_summary}</span>')
            page_items.append(
                "<li class=\"showcase-page-item\">"
                f'<a href="/features/{escape(str(feature.get("slug") or ""))}/{page_path}"><strong>{page_title}</strong></a>'
                f'<div class="showcase-page-meta">{"".join(meta_bits)}</div>'
                "</li>"
            )
        if not page_items:
            continue
        groups.append(
            "<article class=\"showcase-feature-pages\">"
            '<div class="showcase-feature-pages-head">'
            '<p class="showcase-feature-pages-kicker">所属 Feature</p>'
            f"<h3>{feature_title}</h3>"
            f'<p class="showcase-feature-pages-summary">{feature_summary}</p>'
            "</div>"
            '<ul class="showcase-page-list">'
            + "".join(page_items)
            + "</ul>"
            "</article>"
        )
    if not groups:
        return '<p class="empty">暂无代表页面。</p>'
    return "<div class=\"showcase-feature-pages-grid\">" + "".join(groups) + "</div>"


def _render_tool_resources() -> str:
    resources = [
        ("masters/", "长期母版入口"),
        ("features/", "需求原型目录"),
        ("examples/component-showcase.html", "组件参考样例"),
        ("serve.py", "本地预览服务器"),
        ("showcase_catalog.py", "展厅数据聚合"),
    ]
    items = "".join(
        f'<li><a href="/{escape(path)}">{escape(path)}</a><span>{escape(label)}</span></li>'
        for path, label in resources
    )
    return f'<ul class="showcase-resources">{items}</ul>'


def _render_homepage() -> bytes:
    features = collect_feature_catalog(FEATURES_DIR)
    stats = collect_showcase_stats(FEATURES_DIR, MASTERS_DIR)
    statuses, tags = _collect_filter_options(features)
    stat_items = [
        ("Feature 目录", stats.get("feature_count")),
        ("Feature 页面", stats.get("feature_page_count")),
        ("母版页面", stats.get("master_page_count")),
        ("HTML 总数", stats.get("html_page_count")),
    ]
    stat_html = "".join(
        f'<div class="showcase-stat"><strong>{escape(label)}</strong><span>{escape(_format_stat_value(value))}</span></div>'
        for label, value in stat_items
    )
    featured_cards = "".join(_render_feature_card(feature) for feature in features) or ""
    feature_empty = '<p class="showcase-empty" data-showcase-empty hidden>暂无匹配的 Feature，试试搜索关键词或切换筛选条件。</p>'
    feature_summary = f'<p class="showcase-summary" data-showcase-summary>当前展示 {len(features)} 个 Feature</p>'
    status_filters = _render_filter_buttons("全部状态", statuses, "status")
    tag_filters = _render_filter_buttons("全部标签", tags, "tag")
    recent_updates = _render_recent_updates(features)
    representative_pages = _render_representative_pages(features)

    lines = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>BKFlow 原型展厅</title>",
        '<link rel="stylesheet" href="/assets/bkflow-showcase.css">',
        '<script defer src="/assets/bkflow-showcase.js"></script>',
        "</head>",
        "<body>",
        '<main class="showcase-shell" data-showcase-root>',
        '<section class="showcase-hero">',
        '<p class="showcase-kicker">Prototype Showcase</p>',
        "<h1>BKFlow 原型展厅</h1>",
        "<p>features 是首页主角，masters 和 examples 则作为次级资源区。你可以先看最近更新，再进入具体 Feature，最后打开代表页面或工具资源继续搭建。</p>",
        '<div class="showcase-actions"><a class="bk-button bk-button-primary" href="#feature-showcase">查看 Feature 展区</a><a class="bk-button" href="/masters/">浏览母版</a><a class="bk-button" href="/examples/component-showcase.html">打开组件参考</a></div>',
        f'<div class="showcase-stats">{stat_html}</div>',
        "</section>",
        '<section class="showcase-section">',
        "<h2>最近更新</h2>",
        recent_updates,
        "</section>",
        '<section class="showcase-section" id="feature-showcase">',
        "<h2>Feature 展区</h2>",
        '<div class="showcase-toolbar">',
        '<label class="showcase-search" for="showcase-search">',
        '<span>搜索</span>',
        '<input id="showcase-search" type="search" placeholder="搜索 Feature、标签或关键字" data-showcase-search>',
        "</label>",
        '<div class="showcase-filter-cluster">',
        '<div class="showcase-filter-group">',
        '<span class="showcase-filter-label">状态</span>',
        f'<div class="showcase-filter-pills" data-showcase-filter-group="status">{status_filters}</div>',
        "</div>",
        '<div class="showcase-filter-group">',
        '<span class="showcase-filter-label">标签</span>',
        f'<div class="showcase-filter-pills" data-showcase-filter-group="tag">{tag_filters}</div>',
        "</div>",
        "</div>",
        "</div>",
        feature_summary,
        '<div class="showcase-grid" data-showcase-grid>',
        featured_cards,
        "</div>",
        feature_empty,
        "</section>",
        '<section class="showcase-section">',
        "<h2>代表页面</h2>",
        representative_pages,
        "</section>",
        '<section class="showcase-section">',
        "<h2>工具资源</h2>",
        _render_tool_resources(),
        "</section>",
        "</main>",
        "</body>",
        "</html>",
    ]
    return inject_reload_script("\n".join(lines).encode("utf-8"))


def _json_mtime_value(m: float) -> Union[int, float]:
    """Encode mtime: integer 0 for no files, else preserve sub-second if needed."""
    if m == 0.0:
        return 0
    return int(m) if m == int(m) else m


class PrototypeRequestHandler(SimpleHTTPRequestHandler):
    """Serves prototypes/, index at /, mtime API, HTML auto-reload injection."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROTOTYPES_ROOT, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        sys.stderr.write("{} - - [{}] {}\n".format(self.address_string(), self.log_date_time_string(), format % args))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        norm = path if path.endswith("/") or path == "" else path.rstrip("/")
        if path == "/" or path == "":
            self._send_index()
            return
        if norm == "/api/mtime":
            self._send_mtime_json()
            return

        rel = path.lstrip("/")
        if not _is_safe_relpath(rel):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        full = os.path.normpath(os.path.join(PROTOTYPES_ROOT, rel))
        if os.path.isdir(full):
            index_html = os.path.join(full, "index.html")
            if os.path.isfile(index_html):
                self._send_html_with_reload(index_html)
                return
        if not _under_root(full, PROTOTYPES_ROOT) or not os.path.isfile(full):
            super().do_GET()
            return
        if full.lower().endswith(".html"):
            self._send_html_with_reload(full)
            return
        super().do_GET()

    def _send_index(self) -> None:
        body = _render_homepage()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_mtime_json(self) -> None:
        m = latest_mtime_under((MASTERS_DIR, FEATURES_DIR, EXAMPLES_DIR, ASSETS_DIR))
        payload = json.dumps({"mtime": _json_mtime_value(m)}).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html_with_reload(self, full_path: str) -> None:
        try:
            with open(full_path, "rb") as f:
                raw = f.read()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = inject_reload_script(raw)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve BKFlow prototypes with live reload.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9080, help="Port (default: 9080)")
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), PrototypeRequestHandler)
    print(
        f"Serving prototypes from {PROTOTYPES_ROOT} at http://{args.host}:{args.port}/",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
        server.server_close()


if __name__ == "__main__":
    main()
