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
//  const url = atomClassify === 'component' ? `api/plugin/${atomFile}/` : `api/template/variable/${atomFile}/`;
export const fetchBkFlowInnerPluginDetail = (code, version) => {
  return axios.get(`api/plugin/${code}/`, {
    params: { space_id: store.state.spaceId, version },
  }).then((response) => {
    return response.data.data;
  });
};

/**
 * 获取bkflow内置插件列表（全量标准插件）
 */
export const fetchBkFlowInnerPluginList = () => axios.get('api/plugin/', {
  params: { space_id: store.state.spaceId },
}).then(response => response.data.data.filter(item => item.code !== 'subprocess_plugin'));

/**
 * 获取bkflow第三方插件对应SaaS应用的app详情
 */
// {
//     plugin_code: code,
//     plugin_version: version,
//     with_app_detail: true,
// }
export const fetchBkFlowThirdPartyPluginAppDetail = (pluginCode) => {
  return axios.get('/api/plugin_service/detail/', {
    params: { plugin_code: pluginCode, plugin_version: '', with_app_detail: true },
  }).then(response => response.data);
};

/**
 * 获取变量引用详情(全局变量)
 */
export const fetchVariableRef = params => axios.post('api/template/analysis_constants_ref/', params).then(response => response.data);

/**
 * 获取流程变量类型
 */
export const fetchCustomVariableTypes = () => axios.get('api/template/variable/').then(response => response.data.data);

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
  return axios.post(`/api/template/admin/create_task/${spaceId}/`, params).then((response) => {
    return response.data;
  });
};
/**
 * 操作流程任务
 */
// export const executeFlowTask = (params) => {
//   const { task_id: taskId, action } = params;
//   return axios.post(`task/operate_task/${taskId}/${action}/`, {
//     space_id: store.state.spaceId,
//     ...params,
//   }).then((response) => {
//     return response.data;
//   });
// };

/**
 * 获取控制配置列表(无鉴权获取空间基本配置信息)
 */
export const fetchControlConfig = () => axios.get('/api/space/config/get_control_config/').then(response => response.data);
/**
 * 检查空间配置项的值
 */
export const checkSpaceConfig = (scopeValue, params) => {
  return axios.get(`/api/space/config/${scopeValue}/check_space_config/`, { params }).then(response => response.data);
};

/**
 * 自动排版（画布美化）
 */
export const drawPipeline = (params) => {
  return axios.post('api/template/draw_pipeline/', params).then(response => response.data.data);
};

/**
 * 获取流程草稿详情
 * @param id 流程id
 * @returns 流程草稿详情
 */
export const fetchFlowDraftDetail = id => axios.get(`/api/template/${id}/get_draft_template/`, {
  params: { space_id: store.state.spaceId },
}).then(response => response.data);

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
  return axios.get(`/api/template/${id}/preview_task_tree/`, requestData).then(response => response.data);
};

