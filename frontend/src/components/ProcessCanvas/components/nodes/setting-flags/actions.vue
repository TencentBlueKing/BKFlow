<template>
  <div class="node-actions">
    <!--任务节点-->
    <template v-if="node.type === 'task'">
      <span
        v-if="isShowRetryBtn"
        @click.stop="$emit('onRetryClick')">
        <i class="common-icon-retry" />
        {{ i18n.t('重试') }}
      </span>
      <span
        v-if="isShowSkipBtn"
        @click.stop="$emit('onSkipClick')">
        <i class="common-icon-skip" />
        {{ i18n.t('跳过') }}
      </span>
      <template v-if="node.status === 'RUNNING'">
        <span
          v-if="node.code === 'pause_node'"
          @click.stop="$emit('onTaskNodeResumeClick')">
          <i class="common-icon-play" />
          {{ i18n.t('继续') }}
        </span>
        <span
          v-else-if="node.code === 'bk_approve'"
          @click.stop="$emit('onApprovalClick')">
          <i class="common-icon-circulation" />
          {{ i18n.t('审批') }}
        </span>
        <span
          v-else
          @click.stop="$emit('onForceFail')">
          <i class="common-icon-mandatory-failure" />
          {{ i18n.t('强制终止') }}
        </span>
      </template>
    </template>
    <!--子流程节点-->
    <template v-if="node.type === 'subprocess'">
      <template v-if="node.task_state !== 'REVOKED'">
        <template v-if="node.status === 'FAILED' && node.type === 'tasknode'">
          <span
            v-if="isShowRetryBtn"
            @click.stop="$emit('onRetryClick')">
            <i class="common-icon-retry" />
            {{ i18n.t('重试子流程') }}
          </span>
          <span
            v-if="isShowSkipBtn"
            @click.stop="$emit('onSkipClick')">
            <i class="common-icon-skip" />
            {{ i18n.t('跳过子流程') }}
          </span>
        </template>
        <template v-if="node.status === 'RUNNING'">
          <span @click.stop="$emit('onSubprocessPauseResumeClick','pause')">
            <i class="common-icon-mandatory-failure" />
            {{ i18n.t('暂停') }}
          </span>
          <span
            v-if="hasAdminPerm"
            @click.stop="$emit('onForceFail')">
            <i class="common-icon-resume" />
            {{ i18n.t('强制终止') }}
          </span>
        </template>
        <span
          v-if="node.status === 'SUSPENDED'"
          @click.stop="$emit('onSubprocessPauseResumeClick','resume')">
          <i class="common-icon-play" />
          {{ i18n.t('继续') }}
        </span>
      </template>
    </template>
    <!--网关节点-->
    <template v-if="['branch-gateway', 'parallel-gateway'].includes(node.type)">
      <span
        v-if="isOpenTooltip"
        @click.stop="$emit('onGatewaySelectionClick')">
        <i class="common-icon-skip" />
        {{ i18n.t('跳过') }}
      </span>
    </template>
  </div>
</template>

<script>
  import i18n from '@/config/i18n/index.js';
  export default {
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        i18n,
      };
    },
    computed: {
      isOpenTooltip() {
        const { mode, status, code, type, task_state: taskState } = this.node;
        if (mode === 'execute') {
          if (['branch-gateway', 'parallel-gateway'].includes(type)) {
            return taskState !== 'REVOKED' && status === 'FAILED';
          }
          if (status === 'RUNNING') {
            return ['sleep_timer', 'pause_node'].indexOf(code) > -1;
          }
          return status === 'FAILED';
        }
        return false;
      },
      isShowSkipBtn() {
        const { skippable, status, errorIgnorable } = this.node;
        if (status === 'FAILED' && (skippable || errorIgnorable)) {
          return true;
        }
        return false;
      },
      isShowRetryBtn() {
        const { retryable, status, errorIgnorable } = this.node;
        if (status === 'FAILED' && (retryable || errorIgnorable)) {
          return true;
        }
        return false;
      },
    },
  };
</script>

<style lang="scss">

.node-actions {
  display: flex;
  align-items: center;
  > span {
    &:not(:last-child) {
      margin-right: 23px;
      position: relative;
      &::after {
        content: '';
        position: absolute;
        top: 0;
        right: -11px;
        display: inline-block;
        height: 16px;
        width: 1px;
        background: #979ba5;
      }
    }
    i {
      color: #979ba5;
      margin-right: 5px;
      &.common-icon-play {
        font-size: 14px;
      }
    }
    &:hover {
      cursor: pointer;
      color: #3a84ff;
      i {
        color: #3a84ff;
      }
    }
  }
}
</style>
