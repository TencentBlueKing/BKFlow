<template>
  <div
    ref="processCanvasComp"
    class="process-canvas-comp">
    <div class="canvas-material-container" />
  </div>
</template>
<script>
  import { Graph, Markup } from '@antv/x6';
  // 对齐线
  import { Snapline } from '@antv/x6-plugin-snapline';
  import { registryEvents } from './registry/events.js';
  // 单选/框选
  import { Selection } from '@antv/x6-plugin-selection';
  import { Clipboard } from '@antv/x6-plugin-clipboard';
  import { registryNodes } from './registry/nodes.js';
  import dom from '@/utils/dom.js';
  import utilsTools from '@/utils/tools.js';

  export default {
    name: 'ProcessCanvasComp',
    props: {
      canvasData: {
        type: Array,
        default: () => ([]),
      },
      nodeVariableInfo: {
        type: Object,
        default: () => ({}),
      },
      editable: {
        type: Boolean,
        default: true,
      },
      showPalette: {
        type: Boolean,
        default: true,
      },
      gateways: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        graph: null,
        edgesPosition: {},
        matchLines: {},
        connectionHoverList: [],
        isDisableEndPoint: false,
        activeCell: null,
        showShortcutPanel: false,
        shortcutPanelPosition: { left: 0, right: 0 },
        isPerspective: false,
        isPerspectivePanelShow: false,
        nodeVariable: {},
        nodeTipsPanelPosition: {},
        isSelectionOpen: false,
        graphRandomKey: '',
      };
    },
    mounted() {
      this.initCanvas();
      this.initCanvasData();
      const { x, y } = this.graph.getContentArea();
      this.graph.positionPoint({ x, y }, 40, 134);
      document.addEventListener('mousemove', utilsTools.debounce(this.onMouseMove, 100), false);
    },
    beforeDestroy() {
      document.removeEventListener('mousemove', this.onMouseMove);
    },
    methods: {
      initCanvas() {
        this.graph = new Graph({
          container: this.$refs.processCanvasComp.querySelector('.canvas-material-container'),
          grid: {
            size: 1, // 网格大小 1px
            visible: false, // 不可见
          },
          panning: true, // 画布平移
          mousewheel: { // 画布缩放
            enabled: true,
            modifiers: ['ctrl'],
          },
          scaling: { // 最大和最小缩放比例
            min: 0.25,
            max: 1.5,
          },
          virtual: false, // 是否只渲染可视区域内容
          connecting: {
            allowBlank: false, // 是否允许连接到画布空白位置的点
            allowLoop: false, // 是否允许创建循环连线
            allowNode: false, // 是否允许边连接到节点
            allowEdge: false, // 是否允许边链接到另一个边
            allowMulti: false, // 是否允许在相同的起始节点和终止之间创建多条边
            highlight: false,
            snap: { // 开启连线过程中的自动吸附
              radius: 15, // 吸附半径
            },
            router: {
              name: 'manhattan',
              args: {
                padding: 1,
              },
            },
            connector: {
              name: 'rounded',
              args: {
                radius: 6,
              },
            },
            connectionPoint: 'anchor',
            // createEdge() {
            //   return new Shape.Edge({
            //     id: `line${uuid()}`,
            //     attrs: {
            //       line: {
            //         stroke: '#a9adb6',
            //         strokeWidth: 2,
            //         targetMarker: {
            //           name: 'block',
            //           width: 6,
            //           height: 8,
            //         },
            //       },
            //     },
            //     data: {},
            //     zIndex: 0,
            //   });
            // },
            // validateEdge: this.handleValidateEdge,
          },
          interacting: {
            nodeMovable: this.editable,
            edgeLabelMovable: this.editable,
            arrowheadMovable: this.editable,
          },
          highlighting: {
            // 连接桩可以被连接时在连接桩外围围渲染一个包围框
            magnetAvailable: {
              name: 'stroke',
              args: {
                attrs: {
                  fill: '#fff',
                  stroke: '#31d0c6',
                  'stroke-width': 1,
                },
              },
            },
            // 连接桩吸附连线时在连接桩外围围渲染一个包围框
            magnetAdsorbed: {
              name: 'stroke',
              args: {
                attrs: {
                  fill: '#fff',
                  stroke: '#3a84ff',
                  'stroke-width': 2,
                },
              },
            },
          },
          // 设置节点嵌套，实现分组效果
          embedding: {
            enabled: false,
            findParent({ node }) {
              if (node.shape === 'custom-group-node') {
                return [];
              }
              const bbox = node.getBBox();
              return this.getNodes().filter((node) => {
                const data = node.getData();
                if (data && data.parent) {
                  const targetBBox = node.getBBox();
                  return bbox.isIntersectWithRect(targetBBox);
                }
                return false;
              });
            },
          },
          onEdgeLabelRendered: (args) => {
            const { label } = args.label;
            const content = args.selectors.foContent;
            if (content) {
              const conditionDom = document.createElement('div');
              conditionDom.classList.add('branch-condition');
              if (label.isDefault) {
                conditionDom.classList.add('default-branch');
              }
              conditionDom.innerText = label.name;
              conditionDom.title = label.name;
              conditionDom.setAttribute('data-lineid', label.lineId);
              conditionDom.setAttribute('data-nodeid', label.sourceId);
              content.appendChild(conditionDom);
            }
          },
        });
        this.graph.use(new Snapline({
          enabled: true,
          className: 'custom-snap-line',
          tolerance: 2,
        }));
        this.graph.use(new Clipboard({
          enabled: true,
        }));
        // 点选/框选
        this.graph.use(new Selection({
          enabled: false, // 是否开启
          multiple: true, // 多选
          rubberband: false, // 启用框选
          showNodeSelectionBox: true, // 显示节点的选择框
          pointerEvents: 'none', // 解决节点的事件无法响应
        }));
        registryNodes(this.onEventMap);
        registryEvents(this.graph, this.editable);
        // 鼠标点击
        this.graph.on('cell:click', this.handleCellClick);
        // 新增边
        this.graph.on('edge:added', this.handleEdgeAdded);
      },
      initCanvasData() {
        if (!this.canvasData.length) return;
        this.canvasData.forEach((cell) => {
          if (cell.shape === 'edge') {
            this.graph.addEdge({ ...cell });
          } else {
            this.graph.addNode({ ...cell });
          }
        });
      },
      // 监听鼠标移动
      onMouseMove(e) {
        // 节点透视面板
        if (this.isPerspectivePanelShow) {
          if (!dom.parentClsContains('custom-node', e.target) && !dom.parentClsContains('node-tips-content', e.target)) {
            this.nodeTipsPanelPosition = {};
            this.isPerspectivePanelShow = false;
          }
        }
        // 监听鼠标是否hover到节点/连线上
        if (this.showShortcutPanel) {
          const domClass = this.activeCell.shape === 'edge' ? 'x6-edge' : 'custom-node';
          if (!dom.parentClsContains(`${domClass}`, e.target) && !dom.parentClsContains('shortcut-panel', e.target)) {
            this.closeShortcutPanel();
          }
        }
      },
      // 获取节点坐标/尺寸
      getNodeLocation(node, type) {
        const location = {
          id: node.id,
          type: node.data.type,
          ...node.size(),
          ...node.position(),
        };
        if (type === 'add') {
          // x6画布偏移
          let offsetLeft = 0;
          let offsetTop = 0;
          const x6ViewDom = this.getNodeElement('.x6-graph-svg-viewport');
          const transform = x6ViewDom.getAttribute('transform');
          if (transform) {
            const offset = transform
              .slice(7, -1)
              .split(',')
              .slice(-2);
            offsetLeft = Number(offset[0]);
            offsetTop = Number(offset[1]);
          }
          // 节点坐标
          const nodeCellDom = this.getNodeElement(`g[data-cell-id="${node.id}"]`);
          const { top, left } = nodeCellDom.querySelector('.custom-node').getBoundingClientRect();
          const canvasDom = this.getNodeElement();
          const { left: canvasLeft, top: canvasTop } = canvasDom.getBoundingClientRect();
          const ratio = this.graph.zoom();
          location.x = (left - canvasLeft - offsetLeft) / ratio;
          location.y = (top - canvasTop - offsetTop) / ratio;
        }
        return location;
      },
      setNodeInsetPointStyle(pointDoms, lineConfig, location) {
        // 节点宽高
        let { width: nodeWidth, height: nodeHeight } = location;
        // 获取当前画布的缩放比例
        const ratio = this.graph.zoom();
        nodeWidth = nodeWidth * ratio;
        nodeHeight = nodeHeight * ratio;
        const defaultAttribute = 'position: absolute; z-index: 8; font-size: 14px;';
        const doms = Array.from(pointDoms);
        if (lineConfig.segmentPosition.width > 8) { // 平行
          const sameAttribute = `top: ${((nodeHeight - 14) / 2) / ratio}px; transform: scale(${1 / ratio});`;
          doms[0].style.cssText = `${defaultAttribute}left: -7px;${sameAttribute}`;
          doms[1].style.cssText = `${defaultAttribute}right: -7px;${sameAttribute}`;
        } else { // 垂直
          const sameAttribute = `left: ${((nodeWidth - 14) / 2) / ratio}px; transform: scale(${1 / ratio});`;
          doms[0].style.cssText = `${defaultAttribute}top: -7px;${sameAttribute}`;
          doms[1].style.cssText = `${defaultAttribute}bottom: -7px;${sameAttribute}`;
        }
      },
      // 获取单个对应的边
      getEdgeInstance(lineId) {
        const edges = this.graph.getEdges();
        return edges.find(item => item.id === lineId);
      },
      // 获取单个对应的节点
      getNodeInstance(nodeId) {
        const nodes = this.graph.getNodes();
        return nodes.find(item => item.id === nodeId);
      },
      getConditionInfo({ sourceId, lineId, targetId }) {
        // 拷贝插入节点前网关的配置（todo 保留分支）
        const gateways = utilsTools.deepClone(this.gateways);
        // 插入节点时，若起始节点为网关节点则保留分支表达式
        if (sourceId in gateways) {
          const branchInfo = gateways[sourceId];
          const { conditions, default_condition: defaultCondition } = branchInfo;
          if (conditions) {
            const tagCode = `branch_${sourceId}_${targetId}`;
            conditions.tag = tagCode;
            let conditionInfo = conditions[lineId];
            if (defaultCondition && defaultCondition.flow_id === lineId) {
              defaultCondition.tag = tagCode;
              conditionInfo = { ...defaultCondition, defaultCondition };
            }
            return conditionInfo;
          }
        }
        return null;
      },
      // 节点/边点击
      handleCellClick({ cell, e }) {
        // 是否点击到分支标签上
        if (dom.parentClsContains('branch-condition', e.target)) {
          this.branchConditionEditHandler(e);
          return;
        }
        if (cell.shape === 'custom-node') {
          this.$emit('onSubflowNodeClick', cell.id, cell.data.type, cell.data);
        }
      },
      // 分支条件点击回调
      branchConditionEditHandler(e) {
        const $branchEl = e.target;
        const lineId = $branchEl.dataset.lineid;
        const nodeId = $branchEl.dataset.nodeid;
        const branchInfo = this.getBranchConditions(nodeId);
        const { name, evaluate: value, tag, loc } = branchInfo && branchInfo[lineId];
        if ($branchEl.classList.contains('branch-condition')) {
          e.stopPropagation();
          this.$emit('onConditionClick', {
            id: lineId,
            nodeId,
            name,
            value,
            tag,
            loc,
            outgoing: lineId,
          });
        }
      },
      // 监听画布添加连线
      handleEdgeAdded({ cell }) {
        this.$nextTick(() => {
          // 添加标签
          const branchInfo = this.getBranchConditions(cell.source.cell) || {};
          // 增加分支网关 label
          if (branchInfo && Object.keys(branchInfo).length > 0) {
            const conditionInfo = branchInfo[cell.id] || {};
            if (!Object.keys(conditionInfo).length) return;
            const textDom = document.createElement('span');
            textDom.innerText = conditionInfo.name;
            textDom.style.fontSize = '12px';
            textDom.style.padding = '0 6px';
            document.body.appendChild(textDom);
            let { width = 0 } = textDom.getBoundingClientRect();
            width = width > 60 ? width : 60;
            width = width > 112 ? 112 : width;
            document.body.removeChild(textDom);
            const distance = conditionInfo.loc || (-width / 2 - 20);
            cell.appendLabel({
              markup: Markup.getForeignObjectMarkup(),
              attrs: {
                fo: {
                  width,
                  height: 26,
                  x: -width,
                  y: -13,
                },
              },
              label: {
                ...conditionInfo,
                lineId: cell.id,
                sourceId: cell.source.cell,
              },
              position: {
                distance,
                offset: {
                  x: width / 2,
                  y: 0,
                },
              },
            });
          }
        });
      },
      getBranchConditions(gatewayId) {
        let branchConditions = {};
        Object.keys(this.gateways).some((gKey) => {
          const info = this.gateways[gKey];
          if (info.id === gatewayId) {
            if (info.conditions) {
              branchConditions = Object.assign({}, info.conditions);
            }
            if (info.default_condition) {
              const nodeId = info.default_condition.flow_id;
              branchConditions[nodeId] = {
                ...info.default_condition,
                isDefault: true,
              };
            }
            return true;
          }
          return false;
        });
        return branchConditions;
      },
      // 获取画布中节点元素
      getNodeElement(className) {
        const canvasDom = document.querySelector('.canvas-material-container');
        if (!className) return canvasDom;
        return canvasDom.querySelector(className) || document.querySelector(className);
      },
      onEventMap() {
        const self = this;
        return {
          onNodeCheckClick(id, checked) {
            self.$emit('onNodeCheckClick', id, checked);
          },
          onRetryClick(id) {
            self.$emit('onRetryClick', id);
          },
          onSkipClick(id) {
            self.$emit('onSkipClick', id);
          },
          onTaskNodeResumeClick(id) {
            self.$emit('onTaskNodeResumeClick', id);
          },
          onApprovalClick(id) {
            self.$emit('onApprovalClick', id);
          },
          onForceFail(id) {
            self.$emit('onForceFail', id);
          },
          onSubprocessPauseResumeClick(id, type) {
            self.$emit('onSubprocessPauseResumeClick', id, type);
          },
          onGatewaySelectionClick(id) {
            self.$emit('onGatewaySelectionClick', id);
          },
        };
      },
      // 重置画布
      resetCells() {
        this.graph.clearCells(true);
        this.initCanvasData();
        const cells = this.graph.getCells();
        this.graph.resetCells(cells, true);
      },
      updateConditionCanvasData(data) {
        // 清除旧的生成新的
        const edgeInstance = this.getEdgeInstance(data.id);
        edgeInstance.removeLabelAt(0);
        this.handleEdgeAdded({ cell: edgeInstance });
      },
      onUpdateNodeInfo(id, data) {
        const nodeInstance = this.getNodeInstance(id);
        nodeInstance && nodeInstance.setData(data);
      },
      setCanvasPosition(id, pos = 'center') {
        const nodeInstance = this.getNodeInstance(id);
        this.graph.positionCell(nodeInstance, pos);
      },
    },
  };
