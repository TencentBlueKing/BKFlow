import json
from pathlib import Path
import re


def test_required_root_directories_exist():
    required = [
        Path("prototypes/masters"),
        Path("prototypes/masters/_shared"),
        Path("prototypes/features"),
        Path("prototypes/features/_legacy"),
        Path("prototypes/examples"),
    ]

    for path in required:
        assert path.exists(), path


def test_required_readmes_exist():
    required = [
        Path("prototypes/masters/README.md"),
        Path("prototypes/masters/_shared/README.md"),
        Path("prototypes/features/README.md"),
        Path("prototypes/features/_legacy/README.md"),
        Path("prototypes/examples/README.md"),
        Path("prototypes/features/_legacy/sops-open-plugin/README.md"),
        Path("prototypes/features/_legacy/space-variable-manage/README.md"),
        Path("prototypes/features/_legacy/node-output-viewer/README.md"),
    ]

    for path in required:
        assert path.is_file(), path


def test_showcase_homepage_contract_resources_and_meta_shape():
    required = [
        Path("prototypes/assets/bkflow-showcase.css"),
        Path("prototypes/assets/bkflow-showcase.js"),
    ]

    for path in required:
        assert path.is_file(), path

    features_root = Path("prototypes/features")
    feature_dirs = [
        path
        for path in sorted(features_root.iterdir(), key=lambda item: item.name)
        if path.is_dir() and not path.name.startswith("_") and not path.name.startswith(".")
    ]

    assert feature_dirs, "expected at least one active feature directory"

    for feature_dir in feature_dirs:
        meta_path = feature_dir / "feature.meta.json"
        assert meta_path.is_file(), meta_path

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        expected_keys = {"title", "summary", "status", "tags", "coverTheme", "order", "featuredPages"}

        assert isinstance(meta, dict), feature_dir
        for key in expected_keys:
            assert key in meta, (feature_dir, key)

        assert isinstance(meta["title"], str) and meta["title"].strip(), feature_dir
        assert isinstance(meta["summary"], str) and meta["summary"].strip(), feature_dir
        assert isinstance(meta["status"], str) and meta["status"].strip(), feature_dir
        assert isinstance(meta["tags"], list) and meta["tags"], feature_dir
        assert all(isinstance(tag, str) and tag.strip() for tag in meta["tags"]), feature_dir
        assert isinstance(meta["coverTheme"], str) and meta["coverTheme"].strip(), feature_dir
        assert isinstance(meta["order"], int), feature_dir
        assert isinstance(meta["featuredPages"], list) and meta["featuredPages"], feature_dir

        for page in meta["featuredPages"]:
            assert isinstance(page, dict), (feature_dir, page)
            for key in ["path", "title", "summary", "pageType"]:
                assert key in page, (feature_dir, key)
                assert isinstance(page[key], str) and page[key].strip(), (feature_dir, key)
            feature_root = feature_dir.resolve()
            resolved = (feature_dir / page["path"]).resolve()
            assert feature_root in resolved.parents or resolved == feature_root, (feature_dir, page["path"])
            assert resolved.is_file(), (feature_dir, page["path"])
            assert resolved.suffix == ".html", (feature_dir, page["path"])


def test_examples_only_keep_reference_pages():
    example_dir = Path("prototypes/examples")
    files = sorted(path.name for path in example_dir.iterdir() if path.is_file())
    assert files == ["README.md", "component-showcase.html"], files


def test_legacy_archive_contains_migrated_pages():
    expected = [
        Path("prototypes/features/_legacy/sops-open-plugin/index.html"),
        Path("prototypes/features/_legacy/sops-open-plugin/main-flow.html"),
        Path("prototypes/features/_legacy/sops-open-plugin/space-open-plugin-management.html"),
        Path("prototypes/features/_legacy/sops-open-plugin/task-plugin-error-state.html"),
        Path("prototypes/features/_legacy/sops-open-plugin/template-plugin-selection.html"),
        Path("prototypes/features/_legacy/space-variable-manage/README.md"),
        Path("prototypes/features/_legacy/space-variable-manage/index.html"),
        Path("prototypes/features/_legacy/node-output-viewer/README.md"),
        Path("prototypes/features/_legacy/node-output-viewer/index.html"),
    ]

    for path in expected:
        assert path.is_file(), path


