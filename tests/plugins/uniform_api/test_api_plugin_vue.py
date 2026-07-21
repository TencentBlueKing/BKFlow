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
