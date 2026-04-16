<template>
  <div class="loop-execution-content">
    <LoopVar
      v-if="formData.type === 'array_loop'"
      ref="arrayLoopRef"
      :var-list="formData.loop_params"
      :is-view-mode="isViewMode"
      :subflow-forms="subflowForms"
      @change="onLoopVarListChange" />
    <!-- <FullCodeEditor
        v-if="formData.loopType === 'condition'"
        ref="fullCodeEditor"
        v-model="formData.conditionCode"
        v-validate="{ required: true }"
        class="loop-config-editor"
        :options="{ language: 'python', readOnly: isViewMode }"
        @input="onDataChange" /> -->
    <div
      v-if="formData.type === 'time_loop'"
      class="loop-config-count">
      <span
        v-bk-tooltips="loopCountTipsConfig"
        class="count-label count-laberl-tips">{{ $t('循环次数') }}</span>
      <bk-slider
        v-model="formData.loop_times"
        class="count-slider"
        :show-input="true"
        :min-value="1"
        :max-value="100"
        @input="onLoopTimesChange" />
    </div>
  </div>
</template>

<script>
import tools from '@/utils/tools.js';
import LoopVar from './LoopVar.vue';
import i18n from '@/config/i18n/index.js';
// import FullCodeEditor from '@/components/common/FullCodeEditor.vue';

export default {
  name: 'LoopExecutionConfig',
  components: {
    LoopVar,
    // FullCodeEditor,
  },
  props: {
    loopConfig: {
      type: Object,
      default: () => ({
        type: 'array_loop',
        params: [],
      }),
    },
    isViewMode: {
      type: Boolean,
      default: false,
    },
    subflowForms: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    // this.loopConfig.conditionCode = this.toggleExpressionFormat(this.loopConfig.conditionCode);
    return {
      formData: tools.deepClone(this.loopConfig),
      debounceTimer: null,
      loopCountTipsConfig: {
        allowHtml: true,
        theme: 'light',
        extCls: 'info-label-tips',
        content: i18n.t('最大循环次数为100'),
        placement: 'top-start',
      },
    };
  },
  watch: {
    loopConfig: {
      handler(value) {
        this.formData = tools.deepClone(value);
      },
      deep: true,
    },
  },
  beforeDestroy() {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
  },
  methods: {
    // onDataChange(value) {
    //   this.formData.conditionCode = value;
    // },
    toggleExpressionFormat(str, slice = true) {
      // const gwConfig = this.gateways[this.conditionData.nodeId];
      // const { parse_lang: parseLang } = gwConfig.extra_info || {};
      // if (parseLang !== 'MAKO') {
      //   return str;
      // }
      if (slice) {
        return /^\${.+\}$/.test(str) ? str.slice(2, -1) : str;
      }
      return `\${${str}}`;
    },
    onLoopVarListChange(list) {
      this.formData.loop_params = list;
      this.$emit('change', this.formData);
    },
    onLoopTimesChange() {
      this.debounceEmitChange();
    },
    debounceEmitChange() {
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer);
      }
      this.debounceTimer = setTimeout(() => {
        this.$emit('change', this.formData);
      }, 300);
    },
    validate() {
      const valid = this.$refs.arrayLoopRef;
      if (valid) {
        return valid.validate();
      }
      return Promise.resolve(true);
    },
  },
};
</script>

<style lang="scss" scoped>
  .loop-execution-content{
    margin: 17px 0;
    .loop-config-editor{
      height: 350px !important;
    }
    .loop-config-count{
      display: flex;
      align-items: center;
      margin-bottom: 15px;
      color: #63656E;
      .count-label{
        font-size: 12px;
        margin-right: 8px;
      }
      .count-tip{
        font-size: 12px;
        color: #979BA5;
        margin-right: 8px;
      }
      .count-slider{
        flex: 1;
      }
      .count-laberl-tips{
        position: relative;
        line-height: 21px;
        &::after {
            content: '';
            position: absolute;
            left: 0;
            bottom: -3px;
            border-top: 1px dashed #979ba5;
            width: 100%
        }
      }
    }
  }
</style>
