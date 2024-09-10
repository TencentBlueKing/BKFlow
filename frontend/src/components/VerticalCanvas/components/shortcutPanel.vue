<template>
  <div
    ref="shortcutWrap"
    :style="{ left: `${position.left}px`, top: `${position.top}px` }"
    class="shortcut-panel"
    @mouseover.stop
    @click.stop>
    <ul class="nodes-wrap">
      <li
        v-for="(item, index) in nodeTypeList"
        :key="index"
        v-bk-tooltips="{
          content: item.tips,
          delay: 500
        }"
        :data-test-id="`templateCanvas_panel_${item.key}`"
        :class="['nodes-item', `common-icon-node-${item.key}-shortcut`]"
        @click.stop="onAppendNode(item.id)" />
    </ul>
    <ul
      v-if="isShowOperate"
      class="operate-btn-wrap">
      <li
        v-bk-tooltips="{
          content: $t('复制并插入'),
          delay: 500
        }"
        data-test-id="templateCanvas_panel_nodeCopyInsert"
        class="btn-item common-icon-bkflow-copy-insert"
        @click.stop="onAppendNode(activeCell.data.type, true)" />
      <li
        v-if="isShowDeleteBtn"
        v-bk-tooltips="{
          content: $t('删除节点'),
          delay: 500
        }"
        data-test-id="templateCanvas_panel_nodeDelete"
        class="btn-item common-icon-bkflow-delete"
        @click.stop="onNodeRemove" />
    </ul>
  </div>
