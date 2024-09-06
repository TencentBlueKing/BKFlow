<template>
  <div class="rule-selector-wrapper">
    <!--且/或-->
    <div
      v-if="ruleInfo.conditions.length > 1"
      :class="[
        'rule-type',
        ruleInfo.operator === 'and' ? 'rule-and' : 'rule-or',
        { 'is-disabled': readonly }
      ]"
      @click="handleRuleTypeToggle(ruleInfo)">
      {{ ruleInfo.operator === 'and' ? $t('且') : $t('或') }}
      <i class="bk-icon icon-qiehuan" />
    </div>
    <!--条件列表-->
    <ul class="rule-wrap">
      <li
        v-for="(rule, index) in ruleInfo.conditions"
        :key="index"
        :style="{ paddingLeft: rule.conditions.length > 1 || ruleInfo.conditions.length > 1 ? '62px' : '16px' }"
        :class="['rule-li', { 'multiple-li': ruleInfo.conditions.length > 1 }]">
        <!--子条件--且/或-->
        <div
          v-if="rule.conditions.length > 1"
          :class="[
            'rule-type',
            rule.operator === 'and' ? 'rule-and' : 'rule-or',
            { 'is-disabled': readonly }
          ]"
          @click="handleRuleTypeToggle(rule)">
          {{ rule.operator === 'and' ? $t('且') : $t('或') }}
          <i class="bk-icon icon-qiehuan" />
        </div>
        <!--子条件列表-->
        <div
          v-for="(item, i) in rule.conditions"
          :key="i"
          :class="['rule-item', { 'multiple-item': rule.conditions.length > 1 }]">
          <!--字段-->
          <bk-select
            v-model="item.left.obj.key"
            v-validate="{ required: judgeRequired(item, 'left') }"
            :class="['field-select', { 'vee-error': veeErrors.has(`field_${item.randomKey}`) }]"
            :disabled="readonly"
            :placeholder="$t('字段')"
            :clearable="false"
            :name="`field_${item.randomKey}`"
            @change="handleFieldChange($event, item)">
            <bk-option
              v-for="option in fieldList"
              :id="option.id"
              :key="option.id"
              :name="option.name" />
          </bk-select>
          <!--字段校验-->
          <span
            v-if="veeErrors.has(`field_${item.randomKey}`)"
            v-bk-tooltips="veeErrors.first(`field_${item.randomKey}`)"
            class="bk-icon icon-exclamation-circle-shape error-msg" />
          <!--条件-->
          <compare-selector
            :key="`${item.left.obj.key}-compare`"
            v-model="item.compare"
            v-validate="{ required: judgeRequired(item, 'compare') }"
            :class="['condition-select', { 'vee-error': veeErrors.has(`compare_${item.randomKey}`) }]"
            :name="`compare_${item.randomKey}`"
            :cell-data="item"
            :column="getColumn(item.left.obj.key)"
            :condition-list="getCompareList(item.left.obj.key)"
            :readonly="readonly" />
          <!--条件校验-->
          <span
            v-if="veeErrors.has(`compare_${item.randomKey}`)"
            v-bk-tooltips="veeErrors.first(`compare_${item.randomKey}`)"
            class="bk-icon icon-exclamation-circle-shape error-msg" />
          <!--值-->
          <value-selector
            :key="`${item.left.obj.key}-${item.compare}-value`"
            v-model="item.right.obj.value"
            v-validate="{ required: judgeRequired(item, 'right') }"
            :class="[
              'value-input',
              {
                'value-null': ['is-null', 'not-null'].includes(item.compare),
                'vee-error': veeErrors.has(`value_${item.randomKey}`)
              }
            ]"
            :name="`value_${item.randomKey}`"
            :compare="item.compare"
            :column="getColumn(item.left.obj.key)"
            :readonly="readonly" />
          <!--值校验-->
          <span
            v-if="veeErrors.has(`value_${item.randomKey}`)"
            v-bk-tooltips="veeErrors.first(`value_${item.randomKey}`)"
            class="bk-icon icon-exclamation-circle-shape error-msg" />
          <!--新增、删除-->
          <div
            v-if="!readonly"
            class="operate-wrap">
            <i
              class="bk-icon icon-plus-circle"
              @click="handleAdd(index, i)" />
            <i
              v-if="rule.conditions.length > 1"
              class="bk-icon icon-minus-circle"
              @click="handleClose(index, i)" />
          </div>
        </div>
        <!--删除-->
        <i
          v-if="!readonly && ruleInfo.conditions.length > 1"
          class="bk-icon icon-close-circle-shape delete-group"
          @click="handleDeleteGroup(index)" />
      </li>
    </ul>
    <!--新增条件组-->
    <div
      v-if="!readonly"
      class="add-group"
      :style="{ marginLeft: ruleInfo.conditions.length > 1 ? '40px' : '0' }"
      @click="handleAddGroup">
      <i class="bk-icon icon-plus-circle" />
      {{ $t('新增条件组') }}
    </div>
  </div>
