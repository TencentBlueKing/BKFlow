<template>
  <div class="canvas-tools-wrap">
    <div class="tools-content">
      <div
        v-bk-tooltips="{
          content: $t('缩略视图'),
          delay: 300,
          placements: ['bottom']
        }"
        :class="['tool-icon', {
          'is-active': showSmallMap
        }]"
        @click="onToggleMapShow">
        <i class="common-icon-thumbnail-view" />
      </div>
      <div
        v-if="isShowSelectAllTool"
        v-bk-tooltips="{
          content: selectNodeName,
          delay: 300,
          placements: ['bottom']
        }"
        :class="['tool-icon', {
          'is-active': isAllSelected
        }]"
        @click="onToggleAllNode">
        <i :class="['common-icon-checked-all', { 'tool-disable': isSelectAllToolDisabled }]" />
      </div>
      <div class="zoom-wrapper">
        <i
          v-bk-tooltips="{
            content: $t('放大'),
            delay: 300,
            placements: ['bottom']
          }"
          class="common-icon-zoom-add"
          @click="onZoomOut" />
        <p class="zoom-ratio">
          {{ zoomRatio + '%' }}
        </p>
        <i
          v-bk-tooltips="{
            content: $t('缩小'),
            delay: 300,
            placements: ['bottom']
          }"
          class="common-icon-zoom-minus"
          @click="onZoomIn" />
      </div>
      <div class="square-wrapper">
        <div
          v-bk-tooltips="{
            content: $t('复位'),
            delay: 300,
            placements: ['bottom']
          }"
          class="tool-icon"
          @click="onResetPosition">
          <i class="common-icon-reset" />
        </div>
        <!-- <div
          :class="['tool-icon', {
            'is-disabled': !canUndo
          }]"
          v-bk-tooltips="{
            content: '撤销',
            delay: 300,
            placements: ['bottom']
          }"
          @click="onUndo">
          <i class="common-icon-revoke"></i>
        </div>
        <div
          :class="['tool-icon', {
            'is-disabled': !canRedo
          }]"
          v-bk-tooltips="{
            content: '重做',
            delay: 300,
            placements: ['bottom']
          }"
          @click="onRedo">
          <i class="common-icon-redo"></i>
        </div> -->
        <div
          v-if="editable"
          v-bk-tooltips="{
            content: $t('节点框选'),
            delay: 300,
            placements: ['bottom']
          }"
          :class="['tool-icon', {
            'is-active': isSelectionOpen
          }]"
          @click="onOpenFrameSelect">
          <i class="common-icon-node-selection" />
        </div>
        <div
          v-if="editable"
          v-bk-tooltips="{
            content: $t('排版'),
            delay: 300,
            placements: ['bottom']
          }"
          class="tool-icon"
          @click="onFormatPosition">
          <i class="common-icon-typesetting" />
        </div>
      </div>
      <div
        v-bk-tooltips="{
          content: $t('快捷键'),
          delay: 300,
          placements: ['bottom']
        }"
        :class="['tool-icon', {
          'is-active': isShowHotKey
        }]"
        @click="onToggleHotKeyInfo">
        <i class="common-icon-hot-key" />
      </div>
      <div
        v-bk-tooltips="{
          content: $t('变量引用预览'),
          delay: 300,
          placements: ['bottom']
        }"
        :class="['tool-icon', {
          'is-active': isPerspective
        }]"
        @click="onTogglePerspective">
        <i class="common-icon-perspective" />
      </div>
      <div
        v-bk-tooltips="{
          content: $t('导出图片'),
          delay: 300,
          placements: ['bottom']
        }"
        class="tool-icon"
        @click="$emit('onDownloadCanvas')">
        <i class="common-icon-export-scheme" />
      </div>
    </div>
    <HelpInfo
      :editable="editable"
      :is-show-hot-key="isShowHotKey"
      @onCloseHotkeyInfo="isShowHotKey = false" />
    <div
      v-if="showSmallMap"
      class="canvas-minimap" />
  </div>
