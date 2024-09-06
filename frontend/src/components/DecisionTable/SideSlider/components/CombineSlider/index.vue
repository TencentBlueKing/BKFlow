<template>
  <div class="combine-slider">
    <div class="condition-head">
      <span class="title">{{ $t('规则设置方式') }}</span>
      <bk-radio-group v-model="ruleType">
        <bk-radio
          value="or_and"
          :disabled="readonly">
          {{ $t('表单设置') }}
        </bk-radio>
        <bk-radio
          value="expression"
          :disabled="readonly">
          {{ $t('表达式') }}
        </bk-radio>
      </bk-radio-group>
    </div>
    <!--表达式-->
    <FullCodeEditor
      v-show="ruleType === 'expression'"
      ref="fullCodeEditor"
      :value="conditionData.expression"
      :options="{ readOnly: readonly, language: 'json' }"
      @input="onDataChange" />
    <p
      v-show="ruleType === 'expression'"
      class="condition-tips mt10">
      {{ $t('请填入需要的 FEEL 表达式，支持的语法可参考') }}
      <bk-link
        theme="primary"
        href="https://github.com/TencentBlueKing/bkflow-feel/blob/main/docs/grammer.md"
        target="_blank">
        {{ $t('文档') }}
      </bk-link>
      {{ '。' }}
    </p>
    <!--表单设置-->
    <RuleSelector
      v-show="ruleType === 'or_and'"
      ref="ruleSelector"
      :readonly="readonly"
      :inputs="inputs"
      :value="conditionData.or_and"
      @update="onDataChange" />
  </div>
</template>

<script>
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import RuleSelector from './components/RuleSelector.vue';
  import tools from '@/utils/tools.js';
  export default {
    name: 'CombineSlider',
    components: {
      FullCodeEditor,
      RuleSelector,
    },
    props: {
      readonly: {
        type: Boolean,
        default: true,
      },
      inputs: {
        type: Array,
        default: () => ([]),
      },
      value: {
        type: Object,
        default: () => ({
          type: '',
          conditions: {},
        }),
      },
    },
    data() {
      const { type, conditions } = this.value;
      let ruleType = 'or_and';
      const conditionData = {
        expression: '',
        or_and: {},
      };
      if (type) {
        ruleType = type;
        conditionData[type] = tools.deepClone(conditions);
      }
      const initData = tools.deepClone(conditionData);

      return {
        ruleType,
        conditionData,
        initData,
      };
    },
    watch: {
      ruleType(val) {
        if (val !== 'expression') return;

        this.$nextTick(() => {
          const editorInstance = this.$refs.fullCodeEditor;
          if (editorInstance) {
            editorInstance.layoutCodeEditorInstance();
          }
        });
      },
    },
    methods: {
      onDataChange(val, type = 'expression') {
        this.conditionData[type] = val;
      },
      getRuleValue() {
        // 如果没有值则取消条件组合
        const ruleValue = tools.deepClone(this.conditionData[this.ruleType]);
        if (this.ruleType === 'or_and') {
          ruleValue.conditions = ruleValue.conditions.reduce((acc, cur) => {
            cur.conditions = cur.conditions.reduce((acc1, cur1) => {
              if (cur1.left.obj.key) {
                delete cur1.randomKey;
                acc1.push(cur1);
              }
              return acc1;
            }, []);
            if (cur.conditions.length) {
              delete cur.randomKey;
              acc.push(cur);
            }
            return acc;
          }, []);
          delete ruleValue.randomKey;
        }
        return ruleValue;
      },
      validate() {
        const { ruleSelector } = this.$refs;
        return this.ruleType === 'or_and' ? ruleSelector?.validate() : true;
      },
    },
  };
</script>

<style lang="scss" scoped>
.combine-slider {
  padding: 24px;
  font-size: 14px;
  .condition-head {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
    .title {
      flex-shrink: 0;
      color: #1e252e;
      margin-right: 16px;
      line-height: 22px;
    }
    /deep/.bk-form-radio {
      margin-right: 24px;
    }
  }
  .condition-tips {
    margin-bottom: 10px;
    font-size: 12px;
    color: #b8b8b8;
    /deep/.bk-link {
      vertical-align: initial;
      .bk-link-text {
        font-size: 12px;
      }
    }
  }
  /deep/.full-code-editor {
    height: 460px;
  }
}
</style>
