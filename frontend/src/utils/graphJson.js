import { random4 } from '@/utils/uuid.js';
import { formatLayout } from './formatLayout';
import tools from '@/utils/tools.js';
import store from '@/store';

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
  const { locations, lines, canvasMode } = canvasData;
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
    const { id, x, y, type } = cur;
    const isTaskNode = ['tasknode', 'subflow'].includes(type);
    const cell = {
      id,
      shape: 'custom-node',
      position: { x, y },
      size: {
        height: isTaskNode ? 54 : 34,
        width: isTaskNode ? 154 : 34,
      },
      parent: cur.parent || undefined,
      data: {
        ...cur,
        type: nodeCompMap[type],
      },
    };
    acc.push(cell);
    return acc;
  }, []) || [];
  const edgeCell = lines.reduce((acc, cur) => {
    const { id, source, target } = cur;
    acc.push({
      shape: 'edge',
      id,
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
      zIndex: 0,
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

    return graphToJson(graphData);
  } catch (error) {
    console.warn(error);
    return [];
  }
};
