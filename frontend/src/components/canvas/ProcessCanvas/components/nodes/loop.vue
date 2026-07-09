<template>
  <div class="loop-node-root">
    <bk-popover
      theme="light"
      placement="bottom-end"
      ext-cls="custom-node-popover"
      :disabled="nodeData.mode !== 'execute' || nodeData.task_state === 'REVOKED'"
      :distance="5"
      :arrow="false">
      <div
        :class="[
          'loop-container-node',
          nodeData.mode === 'execute' ? 'default' : '',
          nodeData.status ? nodeData.status.toLowerCase() : '',
          { 'fail-skip': nodeData.status === 'FINISHED' && nodeData.skip },
          { 'ready': nodeData.ready },
          { 'active': nodeData.isActived },
          { 'unchecked ': nodeData.mode === 'select' && nodeData.optional && !nodeData.checked },
          { 'is-actived': nodeData.isActived },
          { 'is-hover': isHovered },
          { 'is-resizing': isResizing }
        ]"
        @mouseenter="onMouseEnter"
        @mouseleave="onMouseLeave">
        <Configs
          v-if="nodeData.type"
          :node="nodeData"
          @onNodeCheckClick="onNodeCheckClick" />
        <ExecuteStatus :node="nodeData" />
        <div class="loop-header">
          <i :class="['node-icon-font', getIconCls(nodeData)]" />
          <div
            v-if="nodeData.stage_name"
            class="stage-name">
            {{ nodeData.stage_name }}
          </div>
          <span class="loop-title">{{ nodeData.name || '循环' }}</span>
          <!-- <span class="loop-child-count">{{ childCount }}</span> -->
          <i
            v-if="nodeData.mode !== 'execute'"
            class="loop-variables-icon common-icon-export"
            @click.stop="onShowVariables" />
        </div>
        <div class="loop-body" />
        <div
          v-show="isEditable && (isHovered || isActived || isResizing)"
          class="resize-handle resize-handle-tl"
          @mousedown.stop.prevent="onResizeStart('tl', $event)" />
        <div
          v-show="isEditable && (isHovered || isActived || isResizing)"
          class="resize-handle resize-handle-tr"
          @mousedown.stop.prevent="onResizeStart('tr', $event)" />
        <div
          v-show="isEditable && (isHovered || isActived || isResizing)"
          class="resize-handle resize-handle-bl"
          @mousedown.stop.prevent="onResizeStart('bl', $event)" />
        <div
          v-show="isEditable && (isHovered || isActived || isResizing)"
          class="resize-handle resize-handle-br"
          @mousedown.stop.prevent="onResizeStart('br', $event)" />
      </div>
      <template slot="content">
        <Actions
          :node="nodeData"
          @onRetryClick="$emit('onRetryClick', nodeData.id)"
          @onSkipClick="$emit('onSkipClick', nodeData.id)"
          @onTaskNodeResumeClick="$emit('onTaskNodeResumeClick', nodeData.id)"
          @onApprovalClick="$emit('onApprovalClick', nodeData.id)"
          @onForceFail="$emit('onForceFail', nodeData.id)"
          @onSubprocessPauseResumeClick="onSubprocessPauseResumeClick"
          @onGatewaySelectionClick="$emit('onGatewaySelectionClick', nodeData.id)" />
      </template>
    </bk-popover>
  </div>
