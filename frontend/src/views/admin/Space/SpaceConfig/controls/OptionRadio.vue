<template>
  <bk-radio-group
    class="option-radio"
    :value="value"
    @change="val => $emit('change', val)">
    <bk-radio
      v-for="opt in options"
      :key="opt.value"
      :value="opt.value"
      class="option-item">
      <span class="option-label">{{ opt.label }}{{ opt.desc ? ':' : '' }}</span>
      <span
        v-if="opt.desc"
        class="option-desc">{{ opt.desc }}</span>
    </bk-radio>
  </bk-radio-group>
</template>

<script>
  export default {
    name: 'OptionRadio',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: [String, Number, Boolean],
        default: '',
      },
      schema: {
        type: Object,
        default: () => ({}),
      },
    },
    computed: {
      options() {
        return this.schema.options || [];
      },
    },
  };
</script>

<style lang="scss" scoped>
  .option-radio {
    display: flex;
    flex-wrap: wrap
  }
  .option-item {
    display: flex;
    align-items: center;
    margin-right: 24px;
    margin-bottom: 8px;
    ::v-deep .bk-radio-text {
      color: #979ba5;
      font-size: 12px;
    }
  }
</style>
