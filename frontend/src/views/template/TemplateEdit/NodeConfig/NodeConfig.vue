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
<template>
  <div class="node-config-wrapper">
    <bk-sideslider
      ref="nodeConfigPanel"
      ext-cls="node-config-panel"
      :width="800"
      :is-show="sideShow"
      :quick-close="true"
      :before-close="beforeClose">
      <!--侧栏头部-->
      <SliderHeader
        slot="header"
        :key="randomKey"
        :is-variable-panel-show="isVariablePanelShow"
        :variable-data="variableData"
        :is-selector-panel-show="isSelectorPanelShow"
        :back-to-variable-panel="backToVariablePanel"
        :is-view-mode="isViewMode"
        :variable-list="variableList"
        @openVariablePanel="openVariablePanel"
        @closeEditingPanel="isVariablePanelShow = false"
        @back="goBackToConfig"
        @close="onClosePanel" />
      <template slot="content">
        <!-- 插件/插件版本不存在面板 -->
        <bk-exception
          v-if="isNotExistAtomOrVersion"
          class="exception-wrap"
          type="500">
          <span>{{ $t('未找到可用的插件或插件版本') }}</span>
          <div
            class="text-wrap"
            @click="handleReslectPlugin">
            {{ $t('重选插件') }}
          </div>
        </bk-exception>
        <!-- 插件/子流程选择面板 -->
        <select-panel
          v-else-if="isSelectorPanelShow"
          :project_id="projectId"
          :template-labels="templateLabels"
          :node-config="nodeConfig"
          :atom-type-list="atomTypeList"
          :basic-info="basicInfo"
          :common="common"
          :is-third-party="isThirdParty"
          :plugin-loading="pluginLoading"
          :is-api-plugin="isApiPlugin"
          :scope-info="scopeInfo"
          :space-id="spaceId"
          :space-related-config="spaceRelatedConfig"
          @back="isSelectorPanelShow = false"
          @viewSubflow="onViewSubflow"
          @select="onPluginOrTplChange" />
        <!-- 变量编辑面板 -->
        <div
          v-else-if="isVariablePanelShow"
          class="variable-edit-panel">
          <variable-edit
            ref="variableEdit"
            :variable-data="variableData"
            :common="common"
            :constants="localConstants"
            :template-id="$route.params.templateId"
            @closeEditingPanel="isVariablePanelShow = false"
            @onSaveEditing="onVariableSaveEditing" />
        </div>
        <!-- 插件/子流程表单面板 -->
        <div
          v-else-if="!isSubflow || !subflowListLoading"
          v-bkloading="{ isLoading: isSubflow && subflowListLoading, opacity: 1 }"
          class="node-config">
          <div class="config-form">
            <!-- 基础信息 -->
            <section
              class="config-section"
              data-test-id="templateEdit_form_nodeBaseInfo">
              <h3>{{ $t('基础信息') }}</h3>
              <basic-info
                v-if="!isBaseInfoLoading"
                ref="basicInfo"
                v-bkloading="{ isLoading: isBaseInfoLoading }"
                class="basic-info-wrapper"
                :basic-info="basicInfo"
                :node-config="nodeConfig"
                :version-list="versionList"
                :is-subflow="isSubflow"
                :input-loading="inputLoading"
                :project-id="projectId"
                :common="common"
                :subflow-updated="subflowUpdated"
                :is-view-mode="isViewMode"
                :is-api-plugin="isApiPlugin"
                :is-subflow-need-to-update="isSubflowNeedToUpdate"
                @openSelectorPanel="isSelectorPanelShow = true"
                @versionChange="versionChange"
                @viewSubflow="onViewSubflow"
                @updateSubflowVersion="updateSubflowVersion"
                @update="updateBasicInfo" />
            </section>
            <!-- 输入参数 -->
            <section
              class="config-section"
              data-test-id="templateEdit_form_inputParamsInfo">
              <h3>{{ $t('输入参数') }}</h3>
              <div
                v-bkloading="{ isLoading: inputLoading, zIndex: 100 }"
                class="inputs-wrapper">
                <template v-if="!inputLoading">
                  <SpecialPluginInputForm
                    v-if="isSpecialPlugin"
                    ref="specialPluginInputParams"
                    :value="inputsParamValue"
                    :code="basicInfo.plugin"
                    :is-view-mode="isViewMode"
                    :space-id="spaceId"
                    :template-id="$route.params.templateId"
                    :variable-list="variableList"
                    :node-id="nodeId"
                    :variable-cited="variableCited"
                    @updateVarCitedData="updateVarCitedData"
                    @updateOutputs="updateOutputs"
                    @update="updateInputsValue" />
                  <input-params
                    v-else
                    ref="inputParams"
                    class="inputs-wrapper"
                    :node-id="nodeId"
                    :scheme="inputs"
                    :subflow-forms="subflowForms"
                    :template-id="$route.params.templateId"
                    :forms-not-referred="formsNotReferred"
                    :value="inputsParamValue"
                    :render-config="inputsRenderConfig"
                    :is-subflow="isSubflow"
                    :is-view-mode="isViewMode"
                    :constants="localConstants"
                    :is-api-plugin="isApiPlugin"
                    :basic-info="basicInfo"
                    :is-third-party="isThirdParty"
                    @hookChange="onHookChange"
                    @renderConfigChange="onRenderConfigChange"
                    @update="updateInputsValue" />
                </template>
              </div>
            </section>
            <!-- 输出参数 -->
            <section
              class="config-section"
              data-test-id="templateEdit_form_outputParamsInfo">
              <h3>{{ $t('输出参数') }}</h3>
              <div
                v-bkloading="{ isLoading: outputLoading, zIndex: 100 }"
                class="outputs-wrapper">
                <output-params
                  v-if="!outputLoading"
                  ref="outputParams"
                  v-bkloading="{ isLoading: outputLoading, zIndex: 100 }"
                  class="outputs-wrapper"
                  :constants="localConstants"
                  :params="outputs"
                  :version="basicInfo.version"
                  :node-id="nodeId"
                  :is-third-party="isThirdParty"
                  :is-view-mode="isViewMode"
                  :uniform-outputs="uniformOutputs"
                  @hookChange="onHookChange"
                  @openVariablePanel="openVariablePanel" />
              </div>
            </section>
          </div>
          <div class="btn-footer">
            <bk-button
              v-if="!isViewMode"
              theme="primary"
              :disabled="inputLoading || (isSubflow && subflowListLoading)"
              data-test-id="templateEdit_form_saveNodeConfig"
              @click="onSaveConfig">
              {{ $t('确定') }}
            </bk-button>
            <bk-button
              theme="default"
              data-test-id="templateEdit_form_cancelNodeConfig"
              @click="onClosePanel()">
              {{ $t('取消') }}
            </bk-button>
          </div>
        </div>
      </template>
    </bk-sideslider>
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import { mapActions, mapState, mapMutations } from 'vuex';
  import atomFilter from '@/utils/atomFilter.js';
  import tools from '@/utils/tools.js';
  import BasicInfo from './BasicInfo.vue';
  import InputParams from './InputParams.vue';
  import OutputParams from './OutputParams.vue';
  import SelectPanel from './SelectPanel/index.vue';
  import VariableEdit from '../TemplateSetting/TabGlobalVariables/VariableEdit.vue';
  import SliderHeader from './SliderHeader.vue';
  import SpecialPluginInputForm from '@/components/SpecialPluginInputForm/index.vue';
  import bus from '@/utils/bus.js';
  import permission from '@/mixins/permission.js';
  import formSchema from '@/utils/formSchema.js';
  import jsonFormSchema from '@/utils/jsonFormSchema.js';
  import copy from '@/mixins/copy.js';

  export default {
    name: 'NodeConfig',
    components: {
      BasicInfo,
      InputParams,
      OutputParams,
      SelectPanel,
      VariableEdit,
      SliderHeader,
      SpecialPluginInputForm,
    },
    mixins: [permission, copy],
    props: {
      projectId: {
        type: [String, Number],
        default: '',
      },
      nodeId: {
        type: String,
        default: '',
      },
      isShow: Boolean,
      isShowSelect: Boolean,
      atomList: {
        type: Array,
        default: () => ([]),
      },
      subflowList: {
        type: Array,
        default: () => ([]),
      },
      atomTypeList: {
        type: Object,
        default: () => ({}),
      },
      templateLabels: {
        type: Array,
        default: () => ([]),
      },
      common: {
        type: [String, Number],
        default: '',
      },
      isSubflowNeedToUpdate: {
        type: Boolean,
        default: false,
      },
      subflowListLoading: Boolean,
      backToVariablePanel: Boolean,
      isNotExistAtomOrVersion: Boolean,
      pluginLoading: Boolean,
      isViewMode: Boolean,
      spaceRelatedConfig: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        sideShow: false,
        initLoading: true, // 初始化loading
        subflowUpdated: false, // 子流程是否更新
        taskNodeLoading: false, // 普通任务节点数据加载
        subflowLoading: false, // 子流程任务节点数据加载
        constantsLoading: false, // 子流程输入参数配置项加载
        subflowVersionUpdating: false, // 子流程更新
        nodeConfig: {}, // 任务节点的完整 activity 配置参数
        isBaseInfoLoading: true, // 基础信息loading
        basicInfo: {}, // 基础信息模块
        versionList: [], // 标准插件版本
        inputs: [], // 输入参数表单配置项
        inputsParamValue: {}, // 输入参数值
        inputsRenderConfig: {}, // 输入参数是否配置渲染豁免
        outputs: [], // 输出参数
        uniformOutputs: [], // api插件输出参数
        subflowForms: {}, // 子流程输入参数
        formsNotReferred: {}, // 未被子流程引用的全局变量
        isSelectorPanelShow: false, // 是否显示选择插件(子流程)面板
        isVariablePanelShow: false, // 是否显示变量编辑面板
        variableData: {}, // 当前编辑的变量
        localConstants: {}, // 全局变量列表，用来维护当前面板勾选、反勾选后全局变量的变化情况，保存时更新到 store
        randomKey: new Date().getTime(), // 输入、输出参数勾选状态改变时更新popover
        isThirdParty: false, // 是否为第三方插件
        quickOperateVariableVisable: false,
        variableCited: {}, // 全局变量被任务节点、网关节点以及其他全局变量引用情况
        unhookingVarForm: {}, // 正被取消勾选的表单配置
        isUpdateConstants: false, // 是否更新输入参数配置
        isDataChange: false, // 数据是否改变
        isApiPlugin: false, // 是否为Api插件
        apiInputs: [], // api数据
        isInitDecision: true,
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.template.spaceId,
        scopeInfo: state => state.template.scopeInfo,
        activities: state => state.template.activities,
        gateways: state => state.template.gateways,
        constants: state => state.template.constants,
        internalVariable: state => state.template.internalVariable,
        locations: state => state.template.location,
        pluginConfigs: state => state.atomForm.config,
        pluginOutput: state => state.atomForm.output,
        infoBasicConfig: state => state.infoBasicConfig,
      }),
      variableList() {
        const systemVars = Object.keys(this.internalVariable).map(key => this.internalVariable[key]);
        const userVars = Object.keys(this.localConstants).map(key => this.localConstants[key]);
        return [...systemVars, ...userVars];
      },
      isSubflow() {
        return this.nodeConfig.type !== 'ServiceActivity';
      },
      atomGroup() { // 某一标准插件下所有版本分组
        return this.atomList.find(item => item.code === this.basicInfo.plugin);
      },
      inputLoading() { // 以下任一方法处于 pending 状态，输入参数展示 loading 效果
        return this.isBaseInfoLoading
          || this.taskNodeLoading
          || this.subflowLoading
          || this.constantsLoading
          || this.subflowVersionUpdating
          || this.initLoading;
      },
      outputLoading() {
        return this.isBaseInfoLoading || this.taskNodeLoading || this.subflowLoading;
      },
      // 特殊输入参数插件
      isSpecialPlugin() {
        return ['dmn_plugin', 'value_assign'].includes(this.basicInfo.plugin);
      },
    },
    watch: {
      constants(val) {
        this.localConstants = tools.deepClone(val);
      },
      subflowListLoading(val) {
        if (!val) {
          // 获取子流程模板的名称
          Promise.resolve(this.getNodeBasic(this.nodeConfig)).then((res) => {
            this.basicInfo = res;
          });
        }
      },
      isShow: {
        handler(val) {
          // 添加延迟触发sideSlider遮罩
          this.$nextTick(() => {
            this.sideShow = val;
          });
        },
        immediate: true,
      },
    },
    created() {
      /**
       * notice: 该方法为了兼容“job-执行作业（job_execute_task）标准插件”动态添加输出参数
       * description: 切换作业模板时，将当前作业的全局变量表格数据部分添加到输出参数
       */
      bus.$on('jobExecuteTaskOutputs', (args) => {
        const { plugin, version } = this.basicInfo;
        if (!this.isSubflow && plugin === 'job_execute_task') {
          // tagDatatable 值发生变更前后的值
          const { val, oldVal } = args;
          const outputs = [...this.pluginOutput[plugin][version]];
          if (val && val.length > 0) {
            val.forEach((item) => {
              if (item.category === 1) {
                outputs.push({
                  name: item.name,
                  key: item.name,
                  version,
                });
              }
            });
          }
          if (oldVal && oldVal.length > 0) {
            // 清除变更后不存在且被勾选的输出变量
            oldVal.forEach((item) => {
              if (item.category === 1) {
                // 切换前后一直存在的变量不处理
                if (val.find(v => v.id === item.id)) {
                  return;
                }
                Object.keys(this.localConstants).some((key) => {
                  let result = false;
                  const constant = this.localConstants[key];
                  const sourceInfo = constant.source_info[this.nodeId];
                  if (sourceInfo && sourceInfo.includes(item.name)) {
                    this.deleteVariable(key);
                    result = true;
                  }
                  return result;
                });
              }
            });
          }

          this.outputs = outputs;
        }
      });
      this.localConstants = tools.deepClone(this.constants);
    },
    async mounted() {
      try {
        const defaultData = await this.initDefaultData();
        for (const [key, val] of Object.entries(defaultData)) {
          this[key] = val;
        }
        if (!this.isNotExistAtomOrVersion) {
          await this.initData();
        }
      } catch (error) {
        console.warn(error);
      } finally {
        this.initLoading = false;
      }
    },
    methods: {
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceMeta',
        'loadPluginServiceDetail',
        'loadPluginServiceAppDetail',
      ]),
      ...mapActions('template/', [
        'loadTemplateData',
        'getVariableCite',
        'getProcessOpenChdProcess',
        'loadUniformApiMeta',
      ]),
      ...mapActions('task', [
        'loadSubflowConfig',
      ]),
      ...mapMutations('template/', [
        'setSubprocessUpdated',
        'setActivities',
        'addVariable',
        'setConstants',
        'setOutputs',
      ]),
      async initDefaultData() {
        const nodeConfig = tools.deepClone(this.activities[this.nodeId]);
        const isThirdParty = nodeConfig.component && nodeConfig.component.code === 'remote_plugin';
        const isApiPlugin = nodeConfig.component && nodeConfig.component.code === 'uniform_api';
        if (nodeConfig.type === 'ServiceActivity') {
          this.basicInfo = await this.getNodeBasic(nodeConfig);
        } else {
          this.isSelectorPanelShow = !nodeConfig.template_id;
          this.basicInfo = await this.getNodeBasic(nodeConfig);
        }
        this.$nextTick(() => {
          this.isBaseInfoLoading = false;
        });
        const { basicInfo } = this;
        let versionList = [];
        if (nodeConfig.type === 'ServiceActivity') {
          const code = isThirdParty ? nodeConfig.name : nodeConfig.component.code;
          versionList = isApiPlugin ? [] : this.getAtomVersions(code, isThirdParty);
        }
        const isSelectorPanelShow = nodeConfig.type === 'ServiceActivity' ? !basicInfo.plugin : !basicInfo.tpl;
        return {
          nodeConfig,
          isThirdParty,
          isApiPlugin,
          basicInfo,
          versionList,
          isSelectorPanelShow,
        };
      },
      async setThirdPartyList(nodeConfig) {
        try {
          // 设置第三发插件缓存
          const { thirdPartyList } = this.$parent;
          if (nodeConfig.component
            && nodeConfig.component.code === 'remote_plugin'
            && !thirdPartyList[this.nodeId]) {
            const resp = await this.loadPluginServiceMeta({ plugin_code: nodeConfig.component.data.plugin_code.value });
            const { code, versions, description } = resp.data;
            const versionList = versions.map(version => ({ version }));
            const { data } = nodeConfig.component;
            let version = data && data.plugin_version;
            version = version && version.value;
            const group = {
              code,
              list: versionList,
              version,
              desc: description,
            };
            thirdPartyList[this.nodeId] = group;
          }
        } catch (error) {
          console.warn(error);
          this.isBaseInfoLoading = false;
        }
      },
      // 初始化节点数据
      async initData() {
        if (!this.basicInfo.plugin && !this.basicInfo.tpl) { // 未选择插件
          return;
        }
        if (!this.isSubflow) {
          const paramsVal = {};
          const renderConfig = {};
          Object.keys(this.nodeConfig.component.data || {}).forEach((key) => {
            const val = tools.deepClone(this.nodeConfig.component.data[key].value);
            paramsVal[key] = val;
            renderConfig[key] = 'need_render' in this.nodeConfig.component.data[key] ? this.nodeConfig.component.data[key].need_render : true;
          });
          this.inputsRenderConfig = renderConfig;
          await this.getPluginDetail();
          // api插件json字段展示解析优化
          this.handleJsonValueParse(false, paramsVal);
          this.inputsParamValue = paramsVal;
        } else {
          const { tpl, version } = this.basicInfo;
          const forms = {};
          const renderConfig = {};
          Object.keys(this.nodeConfig.constants).forEach((key) => {
            const form = this.nodeConfig.constants[key];
            if (form.show_type === 'show') {
              forms[key] = form;
              renderConfig[key] = 'need_render' in form ? form.need_render : true;
            }
          });
          await this.getSubflowDetail(tpl, version, true);
          // 加载子流程输入参数表单配置项
          this.inputs = await this.getSubflowInputsConfig();
          // 获取子流程任务节点输入参数值
          this.inputsParamValue = this.getSubflowInputsValue(forms);
          this.inputsRenderConfig = renderConfig;
        }
        // 节点参数错误时，配置项加载完成后，执行校验逻辑，提示用户错误信息
        const location = this.locations.find(item => item.id === this.nodeConfig.id);
        if (location && location.status === 'FAILED') {
          this.validate();
        }
        // 获取插件配置时会去更新baseInfo，这个时候数据并没有修改
        this.isDataChange = false;
      },
      /**
       * 加载标准插件节点输入参数表单配置项，获取输出参数列表
       */
      async getPluginDetail() {
        const { plugin, version } = this.basicInfo;
        this.taskNodeLoading = true;
        try {
          // 获取输入输出参数
          this.inputs = await this.getAtomConfig({ plugin, version, isThird: this.isThirdParty });
          if (!this.isThirdParty && !this.isApiPlugin) {
            this.outputs = this.atomGroup.list.find(item => item.version === version)?.output || [];
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.taskNodeLoading = false;
        }
      },
      /**
       * 加载标准插件表单配置项文件
       * 优先取 store 里的缓存
       */
      async getAtomConfig(config) {
        const { plugin, version, classify, name, isThird } = config;
        try {
          // 先取标准节点缓存的数据
          const pluginGroup = this.pluginConfigs[plugin];
          if (pluginGroup && pluginGroup[version]) {
            return pluginGroup[version];
          }
          // api插件输入输出
          if (this.isApiPlugin && this.basicInfo.metaUrl) {
            // 统一api基础配置
            await this.loadAtomConfig({ atom: plugin, version, space_id: this.spaceId });
            // api插件配置
            const resp = await this.loadUniformApiMeta({
              templateId: this.$route.params.templateId,
              spaceId: this.spaceId,
              meta_url: this.basicInfo.metaUrl,
              ...this.scopeInfo,
            });
            if (!resp.result) return;
            // 输出参数
            const storeOutputs = this.pluginOutput.uniform_api[version];
            this.uniformOutputs = resp.data.outputs || [];
            this.outputs = [...storeOutputs];
            const { url, methods, response_data_path: respDataPath, polling, callback } = resp.data;
            const method = methods.length === 1 ? methods[0] : ''; // 请求方法只有一个时，默认选中
            this.updateBasicInfo({
              method,
              methodList: methods,
              realMetaUrl: url,
              methodList: resp.data.methods,
              respDataPath,
              polling,
              callback,
            });
            this.apiInputs = resp.data.inputs;
            return jsonFormSchema(resp.data, { disabled: this.isViewMode });
          }
          // 第三方插件
          if (isThird) {
            await this.getThirdConfig(plugin, version);
          } else {
            await this.loadAtomConfig({ atom: plugin, version, classify, name, space_id: this.spaceId });
          }
          const config = $.atoms[plugin];
          return config;
        } catch (e) {
          console.log(e);
        }
      },
      // 第三方插件输入输出配置
      async getThirdConfig(plugin, version) {
        try {
          const resp = await this.loadPluginServiceDetail({
            plugin_code: plugin,
            plugin_version: version,
            with_app_detail: true,
          });
          if (!resp.result) return;
          // 获取参数
          const { outputs: respOutputs, forms, inputs } = resp.data;
          // 获取不同版本的描述
          let desc = resp.data.desc || '';
          if (desc && desc.includes('\n')) {
            const descList = desc.split('\n');
            desc = descList.join('<br>');
          }
          this.updateBasicInfo({ desc });
          // 获取host
          const { origin } = window.location;
          const hostUrl = `${origin + window.SITE_URL}plugin_service/data_api/${plugin}/`;
          $.context.bk_plugin_api_host[plugin] = hostUrl;
          if (forms.renderform) {
            // 输入参数
            $.atoms[plugin] = {};
            const renderFrom = forms.renderform;
            /* eslint-disable-next-line */
            eval(renderFrom)
          } else {
            $.atoms[plugin] = inputs;
          }

          // 输出参数
          const outputs = [];
          // 获取第三方插件公共输出参数
          if (!this.pluginOutput.remote_plugin) {
            await this.loadAtomConfig({ atom: 'remote_plugin', version: '1.0.0', space_id: this.spaceId });
          }
          const storeOutputs = this.pluginOutput.remote_plugin['1.0.0'];
          for (const [key, val] of Object.entries(respOutputs.properties)) {
            outputs.push({
              name: val.title || key,
              key,
              type: val.type,
              schema: { description: val.description },
            });
          }
          this.outputs = [...storeOutputs, ...outputs];
        } catch (error) {
            console.warn(error);
        }
    },
      /**
       * 加载子流程任务节点输入、输出、版本配置项
       */
      async getSubflowDetail(tpl, version = '', isInit = false) {
        this.subflowLoading = true;
        try {
          const params = {
            templateId: tpl,
            is_all_nodes: true,
          };
          if (version) {
            params.version = version;
          }
          const resp = await this.loadSubflowConfig(params);
          // 子流程的输入参数包括流程引用的变量、自定义变量和未被引用的变量
          // custom_constants
          this.subflowForms = {
            ...resp.data.pipeline_tree.constants,
            ...resp.data.constants_not_referred,
          };
          this.formsNotReferred = resp.data.constants_not_referred;
          // 子流程模板版本更新时，未带版本信息，需要请求接口后获取最新版本
          if (isInit) {
            this.updateBasicInfo({ latestVersion: resp.data.version });
          } else {
            this.updateBasicInfo({ version: resp.data.version, latestVersion: resp.data.version });
          }
          // 输出变量
          const has = Object.prototype.hasOwnProperty;
          this.outputs = Object.keys(resp.data.outputs).map((item) => {
            const output = resp.data.outputs[item];
            return {
              plugin_code: output.plugin_code,
              name: output.name,
              key: output.key,
              version: has.call(output, 'version') ? output.version : 'legacy',
            };
          });
        } catch (e) {
          console.log(e);
        } finally {
          this.subflowLoading = false;
        }
      },
      /**
       * 加载子流程输入参数表单配置项
       * 遍历每个非隐藏的全局变量，由 source_tag、coustom_type 字段确定需要加载的标准插件
       * 同时根据 source_tag 信息获取全局变量对应标准插件的某一个表单配置项
       *
       * @return {Array} 每个非隐藏全局变量对应表单配置项组成的数组
       */
      async getSubflowInputsConfig() {
        this.constantsLoading = true;
        const inputs = [];
        const variables = Object.keys(this.subflowForms)
          .map(key => this.subflowForms[key])
          .filter(item => item.show_type === 'show')
          .sort((a, b) => a.index - b.index);

        await Promise.all(variables.map(async (variable) => {
          const { key } = variable;
          const { name, atom, tagCode, classify } = atomFilter.getVariableArgs(variable);
          const version = variable.version || 'legacy';
          const isThird = Boolean(variable.plugin_code);
          const atomConfig = await this.getAtomConfig({ plugin: atom, version, classify, name, isThird });
          let formItemConfig = tools.deepClone(atomFilter.formFilter(tagCode, atomConfig));
          if (variable.is_meta || formItemConfig.meta_transform) {
            formItemConfig = formItemConfig.meta_transform(variable.meta || variable);
            if (!variable.meta) {
              variable.meta = tools.deepClone(variable);
              variable.value = formItemConfig.attrs.value;
            }
          }
          // 特殊处理逻辑，针对子流程节点，如果为自定义类型的下拉框变量，默认开始支持用户创建不存在的选项配置项
          if (variable.custom_type === 'select') {
            formItemConfig.attrs.allowCreate = true;
          }
          formItemConfig.tag_code = key;
          formItemConfig.attrs.name = variable.name;
          // 自定义输入框变量正则校验添加到插件配置项
          if (['input', 'textarea'].includes(variable.custom_type) && variable.validation !== '') {
            formItemConfig.attrs.validation.push({
              type: 'regex',
              args: variable.validation,
              error_message: i18n.t('默认值不符合正则规则：') + variable.validation,
            });
          }
          // 参数填写时为保证每个表单 tag_code 唯一，原表单 tag_code 会被替换为变量 key，导致事件监听不生效
          const has = Object.prototype.hasOwnProperty;
          if (has.call(formItemConfig, 'events')) {
            formItemConfig.events.forEach((e) => {
              if (e.source === tagCode) {
                e.source = `\${${e.source}}`;
              }
            });
          }
          inputs.push(formItemConfig);
        }));
        this.constantsLoading = false;
        return inputs;
      },
      /**
       * 获取任务节点基础信息数据
       */
      async getNodeBasic(config) {
        if (config.type === 'ServiceActivity') {
          const {
            component,
            name,
            stage_name: stageName = '',
            labels,
            error_ignorable,
            can_retry: canRetry,
            retryable,
            isSkipped,
            skippable,
            optional,
            auto_retry,
            timeout_config: timeoutConfig,
            executor_proxy: executorProxy,
          } = config;
          let basicInfoName = i18n.t('请选择插件');
          let code = '';
          let desc = '';
          let version = '';
          // 节点已选择标准插件
          if (component.code && !this.isNotExistAtomOrVersion) { // 节点插件存在
            if (component.code === 'remote_plugin') {
              const atom = this.$parent.thirdPartyList[this.nodeId];
              code = component.data.plugin_code.value;
              const resp = await this.loadPluginServiceAppDetail({ plugin_code: code });
              basicInfoName = resp.data.name;
              version = atom.version;
              desc = atom.desc;
            } else if (component.code === 'uniform_api') {
              code = component.code;
              version = component.version;
            } else {
              const atom = this.atomList.find(item => item.code === component.code);
              code = component.code;
              basicInfoName = `${atom.group_name}-${atom.name}`;
              const has = Object.prototype.hasOwnProperty;
              version = has.call(component, 'version') ? component.version : 'legacy';
              // 获取不同版本的描述
              desc = atom.list.find(item => item.version === version)?.desc;
            }
            if (desc && desc.includes('\n')) {
              const descList = desc.split('\n');
              desc = descList.join('<br>');
            }
          }

          const data = {
            plugin: code,
            name: basicInfoName, // 插件名称
            nodeName: name, // 节点名称
            stageName,
            nodeLabel: labels || [], // 兼容旧数据，节点标签字段为后面新增
            version, // 标准插件版本
            desc, // 空节点不存在插件描述信息
            ignorable: error_ignorable,
            // isSkipped 和 can_retry 为旧数据字段，后来分别变更为 skippable、retryable，节点点开编辑保存后会删掉旧字段
            // 这里取值做兼容处理，新旧数据不可能同时存在，优先取旧数据字段
            skippable: isSkipped === undefined ? skippable : isSkipped,
            retryable: canRetry === undefined ? retryable : canRetry,
            selectable: optional,
            autoRetry: Object.assign({}, { enable: false, interval: 0, times: 1 }, auto_retry),
            timeoutConfig: timeoutConfig || { enable: false, seconds: 10, action: 'forced_fail' },
            executor_proxy: executorProxy ? executorProxy.split(',') : [],
          };
          if (component.code === 'uniform_api' &&  component.api_meta) { // 新版api插件中component包含api_meta字段
            const { id, name, api_key: apiKey, meta_url, category = {} } = component.api_meta;
            const { uniform_api_plugin_method: method, uniform_api_plugin_url: realMetaUrl } = component.data;
            Object.assign(data, {
              plugin: 'uniform_api',
              name: `${category.name}-${name}`,
              pluginId: id,
              method: method.value,
              groupId: category.id,
              groupName: category.name,
              apiKey,
              metaUrl: meta_url,
              realMetaUrl,
              methodList: [],
            });
          }
          return data;
        }
        const {
          template_id: templateId,
          name,
          stage_name: stageName = '',
          labels,
          optional,
          always_use_latest: alwaysUseLatest,
          scheme_id_list: schemeIdList,
          executor_proxy: executorProxy,
          auto_retry,
          timeout_config: timeoutConfig,
          error_ignorable,
          isSkipped,
          skippable,
          can_retry: canRetry,
          retryable,
        } = config;
        let templateName = i18n.t('请选择子流程');

        if (templateId) {
          const subflowInfo = this.atomTypeList.subflow.find(item => item.template_id === Number(templateId));
          if (subflowInfo) {
            templateName = subflowInfo.name;
          } else {
            const templateData = await this.loadTemplateData({
              templateId,
              common: false,
              checkPermission: true })
              .catch((error) => {
                this.onClosePanel();
                console.log(error);
              }) || {};
            templateName = templateData.name;
          }
        }
        const has = Object.prototype.hasOwnProperty;
        const version = has.call(config, 'version') ? config.version : ''; // 子流程版本，区别于标准插件版本
        return {
          tpl: templateId || '',
          name: templateName, // 流程模版名称
          nodeName: name, // 节点名称
          stageName,
          nodeLabel: labels || [], // 兼容旧数据，节点标签字段为后面新增
          selectable: optional,
          alwaysUseLatest: alwaysUseLatest || false, // 兼容旧数据，该字段为新增
          schemeIdList: schemeIdList || [], // 兼容旧数据，该字段为后面新增
          version,
          ignorable: error_ignorable,
          skippable: isSkipped === undefined ? skippable : isSkipped,
          retryable: canRetry === undefined ? retryable : canRetry,
          autoRetry: Object.assign({}, { enable: false, interval: 0, times: 1 }, auto_retry),
          timeoutConfig: timeoutConfig || { enable: false, seconds: 10, action: 'forced_fail' },
          executor_proxy: executorProxy ? executorProxy.split(',') : [],
        };
      },
      /**
       * 获取某一标准插件所有版本列表
       */
      getAtomVersions(code, isThirdParty = false) {
        if (!code || this.isNotExistAtomOrVersion) {
          return [];
        }
        let atom;
        if (isThirdParty) {
          atom = this.$parent.thirdPartyList[this.nodeId];
          return atom && atom.list;
        }
        atom = this.atomList.find(item => item.code === code);
        return atom.list.map(item => ({
          version: item.version,
        })).reverse();
      },
      /**
       * 获取子流程任务节点输入参数值，有三种情况：
       * 1.节点点开编辑时取 activitity 里的 constants 数据
       * 2.切换子流程时，取接口返回的 form 数据
       * 3.子流程更新时，先判断表单项是否为勾选状态，勾选取旧表单项数据，
       * 未勾选则判断新旧表单项数据 custom_type(自定义全局变量)或者 source_tag(标准插件表单项)是否相同，
       * 相同取旧数据里的表单值，否则取新数据
       */
      getSubflowInputsValue(forms, oldForms = {}) {
        return Object.keys(forms).reduce((acc, cur) => { // 遍历新表单项
          const variable = forms[cur];
          if (variable.show_type === 'show') {
            let canReuse = false;
            const oldVariable = oldForms[cur];
            const isHooked = this.isInputParamsInConstants(variable);
            if (oldVariable && !isHooked) { // 旧版本中存在相同key的表单项，且不是勾选状态
              if (variable.custom_type || oldVariable.custom_type) {
                canReuse = variable.custom_type === oldVariable.custom_type;
              } else {
                canReuse = variable.source_tag === oldVariable.source_tag;
              }
            }
            const val = canReuse ? this.inputsParamValue[cur] : variable.value;
            acc[variable.key] = tools.deepClone(val);
          }

          return acc;
        }, {});
      },
      // 输入参数是否已被勾选到全局变量
      isInputParamsInConstants(form) {
        return Object.keys(this.localConstants).some((key) => {
          const varItem = this.localConstants[key];
          const sourceInfo = varItem.source_info[this.nodeId];
          return sourceInfo && sourceInfo.includes(form.tag_code);
        });
      },
      // 由标准插件(子流程)选择面板返回配置面板
      goBackToConfig() {
        if (this.isSelectorPanelShow && (this.basicInfo.plugin || this.basicInfo.tpl)) {
          this.isSelectorPanelShow = false;
        }
      },
      // 变量编辑确认
      onVariableSaveEditing(variable) {
        this.isVariablePanelShow = false;

        const { key } = this.variableData;
        if (!key || key === variable.key) return;

        this.onHookChange('delete', this.variableData);
        this.onHookChange('create', variable);
        this.variableData = {};
      },
      // 标准插件（子流程）选择面板切换插件（子流程）
      // isThirdParty 是否为第三方插件
      async onPluginOrTplChange(val) {
        // api插件
        if (val.code === 'uniform_api') {
          this.isThirdParty = false;
          this.isApiPlugin = true;
          this.isSelectorPanelShow = false;
          this.apiInputs = [];
          this.inputsParamValue = {};
          const config = this.getBasicConfig(val);
          this.updateBasicInfo(config);
          this.getPluginDetail();
          return;
        }
        this.isApiPlugin = false;
        let { inputs } = this; // 上一个子流程的输入参数
        if (this.isSubflow) {
          // 重置basicInfo, 避免基础信息面板因监听basicInfo导致重复调取接口，初始化时获取空值
          const { id, name, version } = val;
          const config = {
            name,
            version,
            tpl: id,
            nodeName: name,
            selectable: true,
            alwaysUseLatest: false,
            schemeIdList: [],
          };
          this.updateBasicInfo(config);
          if ('project' in val && typeof val.project.id === 'number') {
            this.$set(this.nodeConfig, 'template_source', 'business');
          } else {
            this.$set(this.nodeConfig, 'template_source', 'common');
          }
          // 清空输入参数，否则会先加载上一个的子流程的配置再去加载选中的子流程配置
          inputs = tools.deepClone(this.inputs);
          this.inputs = [];
        }
        this.isSelectorPanelShow = false;
        this.isThirdParty = val.id === 'remote_plugin';
        await this.clearParamsSourceInfo(inputs);
        if (this.isSubflow) {
          this.tplChange(val);
        } else {
          this.pluginChange(val);
        }
      },
      getBasicConfig(val) {
        const {
          code,
          group_name: groupName,
          name,
          list,
          id: pluginId,
          group_id: groupId,
          metaUrl,
          apiKey,
        } = val;
        let versionList = [];
        if (this.isThirdParty) {
          versionList = list;
        } else if (!this.isApiPlugin) {
          versionList = this.getAtomVersions(code);
        }
        this.versionList = versionList;
        // 获取不同版本的描述
        let desc = val.desc || '';
        if (!this.isThirdParty && !this.isApiPlugin) {
          const atom = this.atomList.find(item => item.code === code);
          desc = atom.list.find(item => item.version === list[list.length - 1].version).desc;
        } else {
          desc = '';
        }
        if (desc && desc.includes('\n')) {
          const descList = desc.split('\n');
          desc = descList.join('<br>');
        }
        const config = {
          plugin: code,
          version: this.isApiPlugin ? 'V2.0.0' : list[list.length - 1].version,
          name: this.isThirdParty ? name : `${groupName}-${name}`,
          nodeName: name,
          stageName: '',
          nodeLabel: [],
          desc,
          ignorable: false,
          skippable: true,
          retryable: true,
          selectable: true,
        };
        if (this.isApiPlugin) {
          Object.assign(config, {
            pluginId,
            groupId,
            groupName,
            metaUrl,
            apiKey,
          });
        }
        return config;
      },
      /**
       * 标准插件切换
       * - 清除勾选变量与全局变量关联
       * - 更新基础信息
       * - 加载插件配置详情
       * - 校验基础信息
       */
      async pluginChange(atomGroup) {
        const config = this.getBasicConfig(atomGroup);
        this.updateBasicInfo(config);
        this.inputsParamValue = {};
        await this.getPluginDetail();
        if (Array.isArray(this.inputs)) {
          this.inputsRenderConfig = this.inputs.reduce((acc, crt) => {
            acc[crt.tag_code] = true;
            return acc;
          }, {});
        }
        this.$refs.basicInfo && this.$refs.basicInfo.validate(); // 清除节点保存报错时的错误信息
      },
      /**
       * 标准插件版本切换
       */
      async versionChange(val) {
        // 获取不同版本的描述
        let { desc } = this.basicInfo;
        if (!this.isThirdParty) {
          const atom = this.atomList.find(item => item.code === this.basicInfo.plugin);
          desc = atom.list.find(item => item.version === val).desc;
        }
        if (desc && desc.includes('\n')) {
          const descList = desc.split('\n');
          desc = descList.join('<br>');
        }
        this.updateBasicInfo({ version: val, desc });
        await this.clearParamsSourceInfo();
        this.inputsParamValue = {};
        await this.getPluginDetail();
        if (Array.isArray(this.inputs)) {
          this.inputsRenderConfig = this.inputs.reduce((acc, crt) => {
            acc[crt.tag_code] = true;
            return acc;
          }, {});
        }
      },
      /**
       * 子流程切换
       * - 清除勾选变量与全局变量关联
       * - 请求子流程模板详情，组装 scheme 和 value，更新基础信息
       * - 清除子流程更新（每次都调用，store 里方法对不存在新版本的模板有做兼容）
       * - 校验基础信息
       */
      async tplChange(data) {
        await this.getSubflowDetail(data.id, data.version);
        this.inputs = await this.getSubflowInputsConfig();
        this.inputsParamValue = this.getSubflowInputsValue(this.subflowForms);
        this.inputsRenderConfig = Object.keys(this.subflowForms).reduce((acc, crt) => {
          const formItem = this.subflowForms[crt];
          if (formItem.show_type === 'show') {
            acc[crt] = 'need_render' in formItem ? formItem.need_render : true;
          }
          return acc;
        }, {});
        this.setSubprocessUpdated({
          expired: false,
          subprocess_node_id: this.nodeConfig.id,
        });
        this.$refs.basicInfo && this.$refs.basicInfo.validate(); // 清除节点保存报错时的错误信息
      },
      /**
       * 更新基础信息
       * 填写基础信息表单，切换插件/子流程，选择插件版本，子流程更新
       */
      updateBasicInfo(data) {
        this.isDataChange = true;
        this.basicInfo = Object.assign({}, this.basicInfo, data);
      },
      // 输入参数表单值更新
      updateInputsValue(val) {
        this.isDataChange = true;
        this.inputsParamValue = val;
      },
      /**
       * 子流程版本更新
       */
      async updateSubflowVersion() {
        this.subflowVersionUpdating = true;
        const oldForms = Object.assign({}, this.subflowForms);
        // 获取最新的子流程输入输出数据
        await this.getSubflowDetail(this.basicInfo.tpl);
        await this.subflowUpdateParamsChange();
        // 获取子流程输入参数配置
        this.inputs = await this.getSubflowInputsConfig();
        this.subflowVersionUpdating = false;
        this.$nextTick(() => {
          this.inputsParamValue = this.getSubflowInputsValue(this.subflowForms, oldForms);
          this.inputsRenderConfig = Object.keys(this.subflowForms).reduce((acc, crt) => {
            const formItem = this.subflowForms[crt];
            if (formItem.show_type === 'show') {
              acc[crt] = 'need_render' in formItem ? formItem.need_render : true;
            }
            return acc;
          }, {});
          this.subflowUpdated = true;
        });
      },
      /**
       * 子流程版本更新后，输入、输出参数如果有变更，需要处理全局变量的 source_info 更新
       * 分为两种情况：
       * 1.输入、输出参数被勾选，并且对应变量在新流程模板中被删除或者变量 source_tag 有更新，需要在更新后修改全局变量 source_info 信息
       * 2.新增和修改输入、输出参数，不做处理
       */
      async subflowUpdateParamsChange() {
        this.isUpdateConstants = true;
        this.variableCited = await this.getVariableCitedData() || {};
        const nodeId = this.nodeConfig.id;
        Object.keys(this.localConstants).forEach((key) => {
          const varItem = this.localConstants[key];
          const { source_type: sourceType, source_info } = varItem;
          const sourceInfo = source_info[this.nodeId];
          if (sourceInfo) {
            if (sourceType === 'component_inputs' || sourceType === 'custom') {
              sourceInfo.forEach((nodeFormItem) => {
                const newTplVar = this.subflowForms[nodeFormItem];

                if (!newTplVar || newTplVar.source_tag !== varItem.source_tag) { // 变量被删除或者变量类型有变更
                  this.setVariableSourceInfo({
                    key,
                    id: nodeId,
                    type: 'delete',
                    tagCode: nodeFormItem,
                  });
                }
              });
            }
            if (sourceType === 'component_outputs' || sourceType === 'custom') {
              sourceInfo.forEach((nodeFormItem) => {
                if (!this.outputs.find(item => item.key === nodeFormItem)) {
                  this.setVariableSourceInfo({
                    key,
                    id: nodeId,
                    type: 'delete',
                    tagCode: nodeFormItem,
                  });
                }
              });
            }
          }
        });
        this.variableCited = {};
        this.isUpdateConstants = false;
      },
      // 取消已勾选为全局变量的输入、输出参数勾选状态
      async clearParamsSourceInfo(inputs = this.inputs) {
        this.isUpdateConstants = true;
        this.variableCited = await this.getVariableCitedData() || {};
        const nodeId = this.nodeConfig.id;
        Object.keys(this.localConstants).forEach((key) => {
          const varItem = this.localConstants[key];
          const { source_type: sourceType, source_info } = varItem;
          const sourceInfo = source_info[this.nodeId];
          if (sourceInfo) {
            if (sourceType === 'component_inputs') {
              inputs.forEach((formItem) => {
                if (sourceInfo.includes(formItem.tag_code)) {
                  this.setVariableSourceInfo({
                    key,
                    id: nodeId,
                    type: 'delete',
                    tagCode: formItem.tag_code,
                  });
                }
              });
            }
            if (sourceType === 'component_outputs') {
              this.outputs.forEach((formItem) => {
                if (sourceInfo.includes(formItem.key)) {
                  this.setVariableSourceInfo({
                    key,
                    id: nodeId,
                    type: 'delete',
                    tagCode: formItem.key,
                  });
                }
              });
            }
          }
        });
        this.variableCited = {};
        this.isUpdateConstants = false;
      },
      // 重选插件
      handleReslectPlugin() {
        this.$parent.isNotExistAtomOrVersion = false;
        this.isSelectorPanelShow = true;
      },
      // 查看子流程模板
      onViewSubflow(id) {
        const pathData = {
          name: 'templatePanel',
          params: {
            templateId: id,
            type: 'view',
          },
        };
        const { href } = this.$router.resolve(pathData);
        window.open(href, '_blank');
      },
      // 是否渲染豁免切换
      onRenderConfigChange(data) {
        this.isDataChange = true;
        const [key, val] = data;
        this.inputsRenderConfig[key] = val;
      },
      // 输入、输出参数勾选状态变化
      onHookChange(type, data) {
        if (type === 'create') {
          this.$set(this.localConstants, data.key, data);
        } else {
          this.variableCited = {};
          this.setVariableSourceInfo(data);
        }
        // 如果全局变量数据有变，需要更新popover
        this.randomKey = new Date().getTime();
      },
      // 更新全局变量的 source_info
      async setVariableSourceInfo(data) {
        const { type, id, key, tagCode, source } = data;
        const constant = this.localConstants[key];
        if (!constant) return;
        const sourceInfo = constant.source_info;
        if (type === 'add') {
          if (sourceInfo[id]) {
            sourceInfo[id].push(tagCode);
          } else {
            this.$set(sourceInfo, id, [tagCode]);
          }
        } else if (type === 'delete') {
          this.unhookingVarForm = { ...data, value: constant.value };
          if (!Object.keys(this.variableCited).length) {
            this.variableCited = await this.getVariableCitedData() || {};
          }
          const { activities, conditions, constants } = this.variableCited[key];
          const citedNum = activities.length + conditions.length + constants.length;
          if (citedNum <= 1) {
            // 直接删除引用量为1变量
            this.deleteUnhookingVar();
          } else {
            if (sourceInfo[id].length <= 1) {
              this.$delete(sourceInfo, id);
            } else {
              let atomIndex;
              sourceInfo[id].some((item, index) => {
                let result = false;
                if (item === tagCode) {
                  atomIndex = index;
                  result = true;
                }
                return result;
              });
              sourceInfo[id].splice(atomIndex, 1);
            }
            if (Object.keys(sourceInfo).length === 0) {
              this.$delete(this.localConstants, key);
            }
            let refType = Array.isArray(this.inputs) ? 'inputParams' : 'jsonSchemaInput';
            refType = source === 'output' ? 'outputParams' : refType;
            const refDom = this.$refs[refType];
            refDom && refDom.setFormData({ ...this.unhookingVarForm });
          }
        }
      },
      async getVariableCitedData() {
        try {
          const config = this.getNodeFullConfig();
          const activities = Object.assign({}, this.activities, { [this.nodeId]: config });
          const data = {
            activities,
            gateways: this.gateways,
            constants: { ...this.internalVariable, ...this.localConstants },
          };
          const resp = await this.getVariableCite(data);
          if (resp.result) {
            return resp.data.defined;
          }
        } catch (e) {
          console.log(e);
        }
      },
      deleteUnhookingVar() {
        const { key, source } = this.unhookingVarForm;
        this.$delete(this.localConstants, key);
        let refType = Array.isArray(this.inputs) ? 'inputParams' : 'jsonSchemaInput';
        refType = source === 'output' ? 'outputParams' : refType;
        const refDom = this.$refs[refType];
        refDom && refDom.setFormData({ ...this.unhookingVarForm });
      },
      onCancelVarConfirmClick() {
        const { key, source } = this.unhookingVarForm;
        const constant = this.localConstants[key];
        constant.source_info = {};
        const refDom = source === 'input' ? this.$refs.inputParams : this.$refs.outputParams;
        refDom && refDom.setFormData({ ...this.unhookingVarForm });
      },
      // 删除全局变量
      deleteVariable(key) {
        const constant = this.localConstants[key];

        Object.keys(this.localConstants).forEach((key) => {
          const varItem = this.localConstants[key];
          if (varItem.index > constant.index) {
            varItem.index = varItem.index - 1;
          }
        });

        this.$delete(this.localConstants, key);
      },
      // 节点配置面板表单校验，基础信息和输入参数
      validate() {
        return this.$refs.basicInfo.validate().then(() => {
          if (this.$refs.inputParams) {
            let result = this.$refs.inputParams.validate();
            // api插件额外校验json类型
            if (this.isApiPlugin && result) {
              // 校验api插件中json数据是否符合JSON格式
              result = this.handleJsonValueParse(true);
              if (!result) {
                this.$bkMessage({
                  message: this.$t('json数据格式不正确'),
                  theme: 'error',
                });
              }
            }
            return result;
          }
          if (this.$refs.specialPluginInputParams) {
            return this.$refs.specialPluginInputParams.validate();
          }
          return true;
        });
      },
      handleJsonValueParse(parse, params = this.inputsParamValue) {
        // api插件json字段展示解析优化
        if (this.isApiPlugin) {
          const jsonFields = [];
          const { properties = {} } = this.inputs;
          Object.keys(properties).forEach((key) => {
            if (properties[key].sourceType === 'json') {
              jsonFields.push(key);
            }
          });
          const result = jsonFields.every((key) => {
            const value = params[key];
            // 如果没有值或者值为变量则不进行后续校验
            if (!value || value in this.localConstants) return true;
            const match = tools.checkIsJSON(value);
            if (match) {
              params[key] = parse && JSON.parse(value);
              return true;
            }
            params[key] = !parse && JSON.stringify(value, null, 4);
            return false;
          });
          return result;
        }
        return true;
      },
      getNodeFullConfig() {
        let config;
        if (this.isSubflow) {
          const {
            nodeName,
            stageName,
            nodeLabel,
            selectable,
            alwaysUseLatest,
            schemeIdList,
            version,
            tpl,
            executor_proxy,
            retryable,
            skippable,
            ignorable,
            autoRetry,
            timeoutConfig,
          } = this.basicInfo;
          const constants = {};
          Object.keys(this.subflowForms).forEach((key) => {
            const constant = tools.deepClone(this.subflowForms[key]);
            if (constant.show_type === 'show') {
              constant.value = key in this.inputsParamValue
                ? tools.deepClone(this.inputsParamValue[key])
                : constant.value;
              constant.need_render = key in this.inputsRenderConfig ? this.inputsRenderConfig[key] : true;
            }
            constants[key] = constant;
          });
          config = Object.assign({}, this.nodeConfig, {
            constants,
            version,
            name: nodeName,
            stage_name: stageName,
            labels: nodeLabel,
            template_id: tpl,
            optional: selectable,
            always_use_latest: alwaysUseLatest,
            scheme_id_list: schemeIdList.filter(item => item),
            retryable,
            skippable,
            error_ignorable: ignorable,
            auto_retry: autoRetry,
            timeout_config: timeoutConfig,
          });
          if (this.common) {
            config.executor_proxy = executor_proxy.join(',');
          }
        } else {
          const {
            ignorable,
            nodeName,
            stageName,
            nodeLabel,
            plugin,
            retryable,
            skippable,
            selectable,
            version,
            autoRetry,
            timeoutConfig,
            executor_proxy,
          } = this.basicInfo;
          // 设置标准插件节点在 activity 的 component.data 值
          let data = {};
          if (this.basicInfo.plugin === 'dmn_plugin') { // 决策插件
            data = this.getDmnNodeComponentData();
            this.isInitDecision = false;
          } else {
            data = this.getNodeComponentData(plugin, version);
          }
          const component = {
            code: this.isThirdParty ? 'remote_plugin' : plugin,
            data,
            version: this.isThirdParty ? '1.0.0' : version,
          };
          if (this.isApiPlugin && this.basicInfo.pluginId) { // 新版api插件中component包含pluginId字段
            const { pluginId, name, metaUrl, groupId, groupName, apiKey } = this.basicInfo;
            component.api_meta = {
              id: pluginId,
              name: name.split('-')[1],
              meta_url: metaUrl,
              api_key: apiKey,
              category: {
                id: groupId,
                name: groupName,
              },
            };
            component.version = 'v2.0.0';
          }
          config = Object.assign({}, this.nodeConfig, {
            component,
            retryable,
            skippable,
            name: nodeName,
            stage_name: stageName,
            labels: nodeLabel,
            error_ignorable: ignorable,
            optional: selectable,
            auto_retry: autoRetry,
            timeout_config: timeoutConfig,
          });
          if (this.common) {
            config.executor_proxy = executor_proxy.join(',');
          }
          delete config.can_retry;
          delete config.isSkipped;
        }
        return config;
      },
      // 设置标准插件节点在 activity 的 component.data 值
      getNodeComponentData(plugin, version) {
        const data = {};
        Object.keys(this.inputsParamValue).forEach((key) => {
          const formVal = this.inputsParamValue[key];
          let hook = false;
          // 获取输入参数的勾选状态
          if (this.$refs.inputParams && this.$refs.inputParams.hooked) {
            hook = this.$refs.inputParams.hooked[key] || false;
          }
          const needRender = key in this.inputsRenderConfig ? this.inputsRenderConfig[key] : true;
          data[key] = {
            hook, // 页面实际未用到这个字段，作为一个标识位更新，确保数据正确
            need_render: needRender,
            value: tools.deepClone(formVal),
          };
        });
        // api插件需手动设置uniform_api_plugin_url和uniform_api_plugin_method
        if (this.isApiPlugin) {
          data.uniform_api_plugin_url = {
            hook: false,
            value: this.basicInfo.realMetaUrl,
          };
          data.uniform_api_plugin_method = {
            hook: false,
            value: this.basicInfo.method,
          };
          if (this.basicInfo.callback) {
            data.uniform_api_plugin_callback = {
              hook: false,
              value: this.basicInfo.callback,
            };
          } else if (this.basicInfo.polling) {
            data.uniform_api_plugin_polling = {
              hook: false,
              value: this.basicInfo.polling,
            };
          }
          if (this.basicInfo.respDataPath) {
            data.response_data_path = {
              hook: false,
              value: this.basicInfo.respDataPath,
            };
          }
        }
        // 第三方插件需手动设置plugin_code和plugin_version
        if (this.isThirdParty) {
          data.plugin_code = {
            hook: false,
            value: plugin,
          };
          data.plugin_version = {
            hook: false,
            value: version,
          };
        }
        return data;
      },
      // 决策表节点component.data
      getDmnNodeComponentData() {
        const data = {};
        Object.keys(this.inputsParamValue).forEach((key) => {
          const hook = false;
          const value = tools.deepClone(this.inputsParamValue[key]) || '';
          if (key === 'table_id') {
            data[key] = { hook, value };
          }  else {
            let variable = false;
            // 判断节点是否使用了变量
            const inputRef = this.$refs.specialPluginInputParams;
            if (inputRef) {
              const info = inputRef.inputs.find(item => item.id === key);
              variable = info && info.variableMode;
            }
            if (data.facts) {
              data.facts.value[key] = { value, variable };
            } else {
              data.facts = {
                hook,
                value: {
                  [key]: { value, variable },
                },
              };
            }
          }
        });
        return data;
      },
      /**
       * 同步节点配置面板数据到 store.activities
       */
      syncActivity() {
        const config = this.getNodeFullConfig();
        this.nodeConfig = config;
        this.setActivities({ type: 'edit', location: config });
      },
      handleVariableChange() {
        // 如果变量已删除，需要删除变量是否输出的勾选状态
        this.$store.state.template.outputs.forEach((key) => {
          if (!(key in this.localConstants)) {
            this.setOutputs({ changeType: 'delete', key });
          }
        });
        // 设置全局变量面板icon小红点
        const localConstantKeys = Object.keys(this.localConstants);
        if (Object.keys(this.constants).length !== localConstantKeys.length) {
          this.$emit('globalVariableUpdate', true);
        } else {
          localConstantKeys.some((key) => {
            let result = false;
            if (!(key in this.constants)) {
              this.$emit('globalVariableUpdate', true);
              result = true;
            }
            return result;
          });
        }

        this.setConstants(this.localConstants);
      },
      /**
       * 获取标准插件生命周期状态
       */
      getAtomPhase() {
        let phase = '';
        this.atomList.some((group) => {
          let result = false;
          if (group.code === this.basicInfo.plugin) {
            result = group.list.some((item) => {
              if (item.version === (this.basicInfo.version || 'legacy')) {
                phase = item.phase;
                result = true;
              }
              return result;
            });
          }
          return result;
        });
        return phase;
      },
      isOutputsChanged() {
        const localOutputs = [];
        const outputs = [];
        Object.keys(this.localConstants).forEach((key) => {
          const item = this.localConstants[key];
          if (item.source_type === 'component_outputs') {
            localOutputs.push(item);
          }
        });
        Object.keys(this.constants).forEach((key) => {
          const item = this.constants[key];
          if (item.source_type === 'component_outputs') {
            outputs.push(item);
          }
        });
        return !tools.isDataEqual(localOutputs, outputs);
      },
      // 打开全局变量编辑面板
      async openVariablePanel(variable = {}) {
        if (variable.key) {
          const variableData = this.variableList.find(item => item.key === variable.key);
          const variableCited = await this.getVariableCitedData() || {};
          const { activities, conditions, constants } = variableCited[variable.key];
          const cited = activities.length + conditions.length + constants.length;
          this.variableData = {
            ...variableData,
            cited,
          };
        } else {
          this.variableData = {
            custom_type: 'input',
            desc: '',
            form_schema: {},
            index: Object.keys(this.constants).length + 1,
            key: '',
            name: '',
            show_type: 'show',
            source_info: {},
            source_tag: 'input.input',
            source_type: 'custom',
            validation: '^.+$',
            pre_render_mako: false,
            value: '',
            version: 'legacy',
          };
        }
        this.isVariablePanelShow = true;
      },
      beforeClose() {
        if (this.isViewMode) {
          this.onClosePanel();
          return true;
        }
        if (this.isSelectorPanelShow) { // 当前为插件/子流程选择面板，但没有选择时，支持自动关闭
          if (!(this.isSubflow ? this.basicInfo.tpl : this.basicInfo.plugin)) {
            this.onClosePanel();
            return true;
          }
        }
        if (this.isVariablePanelShow) { // 变量编辑时，点击遮罩需要确认是否保存变量
          this.$refs.variableEdit.handleMaskClick();
          return false;
        }
        if (!this.isDataChange && !this.isOutputsChanged()) {
          this.onClosePanel();
          return true;
        }
        this.$bkInfo({
          ...this.infoBasicConfig,
          confirmFn: () => {
            this.onClosePanel();
          },
        });
        this.isSelectorPanelShow = false;
        return false;
      },
      onSaveConfig() {
        this.validate().then((result) => {
          if (result) {
            ['stageName', 'nodeName'].forEach((item) => {
              this.basicInfo[item] = this.basicInfo[item].trim();
            });
            const { alwaysUseLatest, latestVersion, version, skippable, retryable, selectable: optional,
                    desc, nodeName, autoRetry, timeoutConfig, executor_proxy,
            } = this.basicInfo;
            const nodeData = { status: '', skippable, retryable, optional, auto_retry: autoRetry, timeout_config: timeoutConfig, isActived: false };
            if (this.common) {
              nodeData.executor_proxy = executor_proxy.join(',');
            }
            if (!this.isSubflow) {
              const phase = this.getAtomPhase();
              nodeData.phase = phase;
            } else {
              if (this.subflowUpdated || alwaysUseLatest) {
                // 更新store存储的子流程更新信息
                this.setSubprocessUpdated({
                  expired: false,
                  subprocess_node_id: this.nodeConfig.id,
                });
                this.$emit('updateNodeInfo', this.nodeConfig.id, { hasUpdated: false });
              }
              if (!alwaysUseLatest && latestVersion && latestVersion !== version) {
                this.setSubprocessUpdated({ expired: true, subprocess_node_id: this.nodeConfig.id });
              }
              // 更新子流程已勾选的变量值
              Object.keys(this.localConstants).forEach((key) => {
                const constantValue = this.localConstants[key];
                const formValue = this.subflowForms[key];
                if (constantValue.is_meta && formValue) {
                  const schema = formSchema.getSchema(formValue.key, this.inputs);
                  constantValue.form_schema = schema;
                  constantValue.meta = formValue.meta;
                  // 如果之前选中的下拉项被删除了，则删除对应的值
                  const curVal = constantValue.value;
                  const isMatch = curVal ? schema.attrs.items.find(item => item.value === curVal) : true;
                  constantValue.value = isMatch ? curVal : '';
                }
              });
            }
            this.syncActivity();
            // 将第三方插件信息传给父级存起来
            if (this.isThirdParty) {
              const params = {
                desc,
                nodeName,
                version,
                list: tools.deepClone(this.versionList),
              };
              this.$parent.thirdPartyList[this.nodeId] = params;
            }
            this.handleVariableChange(); // 更新全局变量列表、全局变量输出列表、全局变量面板icon小红点
            this.$emit('updateNodeInfo', this.nodeId, nodeData);
            this.$emit('templateDataChanged');
            this.$emit('close');
          }
        });
      },
      onClosePanel(openVariablePanel) {
        this.$emit('updateNodeInfo', this.nodeId, { isActived: false });
        this.$emit('close', openVariablePanel);
      },
      // 决策表插件切换表的时候更新输出参数配置
      async updateOutputs(outputs) {
        try {
          if (!this.isInitDecision) {
             await this.clearParamsSourceInfo();
          }
          this.outputs = this.outputs.filter(item => !item.fromDmn);
          this.outputs.push(...outputs);
        } catch (error) {
          console.warn(error);
        }
      },
      // 决策表插件-切换决策表选项时需更新变量引用情况
      async updateVarCitedData() {
        try {
          this.variableCited = await this.getVariableCitedData() || {};
        } catch (error) {
          console.warn(error);
        }
      },
    },
  };
