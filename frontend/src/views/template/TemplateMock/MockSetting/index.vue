<template>
  <bk-sideslider
    :is-show.sync="sideShow"
    :width="640"
    :show-mask="true"
    :quick-close="true"
    :before-close="handleCancel">
    <div
      slot="header"
      class="side-header">
      <span class="title">{{ $t('设置 Mock 数据') }}</span>
      <span class="vertical-line" />
      <span
        v-bk-overflow-tips
        class="node-name">{{ nodeConfig.name }}</span>
    </div>
    <div
      slot="content"
      v-bkloading="{ isLoading, opacity: 1 }"
      class="side-content">
      <bk-tab
        v-if="!isLoading"
        class="tab-wrap"
        :active.sync="activeTab"
        type="card-tab"
        :label-height="42"
        @tab-change="activeTab = $event">
        <bk-tab-panel
          name="mock"
          :label="$t('Mock数据')">
          <MockConfig
            ref="mockConfig"
            :node-config="nodeConfig"
            :outputs="outputs"
            :template-id="templateId"
            :space-id="spaceId"
            :constants="constants"
            :mock-data="mockData"
            :tpl-actions="tplActions"
            :is-api-plugin="isApiPlugin" />
        </bk-tab-panel>
        <bk-tab-panel
          name="pluginConfig"
          :label="$t('插件配置')">
          <PluginConfig
            :node-config="nodeConfig"
            :inputs="inputs"
            :outputs="outputs"
            :hooked="hooked"
            :template-id="templateId"
            :space-id="spaceId"
            :inputs-form-data="inputsFormData"
            :inputs-render-config="inputsRenderConfig"
            :sub-flow-forms="subFlowForms"
            :is-sub-flow="isSubFlow"
            :is-api-plugin="isApiPlugin"
            :constants="constants"
            @updateOutputs="updateOutputs" />
        </bk-tab-panel>
        <bk-tab-panel
          name="controlOption"
          :label="$t('流程控制选项')">
          <ControlOption
            :node-config="nodeConfig"
            :activities="activities"
            :is-sub-flow="isSubFlow" />
        </bk-tab-panel>
      </bk-tab>
    </div>
    <div
      slot="footer"
      class="pl30">
      <bk-button
        v-if="tplActions.includes('MOCK')"
        :disabled="isLoading"
        theme="primary"
        @click="handleConfirm(true)">
        {{ $t('确定') }}
      </bk-button>
      <bk-button
        theme="default"
        @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </div>
  </bk-sideslider>
</template>

