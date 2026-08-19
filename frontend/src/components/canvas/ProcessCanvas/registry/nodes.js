import { register } from '@antv/x6-vue-shape';
import CustomNode from '../components/nodes/index.vue';
import CustomGroupNode from '../components/nodes/group.vue';

const ports = {
  groups: {
    top: {
      position: 'top',
      attrs: {
        circle: {
          r: 6,
          magnet: true,
          stroke: '#5F95FF',
          strokeWidth: 1,
          fill: '#fff',
          style: {
            visibility: 'hidden',
          },
        },
      },
    },
    right: {
      position: 'right',
      attrs: {
        circle: {
          r: 6,
          magnet: true,
          stroke: '#5F95FF',
          strokeWidth: 1,
          fill: '#fff',
          style: {
            visibility: 'hidden',
          },
        },
      },
    },
    bottom: {
      position: 'bottom',
      attrs: {
        circle: {
          r: 6,
          magnet: true,
          stroke: '#5F95FF',
          strokeWidth: 1,
          fill: '#fff',
          style: {
            visibility: 'hidden',
          },
        },
      },
    },
    left: {
      position: 'left',
      attrs: {
        circle: {
          r: 6,
          magnet: true,
          stroke: '#5F95FF',
          strokeWidth: 1,
          fill: '#fff',
          style: {
            visibility: 'hidden',
          },
        },
      },
    },
  },
  items: [
    {
      id: 'port_top',
      group: 'top',
    },
    {
      id: 'port_right',
      group: 'right',
    },
    {
      id: 'port_bottom',
      group: 'bottom',
    },
    {
      id: 'port_left',
      group: 'left',
    },
  ],
};

// 注册节点
export const registryNodes = (eventMap) => {
  register({
    shape: 'custom-node',
    ports: { ...ports },
    component: {
      render: h => h(CustomNode, {
        on: eventMap(),
      }),
    },
  });
  register({
    shape: 'custom-group-node',
    component: CustomGroupNode,
  });
};
