/**
 * 插件管理接口
 */
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    // 插件概要
    getPluginSummary({}, data) {
      return axios.get('api/plugin_catalog/plugins/summary/', {
        params: { space_id: data.space_id },
      }).then(response => response.data.data);
    },
    // 查询新插件策略
    getStrategy({}, data) {
      return axios.get('api/plugin_catalog/strategy/', {
        params: { space_id: data.space_id },
      }).then(response => response.data.data);
    },
    // 插件列表（status / plugin_type / source_key / keyword 为数组型参数，重复传参）
    getPluginList({}, data) {
      return axios.get('api/plugin_catalog/plugins/', {
        params: data,
      }).then(response => response.data.data);
    },
    // 空间推荐列表
    getRecommendList({}, data) {
      return axios.get('api/plugin_catalog/plugins/recommend/', {
        params: { space_id: data.space_id },
      }).then(response => response.data.data);
    },
    // 编辑插件
    updatePlugin({}, data) {
      const { plugin_id: pluginId, ...params } = data;
      return axios.post(`api/plugin_catalog/plugins/${pluginId}/`, params)
        .then(response => response.data.data);
    },
    // 编辑未启用配置
    updateDisableConfig({}, data) {
      const { plugin_id: pluginId, ...params } = data;
      return axios.post(`api/plugin_catalog/plugins/${pluginId}/reason/`, params)
        .then(response => response.data.data);
    },
    // 更新单个插件状态
    updatePluginStatus({}, data) {
      const { plugin_id: pluginId, ...params } = data;
      return axios.post(`api/plugin_catalog/plugins/${pluginId}/status/`, params)
        .then(response => response.data.data);
    },
    // 批量更新状态
    batchUpdatePluginStatus({}, data) {
      return axios.post('api/plugin_catalog/plugins/batch_status/', data)
        .then(response => response.data.data);
    },
    // 批量移动目录
    batchUpdatePluginCategory({}, data) {
      return axios.post('api/plugin_catalog/plugins/batch_category/', data)
        .then(response => response.data.data);
    },
    // 目录批量管理页数据
    getDirectoryManagePage({}, data) {
      return axios.get('api/plugin_catalog/directories/manage_data/', {
        params: { space_id: data.space_id },
      }).then(response => response.data.data);
    },
    // 目录批量管理页保存
    saveDirectoryManage({}, data) {
      return axios.post('api/plugin_catalog/directories/manage_save/', data)
        .then(response => response.data.data);
    },
    // 删除分类
    deleteCategory({}, data) {
      return axios.post('api/plugin_catalog/directories/execute_delete/', data)
        .then(response => response.data.data);
    },
    // 删除分类影响评估
    getCategoryDeleteImpact({}, data) {
      return axios.post('api/plugin_catalog/directories/preview_delete/', data)
        .then(response => response.data.data);
    },
    // AI 分类建议
    aiClassify({}, data) {
      return axios.post('api/plugin_catalog/plugins/ai_classify/', data)
        .then(response => response.data.data);
    },
    // AI 智能分类
    aiSmartClassify({}, data) {
      const { space_id: spaceId, ...body } = data;
      return axios.post('api/plugin_catalog/directories/ai_classify/', body, {
        params: { space_id: spaceId },
      }).then(response => response.data.data);
    },
    // 保存新插件策略
    savePluginStrategy({}, data) {
      return axios.post('api/plugin_catalog/strategy/', data)
        .then(response => response.data.data);
    },
    // 启用来源分组
    getStrategySources({}, data) {
      return axios.get('api/plugin_catalog/strategy/sources/', {
        params: data || {},
      }).then(response => response.data.data);
    },
    // 取消推荐
    cancelRecommend({}, data) {
      return axios.delete(`api/plugin_catalog/plugins/${data.plugin_id}/recommend/`, {
        params: { space_id: data.space_id },
      }).then(response => response.data.data);
    },
    // 插件详情
    getPluginDetail({}, data) {
      return axios.get(`api/plugin_catalog/plugins/${data.plugin_id}/detail/`, {
        params: { space_id: data.space_id },
      }).then(response => response.data.data);
    },
    // 插件引用流程列表
    getPluginReferences({}, data) {
      const { plugin_id: pluginId, ...query } = data;
      return axios.get(`api/plugin_catalog/plugins/${pluginId}/references/`, {
        params: query,
      }).then(response => response.data.data);
    },
  },
};
