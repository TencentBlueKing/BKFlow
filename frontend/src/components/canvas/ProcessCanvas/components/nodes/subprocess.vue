<template>
  <div
    class="node-item subprocess-node"
    :class="[
      node.mode === 'execute' ? 'default' : '',
      { 'fail-skip': node.status === 'FINISHED' && node.skip },
      { 'ready': node.ready },
      { 'active': node.isActived },
      { 'unchecked ': node.mode === 'select' && node.optional && !node.checked }
    ]">
    <div class="node-status-block">
      <img
        v-if="node.icon"
        class="node-icon"
        :src="node.icon">
      <i
        v-else
        :class="['node-icon-font', getIconCls(node)]" />
      <div
        v-if="node.stage_name"
        class="stage-name">
        {{ node.stage_name }}
      </div>
    </div>
    <div class="node-name">
      <div class="name-text">
        {{ node.name }}
      </div>
    </div>
    <!-- 子流程是否需要更新的节点提示 -->
    <div
      v-if="node.hasUpdated"
      class="updated-dot">
      <div class="ripple" />
    </div>
  </div>
</template>
<script>
  export default {
    name: 'SubProcess',
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
    computed: {
      isOpenTooltip() {
        if (this.node.mode === 'execute') {
          if (this.node.status === 'RUNNING') {
            return ['sleep_timer', 'pause_node'].indexOf(this.node.code) > -1;
          }
          return this.node.status === 'FAILED';
        }
        return false;
      },
      isShowSkipBtn() {
        if (this.node.status === 'FAILED' && (this.node.skippable || this.node.errorIgnorable)) {
          return true;
        }
        return false;
      },
      isShowRetryBtn() {
        if (this.node.status === 'FAILED' && (this.node.retryable || this.node.errorIgnorable)) {
          return true;
        }
        return false;
      },
      isSubProcessNode() {
        return this.node.code === 'subprocess_plugin';
      },
    },
    methods: {
      onSubflowPauseResumeClick(value) {
        this.$emit('onSubflowPauseResumeClick', this.node.id, value);
      },
      onNodeCheckClick() {
        if (this.node.checkDisable) {
          return;
        }
        this.$emit('onNodeCheckClick', this.node.id, !this.node.checked);
      },
      getIconCls(node) {
        const { code, type } = node;
         if (code === 'subprocess_plugin' || type === 'subflow') {
          return 'common-icon-subflow-mark';
        }
        return 'common-icon-sys-default';
      },
    },
  };
</script>
<style lang="scss" scoped>
.subprocess-node {
  position: relative;
  width: 154px;
  height: 54px;
  text-align: center;
  background: #ffffff;
  border-radius: 4px;
  .node-status-block {
    display: flex;
    align-items: center;
    padding: 0 8px;
    height: 20px;
    background: #738abe;
    text-align: left;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    & > i {
      color: #ffffff;
    }
  }
  .node-name {
    display: flex;
    align-items: center;
    padding: 0 8px;
    height: calc(100% - 20px);
    line-height: 14px;
    border: 1px solid #ffffff;
    border-top: none;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 4px;
    border-color: #b4becd;
  }
  .subprocess-mark::before {
    content: '';
    position: absolute;
    bottom: 1px;
    right: 0px;
    background: linear-gradient(to left top, #a2a5ad, #9fa3aa 40%, #82848a 50%, #fff 60%, #fff) 100% 0 no-repeat;
    width: 11px;
    height: 11px;
    border-top: 1px solid #e5e5e5;
    border-left: 1px solid #e5e5e5;
    border-bottom-right-radius: 4px;
    box-shadow: -1px -1px 2px -2px rgba(0,0,0,0.5);
  }
}
.updated-dot {
    position: absolute;
    top: -4px;
    right: -4px;
    width: 8px;
    height: 8px;
    background: #ff5757;
    border-radius: 50%;
    z-index: 1;
    &.show-animation .ripple {
        position: absolute;
        top: 50%;
        left: 50%;
        height: 100%;
        width: 100%;
        background: transparent;
        border: 1px solid #ff5757;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        animation: ripple .8s ease-out 5;
    }
}
@keyframes ripple {
    100% {
        width: 200%;
        height: 200%;
    }
}
</style>
