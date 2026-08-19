<template>
  <div
    ref="processCanvasComp"
    class="process-canvas-comp">
    <Tools
      v-if="graph && !isSubflowGraph"
      :instance="graph"
      class="canvas-tools"
      :class="{ 'view-mode': !editable }"
      :editable="editable"
      :is-perspective="isPerspective"
      :is-selection-open="isSelectionOpen"
      :is-all-selected="isAllSelected"
      :is-show-select-all-tool="isShowSelectAllTool"
      :is-select-all-tool-disabled="isSelectAllToolDisabled"
      @onNodeRemove="onNodeRemove"
      @onToggleAllNode="onToggleAllNode"
      @onFrameSelectToggle="isSelectionOpen = $event"
      @onFormatPosition="onFormatPosition"
      @onLocationMoveDone="onLocationMoveDone"
      @onLocationChange="onLocationChange"
      @onLineChange="onLineChange"
      @onDownloadCanvas="onDownloadCanvas"
      @onTogglePerspective="onTogglePerspective" />
    <Dnd
      v-if="graph && showPalette"
      ref="dndInstance"
      :instance="graph"
      :canvas-data="canvasData"
      @dragging="onNodeMoving"
      @dragEnd="onNodeMoveStop" />
    <div class="canvas-material-container" />
    <template v-if="graph">
      <NodeTipsPanel
        v-if="isPerspectivePanelShow"
        :instance="graph"
        :is-perspective-panel-show="isPerspectivePanelShow"
        :node-variable="nodeVariable"
        :node-tips-panel-position="nodeTipsPanelPosition" />
      <!-- 节点透视面板/变量引用预览面板 -->
      <ShortcutPanel
        v-if="showShortcutPanel"
        :instance="graph"
        :active-cell="activeCell"
        :position="shortcutPanelPosition"
        @onNodeRemove="onNodeRemove"
        @onLineChange="onLineChange"
        @onLocationChange="onLocationChange"
        @updateShortcutPanel="updateShortcutPanel" />
    </template>
  </div>
