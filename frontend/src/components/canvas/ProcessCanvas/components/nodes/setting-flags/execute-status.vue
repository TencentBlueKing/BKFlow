<template>
  <div class="execute-status">
    <!-- 节点执行顶部右侧 icon， 执行中、重试次数、是否为跳过-->
    <div
      v-if="node.status === 'RUNNING'"
      class="task-status-icon">
      <i class="common-icon-loading" />
    </div>
    <div
      v-else-if="node.status === 'FINISHED' && (node.retry > 0 || node.skip)"
      class="task-status-icon">
      <i
        v-if="node.skip"
        class="bk-icon icon-arrows-right-shape" />
      <span
        v-else-if="node.retry > 0"
        class="retry-times">{{ node.retry > 99 ? '100+' : node.retry }}</span>
    </div>
    <!-- 节点失败后自动忽略icon -->
    <div
      v-else-if="node.status === 'FINISHED' && node.error_ignored"
      class="task-status-icon node-subscript">
      <i class="bk-icon icon-arrows-right-shape" />
    </div>
    <!-- 节点循环次数 -->
    <div
      v-if="node.loop > 1"
      :class="['task-status-icon task-node-loop', { 'loop-plural': node.loop > 9 }]">
      <i :class="`common-icon-loading-${ node.loop > 9 ? 'oval' : 'round' }`" />
      <span>{{ node.loop > 99 ? '99+' : node.loop }}</span>
    </div>
    <!-- 节点顶部右侧生命周期 icon -->
    <div
      v-if="[1, 2].includes(node.phase)"
      class="node-phase-icon">
      <i
        v-bk-tooltips="{
          content: phaseStr[node.phase],
          width: 210
        }"
        :class="['bk-icon', 'icon-exclamation-circle', {
          'phase-warn': node.phase === 1,
          'phase-error': node.phase === 2
        }]" />
    </div>
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
  };
</script>

<style lang="scss" scoped>
  @keyframes loading {
    0% {
      transform: rotate(0);
    }
    100% {
      transform: rotate(360deg);
    }
  }
  $redDark: #ea3636;
  $yellowDark: #ff9c01;
  .execute-status {
    position: absolute;
    top: -9px;
    right: -9px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    font-size: 14px;
    border-radius: 50%;
    z-index: 1;
  }
  .task-status-icon {
    display: flex;
    justify-content: center;
    align-items: center;
    margin-left: 2px;
    width: 18px;
    height: 18px;
    font-size: 14px;
    border-radius: 50%;
    background: #f8b53f;
    color: #ffffff;
    box-shadow: 0px 2px 4px 0px rgba(0, 0, 0, 0.1);
    .common-icon-double-vertical-line {
      display: inline-block;
      font-size: 12px;
      transform: scale(0.8);
    }
    .common-icon-clock {
      display: inline-block;
    }
    .common-icon-loading {
      display: inline-block;
      animation: loading 1.4s infinite linear;
    }
    .icon-arrows-right-shape {
      font-size: 12px;
    }
    .retry-times {
      font-size: 12px;
    }
    &.task-node-loop {
      position: relative;
      height: 16px;
      width: 16px;
      color: #3a84ff;
      background: #fff !important;
      > i {
        position: absolute;
        font-size: 14px;
      }
      > span {
        position: relative;
        top: -0.5px;
        font-weight: 700;
        font-size: 18px;
        transform: scale(.5);
      }
      &.loop-plural {
        width: 26px;
        height: 16px;
        border-radius: 8px;
      }
    }
  }
  .node-subscript {
    font-size: 12px;
    background: #ea3636 !important;
  }
  .node-phase-icon {
    i {
      font-size: 14px;
      &.phase-warn {
        color: $yellowDark;
      }
      &.phase-error {
        color: $redDark;
      }
    }
  }
  .common-icon-loading {
    color: #ffffff;
    animation: loading 1.4s infinite linear;
  }
</style>
