import tools from '@/utils/tools.js';
import { NODE_DICT } from '@/constants/index.js';
import i18n from '@/config/i18n/index.js';
/**
 * @param {String} flowId - 连线ID
 * @param {Object} flows - 连线数据
 * @param {Object} activities - 节点数据
 * @param {Object} gateways - 网关数据
 * @param {Array} ordered - 已处理的有序节点列表
 * @param {Array} nodeIds - 已处理的节点ID列表
 * @param {Object} options - 配置选项
 * @param {Boolean} options.collectPath - 是否收集路径节点
 * @param {Boolean} options.returnTarget - 是否返回目标节点
 * @returns {Boolean|Object|Array|null} 根据配置返回不同类型的结果
 */
function traverseFlowPath(flowId, flows, activities, gateways, ordered, nodeIds, options = {}) {
  const { collectPath = false, returnTarget = false } = options;
  const flow = flows[flowId];
  if (!flow) {
    if (collectPath) {
      return [];
    }
    if (returnTarget) {
      return null;
    }
    return false;
  }
  const pathNodes = [];
  let currentNodeId = flow.target;
  const visitedNodes = new Set();
  if (!options.globalVisited) {
    options.globalVisited = new Set();
  }
  if (!options.depth) {
    options.depth = 0;
  }
  const isNodeProcessed = nodeId => ordered.some(item => item?.id === nodeId)
    || ((returnTarget || collectPath) && nodeIds.includes(nodeId));

  while (currentNodeId) {
    // 避免无限循环 - 检查当前路径和全局访问记录
    if (visitedNodes.has(currentNodeId) || options.globalVisited.has(currentNodeId)) {
      break;
    }
    visitedNodes.add(currentNodeId);
    options.globalVisited.add(currentNodeId);
    // 检查是否已经处理过的节点
    const isProcessed = isNodeProcessed(currentNodeId);
    if (isProcessed) {
      if (returnTarget) {
        return [activities[currentNodeId] || gateways[currentNodeId]];
      }
      if (collectPath) {
        break;
      }
      return true;
    }
    // 获取当前节点
    const currentNode = activities[currentNodeId] || gateways[currentNodeId];
    if (!currentNode) {
      break;
    }
    // 如果需要收集路径，则处理并添加当前节点
    if (collectPath) {
      const nodeClone = tools.deepClone(currentNode);
      if (activities[currentNodeId]) {
        // 非网关节点
        if (!nodeClone.title && nodeClone.name) {
          nodeClone.title = nodeClone.name;
        }
        if (nodeClone.expanded === undefined) {
          nodeClone.expanded = !(nodeClone.type === 'SubProcess' || nodeClone.component?.code === 'subprocess_plugin');
        }
        // 为子流程节点初始化children数组
        if (nodeClone.type === 'SubProcess' || nodeClone.component?.code === 'subprocess_plugin') {
          nodeClone.children = nodeClone.children || [];
        }
      } else if (gateways[currentNodeId]) {
        // 网关节点
        const name = NODE_DICT[nodeClone.type.toLowerCase()];
        nodeClone.title = nodeClone.title || name;
        nodeClone.name = nodeClone.name || name;
        nodeClone.children = nodeClone.children || [];
        nodeClone.expanded = false;
      }
      pathNodes.push(nodeClone);
    }
    // 获取下一个节点
    if (!currentNode.outgoing) {
      break;
    }
    const outgoingFlows = Array.isArray(currentNode.outgoing)
      ? currentNode.outgoing
      : [currentNode.outgoing];
    // 如果有多条outgoing，需要递归处理每一条
    if (outgoingFlows.length > 1) {
      const targetNodes = [];
      let hasLoop = false;
      for (const item of outgoingFlows) {
        // 为每个分支创建独立的选项对象，但共享全局访问记录
        const branchOptions = {
          returnTarget,
          collectPath,
          globalVisited: options.globalVisited,
          depth: options.depth + 1,
        };
        const result = traverseFlowPath(item, flows, activities, gateways, ordered, nodeIds, branchOptions);
        if (returnTarget && result) {
          // 如果是查找目标节点模式，收集所有目标节点
          if (Array.isArray(result)) {
            targetNodes.push(...result);
          } else {
            targetNodes.push(result);
          }
        } else if (!returnTarget && !collectPath && result === true) {
          // 如果是循环检测模式，只要有一个分支返回true就表示有循环
          hasLoop = true;
        } else if (collectPath && Array.isArray(result)) {
          // 如果是收集路径模式，合并所有路径
          targetNodes.push(...result);
        }
      }
      if (returnTarget) {
        return targetNodes.length > 0 ? targetNodes : null;
      } if (collectPath) {
        return pathNodes.concat(targetNodes);
      }
      return hasLoop;
    }
    // 单条连线，继续沿着这条线走
    const nextFlowId = outgoingFlows[0];
    const nextFlow = flows[nextFlowId];
    if (!nextFlow) break;
    currentNodeId = nextFlow.target;
  }
  if (collectPath) {
    return pathNodes;
  }
  if (returnTarget) {
    return null;
  }
  return false;
}

