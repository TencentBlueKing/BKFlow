from pathlib import Path
import re


ROOT = Path("prototypes")
SHARED = ROOT / "masters" / "_shared"
OVERLAYS = ROOT / "masters" / "overlays"
MASTERS = ROOT / "masters"
ASSETS = ROOT / "assets"
LIST_MASTER = MASTERS / "list-page"
CONFIG_MASTER = MASTERS / "config-page"
ENGINE_MASTER = MASTERS / "engine-panel"
DECISION_MASTER = MASTERS / "decision-editor"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_shared_shells_and_overlay_files_exist():
    required = [
        SHARED / "space-shell.html",
        SHARED / "system-shell.html",
        SHARED / "plugin-shell.html",
        OVERLAYS / "README.md",
        OVERLAYS / "dialogs.html",
        OVERLAYS / "sidesliders.html",
    ]

    for path in required:
        assert path.is_file(), path


def test_shared_shells_keep_common_header_and_distinct_sidebars():
    shells = {
        "space": SHARED / "space-shell.html",
        "system": SHARED / "system-shell.html",
        "plugin": SHARED / "plugin-shell.html",
    }

    for name, path in shells.items():
        text = read_text(path)
        assert "<header" in text
        assert "bk-prototype-shell" in text
        assert "bk-prototype-topbar" in text
        assert f'data-nav-group="{name}"' in text
        assert "data-toggle-target" in text
        assert "data-toggle-class" in text

    assert "空间选择区" in read_text(shells["space"])
    assert "空间侧栏" in read_text(shells["space"])
    assert "系统管理侧栏" in read_text(shells["system"])
    assert "插件侧栏" in read_text(shells["plugin"])


def test_shared_shell_data_page_items_map_to_real_panels():
    shells = {
        "space-shell": read_text(SHARED / "space-shell.html"),
        "system-shell": read_text(SHARED / "system-shell.html"),
        "plugin-shell": read_text(SHARED / "plugin-shell.html"),
    }

    for shell_name, text in shells.items():
        data_pages = set(re.findall(r'data-page="([^"]+)"', text))
        panel_ids = set(re.findall(r'<section class="bk-page-panel" id="([^"]+)"', text))
        panel_ids.update(re.findall(r'<div class="bk-page-panel" id="([^"]+)"', text))

        assert data_pages, shell_name
        assert data_pages <= panel_ids, (shell_name, data_pages - panel_ids)


def test_overlay_masters_cover_required_dialog_and_sideslider_patterns():
    dialogs = read_text(OVERLAYS / "dialogs.html")
    sidesliders = read_text(OVERLAYS / "sidesliders.html")

    assert "删除确认" in dialogs
    assert "发布确认" in dialogs
    assert "异常提示" in dialogs
    assert "表单编辑侧滑" in sidesliders
    assert "只读详情侧滑" in sidesliders


def test_shared_assets_expose_generic_interaction_hooks():
    css = read_text(ASSETS / "bkflow-prototype.css")
    js = read_text(ASSETS / "bkflow-prototype.js")

    for token in [
        ".bk-prototype-shell",
        ".bk-right-panel",
        ".bk-save-button.is-disabled",
        ".bk-save-button.is-enabled",
    ]:
        assert token in css

    for token in [
        "data-nav-group",
        "data-toggle-target",
        "data-toggle-class",
        "data-right-panel-open",
        "data-right-panel-close",
        "data-save-target",
        "data-open",
        "data-close",
        "data-page",
        ".bk-page-panel",
    ]:
        assert token in js


def test_shared_assets_do_not_expose_old_toolkit_only_behaviors():
    js = read_text(ASSETS / "bkflow-prototype.js")

    forbidden_tokens = [
        "data-sortable",
        "data-filter",
        "data-dropdown",
        "data-required",
        "data-pattern",
        "data-notify",
        "data-href",
        "data-step",
        ".bk-switcher",
        ".bk-select-trigger",
        "data-sortable",
        "data-filter",
        "data-dropdown",
    ]

    for token in forbidden_tokens:
        assert token not in js


def test_shared_assets_include_minimal_data_page_switching_logic():
    js = read_text(ASSETS / "bkflow-prototype.js")

    assert "data-page" in js
    assert ".bk-page-panel" in js
    assert "hidden = panel.id !== pageId" in js


