<template>
  <bk-switcher
    :value="isOn"
    theme="primary"
    size="small"
    show-text
    @change="handleChange" />
</template>
<script>
  export default {
    name: 'BoolSwitch',
    model: { prop: 'value', event: 'change' },
    props: {
      value: {
        type: [String, Boolean],
        default: '',
      },
      schema: {
        type: Object,
        default: () => ({}),
      },
    },
    computed: {
      trueValue() {
        return this.schema.true_value || 'true';
      },
      falseValue() {
        return this.schema.false_value || 'false';
      },
      isOn() {
        return this.value === this.trueValue || this.value === true;
      },
    },
    methods: {
      handleChange(val) {
        this.$emit('change', val ? this.trueValue : this.falseValue);
      },
    },
  };
</script>