/**
 * 检查条件连线是否回退到已处理节点
 * @returns {Boolean} 是否为回退连线
 */
export function checkConditionLoop(flowId, flows, activities, gateways, ordered, nodeIds) {
  return traverseFlowPath(flowId, flows, activities, gateways, ordered, nodeIds);
}

/**
 * 查找回退的目标节点
 * @returns {Object|null} 回退的目标节点
 */
export function findLoopTarget(flowId, flows, activities, gateways, ordered, nodeIds) {
  return traverseFlowPath(flowId, flows, activities, gateways, ordered, nodeIds, {
    returnTarget: true,
  });
}

/**
 * 获取回退路径上的所有节点
 * @returns {Array} 回退路径上的所有节点
 */
export function getLoopPathNodes(flowId, flows, activities, gateways, ordered, nodeIds) {
  return traverseFlowPath(flowId, flows, activities, gateways, ordered, nodeIds, {
    collectPath: true,
  });
}

/**
 * 通过汇聚网关的incoming连线逐层往上寻找最近的网关节点
 * @param {Object} currentGateway - 当前汇聚网关节点
 * @param {Object} flows - 连线数据
 * @param {Object} activities - 活动节点数据
 * @param {Object} gateways - 网关节点数据
 * @param {Set} visited - 已访问的节点集合，防止循环引用
 * @returns {Object|null} 找到的最近网关节点，如果没找到返回null
 */
export function findNearestGatewayByIncoming(currentGateway, flows, activities, gateways) {
  const visited = new Set();
  if (visited.has(currentGateway.id)) {
    return null;
  }
  visited.add(currentGateway.id);
  // 遍历当前网关的所有入线
  for (const incomingFlowId of currentGateway.incoming) {
    const flow = flows[incomingFlowId];
    if (!flow) continue;
    // 获取入线的源节点
    const sourceNodeId = flow.source;
    const sourceNode = activities[sourceNodeId] || gateways[sourceNodeId];
    if (!sourceNode) continue;
    // 如果源节点是网关节点（且不是汇聚网关），则找到了目标
    if (sourceNode.type && sourceNode.type.includes('Gateway') && sourceNode.type !== 'ConvergeGateway') {
      return sourceNode;
    }
    // 如果源节点是汇聚网关，继续往上递归查找
    if (sourceNode.type === 'ConvergeGateway' || sourceNode.type === 'ServiceActivity') {
      const result = findNearestGatewayByIncoming(sourceNode, flows, activities, gateways, visited);
      if (result) {
        return result;
      }
    }
  }
  return null;
}

