<template>
  <div :class="['node-item gateway-node', { 'ready': node.ready }]">
    <div class="bpmn-flow-icon common-icon-node-parallelgateway" />
  </div>
</template>
<script>
  export default {
    name: 'ParallelGateway',
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
  };
</script>
