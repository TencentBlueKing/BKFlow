import { random4 } from '@/utils/uuid.js';
import { formatLayout } from './formatLayout';
import tools from '@/utils/tools.js';
import store from '@/store';

/**
 * 展平嵌套 pipelineTree：将 SubCanvas 的 pipeline 中 location/line 递归展开到顶层数组
 * @param {Array} locations - 顶层 location 数组
 * @param {Array} lines - 顶层 line 数组
 * @param {Object} activities - 顶层 activities（可能含嵌套 pipelineTree 的 loopGroupNode）
 * @returns {{ locations: Array, lines: Array }}
 */
function flattenNestedPipelineTreeData(locations, lines, activities, isExecuteMode = null) {
  const flatLocations = [...locations];
  const flatLines = [...lines];
  if (isExecuteMode === null) {
    isExecuteMode = locations.some(loc => loc.mode === 'execute');
  }
  Object.values(activities || {}).forEach((act) => {
    const isSubCanvas = act.type === 'SubCanvas' || (act.component && act.component.code === 'subcanvas_plugin');
    if (!isSubCanvas || !act.pipeline) return;
    const pt = act.pipeline;
    // 递归添加子节点的location
    (pt.location || []).forEach((loc) => {
      const code = loc.type === 'tasknode' ? (pt.activities?.[loc.id]?.component?.code || '') : '';
      const childLoc = {
        ...loc,
        parent: act.id,
        checked: true,
        code,
      };
      // 只有在任务执行页才设置 mode: 'execute'，编辑页不设置
      if (isExecuteMode) {
        childLoc.ready = true;
        childLoc.mode = 'execute';
      }
      flatLocations.push(childLoc);
    });
    // 添加子节点的 line（带 parent 标记）
    (pt.line || []).forEach((l) => {
      flatLines.push({
        ...l,
        parent: act.id,
      });
    });
    // 递归处理子 pipeline 中可能嵌套的 SubCanvas（保持 isExecuteMode 上下文）
    if (pt.activities) {
      const nested = flattenNestedPipelineTreeData([], [], pt.activities, isExecuteMode);
      flatLocations.push(...nested.locations);
      flatLines.push(...nested.lines);
    }
  });

  return { locations: flatLocations, lines: flatLines };
}

function getNodeTargetMaps(lines) {
  return lines.reduce((acc, cur) => {
    const { source, target } = cur;
    if (acc[source.id]) {
      acc[source.id].push(target.id);
    } else {
      acc[source.id] = [target.id];
    }
    return acc;
  }, {});
}

function getGroupInfo(params = {}) {
  const { groupInfo, nodeId, nodeTargetMaps, canvasData, gatewayId } = params;
  if (!nodeId) return;

  const targetNodes = nodeTargetMaps[nodeId] || [];
  const info = canvasData.locations.find(item => item.id === nodeId);

  // 组群Id
  let { groupId } = params;
  if (!groupId) {
    groupId = `group_${random4()}`;
    groupInfo[groupId] = '';
  }
  // 添加parent、sourceGatewayId字段
  if (info && info.type === 'endpoint') {
    const startInfo = canvasData.locations.find(item => item.type === 'startpoint');
    info.parent = startInfo.parent;
  } else {
    info.parent = groupId;
    info.sourceGatewayId = gatewayId;
  }

  if (targetNodes.length > 1) {
    // 分支网关
    const parentGroupId = `group_${random4()}`;
    info.parent = parentGroupId;
    groupInfo[parentGroupId] = groupId;
    // 遍历分支
    targetNodes.forEach((item) => {
      const childGroupId = `group_${random4()}`;
      // 记录上级群组
      groupInfo[childGroupId] = parentGroupId;
      getGroupInfo({
        ...params,
        nodeId: item,
        gatewayId: nodeId,
        groupId: childGroupId,
      });
    });
  } else {
    // 分支网关对应的汇聚网关
    if (info.type === 'convergegateway') {
      const gatewayInfo = Object.values(canvasData.gateways).find(item => item.converge_gateway_id === nodeId);
      if (gatewayInfo) {
        const convergeInfo = canvasData.locations.find(item => item.id === gatewayInfo.id);
        info.parent = convergeInfo.parent;
        groupId = convergeInfo.parent;
      }
    }
    getGroupInfo({
      ...params,
      groupId,
      nodeId: targetNodes[0],
    });
  }
};

