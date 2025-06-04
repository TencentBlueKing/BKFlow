import { cloneDeepWith } from 'lodash';
import RenderHightlightConfig from './components/JobAndStageEditSld/components/renderItem/components/renderHightlightConfig.vue';
import RenderLinkConfig from './components/JobAndStageEditSld/components/renderItem/components/renderLinkConfig.vue';
import RenderProgressConfig from './components/JobAndStageEditSld/components/renderItem/components/renderProgressConfig.vue';
import { uuid } from '@/utils/uuid.js';
import templateStore from '@/store/modules/template.js';
export const fontStyleMap = {
  normal: {
    label: '正常',
    value: 'normal',
    getStyle() {
      return {};
    },
  },
  bold: {
    label: '粗体',
    value: 'bold',
    getStyle() {
      return {
        fontWeight: 700,
      };
    },
  },
  italic: {
    label: '斜体',
    value: 'italic',
    getStyle() {
      return {
        fontStyle: 'italic',
      };
    },
  },
};
export const processConfigItem = (configItem) => {
  if (!configItem) return null;

  const { key, value, renders } = configItem;
  const processed = {
    key,
    value,
    hasProgress: false,
    hasLink: false,
    linkUrl: '',
    text: {
      color: '#4D4F56',
      highlightStyle: {},
      highlightBg: '',
    },
    progess: {
      progressColor: '',
      Range: [0, 100],
    },

  };

  if (!renders || !renders.length) {
    return processed;
  }

  // 处理link
  const linkRender = renders.find(r => r.type === 'link');
  if (linkRender) {
    processed.hasLink = true;
    processed.linkUrl = linkRender.url;
  }

  // 处理highlight和progress (只能有一个)
  const highlightRender = renders.find(r => r.type === 'highlight');
  const progressRender = renders.find(r => r.type === 'progress');

  if (progressRender) {
    processed.hasProgress = true;
    processed.progess.Range = progressRender.range || [0, 100];
    processed.progess.progressColor = progressRender.color || '#3A83FF';
  } else if (highlightRender && highlightRender.conditions && highlightRender.conditions.length) {
    // 根据条件确定是否高亮
    const numValue = !isNaN(Number(value)) ? Number(value) : value;

    for (const condition of highlightRender.conditions) {
      let isMatch = false;

      switch (condition.condition) {
        case '>':
          isMatch = numValue > condition.value;
          break;
        case '<':
          isMatch = numValue < condition.value;
          break;
        case '>=':
          isMatch = numValue >= condition.value;
          break;
        case '<=':
          isMatch = numValue <= condition.value;
          break;
        case '=':
          isMatch = value === condition.value;
          break;
      }

      if (isMatch) {
        processed.hasHighlight = true;
        processed.text.color = condition.color || '#4D4F56';
        Object.assign(processed.text.highlightStyle, fontStyleMap[condition.fontStyle || 'normal'].getStyle());
        processed.text.highlightBg = condition.bgColor || '';
        break;
      }
    }
  }

  return processed;
};
export const transformNodeConfigToRenderItems = node => node.config.map(config => processConfigItem(config));

export const getCopyNode = (node) => {
  const tempNode = cloneDeepWith(node);
  tempNode.name = `${tempNode.name}(副本)`;
  tempNode.id = `node${uuid()}`;
  tempNode.jobs?.forEach((job) => {
    job.id = `node${uuid()}`;
    job.nodes = job.nodes.map(copyStepNode);
  });
  if (tempNode.nodes) {
    tempNode.nodes = tempNode.nodes?.map(copyStepNode);
  }

  return tempNode;
};
export const copyStepNode = (node) => {
  const tempNode = cloneDeepWith(node);
  let tempActivites;
  if (templateStore.state.activities[tempNode.id]) {
    tempActivites = cloneDeepWith(templateStore.state.activities[tempNode.id]);
  }
  tempNode.id = `node${uuid()}`;
  templateStore.state.activities[tempNode.id] = tempActivites;
  if (tempActivites)tempActivites.id = tempNode.id;
  return tempNode;
};
export const renderTypeMap = {
  link: {
    label: '超链接',
    value: 'link',
    onlySign: 'link',
    initData: {
      url: '',
    },
    render: RenderLinkConfig,
  },
  highlight: {
    label: '高亮',
    value: 'highlight',
    onlySign: 'textOrProgress',
    initData: {
      conditions: [{
        condition: '',
        fontStyle: 'normal',
        color: '#3A83FF',
        value: 0,
      }],
      tooltips: '',
    },
    render: RenderHightlightConfig,
  },
  progress: {
    label: '进度条',
    value: 'progress',
    onlySign: 'textOrProgress',
    initData: {
      color: '#3A83FF',
      range: ['', ''],
    },
    render: RenderProgressConfig,
  } };
