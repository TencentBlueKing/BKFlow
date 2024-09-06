<template>
  <div class="value-selector">
    <bk-select
      v-if="column.type === 'select'"
      v-model="setValue"
      clearable
      searchable
      :popover-options="{
        zIndex: 2501
      }"
      :placeholder="placeholder"
      ext-popover-cls="compare-select-popover"
      :multiple="isMultiple"
      :disabled="isDisabled">
      <bk-option
        v-for="option in column.options.items"
        :id="option.id"
        :key="option.id"
        :name="option.name">
        <bk-checkbox
          v-if="isMultiple"
          :value="setValue && setValue.includes(option.id)"
          class="mr5" />
        <span
          v-bk-overflow-tips
          class="name ellipsis">{{ option.name }}</span>
        <span
          v-bk-overflow-tips
          class="key ellipsis ml10">({{ option.id }})</span>
      </bk-option>
    </bk-select>
    <bk-input
      v-else-if="compare !== 'in-range'"
      v-model="setValue"
      clearable
      :type="column.type === 'int' ? 'number' : 'text'"
      :disabled="isDisabled"
      :placeholder="placeholder"
      show-clear-only-hover
      @blur="handleNumberInputBlur($event)" />
    <div
      v-else
      class="int-range">
      <bk-input
        v-model="setValue.start"
        clearable
        type="number"
        :disabled="readonly"
        :placeholder="placeholder"
        show-clear-only-hover
        @blur="handleNumberInputBlur($event, 'start')" />
      <span class="divide">{{ '~' }}</span>
      <bk-input
        v-model="setValue.end"
        clearable
        type="number"
        :disabled="readonly"
        :placeholder="placeholder"
        show-clear-only-hover
        @blur="handleNumberInputBlur($event, 'end')" />
    </div>
  </div>
</template>
<script>
  export default {
    name: 'ValueSelector',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: [String, Object, Number, Array],
        default: null,
      },
      column: {
        type: Object,
        default: () => ({}),
      },
      compare: {
        type: String,
        default: '',
      },
      readonly: {
        type: Boolean,
        default: false,
      },
      placeholder: {
        type: String,
        default: '',
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
      isMultiple() {
        return ['in-range', 'not-in-range'].includes(this.compare);
      },
      isDisabled() {
        return this.readonly || ['is-null', 'not-null'].includes(this.compare);
      },
    },
    methods: {
      handleNumberInputBlur(val, type) {
        if (this.column.type !== 'int') return;
        if (type) {
          // 失焦的时候如果值为空则设置默认值0
          if (!val && val !== 0) {
            this.value[type] = type === 'start' ? 0 : 1;
          } else {
            this.value[type] = Number(val);
          }
        } else {
          this.$emit('change', Number(val));
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .int-range {
    display: flex;
    align-items: center;
    .divide {
      margin: 0 8px;
    }
  }
</style>
<style lang="scss">
  .compare-select-popover {
    .bk-option {
      &:hover {
        color: #63656e;
        background: #f4f5f8 !important;
      }
      &.is-selected {
        color: #3a84ff;
        background: #fff;
      }
    }
    .bk-option-content {
      display: flex;
      align-items: center;
      .name {
        max-width: 50%;
      }
      .key {
        max-width: 40%;
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
