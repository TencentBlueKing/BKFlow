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
import { applyPluginFormContext } from '@/config/setting.js';
import { loadPluginForms } from '@/utils/pluginFormLoader.js';
import transAtom from '@/utils/transAtom.js';
import { buildV4DetailFromSchemaSnapshot, getOpenPluginSchemaSnapshot } from '@/utils/uniformApi.js';

const createPluginFormStaleError = () => {
  const error = new Error('stale plugin form request');
  error.code = 'FORM_LOAD_STALE';
  return error;
};

/**
 * 获取全局 jQuery 实例上的 $.atoms 对象
 * webpack ProvidePlugin 提供的模块作用域 $ 与 expose-loader 暴露的 window.$ 是不同实例，
 * 插件脚本在全局作用域执行时使用 window.$ 注册 $.atoms，因此需要从全局实例读取
 */
function getGlobalAtoms() {
  return (window.$ && window.$.atoms) || (window.jQuery && window.jQuery.atoms) || $.atoms;
}

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
    const configData = transAtom(getGlobalAtoms(), type);
    $.atoms[type] = configData;
    list = $.atoms[type];
  } else {
    list = await new Promise((resolve) => {
      $.getScript(atomUrl, () => {
        // 从全局 jQuery 实例读取 atoms，因插件脚本在全局作用域注册 $.atoms
        const configData = transAtom(getGlobalAtoms(), type);
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
     * V4 原生表单编排入口：先获取标准化详情，再注入服务端许可的表单上下文，
     * 最后交给 PluginFormLoader 分发表单类型。每个异步边界都检查 isCurrent，
     * 旧请求只能结束，不能覆盖用户随后选择的插件或版本。
     */
    async loadV4OpenPluginForm({ rootState }, payload) {
      const isCurrent = typeof payload.isCurrent === 'function' ? payload.isCurrent : () => true;
      let snapshot = payload.snapshot;
      if (!snapshot && payload.readOnly && payload.taskId && payload.nodeId) {
        const extraInfoById = (rootState && rootState.task && rootState.task.taskExtraInfoById) || {};
        snapshot = getOpenPluginSchemaSnapshot(
          extraInfoById[payload.taskId] || extraInfoById[String(payload.taskId)],
          payload.nodeId,
          payload.templateNodeId,
        );
      }
      if (payload.readOnly && snapshot) {
        const detail = buildV4DetailFromSchemaSnapshot(snapshot);
        if (!isCurrent()) throw createPluginFormStaleError();
        applyPluginFormContext(detail.form_context, payload.runtimeContext);
        return loadPluginForms(detail, { readOnly: payload.readOnly, isCurrent });
      }
      const response = await axios.post('/api/plugin/detail/', payload.request);
      if (!isCurrent()) throw createPluginFormStaleError();
      if (!response.data.result) {
        throw new Error(response.data.message || 'load plugin detail failed');
      }
      const detail = response.data.data;
      if (!isCurrent()) throw createPluginFormStaleError();
      applyPluginFormContext(detail.form_context, payload.runtimeContext);
      return loadPluginForms(detail, { readOnly: payload.readOnly, isCurrent });
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
    /**
     * 加载子流程输出参数
     */
    loadSubprocessOutput({}, params) {
      return axios.get('/api/plugin/subprocess_plugin/', { params }).then(response => response.data);
    },
  },
};

export default atomForm;