</template>
<script>
  import { Graph, Cell } from '@antv/x6';
  import { uuid, random4 } from '@/utils/uuid.js';
  import { mapState } from 'vuex';
  import utilsTools from '@/utils/tools.js';
  export default {
    name: 'ShortcutPanel',
    props: {
      instance: Graph,
      activeCell: Cell,
      position: {
        type: Object,
        default() {
          return {
            left: 0,
            top: 0,
          };
        },
      },
    },
    data() {
      return {
        nodeTargetMaps: {},
        nodeSourceMap: {},
      };
    },
    computed: {
      ...mapState({
        activities: state => state.template.activities,
        locations: state => state.template.location,
        lines: state => state.template.line,
        flows: state => state.template.flows,
        gateways: state => state.template.gateways,
        startNode: state => state.template.start_event,
        endNode: state => state.template.end_event,
      }),
      nodeTypeList () {
        const list = [
          { key: 'tasknode', id: 'task', tips: this.$t('标准插件节点') },
          // { key: 'subflow', id: 'subflow', tips: '子流程节点' },
          { key: 'branchgateway', id: 'branch-gateway', tips: this.$t('分支网关') },
          { key: 'parallelgateway', id: 'parallel-gateway', tips: this.$t('并行网关') },
          { key: 'conditionalparallelgateway', id: 'conditional-parallel-gateway', tips: this.$t('条件并行网关') },
          { key: 'convergegateway', id: 'converge-gateway', tips: this.$t('汇聚网关') },
        ]
        if (this.activeCell.data.type === 'parallel-gateway') {
          return list.filter(item => item.id !== 'converge-gateway')
        }
        return list
      },
      branchConditions() {
        const branchConditions = {};
        Object.keys(this.gateways).forEach((gKey) => {
          const item = this.gateways[gKey];
          if (item.conditions) {
            branchConditions[item.id] = Object.assign({}, item.conditions);
          }
          if (item.default_condition) {
            const nodeId = item.default_condition.flow_id;
            branchConditions[item.id][nodeId] = item.default_condition;
          }
        });
        return branchConditions;
      },
      branchGatewayId() {
        return ['parallel-gateway', 'branch-gateway', 'conditional-parallel-gateway'];
      },
      isShowOperate() {
        const { data } = this.activeCell;
        return !['start', 'end'].includes(data.type);
      },
      isShowDeleteBtn() {
        const { id, data } = this.activeCell;
        // 与分支网关对应的汇聚网关禁止删除
        const gatewayConvergeNodes = Object.values(this.gateways).reduce((acc, cur) => {
          if (cur.type !== 'ConvergeGateway') {
            acc.push(cur.converge_gateway_id);
          }
          return acc;
        }, []);
        return data.type !== 'converge-gateway' || !gatewayConvergeNodes.includes(id);
      },
    },
    methods: {
      // 添加节点
      onAppendNode(type, copyInsert) {
        // 当前选中节点的位置尺寸
        const { id: sourceId, data } = this.activeCell;
        const isBranchGatewayCell = this.branchGatewayId.includes(data.type);
        // 节点输出映射
        this.nodeTargetMaps = this.getNodeTargetMaps();
        // 目标节点
        let targetId; let targetArrow;
        if (isBranchGatewayCell) { // 分支网关
          targetId = this.gateways[sourceId].converge_gateway_id;
          targetArrow = 'port_right';
        } else { // 任务节点
          const lineInfo = this.lines.find(line => line.source.id === sourceId) || {};
          const { source = {}, target = {}, id: lineId } = lineInfo;
          targetId = target.id;
          targetArrow = `port_${target.arrow?.toLowerCase()}`;
          // 删除旧的边
          this.instance.removeEdge(lineId);
          this.$emit('onLineChange', 'delete', {
            id: lineId,
            source: {
              cell: sourceId,
              port: `port_${source.arrow?.toLowerCase()}`,
            },
            target: {
              cell: targetId,
              port: targetArrow,
            },
          });
        }
        // 新节点id
        const nodeId = `node${uuid()}`;
        // 新边、新节点
        const { nodes = [], edges = [] } = this.getCells({
          type,
          nodeId,
          sourceId,
          targetId,
          targetArrow,
        });
        // 平移画布以保新增节点可见
        this.translateGraph(sourceId, type);

        // 群组
        let groupCell = this.getNodeInstance(data.parent);
        // 新分支
        if (isBranchGatewayCell) {
          // 新建分支组群
          const { x, y } = groupCell.position();
          const { width } = groupCell.size();
          const branchGroupCell = this.createGroup({
            parent: data.parent,
            location: {
              y: y + 60,
              x: x + width + 60,
            },
            size: nodes[0].size,
          });
          groupCell.addChild(branchGroupCell);
          groupCell = branchGroupCell;
        }
        // 更新竖向排版
        const nodeHeight = nodes[0].size.height + 60;
        // 组群节点有上下20padding, 所以与下一个节点间隔为20
        this.updateVerticalLayout('add', sourceId, nodeHeight);

        // 新建节点
        nodes.forEach((node) => {
          let nodeCell = null;
          if (node.type === 'group') {
            nodeCell = this.createGroup({
              ...node,
              parent: node.parent || groupCell.id,
            });
          } else {
            const isCopyNode = copyInsert && node.id === nodeId;
            nodeCell = this.createNode({
              ...node,
              parent: node.parent || groupCell.id,
              data: isCopyNode ? { ...data, oldSouceId: sourceId } : {},
            });
            this.$emit('onLocationChange', isCopyNode ? 'copy' : 'add', nodeCell);
          }
          if (node.parent) {
            const parentCell = this.getNodeInstance(node.parent);
            parentCell && parentCell.addChild(nodeCell);
          } else {
            groupCell.addChild(nodeCell);
          }
        });
        // 新建边
        edges.forEach((line) => {
          this.createEdge(line);
        });
        setTimeout(() => {
          // 更新横向排版
          const gatewayId = isBranchGatewayCell ? sourceId : data.sourceGatewayId;
          this.updateHorizontalLayout(gatewayId);
        }, 100);

        // 更新快捷面板
        this.$emit('updateShortcutPanel');
      },
      // 输出节点映射
      getNodeTargetMaps() {
        return this.lines.reduce((acc, cur) => {
          const { source, target } = cur;
          if (acc[source.id]) {
            acc[source.id].push(target.id);
          } else {
            acc[source.id] = [target.id];
          }
          return acc;
        }, {});
      },
      // 获取节点、边
      getCells(info) {
        const { type, nodeId, sourceId, targetId, targetArrow } = info;

        const { x, y } = this.activeCell.position();
        const { height, width } = this.activeCell.size();
        const offsetX = type === 'task' ? 154 / 2 : 34 / 2;

        const location = {
          y: y + height + 60,
          x: x + width / 2 - offsetX,
        };
        const edges = [{
          source: { cell: sourceId, port: 'port_bottom' },
          target: { cell: nodeId, port: 'port_top' },
        }];
        const nodes = [];
        // 更新location、edges
        const { parent, type: sourceType } = this.activeCell.data;
        if (this.branchGatewayId.includes(sourceType)) {
          const parentCell = this.getNodeInstance(parent);
          const { x } = parentCell.position();
          const { width } = parentCell.size();
          location.x = x + width + 60;

          edges[0].source.port = 'port_right';
        }
        // 初始化节点配置
        const initNodeConfig = ({ type, parent, id, location, size }) => ({
          id: id || `node${uuid()}`,
          type,
          parent,
          convergeGatewayId: null,
          sourceGatewayId: id === nodeId ? this.activeCell.id : nodeId,
          location,
          size,
        });
        // 新建分支网关(默认额外创建两个任务节点，一个汇聚网关)
        if (this.branchGatewayId.includes(type)) {
          if (this.branchGatewayId.includes(sourceType)) {
            location.x = location.x + 154 + 40;
          }
          const taskY = location.y + 34 + 60;
          const gatewayY = taskY + 54 + 60;
          const leftX = location.x + 34 / 2 - 40 - 154;
          const rightX = location.x + 34 / 2 + 40;
          const branchGroupId1 = `group_${random4()}`;
          const branchGroupId2 = `group_${random4()}`;
          const branchGroupId3 = `group_${random4()}`;

          nodes.push(
            initNodeConfig({
              type: 'group',
              id: branchGroupId1,
              location: { x: leftX, y: location.y },
              size: { width: (20 + 154 + 40) * 2, height: 34 * 2 + 54 + 60 * 2 },
            }),
            initNodeConfig({
              type: 'group',
              id: branchGroupId2,
              location: { x: leftX, y: taskY },
              size: { width: 154 + 40, height: 54 + 40 },
              parent: branchGroupId1,
            }),
            initNodeConfig({
              type: 'group',
              id: branchGroupId3,
              location: { x: rightX, y: taskY },
              size: { width: 154 + 40, height: 54 + 40 },
              parent: branchGroupId1,
            }),
            initNodeConfig({
              type,
              id: nodeId,
              location,
              parent: branchGroupId1,
            }),
            initNodeConfig({
              type: 'task',
              location: {  x: leftX, y: taskY },
              parent: branchGroupId2,
            }),
            initNodeConfig({
              type: 'task',
              location: { x: rightX, y: taskY },
              parent: branchGroupId3,
            }),
            initNodeConfig({
              type: 'converge-gateway',
              location: { x: location.x, y: gatewayY },
              parent: branchGroupId1,
            })
          );
          // 绑定汇聚网关
          nodes[3].convergeGatewayId = nodes[nodes.length - 1].id;

          // 新增连向分支节点的边
          edges.push(...[
            {
              source: { cell: nodeId, port: 'port_left' },
              target: { cell: nodes[nodes.length - 3].id, port: 'port_top' },
            },
            {
              source: { cell: nodeId, port: 'port_right' },
              target: { cell: nodes[nodes.length - 2].id, port: 'port_top' },
            },
            {
              source: { cell: nodes[nodes.length - 3].id, port: 'port_bottom' },
              target: { cell: nodes[nodes.length - 1].id, port: 'port_left' },
            },
            {
              source: { cell: nodes[nodes.length - 2].id, port: 'port_bottom' },
              target: { cell: nodes[nodes.length - 1].id, port: 'port_right' },
            },
            {
              source: { cell: nodes[nodes.length - 1].id, port: 'port_bottom' },
              target: { cell: targetId, port: targetArrow },
            },
          ]);
        } else {
          // 任务节点
          const { parent, sourceGatewayId, type: sourceType } = this.activeCell.data;
          const isBranchGw = this.branchGatewayId.includes(sourceType);
          const width = type === 'task' ? 154 : 34;
          const height = type === 'task' ? 54 : 34;
          nodes.push({
            id: nodeId,
            type,
            location,
            size: { width, height },
            parent: isBranchGw ? '' : parent,
            sourceGatewayId: isBranchGw ? sourceId : sourceGatewayId,
          });
          edges.push({
            source: { cell: nodeId, port: 'port_bottom' },
            target: { cell: targetId, port: targetArrow },
          });
        }

        return {
          edges,
          nodes,
        };
      },
      // 平移画布以保节点可见
      translateGraph(nodeId, nodeType) {
        // 获取节点dom
        let groupDom = document.querySelector(`[data-cell-id="${nodeId}"]`);
        const nodeCell = this.getNodeInstance(nodeId);
        if (this.branchGatewayId.includes(nodeCell.data.type)) {
          groupDom = document.querySelector(`[data-cell-id="${nodeCell.data.parent}"]`);
        }
        if (!groupDom) return;
        const { right, bottom } = groupDom.getBoundingClientRect();

        // 定义节点类型对应的基础尺寸
        const baseSizes = {
          task: { width: 154, height: 54 },
          'converge-gateway': { width: 34, height: 34 },
          branch: { width: 154 * 2 + 80, height: 34 * 2 + 60 * 2 + 54 },
        };

        // 获取当前节点类型的基础尺寸
        const { width: baseWidth, height: baseHeight } = baseSizes[nodeType] || baseSizes.branch;

        // 计算新建节点的总尺寸（包括边距）
        const totalNodeWidth = baseWidth + 40; // 20px 边距 * 2
        const totalNodeHeight = baseHeight + 40; // 20px 边距 * 2

        // 计算需要平移的距离
        const offsetX = Math.max(0, totalNodeWidth - (window.innerWidth - right) + 60);
        const offsetY = Math.max(0, totalNodeHeight - (window.innerHeight - bottom) + 60);

        // 获取当前画布的平移值
        const { tx, ty } = this.instance.translate();
        // 根据计算出的偏移量平移画布
        this.instance.translate(tx - offsetX, ty - offsetY);
      },
      // 创建节点
      createNode(params = {}) {
        const {
          id = `node${uuid()}`,
          type,
          location = {},
          size = {},
          data = {},
          parent,
          convergeGatewayId,
          sourceGatewayId,
        } = params;
        // 如果节点坐标不在视图容器中则不会挂载到Dom上，故需计算能够呈现在坐标位置
        return this.instance.addNode({
          id,
          shape: 'custom-node',
          width: type === 'task' ? 154 : 34,
          height: type === 'task' ? 54 : 34,
          ...location,
          ...size,
          data: {
            ...data,
            ...size,
            id,
            type,
            parent,
            convergeGatewayId,
            sourceGatewayId,
          },
          zIndex: 6,
        });
      },
      // 创建边
      createEdge({ source, target, data = {} }) {
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
          },
          data,
          zIndex: 2,
          router: {
            name: 'vertical',
            args: {
              padding: 10,
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
      // 创建群组
      createGroup(params = {}) {
        const { id, parent, location = {}, size = {} } = params;
        // 如果节点坐标不在视图容器中则不会挂载到Dom上，故需计算能够呈现在坐标位置
        return this.instance.addNode({
          id: id || `group_${random4()}`,
          shape: 'custom-node',
          ...location,
          ...size,
          parent,
          zIndex: 1,
          data: {
            type: 'group',
            parent,
          },
        });
      },
      // 获取单个对应的节点
      getNodeInstance(nodeId) {
        const nodes = this.instance.getNodes();
        return nodes.find(item => item.id === nodeId);
      },
      // 获取单个对应的边
      getEdgeInstance(lineId) {
        const edges = this.instance.getEdges();
        return edges.find(item => item.id === lineId);
      },
      // 节点删除
      onNodeRemove() {
        const node = this.activeCell;
        const { type, parent, sourceGatewayId } = node.data;
        let parentId = parent;
        // 拷贝数据更新前的数据
        const gateways = utilsTools.deepClone(this.gateways);
        const lines = utilsTools.deepClone(this.lines);

        // 节点/群组的输出连线的节点id
        let outputConnectorId = node.id;
        // 删除节点/群组
        if (type.includes('gateway') && type !== 'converge-gateway') {
          const parentCell = this.getNodeInstance(parent);
          parentId = parentCell.getParentId();
          this.instance.removeNode(parent);
          // 汇聚节点的输出节点
          const { converge_gateway_id: convergeId } = gateways[node.id];
          outputConnectorId = convergeId;
        } else {
          this.instance.removeNode(node.id);
        }

        // 输入、输出连线
        const sourceLine = lines.find(item => item.target.id === node.id);
        const { source: sourceInfo } = sourceLine;
        const targetLine = lines.find(item => item.source.id === outputConnectorId);
        const { target: targetInfo } = targetLine;

        // 如果当前节点是分支上最后一个节点，则不继续创建新的边
        if (sourceGatewayId && parentId) {
          const groupInstance = this.getNodeInstance(parentId);
          if (groupInstance && groupInstance.children.length === 0) {
            this.instance.removeNode(parentId);
            this.$emit('updateShortcutPanel');
            // 更新竖向布局
            this.nodeTargetMaps = this.getNodeTargetMaps();
            this.nodeSourceMap = this.getNodeSourceMaps();
            this.updateVerticalLayout('delete', sourceInfo.id);
            // 更新横向布局
            this.updateHorizontalLayout(sourceGatewayId);
            return;
          }
        }


        // 新增边
        const edgeInfo = {
          source: {
            cell: sourceInfo.id,
            port: `port_${sourceInfo.arrow.toLowerCase()}`,
          },
          target: {
            cell: targetInfo.id,
            port: `port_${targetInfo.arrow.toLowerCase()}`,
          },
        };
        // 若起始节点为网关节点则保留分支表达式
        if (gateways[sourceInfo.id]) {
          const { conditions, default_condition: defaultCondition } = gateways[sourceInfo.id];
          if (conditions) {
            const tagCode = `branch_${sourceInfo.id}_${targetInfo.id}`;
            conditions.tag = tagCode;
            let conditionInfo = conditions[sourceLine.id];
            if (defaultCondition && defaultCondition.flow_id === sourceLine.id) {
              defaultCondition.tag = tagCode;
              conditionInfo = { ...defaultCondition, defaultCondition };
            }
            edgeInfo.data = { conditionInfo };
          }
        }
        this.createEdge(edgeInfo);
        // 更新竖向布局
        this.nodeTargetMaps = this.getNodeTargetMaps();
        this.nodeSourceMap = this.getNodeSourceMaps();
        this.updateVerticalLayout('delete', sourceInfo.id);
        // 更新横向布局
        this.updateHorizontalLayout(sourceGatewayId);

        this.$emit('updateShortcutPanel');
      },
      // 更新横向布局
      updateHorizontalLayout(gwId) {
        if (!gwId) return;
        const gwCell = this.getNodeInstance(gwId);
        const groupCell = gwCell.parent;
        const { x, y } = gwCell.position();
        // 网关中线
        const xLine = x + 34 / 2;
        const yLine = y + 34 + 40;
        // 网关输出输出连线
        const { outgoing: targetLines = [] } = utilsTools.deepClone(this.gateways[gwId]) || {};
        // 网关下的分组组群
        const childCells = targetLines.map((line) => {
          const targetNode = this.flows[line].target;
          const matchCell = groupCell.filterChild(cell => cell.getDescendants().find(item => item.id === targetNode));
          return matchCell[0];
        });
        // 中间项
        const middleIndex = Math.floor(targetLines.length / 2);
        const isEven = targetLines.length % 2 === 0;
        // 偶数列则添加一个空元素方便统一计算
        if (isEven) {
          targetLines.splice(middleIndex, 0, 'empty');
          childCells.splice(middleIndex, 0, 'empty');
        }
        // 遍历分支组群
        targetLines.forEach((lineId, index) => {
          // 左侧和居中
          if (middleIndex >= index) {
            // 分支组群实例和坐标尺寸
            const groupIndex = middleIndex - index;
            const childCell = childCells[groupIndex];
            if (childCell === 'empty') return;
            const { x: cX } = childCell.position();
            const { width: cW } = childCell.size();
            // 重置连线id
            lineId = targetLines[groupIndex];
            // 居中
            if (index === 0) {
              const targetNode = this.flows[lineId].target;
              const targetNodeCell = this.getNodeInstance(targetNode);
              const { x: cNX } = targetNodeCell.position();
              const { width: cNW } = targetNodeCell.size();
              childCell.position(xLine - cNX - cNW / 2 + cX, yLine, { deep: true });
            } else {
              // 左侧
              const nextChildCell = childCells[groupIndex + 1];
              const nCX = nextChildCell === 'empty' ? xLine + 20 : nextChildCell.position().x;
              childCell.position(nCX - 40 - cW, yLine, { deep: true });
            }
            // 更新分支网关与分组组群的连线
            let direction = index === 0 ? 'bottom' : 'left';
            this.updateEdgePortArrow({ type: 'source', lineId, nodeId: gwId, arrow: direction });
            // 更新分组组群与汇聚网关的连线
            const groupOutputLine = this.getGroupOutputLine(childCell.id);
            lineId = groupOutputLine.id;
            const convergeNode = this.flows[lineId].target;
            direction = index === 0 ? 'top' : 'left';
            this.updateEdgePortArrow({ type: 'target', lineId, nodeId: convergeNode, arrow: direction });
          } else {
            // 右侧
            const childCell = childCells[index];
            const prevChildCell = childCells[index - 1];
            const pCX = prevChildCell === 'empty' ? xLine - 20 : prevChildCell.position().x;
            const pCW = prevChildCell === 'empty' ? 0 : prevChildCell.size().width;
            childCell.position(pCX + pCW + 40, yLine, { deep: true });
            // 更新分支网关与分组组群的连线
            this.updateEdgePortArrow({ type: 'source', lineId, nodeId: gwId, arrow: 'right' });
            // 更新分组组群与汇聚网关的连线
            const groupOutputLine = this.getGroupOutputLine(childCell.id);
            lineId = groupOutputLine.id;
            const convergeNode = this.flows[lineId].target;
            this.updateEdgePortArrow({ type: 'target', lineId, nodeId: convergeNode, arrow: 'right' });
          }
        });
        // 向上递归
        const { sourceGatewayId } = gwCell.data;
        if (sourceGatewayId) {
          this.updateHorizontalLayout(sourceGatewayId);
        }
      },
      // 获取分组的输出连线
      getGroupOutputLine(groupId) {
        const groupCell = this.getNodeInstance(groupId);
        let nodeY = 0;
        let groupOutputNode = null;
        groupCell.getDescendants().forEach((cell) => {
          if (cell.shape !== 'custom-node' || cell.data.type === 'group') return;
          const { y: cellY } = cell.position();
          nodeY = cellY > nodeY ? cellY : nodeY;
          groupOutputNode = cellY === nodeY ? cell : groupOutputNode;
        });
        const groupOutputLine = this.lines.find(line => line.source.id === groupOutputNode.id);
        return groupOutputLine;
      },
      // 更新连线
      updateEdgePortArrow({ type, lineId, nodeId, arrow }) {
        if (lineId === 'empty') return;
        const edgeCell = this.getEdgeInstance(lineId);
        edgeCell[type === 'source' ? 'setSource' : 'setTarget']({
          cell: nodeId,
          port: `port_${arrow.toLowerCase()}`,
        });
      },
      // 更新竖向布局
      updateVerticalLayout(type = 'add', nodeId, nodeHeight) {
        if (nodeId === this.endNode.id) return;
        // 新增节点
        if (type === 'add') {
          let targetId = this.nodeTargetMaps[nodeId];
          let nodeCell = this.getNodeInstance(nodeId);
          if (this.branchGatewayId.includes(nodeCell.data.type)) {
            // 网关新增分支
            if (nodeHeight) {
              const { converge_gateway_id: convergeId } = this.gateways[nodeId];
              targetId = [convergeId];
            } else {
              nodeCell = nodeCell.parent;
              const { converge_gateway_id: convergeId } = this.gateways[nodeId];
              targetId = this.nodeTargetMaps[convergeId];
            }
          }
          const { y } = nodeCell.position();
          const { height } = nodeCell.size();
          let targetY = y + height + 60 + nodeHeight;
          if (nodeCell.data.type === 'group') {
            targetY = targetY - 20;
          }
          let nextNodeCell = this.getNodeInstance(targetId[0]);
          if (this.branchGatewayId.includes(nextNodeCell.data.type)) {
            nextNodeCell = nextNodeCell.parent;
          }
          const { y: nY } = nextNodeCell.position();
          if (nextNodeCell.data.type === 'group') {
            targetY = targetY - 20;
          }
          if (targetY > nY) {
            nextNodeCell.translate(0, targetY - nY);
            this.updateVerticalLayout(type, targetId[0], 0);
          }
        } else if (type === 'delete') {
          // 删除节点
          let targetId = this.nodeTargetMaps[nodeId][0];
          let nodeCell = this.getNodeInstance(nodeId);
          if (this.branchGatewayId.includes(nodeCell.data.type)) {
            nodeCell = nodeCell.parent;
            const { converge_gateway_id: convergeId } = this.gateways[nodeId];
            targetId = convergeId;
          }
          let nextNodeCell = this.getNodeInstance(targetId);
          if (this.branchGatewayId.includes(nextNodeCell.data.type)) {
            nextNodeCell = nextNodeCell.parent;
          }
          const { y: nY } = nextNodeCell.position();

          const targetY = [];
          // 检查节点与所有的输入节点之间距离
          const sourceIds = this.nodeSourceMap[targetId];
          const isMatch = sourceIds.every((sourceId) => {
            const sourceNodeCell = this.getNodeInstance(sourceId);
            const { y: sourceY } = sourceNodeCell.position();
            const { height: sourceHeight } = sourceNodeCell.size();
            targetY.push(sourceY + sourceHeight + 60);
            return nY > sourceY + sourceHeight + 60;
          });
          if (isMatch) {
            const maxY = Math.max(...targetY);
            nextNodeCell.translate(0, maxY - nY);
            this.updateVerticalLayout(type, targetId);
          }
        }
      },
      // 输入节点映射
      getNodeSourceMaps() {
        return this.lines.reduce((acc, cur) => {
          const { source, target } = cur;
          if (acc[target.id]) {
            acc[target.id].push(source.id);
          } else {
            acc[target.id] = [source.id];
          }
          return acc;
        }, {});
      },
    },
  };
</script>
<style lang="scss">
.shortcut-panel {
  position: absolute;
  width: 128px;
  background: rgba(255, 255, 255, .9);
  cursor: default;
  z-index: 6;
  .nodes-wrap {
    display: flex;
    align-items: center;
    justify-content: left;
    flex-wrap: wrap;
    padding: 9px 12px 0px;
    width: 128px;
    overflow: hidden;
    border-radius: 4px;
    .nodes-item {
      margin-bottom: 10px;
      width: 24px;
      height: 24px;
      line-height: 24px;
      text-align: center;
      font-size: 24px;
      color: #52699d;
      cursor: pointer;
      &:not(:nth-child(3n)) {
        margin-right: 16px;
      }
      &:hover {
        color: #3a84ff;
      }
      &.common-icon-node-tasknode-shortcut,
      &.common-icon-node-subflow-shortcut {
        font-size: 18px;
      }
    }
  }
  .operate-btn-wrap {
    padding: 6px 12px;
    text-align: left;
    background: #f5f7fa;
    .btn-item {
      display: inline-block;
      margin-left: 8px;
      color: #52699d;
      font-size: 16px;
      cursor: pointer;
      &:hover {
        color: #3a84ff;
      }
      &:first-child {
        margin-left: 0;
      }
    }
  }
}
</style>
