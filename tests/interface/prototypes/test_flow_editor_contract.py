from pathlib import Path
import re


ROOT = Path("prototypes")
FLOW_EDITOR = ROOT / "masters" / "flow-editor"
STATES = FLOW_EDITOR / "states"
ASSETS = ROOT / "assets"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_flow_editor_master_files_exist():
    required = [
        FLOW_EDITOR / "README.md",
        FLOW_EDITOR / "template.html",
        STATES / "node-selected.html",
        STATES / "save-ready.html",
        STATES / "publish-confirm.html",
        STATES / "mock-debug-confirm.html",
    ]

    for path in required:
        assert path.is_file(), path


def test_flow_editor_readme_describes_canvas_drawer_and_release_flow():
    text = read_text(FLOW_EDITOR / "README.md")

    for token in [
        "graph-style flow editing pages",
        "single-click selection",
        "double-click node configuration drawer",
        "global variables floating layer",
        "save / publish / debug header actions",
    ]:
        assert token in text


def test_flow_editor_template_covers_header_canvas_toolbar_drawer_and_confirm_layers():
    template = read_text(FLOW_EDITOR / "template.html")

    for token in [
        "编辑流程",
        "返回流程列表",
        "流程版本",
        "草稿",
        "1.0.0",
        "保存",
        "发布",
        "调试",
        "流程画布",
        "节点悬浮工具条",
        "节点配置",
        "基础信息",
        "输入参数",
        "输出参数",
        "全局变量",
        "_system.task_name",
        "_system.task_id",
        "版本描述",
        "确定保存Mock数据并去执行调试?",
        'data-node-select="flow-editor-main"',
        'data-node-toolbar="#flow-node-toolbar"',
        'data-dblopen="flow-node-config-drawer"',
        'data-save-target="#flow-editor-save"',
        'data-disable-target="#flow-editor-save"',
        'data-enable-target="#flow-editor-publish"',
        'data-open="flow-publish-dialog"',
        'data-open="flow-mock-debug-dialog"',
        'data-open="flow-global-vars-dialog"',
    ]:
        assert token in template


def test_flow_editor_state_pages_capture_selected_save_ready_publish_and_mock_debug_steps():
    node_selected = read_text(STATES / "node-selected.html")
    save_ready = read_text(STATES / "save-ready.html")
    publish_confirm = read_text(STATES / "publish-confirm.html")
    mock_debug_confirm = read_text(STATES / "mock-debug-confirm.html")

    assert "bk-flow-node is-selected" in node_selected
    assert "bk-flow-node-toolbar is-visible" in node_selected
    assert "flow-node-config-drawer" in node_selected
    assert "bk-sideslider is-show" not in node_selected
    assert 'data-open="flow-mock-debug-dialog"' in node_selected
    assert ">发布蓝鲸作业</span>" in node_selected
    assert ">节点悬浮工具条</span>" not in node_selected

    assert "bk-save-button is-enabled" in save_ready
    assert 'id="flow-editor-publish"' in save_ready
    assert "is-disabled" in save_ready

    assert 'id="flow-publish-dialog"' in publish_confirm
    assert "bk-dialog is-show" in publish_confirm
    assert "1.0.0" in publish_confirm
    assert "版本描述" in publish_confirm

    assert 'id="flow-mock-debug-dialog"' in mock_debug_confirm
    assert "bk-dialog is-show" in mock_debug_confirm
    assert "确定保存Mock数据并去执行调试?" in mock_debug_confirm
    assert 'data-open="flow-mock-debug-dialog"' in mock_debug_confirm

    publish_button = re.search(
        r'<button[^>]*id="flow-editor-publish"[^>]*>',
        mock_debug_confirm,
        re.DOTALL,
    )
    assert publish_button, mock_debug_confirm
    assert "is-disabled" in publish_button.group(0)
    assert "disabled" in publish_button.group(0)


def test_shared_assets_expose_minimal_flow_editor_hooks():
    css = read_text(ASSETS / "bkflow-prototype.css")
    js = read_text(ASSETS / "bkflow-prototype.js")

    for token in [
        ".bk-flow-editor",
        ".bk-flow-editor-header",
        ".bk-flow-canvas",
        ".bk-flow-node",
        ".bk-flow-node-toolbar",
        ".bk-flow-node-toolbar.is-visible",
        ".bk-flow-vars-float",
    ]:
        assert token in css

    for token in [
        "data-node-select",
        "data-node-toolbar",
        "data-dblopen",
        "data-enable-target",
        "data-disable-target",
        'removeAttribute("disabled")',
        'setAttribute("disabled", "disabled")',
    ]:
        assert token in js

    assert "node.closest(" in js
    assert ".bk-flow-editor" in js
    assert ".bk-flow-editor-shell" in js
    assert "root.querySelectorAll(" in js
    assert '[data-node-select="' in js
    assert "toolbarSelector" in js
    assert "document.querySelectorAll('[data-node-select=\"" not in js
    assert "document.querySelectorAll(toolbarSelector)" not in js