</template>
<script>
  import { Graph } from '@antv/x6';
  import { History } from '@antv/x6-plugin-history';
  import { MiniMap } from '@antv/x6-plugin-minimap';
  import HelpInfo from './helpInfo.vue';
  import utilsTools from '@/utils/tools.js';
  import { uuid } from '@/utils/uuid.js';
  export default {
    name: 'CanvasTool',
    components: {
      HelpInfo,
    },
    props: {
      instance: Graph,
      editable: {
        type: Boolean,
        default: true,
      },
      isShowSelectAllTool: {
        type: Boolean,
        default: false,
      },
      isSelectAllToolDisabled: {
        type: Boolean,
        default: false,
      },
      isAllSelected: {
        type: Boolean,
        default: false,
      },
      isPerspective: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        canUndo: false,
        canRedo: false,
        zoomRatio: 100,
        isShowHotKey: false,
        showSmallMap: false,
        isSelectionOpen: false,
        selectionOriginPos: {
          x: 0,
          y: 0,
        },
        pasteMousePos: {
          x: 0,
          y: 0,
        },
      };
    },
    computed: {
      selectNodeName() {
        return this.isAllSelected ? this.$t('全选') : this.$t('反选');
      },
    },
    mounted() {
      this.instance.use(new History({
        enabled: true,
      }));
      this.instance.on('history:change', () => {
        this.canRedo = this.instance.canRedo();
        this.canUndo = this.instance.canUndo();
      });
      this.instance.on('scale', this.setZoomRatio);
      // 节点选中
      this.instance.on('selection:changed', this.handleSelectedChange);
      document.addEventListener('keydown', this.handlerKeyDown, false);
    },
    beforeDestroy() {
      document.removeEventListener('keydown', this.handlerKeyDown, false);
    },
    methods: {
      onUndo() {
        this.canUndo && this.instance.undo();
      },
      onRedo() {
        this.canRedo && this.instance.redo();
      },
      handlerKeyDown(e) {
        const ctrl = window.event.ctrlKey;
        const hotKeyTriggeringConditions = [
          { name: 'onZoomOut', keyCodes: [107, 187], ctrl: true },
          { name: 'onZoomIn', keyCodes: [109, 189], ctrl: true },
          { name: 'onResetPosition', keyCodes: [96, 48], ctrl: true },
        ];
        const action = hotKeyTriggeringConditions.find((item) => {
          const result  = item.keyCodes.indexOf(e.keyCode) > -1 && !!ctrl === item.ctrl;
          return result;
        });
        if (action && this.isUsable(action.name)) {
          e.preventDefault();
          this[action.name](action.params);
        }
      },
      isUsable(name) {
        // 只读模式可用快捷键列表
        const readOnlyModeCanUse = ['onZoomIn', 'onZoomOut', 'onResetPosition'];
        if (!this.editable && readOnlyModeCanUse.indexOf(name) < -1) {
          return false;
        }
        return true;
      },
      onExportData() {
        const data = this.instance.toJSON();
        const blob = new Blob([JSON.stringify(data)], { type: 'text/plain;charset=UTF-8' });
        const eleLink = document.createElement('a');
        const blobURL = window.URL.createObjectURL(blob);
        eleLink.style.display = 'none';
        eleLink.href = blobURL;
        eleLink.setAttribute('download', 'x6_canvas_export_data.json');

        // hack HTML5 download attribute
        if (typeof eleLink.download === 'undefined') {
          eleLink.setAttribute('target', '_blank');
        }
        document.body.appendChild(eleLink);
        eleLink.click();
        document.body.removeChild(eleLink);
        window.URL.revokeObjectURL(blobURL);
      },
      onZoomIn() {
        this.instance.zoom(-0.1);
        this.setZoomRatio();
      },
      onZoomOut() {
        this.instance.zoom(0.1);
        this.setZoomRatio();
      },
      setZoomRatio() {
        this.zoomRatio = Math.round(this.instance.zoom() * 100);
      },
      onToggleMapShow() {
        this.isShowHotKey = false;
        this.showSmallMap = !this.showSmallMap;
        this.$nextTick(() => {
          if (this.showSmallMap) {
            this.instance.use(new MiniMap({
              container: document.querySelector('.canvas-minimap'),
              width: 344,
              height: 216,
              scalable: false,
            }));
          } else {
            this.instance.disposePlugins('minimap');
          }
        });
      },
      onToggleHotKeyInfo() {
        this.showSmallMap = false;
        this.isShowHotKey = !this.isShowHotKey;
      },
      onResetPosition() {
        this.instance.zoomTo(1);
        this.instance.translate(0, 0);
      },
      onFormatPosition() {
        this.$emit('onFormatPosition');
      },
      onToggleAllNode() {
        this.showSmallMap = false;
        this.$emit('onToggleAllNode', !this.isAllSelected);
      },
      onOpenFrameSelect() {
        this.isSelectionOpen = true;
        this.$emit('onFrameSelectToggle', true);
        // 禁用画布平移
        this.instance.disablePanning();
        // 开启选择
        this.instance.enableSelection();
        // 开启框选
        this.instance.enableRubberband();
        // 设置光标样式
        const graphSvg = this.getNodeElement('.x6-graph-svg');
        graphSvg.style.cursor = 'crosshair';
      },
      onFrameSelectEnd() {
        this.isSelectionOpen = false;
        this.$emit('onFrameSelectToggle', false);
        this.instance.enablePanning();
        this.instance.disableSelection();
        this.instance.disableRubberband();
        const graphSvg = this.getNodeElement('.x6-graph-svg');
        graphSvg.style.cursor = 'pointer';
      },

      // 节点选中
      handleSelectedChange({ selected }) {
        if (this.isSelectionOpen) {
          this.onFrameSelectEnd();
        }
        if (selected.length) {
          this.selectionOriginPos = this.getNodesLocationOnLeftTop(selected);
          document.addEventListener('keydown', this.handleKeydown);
          document.addEventListener('mousemove', this.pasteMousePosHandler);
        } else {
          document.removeEventListener('keydown', this.handleKeydown);
          document.removeEventListener('mousemove', this.pasteMousePosHandler);
        }
      },
      /**
       * 获取节点组里，相对画布靠左上角的点位置
       */
      getNodesLocationOnLeftTop(nodes) {
        let x = 0;
        let y = 0;
        nodes.forEach((node, index) => {
          const { x: nodeX, y: nodeY } = node.position();
          x = index === 0 ? nodeX : Math.min(x, nodeX);
          y = index === 0 ? nodeY : Math.min(y, nodeY);
        });
        return { x, y };
      },
      // 监听按键按下
      handleKeydown(e) {
        const selectedNodes = this.instance.getSelectedCells();
        if (!selectedNodes.length) {
          return false;
        }
        if ((e.ctrlKey || e.metaKey) && e.keyCode === 86) { // ctrl + v
          this.onPasteNodes();
        } else if ([37, 38, 39, 40].includes(e.keyCode)) { // 选中后支持上下左右移动节点
          const typeMap = {
            37: 'left',
            38: 'top',
            39: 'right',
            40: 'bottom',
          };
          this.onMoveNodesByHand(selectedNodes, typeMap[e.keyCode]);
        } else if ([46, 8].includes(e.keyCode)) { // 删除
          selectedNodes.forEach((node) => {
            this.$emit('onNodeRemove', node);
          });
        }
      },
      pasteMousePosHandler(e) {
        this.pasteMousePos = {
          x: e.offsetX,
          y: e.offsetY,
        };
      },
      /**
       * 手动移动节点
       * @param {Array} selectedNodes 移动节点信息，数组
       * @param {String} direction 移动方向
       * @param {Number} length 移动距离，默认 5px
       */
      onMoveNodesByHand(selectedNodes, direction, length = 5) {
        let bx = 0;
        let by = 0;
        switch (direction) {
          case 'left':
            bx = -length;
            break;
          case 'right':
            bx = length;
            break;
          case 'top':
            by = -length;
            break;
          case 'bottom':
            by = length;
            break;
        }
        selectedNodes.forEach((node) => {
          const { x, y } = node.position();
          node.position(x + bx, y + by);
          this.$emit('onLocationMoveDone', node);
        });
      },
      // 粘贴节点
      onPasteNodes() {
        const cells = this.instance.getSelectedCells();
        const { x: originX, y: originY } = this.selectionOriginPos;
        const { x: mouseX, y: mouseY } = this.pasteMousePos;
        const { line: lines, activities } = this.$store.state.template;
        const locationHash = {};
        const selectCells = [];
        // 克隆生成的节点
        cells.forEach((node) => {
          const nodeId = `node${uuid()}`;
          const { id, data, shape } = node;
          const { x, y } = node.position();
          const activity = utilsTools.deepClone(activities[id]);
          const extraData = {
            ...data,
            oldSouceId: id,
          };
          if (activity) {
            extraData.atomId = activity.type === 'ServiceActivity' ? activity.component.code : activity.template_id;
          }
          const nodeInstance = this.instance.addNode({
            id: nodeId,
            x: x + mouseX - originX,
            y: y + mouseY - originY,
            ...node.size(),
            shape,
            data: extraData,
            zIndex: 6,
          });
          locationHash[id] = nodeId;
          selectCells.push(nodeInstance);
          this.$emit('onLocationChange', 'copy', nodeInstance);
        });
        // 克隆生成的线
        lines.forEach((line) => {
          const { source, target } = line;
          if (locationHash[source.id] && locationHash[target.id]) {
            this.createEdge({
              source: {
                port: `port_${source.arrow.toLowerCase()}`,
                cell: locationHash[source.id],
              },
              target: {
                port: `port_${target.arrow.toLowerCase()}`,
                cell: locationHash[target.id],
              },
              data: {
                oldSouceId: line.id,
              },
            });
          }
        });
        this.instance.cleanSelection();
        this.instance.select(selectCells);
      },
      // 创建边
      createEdge({ source, target, data }) {
        const edgeId = `line${uuid()}`;
        this.instance.addEdge({
          shape: 'edge',
          id: edgeId,
          source,
          target,
          attrs: {
            line: {
              stroke: '#a9adb6',
              strokeWidth: 2,
              targetMarker: {
                name: 'block',
                width: 6,
                height: 8,
              },
            },
            class: edgeId,
          },
          data,
          zIndex: 0,
          router: {
            name: 'manhattan',
            args: {
              padding: 1,
            },
          },
        });
        this.$emit('onLineChange', 'add', {
          id: edgeId,
          source,
          target,
          data,
        });
      },
      // 获取画布中节点元素
      getNodeElement(className) {
        const canvasDom = document.querySelector('.canvas-material-container');
        if (!className) return canvasDom;
        return canvasDom.querySelector(className) || document.querySelector(className);
      },
      onTogglePerspective() {
        this.$emit('onTogglePerspective');
      },
      onExportScheme() {
        this.$emit('onExportScheme');
      },
    },
  };
