
// 布局配置常量
const LAYOUT_CONFIG = {
  baseX: 40,
  baseY: 134,
  horizontalSpacing: 46,
  verticalSpacing: 46,
  branchOffset: 168,
};

// 节点尺寸映射
const NODE_SIZES = {
  ServiceActivity: { width: 154, height: 54 },
  default: { width: 34, height: 34 },
  SubProcess: { width: 154, height: 54 },
};

// 节点类型映射
const NODE_TYPE_MAPPING = {
  ServiceActivity: 'tasknode',
  EmptyStartEvent: 'startpoint',
  EmptyEndEvent: 'endpoint',
  ExclusiveGateway: 'branchgateway',
  ParallelGateway: 'parallelgateway',
  ConditionalParallelGateway: 'conditionalparallelgateway',
  ConvergeGateway: 'convergegateway',
  SubProcess: 'subflow'
};

// 状态管理
let state = {
  nodes: {},
  flows: {},
  visited: new Set(),
  visitedConvergeNode: new Set(),
  nodePositions: new Map(),
  branchVisitedNodes: new Map(),
};

// 主布局函数
export const formatLayout = (nodes, flows) => {
  initState(nodes, flows);

  const startNode = findStartNode();
  updateFlowLayout(startNode, LAYOUT_CONFIG.baseX, LAYOUT_CONFIG.baseY);

  return generateResult();
};

// 初始化状态
const initState = (nodes, flows) => {
  state = {
    nodes,
    flows,
    visited: new Set(),
    visitedConvergeNode: new Set(),
    nodePositions: new Map(),
    branchVisitedNodes: new Map(),
  };
};

// 查找开始节点
const findStartNode = () => Object.values(state.nodes).find(node => node.type === 'EmptyStartEvent');

// 生成结果
const generateResult = () => ({
  locations: generateLocations(),
  lines: generateLines(),
});

// 生成节点位置数据
const generateLocations = () => Array.from(state.nodePositions.keys()).map(nodeId => ({
  id: nodeId,
  ...state.nodePositions.get(nodeId),
  type: NODE_TYPE_MAPPING[state.nodes[nodeId].type] || '',
  name: state.nodes[nodeId].name || '',
}));

// 生成连线数据
const generateLines = () => Object.values(state.flows).map(flow => ({
  id: flow.id,
  source: { arrow: flow.sourcePort, id: flow.source },
  target: { arrow: flow.targetPort, id: flow.target },
}));

// 核心布局逻辑
const updateFlowLayout = (node, x, y) => {
  if (!node || state.visited.has(node.id)) return;

  // 记录节点位置
  recordNodePosition(node, x, y);

  // 结束节点不继续处理
  if (node.type === 'EmptyEndEvent') return;

  const edges = getOutgoingEdges(node.id);
  if (!edges.length) return;

  if (edges.length > 1) {
    processBranchNode(node, edges);
  } else {
    processSingleEdge(node, edges[0]);
  }
};

// 记录节点位置
const recordNodePosition = (node, x, y) => {
  const size = getNodeSize(node);
  state.nodePositions.set(node.id, { x, y, ...size });
  state.visited.add(node.id);
};

// 获取节点尺寸
const getNodeSize = node => NODE_SIZES[node.type] || NODE_SIZES.default;

// 获取节点的出边
const getOutgoingEdges = nodeId => Object.values(state.flows).filter(flow => flow.source === nodeId);

// 处理分支节点
const processBranchNode = (node, edges) => {
  const sortedEdges = sortBranches(edges);

  sortedEdges.forEach((edge, index) => {
    const targetNode = state.nodes[edge.target];
    const position = calculateNodePosition(node, targetNode, index, sortedEdges);

    updateFlowLayout(targetNode, position.x, position.y);
    updateEdgePort(edge, index);
  });

  adjustBranchPositions(sortedEdges);
};

