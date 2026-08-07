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
        :class="['nodes-item', item.key === 'SubCanvas' ? 'subcanvas-node-item' : `common-icon-node-${item.key}-shortcut`]"
        @click.stop="onAppendNode(item.id)">
        <img
          v-if="item.key === 'SubCanvas'"
          class="node-subcanvas-icon"
          :src="subcanvasIcon">
      </li>
    </ul>
    <ul
      v-if="operate || nodeType === 'edge'"
      class="operate-btn-wrap">
      <template v-if="operate">
        <li
          v-bk-tooltips="{
            content: '复制节点',
            delay: 500
          }"
          data-test-id="templateCanvas_panel_nodeCopy"
          class="btn-item common-icon-bkflow-copy"
          @click.stop="onAppendNode(activeCell.data.type, true)" />
        <li
          v-bk-tooltips="{
            content: '复制并插入',
            delay: 500
          }"
          data-test-id="templateCanvas_panel_nodeCopyInsert"
          class="btn-item common-icon-bkflow-copy-insert"
          @click.stop="onAppendNode(activeCell.data.type, true, true)" />
        <li
          v-bk-tooltips="{
            content: '解除连线',
            delay: 500
          }"
          data-test-id="templateCanvas_panel_nodeDisconnect"
          class="btn-item common-icon-bkflow-disconnect"
          @click.stop="$emit('onNodeRemove', activeCell, false)" />
        <li
          v-bk-tooltips="{
            content: '删除节点',
            delay: 500
          }"
          data-test-id="templateCanvas_panel_nodeDelete"
          class="btn-item common-icon-bkflow-delete"
          @click.stop="$emit('onNodeRemove', activeCell)" />
      </template>
      <li
        v-if="nodeType === 'edge'"
        v-bk-tooltips="{
          content: '删除连线',
          delay: 500
        }"
        data-test-id="templateCanvas_panel_lineDelete"
        class="btn-item common-icon-bkflow-delete"
        @click.stop="onDeleteLineClick" />
    </ul>
  </div>
