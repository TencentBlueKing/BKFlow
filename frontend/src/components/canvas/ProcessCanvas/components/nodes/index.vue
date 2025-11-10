<template>
  <bk-popover
    theme="light"
    placement="bottom-end"
    ext-cls="custom-node-popover"
    :disabled="node.mode !== 'execute' || node.task_state === 'REVOKED' || node.isSubflowCanvas"
    :distance="5"
    :arrow="false">
    <div class="custom-node">
      <Configs
        v-if="['task', 'tasknode', 'subflow'].includes(node.type)"
        :node="node"
        @onNodeCheckClick="onNodeCheckClick" />
      <ExecuteStatus
        v-if="!['start', 'end'].includes(node.type)"
        :node="node" />
      <component
        :is="comp"
        :node="node"
        :class="node.status ? node.status.toLowerCase() : ''" />
    </div>
    <template slot="content">
      <Actions
        :node="node"
        @onRetryClick="$emit('onRetryClick', node.id)"
        @onSkipClick="$emit('onSkipClick', node.id)"
        @onTaskNodeResumeClick="$emit('onTaskNodeResumeClick', node.id)"
        @onApprovalClick="$emit('onApprovalClick', node.id)"
        @onForceFail="$emit('onForceFail', node.id)"
        @onSubprocessPauseResumeClick="onSubprocessPauseResumeClick"
        @onGatewaySelectionClick="$emit('onGatewaySelectionClick', node.id)" />
    </template>
  </bk-popover>
</template>
<script>
  import Start from './start.vue';
  import End from './end.vue';
  import Task from './task.vue';
  import Subprocess from './subprocess.vue';
  import BranchGateway from './branch-gateway.vue';
  import ParallelGateway from './parallel-gateway.vue';
  import ConditionalParallelGateway from './conditional-parallel-gateway.vue';
  import ConvergeGateway from './converge-gateway.vue';
  import Configs from './setting-flags/configs.vue';
  import ExecuteStatus from './setting-flags/execute-status.vue';
  import Actions from './setting-flags/actions.vue';

  const NODE_COMP_MAP = {
    start: Start,
    end: End,
    task: Task,
    tasknode: Task,
    subflow: Subprocess,
    'branch-gateway': BranchGateway,
    'parallel-gateway': ParallelGateway,
    'conditional-parallel-gateway': ConditionalParallelGateway,
    'converge-gateway': ConvergeGateway,
  };

  export default {
    name: 'ProcessNode',
    components: {
      Configs,
      ExecuteStatus,
      Actions,
    },
    inject: ['getNode'],
    data() {
      return {
        node: {},
      };
    },
    computed: {
      comp() {
        const node = this.getNode();
        const { type, code } = node.getData();
        // 独立任务下子流程节点的判断
        if (code === 'subprocess_plugin' || type === 'SubProcess') {
          return NODE_COMP_MAP.subflow;
        }
        return NODE_COMP_MAP[type];
      },
    },
    mounted() {
      const node = this.getNode();
      this.node = node.getData();
      // 监听数据改变事件
      node.on('change:data', ({ current }) => {
        this.node = current;
      });
    },
    methods: {
      onNodeCheckClick(checked) {
        this.$emit('onNodeCheckClick', this.node.id, checked);
      },
      onSubprocessPauseResumeClick(type) {
        this.$emit('onSubprocessPauseResumeClick', this.node.id, type);
      },
    },
  };
