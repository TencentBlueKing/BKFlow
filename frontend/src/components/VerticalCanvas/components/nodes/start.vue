<template>
  <div :class="['node-item circle-node', { 'ready': node.ready }]">
    {{ i18n.t('开始') }}
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  export default {
    name: 'Start',
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