function retrieveLines(data, lineId, ordered, isLoop = false, cacheParamsData, isNoDirectLoopCondition = false) {
  const { end_event, activities, gateways, flows } = data;
  const currentNode = flows[lineId].target;
  const endEvent = end_event.id === currentNode ? tools.deepClone(end_event) : undefined;
  const activity = tools.deepClone(activities[currentNode]);
  const gateway = tools.deepClone(gateways[currentNode]);
  const node = endEvent || activity || gateway;
  // 如果是循环处理且当前节点已经在ordered列表中，则停止递归避免无限循环
  if (ordered.findIndex(item => item.id === node.id) !== -1 || cacheParamsData.curNodeIds.includes(node.id)) {
    return;
  }
  if (node && ordered.findIndex(item => item.id === node.id) === -1) {
    let outgoing;
    if (Array.isArray(node.outgoing)) {
      outgoing = node.outgoing;
    } else {
      outgoing = node.outgoing ? [node.outgoing] : [];
    }
    // 检查当前节点是否已存在于节点ID列表中（避免重复处理）
    if (cacheParamsData.copyOrdered.some(item => item.id === node.id)) {
      return;
    }
    const isAt = !cacheParamsData.curNodeIds.includes(node.id);
    if (gateway) { // 网关节点
      const gatewayClone = tools.deepClone(gateway);
      cacheParamsData.copyOrdered.push(gatewayClone);
      const name = NODE_DICT[gateway.type.toLowerCase()];
      gateway.title = name;
      gateway.name = name;
      gateway.expanded = false;
      gateway.children = [];
      if (isAt && (gateway.conditions || gateway.default_condition)) {
        const conditions = Object.keys(gateway.conditions).map((item, index) => {
          const conditionInfo = gateway.conditions[item];
          // 检查当前条件连线是否回退到已处理节点
          let isLoopCondition = false;
          const curNode = activities[flows[item].target] || gateways[flows[item].target];
          // 获取回退目标节点信息
          let callback = '';
          let callbackData = {}; // 条件的节点详情数据需要callbackData包含的数据
          let targetNode = [];
          let isNoDirectLoopCondition = false;

          // 判断是否为回退连线: 回退直连、非直连
          if (curNode && (ordered.find(ite => ite.id === curNode.id || cacheParamsData.curNodeIds.find(ite => ite === curNode.id)))) {
            isLoopCondition = true;
            isNoDirectLoopCondition = false;
            targetNode = [activities[flows[item].target]];
          } else { // 非直连
            isLoopCondition = checkConditionLoop(item, flows, activities, gateways, isLoop ? cacheParamsData.copyOrdered : ordered, cacheParamsData.curNodeIds);
            isNoDirectLoopCondition = isLoopCondition;
            if (isLoopCondition) {
              targetNode = findLoopTarget(item, flows, activities, gateways, isLoop ? cacheParamsData.copyOrdered : ordered, cacheParamsData.curNodeIds);
            }
          }
          if (isLoopCondition) {
            if (targetNode.length === 1) {
              callback = targetNode[0];
            } else if (targetNode.length > 1) {
              callback = targetNode[index];
            }
            if (callback) {
              callbackData = {
                id: callback.id,
                name: conditionInfo.name,
                nodeId: gateway.id,
                overlayId: `condition${item}`,
                tag: conditionInfo.tag,
                value: conditionInfo.evaluate,
              };
            }
          } else {
            // const callback = loopList.includes(item) ? activities[flows[item].target] : '';
            callbackData = {
              id: null,
              name: conditionInfo.name,
              nodeId: gateway.id,
              overlayId: `condition${item}`,
              tag: conditionInfo.tag,
              value: conditionInfo.evaluate,
            };
          }
          return {
            id: `${conditionInfo.name}-${item}`,
            conditionsId: '',
            callbackName: callback?.name || '',
            name: `${conditionInfo.name}-${item}`,
            title: conditionInfo.name,
            isGateway: true,
            conditionType: 'condition', // 条件、条件并行网关
            expanded: false,
            outgoing: item,
            children: [],
            isLoop: isLoopCondition,
            callbackData,
            isNoDirectLoopCondition,
          };
        });
        // 添加条件分支默认节点
        if (gateway.default_condition) {
          const defaultCondition = [
            {
              id: `${gateway.default_condition.name}-${gateway.default_condition.flow_id}`,
              name: `${gateway.default_condition.name}-${gateway.default_condition.flow_id}`,
              title: gateway.default_condition.name,
              isGateway: true,
              conditionType: 'default',
              expanded: false,
              outgoing: gateway.default_condition.flow_id,
              children: [],
            },
          ];
          conditions.unshift(...defaultCondition);
        }
        // 将条件分支添加到网关的子节点中
        gateway.children.push(...conditions);
        gateway.children = gateway.children.map((item) => {
          // 递归处理每个条件分支的子节点
          retrieveLines(data, item.outgoing, item.children, item.isLoop, cacheParamsData, item.isNoDirectLoopCondition);
          if (item.children.length === 0) cacheParamsData.conditionOutgoing.push(item.outgoing);
          item.children.forEach((i) => {
            if (!cacheParamsData.curNodeIds.includes(i.id)) {
              cacheParamsData.curNodeIds.push(i.id);
            }
          });
          return item;
        });
        ordered.push(gateway);
        outgoing.forEach((line) => {
          retrieveLines(data, line, ordered, false, cacheParamsData);
        });
      } else if (isAt && gateway.type === 'ParallelGateway') {
        // 添加并行默认条件
        const defaultCondition = gateway.outgoing.map((item, index) => ({
          name: i18n.t('并行') + (index + 1),
          title: i18n.t('并行'),
          isGateway: true,
          expanded: false,
          conditionType: 'parallel',
          outgoing: item,
          children: [],
        }));
        gateway.children.push(...defaultCondition);
        defaultCondition.forEach((item) => {
          retrieveLines(data, item.outgoing, item.children, false, cacheParamsData);
          item.children.forEach((i) => {
            if (!cacheParamsData.curNodeIds.includes(i.id)) {
              cacheParamsData.curNodeIds.push(i.id);
            }
          });
        });
        ordered.push(gateway);
        outgoing.forEach((line) => {
          retrieveLines(data, line, ordered, false, cacheParamsData);
        });
      }
      if (gateway.type === 'ConvergeGateway') {
        // 判断ordered中 汇聚网关的incoming是否存在
        const list = [];
        const converList = Object.assign({}, activities, gateways);
        cacheParamsData.curNodeIds.forEach((item) => {
          if (converList[item]) {
            list.push(converList[item]);
          }
        });
        const outgoingList = [];
        list.forEach((item) => {
          if (Array.isArray(item.outgoing)) {
            item.outgoing.forEach((ite) => {
              outgoingList.push(ite);
            });
          } else {
            outgoingList.push(item.outgoing);
          }
        });
        let prev = ordered[ordered.findLastIndex(order => order.type !== 'ServiceActivity' && order.type !== 'ConvergeGateway')];
        if (!prev) {
          const nearestGateway = findNearestGatewayByIncoming(gateway, flows, activities, gateways);
          if (nearestGateway) {
            prev = tools.deepClone(cacheParamsData.copyOrdered.find(item => item.id === nearestGateway.id));
            if (!prev) {
              prev = nearestGateway;
            }
            if (!prev.children) {
              prev.children = [];
            }
          }
        }
        // 独立子流程的children为 subChildren
        gateway.gatewayType = 'converge';
        if (prev
          && prev.children
          && !prev.children.find(item => item.id === gateway.id)
          && !cacheParamsData.converNodeList.includes(gateway.id)) {
          cacheParamsData.converNodeList.push(gateway.id);
          prev.children.push(gateway);
          cacheParamsData.copyOrdered.forEach((item) => {
            if (item.id === prev.id) {
              item.children = tools.deepClone(prev.children);
            }
          });
        }
        ordered.push(gateway);
        if (!cacheParamsData.curNodeIds.includes(gateway.id)) {
          cacheParamsData.curNodeIds.push(gateway.id);
        }
        outgoing.forEach((line) => {
          retrieveLines(data, line, ordered, false, cacheParamsData);
        });
      }
    } else if (activity) { // 任务节点
      if (isLoop) {
        if (isNoDirectLoopCondition) {
          if (!cacheParamsData.curNodeIds.includes(activity.id)) {
            cacheParamsData.curNodeIds.push(activity.id);
          }
          activity.title = activity.name;
          activity.expanded = !(activity.type === 'SubProcess' || activity.component.code === 'subprocess_plugin');
          ordered.push(activity);
          if (!cacheParamsData.curNodeIds.includes(activity.id)) {
            cacheParamsData.curNodeIds.push(activity.id);
          }
          retrieveLines(data, activity.outgoing, ordered, isLoop, cacheParamsData, isNoDirectLoopCondition);
        }
        return;
      }
      if (isAt) {
        if (!cacheParamsData.curNodeIds.includes(activity.id)) {
          cacheParamsData.curNodeIds.push(activity.id);
        }
        cacheParamsData.copyOrdered.push(activity);
        if (activity.type === 'SubProcess' || activity.component.code === 'subprocess_plugin') {
          // 只递归第一层 子流程的子流程不递归
          // const  recursionDepth = 0;
          if (activity.pipeline) {
            activity.children = getOrderedTree(activity.pipeline);
          } else {
            if (activity.component?.data && activity.component.data?.subprocess && activity.component.data?.subprocess?.value?.pipeline) {
              activity.children = getOrderedTree(activity.component.data.subprocess.value.pipeline);
            }
          }
        }
        activity.title = activity.name;
        activity.expanded = !(activity.type === 'SubProcess' || activity.component.code === 'subprocess_plugin');
        // activity.type === 'SubProcess' || activity.component.code === 'subprocess_plugin';
        ordered.push(activity);
      }
      outgoing.forEach((line) => {
        retrieveLines(data, line, ordered, false, cacheParamsData);
      });
    }
  }
}

function getOrderedTree(data, cacheParamsData) {
  const startNode = tools.deepClone(data.start_event);
  const endNode = tools.deepClone(data.end_event);
  const fstLine = startNode.outgoing;
  const orderedData = [Object.assign({}, startNode, {
    title: i18n.t('开始节点'),
    name: i18n.t('开始节点'),
    expanded: false,
  })];
  const endEvent = Object.assign({}, endNode, {
    title: i18n.t('结束节点'),
    name: i18n.t('结束节点'),
    expanded: false,
  });
  retrieveLines(data, fstLine, orderedData, false, cacheParamsData);
  orderedData.push(endEvent);
  // 过滤root最上层汇聚网关
  return orderedData;
}

export function getOrderNodeToNodeTree(pipelineTree) {
  const sharedData = {
    curNodeIds: [],
    conditionOutgoing: [],
    converNodeList: [],
    copyOrdered: [],
  };
  const children = getOrderedTree(pipelineTree, sharedData);
  return children;
}
