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
        config: [
          {
            key: '已规范',
            value: '23',
            renders: [
              {
                type: 'progress',
                range: [0, 42],
                color: '#3A83FF',
              },
            ],
          },
        ],
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
  jobs: [
    getDefaultNewJob(id + 1),
  ],
});
export const getDefaultNewJob = (id = `node${uuid()}`) => ({
  id,
  name: '',
  config: [],
  nodes: [
    getDefaultNewStep(id + 1),
  ],
});
export const getDefaultNewStep = (id = `node${uuid()}`) => ({
  id,
  name: '',
  type: 'check',
  config: {
    id,
  },
}
);

