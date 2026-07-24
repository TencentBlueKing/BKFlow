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
import i18n from '@/config/i18n/index.js';
import { NODE_DICT } from '@/constants/index.js';
import validator from '@/constants/pipelineTreeSchema.js';

/**
 * AJV 校验错误 keyword 到中文提示的映射
 */
const AJV_ERROR_CN_MAP = {
  pattern: '{field}格式不正确',
  required: '{field}为必填字段',
  minLength: '{field}长度不能少于{limit}个字符',
  maxLength: '{field}长度不能超过{limit}个字符',
  type: '{field}类型错误',
  const: '{field}取值不合法',
  enum: '{field}取值不在允许范围内',
  minimum: '{field}不能小于{limit}',
  maximum: '{field}不能大于{limit}',
  additionalProperties: '不允许存在额外字段',
  oneOf: '{field}数据不满足节点类型要求',
  allOf: '{field}数据不满足节点类型要求',
  anyOf: '{field}数据不满足节点类型要求',
};

/**
 * 字段名中文映射
 */
const FIELD_NAME_CN_MAP = {
  id: '节点ID',
  name: '节点名称',
  incoming: '输入连线',
  outgoing: '输出连线',
  type: '节点类型',
  component: '插件配置',
  code: '插件编码',
  data: '插件数据',
  constants: '变量配置',
  pipeline: '子流程配置',
  activities: '任务节点',
  gateways: '网关',
  flows: '连线',
  line: '连线',
  location: '坐标',
  outputs: '输出变量',
  start_event: '开始事件',
  end_event: '结束事件',
  template_id: '模板ID',
  version: '版本号',
  error_ignorable: '是否忽略错误',
  retryable: '是否可重试',
  skippable: '是否可跳过',
  can_retry: '是否可重试',
  isSkipped: '是否可跳过',
  optional: '是否可选',
  conditions: '分支条件',
  evaluate: '分支表达式',
  source: '源节点',
  target: '目标节点',
  is_default: '是否默认连线',
  key: '变量KEY',
  desc: '描述',
  index: '索引',
  show_type: '显示类型',
  source_info: '变量来源信息',
  custom_type: '自定义类型',
  source_tag: '来源标签',
  source_type: '来源类型',
  validation: '校验规则',
  x: 'X坐标',
  y: 'Y坐标',
  state_name: '状态名称',
};

/**
 * 从 dataPath 中解析节点名称
 * 支持嵌套路径，如 .activities['outerId'].pipeline.activities['innerId'].outgoing
 * 返回包含节点名和容器名的对象
 */