</template>
<script>
  import { Graph, Cell } from '@antv/x6';
  import { uuid } from '@/utils/uuid.js';
  import { mapState } from 'vuex';
  import utilsTools from '@/utils/tools.js';
  import subcanvasIcon from '@/assets/images/subcanvas-node-icon.svg';
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
        nodeType: '',
        operate: '',
        subcanvasIcon,
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
      // 当前活跃节点/边所属的循环容器父节点ID
      loopGroupParentId() {
        if (!this.activeCell) return null;
        if (this.activeCell.shape === 'edge') {
          // 边的情况：直接检查源/目标 X6 cell 的父节点
          const sourceCell = this.activeCell.getSourceCell();
          const targetCell = this.activeCell.getTargetCell();
          const sourceParent = sourceCell?.getParent?.();
          const targetParent = targetCell?.getParent?.();
          if (sourceParent?.shape === 'custom-loop-group-node') return sourceParent.id;
          if (targetParent?.shape === 'custom-loop-group-node') return targetParent.id;
          return null;
        }
        const parent = this.activeCell.getParent();
        return (parent?.shape === 'custom-loop-group-node') ? parent.id : null;
      },
      // 当前活跃节点/边是否在循环容器内部
      isInLoopGroup() {
        return !!this.loopGroupParentId;
      },
      innerPipelineTree() {
        if (!this.loopGroupParentId) return null;
        return this.activities[this.loopGroupParentId]?.pipeline || null; // eslint-disable-line camelcase
      },
      effectiveLines() {
        if (this.isInLoopGroup && this.innerPipelineTree?.line) {
          return this.innerPipelineTree.line;
        }
        return this.lines;
      },
      effectiveLocations() {
        if (this.isInLoopGroup && this.innerPipelineTree?.location) {
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
          return this.innerPipelineTree.location.map(loc => ({
            ...loc,
            type: innerToOuterTypeMap[loc.type] || loc.type,
          }));
        }
        return this.locations;
      },
      effectiveGateways() {
        if (this.isInLoopGroup && this.innerPipelineTree?.gateways) {
          return this.innerPipelineTree.gateways;
        }
        return this.gateways;
      },
      nodeTypeList() {
        const list = [
          { key: 'tasknode', id: 'task', tips: this.$t('标准插件节点') },
          { key: 'subflow', id: 'subflow', tips: '子流程节点' },
          { key: 'branchgateway', id: 'branch-gateway', tips: this.$t('分支网关') },
          { key: 'parallelgateway', id: 'parallel-gateway', tips: this.$t('并行网关') },
          { key: 'conditionalparallelgateway', id: 'conditional-parallel-gateway', tips: this.$t('条件并行网关') },
          { key: 'convergegateway', id: 'converge-gateway', tips: this.$t('汇聚网关') },
          { key: 'SubCanvas', id: 'SubCanvas', tips: this.$t('循环节点') },
        ];
        // 循环流分组内部不允许添加循环流节点（禁止嵌套）
        if (this.activeCell.data.type === 'parallel-gateway') {
          return list.filter(item => item.id !== 'converge-gateway' && !(this.isInLoopGroup && item.id === 'SubCanvas'));
        }
        if (this.isInLoopGroup) {
          return list.filter(item => !['subflow', 'SubCanvas'].includes(item.id));
        }
        return list;
      },
      branchConditions() {
        const branchConditions = {};
        const gateways = this.effectiveGateways;
        Object.keys(gateways).forEach((gKey) => {
          const item = gateways[gKey];
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
    },
    watch: {
      activeCell: {
        handler(val) {
          this.nodeType = val.shape === 'edge' ? 'edge' : 'node';
          this.operate = val.shape === 'edge' ? false : !['start', 'end'].includes(val.data.type);
        },
        immediate: true,
      },
    },
    methods: {
      /**
       * 添加节点
       * @param {String} type -添加节点类型
       */
      onAppendNode(type, isFillParam = false, insert = false) {
        // 获取新节点坐标：根据当前激活的节点或边确定新节点的位置
        let currLoc; let lineInfo;
        const { id, shape, data } = this.activeCell;
        if (shape === 'edge') {
          // 如果当前激活的是边，找到对应的边信息
          lineInfo = this.effectiveLines.find(line => line.id === id);
          const sourceId = lineInfo.source.id;
          const nodeInstance = this.getNodeInstance(sourceId);
          currLoc = {
            id: nodeInstance.id,
            type: nodeInstance.data.type,
            ...nodeInstance.position(),
            data: nodeInstance.data,
          };
        } else {
          const { x, y } = this.activeCell.position();
          currLoc = {
            id,
            type: data.type,
            x,
            y,
            data,
          };
        }
        // 如果是复制操作需要
        const nodeId = `node${uuid()}`;
        // 判断当前节点和待添加节点是否为网关类型
        const isGatewayCurrNode = currLoc.type.indexOf('gateway') > -1;
        const isGatewayAppendNode = type.indexOf('gateway') > -1;
        // 判断当前/待添加节点是否为循环流分组节点（SubCanvas）
        const isLoopGroupCurrNode = currLoc.type === 'SubCanvas';
        const isLoopGroupAppendNode = type === 'SubCanvas';
        // 循环流节点宽度自适应，需根据实际宽度偏移
        const xOffset = isLoopGroupCurrNode
          ? this.getNodeInstance(currLoc.id).getSize().width + 200
          : 200;
        // 判断当前节点是否在分组内（子节点），需要将新节点也加入同一分组
        let loopGroupParent = null;
        if (!isLoopGroupCurrNode && !isLoopGroupAppendNode) {
          if (shape === 'edge' && this.loopGroupParentId) {
            // 边在循环容器内部时，使用 computed 属性获取父节点
            loopGroupParent = this.getNodeInstance(this.loopGroupParentId);
          } else if (shape !== 'edge') {
            const parentNode = this.activeCell.getParent();
            if (parentNode && parentNode.shape === 'custom-loop-group-node') {
              loopGroupParent = parentNode;
            }
          }
        }
        let currNodeHeight = 54;
        if (isGatewayCurrNode) currNodeHeight = 34;
        else if (isLoopGroupCurrNode) currNodeHeight = 158;
        let appendNodeHeight = 54;
        if (isGatewayAppendNode) appendNodeHeight = 34;
        else if (isLoopGroupAppendNode) appendNodeHeight = 158;
        // 计算新节点的位置
        const location = {
          id: nodeId,
          y: currLoc.y + (currNodeHeight / 2) - (appendNodeHeight / 2),
          x: currLoc.x + xOffset,
          parent: loopGroupParent ? loopGroupParent.id : undefined,
        };
        // 初始化新节点的边信息
        let edges = [
          {
            source: {
              cell: currLoc.id,
              port: 'port_right',
            },
            target: {
              cell: nodeId,
              port: 'port_left',
            },
          },
        ];
        // 如果是复制操作且不需要插入，直接创建节点并返回
        if (isFillParam && !insert) {
          const copyData = type === 'SubCanvas' ? { ...currLoc.data, isCopy: true } : currLoc.data;
          const nodeInstance = this.createNode(type, location, copyData);
          nodeInstance.setData({ oldSouceId: id, id: nodeInstance.id }, { silent: false });
          // 如果当前节点在分组内，将新节点也加入同一分组
          if (loopGroupParent) {
            loopGroupParent.addChild(nodeInstance);
            nodeInstance.setData({ parent: loopGroupParent.id });
          }
          // 避免创建默认子节点/连线，由 copyLoopGroupLocationAndFlows 统一处理
          // 创建连接边（从当前节点到新复制节点）
          // edges.forEach((item) => {
          //   this.createEdge(item);
          // });
          // 添加选中态
          this.instance.select(nodeInstance);
          // 更新快捷面板
          this.$emit('updateShortcutPanel', nodeId);
          this.$emit('onLocationChange', 'copy', nodeInstance);
          // 分组容器自适应（如果新节点在分组内）
          if (loopGroupParent) {
            this.$emit('onFitCanvas', loopGroupParent.id);
          }
          return;
        }
        /**
         * 添加规则
         * 当前节点类型为并行/分支网管：都是 onAppendNode
         * 其他节点类型：后面有节点为插入，没有为追加
         * 由边打开的面板，都是插入
         */
        const isHaveNodeBehind = this.effectiveLines.find(line => line.source.id === (shape === 'edge' ? lineInfo.source.id : id));
        // 并行/分支网关类型节点
        const specialType = ['parallel-gateway', 'branch-gateway', 'conditional-parallel-gateway'];
        // 其他节点类型
        const otherType = ['task', 'subflow', 'converge-gateway', 'start', 'tasknode', 'SubCanvas'];
        // 插入逻辑
        if ((isHaveNodeBehind && otherType.indexOf(currLoc.type) > -1) || shape === 'edge') {
          if (shape === 'edge') {
            if (specialType.indexOf(currLoc.type) > -1) {
              const conditions = this.branchConditions;
              if (conditions[id] && Object.keys(conditions[id]).length > 1) {
                // 获取并行网关中最靠下的节点位置
                const { x: parallelX, y: parallelY } = this.getParallelNodeMinDistance(id);
                location.y = parallelY + 100;
                location.x = parallelX;
              }
            }
          } else {
            lineInfo = this.effectiveLines.find(line => line.source.id === id);
          }
          // 更新边信息
          edges = this.updateConnector({
            lineInfo,
            nodeId,
          });
        } else if (specialType.indexOf(currLoc.type) > -1 && isHaveNodeBehind) {
          // 如果网关分支已有输出连线则后续连线输出端点都由bottom出发
          edges[0].source.port = 'port_bottom';
          // 拿到并行中最靠下的节点
          const { x: parallelX, y: parallelY } = this.getParallelNodeMinDistance(id);
          location.y = parallelY + 100;
          location.x = parallelX;
        }
        // 克隆节点
        let nodeInstance;
        if (insert) {
          nodeInstance = this.createNode(type, location, currLoc.data);
          nodeInstance.setData({ oldSouceId: id, id: nodeInstance.id }, { silent: false });
          this.$emit('onLocationChange', 'copy', nodeInstance);
        } else { // 新建节点
          nodeInstance = this.createNode(type, location);
          this.$emit('onLocationChange', 'add', nodeInstance);
        }
        // 如果当前节点在分组内，将新节点也加入同一分组
        if (loopGroupParent) {
          loopGroupParent.addChild(nodeInstance);
          nodeInstance.setData({ parent: loopGroupParent.id });
        }
        // 新建边
        edges.forEach((item) => {
          this.createEdge(item);
        });
        // 更新快捷面板
        this.$emit('updateShortcutPanel', nodeId);
        // 分组容器自适应（如果新节点在分组内）
        if (loopGroupParent) {
          this.$emit('onFitCanvas', loopGroupParent.id);
        }
      },
      /**
       * 获得并行节点中最靠下面的节点
       * @param {String} nodeId 并行网管/分支网管
       */
      getParallelNodeMinDistance(nodeId) {
        const { x, y } = this.effectiveLocations.find(m => m.id === nodeId);
        const parallelNodes = this.effectiveLines.filter(m => m.source.id === nodeId).map(m => m.target.id);
        let maxDistance = null;
        // 距离网管节点垂直距离最近的节点
        let needNodeLocation = { x: x + 200, y }; // 默认新增节点坐标
        this.effectiveLocations.forEach((m) => {
          if (m.type === 'tasknode' && parallelNodes.indexOf(m.id) > -1) {
            if (maxDistance === null) {
              maxDistance = m.y - y;
              needNodeLocation = m;
            } else if (parallelNodes.indexOf(m.id) && m.y - y > maxDistance) {
              maxDistance = m.y - y;
              needNodeLocation = m;
            }
          }
        });
        return needNodeLocation;
      },
      // 更新连线
      updateConnector({ lineInfo, nodeId }) {
        const { id, source, target } = lineInfo;
        // 新联连线配置
        const edges = [
          {
            source: {
              cell: source.id,
              port: `port_${source.arrow.toLowerCase()}`,
            },
            target: {
              cell: nodeId,
              port: 'port_left',
            },
          },
          {
            source: {
              cell: nodeId,
              port: 'port_right',
            },
            target: {
              cell: target.id,
              port: `port_${target.arrow.toLowerCase()}`,
            },
          },
        ];
        // 拷贝插入节点前网关的配置
        const gateways = utilsTools.deepClone(this.effectiveGateways);
        // 如果通过线的面板插入节点，若起始节点为网关节点则保留分支表达式
        if (source.id in gateways) {
          const branchInfo = gateways[source.id];
          const { conditions, default_condition: defaultCondition } = branchInfo;
          if (conditions) {
            const tagCode = `branch_${source.id}_${nodeId}`;
            conditions.tag = tagCode;
            let conditionInfo = conditions[id];
            if (defaultCondition && defaultCondition.flow_id === id) {
              defaultCondition.tag = tagCode;
              conditionInfo = { ...defaultCondition, default_condition: defaultCondition };
            }
            // 将分支条件添加给新生成的第一条连线
            edges[0].data = { conditionInfo };
          }
        }
        // 删除旧的连线
        this.instance.removeEdge(id);
        this.$emit('onLineChange', 'delete', {
          id,
          source: edges[0].source,
          target: edges[1].target,
        });
        return edges;
      },
      createNode(type, location, data = {}) {
        if (type === 'SubCanvas') {
          return this.instance.addNode({
            id: `node${uuid()}`,
            ...location,
            shape: 'custom-loop-group-node',
            width: 415,
            height: 158,
            data: {
              ...data,
              type: 'SubCanvas',
              parent: true,
              name: '循环',
            },
            zIndex: 1,
          });
        }
        const isTask = type === 'task' || type === 'tasknode';
        const isSubflow = type === 'subflow' || type === 'SubProcess';
        return this.instance.addNode({
          id: `node${uuid()}`,
          ...location,
          shape: 'custom-node',
          width: isTask || isSubflow ? 154 : 34,
          height: isTask || isSubflow ? 54 : 34,
          data: {
            ...data,
            type,
          },
          zIndex: 6,
        });
      },
      // 创建边
      createEdge({ source, target, data = {}, router = {} }) {
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
              class: edgeId,
            },
          },
          data,
          zIndex: 10, // 边显示在分组节点（zIndex=1）和子节点（zIndex=10）上面
          router: Object.assign({
            name: 'manhattan',
            args: {
              padding: 1,
            },
          }, router),
        });
        this.$emit('onLineChange', 'add', {
          id: edgeId,
          source,
          target,
          data,
        });
      },
      // 获取单个对应的节点
      getNodeInstance(nodeId) {
        const nodes = this.instance.getNodes();
        return nodes.find(item => item.id === nodeId);
      },
      // 通过快捷面板删除连线
      onDeleteLineClick() {
        const info = this.effectiveLines.find(line => line.id === this.activeCell.id);
        // 先移除边（从 X6 图中删除），再触发 onLineChange 同步数据
        this.instance.removeEdge(info.id);
        this.$emit('onLineChange', 'delete', {
          id: info.id,
          source: { cell: info.source.id },
          target: { cell: info.target.id },
        });
        this.$emit('updateShortcutPanel');
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
      .node-subcanvas-icon {
        display: block;
        width: 24px;
        height: 24px;
        margin: 3px auto 0;
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
