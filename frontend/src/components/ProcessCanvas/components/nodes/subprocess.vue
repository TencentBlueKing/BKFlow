<template>
  <div
    class="node-item subprocess-node"
    :class="[
      { 'fail-skip': node.status === 'FINISHED' && node.skip },
      { 'ready': node.ready },
      { 'active': node.isActived },
      { 'unchecked ': node.mode === 'select' && node.optional && !node.checked }
    ]">
    <div class="node-status-block">
      <i class="bpmn-flow-icon icon-subflow-mark" />
    </div>
    <div class="node-name">
      <div class="name-text" />
      <div class="subprocess-mark" />
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
</style>