</script>
<style lang="scss">
@import '../../../../scss/mixins/scrollbar.scss';
.node-config-panel {
    height: 100%;
    .node-config {
        height: calc(100vh - 60px);
        overflow: hidden;
        .config-form {
            padding: 20px 30px 0 30px;
            height: calc(100% - 49px);
            overflow-y: auto;
            @include scrollbar;
        }
        .btn-footer {
            padding: 8px 30px;
            border-top: 1px solid #cacedb;
            .bk-button {
                margin-right: 10px;
                padding: 0 25px;
            }
        }
    }
    .config-section {
        position: relative;
        margin-bottom: 50px;
        & > h3 {
            margin: 0 0 20px 0;
            padding-bottom: 14px;
            font-size: 14px;
            font-weight: bold;
            line-height: 1;
            color: #313238;
            border-bottom: 1px solid #cacecb;
        }
        .citations-waivers-guide {
            position: absolute;
            right: 0;
            top: 0;
            color: #979ba5;
            font-size: 12px;
            cursor: pointer;
            &:hover {
                color: #3a84ff;
            }
        }
        .basic-info-wrapper {
            min-height: 250px;
        }
        .inputs-wrapper,
        .outputs-wrapper {
            min-height: 80px;
        }
        .section-tips {
            font-size: 16px;
            color: #c4c6cc;
            &:hover {
                color: #f4aa1a;
            }
        }
    }
    .bk-sideslider-content {
        overflow: initial;
    }
    .variable-edit-panel {
        height: calc(100vh - 60px);
        overflow: hidden;
    }
    .exception-wrap {
        height: 280px;
        margin-top: 100px;
        justify-content: center;
        .bk-exception-img {
            margin-bottom: 12px;
        }
        .bk-exception-text {
            font-size: 12px;
            color: #444444;
        }
        .text-wrap {
            color: #3a84ff;
            margin-top: 5px;
            cursor: pointer;
        }
    }
}
</style>
