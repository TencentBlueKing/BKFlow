<template>
  <div class="task-param-wrapper">
    <template v-if="!isConfigLoading">
      <template v-for="section in formSections">
        <RenderForm
          v-if="section.type === 'array'"
          :key="section.type"
          ref="renderForm-array"
          v-model="renderData"
          :scheme="section.scheme"
          :constants="variables"
          :form-option="renderOption"
          :is-trigger-config="true" />
        <JsonschemaInputParams
          v-else
          :key="section.type"
          ref="renderForm-object"
          :form-data="renderData"
          :schema="section.scheme"
          :is-view-mode="!editable"
          @update="updateRenderData" />
      </template>
    </template>
    <NoData
      v-if="isNoData && !isConfigLoading"
      :message="$t('暂无参数')" />
  </div>
</template>

<script>
  import { mapState, mapActions } from 'vuex';
  import tools from '@/utils/tools.js';
  import atomFilter from '@/utils/atomFilter.js';
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import JsonschemaInputParams from '@/views/template/TemplateEdit/NodeConfig/JsonschemaInputParams.vue';
  import renderFormSchema from '@/utils/renderFormSchema.js';
  import NoData from '@/components/common/base/NoData.vue';
  import {
    buildApiVariableFormFromExtraInfo,
    buildV4PluginDetailRequest,
    getPluginFormErrorKey,
    isV4OpenPlugin,
    isPluginFormStale,
    buildVariablePluginRuntimeInputs,
    resolveVariableSourceComponent,
    normalizePluginFormRefs,
    shouldNotifyPluginFormError,
    validatePluginFormSections,
  } from '@/utils/uniformApi.js';
  import { hasPluginFormFields, selectPluginFormField } from '@/utils/pluginFormLoader.js';
  export default {
    name: 'VariableEdit',
    components: {
      RenderForm,
      JsonschemaInputParams,
      NoData,
    },
    props: {
      templateId: {
        type: [String, Number],
        default: '',
      },
      constants: {
        type: Object,
        default() {
          return {};
        },
      },
      preMakoDisabled: {
        type: Boolean,
        default: false,
      },
      editable: {
        type: Boolean,
        default: true,
      },
      triggerConfig: {
        type: Object,
        default() {
          return {};
        },
      },
      isTriggerConfig: {
        type: Boolean,
        default: false,
      },
      savedRequestConstants: {
        type: Object,
        default() {
          return {};
        },
      },
    },
    data() {
      return {
        currentFormConfig: tools.deepClone(this.triggerConfig),
        savedConstants: tools.deepClone(this.savedRequestConstants),
        isConfigLoading: false,
        variables: tools.deepClone(this.constants),
        formSections: [],
        renderOption: {
          showRequired: true,
          showGroup: true,
          showLabel: false,
          showHook: false,
          showDesc: true,
          formEdit: this.editable,
        },
        metaConfig: {},
        renderData: {},
        initialRenderData: {},
        isNoData: false,
        triggerInputData: {},
        isInternalRenderDataUpdate: false,
        saveInitialBackfillData: {},
        pluginFormRequestId: 0,
        formGeneration: 0,
        isDestroyed: false,
        lastPluginFormErrorKey: '',
      };
    },
    computed: {
      ...mapState({
        atomFormConfig: state => state.atomForm.config,
        spaceId: state => state.template.spaceId,
        scopeInfo: state => state.template.scopeInfo,
        activities: state => state.template.activities,
      }),
    },
    watch: {
      constants(val) {
        this.variables = tools.deepClone(val);
        this.loadFormData();
      },
      savedRequestConstants(val) {
        if (val && this.isTriggerConfig) {
          this.savedConstants = tools.deepClone(val);
          if (Object.keys(this.savedConstants).length === 0) {
            this.renderData = tools.deepClone(this.initialRenderData);
          } else if (this.savedConstants && this.currentFormConfig.config.mode === 'form') {
              const newRenderData = tools.deepClone(this.renderData);
              Object.keys(val).forEach((key) => {
                newRenderData[key] = tools.deepClone(val[key]);
              });
              this.renderData = newRenderData;
              this.saveInitialBackfillData = newRenderData;
            }
        }
      },
      renderData(val) {
        if (this.isTriggerConfig) {
          if (this.currentFormConfig.config.mode === 'form') {
            this.$emit('change', tools.deepClone(val), this.saveInitialBackfillData, this.isEqual);
          }
        } else {
          this.$emit('change', tools.deepClone(val));
        }
      },
    },
    mounted() {
      this.loadFormData();
    },
    beforeDestroy() {
      this.isDestroyed = true;
      this.pluginFormRequestId += 1;
      this.formGeneration += 1;
    },
    methods: {
      ...mapActions('template/', [
        'loadCustomVarCollection',
        'loadUniformApiMeta',
      ]),
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
        'loadV4OpenPluginForm',
      ]),
      async loadFormData() {
        try {
          await this.getFormData();
        } catch (error) {
          if (error?.isV4PluginFormError) {
            if (shouldNotifyPluginFormError(error, () => !this.isDestroyed, this.lastPluginFormErrorKey)) {
              this.lastPluginFormErrorKey = getPluginFormErrorKey(error);
              this.$bkMessage({
                message: error.message || this.$t('原生表单加载失败'),
                theme: 'error',
              });
            }
            return;
          }
          console.warn(error);
        }
      },
      /**
       * 加载表单元素的标准插件配置文件
       */
      async getFormData() {
        this.formGeneration += 1;
        const generation = this.formGeneration;
        const isCurrentGeneration = () => !this.isDestroyed && generation === this.formGeneration;
        let variableArray = [];
        this.formSections = [];
        this.renderData = {};
        const arrayFormConfig = [];
        const jsonSchema = { type: 'object', properties: {}, required: [] };
        const nextRenderData = {};
        const nextMetaConfig = {};
        Object.keys(this.variables).forEach((key) => {
          const variable = tools.deepClone(this.variables[key]);
          // 输入参数只展示显示类型全局变量
          if (variable.show_type === 'show') {
            variableArray.push(variable);
          }
        });

        this.isNoData = variableArray.length === 0;

        variableArray = variableArray.sort((a, b) => a.index - b.index);

        if (variableArray.length > 0) {
          this.isConfigLoading = true;
          this.$emit('onChangeConfigLoading', true);
        }

        for (const variable of variableArray) {
          if (!isCurrentGeneration()) return;
          const {
            key,
            plugin_code: pluginCode,
            source_tag: sourceTag,
            source_info: sourceInfo,
            custom_type: customType,
          } = variable;
          const { name, atom, tagCode, classify } = atomFilter.getVariableArgs(variable);
          // custom_type 可以判断是手动新建节点还是组件勾选
          const version = variable.version || 'legacy';
          try {
            const v4Result = await this.loadV4VariableForm(variable, atom, version, generation);
            if (!isCurrentGeneration()) return;
            if (v4Result && v4Result.isV4) {
              if (v4Result.stale) return;
              if (!v4Result.input) {
                throw v4Result.error || new Error('FORM_LOAD_FAILED');
              }
              const field = selectPluginFormField(v4Result.input, tagCode);
              if (Array.isArray(v4Result.input)) {
                const formConfig = tools.deepClone(field);
                formConfig.tag_code = key;
                formConfig.name = variable.name;
                formConfig.attrs = { ...(formConfig.attrs || {}), desc: variable.desc };
                arrayFormConfig.push(formConfig);
              } else {
                const sourceKey = Object.keys(field.properties)[0];
                jsonSchema.properties[key] = field.properties[sourceKey];
                if ((field.required || []).includes(sourceKey)) jsonSchema.required.push(key);
              }
              nextRenderData[key] = tools.deepClone(variable.value);
              continue;
            }
          } catch (error) {
            if (isCurrentGeneration()) {
              this.isConfigLoading = false;
              this.$emit('onChangeConfigLoading', false);
              const v4Error = error instanceof Error ? error : new Error(error?.message || 'FORM_LOAD_FAILED');
              Object.assign(v4Error, error);
              v4Error.isV4PluginFormError = true;
              throw v4Error;
            }
            throw error;
          }
          let atomConfig;
          const codeType = (sourceTag || '').split('.')[0] || customType;
          if (codeType === 'uniform_api') {
            atomConfig = await this.getApiAtomConfig(sourceInfo, sourceTag, variable);
          } else if (atomFilter.isConfigExists(atom, version, this.atomFormConfig)) { // 已加载过相同类型且相同版本的插件配置项，直接取缓存
            atomConfig = this.atomFormConfig[atom][version];
          } else if (pluginCode) {
            atomConfig = await this.getThirdPartyAtomConfig(pluginCode, version);
          } else {
            await this.loadAtomConfig({ name, atom, classify, version, space_id: this.spaceId });
            atomConfig = tools.deepClone(this.atomFormConfig[atom][version]);
          }

          const isPreRenderMako = this.preMakoDisabled && variable.pre_render_mako; // 变量预渲染
          if (Array.isArray(atomConfig)) {
            atomConfig.forEach((item) => {
            if (!item.attrs) {
              item.attrs = {};
            }
            item.attrs.disabled = isPreRenderMako;
            if (isPreRenderMako) {
              item.attrs.pre_mako_tip = this.$t('设为「常量」的参数中途不允许修改');
            } else {
              delete item.attrs.pre_mako_tip;
              delete item.attrs.used_tip;
            }
            if (item.attrs.children) { // 子组件是否禁用
              this.setAtomDisable(item.attrs.children, isPreRenderMako);
            }
          });
          }
          let currentFormConfig = tools.deepClone(atomFilter.formFilter(tagCode, atomConfig));

          if (currentFormConfig) {
            // 若该变量是元变量则进行转换操作
            if (variable.is_meta || currentFormConfig.meta_transform) {
              currentFormConfig = currentFormConfig.meta_transform(variable.meta || variable);
              // 执行过的元变量，attr配置需要单独处理
              if (this.preMakoDisabled && variable.pre_render_mako) {
                currentFormConfig.attrs.disabled = true;
                currentFormConfig.attrs.pre_mako_tip = this.$t('设为「常量」的参数中途不允许修改');
              }
              nextMetaConfig[key] = tools.deepClone(variable);
              if (!variable.meta) {
                variable.value = currentFormConfig.attrs.value;
              }
            }
            currentFormConfig.tag_code = key;
            currentFormConfig.name = variable.name; // 变量名称，全局变量编辑时填写的名称，和表单配置项 label 名称不同
            currentFormConfig.attrs.desc = variable.desc;

            // 参数填写时为保证每个表单 tag_code 唯一，原表单 tag_code 会被替换为变量 key，导致事件监听不生效
            if ('events' in currentFormConfig) {
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
                error_message: this.$t('参数值不符合正则规则：') + variable.validation,
              });
            }
            arrayFormConfig.push(currentFormConfig);
          }
          nextRenderData[key] = tools.deepClone(variable.value);
        }
        if (!isCurrentGeneration()) return;
        const nextFormSections = [];
        if (hasPluginFormFields(arrayFormConfig)) {
          nextFormSections.push({ type: 'array', scheme: arrayFormConfig });
        }
        if (hasPluginFormFields(jsonSchema)) {
          nextFormSections.push({
            type: 'object',
            scheme: {
              ...jsonSchema,
              required: [...new Set(jsonSchema.required)],
            },
          });
        }
        if (this.isTriggerConfig && this.savedConstants && this.currentFormConfig.config.mode === 'form') {
          Object.keys(this.savedConstants).forEach((key) => {
            nextRenderData[key] = tools.deepClone(this.savedConstants[key]);
          });
        }
        this.formSections = nextFormSections;
        this.metaConfig = nextMetaConfig;
        this.renderData = nextRenderData;
        this.isNoData = nextFormSections.length === 0;
        this.initialRenderData = nextRenderData;
        this.lastPluginFormErrorKey = '';
        this.$nextTick(() => {
          if (!isCurrentGeneration()) return;
          this.isConfigLoading = false;
          this.$emit('onChangeConfigLoading', false);
        });
      },
      getV4Component(variable, atom, version) {
        return resolveVariableSourceComponent(variable, {
          activities: this.activities,
          atom,
          version,
        });
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
              templateId: this.templateId,
              scopeType: variable.scope_type || this.scopeInfo.scope_type,
              scopeValue: variable.scope_value || this.scopeInfo.scope_value,
            }),
            readOnly: !this.editable,
            isCurrent,
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
          return { isV4: true, ...result };
        } catch (error) {
          if (isPluginFormStale(error, isCurrent)) {
            return { isV4: true, stale: true };
          }
          return { isV4: true, error };
        }
      },
      updateRenderData(value) {
        this.renderData = { ...this.renderData, ...value };
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
      async getApiAtomConfig(sourceInfo, sourceTag, variable) {
        try {
          const sourceNodeId = Object.keys(sourceInfo || {})[0];
          const component = sourceNodeId && this.activities[sourceNodeId] && this.activities[sourceNodeId].component;
          const apiMeta = (component && component.api_meta) || {};
          const { meta_url: metaUrl } = apiMeta;
          if (metaUrl) {
            const resp = await this.loadUniformApiMeta({
              templateId: this.templateId,
              spaceId: this.spaceId,
              meta_url: metaUrl,
              ...this.scopeInfo,
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
      async validate() {
        if (this.isConfigLoading) return false;
        const formRefs = normalizePluginFormRefs([
          this.$refs['renderForm-array'],
          this.$refs['renderForm-object'],
        ]);
        return await validatePluginFormSections(formRefs);
      },
      async judgeDataEqual() {
        const formValid = await this.validate();
        if (formValid) {
          return tools.isDataEqual(this.initialRenderData, this.renderData);
        }
        return false;
      },
      async getVariableData() {
        if (!await this.validate()) {
          return;
        }
        const variables = tools.deepClone(this.constants);
        Object.keys(variables).forEach((key) => {
          const variable = variables[key];
          if (Object.prototype.hasOwnProperty.call(this.renderData, key)
            && this.renderData[key] !== undefined) {
            variable.value = this.renderData[key];
          }
        });
        return variables;
      },
    },
  };
</script>

<style lang="scss" scoped>
  ::v-deep .render-form {
    .rf-form-item {
      margin-bottom: 24px;
    }
    .rf-group-name {
      display: flex;
      align-items: center;
      margin-bottom: 8px;
      .name {
        font-size: 14px;
        line-height: 22px;
        padding: 0;
      }
      .scheme-code {
        color: #979ba5;
        margin-left: 15px;
      }
      &::before {
        display: none;
      }
    }
    .el-input-number {
      line-height: 32px;
    }
  }
</style>