// 处理单一边
const processSingleEdge = (node, edge) => {
  const targetNode = state.nodes[edge.target];
  const position = calculateNodePosition(node, targetNode);

  updateFlowLayout(targetNode, position.x, position.y);
  updateEdgePort(edge);
};

// 计算节点位置
const calculateNodePosition = (sourceNode, targetNode, index = 0, edges) => {
  const sourcePos = state.nodePositions.get(sourceNode.id);
  const targetSize = getNodeSize(targetNode);
  const isBranchNode = ['ExclusiveGateway', 'ConditionalParallelGateway'].includes(sourceNode.type);

  // 计算X坐标
  let x = sourcePos.x + sourcePos.width;
  x += isBranchNode ? LAYOUT_CONFIG.branchOffset : LAYOUT_CONFIG.horizontalSpacing;

  // 如果不是第一个分支，检查是否需要对齐前一个分支
  if (index > 0) {
    const prevBranchPos = state.nodePositions.get(edges[index - 1].target);
    x = Math.max(x, prevBranchPos.x);
  }

  // 计算Y坐标
  const y = index === 0
    ? sourcePos.y + sourcePos.height / 2 - targetSize.height / 2
    : calculateBranchYPosition(index, edges);

  return { x, y };
};

// 更新边的输入输出端点
const updateEdgePort = (edge, index = 0) => {
  const sourcePort = index === 0 ? 'Right' : 'Bottom';
  const targetPort = state.visitedConvergeNode.has(edge.target) ? 'Bottom' : 'Left';

  // 该目标节点第一次访问时输入端点为Left，后续为Bottom
  state.visitedConvergeNode.add(edge.target);

  edge.sourcePort = sourcePort;
  edge.targetPort = targetPort;
};

// 分支排序
const sortBranches = (edges) => {
  const branchDepths = new Map();

  edges.forEach((edge) => {
    const visited = new Set();
    const depth = calculateBranchDepth(edge.target, visited);
    branchDepths.set(edge.id, depth);
    state.branchVisitedNodes.set(edge.id, visited);
  });

  // 如果所有分支深度相同，保持原顺序
  if (new Set(branchDepths.values()).size === 1) {
    return edges;
  }

  // 按深度降序排序
  return [...edges].sort((a, b) => branchDepths.get(b.id) - branchDepths.get(a.id));
};

// 计算分支深度
const calculateBranchDepth = (nodeId, visited) => {
  if (!nodeId || visited.has(nodeId)) return 0;
  visited.add(nodeId);

  const node = state.nodes[nodeId];
  if (!node || node.type === 'EmptyEndEvent') return 0;

  const edges = getOutgoingEdges(node.id);
  if (!edges.length) return 1;

  let maxDepth = 0;
  edges.forEach((edge) => {
    maxDepth = Math.max(maxDepth, calculateBranchDepth(edge.target, visited));
  });

  return 1 + maxDepth;
};

// 查找汇聚节点
const findConvergenceNode = (edges) => {
  const branchPaths = edges.map(edge => Array.from(state.branchVisitedNodes.get(edge.id) || []));

  if (!branchPaths.length) return null;

  // 查找所有分支共有的第一个节点
  for (const nodeId of branchPaths[0]) {
    if (branchPaths.every(path => path.includes(nodeId))) {
      return nodeId;
    }
  }

  return null;
};

