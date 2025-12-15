<template>
  <div class="task-param-wrapper">
    <RenderForm
      v-if="!isConfigLoading"
      ref="renderForm"
      v-model="renderData"
      :scheme="renderConfig"
      :constants="variables"
      :form-option="renderOption"
      :is-trigger-config="true" />
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
  import renderFormSchema from '@/utils/renderFormSchema.js';
  import NoData from '@/components/common/base/NoData.vue';
  export default {
    name: 'VariableEdit',
    components: {
      RenderForm,
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
        renderConfig: [],
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
        this.getFormData();
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
      this.getFormData();
    },
    methods: {
      ...mapActions('template/', [
        'loadCustomVarCollection',
        'loadUniformApiMeta',
      ]),
      ...mapActions('atomForm/', [
        'loadAtomConfig',
        'loadPluginServiceDetail',
      ]),
      /**
       * 加载表单元素的标准插件配置文件
       */
      async getFormData() {
        let variableArray = [];
        this.renderConfig = [];
        this.renderData = {};
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
          let atomConfig;
          if (atomFilter.isConfigExists(atom, version, this.atomFormConfig)) { // 已加载过相同类型且相同版本的插件配置项，直接取缓存
            atomConfig = this.atomFormConfig[atom][version];
          } else {
            // api插件变量
            const codeType = sourceTag.split('.')[0] || customType;
            if (codeType === 'uniform_api') {
              atomConfig = await this.getApiAtomConfig(sourceInfo, sourceTag);
            } else if (pluginCode) {
              atomConfig = await this.getThirdPartyAtomConfig(pluginCode, version);
            } else {
              await this.loadAtomConfig({ name, atom, classify, version, space_id: this.spaceId });
              atomConfig = tools.deepClone(this.atomFormConfig[atom][version]);
            }
          }

          const isPreRenderMako = this.preMakoDisabled && variable.pre_render_mako; // 变量预渲染
          if (atomConfig) {
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
              this.metaConfig[key] = tools.deepClone(variable);
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
            this.renderConfig.push(currentFormConfig);
          }
          this.renderData[key] = tools.deepClone(variable.value);
        }
        if (this.isTriggerConfig && this.savedConstants && this.currentFormConfig.config.mode === 'form') {
          Object.keys(this.savedConstants).forEach((key) => {
               this.renderData[key] = tools.deepClone(this.savedConstants[key]);
          });
        }
        this.initialRenderData = this.renderData;
        this.$nextTick(() => {
          this.isConfigLoading = false;
          this.$emit('onChangeConfigLoading', false);
        });
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
      async getApiAtomConfig(sourceInfo, sourceTag) {
        try {
          const sourceNodeId = Object.keys(sourceInfo)[0];
          if (!sourceNodeId) return [];
          const { api_meta: apiMeta = {} } = this.activities[sourceNodeId].component;
          const { meta_url: metaUrl } = apiMeta;
          if (!metaUrl) return;
          // api插件配置
          const resp = await this.loadUniformApiMeta({
            templateId: this.templateId,
            spaceId: this.spaceId,
            meta_url: metaUrl,
            ...this.scopeInfo,
          });
          if (!resp.result) return;
          const tag = sourceTag.split('.')[1];
          const field = resp.data.inputs.find(item => item.key === tag);
          return renderFormSchema([field]);
        } catch (error) {
          console.warn(error);
        }
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
        return this.isConfigLoading ? false : await this.$refs.renderForm.validate();
      },
      judgeDataEqual() {
        const formValid = this.validate();
        if (formValid) {
          return tools.isDataEqual(this.initialRenderData, this.renderData);
        }
        return !this.$refs.renderForm;
      },
      getVariableData() {
        if (!this.validate()) {
          return;
        }
        const variables = tools.deepClone(this.constants);
        Object.keys(variables).forEach(async (key) => {
          const variable = variables[key];
          variable.value = this.renderData[key] || variable.value;
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
