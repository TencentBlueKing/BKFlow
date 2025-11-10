<template>
  <section
    class="info-section input-section"
    data-test-id="taskExecute_form_inputParams">
    <h4 class="common-section-title">
      {{ $t('输入参数') }}
    </h4>
    <div
      v-if="!adminView"
      class="origin-value">
      <bk-switcher
        v-model="isShowInputOrigin"
        size="small"
        @change="inputSwitcher" />
      {{ 'Code' }}
    </div>
    <template v-if="!adminView">
      <SpecialPluginInputForm
        v-if="isSpecialPlugin && !isShowInputOrigin"
        :value="inputs"
        :code="pluginCode"
        :space-id="spaceId"
        :template-id="templateId"
        :is-view-mode="true"
        :variable-list="variableList"
        @updateOutputs="$emit('updateOutputs', $event)" />
      <div
        v-else-if="!isShowInputOrigin"
        class="input-table">
        <div class="table-header">
          <span class="input-name">{{ $t('参数名') }}</span>
          <span class="input-key">{{ $t('参数值') }}</span>
        </div>
        <template v-if="Array.isArray(renderConfig)">
          <RenderForm
            v-if="!isEmptyParams && !loading"
            :key="renderKey"
            v-model="inputRenderDate"
            :scheme="renderConfig"
            :form-option="renderOption"
            :constants="inputConstants" />
          <NoData v-else />
        </template>
        <template v-else>
          <jsonschema-form
            v-if="renderConfig.properties && Object.keys(renderConfig.properties).length > 0"
            :schema="renderConfig"
            :value="inputRenderDate" />
          <no-data v-else />
        </template>
      </div>
      <full-code-editor
        v-else
        :value="inputsInfo" />
    </template>
    <div
      v-else
      class="code-block-wrap">
      <VueJsonPretty :data="inputsInfo" />
    </div>
  </section>
</template>

