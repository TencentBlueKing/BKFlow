/**
* Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
* Edition) available.
* Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
* Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* http://opensource.org/licenses/MIT
* Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
* an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
* specific language governing permissions and limitations under the License.
*/
import Vue, { ref } from 'vue';
import nodeFilter from '@/utils/nodeFilter.js';
import { uuid, random4 } from '@/utils/uuid.js';
import tools from '@/utils/tools.js';
import validatePipeline from '@/utils/validatePipeline.js';
import axios from 'axios';
import i18n from '@/config/i18n/index.js';
import { stage } from '@/components/canvas/StageCanvas/data.js';
const ATOM_TYPE_DICT = {
  startpoint: 'EmptyStartEvent',
  endpoint: 'EmptyEndEvent',
  tasknode: 'ServiceActivity',
  subflow: 'SubProcess',
  parallelgateway: 'ParallelGateway',
  branchgateway: 'ExclusiveGateway',
  convergegateway: 'ConvergeGateway',
  conditionalparallelgateway: 'ConditionalParallelGateway',
};
// 默认流程模板，默认节点
const generateInitLocation = () => [
  {
    id: `node${uuid()}`,
    x: 40,
    y: 150,
    type: 'startpoint',
  },
  {
    id: `node${uuid()}`,
    x: 240,
    y: 140,
    name: '',
    stage_name: '',
    type: 'tasknode',
  },
  {
    id: `node${uuid()}`,
    x: 540,
    y: 150,
    type: 'endpoint',
  },
];
// 默认流程模板，activities 字段
const generateInitActivities = (location, line) => ({
  [location[1].id]: {
    component: {
      version: undefined,
      code: undefined,
      data: undefined,
    },
    error_ignorable: false,
    id: location[1].id,
    incoming: [line[0].id],
    loop: null,
    name: '',
    optional: true,
    outgoing: line[1].id,
    stage_name: '',
    type: 'ServiceActivity',
    retryable: true,
    skippable: true,
    auto_retry: {
      enable: false,
      interval: 0,
      times: 1,
    },
    timeout_config: {
      enable: false,
      seconds: 10,
      action: 'forced_fail',
    },
  },
});
// 默认流程模板，开始节点
const generateStartNode = (location, line) => ({
  id: location.id,
  incoming: '',
  name: '',
  outgoing: line.id,
  type: 'EmptyStartEvent',
});
// 默认流程模板，结束节点
const generateEndNode = (location, line) => ({
  id: location.id,
  incoming: [line.id],
  name: '',
  outgoing: '',
  type: 'EmptyEndEvent',
});
// 默认流程模板，初始化 line 字段
const generateInitLine = (location) => {
  const line = [];
  const locationLength = location.length;
  if (locationLength < 2) {
    return line;
  }

  location.forEach((item, index) => {
    if (index > locationLength - 2) {
      return;
    }
    line.push({
      id: `line${uuid()}`,
      source: {
        arrow: 'Right',
        id: item.id,
      },
      target: {
        arrow: 'Left',
        id: location[index + 1].id,
      },
    });
  });
  return line;
};
// 默认流程模板，初始化 flows 字段
const generateInitFlow = (line) => {
  const flow = {};
  line.forEach((item) => {
    flow[item.id] = {
      id: item.id,
      is_default: false,
      source: item.source.id,
      target: item.target.id,
    };
  });
  return flow;
};

/**
 * 更新数据的 incoming 字段，兼容旧数据 string => array
 * @param {String、Array} data 原始数据
 * @param {String} id 待新增或删除数据
 * @param {String} type 操作类型，新增(add)或删除(delete)
 */
const updateIncoming = (incoming, id, type) => {
  let data = Array.isArray(incoming) ? incoming.slice(0) : incoming;
  if (type === 'add') {
    if (Array.isArray(data)) {
      data.push(id);
    } else {
      data = data === '' ? [id] : [data, id];
    }
  } else {
    if (Array.isArray(data)) {
      data = data.filter(line => line !== id);
    } else {
      data = [];
    }
  }
  return data;
};