function getNodeNameFromPath(dataPath, data) {
  // 匹配路径中所有的 .activities['xxx'] 和 .gateways['xxx']
  const pathSegments = [];
  const actReg = /\.activities\['([^']+)'\]/g;
  const gwReg = /\.gateways\['([^']+)'\]/g;
  let match;
  while ((match = actReg.exec(dataPath)) !== null) {
    pathSegments.push({ type: 'activity', id: match[1] });
  }
  while ((match = gwReg.exec(dataPath)) !== null) {
    pathSegments.push({ type: 'gateway', id: match[1] });
  }
  if (pathSegments.length === 0) {
    // 可能是 start_event / end_event 等顶层字段
    if (dataPath.includes('start_event')) return { nodeName: data.start_event?.id || '开始节点', nodeType: 'start_event' };
    if (dataPath.includes('end_event')) return { nodeName: data.end_event?.id || '结束节点', nodeType: 'end_event' };
    return { nodeName: '' };
  }

  const hasPipeline = dataPath.includes('.pipeline.');
  let nodeName = '';
  let containerName = '';
  let nodeType = '';
  let nodeDisplayName = '';

  // 顶层节点（非嵌套）：activities / gateways 在 data 根层级
  if (!hasPipeline && pathSegments.length === 1) {
    const seg = pathSegments[0];
    if (seg.type === 'activity') {
      const act = data.activities?.[seg.id];
      return { nodeName: seg.id, nodeType: 'activity', nodeDisplayName: act?.name || '', containerName };
    }
    if (seg.type === 'gateway') {
      const gw = data.gateways?.[seg.id];
      return { nodeName: seg.id, nodeType: 'gateway', nodeDisplayName: gw?.name || '', containerName };
    }
  }

  // 嵌套场景（hasPipeline 或 pathSegments.length > 1）
  // 第一个 segment 是最外层容器
  const firstSeg = pathSegments[0];
  if (firstSeg.type === 'activity') {
    const outerAct = data.activities?.[firstSeg.id];
    if (outerAct) {
      containerName = firstSeg.id;

      if (hasPipeline) {
        // 取最后一个 .pipeline. 之后的部分，判断内部出错节点
        const parts = dataPath.split('.pipeline.');
        const lastPart = parts[parts.length - 1];

        if (lastPart.startsWith('start_event')) {
          nodeName = outerAct.pipeline?.['start_event']?.id || '开始节点';
          nodeType = 'start_event';
        } else if (lastPart.startsWith('end_event')) {
          nodeName = outerAct.pipeline?.['end_event']?.id || '结束节点';
          nodeType = 'end_event';
        } else if (pathSegments.length > 1) {
          // 内部嵌套的 activities/gateways
          let currentPipeline = outerAct.pipeline;
          for (let i = 1; i < pathSegments.length; i++) {
            const seg = pathSegments[i];
            if (!currentPipeline) break;
            if (i === pathSegments.length - 1) {
              nodeName = seg.id;
              nodeType = seg.type;
              if (seg.type === 'activity') {
                nodeDisplayName = currentPipeline.activities?.[seg.id]?.name || '';
              } else if (seg.type === 'gateway') {
                nodeDisplayName = currentPipeline.gateways?.[seg.id]?.name || '';
              }
            }
            // 继续向深层遍历（处理多层嵌套）
            if (seg.type === 'activity') {
              currentPipeline = currentPipeline.activities?.[seg.id]?.pipeline;
            }
          }
        }
        // else: pathSegments.length === 1 且 lastPart 不是 start_event/end_event
        // → 错误字段可能为 pipeline 自身或其非节点子字段，nodeName 留空
      } else {
        // pathSegments.length > 1 但没有 .pipeline. 标记（防御性分支，正常不应进入）
        const lastSeg = pathSegments[pathSegments.length - 1];
        nodeName = lastSeg.id;
        nodeType = lastSeg.type;
      }
    }
  }
  return { nodeName, containerName, nodeType, nodeDisplayName };
}

/**
 * 从 dataPath 最后一段提取字段名，如 .outgoing → outgoing
 */