def test_legacy_archive_relative_links_resolve():
    archive_root = Path("prototypes/features/_legacy")
    pattern = re.compile(r'(?:href|data-href)="([^"#][^"]*)"')

    for html_path in archive_root.rglob("*.html"):
        text = html_path.read_text(encoding="utf-8")
        for target in pattern.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "javascript:")):
                continue
            resolved = (html_path.parent / target).resolve()
            assert resolved.exists(), (html_path, target)


def test_obsolete_flat_pages_are_removed():
    removed = [
        Path("prototypes/base.html"),
        Path("prototypes/output/.gitkeep"),
        Path("prototypes/output/sops-open-plugin-main-flow.html"),
        Path("prototypes/output/sops-open-plugin-space-open-plugin-management.html"),
        Path("prototypes/output/sops-open-plugin-task-plugin-error-state.html"),
        Path("prototypes/output/sops-open-plugin-template-plugin-selection.html"),
        Path("prototypes/output/space-variable-manage.html"),
        Path("prototypes/output/node-output-viewer-proposal-v1.html"),
        Path("prototypes/examples/composite-page.html"),
        Path("prototypes/examples/detail-page.html"),
        Path("prototypes/examples/flow-edit.html"),
        Path("prototypes/examples/form-slider.html"),
        Path("prototypes/examples/list-page.html"),
        Path("prototypes/examples/tab-page.html"),
        Path("prototypes/examples/task-detail.html"),
    ]

    for path in removed:
        assert not path.exists(), path


def test_retired_directories_are_removed():
    removed = [
        Path("prototypes/cache"),
        Path("prototypes/metadata"),
        Path("prototypes/renderers"),
        Path("prototypes/output"),
    ]

    for path in removed:
        assert not path.exists(), path


def test_directory_readmes_describe_contract():
    checks = {
        Path("prototypes/masters/README.md"): [
            "source of truth",
            "page-type masters",
            "stable states",
            "_shared",
            "docs/specs",
            "docs/plans",
        ],
        Path("prototypes/masters/_shared/README.md"): [
            "shared scaffolding",
            "does not preview independently",
            "reuse-only",
            "Do not put delivery pages",
        ],
        Path("prototypes/features/README.md"): [
            "feature slug",
            "spec and one plan",
            "feature.meta.json",
            "homepage showcase contract",
        ],
        Path("prototypes/features/_legacy/README.md"): [
            "archive-only",
            "migrated historical feature material",
            "prototypes/features/<feature-slug>/",
            "Do not put shared masters",
        ],
        Path("prototypes/examples/README.md"): [
            "reference only",
            "component-showcase.html",
            "not for delivery",
            "docs/specs",
            "docs/plans",
        ],
        Path(".ai/skills/prototype-generator/SKILL.md"): [
            "BKFlow 原型展厅",
            "feature.meta.json",
            "features/<slug>/",
            "首页展示所需的卡片信息",
            "不要只生成 `README.md` 和 `index.html`",
        ],
    }

    for path, expected_snippets in checks.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        text = "\n".join(lines)
        for line in expected_snippets:
            assert line in text, (path, line)


def test_prototypes_readme_describes_showcase_homepage_sources():
    text = Path("prototypes/README.md").read_text(encoding="utf-8")
    expected_snippets = [
        "BKFlow 原型展厅",
        "根路径 `/`",
        "feature.meta.json",
        "首页元数据",
        "首页展示来源",
        "不再把根首页描述成简单目录索引",
    ]

    for snippet in expected_snippets:
        assert snippet in text, snippet
