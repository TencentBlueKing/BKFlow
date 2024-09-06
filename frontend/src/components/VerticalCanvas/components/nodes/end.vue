<template>
  <div :class="['node-item circle-node', { 'ready': node.ready }]">
    {{ i18n.t('结束') }}
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  export default {
    name: 'End',
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        i18n,
      };
    },
  };
</script>