const template = {
  namespaced: true,
  state: {
    name: '',
    activities: {},
    end_event: {},
    flows: {},
    gateways: {},
    line: [],
    stage_canvas_data: [],
    location: [],
    outputs: [],
    start_event: {},
    template_id: '',
    constants: {},
    projectBaseInfo: {},
    notify_receivers: {
      receiver_group: [],
      more_receiver: '',
    },
    notify_type: { success: [], fail: [] },
    time_out: '',
    category: '',
    description: '',
    executor_proxy: '',
    template_labels: [],
    subprocess_info: {
      details: [],
      subproc_has_update: false,
    },
    internalVariable: [],
    default_flow_type: 'common',
    spaceId: '',
    scopeInfo: {},
    canvas_mode: '',
    triggers: [],
    webhook_configs: {},
    enable_webhook: false,
  },
  mutations: {
    setWebhookConfigs(state, webhookConfigs) {
      state.webhook_configs = webhookConfigs;
    },
    setTemplateName(state, name) {
      state.name = name;
    },
    setTemplateLabel(state, labels) {
      state.template_labels = labels;
    },
    setReceiversGroup(state, data) {
      state.notify_receivers.receiver_group = data;
    },
    setNotifyType(state, data) {
      state.notify_type = data;
    },
    setOvertime(state, data) {
      state.time_out = data;
    },
    setCategory(state, data) {
      state.category = data;
    },
    setTplConfig(state, data) {
      state.name = data.name;
      state.category = data.category;
      state.notify_type = data.notify_type;
      state.notify_receivers.more_receiver = data.more_receiver?.join(',');
      state.notify_receivers.receiver_group = data.receiver_group;
      state.description = data.description;
      state.executor_proxy = data.executor_proxy;
      state.template_labels = data.template_labels;
      state.default_flow_type = data.default_flow_type;
      state.triggers = data.triggers;
      state.webhook_configs = data.webhook_configs;
      state.enable_webhook = data.enable_webhook || false;
    },
    setSubprocessUpdated(state, subflow) {
      if (state.subprocess_info) {
        const data = state.subprocess_info.find(item => subflow.subprocess_node_id === item.subprocess_node_id);
        if (data) {
          data.expired = subflow.expired;
          if (subflow.version) {
            data.version = subflow.version;
          }
        }
      }
    },
    setPipelineTree(state, data) {
      const pipelineTreeOrder = [
        'activities', 'constants', 'end_event', 'flows', 'gateways',
        'line', 'location', 'outputs', 'start_event', 'stage_canvas_data',
      ];
      pipelineTreeOrder.forEach((key) => {
        let val = data[key];

        if (key === 'constants') {
          // 全局变量 index 修正，3.5版本之前变量 index 存在不连续的情况，导致新增变量时 index 不正确
          Object.keys(val).map(varKey => val[varKey])
            .sort((a, b) => a.index - b.index)
            .forEach((item, index) => {
              item.index = index;
            });
        } else {
          // 节点、连线不和规则 id 替换
          // 3.1版本之前节点和连线的 id 可能存在以数字开头的情况，导致使用 docuement.getElementById 等查找DOM节点失败
          val = nodeFilter.convertInvalidIdData(key, val);
          if (key === 'activities') { // 兼容脏数据 can_retry、isSkipped 字段不存在问题
            Object.keys(val).forEach((nodeId) => {
              const item = val[nodeId];
              const has = Object.prototype.hasOwnProperty;
              if (!has.call(item, 'can_retry') && !has.call(item, 'retryable')) {
                item.can_retry = true;
              }
              if (!has.call(item, 'isSkipped') && !has.call(item, 'skippable')) {
                item.isSkipped = true;
              }
            });
          }
          if (key === 'location') {
            val = val.map((item) => {
              if (item.type === 'tasknode' || item.type === 'subflow' || item.type === 'SubProcess' || item.type === 'SubCanvas') {
                const node = state.activities[item.id];
                if (!node) return item;
                const loc = Object.assign({}, item, {
                  name: node.name,
                  stage_name: node.stage_name,
                  optional: node.optional,
                  error_ignorable: node.error_ignorable,
                  retryable: node.can_retry || node.retryable,
                  skippable: node.isSkipped || node.skippable,
                  auto_retry: node.auto_retry || { enable: false, interval: 0, times: 1 },
                  timeout_config: node.timeout_config || {
                    enable: false,
                    seconds: 10,
                    action: 'forced_fail',
                  },
                  loop_config: node.loop_config || {},
                });
                return loc;
              }
              return item;
            });
          }
          if (key === 'stage_canvas_data') {
            if (!val) {
              val = ref([...stage]).value;
            } else {
              val = ref(val).value;
            }
          }
        }

        state[key] = val;
      });
    },
    updatePipelineTree(state, data) {
      const { activities, flows, gateways, line, location, start_event: startEvent, end_event: endEvent, canvas_mode: canvasMode, stage_canvas_data: stageCanvasData, constants, outputs } = data;
      activities && (state.activities = activities);
      flows && (state.flows = flows);
      gateways && (state.gateways = gateways);
      line && (state.line = line);
      location && (state.location = location);
      startEvent && (state.start_event = startEvent);
      endEvent && (state.end_event = endEvent);
      canvasMode && (state.canvas_mode = canvasMode);
      stageCanvasData && (state.stage_canvas_data = stageCanvasData);
      constants && (state.constants = constants);
      outputs && (state.outputs = outputs);
    },
    updateStageCanvasData(state, stageCanvasData) {
      state.stage_canvas_data = stageCanvasData;
    },
    // 更新模板各相关字段数据
    setTemplateData(state, data) {
      const {
        name,
        id: templateId,
        pipeline_tree: pipelineData,
        notify_config: notifyConfig,
        description,
        executor_proxy: executorProxy,
        time_out: timeOut,
        category,
        subprocess_info: subprocessInfo,
        default_flow_type: defaultFlowType,
        space_id: spaceId,
        scope_type, // 作用域类型
        scope_value, // 作用域值
        triggers,
        webhook_configs: webhookConfigs,
        enable_webhook: enableWebhook,
      } = data;

      const {
        notify_type: notifyType = { success: [], fail: [] },
        notify_receivers: receiver = { receiver_group: [], more_receiver: '' },
      } = notifyConfig || {};
      state.name = name;
      state.template_id = templateId;
      state.notify_receivers.more_receiver = receiver.more_receiver || '';
      state.notify_receivers.receiver_group = receiver.receiver_group || [];
      state.notify_type = typeof notifyType === 'string' ? { success: JSON.parse(notifyType), fail: [] } : notifyType;
      state.description = description;
      state.executor_proxy = executorProxy;
      state.time_out = timeOut;
      state.category = category;
      state.subprocess_info = subprocessInfo;
      state.default_flow_type = defaultFlowType;
      state.spaceId = spaceId;
      state.scopeInfo = {
        scope_type,
        scope_value,
      };
      state.triggers = triggers;
      state.webhook_configs = webhookConfigs;
      state.enable_webhook = enableWebhook;
      state.canvas_mode = pipelineData.canvas_mode;
      this.commit('template/setPipelineTree', pipelineData);
    },
    setProjectBaseInfo(state, data) {
      state.projectBaseInfo = data;
    },
    // 初始化模板数据
    initTemplateData(state) {
      const location = generateInitLocation();
      const line = generateInitLine(location);
      const flow = generateInitFlow(line);
      const activities = generateInitActivities(location, line);
      const startEvent = generateStartNode(location[0], line[0]);
      const endEvent = generateEndNode(location[2], line[1]);
      state.name = '';
      state.activities = activities;
      state.end_event = endEvent;
      state.flows = flow;
      state.gateways = {};
      state.line = line;
      state.location = location;
      state.outputs = [];
      state.start_event = startEvent;
      state.template_id = '';
      state.constants = {};
      state.category = 'Default';
      state.notify_type = { success: [], fail: [] };
      state.notify_receivers = {
        receiver_group: [],
        more_receiver: '',
      };
      state.description = '';
      state.executor_proxy = '';
      state.default_flow_type = 'common';
    },
    // 重置模板数据
    resetTemplateData(state) {
      state.name = '';
      state.activities = {};
      state.end_event = {};
      state.flows = {};
      state.gateways = {};
      state.line = [];
      state.location = [];
      state.outputs = [];
      state.start_event = {};
      state.template_id = '';
      state.constants = {};
      state.category = 'Default';
      state.notify_type = { success: [], fail: [] };
      state.notify_receivers = {
        receiver_group: [],
        more_receiver: '',
      };
      state.description = '';
      state.executor_proxy = '';
      state.template_labels = [];
      state.default_flow_type = 'common';
    },
    // 增加全局变量
    addVariable(state, variable) {
      Vue.set(state.constants, variable.key, variable);
    },
    // 编辑全局变量
    editVariable(state, payload) {
      const { key, variable } = payload;
      Vue.delete(state.constants, key);
      Vue.set(state.constants, variable.key, variable);
    },
    // 删除全局变量
    deleteVariable(state, key) {
      const constant = state.constants[key];
      const { source_info } = constant;

      // 遍历节点，去掉表单的勾选状态，并将变量值复制给对应表单
      Object.keys(source_info).forEach((id) => {
        if (state.activities[id]) {
          source_info[id].forEach((item) => {
            let data;
            if (state.activities[id].type === 'ServiceActivity') {
              data = state.activities[id].component.data[item];
            } else {
              const variableKey = /^\$\{[\w]*\}$/.test(item) ? item : `\${${item}}`;
              data = state.activities[id].constants[variableKey];
            }
            if (data) {
              data.hook = false;
              data.value = constant.value;
            }
          });
        }
      });
      // 删除输出变量的勾选状态
      if (state.outputs.includes(key)) {
        state.outputs.splice(state.outputs.indexOf(key), 1);
      }

      Object.keys(state.constants).forEach((key) => {
        const varItem = state.constants[key];
        if (varItem.index > constant.index) {
          varItem.index = varItem.index - 1;
        }
      });

      Vue.delete(state.constants, key);
    },
    // 配置全局变量 source_info 字段
    setVariableSourceInfo(state, payload) {
      const { type, id, key, tagCode } = payload;
      const constant = state.constants[key];
      if (!constant) return;
      const sourceInfo = constant.source_info;
      if (type === 'add') {
        if (sourceInfo[id]) {
          sourceInfo[id].push(tagCode);
        } else {
          Vue.set(sourceInfo, id, [tagCode]);
        }
      } else if (type === 'delete') {
        if (sourceInfo[id].length <= 1) {
          Vue.delete(sourceInfo, id);
        } else {
          let atomIndex;
          sourceInfo[id].some((item, index) => {
            if (item === tagCode) {
              atomIndex = index;
              return true;
            }
            return false;
          });
          sourceInfo[id].splice(atomIndex, 1);
        }
        if (!Object.keys(sourceInfo).length) {
          this.commit('template/deleteVariable', key);
        }
      }
    },
    // 配置分支网关条件
    setBranchCondition(state, condition) {
      const { id, nodeId, name, value, loc, default_condition: defaultCondition, loopNodeId } = condition;
      // 若条件属于循环流内部，则从loopNodeId对应的 pipeline 中获取网关配置
      let gatewayState;
      if (loopNodeId && state.activities[loopNodeId] && state.activities[loopNodeId].pipeline) {
        gatewayState = state.activities[loopNodeId].pipeline;
      } else {
        gatewayState = state;
      }
      const { conditions } = gatewayState.gateways[nodeId];
      if (defaultCondition) {
        gatewayState.gateways[nodeId].default_condition = defaultCondition;
        Vue.delete(conditions, id);
      } else if (conditions[id]) {
        conditions[id].name = name;
        conditions[id].evaluate = value;
      } else if (!conditions[id]) {
        const { tag } = gatewayState.gateways[nodeId].default_condition;
        conditions[id] = {
          tag,
          name,
          evaluate: value,
        };
        Vue.delete(gatewayState.gateways[nodeId], 'default_condition');
      }
      if (loc !== undefined) {
        if (defaultCondition) {
          gatewayState.gateways[nodeId].default_condition.loc = loc;
        } else if (conditions[id]) {
          conditions[id].loc = loc;
        }
      }
    },
    // 节点增加、删除、编辑、复制,操作，数据更新
    setLocation(state, payload) {
      const { type, location } = payload;
      let locationIndex;
      const isLocationExist = state.location.some((item, index) => {
        if (item.id === location.id) {
          locationIndex = index;
          return true;
        }
        return false;
      });
      if (['add', 'copy'].indexOf(type) > -1 && !isLocationExist) {
        const loc = tools.deepClone(location);
        delete loc.atomId; // 添加节点后删除标准插件类型字段
        state.location.push(loc);
      } else if (isLocationExist) {
        // 只有当目标 id 在 location 中实际存在时才执行编辑/删除操作
        // 否则 splice(undefined, 1) 会误删数组的第一个元素
        if (type === 'edit') {
          state.location.splice(locationIndex, 1, location);
        } else if (type === 'delete') {
          state.location.splice(locationIndex, 1);
        }
      }
    },
    // 节点拖动，位置/尺寸更新
    setLocationXY(state, location) {
      const { id, x, y, width, height } = location;
      const data = state.location.find(item => item.id === id);
      if (data) {
        data.x = x;
        data.y = y;
        if (width !== undefined) data.width = width;
        if (height !== undefined) data.height = height;
        return;
      }
      Object.values(state.activities).forEach((act) => {
        if (act.type !== 'SubCanvas' || !act.pipeline) return;
        const loc = act.pipeline.location.find(item => item.id === id);
        if (loc) {
          loc.x = x;
          loc.y = y;
          if (width !== undefined) loc.width = width;
          if (height !== undefined) loc.height = height;
        }
      });
    },
    // 增加、删除节点连线操作，更新模板各相关字段数据
    setLine(state, payload) {
      const { type, line } = payload;

      if (type === 'add') { // 添加连线(手动拖拽连接的情况)
        const id = line.id || `line${uuid()}`;
        const newLine = Object.assign({}, line, { id });
        const sourceNode = newLine.source.id;
        const targetNode = newLine.target.id;

        Vue.set(state.flows, id, {
          id,
          is_default: false,
          source: sourceNode,
          target: targetNode,
        });
        if (state.activities[sourceNode]) {
          state.activities[sourceNode].outgoing = id;
        }
        if (state.activities[targetNode]) {
          state.activities[targetNode].incoming = updateIncoming(state.activities[targetNode].incoming, id, 'add');
        }

        if (state.start_event.id === sourceNode) {
          state.start_event.outgoing = id;
        }

        if (state.end_event.id === targetNode) {
          state.end_event.incoming = updateIncoming(state.end_event.incoming, id, 'add');
        }

        // 循环容器内部开始/结束节点连线处理
        Object.values(state.activities).forEach((a) => {
          if (a.type !== 'SubCanvas' || !a.pipeline) return;
          const pt = a.pipeline;
          if (pt.start_event && pt.start_event.id === sourceNode) {
            pt.start_event.outgoing = id;
          }
          if (pt.end_event && pt.end_event.id === targetNode) {
            pt.end_event.incoming = updateIncoming(pt.end_event.incoming, id, 'add');
          }
        });

        if (state.gateways[sourceNode]) {
          const gatewayNode = state.gateways[sourceNode];
          if (Array.isArray(gatewayNode.outgoing)) {
            const len = gatewayNode.outgoing.length;
            Vue.set(gatewayNode.outgoing, len, id);
            if (
              gatewayNode.type === ATOM_TYPE_DICT.branchgateway
              || gatewayNode.type === ATOM_TYPE_DICT.conditionalparallelgateway
            ) {
              const { conditions } = gatewayNode;
              let evaluate;
              let name;
              // copy 连线，需复制原来的分支条件信息
              if (line.oldSouceId) {
                const sourceNodeId = state.flows[line.oldSouceId].source;
                const sourceGateWayNode = state.gateways[sourceNodeId];
                const sourceCondition = sourceGateWayNode.conditions[line.oldSouceId];

                evaluate = sourceCondition.evaluate || sourceCondition.name;
                name = sourceCondition.name;
              } else if (line.condition) { // 自动重连，保留原连线分支条件
                evaluate = line.condition.evaluate;
                name = line.condition.name;
              } else {
                if (line.parseLang === 'FEEL') {
                  evaluate = Object.keys(conditions).length ? '1 = 0' : '1 = 1';
                } else {
                  evaluate = Object.keys(conditions).length ? '1 == 0' : '1 == 1';
                }
                if (line.parseLang === 'MAKO') {
                  evaluate = `\${${evaluate}}`;
                }
                const defaultName = i18n.t('条件');
                const regStr = `^${i18n.t('条件')}[0-9]*$`;
                const reg = new RegExp(regStr);
                let maxCount = 0;
                Object.values(conditions).forEach((item) => {
                  if (reg.test(item.name)) {
                    let count = item.name.split(defaultName)[1];
                    count = Number(count);
                    maxCount = maxCount > count ? maxCount : count;
                  }
                });
                name = defaultName + (maxCount + 1);
              }

              const conditionItem = {
                evaluate,
                name,
                tag: `branch_${sourceNode}_${targetNode}`,
              };
              Vue.set(conditions, id, conditionItem);
            }
          } else {
            gatewayNode.outgoing = id;
          }
        }
        if (state.gateways[targetNode]) {
          const gatewayNode = state.gateways[targetNode];
          gatewayNode.incoming = updateIncoming(gatewayNode.incoming, id, 'add');
        }
        state.line.push(newLine);
      } else if (type === 'delete') { // sync activities、flows、gateways、start_event、end_event
        const deletedLine = state.flows[line.id];
        if (!deletedLine) {
          return;
        }
        const sourceNode = state.flows[deletedLine.id].source;
        const targetNode = state.flows[deletedLine.id].target;

        if (state.activities[sourceNode]) {
          state.activities[sourceNode].outgoing = '';
        }

        if (state.activities[targetNode]) {
          state.activities[targetNode].incoming = updateIncoming(state.activities[targetNode].incoming, deletedLine.id, 'delete');
        }

        if (state.start_event.id === sourceNode) {
          state.start_event.outgoing = '';
        }

        if (state.end_event.id === targetNode) {
          state.end_event.incoming = updateIncoming(state.end_event.incoming, deletedLine.id, 'delete');
        }

        // 循环容器内部开始/结束节点连线删除处理
        Object.values(state.activities).forEach((a) => {
          if (a.type !== 'SubCanvas' || !a.pipeline) return;
          const pt = a.pipeline;
          if (pt.start_event && pt.start_event.id === sourceNode) {
            pt.start_event.outgoing = '';
          }
          if (pt.end_event && pt.end_event.id === targetNode) {
            pt.end_event.incoming = updateIncoming(pt.end_event.incoming, deletedLine.id, 'delete');
          }
        });

        state.line = state.line.filter(ln => ln.id !== deletedLine.id);
        if (state.gateways[sourceNode]) {
          const gatewayNode = state.gateways[sourceNode];
          if (Array.isArray(gatewayNode.outgoing)) {
            gatewayNode.outgoing = gatewayNode.outgoing.filter(item => item !== deletedLine.id);
            if (
              gatewayNode.type === ATOM_TYPE_DICT.branchgateway
              || gatewayNode.type === ATOM_TYPE_DICT.conditionalparallelgateway
            ) {
              const { conditions } = gatewayNode;
              conditions[deletedLine.id] && Vue.delete(conditions, deletedLine.id);
            }
          } else {
            gatewayNode.outgoing = '';
          }
          // 删除默认网关分支连线时需要清除网关处理的default_condition
          const tag = `branch_${sourceNode}_${targetNode}`;
          if (gatewayNode.default_condition && gatewayNode.default_condition.tag === tag) {
            Vue.delete(gatewayNode, 'default_condition');
          }
        }
        if (state.gateways[targetNode]) {
          const gatewayNode = state.gateways[targetNode];
          gatewayNode.incoming = updateIncoming(gatewayNode.incoming, deletedLine.id, 'delete');
        }
        Vue.delete(state.flows, deletedLine.id);
      } else if (type === 'edit') {
        const lineInfo = state.line.find(ln => ln.id === line.id);
        Object.assign(lineInfo, line);
      }
    },
    // 任务节点增加、删除、编辑,复制操作，更新模板各相关字段数据
    setActivities(state, payload) {
      const { type, location } = payload;
      if (type === 'add') {
        if (!state.activities[location.id]) {
          let activity = {};
          if (location.type === 'tasknode') {
            activity = {
              component: {
                code: location.atomId,
                data: location.data,
                version: location.version,
                api_meta: location.api_meta,
              },
              error_ignorable: false,
              id: location.id,
              incoming: [],
              loop: null,
              name: location.name || '',
              optional: true,
              outgoing: '',
              stage_name: '',
              type: 'ServiceActivity',
              retryable: true,
              skippable: true,
              auto_retry: { enable: false, interval: 0, times: 1 },
              timeout_config: {
                enable: false,
                seconds: 10,
                action: 'forced_fail',
              },
              parent: location.parent || null,
            };
          } else if (location.type === 'subflow') {
            activity = {
              constants: {},
              hooked_constants: [],
              error_ignorable: false,
              id: location.id,
              incoming: [],
              loop: null,
              name: location.name || '',
              optional: true,
              outgoing: '',
              stage_name: '',
              template_id: location.atomId,
              version: location.atomVersion,
              type: 'SubProcess',
              retryable: true,
              skippable: true,
              always_use_latest: false,
              scheme_id_list: [],
              template_source: location.tplSource || 'business',
              parent: location.parent || null,
            };
          } else if (location.type === 'SubCanvas') {
            activity = {
              constants: {},
              hooked_constants: [],
              error_ignorable: false,
              id: location.id,
              incoming: [],
              loop: null,
              name: location.name || '',
              optional: true,
              outgoing: '',
              stage_name: '',
              template_id: location.atomId,
              version: location.atomVersion,
              type: 'SubCanvas',
              retryable: true,
              skippable: true,
              always_use_latest: false,
              scheme_id_list: [],
              template_source: location.tplSource || 'business',
              pipeline: null,
              loop_config: {
                enable: true,
                type: 'time_loop',
                loop_times: 3,
                loop_params: {},
                fail_skip: false,
                retryable: true,
                skippable: true,
              },
            };
          }
          Vue.set(state.activities, location.id, activity);
        }
      } else if (type === 'edit') {
        Vue.set(state.activities, location.id, location);
        state.location.forEach((item) => {
          if (item.id === location.id) {
            Vue.set(item, 'name', location.name);
            Vue.set(item, 'stage_name', location.stage_name);
          }
        });
      } else if (type === 'delete') {
        Vue.delete(state.activities, location.id);
        Object.keys(state.constants).forEach((cKey) => {
          const constant = state.constants[cKey];
          const sourceInfo = constant.source_info;
          if (sourceInfo && sourceInfo[location.id]) {
            if (Object.keys(sourceInfo).length > 1) {
              Vue.delete(sourceInfo, location.id);
            } else {
              this.commit('template/deleteVariable', cKey);
            }
          }
        });
      } else if (type === 'copy') { // 复制节点
        const { oldSouceId } = location;
        const newActivitie = tools.deepClone(state.activities[oldSouceId]);
        if (!state.activities[location.id]) {
          if (location.type === 'tasknode' || location.type === 'subflow') {
            newActivitie.id = location.id;
            newActivitie.incoming = '';
            newActivitie.loop = null;
            newActivitie.outgoing = '';
            newActivitie.parent = location.parent || null;
            state.activities[location.id] = newActivitie;
          } else if (location.type === 'SubCanvas') {
            // 复制 SubCanvas：直接 deepClone，嵌套 pipeline 中的子节点 ID 由 copyLoopGroupLocationAndFlows 负责重映射
            newActivitie.id = location.id;
            newActivitie.incoming = '';
            newActivitie.outgoing = '';
            newActivitie.parent = location.parent || null;
            state.activities[location.id] = newActivitie;
          }
        }
        // 勾选变量处理
        Object.keys(state.constants).forEach((key) => {
          const item = state.constants[key];
          const { source_info } = item;
          const info = source_info[oldSouceId];
          if (info) {
            const { source_type: sourceType } = state.constants[key];
            if (sourceType === 'component_inputs') { // 复用输入变量
              Vue.set(source_info, location.id, info);
            } else if (sourceType === 'component_outputs') { // 新建输出变量
              const constantsLen = Object.keys(state.constants).length;
              const varId = `\${${info[0]}_${random4()}}`;
              const varValue = tools.deepClone(item);
              const changeObj = {
                source_info: { [location.id]: info },
                key: varId,
                index: constantsLen,
              };
              Vue.set(state.constants, varId, Object.assign(varValue, changeObj));
            }
          }
        });
      }
    },
    // 更新嵌套pipelineTree 中的activity数据
    setInnerActivity(state, { nodeId, config }) {
      let found = false;
      Object.values(state.activities).forEach((act) => {
        if (act.type !== 'SubCanvas' || !act.pipeline) return;
        const pt = act.pipeline;
        if (pt.activities && pt.activities[nodeId]) {
          // 保留 pipeline 特有的字段（parent），用配置数据覆盖其余字段
          const existingParent = pt.activities[nodeId].parent;
          pt.activities[nodeId] = { ...config, parent: existingParent };
          // 同步更新 location 中的 name 和 stage_name
          if (pt.location) {
            const loc = pt.location.find(l => l.id === nodeId);
            if (loc) {
              loc.name = config.name || '';
              loc.stage_name = config.stage_name || '';
            }
          }
          found = true;
        }
      });
      if (!found && process.env.NODE_ENV === 'development') {
        console.warn(`[setInnerActivity] node ${nodeId} not found in any pipeline`);
      }
    },
    // 更新嵌套pipelineTree中的location数据
    setInnerLocation(state, { nodeId, data }) {
      Object.values(state.activities).forEach((item) => {
        if (item.type !== 'SubCanvas' || !item.pipeline) return;
        const innerPipeline = item.pipeline;
        if (!innerPipeline.location) return;
        const locIdx = innerPipeline.location.findIndex(l => l.id === nodeId);
        if (locIdx >= 0) {
          Object.assign(innerPipeline.location[locIdx], data);
        }
      });
    },
    // 网关节点增加、删除操作，更新模板各相关字段数据
    setGateways(state, payload) {
      const { type, location } = payload;
      if (['add', 'copy'].indexOf(type) > -1) {
        if (!state.gateways[location.id]) {
          state.gateways[location.id] = {
            id: location.id,
            incoming: [],
            name: location.name || '',
            outgoing: location.type === 'convergegateway' ? '' : [],
            type: ATOM_TYPE_DICT[location.type],
          };
          if (location.type === 'branchgateway' || location.type === 'conditionalparallelgateway') {
            state.gateways[location.id].conditions = {};
            // 网关分支表达式解析类型字段
            let { parseLang } = location;
            const oldGatewayInfo = state.gateways[location.oldSouceId];
            if (oldGatewayInfo) {
              const { parse_lang: oldParseLang } = oldGatewayInfo.extra_info || {};
              parseLang = oldParseLang;
            }
            if (['FEEL', 'MAKO'].includes(parseLang)) {
              state.gateways[location.id].extra_info = { parse_lang: parseLang };
            }
          }
          if (location.type !== 'convergegateway') {
            state.gateways[location.id].converge_gateway_id = location.convergeGatewayId || '';
          }
          if (location.parent) {
            state.gateways[location.id].parent = location.parent;
          }
        }
      } else if (type === 'delete') {
        Vue.delete(state.gateways, location.id);
        // 如果删除的是汇聚网关则需要清除其他并行网关与之配置的converge_gateway_id
        if (location.type === 'convergegateway') {
          Object.values(state.gateways).forEach((gateway) => {
            if (gateway.converge_gateway_id === location.id) {
              Vue.set(state.gateways[gateway.id], 'converge_gateway_id', '');
            }
          });
        }
      } else if (type === 'edit') {
        // 编辑已有网关
        if (state.gateways[location.id]) {
          Object.assign(state.gateways[location.id], location);
          // 如果传入数据中不包含parent（即网关从分组中移出），显式清除残留的parent
          if (!('parent' in location) && state.gateways[location.id].parent) {
            Vue.delete(state.gateways[location.id], 'parent');
          }
        } else {
          Vue.set(state.gateways, location.id, { ...location });
        }
      }
    },
    // 开始节点增加、删除操作，更新模板各相关字段数据
    setStartpoint(state, payload) {
      const { type, location } = payload;
      if (type === 'add') {
        if (!state.start_event.id) {
          state.start_event = {
            id: location.id,
            incoming: '',
            name: location.name || '',
            outgoing: '',
            type: 'EmptyStartEvent',
          };
        }
      } else if (type === 'delete') {
        Vue.set(state, 'start_event', {});
      }
    },
    // 终止节点增加、删除操作，更新模板各相关字段数据
    setEndpoint(state, payload) {
      const { type, location } = payload;
      if (type === 'add') {
        if (!state.end_event.id) {
          state.end_event = {
            id: location.id,
            incoming: '',
            name: location.name || '',
            outgoing: '',
            type: 'EmptyEndEvent',
          };
        }
      } else if (type === 'delete') {
        Vue.set(state, 'end_event', {});
      }
    },
    // 更新全局变量
    setConstants(state, data) {
      state.constants = tools.deepClone(data);
    },
    // 全局变量勾选是否为输出
    setOutputs(state, payload) {
      const { changeType, key, newKey } = payload;
      if (changeType === 'add') {
        if (state.outputs.includes(key)) {
          return;
        }
        state.outputs.push(key);
      } else if (changeType === 'delete') {
        state.outputs = state.outputs.filter(item => item !== key);
      } else {
        const index = state.outputs.findIndex(item => item === key);
        state.outputs.splice(index, 1, newKey);
      }
    },
    // 修改state中的模板数据
    replaceTemplate(state, template) {
      if (template !== undefined) {
        Object.keys(template).forEach((prop) => {
          state[prop] = template[prop];
        });
      }
    },
    // 修改lines和locations
    replaceLineAndLocation(state, payload) {
      //  需要做一次深层拷贝
      const { lines, locations } = tools.deepClone(payload);
      state.line = lines;
      state.location = locations;
    },
    // 设置内置变量
    setInternalVariable(state, payload) {
      state.internalVariable = payload;
    },
    setSpaceId(state, id) {
      state.spaceId = id;
    },
    // 批量设置循环流内部变量
    setLoopInnerConstants(state, payload) {
      const { loopNodeId, constants } = payload;
      const loopNode = state.activities[loopNodeId];
      if (!loopNode || !loopNode.pipeline) return;
      Vue.set(loopNode.pipeline, 'constants', constants);
      Vue.set(loopNode, 'constants', tools.deepClone(constants));
    },
    // 添加循环流内部变量
    addLoopInnerVariable(state, payload) {
      const { loopNodeId, variable } = payload;
      const loopNode = state.activities[loopNodeId];
      if (loopNode && loopNode.pipeline) {
        if (!loopNode.pipeline.constants) {
          Vue.set(loopNode.pipeline, 'constants', {});
        }
        Vue.set(loopNode.pipeline.constants, variable.key, variable);
        if (!loopNode.constants) {
          Vue.set(loopNode, 'constants', {});
        }
        Vue.set(loopNode.constants, variable.key, tools.deepClone(variable));
      }
    },
    // 编辑循环流内部变量
    editLoopInnerVariable(state, payload) {
      const { loopNodeId, key, variable } = payload;
      const loopNode = state.activities[loopNodeId];
      if (loopNode && loopNode.pipeline && loopNode.pipeline.constants) {
        Vue.delete(loopNode.pipeline.constants, key);
        Vue.set(loopNode.pipeline.constants, variable.key, variable);
        if (loopNode.constants) {
          if (loopNode.constants[key]) {
            Vue.delete(loopNode.constants, key);
          }
          Vue.set(loopNode.constants, variable.key, tools.deepClone(variable));
        }
      }
    },
    // 删除循环流内部变量
    deleteLoopInnerVariable(state, payload) {
      const { loopNodeId, key } = payload;
      const loopNode = state.activities[loopNodeId];
      if (loopNode && loopNode.pipeline && loopNode.pipeline.constants) {
        if (loopNode.pipeline.constants[key]) {
          Vue.delete(loopNode.pipeline.constants, key);
        }
        // 同步删除 loopNode.constants 中的变量
        if (loopNode.constants && loopNode.constants[key]) {
          Vue.delete(loopNode.constants, key);
        }
        // 如果变量勾选了输出，从 pipeline.outputs 列表中移除
        if (loopNode.pipeline && loopNode.pipeline.outputs && loopNode.pipeline.outputs.includes(key)) {
          loopNode.pipeline.outputs.splice(loopNode.pipeline.outputs.indexOf(key), 1);
        }
      }
    },
    // 编辑循环流内部变量 key 时同步更新 pipeline.outputs 中的 key
    editLoopInnerVariableOutputKey(state, payload) {
      const { loopNodeId, oldKey, newKey } = payload;
      const loopNode = state.activities[loopNodeId];
      if (!loopNode || !loopNode.pipeline || !loopNode.pipeline.outputs) return;
      const idx = loopNode.pipeline.outputs.indexOf(oldKey);
      if (idx > -1) {
        Vue.set(loopNode.pipeline.outputs, idx, newKey);
      }
    },
    // 设置循环流内部变量的输出状态
    setLoopInnerVariableOutput(state, payload) {
      const { loopNodeId, key, checked } = payload;
      const loopNode = state.activities[loopNodeId];
      if (!loopNode || !loopNode.pipeline) return;
      if (!loopNode.pipeline.outputs) {
        Vue.set(loopNode.pipeline, 'outputs', []);
      }
      if (checked) {
        if (!loopNode.pipeline.outputs.includes(key)) {
          loopNode.pipeline.outputs.push(key);
        }
      } else {
        if (loopNode.pipeline.outputs.includes(key)) {
          loopNode.pipeline.outputs.splice(loopNode.pipeline.outputs.indexOf(key), 1);
        }
      }
    },
  },
  actions: {
    loadProjectBaseInfo() {
      return axios.get('core/api/get_basic_info/').then(response => response.data);
    },
    loadTemplateData({}, data) {
      const { templateId, common, checkPermission = false } = data;
      let prefixUrl = '';
      if (common) {
        prefixUrl = 'api/common_template/';
      } else {
        prefixUrl = 'api/template/';
      }
      return axios({
        method: 'get',
        url: `${prefixUrl}${templateId}/`,
        headers: {
          'Tpl-Node-Permission-Check': checkPermission,
        },
      }).then(response => response.data.data);
    },
    // 批量获取模板最新版本信息
    batchGetTemplateVersion({}, data) {
      const { templateIds } = data;
      return axios.get('api/template/batch_get_template_version/', {
        params: { template_ids: templateIds },
      }).then(response => response.data);
    },
    loadCustomVarCollection() {
      return axios.get('api/template/variable/').then(response => response.data.data);
    },
    createTemplate({}, data) {
      const { spaceId, params } = data;
      return axios.post(`api/template/admin/create_default_template/${spaceId}/`, params).then(response => response.data.data);
    },
    /**
     * 保存模板数据
     * @param {Object} data 模板完整数据
     */
    saveTemplateData({ state }, data) {
      const { templateId, common, spaceId, version } = data;
      const { activities, constants, end_event, flows, gateways, line,
        location, outputs, start_event, notify_receivers, notify_type,
        time_out: timeout, category, description, executor_proxy, template_labels, default_flow_type,
        canvas_mode,
        stage_canvas_data, triggers, webhook_configs, enable_webhook,
      } = state;
      triggers.forEach((trigger) => {
        if (trigger) {
          if (Object.hasOwn(trigger, 'isNewTrigger')) {
            delete trigger.isNewTrigger;
          }
          if (trigger.config.constants === null || !trigger.config.constants) {
            trigger.config.constants = {};
          }
        }
      });
      // 剔除 location 的冗余字段
      const pureLocation = location.map(item => ({
        id: item.id,
        type: item.type,
        name: item.name,
        stage_name: item.stage_name,
        x: item.x,
        y: item.y,
        width: item.width,
        height: item.height,
        group: item.group,
        icon: item.icon,
        parent: item.parent || undefined,
      }));
      // 剔除 gateways condition中默认分支配置
      const pureGateways = Object.values(gateways).reduce((acc, cur) => {
        if (cur.default_condition) {
          const lineId = cur.default_condition.flow_id;
          if (cur.conditions[lineId]) {
            Vue.delete(cur.conditions, lineId);
          }
        }
        acc[cur.id] = cur;
        return acc;
      }, {});
      // 完整的画布数据
      const pipelineTree = {
        activities,
        canvas_mode,
        constants,
        end_event,
        flows,
        gateways: pureGateways,
        line,
        location: pureLocation,
        outputs,
        start_event,
        stage_canvas_data,
      };
      const validateResult = validatePipeline.isPipelineDataValid(pipelineTree);

      if (!validateResult.result) {
        return new Promise((resolve) => {
          resolve(validateResult);
        });
      }
      const { name } = state;
      const headers = {};
      let url = '';
      if (common) {
        url = 'api/common_template/';
      } else {
        url = 'api/template/';
      }

      if (templateId !== undefined) {
        url = `${url}${templateId}/`;
        headers['X-HTTP-Method-Override'] = 'PATCH';
      }

      // 新增用post, 编辑用put
      return axios[templateId === undefined ? 'post' : 'put'](url, {
        name,
        category,
        timeout,
        description,
        executor_proxy,
        labels: Array.isArray(template_labels) && template_labels.length > 0 ? template_labels.map(label => label.id) : [],
        default_flow_type,
        pipeline_tree: pipelineTree,
        space_id: spaceId,
        version,
        notify_config: {
          notify_type,
          notify_receivers,
        },
        triggers,
        webhook_configs,
        enable_webhook,
      }, {
        headers,
      }).then(response => response.data);
    },
    // 自动排版
    getLayoutedPipeline({}, data) {
      return axios.post('api/template/draw_pipeline/', data).then(response => response.data);
    },
    // 获取内置变量
    loadInternalVariable() {
      return axios.get('api/template/variable/system_variable/').then(response => response.data);
    },
    // 获取节点标签列表
    getLabels({}, data = {}) {
      return axios.get('api/label/', { params: data }).then((response) => {
        if (!('limit' in data)) { // 不传limit代表拉取全量列表
          return { results: response.data.data };
        }
        return response.data.data;
      });
    },
    // 获取变量预览值
    getConstantsPreviewResult({}, data) {
      return axios.post('api/template/variable/get_constant_preview_result/', data).then(response => response.data);
    },
    // 获取全局变量被引用数据
    getVariableCite({}, data) {
      return axios.post('api/template/analysis_constants_ref/', data).then(response => response.data);
    },
    checkKey({}, params) {
      return axios.get('api/template/variable/check_variable_key/', { params }).then(response => response.data);
    },
    getBatchForms({}, data) {
      const { projectId, tpls } = data;
      return axios.post('template/api/batch_form_with_schemes/', {
        project_id: projectId,
        template_list: tpls,
      }).then(response => response.data);
    },
    // 获取所有mako模板操作
    getMakoOperations() {
      return axios.get('mako_operations/').then(response => response.data);
    },
    getVariableFieldExplain() {
      return axios.get('template/api/variable_field_explain/').then(response => response.data);
    },
    // 获取流程是否开启重试和超时控制
    getProcessOpenRetryAndTimeout({}, data) {
      const { id } = data;
      return axios.get(`/api/template/${id}/enable_independent_subprocess/`, { params: data }).then(response => response.data);
    },
    // 获取流程详情公开信息
    getTemplatePublicData({}, data) {
      const { templateId, project__id } = data;
      return axios.get(`/api/template/${templateId}/common_info/`, { params: { project__id } }).then(response => response.data);
    },
    // 获取公共流程详情公开信息
    getCommonTemplatePublicData({}, data) {
      const { templateId } = data;
      return axios.get(`/api/common_template/${templateId}/common_info/`).then(response => response.data);
    },
    // api插件分类列表
    loadUniformCategoryList({ state }, data) {
      const { spaceId, scope_type, scope_value, api_name } = data;
      const { template_id } = state;
      return axios.get(`api/plugin_query/uniform_api/category_list/${spaceId}/`, {
        params: {
          scope_type,
          scope_value,
          api_name,
          template_id,
        },
      }).then(response => response.data);
    },
    // api插件请求列表
    loadUniformApiList({ state }, data) {
      const { spaceId, scope_type, scope_value, offset, limit, category, key, api_name } = data;
      const { template_id } = state;
      return axios.get(`/api/plugin_query/uniform_api/list/${spaceId}/`, {
        params: {
          limit,
          offset,
          scope_type,
          scope_value,
          category,
          key,
          api_name,
          template_id,
        },
      }).then(response => response.data);
    },
    // api插件请求详情
    loadUniformApiMeta({ state }, data) {
      const {  spaceId, meta_url, scope_type, scope_value, taskId, templateId } = data;
      const paramsData = {
        meta_url,
        scope_type,
        scope_value,
      };
      if (taskId) {
        paramsData.task_id = taskId;
      } else {
        paramsData.template_id = templateId ? templateId : state.template_id;
      }
      return axios.get(`/api/plugin_query/uniform_api/meta/${spaceId}/`, {
        params: {
          ...paramsData,
        },
      }).then(response => response.data);
    },
    // 空间相关配置
    loadSpaceRelatedConfig({}, data) {
      return axios.get(`/api/template/${data.id}/get_space_related_configs/`).then(response => response.data);
    },
    // 获取模板mock方案
    getTemplateMockScheme({}, data) {
      return axios.get('/api/template/template_mock_scheme/', { params: data }).then(response => response.data);
    },
    // 更新模板mock方案
    updateTplMockScheme({}, data) {
      const method = data.schemeId ? 'put' : 'post';
      let url = '/api/template/template_mock_scheme/';
      if (data.schemeId) {
        url = `${url}${data.schemeId}/`;
      }
      return axios[method](url, data).then(response => response.data);
    },
    // 获取节点mock数据
    getTemplateMockData({}, data) {
      return axios.get('/api/template/template_mock_data/', { params: data }).then(response => response.data);
    },
    // 设置节点mock数据
    setTemplateMockData({}, data) {
      return axios.post('/api/template/template_mock_data/batch_update/', data).then(response => response.data);
    },
    // 获取模板预览数据
    gerTemplatePreviewData({}, data) {
      const { templateId, version, selectedNodes, is_draft, isInMock = false } = data;
      let requestData = {};
      if (isInMock) {
        requestData = {
          appoint_node_ids: selectedNodes || [],
          is_draft,
        };
      } else {
        requestData = {
          is_all_nodes: true,
        };
      }
      if (version !== undefined && version !== null) {
        requestData.version = version;
      }
      return axios.post(`/api/template/${templateId}/preview_task_tree/`, requestData).then(response => response.data);
    },
    // 获取模板mock任务列表
    getTemplateMockTaskList({}, data) {
      return axios.get('/api/template/template_mock_task/', { params: data }).then(response => response.data);
    },
    getPreviewTaskTree({}, data) {
      return axios.post(`/api/template/${data.templateId}/preview_task_tree/`, data).then(response => response.data);
    },
    // 获取版本号
    getRandomVersion({}, data) {
      return axios.get(`/api/template/${data.templateId}/calculate_version/`, { params: data }).then(response => response.data);
    },
    // 发布模板
    publishTemplate({}, data) {
      const { templateId, version, desc, space_id } = data;
      return axios.post(`/api/template/${templateId}/release_template/`, { version, desc, space_id }).then(response => response.data);
    },
    // 获取草稿版本模板数据
    getDraftVersionData({}, data) {
      return axios.get(`/api/template/${data.templateId}/get_draft_template/`, { params: data }).then(response => response.data);
    },
    // 删除版本快照数据
    deleteVersionSnapshotData({}, data) {
      // id为版本快照id template_id 限制不能删除最新或草稿版本
      const { template_id, space_id, id } = data;
      return axios.post(`/api/template/snapshot/${id}/delete_snapshot/`, { template_id, space_id }).then(response => response.data);
    },
    // 获取指定模板的所有快照信息
    getTemplateVersionSnapshotList({}, data) {
      return axios.get('/api/template/snapshot/', { params: data }).then(response => response.data);
    },
    // 回滚到指定版本
    rollbackToVersion({}, data) {
      const { templateId, space_id, version } = data;
      return axios.post(`/api/template/${templateId}/rollback_template/`, { version, space_id }).then(response => response.data);
    },
    // 获取凭证列表
    getCredentialList({}, data) {
      return axios.get(`/api/template/${data.template_id}/credentials/`, { params: data }).then(response => response.data);
    },
    debugWebhook({}, data) {
      return axios.post('/api/template/verify_webhook_configuration/', data).then(response => response.data);
    },
  },
  getters: {
    // 获取所有模板数据
    getLocalTemplateData(state) {
      return tools.deepClone(state);
    },
    getPipelineTree(state) {
      const {
        activities, constants, end_event, flows, gateways,
        line, location, outputs, start_event, stage_canvas_data,
      } = state;
      // 剔除 location 的冗余字段
      const pureLocation = location.map(item => ({
        id: item.id,
        type: item.type,
        name: item.name,
        stage_name: item.stage_name,
        status: item.status,
        x: item.x,
        y: item.y,
        width: item.width,
        height: item.height,
        parent: item.parent || undefined,
      }));
      return {
        activities,
        constants,
        end_event,
        flows,
        gateways,
        line,
        location: pureLocation,
        outputs,
        start_event,
        stage_canvas_data,
      };
    },
  },
};

export default template;