<script>
  import VueJsonPretty from 'vue-json-pretty';
  import NoData from '@/components/common/base/NoData.vue';
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import JsonschemaForm from './JsonschemaForm.vue';
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import tools from '@/utils/tools.js';
  import SpecialPluginInputForm from '@/components/SpecialPluginInputForm/index.vue';
  export default {
    components: {
      VueJsonPretty,
      NoData,
      RenderForm,
      JsonschemaForm,
      FullCodeEditor,
      SpecialPluginInputForm,
    },
    props: {
      adminView: {
        type: Boolean,
        default: false,
      },
      loading: {
        type: Boolean,
        default: false,
      },
      inputs: {
        type: Object,
        default: () => ({}),
      },
      renderConfig: {
        type: [Array, Object],
        default: () => ([]),
      },
      constants: {
        type: Object,
        default: () => ({}),
      },
      renderData: {
        type: Object,
        default: () => ({}),
      },
      pluginCode: {
        type: String,
        default: '',
      },
      spaceId: {
        type: Number,
        default: 0,
      },
      templateId: {
        type: [Number, String],
        default: '',
      },
    },
    data() {
      return {
        isShowInputOrigin: false,
        inputsInfo: null,
        renderOption: {
          showGroup: false,
          showLabel: true,
          showHook: false,
          formEdit: false,
          formMode: false,
        },
        renderKey: null,
        inputConstants: {},
        inputRenderDate: {},
      };
    },
    computed: {
      isEmptyParams() {
        return this.renderConfig && this.renderConfig.length === 0;
      },
      // 特殊输入参数插件
      isSpecialPlugin() {
        return ['dmn_plugin', 'value_assign'].includes(this.pluginCode);
      },
      variableList() {
        return [...Object.values(this.constants)];
      },
    },
    watch: {
      inputs: {
        handler(val) {
          this.inputsInfo = tools.deepClone(val);
        },
        immediate: true,
      },
      constants: {
        handler(val) {
          const constants = tools.deepClone(val);
          if (constants.subflow_detail_var) {
            // 兼容接口返回的key值和form配置的key不同
            Object.keys(this.inputs).forEach((key) => {
              if (!(key in constants) && /^\${[^${}]+}$/.test(key)) {
                const varKey = key.split('').slice(2, -1)
                  .join('');
                if (varKey in constants) {
                  constants[key] = constants[varKey];
                  this.$delete(constants, varKey);
                }
              }
            });
          }
          this.inputConstants = constants;
        },
        deep: true,
      },
      renderData: {
        handler(val) {
          this.renderKey = new Date().getTime();
          const renderData = tools.deepClone(val);
          // 兼容form配置的key为变量的情况
          if (this.constants.subflow_detail_var) {
            Object.keys(this.renderData).forEach((key) => {
              const value = this.renderData[key];
              if (/^\${[^${}]+}$/.test(value) && key in this.inputConstants) {
                this.renderData[key] = this.inputConstants[key];
              }
            });
          }
          this.inputRenderDate = renderData;
        },
        deep: true,
        immediate: true,
      },
    },
    mounted() {
      $.context.exec_env = 'NODE_EXEC_DETAIL';
    },
    beforeDestroy() {
      $.context.exec_env = '';
    },
    methods: {
      inputSwitcher() {
        if (!this.isShowInputOrigin) {
          this.inputsInfo = this.constants.subflow_detail_var
            ? tools.deepClone(this.inputs)
            : JSON.parse(this.inputsInfo);
        } else {
          let info = this.inputs;
          if (this.constants.subflow_detail_var) {
            info = tools.deepClone(this.constants);
            this.$delete(info, 'subflow_detail_var');
          }
          this.inputsInfo = JSON.stringify(info, null, 4);
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
    .input-section .input-table {
        flex: 1;
        display: flex;
        flex-direction: column;
        max-width: 682px;
        border: 1px solid #dcdee5;
        border-bottom: none;
        border-radius: 2px;
        .table-header {
            display: flex;
            align-items: center;
            height: 42px;
            color: #313238;
            border-bottom: 1px solid #dcdee5;
            background: #fafbfd;
            > span {
                padding: 10px 13px;
            }
            .input-name {
                line-height: 20px;
                width: 30%;
            }
        }
        ::v-deep .render-form {
            >.rf-form-item,
            .rf-form-group >.rf-form-item {
                margin: 0;
                padding: 5px 0;
                width: 100% !important;
                border-bottom: 1px solid #dcdee5;
                label {
                    width: 30%;
                    text-align: left;
                    padding-left: 13px;
                    color: #63656e;
                    &::before {
                        content: initial;
                    }
                }
                >.rf-tag-form {
                    margin-left: 30%;
                    padding-left: 13px;
                    padding-right: 15px;
                }
                .el-table {
                    tr,
                    .el-table__cell {
                        height: 42px;
                        padding: 0;
                        background-color: initial;
                    }
                    .cell {
                        height: auto;
                        line-height: 20px;
                    }
                }
            }
        }
        ::v-deep .bk-schema-form {
            .bk-schema-form-group-content >.bk-form-item {
                margin: 0;
                padding: 5px 0;
                width: 100% !important;
                border-bottom: 1px solid #dcdee5;
                label {
                    width: 30% !important;
                    text-align: left;
                    padding-left: 13px;
                    color: #63656e;
                    &::before {
                        content: initial;
                    }
                }
                >.bk-form-content {
                    margin-left: 30% !important;
                    padding-left: 13px;
                    padding-right: 15px;
                    > div {
                      word-break: break-all;
                    }
                }
                .el-table {
                    tr,
                    .el-table__cell {
                        height: 42px;
                        padding: 0;
                        background-color: initial;
                    }
                    .cell {
                        height: auto;
                        line-height: 20px;
                    }
                }
            }
        }
        .no-data-wrapper {
            padding: 16px 13px;
            border-bottom: 1px solid #dcdee5;
        }
    }
    .input-section .full-code-editor {
        height: 400px;
    }
</style>
