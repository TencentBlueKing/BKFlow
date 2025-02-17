<template>
  <div class="input-item">
    <div class="field-wrap mr10">
      <span
        v-bk-overflow-tips
        class="field-name">{{ inputs.name }}</span>
      <i
        v-if="inputs.desc"
        v-bk-tooltips.top="{
          content: inputs.desc ,
          allowHTML: false,
          multiple: true,
          maxWidth: 400
        }"
        class="bk-icon icon-question-circle ml5" />
    </div>
    <span>{{ '=' }}</span>
    <div class="value-wrap ml10">
      <!--变量输入框-->
      <bk-select
        v-if="inputs.variableMode"
        v-model="formData[inputs.id]"
        ext-cls="value-selector"
        ext-popover-cls="value-selector-popover"
        :disabled="isViewMode"
        allow-create
        :empty-text="$t('无匹配数据，可【回车】插入后新建变量')"
        searchable>
        <bk-option
          v-for="option in variableList"
          :id="option.key"
          :key="option.index"
          :name="option.key">
          <span
            v-bk-overflow-tips
            class="key ellipsis">{{ option.key }}</span>
          <span
            v-bk-overflow-tips
            class="name ellipsis">{{ option.name }}</span>
        </bk-option>
      </bk-select>
      <!--默认输入框-->
      <value-selector
        v-else
        v-model="formData[inputs.id]"
        :column="inputs"
        :readonly="isViewMode" />
      <!--切换按钮-->
      <i
        v-if="render"
        v-bk-tooltips="inputs.variableMode ? $t('取消变量快捷输入') : $t('变量快捷输入')"
        :class="[
          'render-icon',
          inputs.variableMode ? 'common-icon-undo' : 'common-icon-variable',
          { 'is-disabled': isViewMode }
        ]"
        @click="switchInputModel" />
    </div>
  </div>
</template>

<script>
  import ValueSelector from '@/components/DecisionTable/common/ValueSelector.vue';
  export default {
    name: 'DmnPluginInputItem',
    components: {
      ValueSelector,
    },
    provide() {
      return {
        getFormData: () => this.formData,
      };
    },
    props: {
      inputs: {
        type: Object,
        default: () => ({}),
      },
      formData: {
        type: Object,
        default: () => ({}),
      },
      isViewMode: {
        type: Boolean,
        default: true,
      },
      variableList: {
        type: Array,
        default: () => ([]),
      },
      render: {
        type: Boolean,
        default: true,
      },
    },
    methods: {
      // 切换输入值/输入变量
      switchInputModel() {
        if (this.isViewMode) return;
        this.inputs.variableMode = !this.inputs.variableMode;
        this.formData[this.inputs.id] = undefined;
        this.$emit('clear');
      },
    },
  };
</script>

<style lang="scss" scoped>
.input-item {
  display: flex;
  align-items: center;
  height: 32px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #63656e;
  .field-wrap {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    width: 150px;
    justify-content: space-between;
    padding: 0 8px;
    background: #fafbfd;
    border: 1px solid #dfe0e5;
    .field-name {
      overflow: hidden;
      word-break: break-all;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    i {
      font-size: 12px;
      color: #b2bdcc;
    }
  }
  .value-wrap {
    flex: 1;
    display: flex;
    align-items: center;
    .value-selector {
      flex: 1;
      &.is-disabled {
        /deep/.bk-select-name {
          pointer-events: none;
          background: #fafbfd;
        }
      }
    }
    .render-icon {
      flex-shrink: 0;
      height: 32px;
      width: 32px;
      font-size: 16px;
      text-align: center;
      line-height: 32px;
      color: #979ba5;
      cursor: pointer;
      &:hover {
        color: #3a84ff;
      }
      &.is-disabled {
        color: #979ba5;
        background: #fafbfd;
        border-color: #dfe0e5;
        cursor: not-allowed;
      }
    }
  }
}
</style>
<style lang="scss">
.value-selector-popover {
  .bk-option-content {
    display: flex;
    align-items: center;
    .key {
      max-width: 200px;
    }
    .name {
      color: #c4c6cc;
      margin-left: 16px;
    }
    .ellipsis {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
  }
}
</style>
