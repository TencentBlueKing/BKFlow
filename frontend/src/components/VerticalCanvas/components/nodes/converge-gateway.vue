<template>
  <div :class="['node-item gateway-node', { 'ready': node.ready }]">
    <div class="bpmn-flow-icon common-icon-node-convergegateway" />
  </div>
</template>
<script>
  export default {
    name: 'ConvergeGateway',
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
  };
</script>
