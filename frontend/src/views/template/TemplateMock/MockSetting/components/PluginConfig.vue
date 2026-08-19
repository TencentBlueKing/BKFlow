<template>
  <section class="plugin-config-section">
    <h4 class="common-section-title">
      {{ $t('输入参数') }}
    </h4>
    <div class="input-wrap">
      <template v-if="isSpecialPlugin">
        <SpecialPluginInputForm
          :value="inputsFormData"
          :code="pluginCode"
          :is-view-mode="true"
          :space-id="spaceId"
          :template-id="templateId"
          :variable-list="variableList"
          @updateOutputs="$emit('updateOutputs', $event)" />
      </template>
      <template v-else-if="Array.isArray(inputs)">
        <render-form
          v-if="inputs.length > 0"
          ref="renderForm"
          :scheme="inputs"
          :hooked="hooked"
          :constants="isSubFlow ? subFlowForms : constants"
          :form-option="option"
          :form-data="inputsFormData"
          :render-config="inputsRenderConfig" />
        <no-data
          v-else
          :message="$t('暂无参数')" />
      </template>
      <template v-else>
        <jsonschema-input-params
          v-if=" inputs.properties && Object.keys(inputs.properties).length > 0"
          :schema="inputs"
          :is-view-mode="true"
          :is-api-plugin="isApiPlugin"
          :form-data="inputsFormData" />
        <no-data
          v-else
          :message="$t('暂无参数')" />
      </template>
    </div>
    <h4 class="common-section-title">
      {{ $t('输出参数') }}
    </h4>
    <div class="outputs-wrapper">
      <bk-table
        v-if="outputs.length"
        :data="outputList"
        :col-border="false"
        :row-class-name="getRowClassName">
        <bk-table-column
          :label="$t('名称')"
          :width="180"
          prop="name">
          <p
            slot-scope="props"
            v-bk-tooltips="props.row.description"
            class="output-name">
            {{ props.row.name }}
          </p>
        </bk-table-column>
        <bk-table-column
          label="KEY"
          class-name="param-key">
          <div
            slot-scope="props"
            class="output-key">
            <div
              v-bk-overflow-tips
              class="key">
              {{ props.row.key }}
            </div>
            <div
              v-if="props.row.hooked"
              class="hooked-input">
              {{ props.row.varKey }}
            </div>
            <span class="hook-icon-wrap">
              <i
                v-bk-tooltips="{
                  content: props.row.hooked
                    ? $t('取消变量引用') : $t('设置为变量'),
                  placement: 'bottom',
                  zIndex: 3000
                }"
                :class="[
                  'common-icon-variable-hook hook-icon',
                  {
                    actived: props.row.hooked,
                    disabled: true
                  }
                ]" />
            </span>
          </div>
        </bk-table-column>
      </bk-table>
      <no-data
        v-else
        :message="$t('暂无参数')" />
    </div>
  </section>
</template>

<script>
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import JsonschemaInputParams from '@/views/template/TemplateEdit/NodeConfig/JsonschemaInputParams.vue';
  import NoData from '@/components/common/base/NoData.vue';
  import SpecialPluginInputForm from '@/components/SpecialPluginInputForm/index.vue';

  export default {
    components: {
      RenderForm,
      JsonschemaInputParams,
      NoData,
      SpecialPluginInputForm,
    },
    props: {
      nodeConfig: {
        type: Object,
        default: () => ({}),
      },
      inputs: {
        type: [Object, Array],
        default: () => ([]),
      },
      outputs: {
        type: Array,
        default: () => ([]),
      },
      hooked: {
        type: Object,
        default: () => ({}),
      },
      inputsFormData: {
        type: Object,
        default: () => ({}),
      },
      inputsRenderConfig: {
        type: Object,
        default: () => ({}),
      },
      subFlowForms: {
        type: Object,
        default: () => ({}),
      },
      isSubFlow: {
        type: Boolean,
        default: false,
      },
      isApiPlugin: {
        type: Boolean,
        default: false,
      },
      constants: {
        type: Object,
        default: () => ({}),
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
    },
    data() {
      return {
        option: {
          showGroup: false,
          showHook: true,
          showLabel: true,
          showVarList: true,
          formEdit: false,
        },
      };
    },
    computed: {
      outputList() {
        const list = [];
        const varKeys = Object.keys(this.constants);
        this.outputs.forEach((param) => {
          let { key: varKey } = param;
          const isHooked = varKeys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (varItem && varItem.source_type === 'component_outputs') {
              const sourceInfo = varItem.source_info[this.nodeConfig.id];
              if (sourceInfo && sourceInfo.includes(param.key)) {
                varKey = item;
                result = true;
              }
            }
            return result;
          });
          list.push({
            key: param.key,
            varKey,
            name: param.name,
            description: param.schema ? param.schema.description : '--',
            version: param.version,
            status: param.status,
            hooked: isHooked,
          });
        });
        return list;
      },
      pluginCode() {
        const { code = '' } = this.nodeConfig.component || {};
        return code;
      },
      // 特殊输入参数插件
      isSpecialPlugin() {
        return ['dmn_plugin', 'value_assign'].includes(this.pluginCode);
      },
      variableList() {
        return [...Object.values(this.constants)];
      },
    },
    methods: {
      getRowClassName({ row }) {
        return row.status || '';
      },
    },
  };
</script>

<style lang="scss" scoped>
.plugin-config-section {
  padding-top: 20px;
  .common-section-title {
    color: #313238;
    font-weight: 600;
    line-height: 18px;
    font-size: 12px;
    margin-bottom: 16px;
    &::before {
      height: 18px;
      top: 0;
    }
  }
  .input-wrap {
    margin-bottom: 32px;
  }
  .output-key {
    display: flex;
    align-items: center;
    padding-right: 50px;
    .key {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .hooked-input {
      flex: 1;
      height: 32px;
      min-width: 180px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 8px;
      margin-left: 15px;
      background: #fafbfd;
      border: 1px solid #dcdee5;
      border-radius: 2px;
    }
  }
  .output-name {
    display: inline-block;
    max-width: 100%;
    border-bottom: 1px dashed #979ba5;
    cursor: default;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .hook-icon-wrap {
    position: absolute;
    right: 22px;
    top: 5px;
    display: inline-block;
    width: 32px;
    height: 32px;
    line-height: 32px;
    background: #f0f1f5;
    text-align: center;
    border-radius: 2px;
    .hook-icon {
      font-size: 16px;
      color: #979ba5;
      cursor: pointer;
      &.disabled {
        color: #c4c6cc;
        cursor: not-allowed;
      }
      &.actived {
        color: #3a84ff;
      }
      }
  }
  .no-data-wrapper {
    padding-top: 20px;
  }
}
</style>
