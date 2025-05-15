<template>
  <bk-sideslider
    :is-show.sync="sideShow"
    :width="slideInfo.type === 'combine' ? sliderWidth : 560"
    :show-mask="true"
    :quick-close="true"
    :before-close="handleCancel">
    <div slot="header">
      {{ slideInfo.title }}
    </div>
    <component
      :is="slideInfo.type === 'combine' ? 'CombineSlider' : 'FieldSlider'"
      slot="content"
      ref="sideComponent"
      :readonly="readonly"
      :operate="slideInfo.operate"
      :value="slideInfo.value"
      :inputs="inputs"
      :field-info="colFieldInfo" />
    <template slot="footer">
      <bk-button
        v-if="!readonly"
        class="mr10"
        theme="primary"
        @click="handleSave">
        {{ $t('保存') }}
      </bk-button>
      <bk-button
        theme="default"
        @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </template>
  </bk-sideslider>
</template>

<script>
  import CombineSlider from './components/CombineSlider/index.vue';
  import FieldSlider from './components/FieldSlider/index.vue';
  import tools from '@/utils/tools.js';
  import { mapState } from 'vuex';

  export default {
    name: 'DecisionTableSlider',
    components: {
      CombineSlider,
      FieldSlider,
    },
    props: {
      slideInfo: {
        type: Object,
        default: () => ({
          isShow: false,
          title: '',
          type: '',
          operate: '',
        }),
        required: true,
      },
      colFieldInfo: {
        type: Object,
        default: () => ({}),
      },
      readonly: {
        type: Boolean,
        default: true,
      },
      inputs: {
        type: Array,
        default: () => ([]),
      },
      sliderWidth: {
        type: Number,
        default: 1000,
      },
    },
    data() {
      return {
        sideShow: false,
      };
    },
    computed: {
      ...mapState({
        infoBasicConfig: state => state.infoBasicConfig,
      }),
    },
    watch: {
      'slideInfo.isShow': {
        handler(val) {
          // 添加延迟触发sideSlider遮罩
          this.$nextTick(() => {
            this.sideShow = val;
          });
        },
        immediate: true,
      },
    },
    methods: {
      // 保存
      async handleSave() {
        const { ruleType, getRuleValue, validate, formData } = this.$refs.sideComponent;
        const result = await validate();
        if (!result) return;

        // 条件组合侧栏
        if (this.slideInfo.type === 'combine') {
          const ruleValue = getRuleValue();
          const hasValue = ruleType === 'or_and' ? !!ruleValue.conditions.length : !!ruleValue.length;
          if (hasValue) {
            this.$emit('onConfirm', {
              type: ruleType,
              conditions: ruleValue,
            });
          } else {
            this.$emit('onConfirm');
          }
          this.$emit('onClose');
          return;
        }

        // 字段侧栏
        const { operate, from, index } = this.slideInfo;
        // 除了select 类型需要过滤掉options字段
        if (formData.type !== 'select') {
          delete formData.options;
        }
        this.$emit('updateField', { ...formData, from }, {
          from,
          operate,
          index,
        });
        this.$emit('onClose');
      },
      // 取消
      handleCancel() {
        if (this.readonly) {
          this.$emit('onClose');
          return;
        }
        let isEqual = false;
        if (this.slideInfo.type === 'combine') {
          const { getRuleValue, ruleType, conditionData, initData } = this.$refs.sideComponent;
          const ruleValue = getRuleValue();
          isEqual = tools.isDataEqual({ ...conditionData, [ruleType]: ruleValue }, initData);
        } else {
          const { formData, initFormData } = this.$refs.sideComponent;
          isEqual = tools.isDataEqual(formData, initFormData);
        }
        if (!isEqual) {
          this.$bkInfo({
            ...this.infoBasicConfig,
            confirmFn: () => {
              this.$emit('onClose');
            },
          });
        } else {
          this.$emit('onClose');
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .bk-sideslider {
    ::v-deep .bk-sideslider-footer {
      position: absolute;
      left: 0;
      bottom: 0;
      width: 100%;
      height: 64px;
      padding: 16px 24px;
      border-top: 1px solid #e6e9ee !important;
      line-height: 1;
    }
  }
</style>