// 根据传入的RenderList判断是否禁用选项项
export const getIsDisabledSelecitonByRenderList = (onlySign, renderList = []) => !!renderList.find(render => renderTypeMap[render.type]?.onlySign === onlySign);
const flowToLine = flow => ({
  id: flow.id,
  source: {
    arrow: 'Right',
    id: flow.source,
  },
  target: {
    arrow: 'Left',
    id: flow.target,
  },
});
const getDefaultActivitie = (id = `node${uuid()}`) => ({
  component: {},
  error_ignorable: false,
  id,
  incoming: [],
  loop: null,
  name: '',
  optional: true,
  outgoing: '',
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
});
export const generatePplTreeByCurrentStageCanvasData = (pipelineTree = {
  activities: {
    n4e0723c31cd3f97857d28366792ddb5: {
      component: {
        code: 'bk_display',
        data: {
          bk_display_message: {
            hook: false,
            need_render: true,
            value: '',
          },
        },
        version: 'v1.0',
      },
      error_ignorable: false,
      id: 'n4e0723c31cd3f97857d28366792ddb5',
      incoming: [
        'lcb234af68bb3cdbb000b7066f6cc7a8',
      ],
      loop: null,
      name: '消息展示',
      optional: true,
      outgoing: 'l8e49ac8084c3914b7431c11c4153cce',
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
      labels: [],
    },
  },
  flows: {
    lcb234af68bb3cdbb000b7066f6cc7a8: {
      id: 'lcb234af68bb3cdbb000b7066f6cc7a8',
      is_default: false,
      source: 'n25358217d1f398884fd984ab1fb43f5',
      target: 'n4e0723c31cd3f97857d28366792ddb5',
    },
  },
  gateways: {
    node5fc5644cd9e3b8b12c5bccbdc556: {
      id: 'node5fc5644cd9e3b8b12c5bccbdc556',
      incoming: [
        'line816b30735454ba053c17bd0d3b9b',
      ],
      name: '',
      outgoing: [
        'lineceb862a6dbb6a5a5af15232e4dc8',
      ],
      type: 'ParallelGateway',
      converge_gateway_id: '',
    },
    node1b1c6fed85c1458c51137baa82ee: {
      id: 'node1b1c6fed85c1458c51137baa82ee',
      incoming: [],
      name: '',
      outgoing: '',
      type: 'ConvergeGateway',
    },
  },
  line: [
    {
      id: 'lcb234af68bb3cdbb000b7066f6cc7a8',
      source: {
        arrow: 'Right',
        id: 'n25358217d1f398884fd984ab1fb43f5',
      },
      target: {
        arrow: 'Left',
        id: 'n4e0723c31cd3f97857d28366792ddb5',
      },
    },
  ],
  location: [
    {
      id: 'n25358217d1f398884fd984ab1fb43f5',
      type: 'startpoint',
      x: 40,
      y: 150,
    },

    {
      id: 'nac32cb979b93343a85163ec2bed49f3',
      type: 'endpoint',
      x: 893,
      y: 174,
    },
  ],
  stage_canvas_data: [],
}) => {
  const { activities, stage_canvas_data: stageCanvasData } = cloneDeepWith(pipelineTree);
  const startPointLocation = {
    id: `node${uuid()}`,
    type: 'startpoint',
    x: 40,
    y: 150,
  };
  const endPointLocation = {
    id: `node${uuid()}`,
    type: 'endpoint',
    x: 893,
    y: 150,
  };
  const newPipelineTree = {
    activities: {},
    flows: {},
    line: [],
    gateways: {},
    location: [],
    start_event: {},
  };

  newPipelineTree.location.push(startPointLocation, endPointLocation);
  // 用于计算localtion的x坐标

  // X轴上两个节点的最小间距
  const NODE_X_GAP = 200;
  // Y轴上两条JOB的间距
  const NODE_Y_GAP = 200;
  let nextStageStartPosion = NODE_X_GAP;
  stageCanvasData.forEach((stage, index) => {
    const maxLengthJobs = Math.max(...stage.jobs.map(job => job.nodes.length));
    const currentStageXOffset = (maxLengthJobs + 1) * NODE_X_GAP;
    const startXPositon = startPointLocation.x + nextStageStartPosion;
    nextStageStartPosion += currentStageXOffset + NODE_X_GAP;
    const endXPositon = startXPositon + currentStageXOffset;
    const statrYPosition = startPointLocation.y;
    endPointLocation.x = endXPositon + NODE_X_GAP;
    // satge的并行网关
    const ParallelGatewayNode = {
      id: `node${uuid()}`,
      incoming: [], // 输入线，连向上一个节点的聚集网关或者起始节点
      name: '',
      outgoing: [], // 输出线，连向Stage的Jobs中的第一个节点
      type: 'ParallelGateway',
      converge_gateway_id: '',
    };
    // 输出线，连向Stage的Jobs中的第一个节点
    const newLine = {
      id: `line${uuid()}`,
      source: '',
      target: ParallelGatewayNode.id,
      is_default: false,
    };

    ParallelGatewayNode.incoming.push(newLine.id);
    newPipelineTree.flows[newLine.id] = newLine;
    newPipelineTree.location.push({
      id: ParallelGatewayNode.id,
      type: 'parallelgateway',
      x: startXPositon,
      y: statrYPosition,
    });

    // 连向上一个节点的聚集网关
    if (stageCanvasData[index - 1]) {
      newLine.source = stageCanvasData[index - 1].ConvergeGatewayNode.id;
      stageCanvasData[index - 1].ConvergeGatewayNode.outgoing = newLine.id;
      newPipelineTree.flows[newLine.id] = newLine;
      // 或者起始节点
    } else {
      newLine.source = startPointLocation.id;
      newPipelineTree.start_event = {
        id: startPointLocation.id,
        incoming: '',
        name: '',
        outgoing: newLine.id,
        type: 'EmptyStartEvent',
        labels: [],
      };
    }
    newPipelineTree.line.push(flowToLine(newLine));
    // satge的聚集网关
    const ConvergeGatewayNode = {
      id: `node${uuid()}`,
      incoming: [], // 输入线，连向Stage的Jobs中的最后一个节点
      name: '',
      outgoing: '', // 输出线，连向下一个Stage的并行网关或者结束节点
      type: 'ConvergeGateway',
    };
    newPipelineTree.location.push({
      id: ConvergeGatewayNode.id,
      type: 'convergegateway',
      x: endXPositon,
      y: statrYPosition,
    });
    // 输出线连向结束节点
    if (index === stageCanvasData.length - 1) {
      const newEndLine = {
        id: `line${uuid()}`,
        source: ConvergeGatewayNode.id,
        target: endPointLocation.id,
        is_default: false,
      };
      ConvergeGatewayNode.outgoing = newEndLine.id;
      newPipelineTree.flows[newEndLine.id] = newEndLine;
      newPipelineTree.line.push(flowToLine(newEndLine));
      newPipelineTree.end_event = {
        id: endPointLocation.id,
        incoming: [newEndLine.id],
        name: '',
        outgoing: '',
        type: 'EmptyEndEvent',
        labels: [],
      };
    }
    stage.ParallelGatewayNode = ParallelGatewayNode;
    stage.ConvergeGatewayNode = ConvergeGatewayNode;
    newPipelineTree.gateways[ParallelGatewayNode.id] = ParallelGatewayNode;
    newPipelineTree.gateways[ConvergeGatewayNode.id] = ConvergeGatewayNode;

    stage.jobs.forEach((job, index) => {
      // 这条JOB上每个节点的间距
      const currentJobNodeGap = currentStageXOffset / (job.nodes.length + 1);
      const currentYPosition = statrYPosition + NODE_Y_GAP * index;
      job.nodes.forEach((node, index) => {
        const newNodeLine =  {
          id: `line${uuid()}`,
          source: '', // 连向上一个节点或者连向网关
          target: node.id,
          is_default: false,
        };
        newPipelineTree.activities[node.id] = activities[node.id] || getDefaultActivitie(node.id);
        newPipelineTree.activities[node.id].incoming = []; // 清空旧连线数据
        newPipelineTree.activities[node.id].outgoing = '';
        newPipelineTree.activities[node.id].incoming.push(newNodeLine.id);
        newPipelineTree.location.push({
          id: node.id,
          type: 'tasknode',
          x: startXPositon + currentJobNodeGap * (index + 1),
          y: currentYPosition - 10,
        });
        newPipelineTree.flows[newNodeLine.id] = newNodeLine;

        // 连向上一个节点
        if (job.nodes[index - 1]) {
          newNodeLine.source = job.nodes[index - 1].id;
          newPipelineTree.activities[job.nodes[index - 1].id].outgoing = newNodeLine.id;
          // 或者连向并行网关
        } else {
          newNodeLine.source = ParallelGatewayNode.id;
          ParallelGatewayNode.outgoing.push(newNodeLine.id);
        }
        newPipelineTree.line.push(flowToLine(newNodeLine));
        // 最后一个节点连向聚集网关
        if (index === job.nodes.length - 1) {
          const lineToEndNode = {
            id: `line${uuid()}`,
            is_default: false,
            source: node.id,
            target: ConvergeGatewayNode.id,
          };
          ConvergeGatewayNode.incoming.push(lineToEndNode.id);
          newPipelineTree.flows[lineToEndNode.id] = lineToEndNode;
          newPipelineTree.activities[node.id].outgoing = lineToEndNode.id;
          newPipelineTree.line.push(flowToLine(lineToEndNode));
        }
      });
    });
  });

  return newPipelineTree;
};