def test_shared_shell_user_menus_do_not_use_old_interactions():
    shell_texts = [
        read_text(SHARED / "space-shell.html"),
        read_text(SHARED / "system-shell.html"),
        read_text(SHARED / "plugin-shell.html"),
    ]

    for text in shell_texts:
        assert "data-notify" not in text


def test_task4_master_files_exist_and_have_readmes():
    required = [
        LIST_MASTER / "README.md",
        LIST_MASTER / "template.html",
        LIST_MASTER / "states" / "empty.html",
        LIST_MASTER / "states" / "error.html",
        LIST_MASTER / "states" / "bulk-actions.html",
        CONFIG_MASTER / "README.md",
        CONFIG_MASTER / "template.html",
        CONFIG_MASTER / "states" / "dirty.html",
        ENGINE_MASTER / "README.md",
        ENGINE_MASTER / "template.html",
        DECISION_MASTER / "README.md",
        DECISION_MASTER / "template.html",
    ]

    for path in required:
        assert path.is_file(), path

    assert "list-oriented admin pages" in read_text(LIST_MASTER / "README.md")
    assert "long configuration forms" in read_text(CONFIG_MASTER / "README.md")
    assert "request/response debugging panels" in read_text(ENGINE_MASTER / "README.md")
    assert "decision rule editing flows" in read_text(DECISION_MASTER / "README.md")


def test_list_page_master_contract_covers_table_toolbar_states_and_pagination():
    template = read_text(LIST_MASTER / "template.html")
    empty_state = read_text(LIST_MASTER / "states" / "empty.html")
    error_state = read_text(LIST_MASTER / "states" / "error.html")
    bulk_actions = read_text(LIST_MASTER / "states" / "bulk-actions.html")

    for token in [
        '<div class="bk-toolbar">',
        "搜索",
        "筛选",
        "<th>状态</th>",
        "<th>操作</th>",
        'class="bk-pagination"',
    ]:
        assert token in template

    assert "暂无数据" in empty_state
    assert "加载失败" in error_state
    for state_text in [empty_state, error_state]:
        for token in [
            '<div class="bk-toolbar">',
            '<input class="bk-search-input"',
            '<div class="bk-select"',
            "筛选状态",
        ]:
            assert token in state_text
    assert "批量" in bulk_actions
    assert "已选" in bulk_actions


def test_config_page_master_contract_covers_long_form_code_area_and_dirty_state():
    template = read_text(CONFIG_MASTER / "template.html")
    dirty_state = read_text(CONFIG_MASTER / "states" / "dirty.html")

    template_titles = re.findall(r'<div class="section-title">(.*?)</div>', template)
    dirty_titles = re.findall(r'<div class="section-title">(.*?)</div>', dirty_state)
    template_labels = re.findall(r'<label class="bk-form-label">(.*?)</label>', template)
    dirty_labels = re.findall(r'<label class="bk-form-label">(.*?)</label>', dirty_state)

    for token in [
        "基础配置",
        "代码配置",
        "<pre",
        "<code",
        "bk-save-button is-disabled",
    ]:
        assert token in template

    for token in [
        "未保存",
        "修改后保存",
        "bk-save-button is-enabled",
    ]:
        assert token in dirty_state

    assert dirty_titles == template_titles
    assert dirty_labels == template_labels


def test_engine_panel_master_contract_covers_request_parameter_response_and_actions():
    template = read_text(ENGINE_MASTER / "template.html")

    for token in [
        "请求区",
        "参数区",
        "响应区",
        "发送",
        "重置",
        'class="bk-button bk-button-primary" disabled',
    ]:
        assert token in template


def test_decision_editor_master_contract_covers_basic_info_rules_empty_state_and_footer_actions():
    template = read_text(DECISION_MASTER / "template.html")

    for token in [
        "基础信息",
        "规则配置",
        "暂无规则",
        "底部操作",
        "保存",
        "取消",
        "bk-exception",
    ]:
        assert token in template

    for token in [
        "规则 1：",
        "规则 2：",
        'class="rule-card"',
    ]:
        assert token not in template