function getFieldNameFromPath(dataPath) {
  const parts = dataPath.replace(/\[/g, '.').replace(/['\]]/g, '')
    .split('.');
  return parts[parts.length - 1] || '';
}

/**
 * 将单个 AJV 错误格式化为中文提示
 */
function formatAjvError(error) {
  const { keyword, dataPath, params } = error;
  const field = getFieldNameFromPath(dataPath);
  const fieldLabel = FIELD_NAME_CN_MAP[field] || field || '数据';
  let cnMsg = AJV_ERROR_CN_MAP[keyword];
  if (!cnMsg) {
    // 未映射的 keyword，使用原始 message
    cnMsg = error.message;
  } else {
    cnMsg = cnMsg
      .replace('{field}', fieldLabel)
      .replace('{limit}', params?.limit ?? params?.minimum ?? params?.maximum ?? '');
  }
  return cnMsg;
}

const NODE_RULE = {
  startpoint: {
    min_in: 0,
    max_in: 0,
    min_out: 1,
    max_out: 1,
    allowed_out: ['tasknode', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'subflow', 'SubCanvas'],
    unique: true,
  },
  endpoint: {
    min_in: 1,
    max_in: 1000,
    min_out: 0,
    max_out: 0,
    allowed_out: [],
    unique: true,
  },
  start: {
    min_in: 0,
    max_in: 0,
    min_out: 1,
    max_out: 1,
    allowed_out: ['tasknode', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'subflow', 'SubCanvas'],
    unique: true,
  },
  end: {
    min_in: 1,
    max_in: 1000,
    min_out: 0,
    max_out: 0,
    allowed_out: [],
    unique: true,
  },
  tasknode: {
    min_in: 1,
    max_in: 1000,
    min_out: 1,
    max_out: 1,
    allowed_out: ['tasknode', 'subflow', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'convergegateway', 'endpoint', 'end', 'SubCanvas'],
    unique: false,
  },
  subflow: {
    min_in: 1,
    max_in: 1000,
    min_out: 1,
    max_out: 1,
    allowed_out: ['tasknode', 'subflow', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'convergegateway', 'endpoint', 'end', 'SubCanvas'],
    unique: false,
  },
  branchgateway: {
    min_in: 1,
    max_in: 1000,
    min_out: 1,
    max_out: 1000,
    allowed_out: ['tasknode', 'subflow', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'convergegateway', 'endpoint', 'end', 'SubCanvas'],
    unique: false,
  },
  conditionalparallelgateway: {
    min_in: 1,
    max_in: 1000,
    min_out: 1,
    max_out: 1000,
    allowed_out: ['tasknode', 'subflow', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'convergegateway', 'endpoint', 'end', 'SubCanvas'],
    unique: false,
  },
  parallelgateway: {
    min_in: 1,
    max_in: 1000,
    min_out: 1,
    max_out: 1000,
    allowed_out: ['tasknode', 'subflow', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'SubCanvas'],
    unique: false,
  },
  convergegateway: {
    min_in: 1,
    max_in: 1000,
    min_out: 1,
    max_out: 1,
    allowed_out: ['tasknode', 'subflow', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'convergegateway', 'endpoint', 'end', 'SubCanvas'],
    unique: false,
  },
  SubCanvas: {
    min_in: 1,
    max_in: 1000,
    min_out: 1,
    max_out: 1,
    allowed_out: ['tasknode', 'subflow', 'branchgateway', 'parallelgateway', 'conditionalparallelgateway', 'convergegateway', 'endpoint', 'end', 'start', 'SubCanvas'],
    unique: false,
  },
};

const nodeTargetMaps = {};
const convergeGwNodes = []; // 流程中所有的汇聚网关
let checkedConvergeNodes = []; // 遍历过程中找到的汇聚网关
let checkedNodes = []; // 遍历过程中找到的所有节点
let nodeBranches = []; // 表示分支的节点

const validatePipeline = {
  /**
     * 判断连线是否合法
     * step:
     *  1.源节点(输出连线最大条数、输出节点是否允许连接)
     *  2.目标节点(输入连线的条数)
     * @param {Object} line
     * @param {Object} data
     */
  isLineValid(line, data) {
    const { lines, locations } = data;
    const { source, target } = line;
    const sourceId = source.id;
    const targetId = target.id;
    const sourceNode = locations.filter(item => item.id === sourceId)[0];
    const targetNode = locations.filter(item => item.id === targetId)[0];
    const sourceRule = NODE_RULE[sourceNode.type];
    const targetRule = NODE_RULE[targetNode.type];
    let sourceLinesLinked = 0;
    let targetLinesLinked = 0;
    let isLoop = false;

    if (source.id === target.id) {
      const i18nText = i18n.t('节点不可连接自身');
      const message = `${NODE_DICT[sourceNode.type]}${i18nText}`;
      return this.getMessage(false, message);
    }
    if (sourceRule.max_out === 0) {
      const i18nText = i18n.t('只能添加输入连线');
      const message = `${NODE_DICT[sourceNode.type]}${i18nText}`;
      return this.getMessage(false, message);
    }

    if (targetRule.max_in === 0) {
      const i18nText = i18n.t('只能添加输出连线');
      const message = `${NODE_DICT[targetNode.type]}${i18nText}`;
      return this.getMessage(false, message);
    }

    if (sourceRule.allowed_out.indexOf(targetNode.type) === -1) {
      const i18nText = i18n.t('不能连接');
      const message = `${NODE_DICT[sourceNode.type]}${i18nText}${NODE_DICT[targetNode.type]}`;
      return this.getMessage(false, message);
    }
    const isSameLine = lines.some((item) => {
      let result = false;
      if (item.source.id === sourceId) {
        sourceLinesLinked += 1;
        if (item.target.id === targetId) {
          result = true;
        }
      }
      if (item.target.id === targetId) {
        targetLinesLinked += 1;
      }
      if (item.source.id === targetId && item.target.id === sourceId && sourceNode.type !== 'branchgateway') {
        isLoop = true;
      }
      return result;
    });

    if (isLoop) {
      const message = i18n.t('相同节点不能回连');
      return this.getMessage(false, message);
    }

    if (isSameLine) {
      const message = i18n.t('重复添加连线');
      return this.getMessage(false, message);
    }
    if (!isSameLine) {
      const i18nText1 = i18n.t('已达到');
      if (sourceLinesLinked >= sourceRule.max_out) {
        const i18nText2 = i18n.t('最大输出连线条数');
        const message = `${i18nText1}${NODE_DICT[sourceNode.type]}${i18nText2}`;
        return this.getMessage(false, message);
      }
      if (targetLinesLinked >= targetRule.max_in) {
        const i18nText2 = i18n.t('最大输入连线条数');
        const message = `${i18nText1}${NODE_DICT[targetNode.type]}${i18nText2}`;
        return this.getMessage(false, message);
      }
    }
    return this.getMessage();
  },
  isLocationValid(loc, data) {
    const rule = NODE_RULE[loc.type];
    if (rule.unique) { // 节点唯一性
      const isLocationOverMount = data.some(item => item.type === loc.type && item.id !== loc.id);
      if (isLocationOverMount) {
        const i18nText = i18n.t('在模板中只能添加一个');
        const message = `${NODE_DICT[loc.type]}${i18nText}`;
        return this.getMessage(false, message);
      }
    }
    return this.getMessage();
  },
  /**
     * 检查是否有节点被 SubCanvas（循环容器）遮挡
     * 通过轴对齐矩形相交检测，判断非循环容器节点是否与循环容器的矩形区域重叠
     * @param {Object} data - { locations, ... }
     * @returns {{ result: boolean, message: string, errorId: string[] }}
     */
  isNodeOverlappedBySubCanvas(data) {
    const { locations } = data;
    const subCanvasNodes = locations.filter(loc => loc.type === 'SubCanvas');
    if (subCanvasNodes.length === 0) {
      return this.getMessage();
    }
    // 获取节点默认尺寸（location 中可能没有 width/height）
    const getNodeRect = (loc) => {
      const taskNodeTypes = ['tasknode', 'subflow'];
      const isSubCanvas = loc.type === 'SubCanvas';
      const isTaskNode = taskNodeTypes.includes(loc.type);
      let defaultWidth;
      let defaultHeight;
      if (isSubCanvas) {
        defaultWidth = 415;
        defaultHeight = 158;
      } else if (isTaskNode) {
        defaultWidth = 154;
        defaultHeight = 54;
      } else {
        defaultWidth = 34;
        defaultHeight = 34;
      }
      return {
        x: loc.x,
        y: loc.y,
        width: loc.width || defaultWidth,
        height: loc.height || defaultHeight,
      };
    };
    // 判断两个轴对齐矩形是否重叠
    const isRectOverlap = (a, b) => a.x < b.x + b.width
        && a.x + a.width > b.x
        && a.y < b.y + b.height
        && a.y + a.height > b.y;
    const overlappedIds = [];
    locations.forEach((node) => {
      if (node.type === 'SubCanvas') return;
      const nodeRect = getNodeRect(node);
      for (const subCanvas of subCanvasNodes) {
        if (isRectOverlap(nodeRect, getNodeRect(subCanvas))) {
          overlappedIds.push(node.id);
          break; // 每个节点只记录一次重叠即可
        }
      }
    });
    if (overlappedIds.length > 0) {
      const names = overlappedIds.map((id) => {
        const loc = locations.find(l => l.id === id);
        return loc ? (loc.name || NODE_DICT[loc.type] || id) : id;
      }).join('、');
      const message = `${i18n.t('节点')}[${names}]${i18n.t('被循环容器遮挡，请移动节点避免被遮挡')}`;
      return this.getMessage(false, message, overlappedIds);
    }
    return this.getMessage();
  },
  /**
     * 画布节点连线数目校验
     * @param {Object} data
     */
  isNodeLineNumValid(data) {
    let message;
    let tasknode = 0;
    let subflow = 0;
    const errorId = [];
    const isLineNumValid = data.locations.every((loc) => {
      const rule = NODE_RULE[loc.type];
      const name = loc.name || NODE_DICT[loc.type];
      let sourceLinesLinked = 0;
      let targetLinesLinked = 0;
      if (loc.type === 'tasknode') {
        tasknode += 1;
      } else if (loc.type === 'subflow') {
        subflow += 1;
      }
      data.lines.forEach((line) => {
        if (line.source.id === loc.id) {
          targetLinesLinked += 1;
        }
        if (line.target.id === loc.id) {
          sourceLinesLinked += 1;
        }
      });
      const i18nText1 = i18n.t('至少需要');
      if (sourceLinesLinked < rule.min_in) {
        const i18nText2 = i18n.t('条输入连线');
        message = `${name}${i18nText1}${rule.min_in}${i18nText2}`;
        errorId.push(loc.id);
        return false;
      }
      if (targetLinesLinked < rule.min_out) {
        const i18nText2 = i18n.t('条输出连线');
        message = `${name}${i18nText1}${rule.min_out}${i18nText2}`;
        errorId.push(loc.id);
        return false;
      }
      return true;
    });

    if (!isLineNumValid) {
      return this.getMessage(false, message, errorId);
    }

    if ((tasknode + subflow) === 0) {
      message = i18n.t('请添加任务节点');
      return this.getMessage(false, message);
    }

    return this.getMessage();
  },
  /**
     * 校验 activities、start_event、end_event、gateways 的 incoming、outging 和 flows 的 source、target 是否对应
     * @params {String} node 节点数据
     * @params {Object} flows 数据
     */
  isFlowValid(node, flows) {
    let message = '';
    const { id, incoming, outgoing } = node;
    const lineGroup = [incoming, outgoing];
    const valid = !lineGroup.some((item, index) => {
      const type = index === 0 ? 'target' : 'source';
      const lines = Array.isArray(item) ? item : [item];
      return lines.some((line) => {
        if (line === '') {
          return false;
        }
        if (!flows[line]) {
          message = `flows.${line} data doesn't exist`;
          return true;
        }
        if (flows[line][type] !== id) {
          message = i18n.t(`flows.${line}.${type} doesn't equal to ${id}`);
          return true;
        }
        return false;
      });
    });

    return { valid, message };
  },
  /**
     * 画布pipeline_tree数据校验
     */
  isPipelineDataValid(data) {
    const { activities, start_event: startEvent, end_event: endEvent, gateways, flows } = data;
    let valid = validator(data);
    let message = '';
    let errorId = '';
    if (!valid) {
      const error = validator.errors[0];
      const { nodeName, containerName, nodeType, nodeDisplayName } = getNodeNameFromPath(error.dataPath, data);
      // 提取 errorId：出错节点或外层容器的 ID
      const pathSegments = [];
      const actReg = /\.activities\['([^']+)'\]/g;
      let match;
      while ((match = actReg.exec(error.dataPath)) !== null) {
        pathSegments.push({ type: 'activity', id: match[1] });
      }
      if (pathSegments.length > 0) {
        errorId = pathSegments[pathSegments.length - 1].id;
      }
      `${nodeName} ${error.dataPath} ${error.message}`;
      const cnMsg = formatAjvError(error);
      // 最终消息：容器名 + 节点名 + 错误描述
      const parts = [];
      if (containerName) {
        parts.push(`循环节点[${containerName}]`);
      }
      if (nodeName) {
        if (nodeType === 'start_event') {
          parts.push(`开始节点[${nodeName}]`);
        } else if (nodeType === 'end_event') {
          parts.push(`结束节点[${nodeName}]`);
        } else if (nodeDisplayName) {
          parts.push(`${nodeDisplayName}节点[${nodeName}]`);
        } else {
          parts.push(`节点[${nodeName}]`);
        }
      }
      parts.push(cnMsg);
      message = parts.join('的');
      return this.getMessage(valid, message, errorId);
    }

    const nodes = [
      startEvent,
      endEvent,
      ...Object.keys(activities).map(id => activities[id]),
      ...Object.keys(gateways).map(id => gateways[id]),
    ];

    valid = !nodes.some((node) => {
      const result = this.isFlowValid(node, flows);
      if (!result.valid) {
        let prefix;
        if (node.type === 'EmptyStartEvent') {
          prefix = `开始节点[${node.id}]`;
        } else if (node.type === 'EmptyEndEvent') {
          prefix = `结束节点[${node.id}]`;
        } else if (node.type === 'SubCanvas') {
          prefix = `${i18n.t('循环节点')}[${node.id}]`;
        } else {
          const name = node.name || '';
          prefix = name ? `${name}节点[${node.id}]` : `节点[${node.id}]`;
        }
        message = `${prefix}：${result.message}`;
        errorId = node.id;
        return true;
      }
      // 检查并行网关/条件并行网关是否和汇聚网关相连
      if (['ParallelGateway', 'ConditionalParallelGateway'].includes(node.type)) {
        checkedNodes = [];
        checkedConvergeNodes = [];
        nodeBranches = new Set([node.id]);
        this.getNodeBranches(node.id, node.id);
        if (nodeBranches.size === 1) {
          return false;
        }
        message = node.type === 'ParallelGateway'
          ? i18n.t('并行网关缺少对应的汇聚网关')
          : i18n.t('条件并行网关缺少对应的汇聚网关');
        errorId = node.id;
        return true;
      }
      return false;
    });

    if (valid) {
      // 递归校验 SubCanvas（循环节点）的子流程
      const subCanvasNodes = Object.keys(activities).filter((id) => {
        const act = activities[id];
        return act.type === 'SubCanvas' && act.pipeline;
      });

      for (const actId of subCanvasNodes) {
        const act = activities[actId];
        const subResult = this.isPipelineDataValid(act.pipeline);
        if (!subResult.result) {
          message = `${i18n.t('循环节点')}[${actId}]${i18n.t('的子流程校验失败')}：${subResult.message}`;
          errorId = subResult.errorId || actId;
          return this.getMessage(false, message, errorId);
        }
      }
    }

    return this.getMessage(valid, message, errorId);
  },
  getNodeBranches(id, branchId) {
    // 重复节点
    if (checkedNodes.includes(id)) {
      nodeBranches.delete(branchId);
      return;
    }
    checkedNodes.push(id);
    // 当前节点所有输出节点
    const targetIds = nodeTargetMaps[id] || [];
    // 多个输出节点
    if (targetIds.length > 1) {
      // 删除旧的分支branchId，添加新的分支
      nodeBranches.delete(branchId);
      targetIds.forEach((targetId) => {
        nodeBranches.add(targetId);
        this.getNodeBranches(targetId, targetId);
      });
    } else if (targetIds.length === 1) {
      // 汇聚网关
      if (convergeGwNodes.includes(id)) {
        // 如果这个汇聚网关之前被找到过，则表示当前分支和其他分支在该汇聚网关会合了，此时需要删掉当前分支branchId
        if (checkedConvergeNodes.includes(id)) {
          nodeBranches.delete(branchId);
        } else {
          // 将未找到过的汇聚网关记录下来
          checkedConvergeNodes.push(id);
          // 如果存在多个分支，则说明当前的汇聚节点不是分支的回合节点，所以需要用找到过的汇聚网关往下继续找
          if (nodeBranches.size > 1) {
            checkedConvergeNodes.forEach((nodeId) => {
              // 汇聚网关只有一个输出节点所以用[0]取输出id
              const targetId = nodeTargetMaps[nodeId][0];
              this.getNodeBranches(targetId, branchId);
            });
          }
        }
      } else {
        const targetId = targetIds[0];
        // 找到结束节点则退出递归
        this.getNodeBranches(targetId, branchId);
      }
    }
  },
  getMessage(result = true, message = '', errorId) {
    return { result, message, errorId };
  },
};

export default validatePipeline;
