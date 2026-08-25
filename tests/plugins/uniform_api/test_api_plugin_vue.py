"""
TencentBlueKing is pleased to support the open source community by making
BlueKing Flow Engine Service available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License. See http://opensource.org/licenses/MIT.
"""

from pathlib import Path

TASK_V4_SOURCES = [
    "frontend/src/views/task/TaskExecute/ExecuteInfo.vue",
    "frontend/src/views/task/TaskExecute/SideDrawerExecuteInfo.vue",
    "frontend/src/views/task/TaskExecute/RetryNode.vue",
    "frontend/src/views/task/TaskParamEdit.vue",
]
TASK_OPERATION_SOURCE = "frontend/src/views/task/TaskExecute/TaskOperation.vue"
V4_CALLER_SOURCES = [
    "frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue",
    "frontend/src/views/task/TaskExecute/ExecuteInfo.vue",
    "frontend/src/views/task/TaskExecute/SideDrawerExecuteInfo.vue",
    "frontend/src/views/task/TaskExecute/RetryNode.vue",
    "frontend/src/views/task/TaskParamEdit.vue",
    "frontend/src/views/task/TaskExecute/ExecuteInfo/ExecuteInfoForm.vue",
    "frontend/src/views/task/TaskExecute/ExecuteInfoCompoment/ExecuteInfoForm.vue",
]
V4_AUXILIARY_SOURCES = [
    "frontend/src/views/template/TemplateMock/MockSetting/index.vue",
    "frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue",
    "frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue",
    "frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue",
]


def read(relative_path):
    return (Path(__file__).resolve().parents[3] / relative_path).read_text(encoding="utf-8")


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


def test_api_plugin_source_switch_resets_catalog_state():
    """Switching API sources must not reuse the previous source's category or page."""

    source = read("frontend/src/views/template/TemplateEdit/NodeConfig/SelectPanel/apiPlugin.vue")

    assert "handler(val, oldVal)" in source
    assert "const preserveSelection = oldVal === undefined && Boolean(this.apiActive);" in source
    assert "this.resetCatalogState(!preserveSelection);" in source
    assert "resetCatalogState(clearSelection = true)" in source
    assert "this.categoryActive = '';" in source
    assert "this.categoryList = [];" in source
    assert "this.apiList = [];" in source
    assert "this.pagination.current = 1;" in source
    assert "this.pagination.count = 0;" in source
    assert "this.categoryList.some(item => item.id === preferredCategory)" in source


def test_api_plugin_tabs_reuse_plugin_search_and_reload_first_page():
    """API plugin tabs must expose search and reload the remote list from page one."""

    panel_source = read("frontend/src/views/template/TemplateEdit/NodeConfig/SelectPanel/plugin.vue")
    api_source = read("frontend/src/views/template/TemplateEdit/NodeConfig/SelectPanel/apiPlugin.vue")

    assert 'ref="apiPlugin"' in panel_source
    assert "v-if=\"['builtIn', 'thirdParty'].includes(curTab)\"" not in panel_source
    assert '@handleSearch="handleSearch"' in panel_source
    assert "const { apiPlugin } = this.$refs;" in panel_source
    assert "apiPlugin.handleSearch();" in panel_source
    assert "handleSearch()" in api_source
    assert "this.pagination.current = 1;" in api_source
    assert "this.apiList = [];" in api_source
    assert "this.getUniformApiList();" in api_source


def test_uniform_api_does_not_keep_a_parallel_form_renderer():
    frontend_root = Path(__file__).resolve().parents[3] / "frontend" / "src"
    uniform_source = (frontend_root / "components" / "common" / "ApiUniForm.vue").read_text(encoding="utf-8")
    json_schema_source = (frontend_root / "utils" / "jsonFormSchema.js").read_text(encoding="utf-8")

    assert not (frontend_root / "components" / "common" / "ApiCodeEditor.vue").exists()
    assert "ApiCodeEditor" not in uniform_source
    assert "codeEditor:" not in uniform_source
    assert "normalizeStructuredFormSchema" not in json_schema_source


