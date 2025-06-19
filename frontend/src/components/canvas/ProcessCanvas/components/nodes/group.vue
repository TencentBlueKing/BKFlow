<template>
  <div class="custom-group-node">
    分组节点(按住ctrl或cmd键可移出父节点)
  </div>
</template>
<script>
  export default {
    name: 'Group',
  };
</script>
<style lang="scss" scoped>
  .custom-group-node {
    width: 100%;
    height: 100%;
    font-size: 12px;
    border: 1px solid #546a9e;
    border-radius: 2px;
    background: #ffffff;
  }
</style>
