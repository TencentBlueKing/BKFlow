
<template>
  <div class="node-config-flags">
    <template v-if="node.optional">
      <span
        v-if="node.mode === 'edit'"
        class="dark-circle common-icon-dark-circle-checkbox" />
      <bk-checkbox
        v-else-if="node.mode === 'select'"
        :value="node.checked"
        :disabled="node.checkDisable"
        @change="onNodeCheckClick" />
    </template>
    <template v-if="node.mode === 'edit'">
      <span
        v-if="node.error_ignorable"
        class="error-handle-icon"><span class="text">AS</span></span>
      <span
        v-if="node.isSkipped || node.skippable"
        class="error-handle-icon"><span class="text">MS</span></span>
      <span
        v-if="node.can_retry || node.retryable"
        class="error-handle-icon"><span class="text">MR</span></span>
      <span
        v-if="node.auto_retry && node.auto_retry.enable"
        class="error-handle-icon">
        <span class="text">AR</span>
      </span>
    </template>
    <template v-if="node.create_method === 'mock'">
      <span class="mock-label">MOCK</span>
    </template>
  </div>
</template>

<script>
  export default {
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
    methods: {
      onNodeCheckClick(val) {
        if (this.node.checkDisable) {
          return;
        }
        this.$emit('onNodeCheckClick', val);
      },
    },
  };
</script>

<style lang="scss" scoped>
  .node-config-flags {
    position: absolute;
    top: -20px;
    left: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .bk-form-checkbox,
    .dark-circle {
      margin-right: 2px;
      font-size: 14px;
      color: #979ba5;
    }
  .error-handle-icon {
    margin-right: 2px;
    padding: 0 3px;
    line-height: 12px;
    color: #ffffff;
    background: #979ba5;
    border-radius: 2px;
    .text {
      display: inline-block;
      font-size: 12px;
      transform: scale(0.8);
    }
  }
  .mock-label {
    line-height: 13px;
    font-size: 9px;
    padding: 0 2px;
    color: #fff;
    background: #738abe;
    border-radius: 1px;
  }
</style>
