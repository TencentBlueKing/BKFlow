/**
* Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
* Edition) available.
* Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
* Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* http://opensource.org/licenses/MIT
* Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
* an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
* specific language governing permissions and limitations under the License.
*/
import axios from 'axios';

const project = {
  namespaced: true,
  state: {
    project_id: window.DEFAULT_PROJECT_ID,
    bizId: '',
    projectName: '',
    userProjectList: [], // 用户有权限的项目列表
    timezone: window.TIMEZONE,
    config: {}, // 用户在项目下的配置
    commonConfig: {}, // 公共流程管理的配置
    authActions: [],
  },
  mutations: {
    setUserProjectList(state, data) {
      state.userProjectList = data;
    },
    setProjectId(state, id) {
      let projectId = id;
      if (typeof id !== 'number') {
        projectId = isNaN(Number(id)) || id === '' ? '' : Number(id);
      }
      state.project_id = projectId;
    },
    setBizId(state, id) {
      state.bizId = id;
    },
    setTimeZone(state, data) {
      state.timezone = data;
    },
    setProjectName(state, data) {
      state.projectName = data;
    },
    setProjectActions(state, data) {
      state.authActions = data;
    },
    setProjectConfig(state, data) {
      state.config = { ...state.config, ...data };
    },
    setCommonConfig(state, data) {
      state.commonConfig = { ...state.config, ...data };
    },
  },
  actions: {
    // 更改用户的默认项目
    changeDefaultProject({}, id) {
      return axios.post(`core/api/change_default_project/${id}/`).then(response => response.data);
    },
    // 加载用户有权限的项目列表
    loadUserProjectList({ commit }, data = {}) {
      const { params = {}, config = {} } = data;
      return axios.get('api/v3/user_project/', { params, ...config }).then((response) => {
        // 不传limit代表拉取全量列表
        if (!('limit' in params)) { // 拉全量项目时更新项目列表，区分项目管理页面的分页数据
          commit('setUserProjectList', response.data.data);
          return { results: response.data.data };
        }
        return response.data.data;
      });
    },
    // 获取常用业务
    loadCommonProject() {
      return axios.get('api/v3/common_project/').then(response => response.data.data);
    },
    // 获取环境变量列表
    loadEnvVariableList({}, params) {
      return axios.get('api/v3/project_constants/', { params }).then(response => response.data);
    },
    // 新增环境变量
    createEnvVariable({}, data) {
      return axios.post('api/v3/project_constants/', data).then(response => response.data);
    },
    // 更新环境变量
    updateEnvVariable({}, data) {
      const { id } = data;
      return axios.put(`api/v3/project_constants/${id}`, data).then(response => response.data);
    },
    // 删除环境变量
    deleteEnvVariable({}, id) {
      return axios.delete(`api/v3/project_constants/${id}/`).then(response => response.data);
    },

    createProject({}, data) {
      const { name, time_zone, desc } = data;

      return axios.post('api/v3/project/', {
        name,
        time_zone,
        desc,
      }).then(response => response.data);
    },
    loadProjectDetail({}, id) {
      return axios.get(`api/v3/project/${id}/`).then(response => response.data.data);
    },
    // 更新项目详情
    updateProject({}, data) {
      const { id, name, time_zone, desc, is_disable } = data;
      return axios.patch(`api/v3/project/${id}/`, {
        name,
        time_zone,
        desc,
        is_disable,
      }).then(response => response.data.data);
    },
    getProjectConfig({}, id) {
      return axios.get(`api/v3/project_config/${id}/`).then(response => response.data);
    },
    updateProjectConfig({}, params) {
      const { id, executor_proxy, executor_proxy_exempts } = params;
      return axios.patch(`api/v3/project_config/${id}/`, { executor_proxy, executor_proxy_exempts }).then(response => response.data);
    },
    getProjectStaffGroupList({}, params) {
      return axios.get('api/v3/staff_group/', { params }).then(response => response.data);
    },
    createProjectStaffGroup({}, params) {
      return axios.post('api/v3/staff_group/', params.data).then(response => response.data);
    },
    updateProjectStaffGroup({}, params) {
      const { id, data } = params;
      return axios.put(`api/v3/staff_group/${id}/`, data).then(response => response.data);
    },
    delProjectStaffGroup({}, id) {
      return axios.delete(`api/v3/staff_group/${id}/`).then(response => response.data);
    },
    // 查询项目下用户可编辑的模板标签
    getProjectLabels({}, id) {
      return axios.get('api/v3/new_label/', {
        params: { project_id: id },
      }).then(response => response.data);
    },
    // 查询项目下支持的模板标签（包含默认标签）
    getProjectLabelsWithDefault({}, id) {
      return axios.get('api/v3/new_label/list_with_default_labels/', {
        params: { project_id: id },
      }).then(response => response.data);
    },
    createTemplateLabel({}, data) {
      return axios.post('api/v3/new_label/', data).then(response => response.data);
    },
    updateTemplateLabel({}, data) {
      return axios.put(`api/v3/new_label/${data.id}/`, data).then(response => response.data);
    },
    delTemplateLabel({}, id) {
      return axios.delete(`api/v3/new_label/${id}/`).then(response => response.data);
    },
    getLabelsCitedCount({}, payload) {
      const { ids, project_id } = payload;
      return axios.get('api/v3/new_label/get_label_template_count/', {
        params: { label_ids: ids, project_id },
      }).then(response => response.data);
    },
    getUserProjectConfigOptions({}, data) {
      const { id, params } = data;
      return axios.get(`api/v4/user_custom_config_options/${id}/get/`, { params }).then(response => response.data);
    },
    getUserProjectConfigs({}, id) {
      return axios.get(`api/v4/user_custom_config/${id}/get/`).then(response => response.data);
    },
    setUserProjectConfig({ commit }, data) {
      const { id, params } = data;
      return axios.post(`api/v4/user_custom_config/${id}/set/`, params).then((response) => {
        if (id === -1) {
          commit('setCommonConfig', response.data.data);
        } else {
          commit('setProjectConfig', response.data.data);
        }
        return response.data;
      });
    },
  },
};

export default project;