</script>
<style lang="scss" scoped>

  $grayDark: #b4becd;
  $blueDark: #699df4;
  $defaultColor: #738abe;
  $redDark: #ea3636;
  $yellowDark: #ff9c01;
  $greenDark: #9adc9e;
  $brightRedDark: #f0a0a0;
  $whiteColor: #ffffff;
  $defaultShadow: rgba(0, 0, 0, 0.15);
  $activeShadow: rgba(0, 0, 0, 0.3);
  $redShadow: rgba(255, 87, 87, 0.15);
  $yellowShadow: rgba(248, 181, 63, 0.15);
  $greenShadow: rgba(48, 216, 120, 0.15);
  $blueShadow: rgba(58, 132, 255, 0.15);

  @mixin taskNodeStyle ($color) {
    &:hover {
      .node-name {
        border-color: $color;
      }
    }
    .node-status-block {
      background-color: $color;
    }
    .task-status-icon {
      background: $color;
    }
  }
  @mixin nodeClick ($color) {
    .node-name {
      border-color: $color;
      background-color: rgba($color, 0.3);
    }
  }
  @mixin gatewayStyle ($color) {
    .bpmn-flow-icon {
      color: $color;
    }
  }
  @mixin circleStatusStyle ($color) {
    background-color: $color;
    box-shadow: 0 0 0 2px $color;
    .circle-node-text {
      color: $whiteColor;
    }
  }
  @keyframes shake {
    25% {
      transform: rotate(-2deg);
    }
    50% {
      transform: rotate(0);
    }
    75% {
      transform: rotate(2deg);
    }
    100% {
      transform: rotate(0);
    }
  }

  .custom-node {
    width: 100%;
    height: 100%;
    cursor: pointer;
    &.node-shake {
      animation: shake .2s ease-in-out 2;
    }
  }
  :deep(.task-node),
  :deep(.subprocess-node) {
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
      border-color: $grayDark;
      .name-text {
        display: -webkit-box;
        width: 100%;
        font-size: 12px;
        color: #63656e;
        text-align: left;
        overflow : hidden;
        text-overflow: ellipsis;
        word-break: break-all;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
      }
    }
    &:hover {
      box-shadow: 0px 0px 20px 0px rgba(0, 0, 0, 0.15);
    }
    &.active {
      box-shadow: 0px 0px 20px 0px rgba(0, 0, 0, 0.3);
    }
    &.default {
      @include taskNodeStyle ($defaultColor);
      &.active {
        @include nodeClick ($defaultColor);
      }
    }
    &.ready {
      @include taskNodeStyle ($grayDark);
      &.active {
        @include nodeClick ($grayDark);
      }
    }
    &.suspended {
      @include taskNodeStyle ($blueDark);
      &.active {
        @include nodeClick ($blueDark);
      }
    }
    &.finished {
      @include taskNodeStyle ($greenDark);
      &.active {
        @include nodeClick ($greenDark);
      }
    }
    &.running {
      .node-name {
        border-color: $blueDark;
      }
      @include taskNodeStyle ($blueDark);
      &.active {
        @include nodeClick ($blueDark);
      }
    }
    &.failed {
      .node-name {
        border-color: $redDark;
      }
      @include taskNodeStyle ($redDark);
      &.active {
        @include nodeClick ($redDark);
      }
    }
    &.fail-skip {
      .node-name .name-text {
        color: #c4c6cc;
      }
      @include taskNodeStyle ($brightRedDark);
      &.active {
        @include nodeClick ($brightRedDark);
      }
    }
    &.unchecked {
      &::before,
      .node-status-block,
      .node-name {
        opacity: 0.3;
      }
    }
  }
  :deep(.gateway-node) {
    position: relative;
    height: 34px;
    width: 34px;
    color: #738abe;
    text-align: center;
    &::before {
      content: '';
      position: absolute;
      top: 2px;
      left: 3px;
      width: 28px;
      height: 28px;
      background: #ffffff;
      border-radius: 3px;
      transform: rotate(45deg);
      z-index: -1;
    }
    .bpmn-flow-icon {
      height: 32px;
      line-height: 32px;
      font-size: 24px;
      text-align: center;
    }
    &.ready {
      @include gatewayStyle($grayDark);
    }
    &.failed {
      @include gatewayStyle($redDark);
    }
    &.finished {
      @include gatewayStyle($greenDark);
    }
    &.fail-skip {
      @include gatewayStyle($brightRedDark);
    }
  }
  :deep(.circle-node) {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    background: #96a1b9;
    font-size: 12px;
    color: #fff;
    border-radius: 50%;
    box-shadow: 0 0 0 2px #96a1b9;
    &.ready {
      @include circleStatusStyle($grayDark);
    }
    &.finished {
      @include circleStatusStyle($greenDark);
    }
    &.running {
      @include circleStatusStyle($blueDark)
    }
    &.failed {
      @include circleStatusStyle($redDark)
    }
  }

  :deep(.node-inset-line-point) {
    height: 14px;
    width: 14px;
    background-repeat: no-repeat;
    background-size: 14px;
    background-image: url('~@/assets/images/node-inset-line-point.svg');
  }
</style>
<style lang="scss">
  .custom-node-popover {
    .tippy-tooltip {
      background: transparent;
      padding: 0 7px;
      box-shadow: none;
      .tippy-backdrop {
        background: transparent;
      }
    }
  }
</style>
