/**
 * 模板编辑页面的 API 请求管理
 */
import axios from 'axios';
import store from '@/store/index.js';
/**
 * 获取流程详情
 * @param {string|number} id - 模板 ID
 */
export const fetchFlowDetail = id => axios.get(`/api/template/${id}/`).then(response => response.data.data);

/**
 * 保存流程
 */
export const saveFlow = (id, params) => {
  const headers = {};
  headers['X-HTTP-Method-Override'] = 'PATCH';
  return axios.put(`api/template/${id}/`, {
    ...params,
    space_id: store.state.spaceId,
  }, {
    headers,
  }).then(response => response.data);
};

/**
 * 获取系统变量(内置变量)列表
 */
export const fetchSystemVariables = () => axios.get('api/template/variable/system_variable/').then(response => Object.values(response.data.data));

/**
 * 获取空间流程配置
 */
export const fetchSpaceFlowConfig = id => axios.get(`/api/template/${id}/get_space_related_configs/`).then(response => response.data.data);

/**
 * 获取bkflow第三方插件tag下的插件列表
 */
export const fetchBkFlowThirdPartyPluginList = tag => axios.get('api/bk_plugin/', {
  params: { tag, space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 获取bkflow第三方插件tags(获取第三方插件分类)
 */
export const fetchBkFlowThirdPartyPluginTags = () => axios.get('/api/plugin_service/tags/').then(response => response.data.data);

/**
 * 获取所有插件分组列表以及分组下的列表详情
 * @returns {Promise<Array>}
 */
export const fetchAllPluginGroups = () => fetchBkFlowThirdPartyPluginTags().then((bkflowTags) => {
  const innerGroup = {
    code_name: 'INNER',
    id: 0,
    name: '内置',
    priority: 1,
  };
  return [{
    id: 'bkflow',
    name: 'bkflow',
    alias: '插件',
    iconUrl: '',
    properties: {},
    children: [innerGroup, ...bkflowTags],
  }];
});

/**
 * 搜索bkflow第三方插件
 * @param {string} searchTerm - 搜索关键词
 */
export const searchBkFlowThirdPartyPlugins = searchTerm => axios.get('api/bk_plugin/', {
  params: { search_term: searchTerm, space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 获取bkflow第三方插件元数据
 */
export const fetchBkFlowThirdPartyPluginMeta = pluginCode => axios.get('/api/plugin_service/meta/', {
  params: { plugin_code: pluginCode },
}).then(response => response.data.data);

/**
 * 获取bkflow第三方插件详情
 */
export const fetchBkFlowThirdPartyPluginDetail = (pluginCode, pluginVersion) => axios.get('/api/plugin_service/detail/', {
  params: { plugin_code: pluginCode, plugin_version: pluginVersion, with_app_detail: true },
}).then(response => response.data.data);

/**
 * 获取bkflow内置插件详情
 */
export const fetchBkFlowInnerPluginDetail = (code, version) => axios.get(`api/plugin/${code}/`, {
  params: { space_id: store.state.spaceId, version },
}).then(response => response.data.data);

/**
 * 获取内置变量详情
 */
export const fetchInnerVariableDetail = code => axios.get(`api/template/variable/${code}/`, {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 获取bkflow内置插件列表（全量标准插件）
 */
export const fetchBkFlowInnerPluginList = () => axios.get('api/plugin/', {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data.filter(item => !['subprocess_plugin', 'subcanvas_plugin'].includes(item.code)));

/**
 * 获取子流程/子画布插件详情
 */
export const fetchSubprocessOutput = (params) => {
  const { code, version } = params;
  return axios.get(`/api/plugin/${code}/`, {
    params: { space_id: store.state.spaceId, version } },).then(response => response.data.data);
};

/**
 * 获取bkflow第三方插件对应SaaS应用的app详情
 */
// {
//     plugin_code: code,
//     plugin_version: version,
//     with_app_detail: true,
// }
export const fetchBkFlowThirdPartyPluginAppDetail = (pluginCode, pluginVersion) => axios.get('/api/plugin_service/detail/', {
  params: { plugin_code: pluginCode, plugin_version: pluginVersion, with_app_detail: true },
}).then(response => response.data);

/**
 * 获取变量引用详情(全局变量)
 */
export const fetchVariableRef = params => axios.post('api/template/analysis_constants_ref/', params).then(response => response.data);

/**
 * 获取流程变量类型
 */
export const fetchCustomVariableTypes = () => axios.get('api/template/variable/').then(response => response.data);

/**
 * 获取流程操作记录
 */
export const fetchFlowOperateRecord = id => axios.get(`/api/template/${id}/get_template_operation_record/`, {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 创建流程任务
 */
export const createFlowTask = (params) => {
  const { spaceId } = store.state;
  return axios.post(`/api/template/admin/create_task/${spaceId}/`, params).then(response => response.data);
};
/**
 * 操作流程任务
 */
export const executeFlowTask = (params) => {
  const { task_id: taskId, action } = params;
  return axios.post(`task/operate_task/${taskId}/${action}/`, {
    space_id: store.state.spaceId,
  }).then(response => response.data);
};

/**
 * 任务节点操作
 */
export const operateTaskNode = (params) => {
  const ACTION_TO_OPERATION = {
    retry: 'retry',
    skip: 'skip',
    forceFail: 'forced_fail',
    resume: 'callback',
    gatewaySkip: 'skip_exg',
  };
  const { task_id: taskId, node_id: nodeId, action, data, operation: customOperation } = params;
  const operation = customOperation ?? ACTION_TO_OPERATION[action] ?? action;
  return axios.post(`task/operate_node/${taskId}/node/${nodeId}/${operation}/`, {
    space_id: store.state.spaceId,
    ...data,
  }).then(response => response.data);
};

/**
 * 强制终止流程任务
 */
export const revokeFlowTask = (params) => {
  const { task_id: taskId } = params;
  return axios.post(`task/operate_task/${taskId}/revoke/`, {
    space_id: store.state.spaceId,
  }).then(response => response.data);
};

/**
 * 获取任务状态
 */
export const fetchTaskState = ({ task_id: taskId }) => axios.get(`task/get_task_states/${taskId}/`, {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 获取流程任务详情
 */
export const getFlowTaskDetail = ({ task_id: taskId }) => axios.get(`task/get_task_detail/${taskId}/`, {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 获取流程任务节点详情
 */
export const fetchTaskNodeDetail = (params) => {
  const { task_id: taskId, node_id: nodeId, component_code } = params;
  return axios.get(`task/get_task_node_detail/${taskId}/node/${nodeId}/`, {
    params: {
      component_code,
      space_id: store.state.spaceId,
    },
  }).then(response => response.data);
};

/**
 * 获取任务节点快照
 */
export const fetchTaskNodeSnapshot = params => axios.get(`task/get_node_snapshot_config/${params.task_id}/${params.node_id}/`, {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 获取执行记录日志
 */
export const fetchTaskNodeLog = (params) => {
  const { task_id: taskId, node_id: nodeId, version } = params;
  return axios.get(`task/get_task_node_log/${taskId}/${nodeId}/${version}/`, {
    params: {
      space_id: store.state.spaceId,
    },
  }).then(response => response.data);
};
/**
 * 创建mock任务
 */
export const createMockDebugTask = (params) => {
  const { template_id: templateId, ...payload } = params;
  return axios.post(`api/template/${templateId}/create_mock_task/`, {
    space_id: store.state.spaceId,
    ...payload,
  }).then(response => response.data);
};

/**
 * 获取控制配置列表(无鉴权获取空间基本配置信息)
 */
export const fetchControlConfig = () => axios.get('/api/space/config/get_control_config/').then(response => response.data);
/**
 * 检查空间配置项的值
 */
export const checkSpaceConfig = (scopeValue, params) => axios.get(`/api/space/config/${scopeValue}/check_space_config/`, { params }).then(response => response.data);

/**
 * 自动排版（画布美化）
 */
export const drawPipeline = params => axios.post('api/template/draw_pipeline/', params).then(response => response.data.data);

/**
 * 获取流程草稿详情
 * @param id 流程id
 * @returns 流程草稿详情
 */
export const fetchFlowDraftDetail = id => axios.get(`/api/template/${id}/get_draft_template/`, {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 获取流程某个版本下的详情
 */
export const fetchFlowDetailByVersion = (id, version) => {
  const requestData = {
    is_all_nodes: true,
    space_id: store.state.spaceId,
  };
  if (version !== undefined && version !== null) {
    requestData.version = version;
  }
  return axios.post(`/api/template/${id}/preview_task_tree/`, requestData).then(response => response.data.data);
};

/**
 * 获取子流程模板列表
 */
export const fetchSubflowTemplateList = (params) => {
  const { limit, offset, keyword } = params;
  return axios.get('api/template/list_template/', {
    params: {
      limit,
      offset,
      ...(keyword ? { name__icontains: keyword } : {}),
      empty_scope: 1,
      space_id: store.state.spaceId,
      ...store.state.template.scopeInfo,
    },
  }).then(response => response.data.data);
};

/**
 * 获取标签列表（二级标签通过 parent_id 递归拉取）
 */
export const fetchLabelList = params => axios.get('/api/label/', { params }).then(response => response.data.data);

/**
 * 新建标签
 */
export const createLabel = params => axios.post('/api/label/', params).then(response => response.data);

/**
 * 获取流程版本快照列表（limit=-1 取全量）
 */
export const fetchFlowVersionList = templateId => axios.get('/api/template/snapshot/', {
  params: {
    template_id: Number(templateId),
    space_id: store.state.spaceId,
    limit: -1,
  },
}).then(response => response.data.data);

/**
 * 计算下一个建议版本号
 */
export const calculateNextFlowVersion = templateId => axios.get(`/api/template/${templateId}/calculate_version/`, {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data);

/**
 * 发布流程版本
 */
export const releaseFlowVersion = (templateId, params) => axios.post(`/api/template/${templateId}/release_template/`, {
  version: params.version,
  desc: params.desc || '',
  space_id: store.state.spaceId,
}).then(response => response.data.data);

/**
 * 回滚版本
 */
export const rollbackFlowVersion = (templateId, params) => axios.post(`/api/template/${templateId}/rollback_template/`, {
  version: params.version,
  space_id: store.state.spaceId,
}).then(response => response.data.data);


/**
 * 获取调试上下文（调试唯一事实源，页面加载与轮询均调用）
 */
export const fetchDebugContext = templateId => axios.get('/api/template/debug/context/', {
  params: { template_id: Number(templateId) },
}).then(response => response.data.data);

/**
 * 获取调试输入参数 schema（全局调试输入侧滑表单）
 */
export const fetchDebugInputSchema = templateId => axios.get('/api/template/debug/input_schema/', {
  params: { template_id: Number(templateId) },
}).then(response => response.data.data);

/**
 * 获取调试重置影响面
 */
export const fetchDebugResetImpact = templateId => axios.post('/api/template/debug/reset_impact/', {
  template_id: Number(templateId),
}).then(response => response.data.data);

/**
 * 更新节点调试 Mock 配置（保存/启停节点 mock 输出）
 */
export const updateNodeDebugMock = (params) => {
  const body = {
    template_id: Number(params.templateId),
    node_id: params.nodeId,
    enable: params.enable,
  };
  if (params.mockResult !== undefined) body.mock_result = params.mockResult;
  if (params.mockOutputs !== undefined) body.mock_outputs = params.mockOutputs;
  if (params.mockError !== undefined) body.mock_error = params.mockError;
  return axios.post('/api/template/debug/node_mock/', body).then(response => response.data.data);
};

/**
 * 单步调试运行节点（mode: real 实际执行 / mock 使用 mock 输出）
 */
export const runNodeDebugStep = (params) => {
  const body = {
    template_id: Number(params.templateId),
    node_id: params.nodeId,
    mode: params.mode,
  };
  if (params.inputOverrides !== undefined) body.input_overrides = params.inputOverrides;
  if (params.mockResult !== undefined) body.mock_result = params.mockResult;
  if (params.mockOutputs !== undefined) body.mock_outputs = params.mockOutputs;
  if (params.mockError !== undefined) body.mock_error = params.mockError;
  return axios.post('/api/template/debug/step_run/', body).then(response => response.data.data);
};

/**
 * 全局调试运行（整条流程）
 */
export const runGlobalDebug = params => axios.post('/api/template/debug/global_run/', {
  template_id: Number(params.templateId),
  inputs: params.inputs,
}).then(response => response.data.data);

/**
 * 终止调试（nodeId 传值时为单节点维度终止）
 */
export const terminateDebug = (params) => {
  const body = { template_id: Number(params.templateId) };
  if (params.nodeId !== undefined) body.node_id = params.nodeId;
  return axios.post('/api/template/debug/terminate/', body).then(response => response.data.data);
};

/**
 * 重置调试结果（nodeIds 传值时重置指定节点）
 */
export const resetDebugResult = (params) => {
  const body = { template_id: Number(params.templateId) };
  if (params.nodeIds !== undefined) body.node_ids = params.nodeIds;
  return axios.post('/api/template/debug/reset/', body).then(response => response.data.data);
};