<script>
  import tools from '@/utils/tools.js';
  import atomFilter from '@/utils/atomFilter.js';
  import jsonFormSchema from '@/utils/jsonFormSchema.js';
  import { mapState, mapActions } from 'vuex';
  import MockConfig from './components/MockConfig.vue';
  import PluginConfig from './components/PluginConfig.vue';
  import ControlOption from './components/ControlOption.vue';
  export default {
    name: 'TemplateMockSetting',
    components: {
      MockConfig,
      PluginConfig,
      ControlOption,
    },
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
      nodeId: {
        type: String,
        default: '',
      },
      mockData: {
        type: Array,
        default: () => ([]),
      },
      tplActions: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      return {
        sideShow: false,
        activeTab: 'mock',
        inputs: [],
        outputs: [],
        hooked: {},
        inputsFormData: {},
        inputsRenderConfig: {},
        subFlowForms: {},
        taskNodeLoading: false,
        subFlowLoading: false,
        constantsLoading: false,
      };
    },
    computed: {
      ...mapState({
        infoBasicConfig: state => state.infoBasicConfig,
        project_id: state => state.project.project_id,
        spaceId: state => state.template.spaceId,
        scopeInfo: state => state.template.scopeInfo,
        activities: state => state.template.activities,
        constants: state => state.template.constants,
        pluginConfigs: state => state.atomForm.config,
        pluginOutput: state => state.atomForm.output,
      }),
      nodeConfig() {
        return this.activities[this.nodeId];
      },
      isSubFlow() {
        return this.nodeConfig.type !== 'ServiceActivity';
      },
      isThirdPartyNode() {
        return this.nodeConfig.component.code === 'remote_plugin';
      },
      thirdPartyNodeCode() {
        if (!this.isThirdPartyNode) return '';
        let codeInfo = this.nodeConfig.component.data;
        codeInfo = codeInfo && codeInfo.plugin_code;
        codeInfo = codeInfo.value;
        return codeInfo;
      },
      isApiPlugin() {
        const { code } = this.nodeConfig?.component || {};
        return code === 'uniform_api';
      },
      compVersion() {
        let version = '';
        const { component } = this.nodeConfig;
        const has = Object.prototype.hasOwnProperty;
        if (this.isSubFlow) {
          version = has.call(this.nodeConfig, 'version') ? this.nodeConfig.version : ''; // 子流程版本，区别于标准插件版本
        } else {
          if (this.isThirdPartyNode) {
            version = component.data.plugin_version.value;
          } else if (this.isApiPlugin) {
            version = component.version;
          } else {
            version = has.call(component, 'version') ? component.version : 'legacy';
          }
        }
        return version;
      },
      templateId() {
        const { templateId } = this.$route.params;
        return templateId;
      },
      isLoading() {
        return (
          this.taskNodeLoading
          || this.subFlowLoading
          || this.constantsLoading
        );
      },
    },
    watch: {
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
      $.context.exec_env = 'NODE_EXEC_DETAIL';
      this.initData();
    },
    beforeDestroy() {
      $.context.exec_env = '';
    },
    methods: {
      ...mapActions('template/', [
        'getTemplatePublicData',
        'getCommonTemplatePublicData',
        'loadUniformApiMeta',
      ]),
      ...mapActions('task', [
        'loadSubflowConfig',
      ]),
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
      ]),
      // 初始化节点数据
      async initData() {
        try {
          if (this.isSubFlow) {
            const forms = {};
            const renderConfig = {};
            const constants = this.nodeConfig.constants || {};
            Object.keys(constants).forEach((key) => {
              const form = constants[key];
              if (form.show_type === 'show') {
                forms[key] = form;
                renderConfig[key] = 'need_render' in form ? form.need_render : true;
              }
            });
            await this.getSubFlowDetail(this.compVersion);
            this.inputs = await this.getSubFlowInputsConfig();
            this.inputsFormData = this.getSubFlowInputsValue(forms);
            this.inputsRenderConfig = renderConfig;
          } else {
            // 普通任务节点
            const { component } = this.nodeConfig;
            const paramsVal = {};
            const renderConfig = {};
            Object.keys(component.data || {}).forEach((key) => {
              const val = tools.deepClone(component.data[key].value);
              paramsVal[key] = val;
              renderConfig[key] = 'need_render' in component.data[key] ? component.data[key].need_render : true;
            });
            this.inputsRenderConfig = renderConfig;
            await this.getPluginDetail();
            // api插件json字段展示解析优化
            this.handleJsonValueParse(false, paramsVal);
            this.inputsFormData = paramsVal;
          }
          // 获取输入参数的勾选状态
          this.hooked = this.isApiPlugin ? {} : this.getFormsHookState();
        } catch (error) {
          console.warn(error);
        }
      },
      // 获取输入参数勾选状态
      getFormsHookState() {
        const hooked = {};
        const keys = Object.keys(this.constants);
        Array.isArray(this.inputs) && this.inputs.forEach((form) => {
          // 已勾选到全局变量中, 判断勾选的输入参数生成的变量及自定义全局变量source_info是否包含该节点对应表单tag_code
          // 可能存在表单勾选时已存在相同key的变量，选择复用自定义变量
          const isHooked = keys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (
              ['component_inputs', 'custom'].includes(varItem.source_type)
            ) {
              const sourceInfo                = varItem.source_info[this.nodeConfig.id];
              if (sourceInfo && sourceInfo.includes(form.tag_code)) {
                result = true;
              }
            }
            return result;
          });
          hooked[form.tag_code] = isHooked;
        });
        return hooked;
      },
      /**
       * 加载子流程任务节点输入、输出、版本配置项
       */
      async getSubFlowDetail(version = '') {
        this.subFlowLoading = true;
        try {
          const params = {
            templateId: this.nodeConfig.template_id,
            scheme_id_list: [],
            version,
          };
          params.project_id = this.project_id;
          const resp = await this.loadSubflowConfig(params);
          // 子流程的输入参数包括流程引用的变量、自定义变量和未被引用的变量
          this.subFlowForms = {
            ...resp.data.pipeline_tree.constants,
            ...resp.data.custom_constants,
            ...resp.data.constants_not_referred,
          };

          // 输出变量
          this.outputs = Object.keys(resp.data.outputs).map((item) => {
            const output = resp.data.outputs[item];
            const has = Object.prototype.hasOwnProperty;
            return {
              plugin_code: output.plugin_code,
              name: output.name,
              key: output.key,
              version: has.call(output, 'version')
                ? output.version
                : 'legacy',
              type: output.custom_type,
            };
          });
        } catch (e) {
          console.log(e);
        } finally {
          this.subFlowLoading = false;
        }
      },

      /**
       * 加载子流程输入参数表单配置项
       * 遍历每个非隐藏的全局变量，由 source_tag、custom_type 字段确定需要加载的标准插件
       * 同时根据 source_tag 信息获取全局变量对应标准插件的某一个表单配置项
       *
       * @return {Array} 每个非隐藏全局变量对应表单配置项组成的数组
       */
      async getSubFlowInputsConfig() {
        this.constantsLoading = true;
        const inputs = [];
        const variables = Object.keys(this.subFlowForms)
          .map(key => this.subFlowForms[key])
          .filter(item => item.show_type === 'show')
          .sort((a, b) => a.index - b.index);

        await Promise.all(variables.map(async (item) => {
          const variable = { ...item };
          const { key } = variable;
          const { name, atom, tagCode, classify }            = atomFilter.getVariableArgs(variable);
          const version = variable.version || 'legacy';
          const isThird = Boolean(variable.plugin_code);
          const atomConfig = await this.getAtomConfig({
            plugin: atom,
            version,
            classify,
            name,
            isThird,
          });
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
          if (
            ['input', 'textarea'].includes(variable.custom_type)
            && variable.validation !== ''
          ) {
            formItemConfig.attrs.validation.push({
              type: 'regex',
              args: variable.validation,
              error_message: this.$t('默认值不符合正则规则：') + variable.validation,
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
      setFormsSchema(inputs) {
        const keys = Object.keys(this.constants);
        const { properties = {} } = inputs;
        Object.keys(properties).forEach((form) => {
          // 已勾选到全局变量中, 判断勾选的输入参数生成的变量及自定义全局变量source_info是否包含该节点对应表单tag_code
          // 可能存在表单勾选时已存在相同key的变量，选择复用自定义变量
          keys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (
              ['component_inputs', 'custom'].includes(varItem.source_type)
            ) {
              const sourceInfo                = varItem.source_info[this.nodeConfig.id];
              if (sourceInfo && sourceInfo.includes(form)) {
                const schema = properties[form];
                this.inputsFormData[form] = `\${${form}}`;
                inputs.properties[form] = {
                  extend: {
                    can_hook: true,
                    hook: true,
                  },
                  title: schema.title,
                  type: 'string',
                  'ui:component': {
                    name: 'bfInput',
                    props: {
                      disabled: true,
                    },
                  },
                };
                result = true;
              }
            }
            return result;
          });
        });
      },
      /**
       * 加载标准插件表单配置项文件
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
          if (this.isApiPlugin) {
            const { api_meta: apiMeta } = this.nodeConfig.component || {};
            if (!apiMeta) return;
            // 统一api基础配置
            await this.loadAtomConfig({ atom: plugin, version, space_id: this.spaceId });
            // api插件配置
            const resp = await this.loadUniformApiMeta({
              templateId: this.templateId,
              spaceId: this.spaceId,
              meta_url: apiMeta.meta_url,
              ...this.scopeInfo,
            });
            if (!resp.result) return;
            // 输出参数
            const storeOutputs = this.pluginOutput.uniform_api[version];
            const outputs = resp.data.outputs || [];
            this.outputs = [...storeOutputs, ...outputs];
            const renderConfig = jsonFormSchema(resp.data, {
              disabled: true,
            });
            this.setFormsSchema(renderConfig);
            return renderConfig;
          }
          // 第三方插件
          if (isThird) {
            await this.getThirdConfig(plugin, version);
          } else {
            await this.loadAtomConfig({
              atom: plugin,
              version,
              classify,
              name,
              space_id: this.spaceId,
            });
            if (!this.isSubFlow) {
              this.outputs = this.pluginOutput[plugin][version];
            }
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
       * 获取子流程任务节点输入参数值
       */
      getSubFlowInputsValue(forms, oldForms = {}) {
        return Object.keys(forms).reduce((acc, cur) => {
          // 遍历新表单项
          const variable = forms[cur];
          if (variable.show_type === 'show') {
            let canReuse = false;
            const oldVariable = oldForms[cur];
            const isHooked = this.isInputParamsInConstants(variable);
            if (oldVariable && !isHooked) {
              // 旧版本中存在相同key的表单项，且不是勾选状态
              if (variable.custom_type || oldVariable.custom_type) {
                canReuse                  = variable.custom_type
                    === oldVariable.custom_type;
              } else {
                canReuse                  = variable.source_tag === oldVariable.source_tag;
              }
            }
            const val = canReuse
              ? this.inputsParamValue[cur]
              : variable.value;
            acc[variable.key] = tools.deepClone(val);
          }

          return acc;
        }, {});
      },
      // 输入参数是否已被勾选到全局变量
      isInputParamsInConstants(form) {
        return Object.keys(this.constants).some((key) => {
          const varItem = this.constants[key];
          const sourceInfo = varItem.source_info[this.nodeConfig.id];
          return sourceInfo && sourceInfo.includes(form.tag_code);
        });
      },
      /**
       * 加载标准插件节点输入参数表单配置项，获取输出参数列表
       */
      async getPluginDetail() {
        const plugin = this.isThirdPartyNode ? this.thirdPartyNodeCode : this.nodeConfig.component.code;
        const version = this.compVersion;
        this.taskNodeLoading = true;
        try {
          // 获取输入输出参数
          this.inputs = await this.getAtomConfig({ plugin, version, isThird: this.isThirdPartyNode }) || [];
          if (!this.isThirdPartyNode) {
            this.outputs = this.pluginOutput[plugin][version];
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.taskNodeLoading = false;
        }
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
            if (!value || value in this.constants) return true;
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
      async handleConfirm() {
        try {
          const { mockDataList, initDataList, validate } = this.$refs.mockConfig;
          const valid = await validate();
          if (!valid) return;
          if (!tools.isDataEqual(mockDataList, initDataList)) {
            // json字段解析
            const jsonFields = this.outputs.filter(item => item.type === 'json').map(item => item.key);
            mockDataList.forEach((item) => {
              Object.keys(item.data).forEach((key) => {
                const value = item.data[key];
                if (jsonFields.includes(key) && tools.checkIsJSON(value)) {
                  item.data[key] = JSON.parse(value);
                }
              });
            });
            this.$emit('updateMockData', {
              [this.nodeId]: [...mockDataList],
            });
          }
          this.$emit('onClose');
        } catch (error) {
          console.warn(error);
        }
      },
      updateOutputs(outputs) {
        this.outputs = this.outputs.filter(item => !item.fromDmn);
        this.outputs.push(...outputs);
      },
      // 关闭侧栏
      handleCancel() {
        if (this.$refs.mockConfig) {
          const { mockDataList, initDataList } = this.$refs.mockConfig;
          if (!tools.isDataEqual(mockDataList, initDataList)) {
            this.$bkInfo({
              ...this.infoBasicConfig,
              confirmFn: () => {
                this.$emit('onClose');
              },
            });
          } else {
            this.$emit('onClose');
          }
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
@import '../../../../scss/mixins/scrollbar.scss';
.side-header {
  display: flex;
  height: 100%;
  font-size: 16px;
  margin-left: -5px;
  padding-right: 20px;
  color: #63656e;
  .title {
    color: #313238;
  }
  .vertical-line {
    position: relative;
    top: 18px;
    right: -16px;
    height: 24px;
    width: 1px;
    background: #dcdee5;
  }
  .node-name {
    position: relative;
    display: inline-block;
    margin-left: 33px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
.side-content {
  height: calc(100vh - 114px);
  overflow: auto;
  @include scrollbar;
  .tab-wrap {
    height: 50px;
    padding: 8px 24px 0;
    background: #f0f1f5;
    ::v-deep .is-last::after {
      display: none !important;
    }
    ::v-deep .bk-tab-section {
      padding: 8px 0;
    }
  }
}
</style>