</script>
<style lang="scss" scoped>
.canvas-tools-wrap {
  .tools-content {
    height: 36px;
    display: flex;
    align-items: center;
    padding: 0 12px;
    top: 20px;
    left: 80px;
    z-index: 5;
    transition: all 0.5s ease;
    user-select: none;
    background: #ffffff;
    opacity: 1;
    border-radius: 2px;
    box-shadow: 0px 2px 4px 0px rgba(0,0,0,0.10);
    & > *:not(:last-child) {
      position: relative;
      &::after {
        content: '';
        height: 15px;
        width: 1px;
        position: absolute;
        right: -12px;
        top: 5px;
        background: #dcdee5;
      }
    }
  }
  .tool-icon {
    height: 24px;
    width: 24px;
    padding: 0 4px;
    margin-right: 20px;
    color: #919eb5;
    cursor: pointer;
    &:last-child {
      margin-right: 0;
    }
    &:hover {
      color: #699df4;
      background: #f4f7ff;
      border-radius: 1px;
    }
    &.is-active {
      color: #3a84ff;
      background: #f4f7ff;
      border-radius: 1px;
    }
    &.is-disabled {
      color: #ccc;
      cursor: not-allowed;
    }
    .tool-disable {
      cursor: not-allowed;
      opacity: 0.3;
    }
  }
  .zoom-wrapper, .square-wrapper {
    height: 24px;
    display: flex;
    align-items: center;
    margin-right: 20px;
    .common-icon-zoom-add, .common-icon-zoom-minus {
      font-size: 18px;
      color: #919eb5;
      cursor: pointer;
      &:hover {
        color: #3a84ff;
      }
    }
    .zoom-ratio {
      width: 32px;
      text-align: center;
      font-size: 12px;
      transform: scale(.8);
      color: #c4c6cc;
    }
    .tool-icon {
      margin-right: 16px;
      &:last-child {
        margin-right: 0;
      }
    }
  }
  .canvas-minimap {
    position: absolute;
    top: 60px;
    /deep/.x6-widget-minimap {
      .x6-graph {
        box-shadow: none;
      }
      .x6-widget-minimap-viewport {
        border: 1px solid #3a84ff;
      }
    }
    // 小画布tooltip取消固定定位
    /deep/ .x6-cell.x6-node {
      .bk-tooltip {
        position: relative;
      }
    }
  }
}
</style>