export const graphToJson = (canvasData) => {
  // 展平循环流节点的嵌套 pipelineTree 数据（location + line）
  // 优先使用传入的activities（如子流程执行画布），否则回退到全局模板activities
  const activities = canvasData.activities || store.state.template?.activities || {};
  const { locations: flatLocations, lines: flatLines } = flattenNestedPipelineTreeData(
    canvasData.locations,
    canvasData.lines,
    activities,
  );
  const locations = flatLocations;
  const lines = flatLines;
  const { canvasMode } = canvasData;
  const nodeCompMap = {
    startpoint: 'start',
    endpoint: 'end',
    start: 'start',
    end: 'end',
    tasknode: 'task',
    subflow: 'subflow', // 最终画布node.getData()的type
    branchgateway: 'branch-gateway',
    parallelgateway: 'parallel-gateway',
    conditionalparallelgateway: 'conditional-parallel-gateway',
    convergegateway: 'converge-gateway',
  };
  // 节点输出字典
  const nodeTargetMaps = getNodeTargetMaps(lines);
  // 竖版画布群组信息字典
  const groupInfo = {};
  if (canvasMode === 'vertical') {
    getGroupInfo({
      groupInfo,
      nodeId: locations[0].id,
      nodeTargetMaps,
      canvasData,
    });
  }
  const groupCell = Object.keys(groupInfo).reduce((acc, cur) => {
    const group = {
      id: cur,
      shape: 'custom-node',
      parent: groupInfo[cur] || undefined,
      zIndex: 1,
      data: {
        type: 'group',
        parent: groupInfo[cur],
      },
    };
    acc.push(group);
    return acc;
  }, []) || [];

  const nodeCell = locations.reduce((acc, cur) => {
    const { id, x, y, type, width: locWidth, height: locHeight, ...curData } = cur;
    const isTaskNode = ['tasknode', 'subflow'].includes(type);
    const isLoopGroup = type === 'SubCanvas';
    const shape = isLoopGroup ? 'custom-loop-group-node' : 'custom-node';
    // 直接从 location 中读取持久化的 width/height，无则使用默认值
    let nodeWidth = 34;
    let nodeHeight = 34;
    if (isTaskNode) {
      nodeWidth = 154;
      nodeHeight = 54;
    } else if (isLoopGroup) {
      nodeWidth = locWidth || 415;
      nodeHeight = locHeight || 158;
    }
    const cell = {
      id,
      shape,
      position: { x, y },
      size: {
        height: nodeHeight,
        width: nodeWidth,
      },
      parent: cur.parent || undefined,
      data: {
        ...curData,
        type: isLoopGroup ? 'SubCanvas' : nodeCompMap[type],
        // 循环容器节点需要标记 parent: true
        ...(isLoopGroup ? { parent: true } : {}),
      },
    };
    acc.push(cell);
    return acc;
  }, []);
  const edgeCell = lines.reduce((acc, cur) => {
    const { id, source, target } = cur;
    acc.push({
      shape: 'edge',
      id,
      parent: cur.parent || undefined,
      source: {
        cell: source.id,
        port: `port_${source.arrow.toLowerCase()}`,
      },
      target: {
        cell: target.id,
        port: `port_${target.arrow.toLowerCase()}`,
      },
      attrs: {
        line: {
          stroke: '#a9adb6',
          strokeWidth: 2,
          targetMarker: {
            name: 'block',
            width: 6,
            height: 8,
          },
          class: id,
        },
      },
      router: {
        name: 'manhattan',
        args: {
          padding: 1,
        },
      },
      data: {},
    });
    return acc;
  }, []) || [];
  return [...groupCell, ...nodeCell, ...edgeCell];
};


export const generateGraphData = (pipelineTree) => {
  const {
    activities = {},
    flows = [],
    gateways = {},
    start_event: start,
    end_event: end,
  } = tools.deepClone(pipelineTree);

  const nodes = {
    ...activities,
    ...gateways,
    [start.id]: start,
    [end.id]: end,
  };

  try {
    const graphData = formatLayout(nodes, flows);

    // 更新节点树
    store.commit('template/setPipelineTree', {
      ...pipelineTree,
      location: graphData.locations,
      line: graphData.lines,
    });

    return graphToJson({
      ...graphData,
      canvasMode: pipelineTree.canvas_mode,
    });
  } catch (error) {
    console.warn(error);
    return [];
  }
};
