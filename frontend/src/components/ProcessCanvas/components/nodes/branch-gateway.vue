<template>
  <div
    :class="[
      'node-item gateway-node',
      { 'fail-skip': node.status === 'FINISHED' && node.skip },
      { 'ready': node.ready }
    ]">
    <div class="bpmn-flow-icon common-icon-node-branchgateway" />
  </div>
</template>
<script>
  export default {
    name: 'BranchGateway',
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
  };
</script>
