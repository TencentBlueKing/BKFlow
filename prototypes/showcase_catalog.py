"""Catalog helpers for the BKFlow prototypes showcase homepage."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_STATUS = "待补充"
DEFAULT_SUMMARY = "尚未补充首页摘要"
DEFAULT_THEME = "mixed-admin"

_DEFAULT_ORDER = 10**9
_REPRESENTATIVE_PAGE_LIMIT = 2


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _humanize_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title() or slug


def _iter_feature_dirs(features_dir: Path) -> list[Path]:
    if not features_dir.is_dir():
        return []
    return [
        item
        for item in sorted(features_dir.iterdir(), key=lambda path: path.name)
        if item.is_dir() and not item.name.startswith("_") and not item.name.startswith(".")
    ]


def _iter_html_pages(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    pages = [path for path in root.rglob("*.html") if path.is_file()]
    pages.sort(key=lambda path: str(path.relative_to(root)).replace(os.sep, "/"))
    return pages


def _latest_mtime(paths: list[Path]) -> float:
    latest = 0.0
    for path in paths:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > latest:
            latest = mtime
    return latest


def _resolve_feature_page(feature_dir: Path, rel_path: str) -> Path | None:
    candidate = (feature_dir / rel_path).resolve()
    try:
        feature_root = feature_dir.resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(feature_root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _normalize_feature_page(feature_dir: Path, page: dict[str, Any]) -> dict[str, Any] | None:
    rel_path = str(page.get("path") or "").strip()
    if not rel_path:
        return None
    resolved = _resolve_feature_page(feature_dir, rel_path)
    if resolved is None:
        return None
    title = str(page.get("title") or resolved.stem).strip() or resolved.stem
    summary = str(page.get("summary") or "").strip()
    page_type = str(page.get("pageType") or page.get("page_type") or "").strip()
    normalized = {
        "path": rel_path.replace("\\", "/"),
        "title": title,
        "summary": summary,
        "page_type": page_type,
    }
    return normalized


def _default_feature_pages(feature_dir: Path) -> list[dict[str, Any]]:
    pages = []
    for path in _iter_html_pages(feature_dir)[:_REPRESENTATIVE_PAGE_LIMIT]:
        rel_path = path.relative_to(feature_dir).as_posix()
        pages.append(
            {
                "path": rel_path,
                "title": path.stem,
                "summary": "",
                "page_type": "",
            }
        )
    return pages


def collect_feature_catalog(features_dir: str) -> list[dict]:
    """Collect normalized showcase data for feature directories."""

    base_dir = Path(features_dir)
    catalog: list[dict[str, Any]] = []

    for feature_dir in _iter_feature_dirs(base_dir):
        meta_path = feature_dir / "feature.meta.json"
        meta = _safe_read_json(meta_path) if meta_path.is_file() else {}
        html_pages = _iter_html_pages(feature_dir)
        valid_featured_pages: list[dict[str, Any]] = []

        featured_pages = meta.get("featuredPages", [])
        for page in featured_pages if isinstance(featured_pages, list) else []:
            if not isinstance(page, dict):
                continue
            normalized_page = _normalize_feature_page(feature_dir, page)
            if normalized_page is not None:
                valid_featured_pages.append(normalized_page)

        if not valid_featured_pages:
            valid_featured_pages = _default_feature_pages(feature_dir)

        catalog.append(
            {
                "slug": feature_dir.name,
                "title": str(meta.get("title") or _humanize_slug(feature_dir.name)).strip() or feature_dir.name,
                "summary": str(meta.get("summary") or DEFAULT_SUMMARY).strip() or DEFAULT_SUMMARY,
                "status": str(meta.get("status") or DEFAULT_STATUS).strip() or DEFAULT_STATUS,
                "cover_theme": str(meta.get("coverTheme") or DEFAULT_THEME).strip() or DEFAULT_THEME,
                "order": meta.get("order") if isinstance(meta.get("order"), int) else _DEFAULT_ORDER,
                "tags": list(meta.get("tags")) if isinstance(meta.get("tags"), list) else [],
                "page_count": len(html_pages),
                "updated_at": _latest_mtime(html_pages + [meta_path] if meta_path.is_file() else html_pages),
                "featured_pages": valid_featured_pages,
            }
        )

    catalog.sort(key=lambda item: (item["order"], -item["updated_at"], item["slug"]))
    return catalog


def collect_showcase_stats(features_dir: str, masters_dir: str) -> dict:
    """Collect lightweight showcase summary metrics."""

    features_root = Path(features_dir)
    masters_root = Path(masters_dir)
    feature_dirs = _iter_feature_dirs(features_root)
    feature_pages = [path for feature_dir in feature_dirs for path in _iter_html_pages(feature_dir)]
    meta_files = [feature_dir / "feature.meta.json" for feature_dir in feature_dirs if (feature_dir / "feature.meta.json").is_file()]
    master_pages = _iter_html_pages(masters_root)

    return {
        "feature_count": len(feature_dirs),
        "feature_page_count": len(feature_pages),
        "master_page_count": len(master_pages),
        "html_page_count": len(feature_pages) + len(master_pages),
        "updated_at": max(_latest_mtime(feature_pages), _latest_mtime(meta_files), _latest_mtime(master_pages)),
    }
