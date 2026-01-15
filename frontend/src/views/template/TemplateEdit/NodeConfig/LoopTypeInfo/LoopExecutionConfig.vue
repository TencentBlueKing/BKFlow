<template>
  <div class="loop-execution-content">
    <bk-radio-group
      v-model="formData.type"
      @change="onLoopTypeChange">
      <bk-radio
        value="array_loop"
        ext-cls="loop-radio">
        {{ $t('按数组变量循环') }}
      </bk-radio>
      <!-- <bk-radio
        value="condition"
        ext-cls="loop-radio">
        {{ $t('按条件循环') }}
      </bk-radio> -->
      <bk-radio
        value="time_loop"
        ext-cls="loop-radio">
        {{ $t('固定循环次数') }}
      </bk-radio>
    </bk-radio-group>
    <div class="loop-config-contnet">
      <LoopVar
        v-if="formData.type === 'array_loop'"
        ref="arrayLoopRef"
        :var-list="formData.loop_params"
        :is-view-mode="isViewMode"
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
        <span class="count-label">{{ $t('循环次数') }}</span>
        <bk-slider
          v-model="formData.loop_times"
          class="count-slider"
          :show-input="true" />
      </div>
    </div>
  </div>
</template>

<script>
import tools from '@/utils/tools.js';
import LoopVar from './LoopVar.vue';
// import FullCodeEditor from '@/components/common/FullCodeEditor.vue';

export default {
  name: 'BatchExecutionConfig',
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
  },
  data() {
    // this.loopConfig.conditionCode = this.toggleExpressionFormat(this.loopConfig.conditionCode);
    return {
      formData: tools.deepClone(this.loopConfig),
    };
  },
  watch: {
    loopConfig: {
      handler(value) {
        this.formData = tools.deepClone(value);
      },
      deep: true,
    },
    'formData.loop_times': {
        handler(newVal, oldVal) {
          if (newVal !== oldVal) {
            this.$emit('change', this.formData);
          }
        },
      },
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
    onLoopTypeChange() {
      this.$emit('change', this.formData);
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
    margin-top: 6px;
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
      .count-slider{
        flex: 1;
      }
    }
  }
  .loop-radio{
    margin-right: 24px;
    margin-bottom: 16px;
    font-size: 12px;
  }
</style>
