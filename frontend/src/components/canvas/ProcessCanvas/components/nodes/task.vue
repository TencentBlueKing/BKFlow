<template>
  <div
    class="node-item task-node"
    :class="[
      node.mode === 'execute' ? 'default' : '',
      { 'fail-skip': node.status === 'FINISHED' && (node.skip || node.error_ignored) },
      { 'ready': node.ready },
      { 'active': node.isActived },
      { 'active': node.isActived },
      { 'unchecked ': node.mode === 'select' && node.optional && !node.checked }
    ]">
    <div class="node-status-block">
      <i
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
    <div
      v-if="node.hasUpdated"
      class="updated-dot">
      <div class="ripple" />
    </div>
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import { SYSTEM_GROUP_ICON, BK_PLUGIN_ICON } from '@/constants/index.js';
  export default {
    name: 'Task',
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        phaseStr: {
          1: i18n.t('当前插件即将停止维护，请更新插件版本'),
          2: i18n.t('当前插件已停止维护，请更新插件版本'),
        },
      };
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
    },
    methods: {
      getIconCls(node) {
        const { code, group } = node;
        if (BK_PLUGIN_ICON[code]) {
          return BK_PLUGIN_ICON[code];
        }

        if (code === 'remote_plugin') {
          return 'common-icon-sys-third-party';
        }
        const systemType = SYSTEM_GROUP_ICON.find(item => new RegExp(item).test(group));
        if (systemType) {
          return `common-icon-sys-${systemType.toLowerCase()}`;
        }
        return 'common-icon-sys-default';
      },
    },
  };
</script>
<style lang="scss" scoped>
  .task-node {
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
  }
</style>
