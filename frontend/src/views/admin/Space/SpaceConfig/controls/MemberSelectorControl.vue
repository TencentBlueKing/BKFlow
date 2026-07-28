<template>
  <MemberSelect
    :value="normalizedValue"
    :placeholder="schema.placeholder || ''"
    @change="$emit('change', $event)" />
</template>
<script>
  import MemberSelect from '@/components/common/Individualization/MemberSelect.vue';
  export default {
    name: 'MemberSelectorControl',
    components: {
      MemberSelect,
    },
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: Array,
        default: () => [],
      },
      schema: {
        type: Object,
        default: () => ({}) },
      },
    computed: {
      normalizedValue() {
        return Array.isArray(this.value) ? this.value : [];
      },
    },
  };
</script>
