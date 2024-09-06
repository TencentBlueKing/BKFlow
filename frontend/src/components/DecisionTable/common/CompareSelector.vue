<template>
  <bk-select
    v-model="setValue"
    :clearable="false"
    class="compare-selector"
    :disabled="readonly"
    placeholder="条件"
    :popover-options="{
      zIndex: 2501
    }"
    @change="handleCompareChange">
    <bk-option
      v-for="option in conditionList"
      :id="option.key"
      :key="option.key"
      :name="option.name" />
  </bk-select>
</template>
<script>
  export default {
    name: 'CompareSelector',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: String,
        default: '',
      },
      readonly: {
        type: Boolean,
        default: false,
      },
      conditionList: {
        type: Array,
        default: () => ([]),
      },
      column: {
        type: Object,
        default: () => ({}),
      },
      cellData: {
        type: Object,
        default: () => ({}),
      },
    },
    computed: {
      setValue: {
        get() {
          return this.value;
        },
        set(val) {
          this.$emit('change', val);
        },
      },
    },
    methods: {
      handleCompareChange(val) {
        let { type } = this.column;
        let { value } = this.cellData.right.obj;
        const isInRange = ['in-range', 'not-in-range'].includes(val);
        // 空/非空
        if (['is-null', 'not-null'].includes(this.cellData.compare)) {
          this.cellData.right.obj = { value: '' };
          this.$validator.remove(`value_${this.cellData.randomKey}`);
        } else if (type === 'int' || type === 'select') {
          // 数字/下拉框切换比较条件时重置数据类型、值
          if (type === 'int') {
            value = typeof value === 'object' ? null : value;
            value = isInRange ? { start: 0, end: 1 } : value;
          } else {
            // eslint-disable-next-line
            value = isInRange ? (typeof value === 'string' ? '' : value) : (typeof value === 'string' ? value : '')
          }
          type += isInRange ? '[Range]' : '';

          this.cellData.right.obj = { type, value };
        }
      },
    },
  };
</script>