</template>
<script>
  import { Graph, Shape, Markup } from '@antv/x6';
  // 对齐线
  import { Snapline } from '@antv/x6-plugin-snapline';
  import { registryNodes } from './registry/nodes.js';
  import { registryEvents } from './registry/events.js';
  // 工具栏
  import Tools from './components/tools.vue';
  // 左侧菜单面板
  import Dnd from './components/dnd/index.vue';
  // svg path解析
  import parseSvgPath from 'parse-svg-path';

  import { uuid } from '@/utils/uuid.js';

  // 快捷面板
  import ShortcutPanel from './components/shortcutPanel.vue';

  // 变量引用/执行记录面板
  import NodeTipsPanel from './components/nodeTipsPanel.vue';
  // 单选/框选
  import { Selection } from '@antv/x6-plugin-selection';
  import { Clipboard } from '@antv/x6-plugin-clipboard';

  import dom from '@/utils/dom.js';
  import { mapState } from 'vuex';
  import utilsTools from '@/utils/tools.js';
  import validatePipeline from '@/utils/validatePipeline.js';
  import domtoimage from '@/utils/domToImage.js';

  export default {
    name: 'ProcessCanvasComp',
    components: {
      Tools,
      Dnd,
      ShortcutPanel,
      NodeTipsPanel,
    },
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
      isAllSelected: {
        type: Boolean,
        default: false,
      },
      isShowSelectAllTool: {
        type: Boolean,
        default: false,
      },
      isSelectAllToolDisabled: {
        type: Boolean,
        default: false,
      },
      isSubflowGraph: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        graph: null,
        edgesPosition: {},
        matchLines: {},
        connectionHoverList: [],
        activeCell: null,
        showShortcutPanel: false,
        shortcutPanelPosition: { left: 0, right: 0 },
        isPerspective: false,
        isPerspectivePanelShow: false,
        nodeVariable: {},
        nodeTipsPanelPosition: {},
        isSelectionOpen: false,
      };
    },
    computed: {
      ...mapState({
        activities: state => state.template.activities,
        locations: state => state.template.location,
        lines: state => state.template.line,
        gateways: state => state.template.gateways,
        startNode: state => state.template.start_event,
        endNode: state => state.template.end_event,
      }),
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
            createEdge() {
              return new Shape.Edge({
                id: `line${uuid()}`,
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
                },
                data: {},
                zIndex: 0,
              });
            },
            validateEdge: this.handleValidateEdge,
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
        // 节点移动
        this.graph.on('node:moving', this.onNodeMoving);
        // 节点停止移动
        this.graph.on('node:moved', this.onNodeMoveStop);
        // 鼠标点击
        this.graph.on('cell:click', this.handleCellClick);
        // 鼠标移入
        this.graph.on('cell:mouseenter', this.handleCellMouseenter);
        // 新增边
        this.graph.on('edge:added', this.handleEdgeAdded);
        // 节点双击
        this.graph.on('node:dblclick', ({ cell }) => {
          if (!this.editable) return;
          this.onShowNodeConfig(cell.id);
          this.closeShortcutPanel();
        });
        // 标签沿着连线拖拽
        this.graph.on('edge:change:labels', this.handleLabelDrag);
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
      // 显示快捷节点面板
      openShortcutPanel({ cell, e }) {
        // 结束节点不展示快捷面板
        if (cell.data?.type === 'end') return;
        this.activeCell = cell;
        const canvasDom = this.getNodeElement();
        const { left: canvasLeft, top: canvasTop } = canvasDom.getBoundingClientRect();
        let top; let left;
        if (cell.shape === 'edge') {
          left = e.clientX - canvasLeft + 60 + 6; // 6-偏移宽度
          top = e.clientY - canvasTop + 6; // 6-偏移高度
        } else  {
          const nodeDom = this.getNodeElement(`[data-cell-id=${cell.id}] .custom-node`);
          if (!nodeDom) return;
          const { height, width, top: nodeT, left: nodeL  } = nodeDom.getBoundingClientRect();
          left = nodeL - canvasLeft + width / 2 + 80;
          top = nodeT - canvasTop + height + 6;
        }

        this.showShortcutPanel = true;
        this.shortcutPanelPosition = { left, top };
      },
      // 隐藏快捷节点面板
      closeShortcutPanel() {
        this.activeCell = null;
        this.showShortcutPanel = false;
        this.shortcutPanelPosition =  {};
      },
      // 更新快捷面板位置
      updateShortcutPanel(nodeId) {
        // 关闭旧的面板
        this.closeShortcutPanel();
        // 打开新的面板
        if (nodeId) {
          const nodeInstance = this.getNodeInstance(nodeId);
          setTimeout(() => {
            this.openShortcutPanel({ cell: nodeInstance });
          }, 50);
        }
      },
      // 节点移动
      onNodeMoving({ node, type }) {
        if (type === 'add') {
          this.closeShortcutPanel();
        }
        // 节点引用变量面板跟着节点移动
        if (this.isPerspectivePanelShow) {
          this.judgeNodeTipsPanelPos(node);
        }
        // 节点快捷操作面板跟随节点移动
        if (this.showShortcutPanel) {
          this.openShortcutPanel({ cell: node });
        }
        // 判断节点是否存在连线
        const nodeEdges = this.graph.getConnectedEdges(node.id);
        if (nodeEdges.length) {
          // 更新边的避免配置
          nodeEdges.forEach((edge) => {
            edge.setRouter('manhattan', {
              padding: 1,
              excludeNodes: [],
            });
          });
          return;
        }
        // 计算边的坐标
        if (!Object.keys(this.edgesPosition).length) {
          const edges = this.graph.getEdges();
          edges.forEach((item) => {
            const edgeDom = this.getNodeElement(`g[data-cell-id="${item.id}"]`);
            const pathDom = edgeDom && edgeDom.childNodes[0];
            const pathPos = parseSvgPath(pathDom?.attributes.d.value);
            this.edgesPosition[item.id] = pathPos;
            // 所有边不避免该节点
            item.setRouter('manhattan', {
              padding: 1,
              excludeNodes: [node.id],
            });
          });
        }
        const location = this.getNodeLocation(node, type);
        this.onNodeToEdgeDragging(location, type);
      },
      // 节点停止移动
      onNodeMoveStop({ node, type = 'edit' }) {
        this.edgesPosition = {};
        if (Object.keys(this.matchLines).length === 1) {
          const location = {
            id: node.id,
            ...node.size(),
          };
          this.handleDraggerNodeToEdge(location);
        }
        if (type === 'add') {
          // 新增时需从最新的node实例中获取坐标
          const nodeInstance = this.getNodeInstance(node.id);
          this.onLocationChange(type, nodeInstance);
        } else {
          this.onLocationMoveDone(node);
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
      // 节点拖拽到过边过程
      onNodeToEdgeDragging(location, type) {
        if (!location) return;
        // 获取父级节点dom, id为空时表示从左侧菜单栏直接拖拽，还未生成的节点
        const parentDom = this.getNodeElement(`[data-cell-id=${location.id}] .custom-node`);
        // 拖拽节点到线上, 自动匹配连线
        const matchLines = this.getNodeMatchLines(location);
        this.matchLines = matchLines || {};
        if (Object.keys(matchLines).length === 1) {
          const lineConfig = Object.values(matchLines)[0];
          const edgeInstance = this.getEdgeInstance(lineConfig.id);
          edgeInstance.attr('line/stroke', '#3a84ff');
          this.connectionHoverList.push(lineConfig.id);
          // 左侧菜单栏拖拽生成的节点，需添加两侧端点
          if (type !== 'add') return;

          // 判断端点是否已经创建
          const pointDoms = parentDom.querySelectorAll('.node-inset-line-point');
          if (!pointDoms.length) {
            // 创建节点两边插入连线的端点
            const pointDom1 = document.createElement('span');
            const pointDom2 = document.createElement('span');
            pointDom1.className = 'node-inset-line-point';
            pointDom2.className = 'node-inset-line-point';
            this.setNodeInsetPointStyle([pointDom1, pointDom2], lineConfig, location);
            parentDom.appendChild(pointDom1);
            parentDom.appendChild(pointDom2);
          } else { // 未创建的节点拖拽时需要实时计算端点的位置
            this.setNodeInsetPointStyle(pointDoms, lineConfig, location);
          }
        } else if (this.connectionHoverList.length) {
          this.connectionHoverList.forEach((lineId) => {
            const edgeInstance = this.getEdgeInstance(lineId);
            edgeInstance?.attr('line/stroke', '#a9adb6');
          });
          this.connectionHoverList = [];
          // 移除节点两边插入连线的端点
          const pointDoms = parentDom.querySelectorAll('.node-inset-line-point');
          if (pointDoms.length) {
            Array.from(pointDoms).forEach((pointDomItem) => {
              parentDom.removeChild(pointDomItem);
            });
          }
        }
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
      // 拖拽节点到线上, 获取对应匹配连线
      getNodeMatchLines(loc) {
        let offsetLeft; let offsetTop;
        if (loc.type.indexOf('gateway') > -1) {
          offsetLeft = 7;
          offsetTop = 7;
        } else {
          offsetLeft = 40;
          offsetTop = 15;
        }
        // 横向区间
        const horizontalInterval = [loc.x + offsetLeft, loc.x + loc.width - offsetLeft];
        // 纵向区间
        const verticalInterval = [loc.y + offsetTop, loc.y + loc.height - offsetTop];
        // 符合匹配连线
        const matchLines = {};
        // 符合匹配的线段
        let segmentPosition = {};
        Object.keys(this.edgesPosition).forEach((key) => {
          const edgeSegment = this.edgesPosition[key];
          const excludeIndex = [];
          const segments = edgeSegment.reduce((acc, cur, index) => {
            if (!excludeIndex.includes(index) && edgeSegment[index + 1]) {
              const [x1, y1] = cur.slice(-2);
              const [x2, y2] = edgeSegment[index + 1].slice(-2);
              acc.push({ x1, y1, x2, y2 });
              excludeIndex.push(...[index, index + 1]);
            }
            return acc;
          }, []);
          let inputArrow = 'port_left';
          let outputArrow = 'port_right';
          const isMatch = segments.some((item) => {
            // 计算线段的高宽和坐标
            const { x1, x2, y1, y2 } = item;
            // 线段的坐标的最大值/最小值
            const maxX = Math.max(x1, x2);
            const minX = Math.min(x1, x2);
            const maxY = Math.max(y1, y2);
            const minY = Math.min(y1, y2);

            let width; let height;
            if (x1 === x2) { // 垂直
              width = 0;
              height = maxY - minY;
              inputArrow = y1 > y2 ? 'port_bottom' : 'port_top';
              outputArrow = y1 > y2 ? 'port_top' : 'port_bottom';
            } else if (y1 === y2) { // 水平
              height = 0;
              width = maxX - minX;
              inputArrow = x1 > x2 ? 'port_right' : 'port_left';
              outputArrow = x1 > x2 ? 'port_left' : 'port_right';
            }
            segmentPosition = { left: minX, top: minY, height, width };

            if (width > loc.width || height > loc.height) { // 线段长需大于节点宽度或高度
              if (width === 0) { // 垂直线
                return (minX > horizontalInterval[0] && horizontalInterval[1] > minX)
                  && (minY < verticalInterval[0] && maxY > verticalInterval[1]);
              }
              return (minY > verticalInterval[0] && verticalInterval[1] > minY)
                && (minX < horizontalInterval[0] && maxX > horizontalInterval[1]);
            }
            return false;
          });
          if (isMatch) {
            const edgeInstance = this.getEdgeInstance(key);
            const edgeProp = edgeInstance.prop();
            matchLines[key] = {
              id: key,
              source: edgeProp.source,
              target: edgeProp.target,
              segmentPosition,
              inputArrow,
              outputArrow,
            };
          }
        });
        return matchLines || {};
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
      // 拖拽节点到边上, 自动生成边
      handleDraggerNodeToEdge(location) {
        // 只对符合单条线的情况进行处理
        const { id: nodeId, width: nodeWidth, height: nodeHeight } = location;
        const nodeInstance = this.getNodeInstance(nodeId);
        const values = Object.values(this.matchLines)[0];
        // 计算节点的坐标和两端节点的左边是否在一条线上
        const { id: lineId, source, target, segmentPosition, inputArrow, outputArrow } = values;
        const { left, top, height, width } = segmentPosition;
        const bothNodes = [this.getNodeInstance(source.cell), this.getNodeInstance(target.cell)];
        bothNodes.some((item) => {
          const node = this.getNodeLocation(item);
          // 计算方法为：匹配节点的中线坐标 - 当前节点一半的高度
          if (height === 8 && node.y < top && top < (node.y + nodeHeight)) {
            const y = node.y + node.height / 2 - nodeHeight / 2;
            nodeInstance.position(location.x, y);
            return true;
          } if (width === 8 && node.x < left && left < (node.x + nodeWidth)) {
            const x = node.x + node.width / 2 - nodeWidth / 2;
            nodeInstance.position(x, location.y);
            return true;
          }
          return false;
        });
        // 删除旧的连线，创建新的连线
        const result = this.updateConnector({
          lineId,
          location,
          source,
          targetPort: inputArrow,
          sourcePort: outputArrow,
          target,
        });
        if (!result) return;
        const { startLine, endLine } = result;
        this.onLineChange('delete', values);
        this.$nextTick(() => {
          this.createEdge(startLine);
          this.createEdge(endLine);
        });
        this.matchLines = {};
        // 删除节点两端插入连线的端点
        const nodeDom = this.getNodeElement(`[data-cell-id=${location.id}] .custom-node`);
        const pointDoms = nodeDom && nodeDom.querySelectorAll('.node-inset-line-point');
        if (pointDoms.length) {
          Array.from(pointDoms).forEach((pointDomItem) => {
            nodeDom.removeChild(pointDomItem);
          });
        }
      },
      updateConnector(data) {
        const { lineId, location, source, target, sourcePort, targetPort } = data;
        // 删除旧的连线
        this.graph.removeEdge(lineId);
        // 新联连线配置
        const startLine = {
          source,
          target: {
            cell: location.id,
            port: targetPort,
          },
        };
        const endLine = {
          source: {
            port: sourcePort,
            cell: location.id,
          },
          target,
        };
        const conditionInfo = this.getConditionInfo({
          sourceId: source.cell,
          lineId,
          targetId: location.id,
        });
        if (conditionInfo) {
          startLine.data = { conditionInfo };
        }

        return { startLine, endLine };
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
      // 创建边
      createEdge({ source, target, data = {}, router = {} }) {
        const edgeId = `line${uuid()}`;
        this.graph.addEdge({
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
              class: edgeId,
            },
          },
          data,
          zIndex: 0,
          router: Object.assign({
            name: 'manhattan',
            args: {
              padding: 1,
            },
          }, router),
        });
        this.onLineChange('add', {
          id: edgeId,
          source,
          target,
          data,
        });
      },
      // 节点删除
      onNodeRemove(node, remove = this) {
        // 拷贝数据更新前的数据
        const activities = utilsTools.deepClone(this.activities);
        let nodeConfig = activities[node.id] || {};
        const lines = utilsTools.deepClone(this.lines);
        const isGatewayNode = node.data.type.indexOf('gateway') > -1;
        const gateways = utilsTools.deepClone(this.gateways);
        if (isGatewayNode) {
          nodeConfig = this.gateways[node.id];
        }

        if (remove) { // 删除节点, 解除节点时不删除节点
          this.graph.removeNode(node.id);
          this.onLocationChange('delete', node);
        } else { // 解除连线
          const nodeInstance = this.getNodeInstance(node.id);
          this.graph.select(nodeInstance);
        }
        // 删除节点两端旧的连线
        lines.forEach((line) => {
          if ([line.source.id, line.target.id].includes(node.id)) {
            this.onLineChange('delete', {
              id: line.id,
              source: { cell: line.source.id },
              target: { cell: line.target.id },
            });
            this.graph.removeEdge(line.id);
          }
        });
        // 被删除的节点只存在一条输入连线和输出连线时才允许自动连线
        const { incoming = [], outgoing } = nodeConfig;
        if (
          (!['start', 'end'].includes(node.data.type))
          && incoming.length === 1
          && (Array.isArray(outgoing) ? outgoing.length === 1 : outgoing)) {
          const { source } = lines.find(item => item.id === incoming[0]);
          const outlinesId = Array.isArray(outgoing) ? outgoing[0] : outgoing;
          const { target } = lines.find(item => item.id === outlinesId) || {};
          // 当分支上只剩开始/结束节点时，不自动连线
          if (source.id === this.startNode.id && target.id === this.endNode.id) return;
          // 当分支上只剩网关节点时，不自动连线
          if (gateways[source.id] && gateways[target.id]) return;
          // 当两端为汇聚节点和结束节点时，自动连线
          if (gateways[source.id] && gateways[source.id].type !== 'ConvergeGateway' && target.id === this.endNode.id) return;
          // 当需要生成的连线已存在，不自动连线
          const isExist = lines.find(item => item.source.id === source.id && item.target.id === target.id);
          if (isExist) return;
          const edgeInfo = {
            source: {
              cell: source.id,
              port: `port_${source.arrow.toLowerCase()}`,
            },
            target: {
              cell: target.id,
              port: `port_${target.arrow.toLowerCase()}`,
            },
          };
          // 因为边采用的是manhattan路由，解除连线时需过滤调该节点
          if (!remove) {
            edgeInfo.router = {
              name: 'manhattan',
              args: {
                padding: 1,
                excludeNodes: [node.id],
              },
            };
          }
          // 先更新数据再进行连线
          // 删除节点时，若起始节点为网关节点则保留分支表达式
          if (source.id in gateways) {
            const branchInfo = gateways[source.id];
            const { conditions, default_condition: defaultCondition } = branchInfo;
            if (!conditions) return;
            const tagCode = `branch_${source.id}_${target.id}`;
            conditions.tag = tagCode;
            let conditionInfo = conditions[incoming[0]];
            if (defaultCondition && defaultCondition.flow_id === incoming[0]) {
              defaultCondition.tag = tagCode;
              conditionInfo = { ...defaultCondition, defaultCondition };
            }
            edgeInfo.data = { conditionInfo };
          }
          // 创建新的连线
          this.createEdge(edgeInfo);
        }
        this.updateShortcutPanel();
      },
      // 停止拖动边时校验连线是否生效
      handleValidateEdge({ edge }) {
        // 判断当前连线的id已存在
        let existLineInfo = null;
        const lines = this.lines.filter((item) => {
          if (item.id === edge.id) {
            existLineInfo = item;
            return false;
          }
          return true;
        });
        const { id, source, target } = edge;
        const sourceArrow = source.port?.split('_')[1] || '';
        const targetArrow = target.port?.split('_')[1] || '';
        const validateMessage = validatePipeline.isLineValid({
          source: {
            id: source.cell,
            arrow: `${sourceArrow.charAt(0).toUpperCase()}${sourceArrow.slice(1)}`,
          },
          target: {
            id: target.cell,
            arrow: `${targetArrow.charAt(0).toUpperCase()}${targetArrow.slice(1)}`,
          },
        }, {
          lines,
          locations: this.locations,
        });
        if (validateMessage.result) {
          // 如果当前连线的id已存在，则代表是连线源端点拖动，需删除旧的生成新的
          if (existLineInfo) {
            this.graph.removeEdge(id);
            const { source: oldSource = {}, target: oldTarget = {} } = existLineInfo;
            const conditionInfo = this.getConditionInfo({
              lineId: id,
              sourceId: source.cell,
              targetId: target.cell,
            });
            this.onLineChange('delete', {
              id,
              source: {
                cell: oldSource.id,
                port: `port_${oldSource.arrow?.toLowerCase()}`,
              },
              target: {
                cell: oldTarget.id,
                port: `port_${oldTarget.arrow?.toLowerCase()}`,
              },
            });
            this.createEdge({
              source,
              target,
              data: {
                ...edge.data,
                conditionInfo,
              },
            });
            // 更新节点activities输入输出
          } else {
            const line = { id: edge.id, source, target };
            this.$emit('onLineChange', 'add', line);
            this.handleEdgeAdded({ cell: edge });
          }
        } else {
          this.$bkMessage({
            message: validateMessage.message,
            theme: 'warning',
          });
        }
        return validateMessage.result;
      },
      // 节点/边点击
      handleCellClick({ cell, e }) {
        // 节点点选
        if (this.editable && !this.isSelectionOpen) {
          const { data, shape } = cell;
          // 边/开始/结束节点不能被选中
          const supportSelect = shape === 'custom-node' && !['start', 'end'].includes(data.type);
          if (supportSelect && (e.ctrlKey || e.metaKey)) {
            this.graph.select(cell);
            return;
          }
        }
        // 清除选中
        this.graph.resetSelection();

        // 是否点击到checkbox上
        if (dom.parentClsContains('node-config-flags', e.target)) {
          return;
        }

        // 是否点击到分支标签上
        if (dom.parentClsContains('branch-condition', e.target)) {
          this.branchConditionEditHandler(e);
          return;
        }

        // 如果不是模版编辑页面，点击节点相当于打开配置面板（任务执行是打开执行信息面板）
        if (this.editable) {
          // 避免双击时再次触发单击
          if (this.showShortcutPanel) return;
          // 展开节点配置面板
          this.openShortcutPanel({ cell, e });
        } else if (cell.shape === 'custom-node') {
          // 任务执行打开执行信息面板
          this.$emit('onNodeClick', cell.id, cell.data.type);
          // 模板页面打开配置面板
          this.onShowNodeConfig(cell.id);
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
          });
        }
        if (this.editable) {
          this.$emit('templateDataChanged');
        }
      },
      // 鼠标移入
      handleCellMouseenter({ cell }) {
        if (this.showShortcutPanel && cell.id !== this.activeCell.id) {
          this.closeShortcutPanel();
        }
        this.isPerspectivePanelShow = false;
        // 节点透视面板展开
        if (this.isPerspective && cell.shape === 'custom-node' && ['task', 'subflow'].includes(cell.data.type)) {
          const variableInfo = this.nodeVariableInfo[cell.id] || { input: [], output: [] };
          variableInfo.variableList = [...new Set([...variableInfo.input, ...variableInfo.output])];
          this.nodeVariable = variableInfo;
          this.isPerspectivePanelShow = true;
        }
        // 计算位置
        if (this.isPerspectivePanelShow) {
          this.judgeNodeTipsPanelPos(cell);
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
      // 标签拖拽
      handleLabelDrag({ edge, current, previous }) {
        if (!previous || !previous.length || !current.length) return;
        // 边的长度
        const svgPath = this.getNodeElement(`.${edge.id}`);
        const edgeLength = svgPath.getTotalLength();
        current.forEach((item) => {
          const { width } = item.attrs.fo;
          item.position.offset = {
            x: width / 2,
            y: 0,
          };
          // 限制label.position.distance的值在min到max之间
          const min = (width / 2 + 20) / edgeLength;
          const max = 1 - min;
          const distance = Math.max(min, Math.min(max, item.position.distance));
          item.position.distance = distance;
          // 更新本地condition配置
          const condition = {
            ...item.label,
            id: edge.id,
            nodeId: edge.source.cell,
            loc: distance,
            value: item.label.evaluate,
          };
          if (item.label.isDefault) {
            condition.default_condition = {
              ...item.label,
              loc: distance,
            };
          }
          this.$emit('updateCondition', condition);
        });
      },
      // 获取画布中节点元素
      getNodeElement(className) {
        const canvasDom = document.querySelector('.canvas-material-container');
        if (!className) return canvasDom;
        return canvasDom.querySelector(className) || document.querySelector(className);
      },
      onLineChange(type, data) {
        this.$emit('templateDataChanged');
        this.$emit('onLineChange', type, data);
      },
      onLocationChange(type, data) {
        this.$emit('templateDataChanged');
        this.$emit('onLocationChange', type, data);
      },
      onLocationMoveDone(data) {
        this.$emit('templateDataChanged');
        this.$emit('onLocationMoveDone', data);
      },
      onToggleAllNode(val) {
        this.$emit('onToggleAllNode', val);
      },
      onFormatPosition() {
        this.$emit('templateDataChanged');
        this.$emit('onFormatPosition');
      },
      onShowNodeConfig(id) {
        this.$emit('onShowNodeConfig', id);
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
      onTogglePerspective() {
        this.isPerspective = !this.isPerspective;
        this.$emit('onTogglePerspective', this.isPerspective);
      },
      // 计算节点执行历史/输入输出面板位置
      judgeNodeTipsPanelPos(node) {
        if (!node) return;
        // 节点提示面板宽度
        // 计算判断节点右边的距离是否够展示气泡卡片
        const nodeDom = this.getNodeElement(`[data-cell-id=${node.id}] .custom-node`);
        if (!nodeDom) return;
        const { width, left: nodeLeft, right: nodeRight, top: nodeTop } = nodeDom.getBoundingClientRect();
        const canvasDom = this.getNodeElement();
        const { left: canvasLeft, top: canvasTop } = canvasDom.getBoundingClientRect();
        // dnd侧栏宽度
        const dndWidth = this.showPalette ? 60 : 0;
        // 200节点的气泡卡片展示最小宽度
        const bodyWidth = document.body.offsetWidth;
        const isRight = bodyWidth - nodeRight > 200;
        // 设置坐标
        let top = nodeTop - canvasTop - 10;
        let left; let padding;
        if (isRight) {
          left = nodeLeft - canvasLeft + width + dndWidth;
          padding = '0 0 0 10px';
        } else {
          left = nodeLeft - canvasLeft - 200 + dndWidth;
          padding = '0 10px 0 0';
        }
        top = top > 0 ? top : 0;
        this.nodeTipsPanelPosition = {
          top: `${top}px`,
          left: `${left}px`,
          padding,
        };
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
      onDownloadCanvas() {
        this.onGenerateCanvas().then((res) => {
          if (this.canvasImgDownloading) {
            return;
          }
          this.canvasImgDownloading = true;
          const imgEl = document.createElement('a');
          imgEl.download = `bk_sops_template_${+new Date()}.png`;
          imgEl.href = res;
          imgEl.click();
          this.canvasImgDownloading = false;
        });
      },
      // 生成画布图片
      onGenerateCanvas() {
        const canvasFlWp = this.getNodeElement();
        const baseOffset = 200; // 节点宽度
        const xList = this.locations.map(node => node.x);
        const yList = this.locations.map(node => node.y);
        const minX = Math.min(...xList);
        const maxX = Math.max(...xList);
        const minY = Math.min(...yList);
        const maxY = Math.max(...yList);
        const offsetX = minX < 0 ? -minX : 0;
        const offsetY = minY < 0 ? -minY : 0;
        let width = null;
        const windowWidth = document.documentElement.offsetWidth - 60; // 60 header的宽度
        const windowHeight = document.documentElement.offsetHeight - 60 - 50; // 50 tab栏的宽度
        if (minX < 0) {
          width = maxX > windowWidth ? maxX - minX : windowWidth - minX;
        } else {
          width = maxX > windowWidth ? maxX : windowWidth;
        }
        let height = null;
        if (minY < 0) {
          height = maxY > windowHeight ? maxY - minY : windowHeight - minY;
        } else {
          height = maxY > windowHeight ? maxY : windowHeight;
        }
        const canvasHeight = height + baseOffset + 30;
        const canvasWidth = width + baseOffset + 80;
        return domtoimage.toJpeg(canvasFlWp, {
          bgcolor: '#ffffff',
          height: canvasHeight,
          width: canvasWidth,
          cloneBack: (clone) => {
            const svgCloneDom = clone.querySelector('.x6-graph-svg');
            svgCloneDom.style.width = `${canvasWidth}px`;
            svgCloneDom.style.height = `${canvasHeight}px`;
            const viewCloneDom = clone.querySelector('.x6-graph-svg-viewport');
            viewCloneDom.style.transform = `translate(${`${offsetX + 30}px`}, ${`${offsetY + 30}px`})`;
          },
        });
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
