<template>
  <div
    ref="processCanvasComp"
    class="process-canvas-comp">
    <Tools
      v-if="graph"
      :instance="graph"
      class="canvas-tools"
      :class="{ 'view-mode': !editable }"
      :editable="editable"
      :is-perspective="isPerspective"
      :is-selection-open="isSelectionOpen"
      @onToggleAllNode="onToggleAllNode"
      @onFrameSelectToggle="isSelectionOpen = $event"
      @onFormatPosition="onFormatPosition"
      @onLocationMoveDone="onLocationMoveDone"
      @onDownloadCanvas="onDownloadCanvas"
      @onTogglePerspective="onTogglePerspective" />
    <div class="canvas-material-container" />
    <template v-if="graph">
      <NodeTipsPanel
        v-if="isPerspectivePanelShow"
        :instance="graph"
        :is-perspective-panel-show="isPerspectivePanelShow"
        :node-variable="nodeVariable"
        :node-tips-panel-position="nodeTipsPanelPosition" />
      <ShortcutPanel
        v-if="showShortcutPanel"
        :instance="graph"
        :active-cell="activeCell"
        :position="shortcutPanelPosition"
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
  import verticalRouter from './registry/router.js';
  // 工具栏
  import Tools from './components/tools.vue';

  import { uuid } from '@/utils/uuid.js';

  // 快捷面板
  import ShortcutPanel from './components/shortcutPanel.vue';

  // 变量引用/执行记录面板
  import NodeTipsPanel from './components/nodeTipsPanel.vue';
  // 单选/框选
  // import { Selection } from '@antv/x6-plugin-selection';
  import { Clipboard } from '@antv/x6-plugin-clipboard';

  import dom from '@/utils/dom.js';
  import { mapState } from 'vuex';
  import utilsTools from '@/utils/tools.js';
  import domtoimage from '@/utils/domToImage.js';

  export default {
    name: 'ProcessCanvasComp',
    components: {
      Tools,
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
    },
    data() {
      return {
        graph: null,
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
        locations: state => state.template.location,
        lines: state => state.template.line,
        gateways: state => state.template.gateways,
      }),
    },
    mounted() {
      this.initCanvas();
      this.initCanvasData();
      this.$nextTick(() => {
        const { id } = this.locations.find(item => item.type === 'startpoint');
        const nodeInstance = this.getNodeInstance(id);
        const { x, y } = nodeInstance.position();
        this.graph.positionPoint({ x: x + 34 / 2, y }, '50%', 150);
      });
      document.addEventListener('mousemove', utilsTools.debounce(this.onMouseMove, 100), false);
    },
    beforeDestroy() {
      Graph.unregisterRouter('vertical');
      document.removeEventListener('mousemove', this.onMouseMove);
    },
    methods: {
      initCanvas() {
        Graph.registerRouter('vertical', verticalRouter, true);
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
            min: 0.05,
            max: 12,
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
              name: 'vertical',
              args: {
                padding: 20,
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
                router: {
                  name: 'vertical',
                  args: {
                    padding: 20,
                  },
                },
                data: {},
                zIndex: 2,
              });
            },
          },
          interacting: {
            nodeMovable: false,
            edgeLabelMovable: this.editable,
            arrowheadMovable: this.editable,
          },
          highlighting: {
            embedding: {
              name: 'stroke',
              args: {
                padding: -1,
                attrs: {
                  stroke: '#73d13d',
                },
              },
            },
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
            enabled: true,
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
        registryNodes(this.onEventMap);
        registryEvents(this.graph);
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
          this.onShowNodeConfig(cell.id);
          this.closeShortcutPanel();
        });
        // 删除cell
        this.graph.on('cell:removed', ({ cell }) => {
          if (cell.shape === 'custom-node' && cell.data.type !== 'group') {
            this.$emit('onLocationChange', 'delete', cell);
          } else if (cell.shape === 'edge') {
            this.$emit('onLineChange', 'delete', cell);
          }
        });
        // 节点位置变化
        this.graph.on('node:change:position', ({ cell }) => {
          if (cell.shape === 'custom-node' && cell.data.type !== 'group') {
            this.onLocationMoveDone(cell);
          }
        });
        // 边的输入输出变化
        this.graph.on('edge:change:source', ({ cell }) => {
          this.$emit('onLineChange', 'edit', cell);
        });
        this.graph.on('edge:change:target', ({ cell }) => {
          this.$emit('onLineChange', 'edit', cell);
        });
      },
      initCanvasData() {
        if (!this.canvasData.length) return;
        this.canvasData.forEach((cell) => {
          let instance = null;
          if (cell.shape === 'edge') {
            const edge = utilsTools.deepClone(cell);
            delete edge.router;
            this.graph.addEdge({ ...cell, zIndex: 2 });
          } else {
            instance = this.graph.addNode({ ...cell });
          }
          // 绑定组群
          if (cell.parent) {
            this.$nextTick(() => {
              const parentInstance = this.graph.getCellById(cell.parent);
              parentInstance && parentInstance.addChild(instance);
            });
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
        let top; let left;
        if (cell.shape === 'edge') {
          left = e.clientX + 6; // 10-偏移宽度
          top = e.clientY - 48 + 6; // 10-偏移高度
        } else  {
          const customNodeDom = this.getNodeElement(`[data-cell-id=${cell.id}] .custom-node`);
          const { x, y, height, width  } = customNodeDom.getBoundingClientRect();
          const canvasDom = document.querySelector('.process-canvas-comp');
          const { left: canvasLeft, top: canvasTop } = canvasDom.getBoundingClientRect();
          const offsetX = cell.data.type === 'task' ? 60 : 5;
          const offsetY = cell.data.type === 'task' ? 6 : -5;
          left = x + width - offsetX - canvasLeft;
          top = y + height - canvasTop + offsetY; // 48-画布头部高度
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
          const ratio = this.graph.zoom();
          location.x = (left - 60 - offsetLeft) / ratio;
          location.y = (top - 48 - offsetTop) / ratio;
        }
        return location;
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
      //   createEdge ({ source, target, data = {} }) {
      //     const edgeId = `line${uuid()}`
      //     this.graph.addEdge({
      //       shape: 'edge',
      //       id: edgeId,
      //       source,
      //       target,
      //       attrs: {
      //         line: {
      //           stroke: '#a9adb6',
      //           strokeWidth: 2,
      //           targetMarker: {
      //             name: 'block',
      //             width: 6,
      //             height: 8,
      //           },
      //         },
      //       },
      //       data,
      //       zIndex: 0,
      //       router: {
      //         name: 'vertical',
      //         args: {
      //           padding: 20,
      //         },
      //       },
      //     })
      //     this.onLineChange('add', {
      //       id: edgeId,
      //       source,
      //       target,
      //       data,
      //     })
      //   },
      // 节点点击
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

        // 是否点击到分支标签上
        if (dom.parentClsContains('branch-condition', e.target)) {
          this.branchConditionEditHandler(e);
          return;
        }
        if (cell.shape === 'edge' ||  cell.data.type === 'group') return;

        // 如果不是模版编辑页面，点击节点相当于打开配置面板（任务执行是打开执行信息面板）
        if (this.editable) {
          // 避免双击时再次触发单击
          if (this.showShortcutPanel) return;
          // 展开节点配置面板
          this.openShortcutPanel({ cell, e });
        } else if (cell.shape === 'custom-node') {
          this.$emit('onNodeClick', cell.id, cell.data.type);
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
        if (this.showShortcutPanel && cell.id !== this.activeCell.id && cell.data.type !== 'group') {
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
            const conditionInfo = cell.data?.conditionInfo || branchInfo[cell.id] || {};
            if (!Object.keys(conditionInfo).length) return;
            const textDom = document.createElement('span');
            textDom.innerText = conditionInfo.name;
            textDom.style.fontSize = '12px';
            document.body.appendChild(textDom);
            let { width = 0 } = textDom.getBoundingClientRect();
            width = (width + 12) < 60 ? 60 : width;
            width = width > 112 ? 112 : width;
            document.body.removeChild(textDom);
            cell.appendLabel({
              markup: Markup.getForeignObjectMarkup(),
              attrs: {
                fo: {
                  width,
                  height: 26,
                  x: -width / 2,
                  y: -10,
                },
              },
              label: {
                ...conditionInfo,
                lineId: cell.id,
                sourceId: cell.source.cell,
              },
              position: {
                distance: -40,
              },
            });
            // 更新本地condition配置
            if (cell.data?.conditionInfo) {
              const condition = {
                id: cell.id,
                nodeId: cell.source.cell,
                name: conditionInfo.name,
                tag: conditionInfo.tag,
                value: conditionInfo.evaluate,
              };
              if (conditionInfo.default_condition) {
                condition.default_condition = {
                  name: conditionInfo.name,
                  tag: conditionInfo.tag,
                  flow_id: cell.id,
                };
              }
              this.$emit('updateCondition', condition);
            }
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
        // 200节点的气泡卡片展示最小宽度
        const bodyWidth = document.body.offsetWidth;
        const isRight = bodyWidth - nodeRight > 200;
        // 设置坐标
        let top = nodeTop - canvasTop - 10;
        let left; let padding;
        if (isRight) {
          left = nodeLeft - canvasLeft + width;
          padding = '0 0 0 10px';
        } else {
          left = nodeLeft - canvasLeft - 200;
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
        nodeInstance.setData(data);
      },
      setCanvasPosition(id) {
        const nodeInstance = this.getNodeInstance(id);
        this.graph.positionCell(nodeInstance, 'center');
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
      left: 30px;
      z-index: 1;
      &.view-mode {
        left: 40px;
      }
    }
    // 节点样式用到了相对定位、绝对定位，解决在safari上会存在兼容性问题
    /deep/ .x6-cell.x6-node {
        .bk-tooltip {
            position: fixed;
        }
    }
    /deep/.x6-widget-selection-box {
      border: 1px dashed #3a84ff;
      margin-top: -3px;
      margin-left: -3px;
    }

    /deep/.x6-widget-selection-inner {
      border: none;
      box-shadow: none;
    }
    /deep/.branch-condition {
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
    /deep/.custom-snap-line {
      .x6-widget-snapline-vertical,
      .x6-widget-snapline-horizontal {
        stroke: #3a84ff;
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
