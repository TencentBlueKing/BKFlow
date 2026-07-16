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
      @dragEnd="onNodeMoveStop"
      @onInnerNodeAdd="onInnerNodeAdd"
      @onInnerLineAdd="onInnerLineAdd" />
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
        @updateShortcutPanel="updateShortcutPanel"
        @onFitCanvas="adjustLoopGroupSize" />
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

  import { uuid, random4 } from '@/utils/uuid.js';

  // 快捷面板
  import ShortcutPanel from './components/shortcutPanel.vue';

  // 变量引用/执行记录面板
  import NodeTipsPanel from './components/nodeTipsPanel.vue';
  // 单选/框选
  import { Selection } from '@antv/x6-plugin-selection';
  import { Clipboard } from '@antv/x6-plugin-clipboard';

  import dom from '@/utils/dom.js';
  import { mapState, mapMutations } from 'vuex';
  import Vue from 'vue';
  import utilsTools from '@/utils/tools.js';
  import validatePipeline from '@/utils/validatePipeline.js';
  import domtoimage from '@/utils/domToImage.js';
  const gatewayTypes = ['branch-gateway', 'parallel-gateway', 'converge-gateway', 'conditional-parallel-gateway', 'branchgateway', 'parallelgateway', 'convergegateway', 'conditionalparallelgateway'];
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
        shortcutPanelCloseTimer: null,
        draggingNodeId: null, // 当前正在拖拽的节点ID
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
      if (this.shortcutPanelCloseTimer) {
        clearTimeout(this.shortcutPanelCloseTimer);
      }
    },
    methods: {
      ...mapMutations('template/', [
        'setActivities',
        'setGateways',
        'setLocation',
        'setLocationXY',
        'setLine',
      ]),
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
              });
            },
            validateEdge: this.handleValidateEdge,
          },
          interacting: {
            // 节点移动：resize 操作期间禁止拖拽移动，避免与 resize 手势冲突
            nodeMovable: (cellView) => {
              const node = cellView.cell || cellView;
              if (node && node.prop && node.prop('resizeHandling')) return false;
              return this.editable;
            },
            edgeLabelMovable: this.editable, // 边标签
            arrowheadMovable: this.editable, // 箭头
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
          embedding: { // 嵌套交互
            enabled: true,
            findParent({ node }) {
              // 排除容器节点自身（不允许分组嵌套分组）
              if (node.shape === 'custom-group-node' || node.shape === 'custom-loop-group-node') {
                return [];
              }
              // 禁止将分组外的开始节点和结束节点移入分组
              const nodeData = node.getData();
              if (nodeData && ['start', 'end'].includes(nodeData.type)) {
                const parent = node.getParent();
                if (!parent || !parent.isNode()) {
                  return [];
                }
              }
              const bbox = node.getBBox();
              return this.getNodes().filter((node) => {
                const data = node.getData();
                // 只有 data.parent 为 true 的节点才是父节点
                if (data && data.parent && typeof data.parent === 'boolean') {
                  const targetBBox = node.getBBox();
                  return bbox.isIntersectWithRect(targetBBox);
                }
                return false;
              });
            },
          },
          translating: { // 限制节点移动位置
            restrict(view) {
              const { cell } = view;
              if (cell.isNode()) {
                const parent = cell.getParent();
                // 只限制开始节点和结束，其他节点返回 null（不限制）
                if (parent && parent.isNode() && ['start', 'end'].includes(cell.getData()?.type)) {
                  return parent.getBBox();
                }
              }
              return null;
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
        registryEvents(this.graph, this.editable, {
          onContainerSizeChange: (parentNode) => {
            this.onLocationChange('edit', parentNode);
          },
        });
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
        // 节点从分组中脱离时执行清理（删除连线、更新 store）
        this.graph.on('node:change:parent', this.handleNodeChangeParent);
        // 节点添加时自动设置 z-index
        this.graph.on('node:added', ({ node }) => {
          this.updateNodeZIndex(node);
        });
      },
      initCanvasData() {
        if (!this.canvasData.length) return;
        const nodes = this.canvasData.filter(c => c.shape !== 'edge');
        //  保证父节点在子节点之前添加,否则parent关联会失效
        const sortedNodes = [
          ...nodes.filter(n => !n.parent),   // 无父节点的（包括 group 父节点）
          ...nodes.filter(n => n.parent),    // 有父节点的子节点
        ];
        // 1、先添加所有节点（不建立 embedding）
        const addedNodes = {};
        sortedNodes.forEach((node) => {
          const nodeConfig = { ...node };
          // 子节点确保使用绝对坐标（优先 position，其次 x/y）
          if (node.parent && typeof node.parent === 'string') {
            if (node.position) {
              nodeConfig.x = node.position.x;
              nodeConfig.y = node.position.y;
            }
            delete nodeConfig.position;
          }
          const addedNode = this.graph.addNode(nodeConfig);
          addedNodes[node.id] = addedNode;
        });
        // 2、显式建立 embedding 关系，使子节点跟随父节点移动
        sortedNodes.forEach((node) => {
          if (node.parent && typeof node.parent === 'string') {
            const parentNode = addedNodes[node.parent];
            if (parentNode && parentNode.isNode()) {
              parentNode.addChild(addedNodes[node.id]);
            }
          }
        });
        // 3、加载连线并建立 embedding 关系
        const edges = this.canvasData.filter(c => c.shape === 'edge');
        const addedEdges = {};
        edges.forEach((edge) => {
          const addedEdge = this.graph.addEdge({ ...edge });
          addedEdges[edge.id] = addedEdge;
        });
        edges.forEach((edge) => {
          if (edge.parent && typeof edge.parent === 'string') {
            const parentNode = addedNodes[edge.parent];
            if (parentNode && parentNode.isNode()) {
              parentNode.addChild(addedEdges[edge.id]);
            }
          }
        });
      },
      // 判断鼠标是否在当前激活的节点/边上
      isMouseOverActiveCell(e) {
        if (!this.activeCell) return false;
        if (this.activeCell.shape === 'edge') {
          return dom.parentClsContains('x6-edge', e.target);
        }
        if (this.activeCell.shape === 'custom-loop-group-node') {
          return dom.parentClsContains('loop-container-node', e.target);
        }
        // 普通节点或分组子节点
        const activeNodeDom = this.getNodeElement(`[data-cell-id="${this.activeCell.id}"] .custom-node`);
        if (activeNodeDom && (activeNodeDom.contains(e.target) || e.target === activeNodeDom)) {
          return true;
        }
        return false;
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
          const isOverActiveCell = this.isMouseOverActiveCell(e);
          const isOverPanel = dom.parentClsContains('shortcut-panel', e.target);
          if (!isOverActiveCell && !isOverPanel) {
            // 鼠标离开节点且未进入面板，延迟关闭
            if (!this.shortcutPanelCloseTimer) {
              this.shortcutPanelCloseTimer = setTimeout(() => {
                this.closeShortcutPanel();
              }, 200);
            }
          } else {
            // 鼠标在节点上或进入了面板，取消关闭定时器
            if (this.shortcutPanelCloseTimer) {
              clearTimeout(this.shortcutPanelCloseTimer);
              this.shortcutPanelCloseTimer = null;
            }
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
          // 循环流分组节点根元素是 .loop-container-node，普通节点是 .custom-node
          const selector = cell.shape === 'custom-loop-group-node'
            ? `[data-cell-id="${cell.id}"]`
            : `[data-cell-id="${cell.id}"] .custom-node`;
          const nodeDom = this.getNodeElement(selector);
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
        if (this.shortcutPanelCloseTimer) {
          clearTimeout(this.shortcutPanelCloseTimer);
          this.shortcutPanelCloseTimer = null;
        }
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
        // 拖拽时临时提高外部节点的 z-index，避免被循环流容器遮挡
        if (this.draggingNodeId !== node.id) {
          this.draggingNodeId = node.id;
          if (!node.getParent() && node.shape !== 'custom-loop-group-node') {
            node.setZIndex(20);
          }
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
        // 恢复节点的 z-index（根据节点类型和父节点重新计算）
        this.updateNodeZIndex(node);
        // 清除拖拽标志位
        this.draggingNodeId = null;
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
      // 节点父子关系发生变化（node:change:parent驱动）
      handleNodeChangeParent({ node, current, previous }) {
        if (this.graph && this.graph.isResetting) return;
        const nodeData = node.getData();
        if (!nodeData) return;
        const nodeType = nodeData.type;
        const isBusinessNode = ['task', 'subflow'].includes(nodeType) || gatewayTypes.includes(nodeType);
        const nodeId = node.id;
        const isNodeRegistered = this.locations && this.locations.some(loc => loc.id === nodeId);
        // 检查节点是否在某个loop的嵌套pipeline中
        const isInPipelineTree = !isNodeRegistered && this.findNodeInPipelineTree(nodeId, previous);
        const shouldProcess = isNodeRegistered || isInPipelineTree;
        // 情况1：节点从分组中脱离
        if (!current && previous) {
          if (typeof nodeData.parent !== 'string') return;
          if (nodeData.parent !== previous) return;
          node.removeProp('data/parent');
          if (shouldProcess) {
            // 断开跨分组连线
            const connectedEdges = this.graph.getConnectedEdges(nodeId);
            connectedEdges.forEach((edge) => {
              const sourceId = edge.getSourceCellId();
              const targetId = edge.getTargetCellId();
              const otherNodeId = sourceId === nodeId ? targetId : sourceId;
              const otherNode = this.getNodeInstance(otherNodeId);
              if (otherNode && otherNode.getParent()?.id === previous) {
                this.graph.removeEdge(edge.id);
                this.onLineChange('delete', {
                  id: edge.id,
                  source: { cell: sourceId },
                  target: { cell: targetId },
                });
              }
            });
            // 节点不再属于任何loop，从pipeline中移除并添加到外层 store
            if (isBusinessNode) {
              if (isInPipelineTree) {
                this.moveNodeOutOfLoop(nodeId, previous);
              } else {
                this.removeFromPipelineTree(nodeId, previous);
              }
            }
            const nodeInstance = this.getNodeInstance(nodeId);
            this.onLocationChange('edit', nodeInstance);
          }
          // 更新节点和相连连线的z-index
          this.updateNodeZIndex(node);
          const connectedEdgesAfterLeave = this.graph.getConnectedEdges(node.id);
          connectedEdgesAfterLeave.forEach((edge) => {
            this.updateEdgeZIndex(edge);
          });
          return;
        }
        // 情况2：节点移入新分组
        if (current && typeof current === 'string') {
          node.setData({ ...nodeData, parent: current });
          // 更新节点 z-index
          this.updateNodeZIndex(node);
          if (isNodeRegistered) {
            // 断开跨分组连线
            const connectedEdges = this.graph.getConnectedEdges(nodeId);
            connectedEdges.forEach((edge) => {
              const sourceId = edge.getSourceCellId();
              const targetId = edge.getTargetCellId();
              const otherNodeId = sourceId === nodeId ? targetId : sourceId;
              const otherNode = this.getNodeInstance(otherNodeId);
              const otherParent = otherNode?.getParent?.()?.id;
              if (!otherParent || otherParent !== current) {
                this.graph.removeEdge(edge.id);
                this.onLineChange('delete', {
                  id: edge.id,
                  source: { cell: sourceId },
                  target: { cell: targetId },
                });
              }
            });
            if (isBusinessNode) {
              this.onInnerNodeAdd(nodeId, current);
              this.cleanupOuterNodeFromStore(nodeId);
            }
            // 同步整个分组的节点和边数据到 pipelineTree（包含刚移入的节点）
            this.syncLoopGroupInnerNodes(current);
            const nodeInstance = this.getNodeInstance(nodeId);
            this.onLocationChange('edit', nodeInstance);
          }
          // 更新相连连线的 z-index
          const connectedEdgesAfterEnter = this.graph.getConnectedEdges(node.id);
          connectedEdgesAfterEnter.forEach((edge) => {
            this.updateEdgeZIndex(edge);
          });
        }
      },
      // 从 nested pipeline 中移除节点
      removeFromPipelineTree(nodeId, parentLoopId) {
        const loopActivity = this.activities[parentLoopId];
        if (!loopActivity || !loopActivity.pipeline) return;
        const pt = loopActivity.pipeline;
        // 从 activities 中移除
        if (pt.activities && pt.activities[nodeId]) {
          delete pt.activities[nodeId];
        }
        // 从 gateways 中移除
        if (pt.gateways && pt.gateways[nodeId]) {
          const deletedGw = pt.gateways[nodeId];
          // 如果删除的是汇聚网关，清除其他网关对该汇聚网关的 converge_gateway_id 引用
          if (deletedGw.type === 'ConvergeGateway') {
            Object.values(pt.gateways).forEach((gw) => {
              if (gw.converge_gateway_id === nodeId) {
                gw.converge_gateway_id = '';
              }
            });
          }
          delete pt.gateways[nodeId];
        }
        // 从location中移除
        if (pt.location) {
          pt.location = pt.location.filter(l => l.id !== nodeId);
        }
        // 清理相关的flows和line
        if (pt.flows) {
          const removedFlowIds = [];
          Object.entries(pt.flows).forEach(([flowId, flow]) => {
            if (flow.source === nodeId || flow.target === nodeId) {
              removedFlowIds.push(flowId);
            }
          });
          removedFlowIds.forEach(fid => delete pt.flows[fid]);
        }
        if (pt.line) {
          pt.line = pt.line.filter(l => l.source.id !== nodeId && l.target.id !== nodeId);
        }
      },
      // 检查节点是否在指定 loop 的嵌套 pipeline 中
      findNodeInPipelineTree(nodeId, parentLoopId) {
        const loopActivity = this.activities[parentLoopId];
        if (!loopActivity || !loopActivity.pipeline) return false;
        const pt = loopActivity.pipeline;
        if (pt.activities && pt.activities[nodeId]) return true;
        if (pt.gateways && pt.gateways[nodeId]) return true;
        if (pt.start_event && pt.start_event.id === nodeId) return true;
        if (pt.end_event && pt.end_event.id === nodeId) return true;
        if (pt.location && pt.location.some(l => l.id === nodeId)) return true;
        return false;
      },
      // 将节点从嵌套 pipeline 移到外层 store（节点从循环容器拖出时调用）
      moveNodeOutOfLoop(nodeId, parentLoopId) {
        const loopActivity = this.activities[parentLoopId];
        if (!loopActivity || !loopActivity.pipeline) return;
        const pt = loopActivity.pipeline;
        // 1. 从 pipeline 中提取数据
        const activityData = pt.activities?.[nodeId];
        const gatewayData = pt.gateways?.[nodeId];
        const locationData = pt.location?.find(l => l.id === nodeId);
        // 2. 从 pipeline 中移除
        this.removeFromPipelineTree(nodeId, parentLoopId);
        // 3. 将数据写回外层store
        if (activityData) {
          const cleanActivity = { ...activityData };
          delete cleanActivity.parent; // 移除parent字段
          cleanActivity.incoming = [];
          cleanActivity.outgoing = '';
          this.setActivities({ type: 'edit', location: cleanActivity });
        }
        if (gatewayData) {
          const cleanGateway = { ...gatewayData };
          delete cleanGateway.parent;
          cleanGateway.incoming = Array.isArray(cleanGateway.incoming) ? [] : [];
          cleanGateway.outgoing = cleanGateway.type === 'ConvergeGateway' ? '' : [];
          this.setGateways({ type: 'edit', location: cleanGateway });
        }
        if (locationData) {
          const cleanLocation = { ...locationData };
          delete cleanLocation.parent;
          this.setLocation({ type: 'add', location: cleanLocation });
        }
        // 4. 重新计算内部 pipeline 的 incoming/outgoing
        this.recalcInnerPipelineInOut(pt);
      },
      // 节点从外层画布移入分组后，清理外层中的残留数据
      cleanupOuterNodeFromStore(nodeId) {
        const state = this.$store.state.template;
        if (!state) return;
        const locIdx = state.location.findIndex(l => l.id === nodeId);
        if (locIdx >= 0) {
          this.setLocation({ type: 'delete', location: { id: nodeId } });
        }
        if (state.activities[nodeId]) {
          this.setActivities({ type: 'delete', location: { id: nodeId } });
        }
        if (state.gateways && state.gateways[nodeId]) {
          const gwInfo = state.gateways[nodeId];
          this.setGateways({
            type: 'delete',
            location: {
              id: nodeId,
              type: gwInfo.type === 'ConvergeGateway' ? 'convergegateway' : '',
            },
          });
        }
        const flowIdsToDelete = [];
        Object.entries(state.flows).forEach(([flowId, flow]) => {
          if (flow.source === nodeId || flow.target === nodeId) {
            flowIdsToDelete.push(flowId);
          }
        });
        flowIdsToDelete.forEach((fid) => {
          this.setLine({ type: 'delete', line: { id: fid } });
        });
      },
      // 同步循环容器内部子节点到store的嵌套pipelineTree
      syncLoopGroupInnerNodes(nodeId) {
        const nodeInstance = this.getNodeInstance(nodeId);
        if (!nodeInstance || nodeInstance.shape !== 'custom-loop-group-node') return;
        let loopActivity = this.activities[nodeId];
        if (!loopActivity) return;
        if (!loopActivity.pipeline) {
          this.setActivities({
            type: 'edit',
            location: {
              ...loopActivity,
              pipeline: {
                activities: {},
                constants: {},
                flows: {},
                gateways: {},
                line: [],
                location: [],
                start_event: {},
                end_event: {},
                outputs: [],
              },
            },
          });
          // 重新获取更新后的activity
          loopActivity = this.activities[nodeId];
        }
        const pt = loopActivity.pipeline;
        // 遍历graph中所有节点，找出parent指向当前SubCanvas的子节点
        const allNodes = this.graph.getNodes();
        const childNodes = allNodes.filter((n) => {
          const d = n.getData();
          return d && d.parent === nodeId;
        });
        childNodes.forEach((child) => {
          const childData = child.getData();
          if (!childData) return;
          // 同步子节点到 pipeline
          this.onInnerNodeAdd(child.id, nodeId);
        });
        // 同步组内边数据到pipeline.flows和pipeline.line
        const childNodeIds = childNodes.map(n => n.id);
        const allEdges = this.graph.getEdges();
        // 清理 pipeline 中已被X6删除的过期flows/lines
        const x6EdgeIds = new Set(allEdges.map(e => e.id));
        Object.keys(pt.flows).forEach((flowId) => {
          if (!x6EdgeIds.has(flowId)) {
            delete pt.flows[flowId];
          }
        });
        if (pt.line) {
          pt.line = pt.line.filter(l => x6EdgeIds.has(l.id));
        }
        allEdges.forEach((edge) => {
          const sourceCell = edge.getSourceCellId();
          const targetCell = edge.getTargetCellId();
          const isInnerEdge = childNodeIds.includes(sourceCell) || sourceCell === nodeId;
          const isInnerEdge2 = childNodeIds.includes(targetCell) || targetCell === nodeId;
          if (isInnerEdge && isInnerEdge2) {
            this.onInnerLineAdd({
              id: edge.id,
              source: edge.getSource(),
              target: edge.getTarget(),
            }, nodeId);
          }
        });
        // 根据最新的pt.flows全量重建所有节点的 incoming/outgoing（覆盖增量同步可能遗留的脏数据）
        this.recalcInnerPipelineInOut(pt);
      },
      // 处理组内节点数据同步（写入嵌套 pipelineTree）
      onInnerNodeAdd(nodeId, parentLoopId = null) {
        const nodeInstance = this.getNodeInstance(nodeId);
        if (!nodeInstance) return;
        // 查找父 SubCanvas
        const parentNode = parentLoopId
          ? this.activities[parentLoopId]
          : this.getLoopParentByChildId(nodeId);
        if (!parentNode || !parentNode.pipeline) {
          // 如果父节点尚未初始化 pipeline，先通过 syncLoopGroupInnerNodes 初始化
          this.onLocationChange('add', nodeInstance, true);
          return;
        }
        const pt = parentNode.pipeline;
        const childData = nodeInstance.getData();
        const nodeType = childData ? childData.type : '';
        const normalizedType = typeof nodeType === 'string' ? nodeType.toLowerCase() : '';
        const typeMap = {
          start: 'startpoint',
          end: 'endpoint',
          task: 'tasknode',
          subflow: 'subflow',
          'branch-gateway': 'branchgateway',
          'parallel-gateway': 'parallelgateway',
          'conditional-parallel-gateway': 'conditionalparallelgateway',
          'converge-gateway': 'convergegateway',
        };
        const savedType = typeMap[normalizedType] ?? normalizedType.split('-').join('');
        // 同步 location（使用绝对坐标，与 onLocationMoveDone 保持一致）
        const pos = nodeInstance.getPosition({ relative: false });
        const loc = {
          id: nodeId,
          type: savedType,
          name: (childData && childData.name) || '',
          x: pos.x,
          y: pos.y,
          parent: parentNode.id,
        };
        // 存入 pipeline.location
        const existingLocIdx = pt.location.findIndex(l => l.id === nodeId);
        if (existingLocIdx >= 0) {
          pt.location[existingLocIdx] = loc;
        } else {
          pt.location.push(loc);
        }
        // 同步 activities/gateways/events 到 pipeline
        if (['tasknode', 'subflow'].includes(savedType)) {
          // 优先从外层 store 获取，若已清理则从 pipeline 中查找已有数据（避免覆盖已同步的完整数据）
          const existingActivity = this.activities[nodeId] || (pt.activities && pt.activities[nodeId]);
          if (existingActivity) {
            pt.activities[nodeId] = { ...existingActivity, parent: parentNode.id };
          } else {
          // 初始子节点（如 initLoopContainerContent 创建的默认节点）尚未在顶层 store 中注册
            const isSubflow = nodeType === 'subflow';
            pt.activities[nodeId] = {
              id: nodeId,
              type: isSubflow ? 'SubProcess' : 'ServiceActivity',
              name: childData.name || '',
              incoming: [],
              outgoing: '',
              optional: true,
              error_ignorable: false,
              retryable: true,
              skippable: true,
              loop: null,
              stage_name: '',
              parent: parentNode.id,
              ...(isSubflow ? {
                constants: {},
                hooked_constants: [],
                template_id: childData.templateId || '',
                version: childData.templateVersion || 'latest',
                always_use_latest: false,
                scheme_id_list: [],
                template_source: childData.tplSource || 'business',
              } : {
                component: {
                  code: childData.atomId || '',
                  data: childData.atom_data || {},
                  version: childData.version || 'legacy',
                },
              }),
            };
          }
        } else if (savedType === 'startpoint') {
          pt.start_event = {
            id: nodeId,
            type: 'EmptyStartEvent',
            incoming: '',
            outgoing: '',
            name: childData ? childData.name || '' : '',
          };
        } else if (savedType === 'endpoint') {
          pt.end_event = {
            id: nodeId,
            type: 'EmptyEndEvent',
            incoming: '',
            outgoing: '',
            name: childData ? childData.name || '' : '',
          };
        } else if (['branchgateway', 'parallelgateway', 'convergegateway', 'conditionalparallelgateway'].includes(savedType)) {
          const ATOM_TYPE_DICT = {
            branchgateway: 'ExclusiveGateway',
            parallelgateway: 'ParallelGateway',
            convergegateway: 'ConvergeGateway',
            conditionalparallelgateway: 'ConditionalParallelGateway',
          };
          const existingGateway = this.gateways[nodeId];
          if (existingGateway) {
            pt.gateways[nodeId] = { ...existingGateway, parent: parentNode.id };
          } else {
            // 回退创建：外层store尚未注册该网关时，
            // 在 pipeline 中创建默认网关数据
            const gatewayType = ATOM_TYPE_DICT[savedType];
            const isConverge = gatewayType === 'ConvergeGateway';
            const isBranch = gatewayType === 'ExclusiveGateway' || gatewayType === 'ConditionalParallelGateway';
            pt.gateways[nodeId] = {
              id: nodeId,
              incoming: [],
              name: childData ? childData.name || '' : '',
              outgoing: isConverge ? '' : [],
              type: gatewayType,
              ...(isBranch ? { conditions: {} } : {}),
              ...(!isConverge ? { converge_gateway_id: (childData && childData.convergeGatewayId) || '' } : {}),
              parent: parentNode.id,
            };
          }
        }
        this.$emit('templateDataChanged');
      },
      // 查找某个child所属的SubCanvas
      getLoopParentByChildId(childNodeId) {
        return Object.values(this.activities).find((act) => {
          if (act.type !== 'SubCanvas' || !act.pipeline) return false;
          const pt = act.pipeline;
          return !!(pt.activities && pt.activities[childNodeId])
            || !!(pt.gateways && pt.gateways[childNodeId])
            || (pt.start_event && pt.start_event.id === childNodeId)
            || (pt.end_event && pt.end_event.id === childNodeId);
        });
      },
      // 处理组内连线数据同步
      onInnerLineAdd({ id, source, target }, parentLoopId = null) {
        const sourceCellId = typeof source === 'string' ? source : source.cell;
        const targetCellId = typeof target === 'string' ? target : target.cell;
        // 查找父 SubCanvas
        const parentNode = parentLoopId
          ? this.activities[parentLoopId]
          : (this.getLoopParentByChildId(sourceCellId) || this.getLoopParentByChildId(targetCellId));
        if (!parentNode || !parentNode.pipeline) return;
        const pt = parentNode.pipeline;
        pt.flows[id] = {
          id,
          is_default: false,
          source: sourceCellId,
          target: targetCellId,
        };
        if (!pt.line.find(l => l.id === id)) {
          pt.line.push({
            id,
            source: {
              id: sourceCellId,
              arrow: source.port ? source.port.split('_')[1].charAt(0).toUpperCase() + source.port.split('_')[1].slice(1) : 'Right',
            },
            target: {
              id: targetCellId,
              arrow: target.port ? target.port.split('_')[1].charAt(0).toUpperCase() + target.port.split('_')[1].slice(1) : 'Left',
            },
          });
        }
        // 更新 pipeline 中 start_event/end_event/activities/gateways 的 outgoing/incoming
        if (pt.start_event && pt.start_event.id === sourceCellId) {
          pt.start_event.outgoing = id;
        }
        if (pt.activities && pt.activities[sourceCellId]) {
          pt.activities[sourceCellId].outgoing = id;
        }
        if (pt.gateways && pt.gateways[sourceCellId]) {
          const gw = pt.gateways[sourceCellId];
          if (Array.isArray(gw.outgoing)) {
            if (!gw.outgoing.includes(id)) gw.outgoing.push(id);
          } else {
            gw.outgoing = id;
          }
          // 分支网关/条件并行网关：自动生成默认条件
          if (gw.type === 'ExclusiveGateway' || gw.type === 'ConditionalParallelGateway') {
            if (!gw.conditions) gw.conditions = {};
            const { conditions } = gw;
            // 已有该连线的条件则跳过（重连场景保留原条件）
            if (conditions[id]) return;
            const defaultName = this.$t('条件');
            const regStr = `^${defaultName}[0-9]*$`;
            const reg = new RegExp(regStr);
            let maxCount = 0;
            Object.values(conditions).forEach((item) => {
              if (reg.test(item.name)) {
                const count = Number(item.name.split(defaultName)[1]);
                if (count > maxCount) maxCount = count;
              }
            });
            const name = defaultName + (maxCount + 1);
            const evaluate = Object.keys(conditions).length ? '1 == 0' : '1 == 1';
            Vue.set(conditions, id, {
              evaluate,
              name,
              tag: `branch_${sourceCellId}_${targetCellId}`,
            });
          }
        }
        if (pt.end_event && pt.end_event.id === targetCellId) {
          pt.end_event.incoming = Array.isArray(pt.end_event.incoming)
            ? [...pt.end_event.incoming, id]
            : (pt.end_event.incoming ? [pt.end_event.incoming, id] : [id]);
        }
        if (pt.activities && pt.activities[targetCellId]) {
          const { incoming } = pt.activities[targetCellId];
          pt.activities[targetCellId].incoming = Array.isArray(incoming)
            ? [...incoming, id]
            : (incoming ? [incoming, id] : [id]);
        }
        if (pt.gateways && pt.gateways[targetCellId]) {
          const gwIncoming = pt.gateways[targetCellId].incoming;
          pt.gateways[targetCellId].incoming = Array.isArray(gwIncoming)
            ? [...gwIncoming, id]
            : (gwIncoming ? [gwIncoming, id] : [id]);
        }
      },
      // 从 pipeline 中删除一条内部连线（用于内部连线重连场景）
      deleteInnerLine(lineId, parentLoopId) {
        const loopActivity = this.activities[parentLoopId];
        if (!loopActivity || !loopActivity.pipeline) return;
        const pt = loopActivity.pipeline;
        // 删除 flows
        delete pt.flows[lineId];
        // 删除 line
        const lineIndex = pt.line?.findIndex(l => l.id === lineId);
        if (lineIndex !== -1) {
          pt.line.splice(lineIndex, 1);
        }
        // 删除分支网关中对应的 condition
        if (pt.gateways) {
          Object.values(pt.gateways).forEach((gw) => {
            if (gw.conditions && gw.conditions[lineId]) {
              Vue.delete(gw.conditions, lineId);
            }
          });
        }
        // 重建incoming/outgoing
        this.recalcInnerPipelineInOut(pt);
      },
      // 根据 pipelines_tree.flows 全量重建所有节点的 incoming/outgoing
      // 在 syncLoopGroupInnerNodes 末尾调用，确保连线增/删后数据一致
      recalcInnerPipelineInOut(pt) {
        if (!pt || !pt.flows) return;
        // 重置所有节点的 incoming/outgoing
        if (pt.activities) {
          Object.values(pt.activities).forEach((act) => {
            act.incoming = [];
            act.outgoing = '';
          });
        }
        if (pt.gateways) {
          Object.values(pt.gateways).forEach((gw) => {
            gw.incoming = [];
            gw.outgoing = gw.type === 'ConvergeGateway' ? '' : [];
          });
        }
        if (pt.start_event) {
          pt.start_event.outgoing = '';
        }
        if (pt.end_event) {
          pt.end_event.incoming = [];
        }
        // 根据 flows 重新计算
        const flowIds = new Set(Object.keys(pt.flows));
        Object.values(pt.flows).forEach((flow) => {
          const { id, source, target } = flow;
          // 更新 source 的 outgoing
          if (pt.start_event && pt.start_event.id === source) {
            pt.start_event.outgoing = id;
          } else if (pt.activities && pt.activities[source]) {
            pt.activities[source].outgoing = id;
          } else if (pt.gateways && pt.gateways[source]) {
            const gw = pt.gateways[source];
            if (gw.type === 'ConvergeGateway') {
              gw.outgoing = id;
            } else {
              if (!Array.isArray(gw.outgoing)) gw.outgoing = [];
              if (!gw.outgoing.includes(id)) gw.outgoing.push(id);
            }
          }
          // 更新 target 的 incoming
          if (pt.end_event && pt.end_event.id === target) {
            if (!Array.isArray(pt.end_event.incoming)) pt.end_event.incoming = [];
            if (!pt.end_event.incoming.includes(id)) pt.end_event.incoming.push(id);
          } else if (pt.activities && pt.activities[target]) {
            if (!Array.isArray(pt.activities[target].incoming)) pt.activities[target].incoming = [];
            if (!pt.activities[target].incoming.includes(id)) pt.activities[target].incoming.push(id);
          } else if (pt.gateways && pt.gateways[target]) {
            if (!Array.isArray(pt.gateways[target].incoming)) pt.gateways[target].incoming = [];
            if (!pt.gateways[target].incoming.includes(id)) pt.gateways[target].incoming.push(id);
          }
        });
        // 清理分支网关中不再存在的 outgoing 连线对应的 condition
        if (pt.gateways) {
          Object.values(pt.gateways).forEach((gw) => {
            if (gw.conditions && Object.keys(gw.conditions).length > 0) {
              Object.keys(gw.conditions).forEach((condLineId) => {
                if (!flowIds.has(condLineId)) {
                  Vue.delete(gw.conditions, condLineId);
                }
              });
            }
          });
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
          if (x6ViewDom) {
            const transform = x6ViewDom.getAttribute('transform');
            if (transform) {
              const offset = transform
                .slice(7, -1)
                .split(',')
                .slice(-2);
              offsetLeft = Number(offset[0]);
              offsetTop = Number(offset[1]);
            }
          }
          // 节点坐标（拖拽过程中 DOM 可能尚未渲染，需要安全检查）
          const nodeCellDom = this.getNodeElement(`g[data-cell-id="${node.id}"]`);
          const canvasDom = this.getNodeElement();
          if (nodeCellDom && canvasDom) {
            const customNode = nodeCellDom.querySelector('.custom-node');
            if (customNode) {
              const { top, left } = customNode.getBoundingClientRect();
              const { left: canvasLeft, top: canvasTop } = canvasDom.getBoundingClientRect();
              const ratio = this.graph.zoom();
              location.x = (left - canvasLeft - offsetLeft) / ratio;
              location.y = (top - canvasTop - offsetTop) / ratio;
            }
          }
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
          if (parentDom) {
            const pointDoms = parentDom.querySelectorAll('.node-inset-line-point');
            if (pointDoms.length) {
              Array.from(pointDoms).forEach((pointDomItem) => {
                parentDom.removeChild(pointDomItem);
              });
            }
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
        // 如果被断开的连线在分组内，将新节点也加入该分组
        const targetNode = this.getNodeInstance(target.cell);
        const sourceNode = this.getNodeInstance(source.cell);
        const parentNode = targetNode?.getParent?.() || sourceNode?.getParent?.();
        const isInnerLine = parentNode && this.activities[parentNode.id]?.type === 'SubCanvas';
        if (parentNode && !nodeInstance.getParent()) {
          parentNode.addChild(nodeInstance);
        }
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
        if (isInnerLine) {
          // 循环容器内部连线：直接清理 pipeline 中的旧边数据
          this.deleteInnerLine(lineId, parentNode.id);
        } else {
          this.onLineChange('delete', values);
        }
        this.$nextTick(() => {
          // 循环容器内部连线：不触发onLineChange（避免污染外层store），通过syncLoopGroupInnerNodes同步到pipeline
          this.createEdge(startLine, isInnerLine);
          this.createEdge(endLine, isInnerLine);
          if (isInnerLine) {
            this.syncLoopGroupInnerNodes(parentNode.id);
          }
        });
        this.matchLines = {};
        // 删除节点两端插入连线的端点
        const nodeDom = this.getNodeElement(`[data-cell-id=${location.id}] .custom-node`);
        if (nodeDom) {
          const pointDoms = nodeDom.querySelectorAll('.node-inset-line-point');
          if (pointDoms.length) {
            Array.from(pointDoms).forEach((pointDomItem) => {
              nodeDom.removeChild(pointDomItem);
            });
          }
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
      createEdge({ source, target, data = {}, router = {} }, skipSync = false) {
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
          router: Object.assign({
            name: 'manhattan',
            args: {
              padding: 1,
            },
          }, router),
        });
        if (!skipSync) {
          this.onLineChange('add', {
            id: edgeId,
            source,
            target,
            data,
          });
        }
      },
      // 节点删除
      onNodeRemove(node, remove = this) {
        if (node.data && node.data.isProtected && remove) {
          this.$bkMessage({
            message: this.$t('循环节点的开始/结束节点不可删除'),
            theme: 'warning',
          });
          return;
        }
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
        // 如果是分组节点，先删除所有子节点
          if (node.shape === 'custom-loop-group-node') {
            // 先获取并删除外层连线（顶层 flows/line），避免 removeNode 后 getConnectedEdges 取不到
            const outerEdges = this.graph.getConnectedEdges(node);
            outerEdges.forEach((edge) => {
              const source = edge.getSource();
              const target = edge.getTarget();
              this.onLineChange('delete', {
                id: edge.id,
                source: { cell: source.cell },
                target: { cell: target.cell },
              });
              this.graph.removeEdge(edge.id);
            });
            const children = node.getChildren() || [];
            this.setActivities({ type: 'delete', location: { id: node.id } });
            this.setLocation({ type: 'delete', location: { id: node.id } });
            children.forEach((child) => {
              node.removeChild(child);
              this.graph.removeNode(child.id);
            });
            this.graph.removeNode(node.id);
            this.onLocationChange('delete', node, false);
          } else {
            // 如果是组内子节点，先捕获父节点信息
            const parent = node.getParent();
            const parentId = parent ? parent.id : undefined;
            const isGroupInner = !!parentId;
            if (parentId && isGroupInner) {
              this.removeFromPipelineTree(node.id, parentId);
            }
            if (parent && parent.isNode()) {
              parent.removeChild(node);
            }
            this.graph.removeNode(node.id);
            this.onLocationChange('delete', node, isGroupInner, parentId);
          }
        } else { // 解除连线
          const nodeInstance = this.getNodeInstance(node.id);
          this.graph.select(nodeInstance);
        }
        // 删除节点两端旧的连线-获取节点在画布上的实际连线（包括分组子节点的内嵌连线）
        const connectedEdges = this.graph.getConnectedEdges(node.id);
        connectedEdges.forEach((edge) => {
          const edgeId = edge.id;
          const source = edge.getSource();
          const target = edge.getTarget();
          const parentNode = node.getParent();
          const isInnerLine = parentNode && this.activities[parentNode.id]?.type === 'SubCanvas';
          if (isInnerLine) {
            // 分组子节点的连线：从内嵌pipeline中删除
            this.deleteInnerLine(edgeId, parentNode.id);
          } else {
            // 外层节点的连线：从外层store中删除
            this.onLineChange('delete', {
              id: edgeId,
              source: { cell: source.cell },
              target: { cell: target.cell },
            });
          }
          this.graph.removeEdge(edgeId);
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
        // 兼容 source/target 为字符串（cell ID）或对象的情况
        const sourcePort = typeof source === 'string' ? '' : (source.port || '');
        const targetPort = typeof target === 'string' ? '' : (target.port || '');
        const sourceArrow = sourcePort.split('_')[1] || '';
        const targetArrow = targetPort.split('_')[1] || '';
        // 检测连线两端是否都在同一个循环容器内部
        const sourceNodeInstance = this.getNodeInstance(source.cell);
        const targetNodeInstance = this.getNodeInstance(target.cell);
        const sourceParent = sourceNodeInstance?.getParent?.();
        const targetParent = targetNodeInstance?.getParent?.();
        const sameLoopParent = sourceParent?.id && targetParent?.id
          && sourceParent.id === targetParent.id
          && this.activities[sourceParent.id]?.type === 'SubCanvas';
        // 分组内的节点禁止与分组外的节点互连
        if (!sameLoopParent) {
          const sourceInLoop = sourceParent?.id && this.activities[sourceParent.id]?.type === 'SubCanvas';
          const targetInLoop = targetParent?.id && this.activities[targetParent.id]?.type === 'SubCanvas';
          if (sourceInLoop || targetInLoop) {
            // 检查是否是一端为 SubCanvas 自身的情况（loopGroupNode 可以和其子节点连线）
            const sourceData = sourceNodeInstance?.getData?.();
            const targetData = targetNodeInstance?.getData?.();
            const sourceIsGroupSelf = sourceData?.type === 'SubCanvas' && sourceData?.parent === true;
            const targetIsGroupSelf = targetData?.type === 'SubCanvas' && targetData?.parent === true;
            const isGroupToChild = (sourceInLoop && targetIsGroupSelf && targetNodeInstance?.id === sourceParent.id)
                                || (targetInLoop && sourceIsGroupSelf && sourceNodeInstance?.id === targetParent.id);
            if (!isGroupToChild) {
              this.$bkMessage({
                message: this.$t('循环内的节点不能与循环外的节点连线'),
                theme: 'warning',
              });
              return false;
            }
          }
        }
        // 循环容器内部连线时，使用内层 pipeline 的 location 和 line 数据，
        // 并将内层类型名映射为 NODE_RULE 可识别的外层类型名
        const innerToOuterTypeMap = {
          start: 'startpoint',
          end: 'endpoint',
          task: 'tasknode',
          subflow: 'subflow',
          'branch-gateway': 'branchgateway',
          'parallel-gateway': 'parallelgateway',
          'conditional-parallel-gateway': 'conditionalparallelgateway',
          'converge-gateway': 'convergegateway',
          SubCanvas: 'SubCanvas',
        };
        let validateLines;
        let validateLocations;
        if (sameLoopParent) {
          const pt = this.activities[sourceParent.id]?.['pipeline'];
          validateLines = pt ? pt.line.filter(l => l.id !== edge.id) : [];
          validateLocations = pt
            ? pt.location.map(loc => ({ ...loc, type: innerToOuterTypeMap[loc.type] || loc.type }))
            : [];
        } else {
          validateLines = lines;
          validateLocations = this.locations;
        }
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
          lines: validateLines,
          locations: validateLocations,
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
            // 内部连线重连：删除旧连线时需清理 pipeline 中的旧数据
            if (sameLoopParent) {
              this.deleteInnerLine(id, sourceParent.id);
            } else {
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
            }
            this.createEdge({
              source,
              target,
              data: {
                ...edge.data,
                conditionInfo,
              },
            }, sameLoopParent);
            // 内部连线重连后同步 pipeline
            if (sameLoopParent) {
              this.syncLoopGroupInnerNodes(sourceParent.id);
            }
            // 更新节点activities输入输出
          } else {
            if (sameLoopParent) {
              // 循环容器内部连线：只写入 pipeline，不写外层 store
              this.onInnerLineAdd({ id: edge.id, source, target }, sourceParent.id);
              this.handleEdgeAdded({ cell: edge });
            } else {
              const line = { id: edge.id, source, target };
              this.$emit('onLineChange', 'add', line);
              this.handleEdgeAdded({ cell: edge });
            }
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
          const supportSelect = (shape === 'custom-node' || shape === 'custom-loop-group-node')
            && !['start', 'end'].includes(data.type);
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
          // 避免双击同一节点时再次触发单击
          if (this.showShortcutPanel && this.activeCell && this.activeCell.id === cell.id) {
            return;
          }
          // 点击了不同节点，先关闭当前面板
          if (this.showShortcutPanel && this.activeCell && this.activeCell.id !== cell.id) {
            this.closeShortcutPanel();
          }
          // 展开节点配置面板
          this.openShortcutPanel({ cell, e });
        } else if (cell.shape === 'custom-node' || cell.shape === 'custom-loop-group-node') {
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
      // 更新节点 z-index（根据节点类型和父节点）
      updateNodeZIndex(node) {
        if (node.shape === 'custom-loop-group-node') {
          node.setZIndex(10); // 循环流容器
        } else if (node.getParent()) {
          // 节点在循环流内部（高于容器内连线，最高层）
          const parent = node.getParent();
          const parentZIndex = parent.getZIndex() || 10;
          node.setZIndex(parentZIndex + 2); // 内部子节点 > 内部连线
        } else {
          node.setZIndex(5); // 外部节点
        }
      },
      // 更新连线 z-index（根据连线两端的节点是否在循环流内）
      updateEdgeZIndex(edge) {
        const sourceNode = this.graph.getCellById(edge.getSourceCellId());
        const targetNode = this.graph.getCellById(edge.getTargetCellId());
        if (!sourceNode || !targetNode) return;
        const sourceParent = sourceNode.getParent?.();
        const targetParent = targetNode.getParent?.();

        if (sourceParent && targetParent && sourceParent.id === targetParent.id) {
          // 连线在循环流内部（高于容器，低于内部子节点）
          const parentZIndex = sourceParent.getZIndex() || 10;
          edge.setZIndex(parentZIndex + 1); // 内部连线 > 容器
        } else {
          // 外部连线
          edge.setZIndex(2);
        }
      },
      // 监听画布添加连线
      handleEdgeAdded({ cell }) {
        // 设置连线 z-index
        this.updateEdgeZIndex(cell);
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
        // 先从外层 store.gateways 查找
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
        // 外层未找到条件数据时，从 SubCanvas的pipeline.gateways中查找
        if (!Object.keys(branchConditions).length) {
          Object.values(this.activities).forEach((act) => {
            const isSubCanvas = act.type === 'SubCanvas' || (act.component && act.component.code === 'subcanvas_plugin');
            if (!isSubCanvas) return;
            if (!act.pipeline || !act.pipeline.gateways) return;
            const pipelineGateways = act.pipeline.gateways;
            // 优先通过key匹配，回退通过gw.id遍历匹配
            let gw = pipelineGateways[gatewayId];
            if (!gw) {
              Object.keys(pipelineGateways).some((pgKey) => {
                if (pipelineGateways[pgKey].id === gatewayId) {
                  gw = pipelineGateways[pgKey];
                  return true;
                }
                return false;
              });
            }
            if (gw) {
              if (gw.conditions) {
                branchConditions = Object.assign({}, gw.conditions);
              }
              if (gw.default_condition) {
                const nodeId = gw.default_condition.flow_id;
                branchConditions[nodeId] = {
                  ...gw.default_condition,
                  isDefault: true,
                };
              }
            }
          });
        }
        return branchConditions;
      },
      // 标签拖拽
      handleLabelDrag({ edge, current, previous }) {
        if (!previous || !previous.length || !current.length) return;
        // 边的长度：通过data-cell-id 查找边的SVG容器，再取path元素
        const edgeDom = this.getNodeElement(`g[data-cell-id="${edge.id}"]`);
        const svgPath = edgeDom && edgeDom.querySelector('path');
        if (!svgPath) return;
        const edgeLength = svgPath.getTotalLength();
        // 检测是否属于循环流内部连线
        let loopNodeId = '';
        const sourceCellId = edge.source?.cell;
        if (sourceCellId) {
          const sourceNode = this.getNodeInstance(sourceCellId);
          const parent = sourceNode?.getParent?.();
          if (parent?.id && this.activities[parent.id]?.type === 'SubCanvas') {
            loopNodeId = parent.id;
          }
        }
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
          if (loopNodeId) {
            condition.loopNodeId = loopNodeId;
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
        // 检测是否为循环容器内部连线
        let isInnerEdge = false;
        let loopParentId = null;
        if (data) {
          const sourceCellId = data.source?.cell || data.source?.id;
          const targetCellId = data.target?.cell || data.target?.id;
          const sourceNode = this.getNodeInstance(sourceCellId);
          const targetNode = targetCellId ? this.getNodeInstance(targetCellId) : null;
          const parent = sourceNode?.getParent?.() || targetNode?.getParent?.();
          if (parent?.id && this.activities[parent.id]?.type === 'SubCanvas') {
            isInnerEdge = true;
            loopParentId = parent.id;
          }
        }
        if (!isInnerEdge) {
          this.$emit('onLineChange', type, data);
        }
        if (isInnerEdge && loopParentId) {
          this.syncLoopGroupInnerNodes(loopParentId);
        }
      },
      onLocationChange(type, data, isGroupInner, groupParentId) {
        this.$emit('templateDataChanged');
        this.$emit('onLocationChange', type, data, isGroupInner, groupParentId);
        // 循环容器节点新增/复制时：父节点已入 store，统一处理子节点的 children 回填和事件数据同步
        if ((type === 'add' || type === 'copy') && data && data.shape === 'custom-loop-group-node') {
          // 如果是复制操作，先复制原始分组节点的 location 和 flows 数据
          if (type === 'copy' && data.data && data.data.oldSouceId) {
            this.copyLoopGroupLocationAndFlows(data.data.oldSouceId, data.id);
          }
          this.syncLoopGroupInnerNodes(data.id);
        }
        if (type === 'edit' && data && data.shape === 'custom-loop-group-node') {
          this.syncLoopGroupInnerNodes(data.id);
        }
        // dnd拖入/快捷面板添加/复制操作同步写入pipeline
        if ((type === 'add' || type === 'copy') && data) {
          const parent = data.getParent ? data.getParent() : null;
          const parentId = parent?.id;
          if (parentId && this.activities[parentId]?.type === 'SubCanvas') {
            this.syncLoopGroupInnerNodes(parentId);
          }
        }
      },
      // 复制SubCanvas的嵌套pipelineTree数据
      copyLoopGroupLocationAndFlows(oldSourceId, newNodeId) {
        const oldLoopActivity = this.activities[oldSourceId];
        if (!oldLoopActivity || oldLoopActivity.type !== 'SubCanvas') return;

        const newLoopActivity = this.activities[newNodeId];
        if (!newLoopActivity) return;

        const newGroupNode = this.getNodeInstance(newNodeId);
        if (!newGroupNode) return;

        // 尺寸同步
        const oldGroupNode = this.getNodeInstance(oldSourceId);
        let syncedWidth;
        let syncedHeight;
        if (oldGroupNode) {
          const { width, height } = oldGroupNode.size();
          newGroupNode.resize(width, height);
          syncedWidth = width;
          syncedHeight = height;
        }

        // 获取旧的 nested pipelineTree
        const oldPT = oldLoopActivity.pipeline;
        if (!oldPT) {
          // 如果没有pipeline直接让initLoopContainerContent创建默认内容
          return;
        }
        // 清理新分组已有的子节点
        this.clearExistingLoopChildren(newNodeId);
        // 如果旧 pipelineTree 没有 activities/子节点，直接返回（由dnd初始化默认内容）
        if (!oldPT.activities || Object.keys(oldPT.activities).length === 0) return;
        if (!oldPT.start_event || !oldPT.end_event) return;
        // 获取新旧分组节点位置
        const oldGroupPos = this.graph.getCellById(oldSourceId).position();
        const newGroupPos = newGroupNode.position();
        // ID 重映射
        const oldToNewIdMap = {};
        const createNewId = () => `node${uuid()}`;
        // 映射 start_event / end_event
        const oldStartId = oldPT.start_event.id;
        const oldEndId = oldPT.end_event.id;
        oldToNewIdMap[oldStartId] = createNewId();
        oldToNewIdMap[oldEndId] = createNewId();
        // 映射 activities 和 gateways
        Object.keys(oldPT.activities || {}).forEach((id) => {
 oldToNewIdMap[id] = createNewId();
});
        Object.keys(oldPT.gateways || {}).forEach((id) => {
 oldToNewIdMap[id] = createNewId();
});

        // 在 X6 图上创建子节点副本
        const oldChildNodes = this.graph.getNodes().filter((n) => {
          const d = n.getData();
          return d && d.parent === oldSourceId;
        });
        oldChildNodes.forEach((oldChild) => {
          const oldChildData = oldChild.getData();
          const newChildId = oldToNewIdMap[oldChild.id];
          if (!newChildId) return;
          const { width, height } = oldChild.size();
          const oldChildAbsPos = oldChild.position();
          const relX = oldChildAbsPos.x - oldGroupPos.x;
          const relY = oldChildAbsPos.y - oldGroupPos.y;
          const newChild = this.graph.addNode({
            id: newChildId,
            shape: oldChild.shape,
            x: newGroupPos.x + relX,
            y: newGroupPos.y + relY,
            width,
            height,
            data: { ...oldChildData, parent: newNodeId },
            zIndex: oldChild.getZIndex(),
          });
          newGroupNode.addChild(newChild);
        });

        // 复制内部连线到 X6 图
        const oldChildNodeIds = oldChildNodes.map(n => n.id);
        const allEdges = this.graph.getEdges();
        allEdges.filter((edge) => {
          const sId = edge.getSourceCellId();
          const tId = edge.getTargetCellId();
          return oldChildNodeIds.includes(sId) && oldChildNodeIds.includes(tId);
        }).forEach((oldEdge) => {
          const oldSource = oldEdge.getSource();
          const oldTarget = oldEdge.getTarget();
          const newSourceId = oldToNewIdMap[oldSource.cell];
          const newTargetId = oldToNewIdMap[oldTarget.cell];
          if (!newSourceId || !newTargetId) return;
          this.graph.addEdge({
            shape: 'edge',
            id: `line${uuid()}`,
            source: { cell: newSourceId, port: oldSource.port },
            target: { cell: newTargetId, port: oldTarget.port },
            attrs: { line: { stroke: '#a9adb6', strokeWidth: 2, targetMarker: { name: 'block', width: 6, height: 8 } } },
            data: {},
            zIndex: oldEdge.getZIndex(),
            router: { name: 'manhattan', args: { padding: 1 } },
          });
        });

        // 构建新的 pipelineTree 数据（ID 重映射后的深拷贝）
        const newPT = utilsTools.deepClone(oldPT);
        // 重映射 activities
        Object.keys(newPT.activities || {}).forEach((oldId) => {
          const newId = oldToNewIdMap[oldId];
          if (newId) {
            newPT.activities[newId] = { ...newPT.activities[oldId], id: newId };
            delete newPT.activities[oldId];
          }
        });
        // 重映射 gateways
        Object.keys(newPT.gateways || {}).forEach((oldId) => {
          const newId = oldToNewIdMap[oldId];
          if (newId) {
            newPT.gateways[newId] = { ...newPT.gateways[oldId], id: newId };
            delete newPT.gateways[oldId];
          }
        });
        // 重映射 start_event / end_event 的 ID
        if (newPT.start_event) {
          newPT.start_event.id = oldToNewIdMap[oldStartId] || newPT.start_event.id;
        }
        if (newPT.end_event) {
          newPT.end_event.id = oldToNewIdMap[oldEndId] || newPT.end_event.id;
        }
        // 重映射 location（ID + 宽高从旧节点同步）
        (newPT.location || []).forEach((loc) => {
          const oldLocId = loc.id;
          const newId = oldToNewIdMap[loc.id];
          if (newId) loc.id = newId;
          // 同步旧节点的宽高
          const oldCell = this.graph.getCellById(oldLocId);
          if (oldCell && oldCell.isNode()) {
            const { width, height } = oldCell.size();
            loc.width = width;
            loc.height = height;
          }
        });
        // 重映射 flows：flowId 生成新 ID，source/target 重映射节点 ID
        const flowIdMap = {};
        Object.keys(newPT.flows || {}).forEach((flowId) => {
          const flow = newPT.flows[flowId];
          if (oldToNewIdMap[flow.source]) flow.source = oldToNewIdMap[flow.source];
          if (oldToNewIdMap[flow.target]) flow.target = oldToNewIdMap[flow.target];
          const newFlowId = `line${uuid()}`;
          flow.id = newFlowId;
          flowIdMap[flowId] = newFlowId;
          delete newPT.flows[flowId];
          newPT.flows[newFlowId] = flow;
        });
        // 重映射 line：lineId 生成新 ID（与对应 flow 保持一致），source/target 重映射节点 ID
        (newPT.line || []).forEach((line) => {
          if (oldToNewIdMap[line.source.id]) line.source.id = oldToNewIdMap[line.source.id];
          if (oldToNewIdMap[line.target.id]) line.target.id = oldToNewIdMap[line.target.id];
          const newLineId = flowIdMap[line.id] || `line${uuid()}`;
          line.id = newLineId;
        });
        // 重映射 activities 中的 incoming/outgoing 引用的 flowId
        Object.keys(newPT.activities || {}).forEach((actId) => {
          const act = newPT.activities[actId];
          if (act.incoming) {
            act.incoming = Array.isArray(act.incoming)
              ? act.incoming.map(id => flowIdMap[id] || id)
              : (flowIdMap[act.incoming] || act.incoming);
          }
          if (act.outgoing) {
            act.outgoing = Array.isArray(act.outgoing)
              ? act.outgoing.map(id => flowIdMap[id] || id)
              : (flowIdMap[act.outgoing] || act.outgoing);
          }
        });
        // 重映射 gateways 中的 incoming/outgoing 和 conditions 引用的 flowId
        Object.keys(newPT.gateways || {}).forEach((gwId) => {
          const gw = newPT.gateways[gwId];
          if (gw.incoming) {
            gw.incoming = Array.isArray(gw.incoming)
              ? gw.incoming.map(id => flowIdMap[id] || id)
              : (flowIdMap[gw.incoming] || gw.incoming);
          }
          if (gw.outgoing) {
            gw.outgoing = Array.isArray(gw.outgoing)
              ? gw.outgoing.map(id => flowIdMap[id] || id)
              : (flowIdMap[gw.outgoing] || gw.outgoing);
          }
          if (gw.conditions) {
            const newConditions = {};
            Object.keys(gw.conditions).forEach((condFlowId) => {
              const newCondFlowId = flowIdMap[condFlowId] || condFlowId;
              newConditions[newCondFlowId] = gw.conditions[condFlowId];
            });
            gw.conditions = newConditions;
          }
        });
        // 重映射 start_event / end_event 中的 incoming/outgoing
        if (newPT.start_event && newPT.start_event.outgoing) {
          newPT.start_event.outgoing = flowIdMap[newPT.start_event.outgoing] || newPT.start_event.outgoing;
        }
        if (newPT.end_event && newPT.end_event.incoming) {
          newPT.end_event.incoming = Array.isArray(newPT.end_event.incoming)
            ? newPT.end_event.incoming.map(id => flowIdMap[id] || id)
            : (flowIdMap[newPT.end_event.incoming] || newPT.end_event.incoming);
        }

        // 重映射 pipeline.constants：更新 source_info 中的旧节点 ID
        // 对 component_outputs 类型变量生成新 key（避免与原节点冲突），并收集 oldKey→newKey 映射
        // 用于后续更新所有引用该变量的地方（SubProcess 子节点的 constants.value、component.data.value 等）
        const constKeyMap = {};
        if (newPT.constants) {
          const newConstants = {};
          Object.keys(newPT.constants).forEach((oldKey) => {
            const c = newPT.constants[oldKey];
            // 重映射 source_info 中的节点 ID
            if (c.source_info) {
              const newSourceInfo = {};
              Object.keys(c.source_info).forEach((nodeId) => {
                const mappedId = oldToNewIdMap[nodeId] || nodeId;
                newSourceInfo[mappedId] = c.source_info[nodeId];
              });
              c.source_info = newSourceInfo;
            }
            // 输出变量
            if (c.source_type === 'component_outputs') {
              const sourceInfoValues = Object.values(c.source_info || {})[0] || [];
              const rawKey = sourceInfoValues[0] || oldKey;
              const baseName = rawKey.replace(/^\$\{|\}$/g, '');
              const newKey = `\${${baseName}_${random4()}}`;
              c.key = newKey;
              constKeyMap[oldKey] = newKey;
              newConstants[newKey] = c;
            } else {
              newConstants[oldKey] = c;
            }
          });
          newPT.constants = newConstants;
        }

        // 重映射 loop_config.loop_params
        if (newLoopActivity.loop_config && newLoopActivity.loop_config.loop_params) {
          const oldLoopParams = newLoopActivity.loop_config.loop_params;
          const newLoopParams = {};
          Object.keys(oldLoopParams).forEach((paramKey) => {
            const baseName = paramKey.replace(/^\$\{|\}$/g, '');
            const newKey = `\${${baseName}_${random4()}}`;
            constKeyMap[paramKey] = newKey;
            newLoopParams[newKey] = oldLoopParams[paramKey];
          });
          newLoopActivity.loop_config.loop_params = newLoopParams;
        }

        // 更新所有引用 pipeline.constants / loop_params 变量的地方
        // 1) SubProcess 子节点的 constants.value
        // 2) 各 activity 的 component.data.*.value
        // 3) SubProcess 子节点的 constants 中的source_info是子流程模板内部节点ID,不在 oldToNewIdMap 中，不重映射
        const replaceVarRefs = (val) => {
          if (typeof val !== 'string') return val;
          let result = val;
          Object.keys(constKeyMap).forEach((oldKey) => {
            result = result.split(oldKey).join(constKeyMap[oldKey]);
          });
          return result;
        };
        const remapVarRefsInData = (dataObj) => {
          if (!dataObj || typeof dataObj !== 'object') return;
          Object.keys(dataObj).forEach((fieldKey) => {
            const field = dataObj[fieldKey];
            if (field && typeof field === 'object' && 'value' in field) {
              if (typeof field.value === 'string') {
                field.value = replaceVarRefs(field.value);
              }
            }
          });
        };
        Object.keys(newPT.activities || {}).forEach((actId) => {
          const act = newPT.activities[actId];
          // SubProcess 内部 constants.value 中可能引用 pipeline.constants 的输出变量
          if (act.constants) {
            Object.keys(act.constants).forEach((ck) => {
              const c = act.constants[ck];
              if (typeof c.value === 'string') {
                c.value = replaceVarRefs(c.value);
              }
            });
          }
          // component.data 字段中可能引用变量
          if (act.component && act.component.data) {
            remapVarRefsInData(act.component.data);
          }
        });
        // 重映射 pipeline.outputs 中的变量 key 引用
        if (Array.isArray(newPT.outputs)) {
          newPT.outputs = newPT.outputs.map(key => constKeyMap[key] || key);
        }
        // 同步activity.constants：与pipeline.constants保持一致
        if (newPT.constants) {
          newLoopActivity.constants = utilsTools.deepClone(newPT.constants);
        }

        // 更新到 store
        this.setActivities({
          type: 'edit',
          location: { ...newLoopActivity, pipeline: newPT },
        });
        // 同步分组节点坐标和宽高到顶层 store 的 location（在 setActivities edit 之后，确保 location 已存在）
        if (syncedWidth && syncedHeight) {
          const { x, y } = newGroupNode.position();
          this.setLocationXY({
            id: newNodeId,
            x,
            y,
            width: syncedWidth,
            height: syncedHeight,
          });
        }
      },
      // 清理新分组节点已有的子节点
      clearExistingLoopChildren(loopNodeId) {
        const newNode = this.getNodeInstance(loopNodeId);
        if (!newNode) return;
        const existingChildren = this.graph.getNodes().filter((n) => {
          const d = n.getData();
          return d && d.parent === loopNodeId;
        });
        existingChildren.forEach((child) => {
          const connectedEdges = this.graph.getConnectedEdges(child);
          connectedEdges.forEach(edge => this.graph.removeEdge(edge));
          this.graph.removeNode(child);
        });
      },
      onLocationMoveDone(data) {
        if (data && data.shape === 'custom-loop-group-node') {
          // events.js的自动resize链在最后一步不触发onContainerSizeChange，导致之前 syncLoopGroupInnerNodes 保存的是倒数第二步的坐标而非最终坐标
          this.syncLoopGroupInnerNodes(data.id);
        }
        // 同步整个分组(resize会影响所有子节点位置)
        const parent = data && data.getParent ? data.getParent() : null;
        if (parent && parent.isNode() && parent.shape === 'custom-loop-group-node') {
          this.syncLoopGroupInnerNodes(parent.id);
        }
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
          onShowLoopVariables(loopNodeId) {
            self.$emit('onShowLoopVariables', loopNodeId);
          },
          onResizeEnd(node) {
            self.$emit('onLoopGroupResizeEnd', node);
          },
        };
      },
      // 重置画布
      resetCells() {
        // 标记正在重建画布，阻止 DND 组件的 node:added 监听器为循环节点初始化默认子节点
        this.graph.isResetting = true;
        this.graph.clearCells(true);
        this.initCanvasData();
        const cells = this.graph.getCells();
        this.graph.resetCells(cells, true);
        this.graph.isResetting = false;
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
      adjustLoopGroupSize(parentNodeId) {
        const parentNode = this.getNodeInstance(parentNodeId);
        if (!parentNode || parentNode.shape !== 'custom-loop-group-node') return;
        // 取任意子节点微调位置触发分组节点大小自适应
        const children = parentNode.getChildren();
        if (children && children.length) {
          const child = children.find(c => c.isNode()) || children[0];
          if (child && child.isNode()) {
            const pos = child.getPosition();
            child.setPosition(pos.x + 1, pos.y + 1);
            this.$nextTick(() => {
              child.setPosition(pos.x, pos.y);
            });
          }
        }
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