</template>

<script>
  import { getConditionList } from '../../../../common/field.js';
  import { random4 } from '@/utils/uuid.js';
  import tools from '@/utils/tools.js';
  import ValueSelector from '../../../../common/ValueSelector.vue';
  import CompareSelector from '../../../../common/CompareSelector.vue';
  export default {
    name: 'RuleSelectorWrapper',
    components: {
      ValueSelector,
      CompareSelector,
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
        default: () => ({}),
      },
    },
    data() {
      const fieldTypeMap = this.inputs.reduce((acc, cur) => {
        acc[cur.id] = cur.type;
        return acc;
      }, {});
      return {
        ruleInfo: {},
        fieldList: this.inputs,
        fieldTypeMap,
        optionList: [],
      };
    },
    watch: {
      ruleInfo: {
        handler(val) {
          this.$emit('update', val, 'or_and');
        },
        deep: true,
      },
    },
    created() {
      this.initRuleInfo();
    },
    methods: {
      // 初始化规则配置
      initRuleInfo() {
        let ruleInfo = {};
        if (Object.keys(this.value).length) {
          ruleInfo = tools.deepClone(this.value);
          ruleInfo.conditions.forEach((i) => {
            i.conditions.forEach((j) => {
              j.randomKey = random4();
            });
            i.randomKey = random4(); // 当前规则行的唯一标识, 校验时用
          });
        } else {
          ruleInfo = {
            operator: 'and',
            conditions: [{
              operator: 'and',
              conditions: [{
                compare: '',
                left: { type: 'field',  obj: {} },
                right: { type: 'value', obj: {} },
                randomKey: random4(),
              }],
            }],
            randomKey: random4(),
          };
        }
        this.ruleInfo = ruleInfo;
      },
      // 条件列表
      getCompareList(val) {
        if (!val) return [];
        const type = this.fieldTypeMap[val];
        return getConditionList(type);
      },
      // 选项列表
      getColumn(val) {
        return this.fieldList.find(item => item.id === val);
      },
      // 新增条件组
      handleAddGroup() {
        this.ruleInfo.conditions.push({
          operator: 'and',
          conditions: [{
            compare: '',
            left: { type: 'field',  obj: {} },
            right: { type: 'value', obj: {} },
            randomKey: random4(),
          }],
          randomKey: random4(),
        });
      },
      // 切换规则类型且/或
      handleRuleTypeToggle(ruleInfo) {
        if (this.readonly) return;
        ruleInfo.operator = ruleInfo.operator === 'and' ? 'or' : 'and';
      },
      // 删除条件组
      handleDeleteGroup(index) {
        this.ruleInfo.conditions.splice(index, 1);
      },
      // 新增子条件
      handleAdd(index, i) {
        this.ruleInfo.conditions[index].conditions.splice(i + 1, 0, {
          compare: '',
          left: { type: 'field',  obj: {} },
          right: { type: 'value', obj: {} },
          randomKey: random4(),
        });
      },
      // 删除子条件
      handleClose(index, i) {
        this.ruleInfo.conditions[index].conditions.splice(i, 1);
      },
      // 切换字段
      handleFieldChange(val, rule) {
        if (!val) return;
        rule.left.obj = {
          key: val,
          type: 'string',
        };
        // 清空条件和值
        rule.compare = '';
        const fieldInfo = this.fieldList.find(item => item.id === val);
        rule.right.obj.type = fieldInfo.type;
        rule.right.obj.value = '';
      },
      // 判断是否必填
      judgeRequired(item, type) {
        let isRequired = true;
        const { left, compare, right } = item;
        if (['is-null', 'not-null'].includes(compare)) {
          return false;
        }
        const leftValue = left.obj.key;
        const rightValue = right.obj.value;
        if ([leftValue, rightValue, compare].every(item => [undefined, ''].includes(item))) {
          isRequired = false;
        } else {
          isRequired = type === 'compare' ? compare : rightValue;
          isRequired = type === 'left' ? leftValue : isRequired;
          isRequired = !isRequired;
        }
        return isRequired;
      },
      // 校验
      validate() {
        return this.$validator.validateAll().then(valid => valid);
      },
    },
  };