def test_pipeline_tree_save_keeps_legacy_uniform_api_metadata_unchanged():
    """V2/V3 save must preserve the original component metadata and hidden fields."""

    source = read("frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue")
    save_start = source.index("const component = {")
    save_end = source.index("return config", save_start)
    save_source = source[save_start:save_end]

    assert "const isV4 = isV4OpenPlugin(buildUniformApiComponent(this.basicInfo));" in save_source
    assert "const originalApiMeta = this.nodeConfig.component?.['api_meta'];" in save_source
    assert "if (originalApiMeta) component.api_meta = tools.deepClone(originalApiMeta);" in save_source
    assert "if (isV4) {" in save_source
    assert save_source.index("if (isV4) {") < save_source.index("component.api_meta = {")

    form_source = source[source.index("getNodeComponentData(plugin, version)") :]
    assert "const isV4 = isV4OpenPlugin(buildUniformApiComponent(this.basicInfo));" in form_source
    assert form_source.index("if (isV4) {") < form_source.index("data.uniform_api_plugin_version = {")


def test_pipeline_tree_save_preserves_v4_identity_and_execution_fields():
    """V4 save keeps identity and execution fields as explicit pipeline-tree data."""

    source = read("frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue")
    save_source = source[source.index("getNodeComponentData(plugin, version) {") :]
    utility_source = read("frontend/src/utils/uniformApi.js")
    for field in (
        "uniform_api_plugin_id",
        "uniform_api_plugin_source_key",
        "uniform_api_plugin_version",
        "uniform_api_plugin_url",
        "uniform_api_plugin_method",
        "uniform_api_plugin_polling",
        "uniform_api_plugin_callback",
        "uniform_api_plugin_credential_key",
    ):
        assert field in save_source or field in utility_source


def test_template_editor_routes_only_v4_open_plugin_to_unified_loader():
    frontend_root = Path(__file__).resolve().parents[3] / "frontend" / "src"
    node_config = (frontend_root / "views" / "template" / "TemplateEdit" / "NodeConfig" / "NodeConfig.vue").read_text(
        encoding="utf-8"
    )

    assert "buildUniformApiComponent(this.basicInfo)" in node_config
    assert "'loadV4OpenPluginForm'" in node_config
    assert "buildV4PluginDetailRequest" in node_config
    assert "loadUniformApiMeta" in node_config
    assert "loadAtomConfig" in node_config
    assert "loadPluginServiceDetail" in node_config


def test_task_scenes_route_v4_to_unified_loader_and_keep_legacy_actions():
    for path in TASK_V4_SOURCES:
        source = read(path)
        assert "isV4OpenPlugin" in source
        assert "loadV4OpenPluginForm" in source
        assert "loadAtomConfig" in source

    for path in TASK_V4_SOURCES[:2]:
        assert "loadPluginServiceDetail" in read(path)


def test_auxiliary_scenes_use_v4_loader_without_replacing_legacy_paths():
    for path in V4_AUXILIARY_SOURCES:
        source = read(path)
        assert "isV4OpenPlugin" in source
        assert "loadV4OpenPluginForm" in source
        assert "loadAtomConfig" in source


def test_retry_node_receives_task_context_from_task_operation():
    operation = read(TASK_OPERATION_SOURCE)
    retry_node = read("frontend/src/views/task/TaskExecute/RetryNode.vue")

    retry_start = operation.index("<RetryNode")
    retry_block = operation[retry_start : operation.index("/>", retry_start) + 2]
    assert ':space-id="spaceId"' in retry_block
    assert ':template-id="templateId"' in retry_block
    assert ':scope-info="scopeInfo"' in retry_block
    assert "spaceId:" in retry_node
    assert "templateId:" in retry_node
    assert "scopeInfo:" in retry_node
    assert "templateId: this.templateId" in retry_node
    assert "scopeType: this.scopeInfo.scope_type" in retry_node
    assert "scopeValue: this.scopeInfo.scope_value" in retry_node
    assert "this.nodeDetailConfig.template_id" not in retry_node
    assert "this.nodeDetailConfig.scope_type" not in retry_node
    assert "this.nodeDetailConfig.scope_value" not in retry_node