</template>
<script>
  import Configs from './setting-flags/configs.vue';
  import ExecuteStatus from './setting-flags/execute-status.vue';
  import Actions from './setting-flags/actions.vue';
  import { BK_PLUGIN_ICON, SYSTEM_GROUP_ICON } from '@/constants/index.js';

  export default {
    name: 'LoopNode',
    components: {
      Configs,
      ExecuteStatus,
      Actions,
    },
    inject: ['getNode'],
    props: {
      node: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        nodeData: {},
        isActived: false,
        isHovered: false,
        isResizing: false,
        childCount: 0,
        resizeState: null,
        initialWidth: 415,
        initialHeight: 158,
      };
    },
    computed: {
      isOpenTooltip() {
        if (this.nodeData.mode === 'execute') {
          if (this.nodeData.status === 'RUNNING') {
            return ['sleep_timer', 'pause_node'].indexOf(this.nodeData.code) > -1;
          }
          return this.nodeData.status === 'FAILED';
        }
        return false;
      },
      isShowSkipBtn() {
        if (this.nodeData.status === 'FAILED' && (this.nodeData.skippable || this.nodeData.errorIgnorable)) {
          return true;
        }
        return false;
      },
      isShowRetryBtn() {
        if (this.nodeData.status === 'FAILED' && (this.nodeData.retryable || this.nodeData.errorIgnorable)) {
          return true;
        }
        return false;
      },
      isEditable() {
        try {
          const node = this.getNode();
          const graph = node.model?.graph;
          if (!graph) return true;
          const { interacting } = graph.options;
          if (typeof interacting?.nodeMovable === 'function') {
            return interacting.nodeMovable({ cell: node });
          }
          return interacting?.nodeMovable ?? true;
        } catch (e) {
          return true;
        }
      },
    },
    mounted() {
      const node = this.getNode();
      this.nodeData = node.getData();
      node.on('change:data', ({ current }) => {
        this.nodeData = current;
      });
      // 记录初始尺寸作为缩放下限，防止缩小到子节点溢出
      const size = node.size();
      this.initialWidth = size.width;
      this.initialHeight = size.height;
      // this.updateChildCount();
      // 监听子节点变化
      // node.on('change:children', () => {
      //   this.updateChildCount();
      // });
    },
    beforeDestroy() {
      // 清理残留的 resize 事件监听
      if (this.resizeState) {
        document.removeEventListener('mousemove', this.onResizeMove);
        document.removeEventListener('mouseup', this.onResizeEnd);
        const node = this.getNode();
        node.removeProp('resizeHandling');
        this.resizeState = null;
      }
    },
    methods: {
      getIconCls(node) {
        const { code, group, type } = node;
        if (BK_PLUGIN_ICON[code]) {
          return BK_PLUGIN_ICON[code];
        }
        if (code === 'remote_plugin') {
          return 'common-icon-sys-third-party';
        }
        if (type === 'SubCanvas') {
          return 'common-icon-elliptic-cycle';
        }
        const systemType = SYSTEM_GROUP_ICON.find(item => new RegExp(item).test(group));
        if (systemType) {
          return `common-icon-sys-${systemType.toLowerCase()}`;
        }
        return 'common-icon-sys-default';
      },
      onMouseEnter() {
        if (this.isEditable) {
          this.isHovered = true;
        }
      },
      onMouseLeave() {
        this.isHovered = false;
      },
      onNodeCheckClick(checked) {
        this.$emit('onNodeCheckClick', this.nodeData.id, checked);
      },
      onSubprocessPauseResumeClick(type) {
        this.$emit('onSubprocessPauseResumeClick', this.nodeData.id, type);
      },
      onShowVariables() {
        const node = this.getNode();
        this.$emit('onShowLoopVariables', node.id);
      },
      updateChildCount() {
        const node = this.getNode();
        const children = node.getChildren();
        this.childCount = children ? children.length : 0;
      },
      // 计算所有子节点的包围盒（相对父节点左上角的坐标，含 20px padding）
      getChildBounds() {
        const node = this.getNode();
        const children = node.getChildren?.() || [];
        if (!children.length) return null;
        const parentPos = node.position();
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        children.forEach((child) => {
          if (!child.isNode || !child.isNode()) return;
          const pos = child.position(); // X6 v2 默认返回绝对坐标
          const size = child.size();
          const relX = pos.x - parentPos.x;
          const relY = pos.y - parentPos.y;
          minX = Math.min(minX, relX);
          minY = Math.min(minY, relY);
          maxX = Math.max(maxX, relX + size.width);
          maxY = Math.max(maxY, relY + size.height);
        });
        const padding = 20;
        return {
          minX: minX - padding,
          minY: minY - padding,
          maxX: maxX + padding,
          maxY: maxY + padding,
        };
      },
      onResizeStart(direction, e) {
        const node = this.getNode();
        // X6 v2 中从节点获取 Graph 需通过 node.model.graph
        const graph = node.model?.graph;
        const zoom = graph?.zoom?.() ?? 1;
        this.resizeState = {
          direction,
          startX: e.clientX,
          startY: e.clientY,
          startWidth: node.size().width,
          startHeight: node.size().height,
          startPosX: node.position().x,
          startPosY: node.position().y,
          zoom,
        };
        this.isResizing = true;
        // 标记节点正在 resize，阻止 X6 节点拖拽
        node.prop('resizeHandling', true);
        document.addEventListener('mousemove', this.onResizeMove);
        document.addEventListener('mouseup', this.onResizeEnd);
      },
      onResizeMove(e) {
        if (!this.resizeState) return;
        const { direction, startX, startY, startWidth, startHeight, startPosX, startPosY, zoom } = this.resizeState;
        const dx = (e.clientX - startX) / zoom;
        const dy = (e.clientY - startY) / zoom;
        let newWidth = startWidth;
        let newHeight = startHeight;
        let newX = startPosX;
        let newY = startPosY;
        const minW = this.initialWidth;
        const minH = this.initialHeight;
        switch (direction) {
          case 'tl': // 左上角：宽高减少，位置右下移
            newWidth = Math.max(minW, startWidth - dx);
            newHeight = Math.max(minH, startHeight - dy);
            newX = startPosX + startWidth - newWidth;
            newY = startPosY + startHeight - newHeight;
            break;
          case 'tr': // 右上角：宽度增加/高度减少，y 上移
            newWidth = Math.max(minW, startWidth + dx);
            newHeight = Math.max(minH, startHeight - dy);
            newY = startPosY + startHeight - newHeight;
            break;
          case 'bl': // 左下角：宽度减少/高度增加，x 左移
            newWidth = Math.max(minW, startWidth - dx);
            newHeight = Math.max(minH, startHeight + dy);
            newX = startPosX + startWidth - newWidth;
            break;
          case 'br': // 右下角：宽高都增加，位置不变
            newWidth = Math.max(minW, startWidth + dx);
            newHeight = Math.max(minH, startHeight + dy);
            break;
        }

        // 子节点溢出约束：只有当 resize 会导致子节点溢出时才阻止
        const childBounds = this.getChildBounds();
        if (childBounds) {
          const relLeft = newX - startPosX;
          const relTop = newY - startPosY;
          const relRight = relLeft + newWidth;
          const relBottom = relTop + newHeight;

          // 溢出检查：分组边缘越过子节点边缘即为溢出
          const overflowLeft = relLeft > childBounds.minX;
          const overflowTop = relTop > childBounds.minY;
          const overflowRight = relRight < childBounds.maxX;
          const overflowBottom = relBottom < childBounds.maxY;

          switch (direction) {
            case 'tl': {
              // 左/上边缘移动，右/下边缘固定
              if (overflowLeft) {
                newX = startPosX + childBounds.minX;
                newWidth = (startPosX + startWidth) - newX;
              }
              if (overflowTop) {
                newY = startPosY + childBounds.minY;
                newHeight = (startPosY + startHeight) - newY;
              }
              break;
            }
            case 'tr': {
              // 右/上边缘移动，左/下边缘固定
              if (overflowRight) {
                newWidth = childBounds.maxX - relLeft;
              }
              if (overflowTop) {
                newY = startPosY + childBounds.minY;
                newHeight = (startPosY + startHeight) - newY;
              }
              break;
            }
            case 'bl': {
              // 左/下边缘移动，右/上边缘固定
              if (overflowLeft) {
                newX = startPosX + childBounds.minX;
                newWidth = (startPosX + startWidth) - newX;
              }
              if (overflowBottom) {
                newHeight = childBounds.maxY - relTop;
              }
              break;
            }
            case 'br': {
              // 右/下边缘移动，左/上边缘固定
              if (overflowRight) {
                newWidth = childBounds.maxX - relLeft;
              }
              if (overflowBottom) {
                newHeight = childBounds.maxY - relTop;
              }
              break;
            }
          }
          // 再次应用最小尺寸限制
          if (newWidth < minW) {
            if (direction === 'tl' || direction === 'bl') {
              newX = (startPosX + startWidth) - minW;
            }
            newWidth = minW;
          }
          if (newHeight < minH) {
            if (direction === 'tl' || direction === 'tr') {
              newY = (startPosY + startHeight) - minH;
            }
            newHeight = minH;
          }
        }

        const node = this.getNode();
        node.resize(newWidth, newHeight);
        node.setPosition(newX, newY);
      },
      onResizeEnd() {
        if (!this.resizeState) return;
        const node = this.getNode();
        node.removeProp('resizeHandling');
        this.isResizing = false;
        this.resizeState = null;
        document.removeEventListener('mousemove', this.onResizeMove);
        document.removeEventListener('mouseup', this.onResizeEnd);
        // resize 结束后同步位置/尺寸信息到 store
        this.$emit('onResizeEnd', node);
      },
    },
  };
