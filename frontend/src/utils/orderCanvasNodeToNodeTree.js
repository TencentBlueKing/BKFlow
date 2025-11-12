import tools from '@/utils/tools.js';
import { NODE_DICT } from '@/constants/index.js';
import i18n from '@/config/i18n/index.js';

function retrieveLines(data, lineId, ordered, isLoop = false, cacheParamsData) {
  const { end_event, activities, gateways, flows } = data;
  const currentNode = flows[lineId].target;
  const endEvent = end_event.id === currentNode ? tools.deepClone(end_event) : undefined;
  const activity = tools.deepClone(activities[currentNode]);
  const gateway = tools.deepClone(gateways[currentNode]);
  const node = endEvent || activity || gateway;
  if (node && ordered.findIndex(item => item.id === node.id) === -1) {
    let outgoing;
    if (Array.isArray(node.outgoing)) {
      outgoing = node.outgoing;
    } else {
      outgoing = node.outgoing ? [node.outgoing] : [];
    }
    // 当前tree是否已存在
    const isAt = !cacheParamsData.curNodeIds.includes(node.id);
    if (gateway) { // 网关节点
      const name = NODE_DICT[gateway.type.toLowerCase()];
      gateway.title = name;
      gateway.name = name;
      gateway.expanded = false;
      gateway.children = [];
      if (isAt && (gateway.conditions || gateway.default_condition)) {
        const loopList = []; // 需要打回的node的incoming
        outgoing.forEach((item) => {
          const curNode = activities[flows[item].target] || gateways[flows[item].target];
          if (curNode
                && (ordered.find(ite => ite.id === curNode.id || cacheParamsData.curNodeIds.find(ite => ite === curNode.id)))) {
            loopList.push(...curNode.incoming);
          }
        });
        const conditions = Object.keys(gateway.conditions).map((item) => {
          // 给需要打回的条件添加节点id
          const callback = loopList.includes(item) ? activities[flows[item].target] : '';
          const { evaluate, tag } = gateway.conditions[item];
          const callbackData = {
            id: callback.id,
            name: gateway.conditions[item].name,
            nodeId: gateway.id,
            overlayId: `condition${item}`,
            tag,
            value: evaluate,
          };
          return {
            id: `${gateway.conditions[item].name}-${item}`,
            conditionsId: '',
            callbackName: callback.name,
            name: `${gateway.conditions[item].name}-${item}`,
            title: gateway.conditions[item].name,
            isGateway: true,
            conditionType: 'condition', // 条件、条件并行网关
            expanded: false,
            outgoing: item,
            children: [],
            isLoop: loopList.includes(item),
            callbackData,
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

        conditions.forEach((item) => {
          retrieveLines(data, item.outgoing, item.children, item.isLoop, cacheParamsData);
          if (item.children.length === 0) cacheParamsData.conditionOutgoing.push(item.outgoing);
          item.children.forEach((i) => {
            if (!cacheParamsData.curNodeIds.includes(i.id)) {
              cacheParamsData.curNodeIds.push(i.id);
            }
          });
        });
        gateway.children.push(...conditions);
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

        if (gateway.incoming.every(item => outgoingList.concat(cacheParamsData.conditionOutgoing).includes(item))) {
          // 汇聚网关push在最近的条件网关下
          const prev = ordered[ordered.findLastIndex(order => order.type !== 'ServiceActivity' || order.type !== 'ConvergeGateway')];
          // 独立子流程的children为 subChildren
          if (prev
                && prev.children
                && !prev.children.find(item => item.id === gateway.id)
                && !cacheParamsData.converNodeList.includes(gateway.id)) {
            cacheParamsData.converNodeList.push(gateway.id);
            gateway.gatewayType = 'converge';
            prev.children.push(gateway);
          }
          if (!cacheParamsData.curNodeIds.includes(gateway.id)) {
            cacheParamsData.curNodeIds.push(gateway.id);
          }
          outgoing.forEach((line) => {
            retrieveLines(data, line, ordered, false, cacheParamsData);
          });
        }
      }
    } else if (activity) { // 任务节点
      if (isLoop) return;
      if (isAt) {
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
function  getOrderedTree(data, cacheParamsData) {
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


export default function getOrderNodeToNodeTree(pipelineTree) {
  const sharedData = {
    curNodeIds: [],
    conditionOutgoing: [],
    converNodeList: [],
  };
  const children = getOrderedTree(pipelineTree, sharedData);
  return children;
}