def test_task_param_edit_prefers_explicit_template_id_and_modify_params_forwards_it():
    task_param_edit = read("frontend/src/views/task/TaskParamEdit.vue")
    modify_params = read("frontend/src/views/task/TaskExecute/ModifyParams.vue")

    assert "templateId:" in task_param_edit
    assert "resolveTemplateId" in task_param_edit
    assert "this.templateId !== ''" in task_param_edit
    assert "templateId: this.resolveTemplateId()" in task_param_edit
    assert ':template-id="templateId"' in modify_params


def test_task_detail_async_branches_guard_stale_results_before_state_writes():
    for path in TASK_V4_SOURCES[:2]:
        source = read(path)
        get_node_config_start = source.index("async getNodeConfig")
        get_node_config = source[
            get_node_config_start : source.index("async getSubflowInputsConfig", get_node_config_start)
        ]
        set_fill_record_start = source.index("async setFillRecordField")
        set_fill_record = source[set_fill_record_start : source.index("async getTaskNodeDetail", set_fill_record_start)]

        assert "canApplyPluginDetailResult" in source
        assert "const canApply =" in get_node_config
        assert get_node_config.count("if (!canApply()) return;") >= 4
        assert "recordRequestId" in set_fill_record
        assert "isCurrentRecord" in set_fill_record
        assert set_fill_record.count("if (!isCurrentRecord()) return") >= 2


def test_v4_auxiliary_forms_propagate_non_stale_errors_and_close_loading():
    """V4 辅助页面不能把原生表单加载失败伪装成空表单。"""
    mock_execute = read("frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue")
    mock_setting = read("frontend/src/views/template/TemplateMock/MockSetting/index.vue")
    batch_update = read("frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue")

    assert "this.isConfigLoading = false" in mock_execute
    assert "throw error" in mock_execute
    assert "isPluginFormStale" in mock_execute
    assert "isPluginFormStale" in mock_setting
    assert "isPluginFormStale" in batch_update
    assert "throw error" in mock_setting
    assert "throw e" in batch_update


def test_v4_auxiliary_form_error_entrypoints_and_per_key_requests_are_wired():
    """页面入口必须消费错误，批量表单必须使用按 cache key 的请求身份。"""
    mock_execute = read("frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue")
    mock_setting = read("frontend/src/views/template/TemplateMock/MockSetting/index.vue")
    batch_update = read("frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue")

    assert "async loadFormData" in mock_execute
    assert mock_execute.count("this.loadFormData();") >= 2
    assert "shouldNotifyPluginFormError" in mock_execute
    get_plugin_detail = mock_setting[mock_setting.index("async getPluginDetail") :]
    assert "isPluginFormStale" in get_plugin_detail
    assert "createPluginFormRequestRegistry" in batch_update


def test_variable_form_pages_rebuild_runtime_inputs_from_pipeline_activities():
    task_param_edit = read("frontend/src/views/task/TaskParamEdit.vue")
    mock_execute = read("frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue")
    batch_update = read("frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue")

    for source in (task_param_edit, mock_execute, batch_update):
        assert "buildVariablePluginRuntimeInputs" in source
        assert "inputs: runtimeInputs" not in source


def test_task_param_edit_merges_only_the_selected_v4_object_field():
    source = read("frontend/src/views/task/TaskParamEdit.vue")
    helper_source = read("frontend/src/utils/uniformApi.js")

    assert "mergeV4VariableObjectField" in source
    assert "mergeV4VariableObjectField(schema, formSchema, variable, tagCode)" in source
    assert "mergeV4ObjectSchema(schema, formSchema" not in source
    assert "mergeV4VariableObjectField" in helper_source


def test_all_task5_v4_loaders_receive_their_request_current_guard():
    for path in V4_CALLER_SOURCES:
        source = read(path)
        assert "isCurrent:" in source, path


