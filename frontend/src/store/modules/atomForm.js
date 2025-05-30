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
import Vue from 'vue';
import axios from 'axios';
import transAtom from '@/utils/transAtom.js';

/**
 * 异步获取插件配置列表
 * @param {String} atomUrl 配置文件 js 地址
 * @param {Boolean} isEmbedded 是为否嵌入式
 * @param {String} atomType 插件类型
 * @param {Boolean} atomType 是否输出类型
 */
const asyncGetAtomConfig = async function (atomUrl, isEmbedded, atomType, isOutput = false) {
  // 输入表单挂载名为 code
  // 输出表单挂载名为 code_output
  const type = isOutput ? `${atomType}_output` : atomType;
  if (!atomUrl) {
    return [];
  }

  let list;
  if (isEmbedded) {
    /* eslint-disable-next-line */
        eval(atomUrl)
    const configData = transAtom($.atoms, type);
    $.atoms[type] = configData;
    list = $.atoms[type];
  } else {
    list = await new Promise((resolve) => {
      $.getScript(atomUrl, () => {
        const configData = transAtom($.atoms, type);
        $.atoms[type] = configData;
        resolve($.atoms[type]);
      });
    });
  }
  return list;
};

const atomForm = {
  namespaced: true,
  state: {
    fetching: false,
    SingleAtomVersionMap: {},
    form: {}, // 插件所有信息(描述，输入，输出等)
    config: {}, // 输入-表单配置项
    output: {}, // 输出-表单初始值 data
    outputConfig: {}, // 输出-表单配置项
  },
  mutations: {
    setFetching(state, status) {
      state.fetching = status;
    },
    // 设置插件信息
    setAtomForm(state, payload) {
      const { atomType, version, data } = payload;
      if (state.form[atomType]) {
        Vue.set(state.form[atomType], version, data);
      } else {
        Vue.set(state.form, atomType, { [version]: data });
      }
    },
    // 设置输入配置
    setInputConfig(state, payload) {
      const { version, configList, atomType } = payload;
      if (state.config[atomType]) {
        Vue.set(state.config[atomType], version, configList);
      } else {
        Vue.set(state.config, atomType, { [version]: configList });
      }
    },
    // 设置输出数据
    setAtomOutputData(state, payload) {
      const { version, atomType, outputData } = payload;
      if (state.output[atomType]) {
        Vue.set(state.output[atomType], version, outputData);
      } else {
        Vue.set(state.output, atomType, { [version]: outputData });
      }
    },
    // 设置输出配置
    setOutputConfig(state, payload) {
      const { atomType, version, configList } = payload;
      if (state.outputConfig[atomType]) {
        Vue.set(state.outputConfig[atomType], version, configList);
      } else {
        Vue.set(state.outputConfig, atomType, { [version]: configList });
      }
    },
    clearAtomForm(state) {
      $.atoms = {};
      state.form = {};
      state.config = {};
      state.output = {};
      state.outputConfig = {};
    },
  },
  actions: {
    /**
     * 加载全量标准插件
     */
    loadSingleAtomList({}, params) {
      return axios.get('api/plugin/', { params }).then(response => response.data.data);
    },
    /**
     * 加载全量子流程
     */
    loadSubflowList({}, data) {
      let url = '';
      const params = {};
      const { project_id: projectId, common } = data;
      if (common) {
        url = 'api/common_template/';
      } else {
        url = 'api/template/';
        params.project__id = projectId;
      }
      return axios.get(url, { params }).then(response => response.data);
    },
    /**
     * 加载标准插件配置项
     * @param {String} payload.atomType 节点类型
     * @param {String} payload.setName 自定义请求类型
     */
    async loadAtomConfig({ commit }, payload) {
      const { name, atom, classify = 'component', version = 'legacy', space_id } = payload;
      const atomClassify = classify;
      const atomFile = name || atom;
      const atomVersion = atomClassify === 'component' ? version : 'legacy';
      const params = { space_id };
      const url = atomClassify === 'component' ? `api/plugin/${atomFile}/` : `api/template/variable/${atomFile}/`;

      // 变量暂时没有版本系统
      if (atomClassify === 'component') {
        params.version = atomVersion;
      }
      return axios.get(url, { params }).then(async (response) => {
        const {
          output: outputData,
          form: inputForm,
          form_is_embedded: isInputFormEmbedded,
          output_form: outputForm,
          embedded_output_form: isOutputFormEmbedded,
          base,
        } = response.data.data;
        const result = {
          input: [],
          output: [],
          isRenderOutputForm: !!outputForm,
        };

        commit('setAtomForm', { atomType: atom, data: response.data.data, version: atomVersion });
        commit('setAtomOutputData', { atomType: atom, outputData, version: atomVersion });

        // 加载标准插件 base 文件
        if (base) {
          await $.getScript(base);
        }

        if (outputForm) {
          result.output = await asyncGetAtomConfig(outputForm, isOutputFormEmbedded, atom, true);
          commit('setOutputConfig', { atomType: atom, version: atomVersion, configList: result.output });
        }
        if (inputForm) {
          result.input = await asyncGetAtomConfig(inputForm, isInputFormEmbedded, atom);
          commit('setInputConfig', { atomType: atom, version: atomVersion, configList: result.input });
        }
        return result;
      });
    },
    /**
     * 加载第三方插件列表
     */
    loadPluginServiceList({}, params) {
      return axios.get('/api/plugin_service/detail_list/', { params }).then(response => response.data);
    },
    /**
     * 加载第三方插件详情
     */
    loadPluginServiceDetail({}, params) {
      return axios.get('/api/plugin_service/detail/', { params }).then(response => response.data);
    },
    /**
     * 加载第三方插件日志
     */
    loadPluginServiceLog({}, params) {
      return axios.post('/api/plugin_service/logs/', params).then(response => response.data);
    },
    /**
     * 加载第三方插件元信息
     */
    loadPluginServiceMeta({}, params) {
      return axios.get('/api/plugin_service/meta/', { params }).then(response => response.data);
    },
    /**
     * 加载第三方插件
     */
    loadPluginServiceAppDetail({}, params) {
      return axios.get(`/api/plugin_service/app_detail/?plugin_code=${params.plugin_code}`).then(response => response.data);
    },
    /**
     * 加载全量标准插件
     */
    loadAnalysisComponentList() {
      return axios.get('/analysis/get_component_list/').then(response => response.data);
    },
    /**
     * 获取第三方插件分类
     */
    getThirdPluginTags({}, params) {
      return axios.get('/api/plugin_service/tags/', { params }).then(response => response.data);
    },
  },
};

export default atomForm;
