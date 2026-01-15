
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
      <!-- 配置了循环的子流程 -->
      <div
        v-if="node.type === 'subflow' && (node.loop_config && node.loop_config.enable)"
        class="loop-bacth-execute-icon">
        <div class="commonicon-icon common-icon-loading-oval" />
      </div>
      <!-- 子流程循环与批量执行第一期先不做 -->
      <!-- 配置了批量执行的子流程 -->
      <!-- <div
        v-if="node.type === 'subflow'"
        class="loop-bacth-execute-icon">
        <svg
          class="batch-execute-svg"
          viewBox="0 0 1024 1024"
          version="1.1"
          xmlns="http://www.w3.org/2000/svg">
          <path
            fill="#fff"
            fill-rule="evenodd"
            d="M512 136L172.8 336 512 536 851.2 336 512 136zM512 64c3.2 0 6.4 0 8 1.6l432 254.4c11.2 6.4 11.2 24 0 30.4l-432 254.4C518.4 608 515.2 608 512 608c-3.2 0-6.4 0-8-1.6l-432-254.4c-11.2-6.4-11.2-24 0-30.4l432-254.4C505.6 64 508.8 64 512 64zM128 484.8l384 230.4 384-230.4c14.4-9.6 35.2-4.8 43.2 11.2 9.6 14.4 4.8 35.2-11.2 43.2l-400 240c-4.8 3.2-11.2 4.8-16 4.8-6.4 0-11.2-1.6-16-4.8l-400-240C80 529.6 75.2 510.4 84.8 496 94.4 480 113.6 475.2 128 484.8zM128 660.8l384 230.4 384-230.4c14.4-9.6 35.2-4.8 43.2 11.2 9.6 14.4 4.8 35.2-11.2 43.2l-400 240c-4.8 3.2-11.2 4.8-16 4.8-6.4 0-11.2-1.6-16-4.8l-400-240C80 705.6 75.2 686.4 84.8 672 94.4 656 113.6 651.2 128 660.8z"
            clip-rule="evenodd" />
        </svg>
      </div> -->
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
  .loop-bacth-execute-icon{
    height: 16px;
    width: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #738ABE;
    border-radius: 2px;
    margin-right: 2px;
    color: #fff;
    .commonicon-icon {
      font-size: 7px;
    }
    .batch-execute-svg {
      width: 13px;
      height: 13px;
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