def test_retry_node_guards_every_async_branch_and_final_state_write():
    source = read("frontend/src/views/task/TaskExecute/RetryNode.vue")
    start = source.index("async getNodeConfig")
    end = source.index("async getSubflowInputsConfig", start)
    get_node_config = source[start:end]

    assert "this.pluginFormRequestId += 1;" in get_node_config
    assert "const canApply =" in get_node_config
    assert get_node_config.count("if (!canApply()) return") >= 6
    assert "finally" in get_node_config
    assert "if (canApply())" in get_node_config


def test_task_param_edit_commits_one_current_generation_and_awaits_all_section_validation():
    source = read("frontend/src/views/task/TaskParamEdit.vue")
    modify_params = read("frontend/src/views/task/TaskExecute/ModifyParams.vue")
    start = source.index("async getFormData")
    end = source.index("setAtomDisable(atomList", start)
    get_form_data = source[start:end]

    assert "formGeneration" in source
    assert "const generation = this.formGeneration" in get_form_data
    assert "isCurrentGeneration" in source
    assert "nextFormSections" in get_form_data
    assert "this.formSections = nextFormSections" in get_form_data
    assert "await this.validate()" in source
    assert "await paramEditComp.validate()" in modify_params


def test_new_atom_config_request_clears_remote_credential_loading_before_each_branch():
    frontend_root = Path(__file__).resolve().parents[3] / "frontend" / "src"
    node_config = (frontend_root / "views" / "template" / "TemplateEdit" / "NodeConfig" / "NodeConfig.vue").read_text(
        encoding="utf-8"
    )

    request_start = node_config.index("this.atomConfigRequestId += 1;")
    request_reset = node_config.index("this.credentialLoading = false;", request_start)
    branch_markers = [
        "if (isV4)",
        "if (isApiPlugin && (currentBasicInfo.metaUrl || currentBasicInfo.meta_url_template))",
        "if (isThird)",
        "await this.loadAtomConfig({ atom: plugin",
    ]

    assert request_start < request_reset
    assert all(request_reset < node_config.index(marker, request_start) for marker in branch_markers)
    assert "withLoadingState" in node_config


def test_template_editor_invalidates_v4_detail_requests_when_node_config_is_destroyed():
    """NodeConfig must invalidate V4 detail/form callbacks before Vue destroys it."""
    node_config = read("frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue")

    assert "isDestroyed: false" in node_config
    assert "beforeDestroy()" in node_config
    destroy_start = node_config.index("beforeDestroy()")
    destroy_block = node_config[destroy_start : node_config.index("mounted()", destroy_start)]
    assert "this.isDestroyed = true;" in destroy_block
    assert "this.atomConfigRequestId += 1;" in destroy_block
    assert "isCurrentPluginDetailRequest" in node_config
    assert "isCurrentPluginDetailRequest(requestId)" in node_config


def test_template_editor_guards_init_default_data_writes_after_async_basic_info_load():
    """initDefaultData must stop all component writes when getNodeBasic resolves after destroy."""
    node_config = read("frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue")
    method_start = node_config.index("async initDefaultData()")
    method_end = node_config.index("async setThirdPartyList", method_start)
    init_default_data = node_config[method_start:method_end]

    await_basic_info = init_default_data.index("const basicInfo = await this.getNodeBasic(nodeConfig);")
    destroy_guard = init_default_data.index("if (this.isDestroyed) return;", await_basic_info)
    basic_info_write = init_default_data.index("this.basicInfo = basicInfo;", destroy_guard)
    next_tick = init_default_data.index("this.$nextTick(() => {", basic_info_write)
    next_tick_guard = init_default_data.index("if (!this.isDestroyed)", next_tick)
    loading_write = init_default_data.index("this.isBaseInfoLoading = false;", next_tick_guard)

    assert await_basic_info < destroy_guard < basic_info_write < next_tick
    assert next_tick < next_tick_guard < loading_write


