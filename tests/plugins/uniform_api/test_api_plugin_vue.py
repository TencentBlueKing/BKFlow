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


def test_template_editor_uses_render_form_for_uniform_api_plugins():
    frontend_root = Path(__file__).resolve().parents[3] / "frontend" / "src"
    node_config = (frontend_root / "views" / "template" / "TemplateEdit" / "NodeConfig" / "NodeConfig.vue").read_text(
        encoding="utf-8"
    )
    input_params = (frontend_root / "views" / "template" / "TemplateEdit" / "NodeConfig" / "InputParams.vue").read_text(
        encoding="utf-8"
    )

    assert "import renderFormSchema from '@/utils/renderFormSchema.js'" in node_config
    assert "import jsonFormSchema from '@/utils/jsonFormSchema.js'" not in node_config
    assert "return renderFormSchema(resp.data" in node_config
    assert ':api-inputs="apiInputs"' in node_config
    assert "apiInputs:" in input_params
    assert "if (this.isApiPlugin)" in input_params
    assert "const schema = this.apiInputs.find(item => item.key === form)" in input_params


def test_task_detail_and_mock_use_render_form_for_uniform_api_plugins():
    frontend_root = Path(__file__).resolve().parents[3] / "frontend" / "src"
    source_paths = [
        frontend_root / "views" / "task" / "TaskExecute" / "ExecuteInfo.vue",
        frontend_root / "views" / "task" / "TaskExecute" / "SideDrawerExecuteInfo.vue",
        frontend_root / "views" / "task" / "TaskExecute" / "ExecuteInfo" / "ExecuteInfoForm.vue",
        frontend_root / "views" / "task" / "TaskExecute" / "ExecuteInfoCompoment" / "ExecuteInfoForm.vue",
        frontend_root / "views" / "template" / "TemplateMock" / "MockSetting" / "index.vue",
    ]

    for source_path in source_paths:
        source = source_path.read_text(encoding="utf-8")
        assert "import renderFormSchema from '@/utils/renderFormSchema.js'" in source, source_path
        assert "renderFormSchema(resp.data" in source, source_path
        assert "jsonFormSchema(resp.data" not in source, source_path

    for source_path in source_paths[2:4]:
        source = source_path.read_text(encoding="utf-8")
        assert "this.setFormsSchema(renderConfig);" not in source, source_path
        assert "Array.isArray(this.inputs)" in source, source_path
        assert "this.hooked = this.getFormsHookState();" in source, source_path
