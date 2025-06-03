import { uuid } from '@/utils/uuid.js';
export const stage = [
  {
    id: `node${uuid()}`,
    name: '灰度版本确认',
    config: [
      {
        key: '已合入',
        value: '0',
        renders: [
          {
            type: 'link',
            url: 'https://www.baidu.com',
          },
          {
            type: 'highlight',
            conditions: [
              {
                condition: '>',
                value: 10,
                color: '#FF0000',
                fontStyle: 'bold',
              },
              {
                condition: '<',
                value: 10,
                color: '#00FF00',
                fontStyle: 'italic',
              },
            ],
            tooltips: '',
          },
          {
            type: 'progress',
            range: [0, 100],
            color: '#3A83FF',
          },
        ],
      },
    ],
    jobs: [
      {
        id: `node${uuid()}`,
        name: '合入进度',
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
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '已完成',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '已完成',
                        color: '#00AA00',
                        fontStyle: 'bold',
                      },
                      {
                        condition: '===',
                        value: '失败',
                        color: '#FF0000',
                        fontStyle: 'bold',
                      },
                    ],
                  },
                ],
              },
            ],
          },
          {
            id: `node${uuid()}`,
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '失败',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '已完成',
                        color: '#00AA00',
                        fontStyle: 'bold',
                      },
                      {
                        condition: '===',
                        value: '失败',
                        color: '#FF0000',
                        fontStyle: 'bold',
                      },
                    ],
                  },
                  {
                    type: 'link',
                    url: 'https://www.baidu.com/s?wd=help',
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  {
    id: 2,
    name: '合入',
    config: [
      {
        key: '已合入',
        value: '5',
        renders: [
          {
            type: 'highlight',
            conditions: [
              {
                condition: '>=',
                value: 5,
                color: '#00AA00',
                fontStyle: 'bold',
              },
            ],
          },
        ],
      },
    ],
    jobs: [
      {
        id: `node${uuid()}`,
        name: '合入进度',
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
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '已完成',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '已完成',
                        color: '#00AA00',
                        fontStyle: 'bold',
                      },
                    ],
                  },
                ],
              },
            ],
          },
          {
            id: `node${uuid()}`,
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '已完成',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '已完成',
                        color: '#00AA00',
                        fontStyle: 'bold',
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        id: `node${uuid()}`,
        name: '合入进度',
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
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '进行中',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '进行中',
                        color: '#3A83ff',
                        fontStyle: 'normal',
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  {
    id: `node${uuid()}`,
    name: '测试',
    config: [
      {
        key: '进度哈哈',
        value: '60',
        renders: [
          {
            type: 'progress',
            range: [0, 100],
            color: '#3A83FF',
          },
        ],
      },
    ],
    jobs: [
      {
        id: `node${uuid()}`,
        name: '合入进度',
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
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '已完成',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '已完成',
                        color: '#00AA00',
                        fontStyle: 'bold',
                      },
                    ],
                  },
                ],
              },
            ],
          },
          {
            id: `node${uuid()}`,
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '已完成',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '已完成',
                        color: '#00AA00',
                        fontStyle: 'bold',
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  {
    id: `node${uuid()}`,
    name: '发布',
    config: [
      {
        key: '已合入',
        value: '0',
        renders: [
          {
            type: 'link',
            url: 'https://www.baidu.com/s?wd=deploy',
          },
          {
            type: 'highlight',
            conditions: [
              {
                condition: '==',
                value: '0',
                color: '#FF0000',
                fontStyle: 'bold',
              },
            ],
          },
        ],
      },
    ],
    jobs: [
      {
        id: `node${uuid()}`,
        name: '合入进度',
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
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '失败',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '失败',
                        color: '#FF0000',
                        fontStyle: 'bold',
                      },
                    ],
                  },
                ],
              },
            ],
          },
          {
            id: `node${uuid()}`,
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '进行中',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '进行中',
                        color: '#3A83FF',
                        fontStyle: 'normal',
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        id: `node${uuid()}`,
        name: '合入进度',
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
            name: '合入检查-Review人是否存在',
            type: 'check',
            config: [
              {
                key: '状态',
                value: '等待中',
                renders: [
                  {
                    type: 'highlight',
                    conditions: [
                      {
                        condition: '===',
                        value: '等待中',
                        color: '#999999',
                        fontStyle: 'italic',
                      },
                    ],
                  },
                ],
              },
            ],
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