def test_task_detail_and_mock_keep_legacy_json_schema_and_v4_loader():
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
        assert "import jsonFormSchema from '@/utils/jsonFormSchema.js'" in source, source_path
        assert "jsonFormSchema(resp.data" in source, source_path
        assert "renderFormSchema(resp.data" not in source, source_path
        assert "isV4OpenPlugin" in source, source_path
        assert "loadV4OpenPluginForm" in source, source_path

    for source_path in source_paths[2:]:
        source = source_path.read_text(encoding="utf-8")
        assert "this.setFormsSchema(renderConfig);" in source, source_path


def test_variable_edit_v4_keeps_native_array_field_for_the_existing_renderer():
    source = read("frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue")
    start = source.index("async getAtomConfig")
    v4_start = source.index("if (isV4OpenPlugin(component)) {", start)
    v4_end = source.index("const { api_meta: apiMeta = {} }", v4_start)
    v4_branch = source[v4_start:v4_end]

    assert "selectPluginFormField(result.input, tag)" in v4_branch
    assert "? [field]" in v4_branch
    assert "renderFormSchema" not in v4_branch
    assert ": field;" in v4_branch


def test_mock_task_param_edit_validates_every_section_and_preserves_falsy_values():
    source = read("frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue")

    assert 'ref="renderForm-array"' in source
    assert 'ref="renderForm-object"' in source
    assert "normalizePluginFormRefs" in source
    assert "await validatePluginFormSections" in source
    assert "Object.prototype.hasOwnProperty.call(this.renderData, key)" in source


def test_batch_update_keeps_array_and_object_as_separate_sections():
    source = read("frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue")

    assert "mergePluginFormSections" in source
    assert "sections" in source
    assert ':scheme="section.scheme"' in source
    assert ':ref="`inputParams-${subflow.id}`"' in source
    assert "inputsConfig.length" not in source


def test_mock_setting_builds_runtime_inputs_before_loading_v4_form():
    source = read("frontend/src/views/template/TemplateMock/MockSetting/index.vue")
    init_start = source.index("async initData")
    normal_start = source.index("// 普通任务节点", init_start)
    inputs_assignment = source.index("this.inputsFormData = paramsVal;", normal_start)
    detail_load = source.index("await this.getPluginDetail();", normal_start)

    assert inputs_assignment < detail_load
    assert "runtimeContext" in source
    assert "inputs: this.inputsFormData" in source


def test_node_config_assigns_saved_inputs_before_loading_v4_form():
    """已保存节点必须先回填 inputsParamValue，再请求原生表单。"""
    source = read("frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue")
    init_start = source.index("async initData()")
    non_subflow_start = source.index("if (!this.isSubflow)", init_start)
    non_subflow = source[non_subflow_start : source.index("} else {", non_subflow_start)]

    assert non_subflow.index("this.inputsParamValue = paramsVal;") < non_subflow.index("await this.getPluginDetail();")
    assert non_subflow.rindex("this.inputsRenderConfig = renderConfig;") > non_subflow.index(
        "await this.getPluginDetail();"
    )


def test_new_open_plugin_node_prefers_latest_version():
    source = read("frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue")
    helper = read("frontend/src/utils/uniformApi.js")

    assert "resolveNewOpenPluginVersion" in source
    assert "resolveNewOpenPluginVersion" in helper
    assert "defaultVersion: val.default_version" in source
    assert "latestVersion: val.latest_version" in source
    assert helper.index("if (hasValue(latestVersion))") < helper.index("if (hasValue(defaultVersion))")


def test_task_param_edit_recovers_v4_component_from_pipeline_activities():
    task_param_edit = read("frontend/src/views/task/TaskParamEdit.vue")
    modify_params = read("frontend/src/views/task/TaskExecute/ModifyParams.vue")
    mock_execute = read("frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue")
    batch_update = read("frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue")
    variable_edit = read("frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue")

    for source in (task_param_edit, mock_execute, batch_update, variable_edit):
        assert "resolveVariableSourceComponent" in source

    assert "activities:" in task_param_edit
    assert ':activities="activities"' in modify_params
    assert "this.activities = pipelineData.activities" in modify_params
    assert "disableFields" in task_param_edit
    assert "disablePluginFormFields" in task_param_edit
    assert "paramEditComp.disableFields" in modify_params
    assert "paramEditComp.renderConfig.find" not in modify_params


