import re
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path("prototypes/features/bkflow-engine-admin-prototype-overhaul")
README = ROOT / "README.md"
INDEX = ROOT / "index.html"
ASSET_JS = Path("prototypes/assets/bkflow-prototype.js")

SPACE_PAGES = [
    "template-list.html",
    "flow-view.html",
    "flow-edit.html",
    "flow-debug.html",
    "task-list.html",
    "debug-task-list.html",
    "task-detail-complete.html",
    "task-detail-failed.html",
    "decision-list.html",
    "decision-editor.html",
    "space-config.html",
    "credential-list.html",
    "label-list.html",
    "statistics-exception.html",
]
SYSTEM_PAGES = [
    "space-config-list.html",
    "module-config-list.html",
]
PLUGIN_PAGES = [
    "plugin-list.html",
]

EXPECTED_PAGE_FILES = {
    "Space": [ROOT / "pages" / "space" / name for name in SPACE_PAGES],
    "System": [ROOT / "pages" / "system" / name for name in SYSTEM_PAGES],
    "Plugin": [ROOT / "pages" / "plugin" / name for name in PLUGIN_PAGES],
}

EXPECTED_SECTION_LINKS = {
    "Space": [f"./pages/space/{name}" for name in SPACE_PAGES],
    "System": [f"./pages/system/{name}" for name in SYSTEM_PAGES],
    "Plugin": [f"./pages/plugin/{name}" for name in PLUGIN_PAGES],
}

CRITICAL_INDEX_LINKS = [
    "./pages/space/flow-edit.html",
    "./pages/space/task-detail-complete.html",
    "./pages/system/module-config-list.html",
    "./pages/plugin/plugin-list.html",
]

REPRESENTATIVE_PAGES = [
    ROOT / "pages" / "space" / "flow-edit.html",
    ROOT / "pages" / "space" / "task-detail-complete.html",
    ROOT / "pages" / "system" / "module-config-list.html",
    ROOT / "pages" / "plugin" / "plugin-list.html",
]

TOP_NAV_LANDING_LINKS = {
    "space": {
        "space": "template-list.html",
        "system": "../system/space-config-list.html",
        "plugin": "../plugin/plugin-list.html",
    },
    "system": {
        "space": "../space/template-list.html",
        "system": "space-config-list.html",
        "plugin": "../plugin/plugin-list.html",
    },
    "plugin": {
        "space": "../space/template-list.html",
        "system": "../system/space-config-list.html",
        "plugin": "plugin-list.html",
    },
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_sections(index_text: str) -> dict[str, str]:
    pattern = re.compile(
        r'<section class="group-card">.*?<h2>(Space|System|Plugin)</h2>.*?<ul class="page-list">(.*?)</ul>',
        re.S,
    )
    return {title: body for title, body in pattern.findall(index_text)}


def extract_top_nav_links(page_text: str) -> Dict[str, Tuple[Optional[str], bool]]:
    items: Dict[str, Tuple[Optional[str], bool]] = {}
    pattern = re.compile(
        r'<li(?P<attrs>[^>]*)class="[^"]*bk-navigation-header-nav-item[^"]*"(?P<rest>[^>]*)>(?P<body>.*?)</li>',
        re.S,
    )
    for match in pattern.finditer(page_text):
        attrs = match.group(0)
        group_match = re.search(r'data-nav-group="([^"]+)"', attrs)
        if not group_match:
            continue
        nav_link_match = re.search(r'data-nav-link="([^"]+)"', attrs)
        items[group_match.group(1)] = (
            nav_link_match.group(1) if nav_link_match else None,
            re.search(r'class="[^"]*\bactive\b', attrs) is not None,
        )
    return items


def count_readme_masters(readme_text: str) -> int:
    match = re.search(r"## Masters Used\n(.*?)\n## Page Entries", readme_text, re.S)
    assert match, "Masters Used section missing"
    return len(re.findall(r"^- `", match.group(1), re.M))


def test_feature_readme_links_spec_and_plan():
    text = read_text(README)

    assert "Spec: `docs/specs/2026-04-21-bkflow-engine-admin-prototype-overhaul-design.md`" in text
    assert "Plan: `docs/plans/2026-04-21-bkflow-engine-admin-prototype-overhaul.md`" in text


def test_feature_index_groups_pages_by_space_system_and_plugin():
    text = read_text(INDEX)
    sections = extract_sections(text)

    assert set(sections) == {"Space", "System", "Plugin"}

    for group, expected_links in EXPECTED_SECTION_LINKS.items():
        section = sections[group]
        for link in expected_links:
            assert link in section, (group, link)


def test_expected_feature_pages_exist():
    for group, paths in EXPECTED_PAGE_FILES.items():
        for path in paths:
            assert path.is_file(), (group, path)


def test_index_links_to_critical_representative_pages():
    text = read_text(INDEX)

    for href in CRITICAL_INDEX_LINKS:
        assert href in text, href


def test_representative_pages_define_cross_page_top_nav_targets_and_shared_js_supports_them():
    js = read_text(ASSET_JS)

    for token in [
        'getAttribute("data-nav-link")',
        "window.location.href = navLink",
        'navItem.classList.contains("active")',
    ]:
        assert token in js

    for path in REPRESENTATIVE_PAGES:
        page_text = read_text(path)
        nav_items = extract_top_nav_links(page_text)
        group_name = path.parent.name

        assert set(nav_items) == {"space", "system", "plugin"}, path
        assert sum(1 for _, is_active in nav_items.values() if is_active) == 1, path

        for group, expected_link in TOP_NAV_LANDING_LINKS[group_name].items():
            actual_link, _ = nav_items[group]
            assert actual_link == expected_link, (path, group, actual_link, expected_link)


def test_debug_task_detail_pages_preserve_debug_route_backlink_and_source_template_context():
    expected_tokens = [
        'class="bk-task-detail-back" href="debug-task-list.html">← 返回调试任务列表</a>',
        '源调试模板 <a href="flow-debug.html">/template/mock/true/2166/</a>',
    ]

    for path in [
        ROOT / "pages" / "space" / "task-detail-complete.html",
        ROOT / "pages" / "space" / "task-detail-failed.html",
    ]:
        text = read_text(path)
        for token in expected_tokens:
            assert token in text, (path, token)


def test_index_hero_master_count_matches_feature_readme_inventory():
    readme_text = read_text(README)
    index_text = read_text(INDEX)

    master_count = count_readme_masters(readme_text)

    assert master_count == 11
    assert f"<strong>Masters</strong> {master_count} referenced" in index_text


def test_representative_pages_use_nested_asset_paths():
    expected_tokens = [
        'href="../../../../assets/bkflow-prototype.css"',
        'src="../../../../assets/bkflow-prototype.js"',
        'src="../../../../assets/icons/bkflow-logo.svg"',
    ]

    for path in REPRESENTATIVE_PAGES:
        text = read_text(path)
        for token in expected_tokens:
            assert token in text, (path, token)