</script>
<style lang="scss" scoped>
  .process-canvas-comp {
    position: relative;
    display: flex;
    align-items: top;
    width: 100%;
    height: 100%;
    overflow: hidden;
    .canvas-material-container {
      flex: 1;
      background: #e1e4e8;
      cursor: -webkit-grab;
    }
    .canvas-tools-wrap {
      position: absolute;
      top: 20px;
      left: 100px;
      z-index: 1;
      &.view-mode {
        left: 40px;
      }
    }
    ::v-deep .x6-widget-selection-box {
      border: 1px dashed #3a84ff;
      margin-top: -3px;
      margin-left: -3px;
    }

    ::v-deep .x6-widget-selection-inner {
      border: none;
      box-shadow: none;
    }
    ::v-deep .branch-condition {
      padding: 4px 6px;
      min-width: 60px;
      max-width: 112px;
      min-height: 20px;
      font-size: 12px;
      line-height: 16px;
      text-align: center;
      color: #978e4d;
      background: #fcf9e2;
      border: 1px solid #ccc79f;
      border-radius: 2px;
      outline: none;
      cursor: pointer;
      -webkit-user-select: none;
      -moz-user-select: none;
      user-select: none;
      white-space: nowrap;
      text-overflow: ellipsis;
      overflow: hidden;
      &:hover {
        border-color: #3a84ff;
      }
      &.default-branch {
        background: #f0f1f5;
        border: 1px solid #c4c6cc;
      }
    }
    ::v-deep .custom-snap-line {
      .x6-widget-snapline-vertical,
      .x6-widget-snapline-horizontal {
        stroke: #3a84ff;
      }
    }
    // 节点样式用到了相对定位、绝对定位，解决在safari上会存在兼容性问题
    ::v-deep .x6-cell.x6-node {
        .bk-tooltip {
            position: fixed;
        }
    }
  }

</style>
<style lang="scss">
  .bk-sideslider-show {
    .process-canvas-comp body {
      overflow-y: initial !important;
    }
  }
</style>