def _output_params_block(source):
    start = source.index("<OutputParams")
    end = source.index("/>", start)
    return source[start:end]


def test_execute_record_passes_native_output_form_into_output_params():
    """任务详情执行记录必须把原生输出 scheme/values/flag 交给 OutputParams。"""
    main_record = read("frontend/src/views/task/TaskExecute/ExecuteInfo/ExecuteRecord.vue")
    drawer_record = read("frontend/src/views/task/TaskExecute/ExecuteInfoCompoment/ExecuteRecord.vue")

    main_output = _output_params_block(main_record)
    drawer_output = _output_params_block(drawer_record)

    assert "executeInfo.outputRenderConfig" in main_output
    assert "executeInfo.outputRenderData" in main_output
    assert "executeInfo.isRenderOutputForm" in main_output
    assert "executeRecord.outputRenderConfig" in drawer_output
    assert "executeRecord.outputRenderData" in drawer_output
    assert "executeRecord.isRenderOutputForm" in drawer_output


def test_output_params_renders_array_and_object_native_forms():
    """OutputParams 在 isRenderOutputForm 时走 RenderForm / JSON Schema，而不是只渲染 KV 表格。"""
    for path in (
        "frontend/src/views/task/TaskExecute/ExecuteInfo/OutputParams.vue",
        "frontend/src/views/task/TaskExecute/ExecuteInfoCompoment/OutputParams.vue",
    ):
        source = read(path)
        assert "hasPluginFormFields" in source
        assert "isRenderOutputForm" in source
        assert "RenderForm" in source
        assert "jsonschema-form" in source
        assert 'v-if="shouldRenderNativeForm && !isShowOutputOrigin"' in source


def test_task_detail_copies_output_form_onto_execute_record():
    """setFillRecordField 必须把 outputRenderConfig / Data / flag 写到执行记录上。"""
    for path in TASK_V4_SOURCES[:2]:
        source = read(path)
        set_fill_record_start = source.index("async setFillRecordField")
        set_fill_record = source[set_fill_record_start : source.index("async getTaskNodeDetail", set_fill_record_start)]
        assert "buildOutputRenderData" in source
        assert "outputRenderConfig" in set_fill_record
        assert "outputRenderData" in set_fill_record
        assert "isRenderOutputForm" in set_fill_record


def test_variable_edit_rebuilds_runtime_inputs_from_pipeline_activities():
    """变量编辑给 getInput() 的上下文必须包含源节点全部字段，不能只传当前变量。"""
    source = read("frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue")
    start = source.index("if (isV4OpenPlugin(component)) {")
    v4_branch = source[start : source.index("const { api_meta: apiMeta = {} }", start)]

    assert "buildVariablePluginRuntimeInputs" in v4_branch
    assert "inputs: this.renderData" not in v4_branch


def test_variable_edit_v2_does_not_index_missing_source_activity():
    """源节点被删除时，V2/V3 变量编辑不得再直接索引 activities[sourceNodeId]。"""
    source = read("frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue")
    start = source.index("const { api_meta: apiMeta = {} }")
    v2_branch = source[start : source.index("this.isApiPlugin = false")]

    assert "this.activities[sourceNodeId].component.version" not in v2_branch
    assert "sourceActivity" in v2_branch
    assert "sourceActivity?.component?.version" in v2_branch
    assert "|| version" in v2_branch


def test_retry_node_reads_outputs_and_state_from_node_payload():
    """重试页必须从 nodeInfo.data 读取 outputs/state，而不是从 {result, data} 信封根上读。"""
    source = read("frontend/src/views/task/TaskExecute/RetryNode.vue")
    start = source.index("async getNodeConfig")
    v4_branch = source[start : source.index("if (atomFilter.isConfigExists", start)]

    assert "resolveNodeExecutionPayload" in source
    assert "outputs: this.nodeInfo.outputs" not in v4_branch
    assert "state: this.nodeInfo.state" not in v4_branch
    assert "execution.outputs" in v4_branch
    assert "execution.state" in v4_branch
