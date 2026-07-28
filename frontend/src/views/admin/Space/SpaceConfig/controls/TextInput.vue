<template>
  <div
    class="text-input">
    <div
      v-if="isDuration"
      class="duration-input">
      <bk-input
        :value="durationNum"
        type="number"
        :min="1"
        :placeholder="schema.placeholder || ''"
        class="duration-number"
        @change="onNumberChange" />
      <bk-select
        :value="durationUnit"
        class="duration-unit"
        :clearable="false"
        @change="onUnitChange">
        <bk-option
          id="h"
          :name="$tc('小时', 0)" />
        <bk-option
          id="d"
          :name="$tc('天', 0)" />
      </bk-select>
    </div>
    <bk-input
      v-else
      :value="value"
      :placeholder="schema.placeholder || ''"
      @change="$emit('change', $event)" />
    <div class="ui-help-text">
      {{ schema.help }}
    </div>
  </div>
</template>
<script>
  export default {
    name: 'TextInput',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: [String, Number],
        default: '',
      },
      name: {
        type: String,
        default: '',
      },
      schema: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        durationNum: 1,
        durationUnit: 'h',
      };
    },
    computed: {
      isDuration() {
        return this.schema?.validation?.type === 'duration';
      },
    },
    watch: {
      value: {
        handler(val) {
          if (this.isDuration) {
            this.parseDuration(val);
          }
        },
        immediate: true,
      },
    },
    methods: {
      parseDuration(val) {
        if (val === '' || val === null || val === undefined) {
          this.durationNum = 1;
          this.durationUnit = 'h';
          return;
        }
        const match = String(val).trim()
          .match(/^(\d+)([mhd])$/i);
        if (match) {
          this.durationNum = parseInt(match[1], 10);
          this.durationUnit = match[2].toLowerCase();
        } else {
          const num = parseInt(val, 10);
          this.durationNum = Number.isNaN(num) ? 1 : num;
          this.durationUnit = 'h';
        }
      },
      emitDuration() {
        this.$emit('change', `${this.durationNum}${this.durationUnit}`);
      },
      onNumberChange(val) {
        const num = parseInt(val, 10);
        this.durationNum = Number.isNaN(num) || num < 1 ? 1 : num;
        this.emitDuration();
      },
      onUnitChange(unit) {
        this.durationUnit = unit || 'h';
        this.emitDuration();
      },
    },
  };
</script>
<style lang="scss" scoped>
.text-input {
  width: 100%;
  .duration-input {
    display: flex;
    align-items: center;
    width: 311px;
    .duration-number {
      flex: 1;
    }
    .duration-unit {
      width: 60px;
      ::v-deep .bk-select-name {
        padding: 0 10px 0 10px;
      }
    }
  }
  .ui-help-text {
    color: #979ba5;
    font-size: 12px;
    line-height: 20px;
  }
}
</style>
