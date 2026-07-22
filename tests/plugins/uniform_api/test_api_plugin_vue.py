"""
TencentBlueKing is pleased to support the open source community by making
BlueKing Flow Engine Service available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License. See http://opensource.org/licenses/MIT.
"""

from pathlib import Path


def test_each_api_plugin_list_owns_its_scroll_handler():
    """Every rendered source tab binds pagination to its own scroll container."""

    source_path = (
        Path(__file__).resolve().parents[3]
        / "frontend"
        / "src"
        / "views"
        / "template"
        / "TemplateEdit"
        / "NodeConfig"
        / "SelectPanel"
        / "apiPlugin.vue"
    )
    source = source_path.read_text(encoding="utf-8")

    assert '@scroll="handleApiPluginScroll"' in source
    assert "querySelector('.api-list')" not in source


def test_api_uniform_registers_monaco_code_editor():
    frontend_root = Path(__file__).resolve().parents[3] / "frontend" / "src"
    uniform_source = (frontend_root / "components" / "common" / "ApiUniForm.vue").read_text(encoding="utf-8")
    editor_source = (frontend_root / "components" / "common" / "ApiCodeEditor.vue").read_text(encoding="utf-8")

    assert "import ApiCodeEditor from './ApiCodeEditor.vue'" in uniform_source
    assert "createForm({" in uniform_source
    assert "codeEditor: ApiCodeEditor" in uniform_source
    assert "<FullCodeEditor" in editor_source
    assert "@input=\"$emit('input', $event)\"" in editor_source
