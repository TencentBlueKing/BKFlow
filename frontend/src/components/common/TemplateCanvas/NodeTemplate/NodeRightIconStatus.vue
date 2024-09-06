<template>
  <div class="node-execute-icon">
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
    name: 'NodeRightIconStatus',
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
  };
</script>

<style lang="scss" scoped>

</style>