// 调整分支位置
const adjustBranchPositions = (edges) => {
  edges.reduce((acc, edge, index) => {
    // 获取当前分支路径和汇聚节点
    const prevEdges = index === 0 ? edges : edges.slice(0, index + 1);
    const convergeNode = findConvergenceNode(prevEdges);
    const branchNodes = getBranchNodes(edge, convergeNode);

    // 如果没有分支节点，直接返回当前累积结果
    if (!branchNodes.length) return acc;

    // 获取分支第一个节点及其位置
    const firstNode = state.nodes[branchNodes[0]];
    const firstNodePos = state.nodePositions.get(firstNode.id);

    // 如果是第一个分支，初始化累积结果
    if (index === 0) {
      return { [index]: branchNodes };
    };

    // 获取前一个分支目标节点的位置信息
    const { y: prevY, height: prevHeight } = state.nodePositions.get(edges[index - 1].target);

    // 获取前面所有分支的节点
    const frontBranchNodes = [...new Set(Object.values(acc).flat())];

    // 筛选出在前一个分支下方的节点
    const nodesBelowPrevBranch = frontBranchNodes
      .map(nodeId => state.nodePositions.get(nodeId))
      .filter(nodePos => nodePos.y > (prevY + prevHeight));

    // 如果没有下方节点，进行简单调整
    if (nodesBelowPrevBranch.length === 0) {
      if (firstNodePos.y > (prevY + prevHeight + LAYOUT_CONFIG.verticalSpacing)) {
        resetNodesAndReposition(branchNodes, firstNode, {
          x: firstNodePos.x,
          y: prevY + prevHeight + LAYOUT_CONFIG.horizontalSpacing,
        });
      }
      return { ...acc, [index]: branchNodes };
    }

    // 计算最小X坐标和最大X坐标
    const minX = Math.min(...nodesBelowPrevBranch.map(node => node.x));
    const maxX = calculateMaxXPosition([...branchNodes, convergeNode]);

    // 计算目标Y坐标
    const targetY  = calculateBranchYPosition(index, edges);

    if ((maxX + LAYOUT_CONFIG.horizontalSpacing) < minX || firstNodePos.y !== targetY) {
      resetNodesAndReposition(branchNodes, firstNode, {
        x: firstNodePos.x,
        y: prevY + prevHeight + LAYOUT_CONFIG.horizontalSpacing,
      });
    }

    return Object.assign(acc, { [index]: branchNodes });
  }, {});
};

// 计算最大X坐标
const calculateMaxXPosition = nodeIds => nodeIds.reduce((max, nodeId) => {
  const { x, width } = state.nodePositions.get(nodeId) || { x: 0, width: 0 };
  return Math.max(max, x + width);
}, 0);

// 重置节点并重新定位
const resetNodesAndReposition = (nodeIds, firstNode, newPosition) => {
  // 重置节点状态
  nodeIds.forEach((nodeId) => {
    state.visited.delete(nodeId);
    state.visitedConvergeNode.delete(nodeId);
  });

  // 重新布局第一个节点
  updateFlowLayout(firstNode, newPosition.x, newPosition.y);
};

// 获取分支节点
const getBranchNodes = (edge, convergeNode) => {
  let branchNodes = Array.from(state.branchVisitedNodes.get(edge.id));
  const convergeNodeIndex = branchNodes.findIndex(nodeId => nodeId === convergeNode);

  if (convergeNodeIndex !== -1) {
    branchNodes = branchNodes.slice(0, convergeNodeIndex);
  }

  const nodes = [...branchNodes];

  branchNodes.forEach((node) => {
    const outgoingEdges = getOutgoingEdges(node);
    if (outgoingEdges.length > 1) {
      outgoingEdges.forEach((item) => {
        const childNodes = getBranchNodes(item, convergeNode);
        nodes.push(...childNodes);
      });
    }
  });
  return nodes;
};

// 计算分支Y坐标
const calculateBranchYPosition = (index, edges) => {
  const prevEdge = edges[index - 1];
  const prevNodes = state.branchVisitedNodes.get(prevEdge.id) || [];

  // 找出前一个分支中最下方的节点
  let maxY = 0;
  let maxHeight = 0;

  prevNodes.forEach((nodeId) => {
    const pos = state.nodePositions.get(nodeId);
    if (pos && pos.y > maxY) {
      maxY = pos.y;
      maxHeight = pos.height;
    }
  });

  return maxY + maxHeight + LAYOUT_CONFIG.verticalSpacing;
};