</script>
<style lang="scss" scoped>
  $grayDark: #b4becd;
  $blueDark: #699df4;
  $defaultColor: #738abe;
  $redDark: #ea3636;
  $greenDark: #9adc9e;
  $brightRedDark: #f0a0a0;

  @mixin loopNodeStyle ($color) {
    .loop-header { background: $color; }
    &.active, &.is-actived {
      .loop-header {
        background-color:  $color;
      }
    }
  }

  .loop-node-root {
    width: 100%;
    height: 100%;
    :deep(.bk-tooltip) {
      display: block;
      width: 100%;
      height: 100%;
      overflow: visible;
    }
    :deep(.bk-tooltip-ref) {
      display: block;
      width: 100%;
      height: 100%;
      overflow: visible;
    }
  }
  .loop-container-node {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #ffffff;
    border-radius: 6px;
    box-shadow: 0 1px 4px 0 rgba(0, 0, 0, 0.1);
    overflow: visible;
    transition: box-shadow 0.2s, border-color 0.2s;
    // 确保 resize handles（负坐标定位）不被父级裁剪
    overflow: visible;
    &.is-active {
      box-shadow: 0 0 0 2px #3a84ff;
      border-color: #3a84ff;
    }
    &.is-hover {
      box-shadow: 0 0 20px 0 rgba(0, 0, 0, 0.15);
    }
    &.is-resizing {
      user-select: none;
    }
    .loop-header {
      display: flex;
      align-items: center;
      padding: 0 8px;
      height: 20px;
      background: #738abe;
      border-top-left-radius: 4px;
      border-top-right-radius: 4px;
      flex-shrink: 0;
      transition: background 0.2s;
      .node-icon-font {
        font-size: 16px;
        width: 16px;
        color: #ffffff;
      }
      .stage-name {
        margin-left: 4px;
        font-size: 12px;
        color: #ffffff;
        white-space: nowrap;
        text-overflow: ellipsis;
        overflow: hidden;
      }
      .loop-title {
        margin-left: 4px;
        font-size: 12px;
        line-height: 20px;
        color: #ffffff;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
      }
      .loop-child-count {
        margin-left: 8px;
        font-size: 11px;
        color: rgba(255, 255, 255, 0.8);
        white-space: nowrap;
      }
      .loop-variables-icon {
        margin-left: 8px;
        font-size: 12px;
        color: #ffffff;
        cursor: pointer;
        transition: color 0.2s;
      }
    }
    .loop-body {
      flex: 1;
      position: relative;
      background: #f5f7fa;
      min-height: 80px;
      .loop-body-inner {
        position: relative;
        width: 100%;
        height: 100%;
        min-height: 80px;
      }
      .loop-empty-tip {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        color: #c4c6cc;
        font-size: 12px;
        pointer-events: none;
        .loop-empty-icon {
          font-size: 28px;
          font-style: normal;
          color: #d8dde5;
        }
      }
    }
    .resize-handle {
      position: absolute;
      width: 10px;
      height: 10px;
      background: #3a84ff;
      border: 1px solid #ffffff;
      border-radius: 2px;
      z-index: 10;
      opacity: 0;
      transition: opacity 0.2s ease;
      &.resize-handle-tl {
        top: -5px;
        left: -5px;
        cursor: nwse-resize;
      }
      &.resize-handle-tr {
        top: -5px;
        right: -5px;
        cursor: nesw-resize;
      }
      &.resize-handle-bl {
        bottom: -5px;
        left: -5px;
        cursor: nesw-resize;
      }
      &.resize-handle-br {
        bottom: -5px;
        right: -5px;
        cursor: nwse-resize;
      }
    }
    &.is-hover .resize-handle,
    &.is-active .resize-handle,
    &.is-resizing .resize-handle {
      opacity: 1;
    }
    :deep(.node-config-flags) {
      top: -18px;
      z-index: 5;
    }
    &.unchecked {
      opacity: 0.3;
    }
    &:hover {
      box-shadow: 0px 0px 20px 0px rgba(0, 0, 0, 0.15);
    }
    &.active {
      box-shadow: 0px 0px 20px 0px rgba(0, 0, 0, 0.3);
    }
    &.default {
      @include loopNodeStyle($defaultColor);
    }
    &.ready {
      @include loopNodeStyle($grayDark);
    }
    &.suspended {
      @include loopNodeStyle($blueDark);
    }
    &.finished {
      @include loopNodeStyle($greenDark);
    }
    &.running {
      @include loopNodeStyle($blueDark);
    }
    &.failed {
      @include loopNodeStyle($redDark);
    }
    &.fail-skip {
      @include loopNodeStyle($brightRedDark);
    }
  }
</style>
