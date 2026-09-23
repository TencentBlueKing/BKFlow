import { uuid } from '@/utils/uuid.js';
export const stage = [
  {
    id: `node${uuid()}`,
    name: '',
    config: [
    ],
    jobs: [
      {
        id: `node${uuid()}`,
        name: '',
        config: [],
        nodes: [
          {
            id: `node${uuid()}`,
          },
        ],
      },
    ],
  },

];
stage.forEach((stage) => {
  stage.type = 'Stage';
  stage.jobs.forEach((job) => {
    job.type = 'Job';
    job.nodes.forEach((node) => {
      node.type = 'Node';
    });
  });
});
export const getDefaultNewStage = (id = `node${uuid()}`) => ({
  id,
  name: '',
  config: [],
  type: 'Stage',
  jobs: [
    getDefaultNewJob(),
  ],
});
export const getDefaultNewJob = (id = `node${uuid()}`) => ({
  id,
  name: '',
  config: [],
  type: 'Job',
  nodes: [
    getDefaultNewStep(),
  ],
});
export const getDefaultNewStep = (nodeType = 'Node', id = `node${uuid()}`) => ({
  id,
  type: 'Node',
  option: {
    id,
    nodeType,
  },
});

export const ETaskStatusType = {
  SUCCESS: 'FINISHED',
  ERROR: 'FAILED',
  RUNNING: 'RUNNING',
  PENDING: 'READY',
};
export const ETaskStatusTypeMap = {
  [ETaskStatusType.ERROR]: {
    class: 'error',
    name: '失败',
  },
  [ETaskStatusType.RUNNING]: {
    class: 'running',
    name: '执行中',
  },
  [ETaskStatusType.SUCCESS]: {
    class: 'success',
    name: '成功',
  },
  [ETaskStatusType.PENDING]: {
    class: 'pending',
    name: '等待',
  },
};
