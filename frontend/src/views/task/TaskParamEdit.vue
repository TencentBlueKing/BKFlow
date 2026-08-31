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
  <div class="task-param-wrapper">
    <bk-alert
      v-if="formLoadErrorMessage"
      type="error"
      :title="formLoadErrorMessage" />
    <template v-if="!isConfigLoading">
      <template v-for="section in formSections">
        <RenderForm
          v-if="section.type === 'array'"
          :key="`${randomKey}-${section.type}`"
          ref="renderForm-array"
          v-model="renderData"
          :scheme="section.scheme"
          :constants="variables"
          :form-option="renderOption" />
        <JsonschemaInputParams
          v-else
          :key="`${randomKey}-${section.type}`"
          ref="renderForm-object"
          :form-data="renderData"
          :schema="section.scheme"
          :is-view-mode="!editable"
          @update="updateRenderData" />
      </template>
    </template>
    <NoData
      v-if="isNoData && !isConfigLoading && !formLoadError"
      :message="$t('暂无参数')" />
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import { mapState, mapMutations, mapActions } from 'vuex';
  import atomFilter from '@/utils/atomFilter.js';
  import tools from '@/utils/tools.js';
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import JsonschemaInputParams from '@/views/template/TemplateEdit/NodeConfig/JsonschemaInputParams.vue';
  import NoData from '@/components/common/base/NoData.vue';
  import renderFormSchema from '@/utils/renderFormSchema.js';
  import { buildApiVariableFormFromExtraInfo, getApiVariableFormErrorMessage } from '@/utils/legacyApiVariableForm.js';
  import {
    buildV4PluginDetailRequest,
    buildVariablePluginRuntimeInputs,
    disablePluginFormFields,
    isV4OpenPlugin,
    mergeV4VariableObjectField,
    resolveVariableSourceComponent,
    validatePluginFormSections,
  } from '@/utils/uniformApi.js';
  export default {
    name: 'TaskParamEdit',
    components: {
      RenderForm,
      JsonschemaInputParams,
      NoData,
    },
    props: {
      constants: {
        type: Object,
        default() {
          return {};
        },
      },
      isUsedTipShow: {
        type: Boolean,
        default: true,
      },
      preMakoDisabled: {
        type: Boolean,
        default: false,
      },
      editable: {
        type: Boolean,
        default: true,
      },
      showRequired: {
        type: Boolean,
        default: true,
      },
      unUsedConstants: {
        type: Array,
        default: () => ([]),
      },
      templateId: {
        type: [Number, String],
        default: '',
      },
      activities: {
        type: Object,
        default() {
          return {};
        },
      },
    },
    data() {
      return {
        randomKey: new Date().getTime(),
        variables: tools.deepClone(this.constants),
        renderOption: {
          showRequired: true,
          showGroup: true,
          showLabel: true,
          showHook: false,
          showDesc: true,
          formEdit: this.editable,
        },
        formSections: [],
        metaConfig: {},
        renderData: {},
        initalRenderData: {},
        isConfigLoading: true,
        isNoData: false,
        pluginFormRequestId: 0,
        formGeneration: 0,
        formLoadError: null,
        formLoadErrorMessage: '',
        isDestroyed: false,
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.template.spaceId,
        scopeInfo: state => state.template.scopeInfo,
        atomFormConfig: state => state.atomForm.config,
      }),
      ...mapState('project', {
        project_id: state => state.project_id,
      }),
      reuseTaskId() {
        return this.$route.query.task_id;
      },
    },
    watch: {
      constants(val) {
        this.variables = tools.deepClone(val);
        this.getFormData();
      },
      editable(val) {
        this.$set(this.renderOption, 'formEdit', val);
        this.randomKey = new Date().getTime();
      },
    },
    created() {
      this.getFormData();
      if (this.showRequired === false) {
        this.renderOption.showRequired = this.showRequired;
      }
    },
    beforeDestroy() {
      this.isDestroyed = true;
      this.pluginFormRequestId += 1;
      this.formGeneration += 1;
      this.clearAtomForm();
    },
    methods: {
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
        'loadV4OpenPluginForm',
      ]),
      ...mapActions('template/', [
        'loadUniformApiMeta',
      ]),
      ...mapMutations('atomForm/', [
        'clearAtomForm',
      ]),
      ...mapActions('task/', [
        'getTaskInstanceData',
      ]),
      /**
       * 加载表单元素的标准插件配置文件
       */
      getV4Component(variable, atom, version) {
        return resolveVariableSourceComponent(variable, {
          activities: this.activities,
          atom,
          version,
        });
      },
      disableFields(keys, tip) {
        this.formSections = disablePluginFormFields(this.formSections, keys, {
          disabled: true,
          used_tip: tip,
        });
        this.randomKey = new Date().getTime();
      },
      resolveTemplateId() {
        if (this.templateId !== '' && this.templateId !== null && this.templateId !== undefined) {
          return this.templateId;
        }
        const route = this.$route || {};
        const params = route.params || {};
        const query = route.query || {};
        return params.templateId || query.template_id || '';
      },
      async loadV4VariableForm(variable, atom, version, generation) {
        const component = this.getV4Component(variable, atom, version);
        if (!isV4OpenPlugin(component)) return null;
        this.pluginFormRequestId += 1;
        const requestId = this.pluginFormRequestId;
        const isCurrent = () => !this.isDestroyed
          && generation === this.formGeneration
          && requestId === this.pluginFormRequestId;
        try {
          const result = await this.loadV4OpenPluginForm({
            request: buildV4PluginDetailRequest({
              component,
              spaceId: this.spaceId,
              templateId: this.resolveTemplateId(),
              scopeType: variable.scope_type,
              scopeValue: variable.scope_value,
            }),
            readOnly: !this.editable,
            isCurrent: () => isCurrent(),
            runtimeContext: {
              inputs: buildVariablePluginRuntimeInputs({
                variable,
                activities: this.activities,
                constants: this.variables,
              }),
              outputs: [],
              state: '',
            },
          });
          if (!isCurrent()) return { isV4: true, stale: true };
          return { isV4: true, ...result, component };
        } catch (error) {
          if (!isCurrent() || error?.code === 'FORM_LOAD_STALE') return { isV4: true, stale: true };
          const errorCode = error && error.code ? error.code : 'FORM_LOAD_FAILED';
          const pluginVersion = component.api_meta?.['plugin_version']
            || component.data?.['uniform_api_plugin_version']?.value
            || version
            || '--';
          this.$bkMessage({
            message: `${errorCode}: ${pluginVersion}`,
            theme: 'error',
          });
          return { isV4: true };
        }
      },
      appendJsonSchemaField(schema, formSchema, variable, tagCode) {
        const mergedSchema = mergeV4VariableObjectField(schema, formSchema, variable, tagCode);
        schema.properties = mergedSchema.properties;
        schema.required = mergedSchema.required;
      },
      appendArrayField(formConfig, formSchema, variable, tagCode) {
        if (!Array.isArray(formSchema)) return;
        const field = atomFilter.formFilter(tagCode, formSchema);
        if (field) {
          const item = tools.deepClone(field);
          item.tag_code = variable.key;
          item.name = variable.name;
          item.attrs = { ...(item.attrs || {}), desc: variable.desc };
          formConfig.push(item);
        }
      },
      updateRenderData(value) {
        this.renderData = { ...this.renderData, ...value };
      },
      async getFormData() {
        this.formLoadErrorMessage = '';
        this.formGeneration += 1;
        const generation = this.formGeneration;
        const isCurrentGeneration = () => !this.isDestroyed && generation === this.formGeneration;
        try {
        let variableArray = [];
        const nextFormSections = [];
        const nextRenderData = {};
        const nextMetaConfig = {};
        const arrayFormConfig = [];
        const jsonSchema = { type: 'object', properties: {}, required: [] };
        Object.keys(this.variables).forEach((cKey) => {
          const variable = tools.deepClone(this.variables[cKey]);
          // 输入参数只展示显示类型全局变量
          if (variable.show_type === 'show') {
            variableArray.push(variable);
          }
        });

        variableArray = variableArray.sort((a, b) => a.index - b.index);

        if (variableArray.length > 0) {
          if (isCurrentGeneration()) {
            this.formLoadError = null;
            this.isConfigLoading = true;
            this.$emit('onChangeConfigLoading', true);
          }
        }

        // 任务参数重用
        let pipelineTree = null;
        if (this.reuseTaskId) {
          const instanceData = await this.getTaskInstanceData(this.reuseTaskId);
          if (!isCurrentGeneration()) return;
          pipelineTree = JSON.parse(instanceData.pipeline_tree);
        }

        for (const variable of variableArray) {
          if (!isCurrentGeneration()) return;
          const { key } = variable;
          const { plugin_code: pluginCode } = variable;
          const { name, atom, tagCode, classify } = atomFilter.getVariableArgs(variable);
          // custom_type 可以判断是手动新建节点还是组件勾选
          const version = variable.version || 'legacy';
          const v4Result = await this.loadV4VariableForm(variable, atom, version, generation);
          if (!isCurrentGeneration()) return;
          if (v4Result && v4Result.isV4) {
            if (v4Result.stale) return;
            if (Array.isArray(v4Result.input)) {
              this.appendArrayField(arrayFormConfig, v4Result.input, variable, tagCode);
            } else {
              this.appendJsonSchemaField(jsonSchema, v4Result.input, variable, tagCode);
            }
            nextRenderData[key] = tools.deepClone(variable.value);
            continue;
          }
          let atomConfig;
          const codeType = (variable.source_tag || '').split('.')[0] || variable.custom_type;
          if (codeType === 'uniform_api') {
            atomConfig = await this.getApiAtomConfig(variable);
            if (!isCurrentGeneration()) return;
          } else if (atomFilter.isConfigExists(atom, version, this.atomFormConfig)) { // 已加载过相同类型且相同版本的插件配置项，直接取缓存
            atomConfig = this.atomFormConfig[atom][version];
          } else {
            if (pluginCode) {
              atomConfig = await this.getThirdPartyAtomConfig(pluginCode, version);
            } else {
              await this.loadAtomConfig({ name, atom, classify, version, space_id: this.spaceId });
              atomConfig = tools.deepClone(this.atomFormConfig[atom][version]);
            }
            if (!isCurrentGeneration()) return;
          }

          const isPreRenderMako = this.preMakoDisabled && variable.pre_render_mako; // 变量预渲染
          /* 暂不进行变量是否被使用判断 */
          // const isUsed = this.unUsedConstants.length && !this.unUsedConstants.includes(variable.key) // 变量是否被使用
          const isUsed = false;
          if (Array.isArray(atomConfig)) {
            atomConfig = atomConfig.map((item) => {
              const data = { ...item };
              if (!data.attrs) {
                data.attrs = {};
              }
              data.attrs.disabled = isPreRenderMako || isUsed;
              if (isPreRenderMako) {
                data.attrs.pre_mako_tip = i18n.t('设为「常量」的参数中途不允许修改');
              } else if (isUsed) {
                // data.attrs['used_tip'] = this.isUsedTipShow ? i18n.t('参数已被使用，不可修改') : ''
              } else {
                delete data.attrs.pre_mako_tip;
                delete data.attrs.used_tip;
              }
              if (data.attrs.children) { // 子组件是否禁用
                this.setAtomDisable(data.attrs.children, isPreRenderMako || isUsed);
              }
              return data;
            });
          }
          let currentFormConfig = tools.deepClone(atomFilter.formFilter(tagCode, atomConfig));
          // 任务参数重用(元变量单独处理)
          if (pipelineTree && !variable.is_meta) {
            const taskVariable = pipelineTree.constants[key];
            if (taskVariable && taskVariable.custom_type === variable.custom_type) { // 重用
              if (Object.prototype.toString.call(variable.value) === '[Object Object]') {
                const match = Object.keys(variable.value).every(key => key in taskVariable.value);
                if (match) {
                  variable.value = taskVariable.value;
                }
              } else {
                variable.value = taskVariable.value;
              }
            } else if (currentFormConfig) { // 不重用
              currentFormConfig.attrs.notReuse = true;
            }
          }

          if (currentFormConfig) {
            // 若该变量是元变量则进行转换操作
            if (variable.is_meta || currentFormConfig.meta_transform) {
              currentFormConfig = currentFormConfig.meta_transform(variable.meta || variable);
              // 执行过的元变量，attr配置需要单独处理
              if (this.preMakoDisabled && variable.pre_render_mako) {
                currentFormConfig.attrs.disabled = true;
                currentFormConfig.attrs.pre_mako_tip = i18n.t('设为「常量」的参数中途不允许修改');
              }
              // else if (this.unUsedConstants.length && !this.unUsedConstants.includes(variable.key)) {
              //     currentFormConfig.attrs['disabled'] = true
              //     currentFormConfig.attrs['used_tip'] = this.isUsedTipShow ? i18n.t('参数已被使用，不可修改') : ''
              // }
              nextMetaConfig[key] = tools.deepClone(variable);
              // 任务参数重用(元变量)
              const { remote_url: remoteUrl } = currentFormConfig.attrs;
              if (!remoteUrl && pipelineTree && pipelineTree.constants[key]) { // 重用(远程数据源不进行重用)
                const { value, meta, custom_type: customType } = pipelineTree.constants[key];
                const listType = customType === 'datatable' ? 'columns' : 'items';
                const match = meta && meta.value[`${listType}_text`].replace(/ /g, '') === JSON.stringify(currentFormConfig.attrs[listType]);
                if (match) {
                  currentFormConfig.attrs.value = value;
                }
              } else if (pipelineTree) { // 不重用
                currentFormConfig.attrs.notReuse = true;
              }
              if (!variable.meta) {
                variable.value = currentFormConfig.attrs.value;
              }
            }
            currentFormConfig.tag_code = key;
            currentFormConfig.name = variable.name; // 变量名称，全局变量编辑时填写的名称，和表单配置项 label 名称不同
            currentFormConfig.attrs.desc = variable.desc;

            // 参数填写时为保证每个表单 tag_code 唯一，原表单 tag_code 会被替换为变量 key，导致事件监听不生效
            const has = Object.prototype.hasOwnProperty;
            if (has.call(currentFormConfig, 'events')) {
              currentFormConfig.events.forEach((e) => {
                if (e.source === tagCode) {
                  e.source = `\${${e.source}}`;
                }
              });
            }

            if (
              ['input', 'textarea'].includes(variable.custom_type)
              && variable.validation !== ''
            ) {
              currentFormConfig.attrs.validation.push({
                type: 'regex',
                args: variable.validation,
                error_message: i18n.t('参数值不符合正则规则：') + variable.validation,
              });
            }
            arrayFormConfig.push(currentFormConfig);
          }
          nextRenderData[key] = tools.deepClone(variable.value);
        }
        if (!isCurrentGeneration()) return;
        if (arrayFormConfig.length > 0) {
          nextFormSections.push({ type: 'array', scheme: arrayFormConfig });
        }
        if (Object.keys(jsonSchema.properties).length > 0) {
          nextFormSections.push({
            type: 'object',
            scheme: {
              ...jsonSchema,
              required: [...new Set(jsonSchema.required)],
            },
          });
        }
        this.formSections = nextFormSections;
        this.renderData = nextRenderData;
        this.metaConfig = nextMetaConfig;
        this.isNoData = nextFormSections.length === 0;
        this.formLoadError = null;
        this.initalRenderData = this.renderData;
        this.$nextTick(() => {
          if (!isCurrentGeneration()) return;
          this.isConfigLoading = false;
          this.$emit('onChangeConfigLoading', false);
        });
        } catch (error) {
          if (!isCurrentGeneration()) return;
          this.formLoadError = error && error.code ? error.code : 'FORM_LOAD_FAILED';
          this.formLoadErrorMessage = getApiVariableFormErrorMessage(error, this.$t.bind(this));
          this.formSections = [];
          this.renderData = {};
          this.metaConfig = {};
          this.isNoData = true;
          this.isConfigLoading = false;
          this.$emit('onChangeConfigLoading', false);
        }
      },
      setAtomDisable(atomList, disabled = false) {
        atomList.forEach((item) => {
          if (!item.attrs) {
            item.attrs = {};
          }
          item.attrs.disabled = disabled;
          if (item.attrs.children) {
            this.setAtomDisable(item.attrs.children);
          }
        });
      },
      async getApiAtomConfig(variable = {}) {
        const { source_info: sourceInfo = {}, source_tag: sourceTag = '' } = variable;
        try {
          const sourceNodeId = Object.keys(sourceInfo)[0];
          const component = sourceNodeId && this.activities[sourceNodeId] && this.activities[sourceNodeId].component;
          const apiMeta = (component && component.api_meta) || {};
          const { meta_url: metaUrl } = apiMeta;
          if (metaUrl) {
            const resp = await this.loadUniformApiMeta({
              templateId: this.resolveTemplateId(),
              spaceId: this.spaceId,
              meta_url: metaUrl,
              ...(this.scopeInfo || {}),
              meta_url_template: apiMeta.meta_url_template,
              source_key: apiMeta.source_key,
              version: component.version,
            });
            if (resp && resp.result) {
              const tag = sourceTag.split('.')[1];
              const field = (resp.data.inputs || []).find(item => item.key === tag);
              if (field) return renderFormSchema([field]);
            }
          }
        } catch (error) {
          console.warn(error);
        }
        return buildApiVariableFormFromExtraInfo(variable);
      },
      async getThirdPartyAtomConfig(code, version) {
        try {
          const resp = await this.loadPluginServiceDetail({
            plugin_code: code,
            plugin_version: version,
            with_app_detail: true,
          });
          if (!resp.result) return;
          // 设置host
          const { origin } = window.location;
          const hostUrl = `${origin + window.SITE_URL}plugin_service/data_api/${code}/`;
          $.context.bk_plugin_api_host[code] = hostUrl;
          // 输入参数
          $.atoms[code] = {};
          const renderFrom = resp.data.forms.renderform;
          /* eslint-disable-next-line */
          eval(renderFrom)
          const atomConfig = $.atoms[code];
          return atomConfig;
        } catch (error) {
          console.warn(error);
        }
      },
      getFormRefs() {
        return ['array', 'object'].reduce((refs, type) => {
          const formRef = this.$refs[`renderForm-${type}`];
          if (Array.isArray(formRef)) {
            refs.push(...formRef);
          } else if (formRef) {
            refs.push(formRef);
          }
          return refs;
        }, []);
      },
      async validate() {
        if (this.isConfigLoading || this.formLoadError) return false;
        return validatePluginFormSections(this.getFormRefs());
      },
      judgeDataEqual() {
        const formvalid = this.validate();
        if (formvalid) {
          return tools.isDataEqual(this.initalRenderData, this.renderData);
        }
        return false;
      },
      getChangeParams() {
        return Object.keys(this.initalRenderData).reduce((acc, key) => {
          if (!(key in this.renderData) || !tools.isDataEqual(this.initalRenderData[key], this.renderData[key])) {
            acc.push(key);
          }
          return acc;
        }, []);
      },
      async getVariableData() {
        // renderform表单校验
        const formValid = await this.validate();
        if (!formValid) {
          return;
        }
        const variables = tools.deepClone(this.constants);
        Object.keys(variables).forEach(async (key) => {
          const variable = variables[key];
          if (variable.show_type === 'hide') {
            if (variable.is_meta) {
              const { plugin_code: pluginCode } = variable;
              const { name, atom, tagCode, classify } = atomFilter.getVariableArgs(variable);
              // custom_type 可以判断是手动新建节点还是组件勾选
              const version = variable.version || 'legacy';
              let atomConfig;
              if (atomFilter.isConfigExists(atom, version, this.atomFormConfig)) {
                atomConfig = this.atomFormConfig[atom][version];
              } else {
                if (pluginCode) {
                  atomConfig = await this.getThirdPartyAtomConfig(pluginCode, version);
                } else {
                  await this.loadAtomConfig({ name, atom, classify, version, space_id: this.spaceId });
                  atomConfig = this.atomFormConfig[atom][version];
                }
              }
              let currentFormConfig = tools.deepClone(atomFilter.formFilter(tagCode, atomConfig));
              currentFormConfig = currentFormConfig.meta_transform(variable.meta || variable);
              if (!('meta' in variable)) { // 元变量不存在meta字段
                variable.meta = tools.deepClone(variable);
              }
              variable.value = currentFormConfig.attrs.value;
            }
          } else {
            variable.value = this.renderData[key];
            if (variable.is_meta && !('meta' in variable)) { // 元变量不存在meta字段
              variable.meta = this.metaConfig[key];
            }
          }
        });
        return Promise.resolve(variables);
      },
    },
  };
</script>
<style lang="scss" scoped>
@import '../../scss/config.scss';
    .task-param-wrapper {
        ::v-deep .render-form {
            .form-item {
                margin-bottom: 20px;
            }
        }
    }
</style>
