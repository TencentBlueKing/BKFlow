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


def _touch_html(path: Path, content: str = "<html></html>") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collect_feature_catalog_reads_meta_and_featured_pages(tmp_path):
    """有元数据时应读取首页展示字段并跳过无效代表页。"""
    catalog = _load_catalog()
    feature_dir = tmp_path / "features" / "demo-feature"
    _touch_html(feature_dir / "pages" / "flow-edit.html")
    _touch_html(feature_dir / "pages" / "task-detail-complete.html")
    _touch_html(feature_dir / "pages" / "unused.html")
    (feature_dir / "feature.meta.json").write_text(
        json.dumps(
            {
                "title": "示例原型",
                "summary": "覆盖流程编辑与任务详情。",
                "status": "可评审",
                "tags": ["流程编辑", "任务详情"],
                "coverTheme": "mixed-admin",
                "order": 7,
                "featuredPages": [
                    {
                        "path": "pages/flow-edit.html",
                        "title": "流程编辑页",
                        "summary": "画布与节点抽屉。",
                        "pageType": "流程编辑",
                    },
                    {
                        "path": "pages/task-detail-complete.html",
                        "title": "任务详情页",
                        "summary": "执行状态与日志。",
                        "pageType": "任务详情",
                    },
                    {
                        "path": "pages/missing.html",
                        "title": "应被跳过",
                        "summary": "不存在的页面。",
                        "pageType": "流程编辑",
                    },
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
    assert items[0]["page_count"] == 3
    assert [page["title"] for page in items[0]["featured_pages"]] == ["流程编辑页", "任务详情页"]
    assert items[0]["featured_pages"][0]["page_type"] == "流程编辑"


def test_collect_feature_catalog_falls_back_when_meta_missing(tmp_path):
    """缺少元数据时应使用默认展示信息与代表页。"""
    catalog = _load_catalog()
    feature_dir = tmp_path / "features" / "demo-fallback"
    _touch_html(feature_dir / "pages" / "alpha.html")
    _touch_html(feature_dir / "pages" / "beta.html")
    _touch_html(feature_dir / "pages" / "gamma.html")

    items = catalog.collect_feature_catalog(str(tmp_path / "features"))

    assert items[0]["slug"] == "demo-fallback"
    assert items[0]["status"] == "待补充"
    assert items[0]["summary"] == "尚未补充首页摘要"
    assert items[0]["cover_theme"] == "mixed-admin"
    assert items[0]["page_count"] == 3
    assert [page["path"] for page in items[0]["featured_pages"]] == ["pages/alpha.html", "pages/beta.html"]


def test_collect_feature_catalog_sorts_by_order_then_updated_at_desc_and_skips_legacy(tmp_path):
    """应按 order 升序、更新时间降序排序，并跳过 _legacy。"""
    catalog = _load_catalog()
    features_dir = tmp_path / "features"

    older = features_dir / "alpha"
    newer = features_dir / "beta"
    legacy = features_dir / "_legacy" / "old"

    _touch_html(older / "pages" / "index.html")
    _touch_html(newer / "pages" / "index.html")
    _touch_html(legacy / "pages" / "index.html")

    (older / "feature.meta.json").write_text(
        json.dumps({"title": "Alpha", "order": 1}, ensure_ascii=False), encoding="utf-8"
    )
    (newer / "feature.meta.json").write_text(
        json.dumps({"title": "Beta", "order": 1}, ensure_ascii=False), encoding="utf-8"
    )
    (legacy / "feature.meta.json").write_text(
        json.dumps({"title": "Legacy", "order": 0}, ensure_ascii=False), encoding="utf-8"
    )

    old_time = 1_700_000_000
    new_time = 1_700_000_100
    Path(older / "pages" / "index.html").touch()
    Path(newer / "pages" / "index.html").touch()
    import os

    os.utime(older, (old_time, old_time))
    os.utime(older / "pages" / "index.html", (old_time, old_time))
    os.utime(older / "feature.meta.json", (old_time, old_time))
    os.utime(newer, (new_time, new_time))
    os.utime(newer / "pages" / "index.html", (new_time, new_time))
    os.utime(newer / "feature.meta.json", (new_time, new_time))

    items = catalog.collect_feature_catalog(str(features_dir))

    assert [item["slug"] for item in items] == ["beta", "alpha"]
    assert all(item["slug"] != "_legacy" for item in items)


def test_collect_feature_catalog_falls_back_when_meta_is_not_object(tmp_path):
    """元数据不是 JSON object 时应回退到默认展示信息。"""
    catalog = _load_catalog()
    feature_dir = tmp_path / "features" / "demo-bad-meta"
    _touch_html(feature_dir / "pages" / "alpha.html")
    _touch_html(feature_dir / "pages" / "beta.html")
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "feature.meta.json").write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    items = catalog.collect_feature_catalog(str(tmp_path / "features"))

    assert items[0]["slug"] == "demo-bad-meta"
    assert items[0]["status"] == "待补充"
    assert items[0]["summary"] == "尚未补充首页摘要"
    assert [page["path"] for page in items[0]["featured_pages"]] == ["pages/alpha.html", "pages/beta.html"]


def test_collect_showcase_stats_counts_meta_updates(tmp_path):
    """首页统计的更新时间应纳入 feature.meta.json 的变更。"""
    catalog = _load_catalog()
    features_dir = tmp_path / "features"
    masters_dir = tmp_path / "masters"
    feature_dir = features_dir / "demo-feature"

    _touch_html(feature_dir / "pages" / "alpha.html")
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta_path = feature_dir / "feature.meta.json"
    meta_path.write_text(json.dumps({"title": "Demo"}, ensure_ascii=False), encoding="utf-8")
    _touch_html(masters_dir / "template.html")

    html_time = 1_700_000_000
    meta_time = 1_700_000_200
    import os

    os.utime(feature_dir / "pages" / "alpha.html", (html_time, html_time))
    os.utime(meta_path, (meta_time, meta_time))
    os.utime(masters_dir / "template.html", (html_time, html_time))

    stats = catalog.collect_showcase_stats(str(features_dir), str(masters_dir))

    assert stats["feature_count"] == 1
    assert stats["feature_page_count"] == 1
    assert stats["master_page_count"] == 1
    assert stats["html_page_count"] == 2
    assert stats["updated_at"] == meta_time
