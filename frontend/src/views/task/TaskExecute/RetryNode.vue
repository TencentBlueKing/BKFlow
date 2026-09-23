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
  <div
    v-bkloading="{ isLoading: loading, opacity: 1, zIndex: 100 }"
    class="retry-node-container">
    <div class="edit-wrapper">
      <RenderForm
        v-if="Array.isArray(renderConfig) && !isEmptyParams && !loading"
        ref="renderForm"
        v-model="renderData"
        :scheme="renderConfig"
        :form-option="renderOption" />
      <JsonschemaInputParams
        v-else-if="!Array.isArray(renderConfig) && !isEmptyParams && !loading"
        ref="renderForm"
        :form-data="renderData"
        :schema="renderConfig"
        :is-view-mode="false"
        @update="renderData = $event" />
      <NoData v-else />
    </div>
    <div class="action-wrapper">
      <bk-button
        theme="primary"
        class="confirm-btn"
        :loading="retrying"
        data-test-id="taskExcute_form_configRetryBtn"
        @click="onRetryTask">
        {{ $t('确定') }}
      </bk-button>
      <bk-button
        theme="default"
        data-test-id="taskExcute_form_cancelBtn"
        @click="onCancelRetry">
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import { mapState, mapActions } from 'vuex';
  import tools from '@/utils/tools.js';
  import NoData from '@/components/common/base/NoData.vue';
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import JsonschemaInputParams from '@/views/template/TemplateEdit/NodeConfig/JsonschemaInputParams.vue';
  import atomFilter from '@/utils/atomFilter.js';
  import {
    buildV4PluginDetailRequest,
    isV4OpenPlugin,
    resolveNodeExecutionPayload,
    resolveV4OpenPluginVersion,
  } from '@/utils/uniformApi.js';
  import { hasPluginFormFields } from '@/utils/pluginFormLoader.js';
  export default {
    name: 'RetryNode',
    components: {
      RenderForm,
      JsonschemaInputParams,
      NoData,
    },
    props: {
      nodeDetailConfig: {
        type: Object,
        default: () => ({}),
      },
      spaceId: {
        type: [Number, String],
        default: 0,
      },
      templateId: {
        type: [Number, String],
        default: '',
      },
      scopeInfo: {
        type: Object,
        default: () => ({}),
      },
      nodeInputs: {
        type: Object,
        default: () => ({}),
      },
      retrying: Boolean,
      nodeInfo: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        loading: false,
        bkMessageInstance: null,
        renderOption: {
          showGroup: false,
          showLabel: true,
          showHook: false,
        },
        renderConfig: [],
        renderData: {},
        initalRenderData: {},
        pluginFormRequestId: 0,
        isDestroyed: false,
      };
    },
    computed: {
      ...mapState({
        atomFormConfig: state => state.atomForm.config,
      }),
      ...mapState('project', {
        project_id: state => state.project_id,
      }),
      isEmptyParams() {
        return !hasPluginFormFields(this.renderConfig);
      },
      nodeComponent() {
        return this.nodeDetailConfig.component
          || this.nodeInfo.component
          || {
            code: this.nodeDetailConfig.component_code,
            version: this.nodeDetailConfig.version,
            data: this.nodeDetailConfig.componentData || {},
            api_meta: this.nodeDetailConfig.api_meta || {},
          };
      },
      isV4OpenPlugin() {
        return isV4OpenPlugin(this.nodeComponent);
      },
      componentValue() {
        const { componentData, component_code: componentCode } = this.nodeDetailConfig;
        if (componentCode === 'subprocess_plugin') {
          return componentData.subprocess.value;
        }
        return {};
      },
    },
    watch: {
      nodeInputs: {
        handler(value) {
          this.initalRenderData = tools.deepClone(value);
          this.renderData = tools.deepClone(value);
        },
        immediate: true,
      },
    },
    mounted() {
      $.context.exec_env = 'NODE_RETRY';
      const { version, component_code: componentCode } = this.nodeDetailConfig;
      if (componentCode) {
        this.getNodeConfig(componentCode, version);
      }
    },
    beforeDestroy() {
      this.isDestroyed = true;
      this.pluginFormRequestId += 1;
      $.context.exec_env = '';
    },
    methods: {
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
        'loadV4OpenPluginForm',
      ]),
      async getNodeConfig(type, version) {
        this.pluginFormRequestId += 1;
        const requestId = this.pluginFormRequestId;
        const canApply = () => !this.isDestroyed && requestId === this.pluginFormRequestId;
        this.loading = true;
        try {
          if (this.isV4OpenPlugin) {
            this.renderConfig = [];
            const execution = resolveNodeExecutionPayload(this.nodeInfo);
            const result = await this.loadV4OpenPluginForm({
              request: buildV4PluginDetailRequest({
                component: this.nodeComponent,
                spaceId: this.spaceId,
                templateId: this.templateId,
                scopeType: this.scopeInfo.scope_type || '',
                scopeValue: this.scopeInfo.scope_value ?? '',
              }),
              readOnly: false,
              isCurrent: canApply,
              runtimeContext: {
                inputs: this.renderData,
                outputs: execution.outputs,
                state: execution.state,
              },
            });
            if (!canApply()) return;
            this.renderConfig = result.input;
            return;
          }
          if (atomFilter.isConfigExists(type, version, this.atomFormConfig)) {
            if (!canApply()) return;
            this.renderConfig = this.atomFormConfig[type][version];
            return;
          }
          // 第三方插件节点拼接输出参数
          if (this.nodeDetailConfig.component_code === 'remote_plugin') {
            const { inputs } = this.nodeInfo.data;
            const pluginVersion = inputs && inputs.plugin_version;
            const pluginCode = inputs && inputs.plugin_code;
            const resp = await this.loadPluginServiceDetail({
              plugin_code: pluginCode,
              plugin_version: pluginVersion,
              with_app_detail: true,
            });
            if (!canApply()) return;
            if (!resp.result) return;

            // 设置host
            const { origin } = window.location;
            const hostUrl = `${origin + window.SITE_URL}plugin_service/data_api/${pluginCode}/`;
            $.context.bk_plugin_api_host[pluginCode] = hostUrl;
            if (!canApply()) return;
            // 输入参数
            const renderFrom = resp.data.forms.renderform;
            /* eslint-disable-next-line */
                          eval(renderFrom)
            if (!canApply()) return;
            const config = $.atoms[pluginCode];
            this.renderConfig = config || [];
            return;
          }
          if (type === 'subprocess_plugin') {
            const { constants } = this.componentValue.pipeline;
            const config = await this.getSubflowInputsConfig(constants, canApply);
            if (!canApply()) return;
            this.renderConfig = config || [];
            return;
          }
          await this.loadAtomConfig({ atom: type, version, space_id: this.spaceId });
          if (!canApply()) return;
          this.renderConfig = this.atomFormConfig[type][version];
        } catch (error) {
          if (!canApply()) return;
          if (error && error.code === 'FORM_LOAD_STALE') return;
          if (!this.isV4OpenPlugin) {
            console.log(error);
            return;
          }
          const errorCode = error && error.code ? error.code : 'FORM_LOAD_FAILED';
          const pluginVersion = resolveV4OpenPluginVersion(this.nodeComponent) || version || '--';
          this.$bkMessage({
            message: `${errorCode}: ${pluginVersion}`,
            theme: 'error',
          });
        } finally {
          if (canApply()) this.loading = false;
        }
      },
      /**
       * 加载子流程输入参数表单配置项
       * 遍历每个非隐藏的全局变量，由 source_tag、coustom_type 字段确定需要加载的标准插件
       * 同时根据 source_tag 信息获取全局变量对应标准插件的某一个表单配置项
       *
       * @return {Array} 每个非隐藏全局变量对应表单配置项组成的数组
       */
      async getSubflowInputsConfig(subflowForms, isCurrent = () => true) {
        const inputs = [];
        const variables = Object.keys(subflowForms)
          .map(key => subflowForms[key])
          .filter(item => item.show_type === 'show')
          .sort((a, b) => a.index - b.index);

        await Promise.all(variables.map(async (item) => {
          const variable = { ...item };
          const { key } = variable;
          const { name, atom, tagCode, classify } = atomFilter.getVariableArgs(variable);
          const version = variable.version || 'legacy';
          const isThird = Boolean(variable.plugin_code);
          const atomConfig = await this.getAtomConfig({ plugin: atom, version, classify, name, isThird });
          if (!isCurrent()) return;
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
        if (!isCurrent()) return null;
        return inputs;
      },
      /**
       * 加载标准插件表单配置项文件
       * 优先取 store 里的缓存
       */
      async getAtomConfig(config) {
        const { plugin, version, classify, name } = config;
        try {
          // 先取标准节点缓存的数据
          const pluginGroup = this.atomFormConfig[plugin];
          if (pluginGroup && pluginGroup[version]) {
            return pluginGroup[version];
          }
          await this.loadAtomConfig({ atom: plugin, version, classify, name, space_id: this.spaceId });
          const config = $.atoms[plugin];
          return config;
        } catch (e) {
          console.log(e);
        }
      },
      judgeDataEqual() {
        return tools.isDataEqual(this.initalRenderData, this.renderData);
      },
      async onRetryTask() {
        let formvalid = true;
        if (this.$refs.renderForm) {
          formvalid = await this.$refs.renderForm.validate();
        }
        if (!formvalid || this.retrying) return false;

        const { instance_id, component_code: componentCode, node_id } = this.nodeDetailConfig;
        try {
          if (this.nodeDetailConfig.component_code) {
            const data = {
              instance_id,
              node_id,
              component_code: componentCode,
              inputs: this.renderData,
            };
            if (componentCode === 'subprocess_plugin') {
              const { inputs } = this.nodeInfo.data;
              const constants = inputs.subprocess ? inputs.subprocess.pipeline.constants : {};
              Object.keys(constants).forEach((key) => {
                constants[key].value = this.renderData[key];
              });
              data.inputs = inputs;
              // eslint-disable-next-line
              data.inputs._escape_render_keys = ['subprocess']
            }
            this.$emit('retrySuccess', data);
          } else {
            this.$emit('retrySuccess', { instance_id, node_id });
          }
        } catch (e) {
          console.log(e);
        }
      },
      onCancelRetry() {
        const { node_id } = this.nodeDetailConfig;
        this.$emit('retryCancel', node_id);
      },
    },
  };
</script>
<style lang="scss" scoped>
    @import '../../../scss/config.scss';
    @import '../../../scss/mixins/scrollbar.scss';
    .retry-node-container {
        position: relative;
        height: 100%;
        overflow: hidden;
        .edit-wrapper {
            padding: 20px;
            height: calc(100% - 60px);
            overflow-y: auto;
            @include scrollbar;
        }
        .action-wrapper {
            padding-left: 20px;
            height: 60px;
            line-height: 60px;
            border-top: 1px solid $commonBorderColor;
            .confirm-btn{
                margin-right: 12px;
            }
        }
    }
</style>
