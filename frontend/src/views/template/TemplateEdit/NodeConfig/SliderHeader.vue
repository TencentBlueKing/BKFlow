<template>
  <div
    slot="header"
    class="config-header">
    <template v-if="isVariablePanelShow">
      <i
        class="bk-icon icon-arrows-left variable-back-icon"
        @click="$emit('closeEditingPanel')" />
      <span>
        {{ variableData.key ? $t('编辑') : $t('新建全局变量') }}
      </span>
    </template>
    <template v-else>
      <span
        :class="['go-back', { 'active': isSelectorPanelShow }]"
        @click="$emit('back')">
        <i
          v-if="backToVariablePanel"
          class="bk-icon icon-arrows-left variable-back-icon"
          @click="$emit('close', true)" />
        {{ $t('节点配置') }}
      </span>
      <!-- 全局变量popover -->
      <VariablePopover
        v-if="!isSelectorPanelShow"
        :is-view-mode="isViewMode"
        :variable-list="variableList"
        @openVariablePanel="$emit('openVariablePanel', $event)" />
    </template>
  </div>
</template>

<script>
  import VariablePopover from './VariablePopover.vue';
  export default {
    name: 'SliderHeader',
    components: {
      VariablePopover,
    },
    props: {
      isVariablePanelShow: {
        type: Boolean,
        default: false,
      },
      variableData: {
        type: Object,
        default: () => ({}),
      },
      isSelectorPanelShow: {
        type: Boolean,
        default: false,
      },
      backToVariablePanel: {
        type: Boolean,
        default: false,
      },
      isViewMode: {
        type: Boolean,
        default: true,
      },
      variableList: {
        type: Array,
        default: () => ([]),
      },
    },
  };
</script>

<style lang="scss" scoped>

.config-header {
  position: relative;
  display: flex;
  align-items: center;
  .go-back {
    display: flex;
    align-items: center;
    &.active {
      color: #3a84ff;
      cursor: pointer;
    }
  }
  .quick-insert-btn {
    position: absolute;
    top: 14px;
    right: 20px;
    font-weight: normal;
    line-height: 19px;
    font-size: 14px;
    padding: 6px 13px;
    background: #f0f1f5;
    border-radius: 4px;
    cursor: pointer;
  }
  .variable-back-icon {
    font-size: 32px;
    cursor: pointer;
    &:hover {
      color: #3a84ff;
    }
  }
}
</style>