</script>

<style lang="scss" scoped>
  .rule-selector-wrapper {
    position: relative;
    .rule-wrap {
      position: relative;
    }
    .rule-type {
      position: absolute;
      top: 50%;
      transform: translate(-25%, calc(-50% - 20px));
      z-index: 10;
      height: 24px;
      display: flex;
      align-items: center;
      padding: 0 4px;
      font-size: 12px;
      color: #fff;
      border-radius: 4px;
      cursor: pointer;
      i {
        margin-left: 3px;
      }
      &.rule-and {
        background: #3a84ff;
        &:hover {
          background: #699df4;
        }
      }
      &.rule-or {
        background: #2dcb56;
        &:hover {
          background: #45e35f;
        }
      }
      &.is-disabled {
        transform: translate(-25%, -50%);
        cursor: not-allowed;
      }
    }
    .rule-li {
      position: relative;
      margin-bottom: 16px;
      padding: 16px;
      border-radius: 4px;
      background: #f6f8f9;
      .rule-type {
        transform: translate(calc(-100% - 10px), -50%);
        &::after {
          content: '';
          display: inline-block;
          position: absolute;
          top: 50%;
          right: -10px;
          height: 1px;
          width: 10px;
          background: #f6f8f9;
        }
      }
      .delete-group {
        position: absolute;
        top: -10px;
        right: -10px;
        display: none;
        font-size: 20px;
        color: #979ba5;
        &:hover {
          color: #3a84ff;
          cursor: pointer;
        }
      }
      &:hover {
        .delete-group {
          display: block;
        }
      }
    }
    .multiple-li {
      margin-left: 40px;
      padding-left: 62px;
      &::before {
        content: '';
        display: inline-block;
        position: absolute;
        height: calc(100% + 16px);
        border-left: 1px dashed #b2bdcc;
        left: -30px;
        top: 0;
      }
      &:first-child::before {
        height: calc(50% + 16px);
        top: 50%;
      }
      &:last-child::before {
        height: 50%;
      }
      &:first-child,
      &:last-child {
        &::after {
          content: '';
          display: inline-block;
          position: absolute;
          width: calc(62px + 30px);
          border-top: 1px dashed #b2bdcc;
          left: -30px;
          top: 50%;
        }
      }
    }
    .rule-item {
      display: flex;
      align-items: center;
      .condition-select {
        flex-shrink: 0;
        width: 160px;
        margin-right: 8px;
        background: #fff;
      }
      .field-select {
        flex: 1;
        min-width: 322px;
        margin-right: 8px;
        background: #fff;
      }
      .value-input {
        flex: 1;
        margin-right: 12px;
        background: #fff;
        /deep/.int-range {
          background: #f6f8f9;
        }
        &.value-null {
          opacity: 0;
        }
      }
      .operate-wrap {
        width: 45px;
        display: flex;
        align-items: center;
        font-size: 16px;
        color: #979ba5;
        cursor: pointer;
        i:hover {
          cursor: pointer;
          color: #3a84ff;
        }
        .icon-plus-circle {
          margin-right: 12px;
        }
      }
      .vee-error {
        border-color: #ea3636;
        /deep/.bk-select,
        /deep/.bk-form-input {
          border-color: #ea3636;
        }
      }
      .error-msg {
        margin-left: -14px;
        transform: translateX(-16px);
        color: #ea3636;
      }
    }
    .multiple-item {
      position: relative;
      &::before {
        content: '';
        display: inline-block;
        position: absolute;
        height: calc(100% + 16px);
        border-left: 1px dashed #b2bdcc;
        left: -26px;
        top: 0;
      }
      &:nth-child(2)::before {
        height: calc(50% + 16px);
        top: 50%;
      }
      &:last-of-type::before {
        height: 50%;
      }
      &:nth-child(2),
      &:last-of-type {
        &::after {
          content: '';
          display: inline-block;
          position: absolute;
          width: 26px;
          border-top: 1px dashed #b2bdcc;
          left: -26px;
          top: 50%;
        }
      }
      &:not(:nth-child(2)) {
        margin-top: 16px;
      }
    }
    .add-group {
      display: inline-flex;
      align-items: center;
      color: #3a84ff;
      cursor: pointer;
      i {
        margin-right: 5px;
        transform: translateY(1px);
      }
    }
  }
</style>
